"""
Days 2-3 entry point: raw PDF -> ParsedDocument (pages+paragraphs, sections,
references). This is the foundation Days 4-5 (citation extraction) and
Days 6-7 (claim extraction) build on top of -- it does NOT yet look at
in-text citations or claims at all.
"""

from __future__ import annotations

from pathlib import Path
from typing import Union

from citeguard.document_processing.models import ParsedDocument
from citeguard.document_processing.pdf_extraction import extract_pages
from citeguard.document_processing.reference_extractor import extract_references
from citeguard.document_processing.section_detector import detect_sections


def parse_document(pdf: Union[str, Path, bytes]) -> ParsedDocument:
    pages = extract_pages(pdf)
    sections = detect_sections(pages)
    references = extract_references(pages, sections)
    return ParsedDocument(pages=pages, sections=sections, references=references)
