"""
Stage 5 (Days 6-7), part 1: Sentence -> Citation Detection -> Claim Extraction.

A "claim" in this pipeline is any sentence that contains at least one in-text
citation -- an uncited sentence has nothing to verify, so we don't extract it
as a claim. A sentence with a grouped citation "[3, 7, 12]" becomes ONE claim
carrying all three citation_ids (Days 6-7's pairing step, in
claim_citation_pairing.py, is what fans that out into multiple
ClaimCitationPair rows).

Sentence splitting (hardened Days 8-10): split after ./!/? when followed by
whitespace and then a capital letter, quote, or opening paren -- UNLESS the
word immediately before the punctuation is a known abbreviation ("Dr.",
"et al.", "Fig.", etc). The abbreviation guard matters more than it looks:
narrative citations like "Smith et al. (2020) showed..." have an opening
paren right after "al.", which would otherwise look exactly like a sentence
boundary and incorrectly cut the claim in half.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from citeguard.document_processing.models import Citation, NARRATIVE_AUTHOR_YEAR, Page

_SENTENCE_BOUNDARY = re.compile(r'([.!?])(\s+)(?=[A-Z"\'(])')
_WORD_BEFORE = re.compile(r"([A-Za-z]+)$")

# Preceding word (lowercased, punctuation stripped) that means "this period
# is NOT a sentence end". "al" catches "et al." specifically, since that's
# the abbreviation most likely to sit right before a citation.
_ABBREVIATIONS = {
    "dr", "mr", "mrs", "ms", "prof", "sr", "jr",
    "fig", "eq", "eqs", "vs", "approx", "cf", "etc",
    "no", "vol", "pp", "p", "al", "eg", "ie",
}


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
    text = paragraph_text.strip()
    if not text:
        return []

    sentences: list[str] = []
    start = 0
    for match in _SENTENCE_BOUNDARY.finditer(text):
        punct_index = match.start(1)
        preceding_word = _preceding_word(text, punct_index)
        if preceding_word in _ABBREVIATIONS:
            continue  # e.g. "et al." / "Dr." -- not a real sentence boundary

        sentence = text[start:match.end(1)].strip()
        if sentence:
            sentences.append(sentence)
        start = match.end()  # skip past the whitespace, start of next sentence

    tail = text[start:].strip()
    if tail:
        sentences.append(tail)
    return sentences


def _preceding_word(text: str, punct_index: int) -> str:
    match = _WORD_BEFORE.search(text[:punct_index])
    return match.group(1).lower() if match else ""


def _strip_citation_markers(sentence: str, citations: list[Citation]) -> str:
    """Remove each citation's marker from the sentence, leaving a clean claim
    suitable for downstream NLI/evidence comparison.

    For NUMBERED and (parenthetical) AUTHOR_YEAR citations, the whole
    raw_text is a parenthetical aside ("[1]", "(Smith, 2020)") and safe to
    delete outright. For NARRATIVE_AUTHOR_YEAR citations ("Smith et al.
    (2020) showed..."), the author phrase is the sentence's actual subject
    -- deleting all of "Smith et al. (2020)" would gut the claim's grammar.
    We only strip the trailing "(year)" part and leave the author name in
    place.
    """
    cleaned = sentence
    for citation in citations:
        if citation.citation_format == NARRATIVE_AUTHOR_YEAR:
            cleaned = re.sub(r"\s*\(\d{4}[a-z]?\)", "", cleaned, count=1)
        else:
            cleaned = cleaned.replace(citation.raw_text, "")
    cleaned = re.sub(r"\s{2,}", " ", cleaned)          # collapse double spaces
    cleaned = re.sub(r"\s+([.,;:])", r"\1", cleaned)   # "claim ." -> "claim."
    return cleaned.strip()
