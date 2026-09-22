from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum

class VerificationLabel(str, Enum):
    SUPPORTED = "Supported"
    CONTRADICTED = "Contradicted"
    INSUFFICIENT = "Unrelated"
    NUMERICAL_MISMATCH = "Numerical Mismatch"

class ReferenceMetadata(BaseModel):
    raw_reference: str = ""
    provider: str = "bibliography"
    status: str = "not_found"
    title: Optional[str] = None
    doi: Optional[str] = None
    abstract: Optional[str] = None
    venue: Optional[str] = None
    authors: List[str] = Field(default_factory=list)
    year: Optional[int] = None


class ClaimCitationPair(BaseModel):
    reference_metadata: Optional[ReferenceMetadata] = None
    id: str = Field(..., description="Unique identifier for the claim")
    text: str = Field(..., description="The extracted sentence/claim text")
    context: str = Field(default="", description="The surrounding paragraph context")
    citation_marker: str = Field(..., description="The citation marker (e.g. [12], (Vaswani et al., 2017))")
    page_number: int = Field(default=1, description="Page number where the claim was found")
    section: Optional[str] = Field(default=None, description="Section heading if detected")

class NumericalComparison(BaseModel):
    has_numerical_data: bool = Field(default=False)
    claim_entities: List[str] = Field(default_factory=list)
    evidence_entities: List[str] = Field(default_factory=list)
    is_match: Optional[bool] = Field(default=None)
    details: Optional[str] = Field(default=None)

class RetrievedEvidence(BaseModel):
    page_number: int = 1
    claim_id: str = Field(..., description="The ID of the claim this evidence is for")
    source_document: str = Field(..., description="The name or identifier of the source document")
    evidence_text: str = Field(..., description="The retrieved chunk of text from the source")
    relevance_score: float = Field(..., description="The retrieval/reranker relevance score")
    source_citation: Optional[str] = Field(default=None, description="Bibliographic reference citation")

class VerificationResult(BaseModel):
    reference_metadata: Optional[ReferenceMetadata] = None
    id: str = Field(..., description="Claim ID")
    text: str = Field(..., description="Claim text")
    context: str = Field(default="", description="Paragraph context in target document")
    citation_marker: str = Field(default="", description="Citation marker in text")
    source_document: str = Field(default="Source Document", description="Source document or reference")
    evidence: str = Field(default="", description="Best retrieved evidence passage")
    evidence_list: List[RetrievedEvidence] = Field(default_factory=list, description="All retrieved candidates")
    status: VerificationLabel = Field(..., description="Final verification status")
    confidence: float = Field(default=80.0, description="Confidence percentage 0-100 or float")
    numerical_check: Optional[str] = Field(default=None, description="Numerical comparison summary string")
    numerical_comparison: Optional[NumericalComparison] = Field(default=None, description="Structured numerical check")
    page_number: int = Field(default=1)

    # Backwards compatibility properties
    @property
    def claim_id(self) -> str:
        return self.id

    @property
    def claim_text(self) -> str:
        return self.text

    @property
    def nli_label(self) -> VerificationLabel:
        return self.status

    @property
    def nli_confidence(self) -> float:
        return round(self.confidence / 100.0, 2) if self.confidence > 1.0 else self.confidence

    @property
    def numerical_match(self) -> Optional[bool]:
        if self.numerical_comparison is not None:
            return self.numerical_comparison.is_match
        return None

class DocumentSummary(BaseModel):
    document_name: str
    total_claims: int
    supported_count: int
    contradicted_count: int
    unrelated_count: int
    numerical_mismatch_count: int
    supported_percentage: float
    average_confidence: float
    processing_time_seconds: float

class AnalysisResponse(BaseModel):
    job_id: str
    summary: DocumentSummary
    claims: List[VerificationResult]
    status: str = "completed"
    warnings: List[str] = Field(default_factory=list)
    engines: Dict[str, str] = Field(default_factory=dict)

class PipelineStepUpdate(BaseModel):
    step_id: int
    name: str
    status: str  # "pending" | "loading" | "complete" | "error"
    detail: Optional[str] = None
    claims_found: Optional[int] = None
    progress_percentage: int = 0
