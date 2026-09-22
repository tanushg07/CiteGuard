"""
Shared data contracts for CiteGuard.

Every module (document_processing, evidence_retrieval, verification, backend)
imports these instead of inventing its own dicts. If you need a new field,
add it here first and tell the team in the group chat / issue tracker —
don't silently change shapes downstream modules depend on.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 1. Document Processing (Jagadish) output
# ---------------------------------------------------------------------------

class Citation(BaseModel):
    citation_id: str
    raw_text: str                     # e.g. "[12]" or "(Smith et al., 2020)"
    page: int
    paragraph: Optional[int] = None
    source_ref: Optional[str] = None  # resolved reference-list entry, if known


class Claim(BaseModel):
    claim_id: str
    text: str
    page: int
    paragraph: Optional[int] = None


class ClaimCitationPair(BaseModel):
    claim_id: str
    claim: str
    citation_id: str
    page: int
    paragraph: Optional[int] = None


# ---------------------------------------------------------------------------
# 2. Evidence Retrieval (Jayant) output
# ---------------------------------------------------------------------------

class EvidencePassage(BaseModel):
    text: str
    score: float
    page: Optional[int] = None
    source_doc_id: Optional[str] = None


class EvidenceResult(BaseModel):
    claim_id: str
    evidence: list[EvidencePassage] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 3. Verification (Dhanush) output
# ---------------------------------------------------------------------------

class VerificationLabel(str, Enum):
    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    INSUFFICIENT = "INSUFFICIENT"


class VerificationResult(BaseModel):
    claim_id: str
    label: VerificationLabel
    confidence: float
    numerical_check_passed: Optional[bool] = None
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# 4. Backend (Tanush) aggregate output
# ---------------------------------------------------------------------------

class CitationRecord(BaseModel):
    """One row of the final report: a claim, its citation, evidence, and verdict."""
    claim_citation: ClaimCitationPair
    evidence: EvidenceResult
    verification: VerificationResult


class CitationValidityReport(BaseModel):
    document_id: str
    records: list[CitationRecord] = Field(default_factory=list)
