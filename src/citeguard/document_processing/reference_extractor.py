"""
Stage 3: list[Page] + list[Section] -> list[Reference].

Finds the References/Bibliography section (via the sections already detected)
and parses its paragraphs into individual entries. Handles the common
numbered-bracket style ("[1] ...", "[2] ...") used by most CS venues; entries
that wrap onto multiple paragraphs (rare with our paragraph splitting, since
each numbered ref is usually its own block) are still appended to the
previous entry rather than dropped.

Author-year style reference lists (no "[n]" markers) are a known gap --
tracked for the Week 2 hardening pass, not handled here yet.
"""

from __future__ import annotations

import re

from citeguard.document_processing.models import Page, Reference, Section

_REFERENCE_SECTION_NAMES = {"references", "bibliography"}
_NUMBERED_ENTRY = re.compile(r"^\[(\d+)\]\s*(.+)$")


def extract_references(pages: list[Page], sections: list[Section]) -> list[Reference]:
    ref_section = next(
        (s for s in sections if s.name.lower() in _REFERENCE_SECTION_NAMES), None
    )
    if ref_section is None:
        return []

    body_blocks = _paragraphs_after(pages, ref_section)
    return _parse_numbered_entries(body_blocks)


def _paragraphs_after(pages: list[Page], section: Section) -> list[str]:
    """All paragraph text strictly after the section heading itself, up to
    the end of the document (references are assumed to be the last section --
    true for every layout we've tested so far)."""
    started = False
    blocks: list[str] = []
    for page in pages:
        for para in page.paragraphs:
            if not started:
                if page.page_number == section.start_page and para.index == section.start_paragraph:
                    started = True
                continue
            blocks.append(para.text)
    return blocks


def _parse_numbered_entries(blocks: list[str]) -> list[Reference]:
    references: list[Reference] = []
    current_id: str | None = None
    current_parts: list[str] = []

    for block in blocks:
        match = _NUMBERED_ENTRY.match(block)
        if match:
            if current_id is not None:
                references.append(Reference(ref_id=current_id, raw_text=" ".join(current_parts).strip()))
            current_id = match.group(1)
            current_parts = [match.group(2)]
        elif current_id is not None:
            # continuation of a wrapped reference entry
            current_parts.append(block)

    if current_id is not None:
        references.append(Reference(ref_id=current_id, raw_text=" ".join(current_parts).strip()))

    return references
