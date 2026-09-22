import re
import logging
import functools
from typing import List, Optional, Dict, Any

from app.core.models import nli_pipeline

def pipeline(*args, **kwargs):
    return nli_pipeline()
from app.core.schemas import (
    ClaimCitationPair,
    RetrievedEvidence,
    VerificationResult,
    VerificationLabel,
    NumericalComparison,
)

logger = logging.getLogger(__name__)

# HuggingFace NLI model max tokens (safe margin — actual limit is 512)
NLI_MAX_WORDS = 300


def _truncate_to_words(text: str, max_words: int) -> str:
    """Truncate text to at most max_words whitespace-separated words."""
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words])


class Verifier:
    """
    Two-pronged Verification Engine:
    1. Deep Natural Language Inference (NLI) with token-safe truncation.
    2. Exact Numerical & Statistical Entity Verification.
    """

    def __init__(
        self,
        use_nli: bool = True,
        entailment_threshold: float = 0.7,
        contradiction_threshold: float = 0.7,
    ):
        self.use_nli = use_nli
        self.entailment_threshold = entailment_threshold
        self.contradiction_threshold = contradiction_threshold
        self.number_pattern = re.compile(r"\b\d+(?:\.\d+)?\b")

        self.stat_patterns = [
            re.compile(r"\b\d+(?:\.\d+)?\s*(?:%|percent|percentage points?)\b", re.IGNORECASE),
            re.compile(
                r"\b\d+(?:\.\d+)?\s*(?:mg|g|kg|meters?|m|km|cm|mm|hours?|weeks?|days?|years?|months?|seconds?|ms|mins?|billion|million|trillion)\b",
                re.IGNORECASE,
            ),
            re.compile(r"\bp\s*[<>=]\s*0?\.\d+\b", re.IGNORECASE),
            re.compile(r"\b(?:19|20)\d{2}\b"),
            re.compile(r"~?\b\d+(?:\.\d+)?\b"),
        ]

        self.nli_model = None
        if self.use_nli:
            try:
                # The correct model/pipeline for NLI:
                # - task: "text-classification" with a zero-shot/NLI model
                # - return_all_scores=True gives us all three label probabilities
                self.nli_model = pipeline(
                    "text-classification",
                    model="typeform/distilbert-base-uncased-mnli",
                    top_k=None,               # Returns all label scores (replaces deprecated return_all_scores=True)
                    truncation=True,          # Force tokenizer-level truncation
                    max_length=512,           # Hard cap at model's sequence limit
                )
                logger.info("NLI model loaded successfully.")
            except Exception as e:
                logger.warning(f"Could not load NLI model ({e}). Heuristic fallback enabled.")
                self.nli_model = None
                self.use_nli = False

    def _extract_numerical_entities(self, text: str) -> List[str]:
        clean = re.sub(r"\[\s*\d+(?:\s*[,–-]\s*\d+)*\s*\]", "", text)
        clean = re.sub(r"\([^)]*(?:19|20)\d{2}[a-z]?\)", "", clean)
        pattern = r"(?<![\w.])[+-]?\d+(?:,\d{3})*(?:\.\d+)?(?:\s*[- ]?\s*(?:percentage points?|percent|%|mg|kg|km|cm|mm|meters?|hours?|weeks?|days?|years?|months?|seconds?|million|billion|g\b|m\b))?"
        return list(dict.fromkeys(m.group().strip() for m in re.finditer(pattern, clean, re.I)))

    def _quantity(self, entity):
        match = re.match(r"([+-]?[\d,]+(?:\.\d+)?)(.*)", entity.lower())
        value = float(match[1].replace(',', ''))
        unit = match[2].strip(' -').replace('percent', '%')
        unit = {'meters': 'm', 'meter': 'm', 'weeks': 'week', 'days': 'day',
                'years': 'year', 'hours': 'hour', 'seconds': 'second'}.get(unit, unit)
        scales = {'kg': ('g', 1000), 'mg': ('g', .001), 'km': ('m', 1000),
                  'cm': ('m', .01), 'mm': ('m', .001)}
        base, scale = scales.get(unit, (unit, 1))
        return round(value * scale, 9), base

    def _check_numerical_match(self, claim_text, evidence_text):
        return self._check_numerical_alignment(claim_text, evidence_text).is_match

    def _check_numerical_alignment(self, claim_text, evidence_text):
        claim_stats = self._extract_numerical_entities(claim_text)
        evidence_stats = self._extract_numerical_entities(evidence_text)
        values = {self._quantity(e) for e in evidence_stats}
        unmatched = [c for c in claim_stats if self._quantity(c) not in values]
        match = not unmatched if claim_stats else None
        return NumericalComparison(has_numerical_data=bool(claim_stats),
            claim_entities=claim_stats, evidence_entities=evidence_stats, is_match=match,
            details=('Values present in evidence; context still requires NLI.' if match else
                     'Missing or different values: ' + ', '.join(unmatched)) if claim_stats else None)

    @functools.lru_cache(maxsize=2000)
    def _predict_nli_cached(self, evidence_text: str, claim_text: str) -> Optional[List[Dict[str, Any]]]:
        """
        Cached NLI inference. Truncates both inputs before inference to
        prevent IndexError / CUDA OOM on long paragraphs.
        """
        if not self.use_nli or not self.nli_model:
            return None

        # Safe truncation at word level before tokenization
        safe_evidence = _truncate_to_words(evidence_text, NLI_MAX_WORDS)
        safe_claim = _truncate_to_words(claim_text, 80)

        try:
            # HuggingFace text-classification pipeline with two-sequence input:
            # Pass as a list with a single dict using 'text' (premise) and 'text_pair' (hypothesis)
            raw = self.nli_model({"text": safe_evidence, "text_pair": safe_claim})

            # Normalize output: pipeline can return list-of-lists or flat list
            if isinstance(raw, list) and len(raw) > 0 and isinstance(raw[0], list):
                raw = raw[0]

            return raw
        except Exception as e:
            logger.warning(f"NLI inference error: {e}")
            return None

    def _verify_one(self, claim: ClaimCitationPair, evidence_list: List[RetrievedEvidence]) -> VerificationResult:
        """Verifies the claim against candidate evidence passages."""
        if not evidence_list:
            return VerificationResult(
                id=claim.id,
                text=claim.text,
                context=claim.context,
                citation_marker=claim.citation_marker,
                source_document="No Source Document",
                evidence="No matching evidence retrieved.",
                evidence_list=[],
                status=VerificationLabel.INSUFFICIENT,
                confidence=0.0,
                numerical_check=None,
                numerical_comparison=None,
                page_number=claim.page_number,
            )

        top_evidence = evidence_list[0]
        num_match = self._check_numerical_match(claim.text, top_evidence.evidence_text)
        num_comp = self._check_numerical_alignment(claim.text, top_evidence.evidence_text)

        label = VerificationLabel.INSUFFICIENT
        confidence = 0.0

        # Clean claim text: strip citation markers and section numbers for NLI
        clean_claim = re.sub(r"\[\s*\d+(?:\s*[,-]\s*\d+)*\s*\]", "", claim.text)
        clean_claim = re.sub(r"\((?:19|20)\d{2}[a-z]?\)", "", clean_claim)
        clean_claim = re.sub(r"^(?:Section\s+\d+[:\.]?|\d+\.\d*\s+)", "", clean_claim.strip(), flags=re.IGNORECASE).strip()

        if self.use_nli and self.nli_model:
            raw_preds = self._predict_nli_cached(top_evidence.evidence_text, clean_claim)
            if raw_preds is not None and len(raw_preds) > 0:
                score_dict = {p["label"].upper(): p["score"] for p in raw_preds}

                entail_score = score_dict.get("ENTAILMENT", 0.0)
                contra_score = score_dict.get("CONTRADICTION", 0.0)

                best_pred = max(raw_preds, key=lambda x: x["score"])
                confidence = float(best_pred["score"])

                if contra_score >= self.contradiction_threshold:
                    label = VerificationLabel.CONTRADICTED
                    confidence = contra_score
                elif entail_score >= self.entailment_threshold:
                    label = VerificationLabel.SUPPORTED
                    confidence = entail_score
                else:
                    label = VerificationLabel.INSUFFICIENT
            else:
                label = VerificationLabel.INSUFFICIENT
        else:
            # Without NLI, only near-verbatim evidence can establish support.
            normalized_claim = re.sub(r"[^a-z0-9 ]", "", clean_claim.lower()).strip()
            normalized_evidence = re.sub(r"[^a-z0-9 ]", "", top_evidence.evidence_text.lower())
            label = VerificationLabel.SUPPORTED if normalized_claim and normalized_claim in normalized_evidence else VerificationLabel.INSUFFICIENT
            confidence = 0.5

        # If NLI says SUPPORTED but hard numbers don't match, downgrade to NUMERICAL_MISMATCH
        if label == VerificationLabel.SUPPORTED and num_match is False:
            label = VerificationLabel.NUMERICAL_MISMATCH

        conf_val = round(confidence * 100, 1) if confidence <= 1.0 else round(confidence, 1)

        return VerificationResult(
            id=claim.id,
            text=claim.text,
            context=claim.context,
            citation_marker=claim.citation_marker,
            source_document=top_evidence.source_document,
            evidence=top_evidence.evidence_text,
            evidence_list=evidence_list,
            status=label,
            confidence=conf_val,
            numerical_check=num_comp.details,
            numerical_comparison=num_comp,
            page_number=claim.page_number,
        )

    def verify(self, claim, evidence_list):
        if not evidence_list:
            return self._verify_one(claim, [])
        results = [self._verify_one(claim, [e]) for e in evidence_list]
        decisive = [r for r in results if r.status != VerificationLabel.INSUFFICIENT]
        if {r.status for r in decisive} >= {VerificationLabel.SUPPORTED, VerificationLabel.CONTRADICTED}:
            result = max(results, key=lambda r: r.confidence)
            result.status = VerificationLabel.INSUFFICIENT
            result.confidence = 0
        else:
            result = max(decisive or results, key=lambda r: r.confidence)
        result.evidence_list = evidence_list
        return result
