"""
Stage 4 (Days 4-5): list[Page] + list[Section] -> list[Citation].

Detects two citation formats commonly used in academic writing:

  NUMBERED     "[12]"                       -- single
               "[3, 7, 12]"                 -- grouped
               "[3-5]"                      -- range, expanded to ["3","4","5"]
               "[3, 5-7, 9]"                -- mixed group + range

  AUTHOR_YEAR  "(Smith et al., 2020)"                    -- single
               "(Smith et al., 2020; Jones, 2019)"       -- grouped

Each match becomes ONE Citation (one "mention" in the text), which may carry
multiple ref_ids if it was a grouped citation -- Days 6-7 (claim pairing)
is what turns a grouped citation into multiple ClaimCitationPairs, one per
ref_id, sharing the same claim.

We deliberately skip the References/Bibliography section itself: its "[1]",
"[2]", ... markers are list numbering, not in-text citations, and would
otherwise be misdetected as (a lot of) single numbered citations.
"""

from __future__ import annotations

import re

from citeguard.document_processing.models import (
    AUTHOR_YEAR,
    NUMBERED,
    Citation,
    Page,
    Section,
)

_REFERENCE_SECTION_NAMES = {"references", "bibliography"}

# --- Numbered citations: [12]  [3, 7, 12]  [3-5]  [3, 5-7, 9] ---
_NUMBERED_CITATION = re.compile(
    r"\[(\d+(?:\s*[-\u2013]\s*\d+)?(?:\s*,\s*\d+(?:\s*[-\u2013]\s*\d+)?)*)\]"
)
_NUM_RANGE = re.compile(r"^(\d+)\s*[-\u2013]\s*(\d+)$")

# --- Author-year citations: (Smith et al., 2020)  (Smith et al., 2020; Jones, 2019) ---
_AUTHOR_YEAR_ENTRY = r"[A-Z][A-Za-z\-]+(?:\s+(?:et al\.|and\s+[A-Z][A-Za-z\-]+))?,\s*\d{4}[a-z]?"
_AUTHOR_YEAR_ENTRY_RE = re.compile(_AUTHOR_YEAR_ENTRY)
_AUTHOR_YEAR_CITATION = re.compile(
    rf"\(({_AUTHOR_YEAR_ENTRY}(?:\s*;\s*{_AUTHOR_YEAR_ENTRY})*)\)"
)


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
