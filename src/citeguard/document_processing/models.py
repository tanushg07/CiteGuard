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


# Citation formats we can currently recognize. See citation_extractor.py.
NUMBERED = "numbered"
AUTHOR_YEAR = "author_year"


@dataclass
class Citation:
    """One in-text citation mention, which may cover multiple sources at once
    (a grouped citation like "[3, 7, 12]" or "(Smith, 2020; Jones, 2019)")."""

    citation_id: str          # unique per mention, e.g. "cit_001"
    raw_text: str              # exactly as it appears, e.g. "[3, 7, 12]"
    citation_format: str       # NUMBERED or AUTHOR_YEAR
    page: int
    paragraph: int
    ref_ids: list[str] = field(default_factory=list)
    # For NUMBERED citations, ref_ids are reference-list numbers, e.g. ["3","7","12"].
    # For AUTHOR_YEAR citations, ref_ids are the raw author/year strings, e.g.
    # ["Smith et al., 2020", "Jones, 2019"], since there's no number to key on
    # until we cross-reference the reference list (a Week 2 hardening task).


@dataclass
class ParsedDocument:
    pages: list[Page]
    sections: list[Section]
    references: list[Reference]
    citations: list[Citation] = field(default_factory=list)

    def paragraph_text(self, page_number: int, paragraph_index: int) -> str | None:
        for page in self.pages:
            if page.page_number == page_number:
                for para in page.paragraphs:
                    if para.index == paragraph_index:
                        return para.text
        return None
