"""
Document processing entry point: raw PDF -> ParsedDocument, carrying
everything through pages/paragraphs, sections, references, in-text
citations, extracted claims, and the final claim-citation pairs (the
cross-module contract Evidence Retrieval and Verification build on).
"""

from __future__ import annotations

from pathlib import Path
from typing import Union

from citeguard.document_processing.citation_extractor import extract_citations, resolve_citation_sources
from citeguard.document_processing.claim_citation_pairing import build_claim_citation_pairs
from citeguard.document_processing.claim_extractor import extract_claims
from citeguard.document_processing.models import ParsedDocument
from citeguard.document_processing.pdf_extraction import extract_pages
from citeguard.document_processing.reference_extractor import extract_references
from citeguard.document_processing.section_detector import detect_sections
from citeguard.schemas import ClaimCitationPair


def parse_document(pdf: Union[str, Path, bytes]) -> ParsedDocument:
    pages = extract_pages(pdf)
    sections = detect_sections(pages)
    references = extract_references(pages, sections)
    citations = extract_citations(pages, sections)
    resolve_citation_sources(citations, references)  # fills in citation.source_refs, in place
    claims = extract_claims(pages, citations)
    return ParsedDocument(
        pages=pages, sections=sections, references=references, citations=citations, claims=claims
    )


def extract_claim_citation_pairs(pdf: Union[str, Path, bytes]) -> list[ClaimCitationPair]:
    """
    Full Week 1 pipeline: Academic PDF -> Claim-Citation Pairs.
    This is what DocumentProcessor.process() (see interface.py) wraps.
    """
    doc = parse_document(pdf)
    return build_claim_citation_pairs(doc.claims)
