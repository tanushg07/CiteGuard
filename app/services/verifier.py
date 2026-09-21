import re
import logging
import functools
from typing import List, Optional, Tuple, Dict, Any
from transformers import pipeline
from app.core.schemas import (
    ClaimCitationPair, 
    RetrievedEvidence, 
    VerificationResult, 
    VerificationLabel, 
    NumericalComparison
)

logger = logging.getLogger(__name__)

class Verifier:
    """
    Two-pronged Verification Engine:
    1. Deep Natural Language Inference (NLI).
    2. Exact Numerical & Statistical Entity Verification.
    """
    def __init__(self, use_nli: bool = True, entailment_threshold: float = 0.7, contradiction_threshold: float = 0.7):
        self.use_nli = use_nli
        self.entailment_threshold = entailment_threshold
        self.contradiction_threshold = contradiction_threshold
        self.number_pattern = re.compile(r'\b\d+(?:\.\d+)?\b')

        self.stat_patterns = [
            re.compile(r'\b\d+(?:\.\d+)?\s*(?:%|percent|percentage points?)\b', re.IGNORECASE),
            re.compile(r'\b\d+(?:\.\d+)?\s*(?:mg|g|kg|meters?|m|km|cm|mm|hours?|weeks?|days?|years?|months?|seconds?|ms|mins?|billion|million|trillion|k|m)\b', re.IGNORECASE),
            re.compile(r'\bp\s*[<>=]\s*0?\.\d+\b', re.IGNORECASE),
            re.compile(r'\b(?:19|20)\d{2}\b'),
            re.compile(r'\b\d+(?:\.\d+)?\b')
        ]

        if self.use_nli:
            try:
                self.nli_model = pipeline(
                    "text-classification",
                    model="typeform/distilbert-base-uncased-mnli",
                    return_all_scores=True
                )
            except Exception as e:
                logger.warning(f"Could not load NLI model ({e}). Fallback enabled.")
                self.nli_model = None
                self.use_nli = False
        else:
            self.nli_model = None

    def _extract_numerical_entities(self, text: str) -> List[str]:
        """Extracts significant numerical/statistical tokens, ignoring citation markers and section numbers."""
        clean_text = re.sub(r'\[\s*\d+(?:\s*[,-]\s*\d+)*\s*\]', '', text)
        clean_text = re.sub(r'\((?:19|20)\d{2}[a-z]?\)', '', clean_text)
        clean_text = re.sub(r'^(?:Section\s+\d+[:\.]?|\d+\.\d*\s+)', '', clean_text.strip(), flags=re.IGNORECASE)
        
        found = []
        for pat in self.stat_patterns:
            matches = pat.findall(clean_text)
            for m in matches:
                m_str = m.strip()
                if m_str not in found:
                    found.append(m_str)
        return found

    def _check_numerical_match(self, claim_text: str, evidence_text: str) -> Optional[bool]:
        """
        Extracts numbers from the claim. If numbers exist, checks if they are also
        present in the evidence text.
        """
        clean_claim = re.sub(r'\[\s*\d+(?:\s*[,-]\s*\d+)*\s*\]', '', claim_text)
        clean_claim = re.sub(r'^(?:Section\s+\d+[:\.]?|\d+\.\d*\s+)', '', clean_claim.strip(), flags=re.IGNORECASE)
        claim_numbers = set(self.number_pattern.findall(clean_claim))
        if not claim_numbers:
            return None
        evidence_numbers = set(self.number_pattern.findall(evidence_text))
        return claim_numbers.issubset(evidence_numbers)

    def _check_numerical_alignment(self, claim_text: str, evidence_text: str) -> NumericalComparison:
        """
        Structured numerical comparison with detailed diagnostic string.
        """
        claim_stats = self._extract_numerical_entities(claim_text)
        evidence_stats = self._extract_numerical_entities(evidence_text)

        if not claim_stats:
            return NumericalComparison(
                has_numerical_data=False,
                claim_entities=[],
                evidence_entities=evidence_stats,
                is_match=None,
                details=None
            )

        matched = []
        unmatched = []
        for c in claim_stats:
            raw_num = re.search(r'\d+(?:\.\d+)?', c)
            raw_val = raw_num.group(0) if raw_num else c
            if c.lower() in evidence_text.lower() or raw_val in evidence_text:
                matched.append(c)
            else:
                unmatched.append(c)

        if not unmatched:
            details = f"Claim: '{', '.join(claim_stats)}' | Source: '{', '.join(matched)}' -> Match"
            return NumericalComparison(
                has_numerical_data=True,
                claim_entities=claim_stats,
                evidence_entities=evidence_stats,
                is_match=True,
                details=details
            )
        elif matched:
            details = f"Claim: '{', '.join(claim_stats)}' | Source: '{', '.join(evidence_stats[:3]) if evidence_stats else 'None'}' -> Divergence"
            return NumericalComparison(
                has_numerical_data=True,
                claim_entities=claim_stats,
                evidence_entities=evidence_stats,
                is_match=False,
                details=details
            )
        else:
            details = f"Claim: '{', '.join(claim_stats)}' | Source: '{', '.join(evidence_stats[:3]) if evidence_stats else 'No matching stats'}' -> Mismatch"
            return NumericalComparison(
                has_numerical_data=True,
                claim_entities=claim_stats,
                evidence_entities=evidence_stats,
                is_match=False,
                details=details
            )

    @functools.lru_cache(maxsize=1000)
    def _predict_nli(self, evidence_text: str, claim_text: str) -> Optional[List[Dict[str, Any]]]:
        if not self.use_nli or not self.nli_model:
            return None
        try:
            return self.nli_model({"text": evidence_text, "text_pair": claim_text})
        except Exception as e:
            logger.warning(f"NLI model inference failed: {str(e)}")
            return None

    def verify(self, claim: ClaimCitationPair, evidence_list: List[RetrievedEvidence]) -> VerificationResult:
        """
        Verifies the claim against candidate evidence.
        """
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
                confidence=100.0,
                numerical_check=None,
                numerical_comparison=None,
                page_number=claim.page_number
            )

        top_evidence = evidence_list[0]
        num_match = self._check_numerical_match(claim.text, top_evidence.evidence_text)
        num_comp = self._check_numerical_alignment(claim.text, top_evidence.evidence_text)

        label = VerificationLabel.INSUFFICIENT
        confidence = 80.0

        # Calculate semantic word overlap
        clean_claim = re.sub(r'\[\s*\d+(?:\s*[,-]\s*\d+)*\s*\]', '', claim.text)
        clean_claim = re.sub(r'\((?:19|20)\d{2}[a-z]?\)', '', clean_claim)
        clean_claim = re.sub(r'^(?:Section\s+\d+[:\.]?|\d+\.\d*\s+)', '', clean_claim.strip(), flags=re.IGNORECASE).strip()

        claim_words = set(re.findall(r'\b\w{3,}\b', clean_claim.lower()))
        ev_words = set(re.findall(r'\b\w{3,}\b', top_evidence.evidence_text.lower()))
        overlap = len(claim_words.intersection(ev_words)) / len(claim_words) if claim_words else 0.0

        # Polarity & Negation check
        neg_patterns = {"no", "not", "none", "neither", "never", "without", "failed", "fails", "fail", "unable"}
        claim_has_neg = any(w in neg_patterns for w in re.findall(r'\b\w+\b', clean_claim.lower()))
        ev_has_neg = any(w in neg_patterns for w in re.findall(r'\b\w+\b', top_evidence.evidence_text.lower()))

        if self.use_nli and self.nli_model:
            raw_preds = self._predict_nli(top_evidence.evidence_text, clean_claim)
            if raw_preds is not None:
                if isinstance(raw_preds, list) and len(raw_preds) > 0 and isinstance(raw_preds[0], list):
                    raw_preds = raw_preds[0]

                score_dict = {p['label'].upper(): p['score'] for p in raw_preds}

                entail_score = score_dict.get('ENTAILMENT', 0.0)
                contra_score = score_dict.get('CONTRADICTION', 0.0)
                neutral_score = score_dict.get('NEUTRAL', 0.0)

                best_pred = max(raw_preds, key=lambda x: x['score'])
                pred_label = best_pred['label'].upper()
                confidence = float(best_pred['score'])

                if "CONTRADICT" in pred_label or contra_score > self.contradiction_threshold:
                    label = VerificationLabel.CONTRADICTED
                    confidence = max(contra_score, confidence)
                elif contra_score > 0.08 and contra_score > (entail_score * 10) and claim_has_neg != ev_has_neg:
                    # Negation polarity mismatch with high contradiction ratio
                    label = VerificationLabel.CONTRADICTED
                    confidence = 0.94
                elif "ENTAIL" in pred_label or entail_score > self.entailment_threshold:
                    label = VerificationLabel.SUPPORTED
                    confidence = max(entail_score, confidence)
                elif overlap > 0.4 and (num_comp.is_match is True or num_comp.is_match is None) and contra_score < 0.05 and not (claim_has_neg != ev_has_neg):
                    label = VerificationLabel.SUPPORTED
                    confidence = max(0.92, 0.7 + overlap * 0.3)
                else:
                    label = VerificationLabel.INSUFFICIENT

            else:
                label = VerificationLabel.INSUFFICIENT
        else:
            # Fallback heuristic
            if overlap > 0.45:
                if claim_has_neg != ev_has_neg:
                    label = VerificationLabel.CONTRADICTED
                    confidence = 0.92
                else:
                    label = VerificationLabel.SUPPORTED
                    confidence = 0.90
            elif overlap > 0.2:
                label = VerificationLabel.INSUFFICIENT
                confidence = 0.75
            else:
                label = VerificationLabel.INSUFFICIENT
                confidence = 0.65

        # If NLI says SUPPORTED but numerical match is False, downgrade to CONTRADICTED
        if label == VerificationLabel.SUPPORTED and num_match is False:
            label = VerificationLabel.CONTRADICTED

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
            page_number=claim.page_number
        )
