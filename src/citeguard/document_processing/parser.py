"""
Days 2-3 entry point: raw PDF -> ParsedDocument (pages+paragraphs, sections,
references, in-text citations). Days 6-7 (claim extraction) build on top of
this -- it does NOT yet pair citations with the claims they support.
"""

from __future__ import annotations

from pathlib import Path
from typing import Union

from citeguard.document_processing.citation_extractor import extract_citations
from citeguard.document_processing.models import ParsedDocument
from citeguard.document_processing.pdf_extraction import extract_pages
from citeguard.document_processing.reference_extractor import extract_references
from citeguard.document_processing.section_detector import detect_sections


def parse_document(pdf: Union[str, Path, bytes]) -> ParsedDocument:
    pages = extract_pages(pdf)
    sections = detect_sections(pages)
    references = extract_references(pages, sections)
    citations = extract_citations(pages, sections)
    return ParsedDocument(pages=pages, sections=sections, references=references, citations=citations)
