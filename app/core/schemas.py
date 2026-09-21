from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum

class VerificationLabel(str, Enum):
    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    INSUFFICIENT = "INSUFFICIENT"

class ClaimCitationPair(BaseModel):
    id: str = Field(..., description="Unique identifier for the claim")
    text: str = Field(..., description="The text of the claim being made")
    citation_marker: str = Field(..., description="The citation marker in the text (e.g., [1] or (Smith, 2020))")
    page_number: int = Field(..., description="Page number where the claim was found")

class RetrievedEvidence(BaseModel):
    claim_id: str = Field(..., description="The ID of the claim this evidence is for")
    source_document: str = Field(..., description="The name or path of the source document")
    evidence_text: str = Field(..., description="The retrieved chunk of text from the source")
    relevance_score: float = Field(..., description="The retrieval/reranker relevance score")

class VerificationResult(BaseModel):
    claim_id: str = Field(..., description="The ID of the claim being verified")
    claim_text: str = Field(..., description="The text of the claim being verified")
    evidence: List[RetrievedEvidence] = Field(default_factory=list, description="List of evidence chunks used")
    nli_label: VerificationLabel = Field(..., description="The predicted NLI label")
    nli_confidence: float = Field(..., description="The confidence score of the NLI prediction")
    numerical_match: Optional[bool] = Field(None, description="Whether numerical values in claim match evidence")
