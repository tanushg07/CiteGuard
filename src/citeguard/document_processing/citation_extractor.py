"""
Stage 4 (Days 4-5, extended Days 8-10): list[Page] + list[Section] ->
list[Citation], plus reference resolution.

Detects three citation formats commonly used in academic writing:

  NUMBERED               "[12]"                       -- single
                          "[3, 7, 12]"                 -- grouped
                          "[3-5]"                      -- range, expanded to ["3","4","5"]
                          "[3, 5-7, 9]"                -- mixed group + range

  AUTHOR_YEAR             "(Smith et al., 2020)"                    -- single
      (parenthetical)     "(Smith et al., 2020; Jones, 2019)"       -- grouped

  NARRATIVE_AUTHOR_YEAR   "Smith (2020)"
                          "Smith et al. (2020)"
                          "Smith and Jones (2020)"

Each match becomes ONE Citation (one "mention" in the text), which may carry
multiple ref_ids if it was a grouped citation -- Days 6-7 (claim pairing)
is what turns a grouped citation into multiple ClaimCitationPairs, one per
ref_id, sharing the same claim.

We deliberately skip the References/Bibliography section itself: its "[1]",
"[2]", ... markers are list numbering, not in-text citations, and would
otherwise be misdetected as (a lot of) single numbered citations.

resolve_citation_sources() (Days 8-10) is a separate pass that, once
citations AND references are both extracted, fills in each Citation's
source_refs -- the actual reference-list text each citation points to. This
is what lets Evidence Retrieval (Jayant) know exactly which source to fetch
without re-doing the lookup itself.
"""

from __future__ import annotations

import re

from citeguard.document_processing.models import (
    AUTHOR_YEAR,
    NARRATIVE_AUTHOR_YEAR,
    NUMBERED,
    Citation,
    Page,
    Reference,
    Section,
)

_REFERENCE_SECTION_NAMES = {"references", "bibliography"}

# --- Numbered citations: [12]  [3, 7, 12]  [3-5]  [3, 5-7, 9] ---
_NUMBERED_CITATION = re.compile(
    r"\[(\d+(?:\s*[-\u2013]\s*\d+)?(?:\s*,\s*\d+(?:\s*[-\u2013]\s*\d+)?)*)\]"
)
_NUM_RANGE = re.compile(r"^(\d+)\s*[-\u2013]\s*(\d+)$")

# --- Author-year, parenthetical: (Smith et al., 2020)  (Smith et al., 2020; Jones, 2019) ---
_AUTHOR_YEAR_ENTRY = r"[A-Z][A-Za-z\-]+(?:\s+(?:et al\.|and\s+[A-Z][A-Za-z\-]+))?,\s*\d{4}[a-z]?"
_AUTHOR_YEAR_ENTRY_RE = re.compile(_AUTHOR_YEAR_ENTRY)
_AUTHOR_YEAR_CITATION = re.compile(
    rf"\(({_AUTHOR_YEAR_ENTRY}(?:\s*;\s*{_AUTHOR_YEAR_ENTRY})*)\)"
)

# --- Author-year, narrative: Smith (2020)   Smith et al. (2020)   Smith and Jones (2020) ---
_NARRATIVE_AUTHOR = r"[A-Z][A-Za-z\-]+(?:\s+(?:et al\.|and\s+[A-Z][A-Za-z\-]+))?"
_NARRATIVE_CITATION = re.compile(rf"\b({_NARRATIVE_AUTHOR})\s*\((\d{{4}}[a-z]?)\)")


def extract_citations(pages: list[Page], sections: list[Section]) -> list[Citation]:
    ref_section = next(
        (s for s in sections if s.name.lower() in _REFERENCE_SECTION_NAMES), None
    )

    citations: list[Citation] = []
    counter = 0

    for page in pages:
        for para in page.paragraphs:
            if ref_section is not None and _at_or_after(page.page_number, para.index, ref_section):
                continue  # inside the reference list itself -- not in-text citations

            for match in _NUMBERED_CITATION.finditer(para.text):
                counter += 1
                citations.append(
                    Citation(
                        citation_id=f"cit_{counter:03d}",
                        raw_text=match.group(0),
                        citation_format=NUMBERED,
                        page=page.page_number,
                        paragraph=para.index,
                        ref_ids=_expand_numbered_group(match.group(1)),
                    )
                )

            for match in _AUTHOR_YEAR_CITATION.finditer(para.text):
                counter += 1
                entries = _AUTHOR_YEAR_ENTRY_RE.findall(match.group(1))
                citations.append(
                    Citation(
                        citation_id=f"cit_{counter:03d}",
                        raw_text=match.group(0),
                        citation_format=AUTHOR_YEAR,
                        page=page.page_number,
                        paragraph=para.index,
                        ref_ids=entries,
                    )
                )

            for match in _NARRATIVE_CITATION.finditer(para.text):
                counter += 1
                author, year = match.group(1), match.group(2)
                citations.append(
                    Citation(
                        citation_id=f"cit_{counter:03d}",
                        raw_text=match.group(0),
                        citation_format=NARRATIVE_AUTHOR_YEAR,
                        page=page.page_number,
                        paragraph=para.index,
                        ref_ids=[f"{author}, {year}"],
                    )
                )

    return citations


def _expand_numbered_group(inner: str) -> list[str]:
    ids: list[str] = []
    for part in inner.split(","):
        part = part.strip()
        if not part:
            continue
        range_match = _NUM_RANGE.match(part)
        if range_match:
            start, end = int(range_match.group(1)), int(range_match.group(2))
            ids.extend(str(n) for n in range(start, end + 1))
        else:
            ids.append(part)
    return ids


def _at_or_after(page_number: int, paragraph_index: int, section: Section) -> bool:
    if page_number > section.start_page:
        return True
    if page_number == section.start_page and paragraph_index >= section.start_paragraph:
        return True
    return False


# --- Reference resolution (Days 8-10) ---

_YEAR_IN_ENTRY = re.compile(r"(\d{4})")
_LEAD_AUTHOR_SURNAME = re.compile(r"^([A-Za-z\-]+)")


def resolve_citation_sources(citations: list[Citation], references: list[Reference]) -> None:
    """
    Fills in citation.source_refs for every citation, in place.

    NUMBERED citations resolve exactly, by matching ref_id against
    Reference.ref_id. AUTHOR_YEAR / NARRATIVE citations resolve heuristically:
    we pull the lead author's surname and the year out of the citation's
    ref_id string (e.g. "Smith et al., 2020" -> surname "smith", year
    "2020") and look for a reference whose raw_text contains both, case
    -insensitively. This is a best-effort match, not a guarantee -- two
    different works by different authors sharing a surname and year could
    collide. Good enough for Week 2; a stricter match (full author list,
    title overlap) is a later hardening pass if it turns out to matter.
    """
    references_by_id = {r.ref_id: r for r in references}

    for citation in citations:
        resolved: list[str] = []
        for ref_id in citation.ref_ids:
            if citation.citation_format == NUMBERED:
                reference = references_by_id.get(ref_id)
                if reference is not None:
                    resolved.append(reference.raw_text)
                continue

            year_match = _YEAR_IN_ENTRY.search(ref_id)
            author_match = _LEAD_AUTHOR_SURNAME.search(ref_id)
            if not (year_match and author_match):
                continue
            year = year_match.group(1)
            surname = author_match.group(1).lower()
            for reference in references:
                text_lower = reference.raw_text.lower()
                if year in reference.raw_text and surname in text_lower:
                    resolved.append(reference.raw_text)
                    break

        citation.source_refs = resolved
