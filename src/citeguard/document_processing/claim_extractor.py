"""
Stage 5 (Days 6-7), part 1: Sentence -> Citation Detection -> Claim Extraction.

A "claim" in this pipeline is any sentence that contains at least one in-text
citation -- an uncited sentence has nothing to verify, so we don't extract it
as a claim. A sentence with a grouped citation "[3, 7, 12]" becomes ONE claim
carrying all three citation_ids (Days 6-7's pairing step, in
claim_citation_pairing.py, is what fans that out into multiple
ClaimCitationPair rows).

Sentence splitting is a simple regex heuristic: split after ./!/? when
followed by whitespace and then a capital letter, quote, or opening paren.
This deliberately does NOT split on "et al." or similar abbreviations,
since those are always followed by a lowercase word or a citation year, not
a capital letter -- verified against every citation format we detect.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from citeguard.document_processing.models import Citation, Page

_SENTENCE_BOUNDARY = re.compile(r'(?<=[.!?])\s+(?=[A-Z"\'(])')


@dataclass
class Claim:
    claim_id: str
    text: str              # the sentence, with citation markers stripped out
    page: int
    paragraph: int
    citation_ids: list[str] = field(default_factory=list)  # Citation.citation_id values found in this sentence


def extract_claims(pages: list[Page], citations: list[Citation]) -> list[Claim]:
    """
    Args:
        pages: from pdf_extraction.extract_pages()
        citations: from citation_extractor.extract_citations() -- run against
            the SAME pages/sections so page/paragraph numbers line up.

    Returns:
        One Claim per cited sentence, in reading order.
    """
    citations_by_location: dict[tuple[int, int], list[Citation]] = {}
    for citation in citations:
        citations_by_location.setdefault((citation.page, citation.paragraph), []).append(citation)

    claims: list[Claim] = []
    counter = 0

    for page in pages:
        for para in page.paragraphs:
            location_citations = citations_by_location.get((page.page_number, para.index))
            if not location_citations:
                continue  # no citations in this paragraph at all -- skip fast

            for sentence in _split_sentences(para.text):
                matched = [c for c in location_citations if c.raw_text in sentence]
                if not matched:
                    continue  # this particular sentence isn't the one carrying the citation

                counter += 1
                claims.append(
                    Claim(
                        claim_id=f"claim_{counter:03d}",
                        text=_strip_citation_markers(sentence, matched),
                        page=page.page_number,
                        paragraph=para.index,
                        citation_ids=[c.citation_id for c in matched],
                    )
                )

    return claims


def _split_sentences(paragraph_text: str) -> list[str]:
    parts = _SENTENCE_BOUNDARY.split(paragraph_text.strip())
    return [p.strip() for p in parts if p.strip()]


def _strip_citation_markers(sentence: str, citations: list[Citation]) -> str:
    """Remove the citation's raw text (e.g. "[3, 7]" or "(Smith, 2020)") from
    the sentence, leaving a clean claim suitable for downstream NLI/evidence
    comparison, and tidy up the whitespace/punctuation left behind."""
    cleaned = sentence
    for citation in citations:
        cleaned = cleaned.replace(citation.raw_text, "")
    cleaned = re.sub(r"\s{2,}", " ", cleaned)          # collapse double spaces
    cleaned = re.sub(r"\s+([.,;:])", r"\1", cleaned)   # "claim ." -> "claim."
    return cleaned.strip()
