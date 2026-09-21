import re
import logging
from typing import List, Optional
from transformers import pipeline
from app.core.schemas import ClaimCitationPair, RetrievedEvidence, VerificationResult, VerificationLabel

logger = logging.getLogger(__name__)

class Verifier:
    """
    Verifies a claim against retrieved evidence using NLI (Natural Language Inference)
    and a simple numerical matching heuristic.
    """
    def __init__(self, use_nli: bool = True):
        self.use_nli = use_nli
        self.number_pattern = re.compile(r'\b\d+(?:\.\d+)?\b')
        
        if self.use_nli:
            logger.info("Loading NLI model...")
            # Using a fast distilbert model trained on MNLI for the MVP
            self.nli_model = pipeline(
                "text-classification", 
                model="typeform/distilbert-base-uncased-mnli", 
                return_all_scores=True
            )
        else:
            self.nli_model = None

    def _check_numerical_match(self, claim_text: str, evidence_text: str) -> Optional[bool]:
        """
        Extracts numbers from the claim. If numbers exist, checks if they are also
        present in the evidence text. Returns True if all claim numbers are found,
        False if any are missing, and None if the claim has no numbers.
        """
        claim_numbers = set(self.number_pattern.findall(claim_text))
        
        if not claim_numbers:
            return None
            
        evidence_numbers = set(self.number_pattern.findall(evidence_text))
        
        # Check if all numbers in the claim exist in the evidence
        return claim_numbers.issubset(evidence_numbers)

    def verify(self, claim: ClaimCitationPair, evidence_list: List[RetrievedEvidence]) -> VerificationResult:
        """
        Verifies the claim against the top evidence chunk.
        """
        if not evidence_list:
            # No evidence found at all
            return VerificationResult(
                claim_id=claim.id,
                claim_text=claim.text,
                evidence=[],
                nli_label=VerificationLabel.INSUFFICIENT,
                nli_confidence=1.0,
                numerical_match=None
            )
            
        # For simplicity in MVP, we evaluate against the #1 top-ranked evidence
        # A more advanced approach would evaluate all and aggregate.
        top_evidence = evidence_list[0]
        
        # 1. Numerical Check
        num_match = self._check_numerical_match(claim.text, top_evidence.evidence_text)
        
        # 2. NLI Check
        label = VerificationLabel.INSUFFICIENT
        confidence = 0.0
        
        if self.use_nli and self.nli_model:
            # MNLI standard: Premise = Evidence, Hypothesis = Claim
            # Distilbert-mnli format: "evidence_text [SEP] claim_text" 
            # But the pipeline handles string pairs:
            # For typeform/distilbert-base-uncased-mnli, labels are: 'ENTAILMENT', 'NEUTRAL', 'CONTRADICTION'
            try:
                result = self.nli_model({"text": top_evidence.evidence_text, "text_pair": claim.text})
                # result is usually a list of dicts: [{'label': 'ENTAILMENT', 'score': 0.9}, ...]
                # Let's find the highest scoring label
                best_pred = max(result, key=lambda x: x['score'])
                pred_label = best_pred['label'].upper()
                confidence = float(best_pred['score'])
                
                if "ENTAIL" in pred_label:
                    label = VerificationLabel.SUPPORTED
                elif "CONTRADICT" in pred_label:
                    label = VerificationLabel.CONTRADICTED
                else:
                    label = VerificationLabel.INSUFFICIENT
                    
            except Exception as e:
                logger.error(f"NLI model inference failed: {str(e)}")
                # Fallback to insufficient
                label = VerificationLabel.INSUFFICIENT
        
        # Optional: Rule-based override
        # If the NLI model says SUPPORTED but numerical match is False, downgrade it.
        if label == VerificationLabel.SUPPORTED and num_match is False:
            label = VerificationLabel.CONTRADICTED
            
        return VerificationResult(
            claim_id=claim.id,
            claim_text=claim.text,
            evidence=evidence_list,
            nli_label=label,
            nli_confidence=confidence,
            numerical_match=num_match
        )
