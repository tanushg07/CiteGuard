"""
Stage 2: list[Page] -> list[Section].

Heuristic: a paragraph is a heading if it's short, and it's either a known
section name (Abstract, Introduction, References, ...) or matches a numbered
heading pattern ("1. Introduction", "II. Related Work") whose title part is
a known section name. Numbering-only requirement is intentionally strict --
we don't want to misfire on short body sentences that happen to be brief.
"""

from __future__ import annotations

import re

from citeguard.document_processing.models import Page, Section

# Canonical section names we know how to recognize. Extend this list as we
# encounter more papers during Week 2 hardening.
KNOWN_SECTIONS = {
    "abstract",
    "introduction",
    "related work",
    "background",
    "literature review",
    "methodology",
    "method",
    "methods",
    "materials and methods",
    "experiments",
    "experimental setup",
    "results",
    "results and discussion",
    "evaluation",
    "discussion",
    "conclusion",
    "conclusions",
    "future work",
    "references",
    "bibliography",
    "acknowledgements",
    "acknowledgments",
    "appendix",
}

_MAX_HEADING_LEN = 60

# Optional numbering prefix ("1.", "1.2", "II.", "A.") followed by a title.
_NUMBERED_HEADING = re.compile(
    r"^(?:(?:\d+(?:\.\d+)*|[IVXLC]+|[A-Z])\.?\s+)?([A-Za-z][A-Za-z\s\-]{1,55})$"
)


def detect_sections(pages: list[Page]) -> list[Section]:
    sections: list[Section] = []
    for page in pages:
        for para in page.paragraphs:
            candidate = para.text.strip()
            name = _match_known_section(candidate)
            if name:
                sections.append(
                    Section(name=name, start_page=page.page_number, start_paragraph=para.index)
                )
    return sections


def _match_known_section(text: str) -> str | None:
    if len(text) > _MAX_HEADING_LEN:
        return None
    match = _NUMBERED_HEADING.match(text)
    if not match:
        return None
    title = match.group(1).strip()
    if title.lower() in KNOWN_SECTIONS:
        return title.title()
    return None
