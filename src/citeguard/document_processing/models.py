"""
Internal data structures for the document_processing module.

These are NOT the cross-module contract (that's citeguard.schemas). Page /
Paragraph / Section / Reference are intermediate representations used while
building up to a ClaimCitationPair -- other modules never see these directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Paragraph:
    index: int          # 1-indexed, position within the page
    text: str


@dataclass
class Page:
    page_number: int    # 1-indexed
    paragraphs: list[Paragraph] = field(default_factory=list)
    raw_text: str = ""


@dataclass
class Section:
    name: str            # normalized, e.g. "Introduction", "References"
    start_page: int
    start_paragraph: int


@dataclass
class Reference:
    ref_id: str           # e.g. "1" for a "[1]"-style entry
    raw_text: str


@dataclass
class ParsedDocument:
    pages: list[Page]
    sections: list[Section]
    references: list[Reference]

    def paragraph_text(self, page_number: int, paragraph_index: int) -> str | None:
        for page in self.pages:
            if page.page_number == page_number:
                for para in page.paragraphs:
                    if para.index == paragraph_index:
                        return para.text
        return None
