"""
Stage 1: raw PDF -> list[Page], each holding its paragraphs.

Approach: pdfplumber's layout-preserving text extraction reconstructs blank
lines wherever the vertical gap between lines is noticeably larger than the
page's normal line spacing. We treat a run of one or more such blank lines as
a paragraph boundary, then collapse each block's internal line breaks into a
single logical paragraph string.

This is the "basic academic PDF layout" case: single column, normal reading
order top-to-bottom. Multi-column layouts, scanned/OCR'd PDFs, and other
edge cases are explicitly deferred to the Week 2 hardening pass (see
data/test_documents/README.md) -- don't try to handle them here yet.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Union

import pdfplumber

from citeguard.document_processing.models import Page, Paragraph

_BLANK_RUN = re.compile(r"\n\s*\n+")


def extract_pages(pdf: Union[str, Path, bytes]) -> list[Page]:
    """
    Args:
        pdf: path to a PDF file, or raw PDF bytes.

    Returns:
        One Page per PDF page (1-indexed), each with its paragraphs in
        reading order.
    """
    pages: list[Page] = []
    with pdfplumber.open(pdf) as doc:
        for i, plumber_page in enumerate(doc.pages, start=1):
            raw_text = plumber_page.extract_text(layout=True) or ""
            paragraphs = _split_paragraphs(raw_text)
            pages.append(Page(page_number=i, paragraphs=paragraphs, raw_text=raw_text))
    return pages


def _split_paragraphs(raw_text: str) -> list[Paragraph]:
    if not raw_text.strip():
        return []

    blocks = _BLANK_RUN.split(raw_text.strip())
    paragraphs: list[Paragraph] = []
    idx = 0
    for block in blocks:
        text = _collapse_lines(block)
        if not text:
            continue
        idx += 1
        paragraphs.append(Paragraph(index=idx, text=text))
    return paragraphs


def _collapse_lines(block: str) -> str:
    lines = [line.strip() for line in block.splitlines() if line.strip()]
    # collapse repeated internal whitespace left over from PDF word-spacing artifacts
    joined = " ".join(lines)
    return re.sub(r"\s{2,}", " ", joined).strip()
