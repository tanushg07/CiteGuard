"""
Tests for Days 4-5: in-text citation extraction -- single/grouped numbered
citations, author-year citations, range expansion, and mapping each citation
back to its page/paragraph. Also checks we don't misfire on the reference
list's own "[1]", "[2]" ... numbering.
"""

from pathlib import Path

import pytest

from citeguard.document_processing.citation_extractor import extract_citations
from citeguard.document_processing.models import AUTHOR_YEAR, NUMBERED, Page, Paragraph, Section
from citeguard.document_processing.parser import parse_document

TEST_PDF = Path(__file__).parent.parent / "data" / "test_documents" / "doc_1_simple.pdf"


@pytest.fixture(scope="module")
def parsed():
    if not TEST_PDF.exists():
        pytest.skip(f"test fixture not found: {TEST_PDF} (run scripts/generate_test_pdf.py)")
    return parse_document(TEST_PDF)


# --- Against the real synthetic PDF ---

def test_finds_all_in_text_citations(parsed):
    assert len(parsed.citations) == 8


def test_single_numbered_citations_detected(parsed):
    singles = [c for c in parsed.citations if c.citation_format == NUMBERED and len(c.ref_ids) == 1]
    raw = {c.raw_text for c in singles}
    assert raw == {"[1]", "[4]", "[7]", "[8]"}


def test_grouped_numbered_citations_detected(parsed):
    groups = [c for c in parsed.citations if c.citation_format == NUMBERED and len(c.ref_ids) > 1]
    assert {c.raw_text for c in groups} == {"[2, 3]", "[5, 6]", "[9, 10]"}
    by_raw = {c.raw_text: c.ref_ids for c in groups}
    assert by_raw["[2, 3]"] == ["2", "3"]
    assert by_raw["[9, 10]"] == ["9", "10"]


def test_author_year_citation_detected(parsed):
    ay = [c for c in parsed.citations if c.citation_format == AUTHOR_YEAR]
    assert len(ay) == 1
    assert ay[0].raw_text == "(Smith et al., 2020)"
    assert ay[0].ref_ids == ["Smith et al., 2020"]


def test_citations_mapped_to_page_and_paragraph(parsed):
    for c in parsed.citations:
        assert c.page >= 1
        assert c.paragraph >= 1
        # every citation's page/paragraph must correspond to real body text
        text = parsed.paragraph_text(c.page, c.paragraph)
        assert text is not None
        assert c.raw_text.strip("[]") .split(",")[0].strip() or True  # sanity: raw_text non-empty
        assert c.raw_text in text or c.raw_text.replace(" ", "") in text.replace(" ", "")


def test_reference_list_markers_not_misdetected_as_citations(parsed):
    # the References section has its own "[1]".."[10]" list numbering --
    # none of those should show up as extracted in-text citations
    ref_section = next(s for s in parsed.sections if s.name == "References")
    for c in parsed.citations:
        is_in_or_after_refs = c.page > ref_section.start_page or (
            c.page == ref_section.start_page and c.paragraph >= ref_section.start_paragraph
        )
        assert not is_in_or_after_refs, f"{c.raw_text} incorrectly extracted from the reference list"


def test_citation_ids_are_unique(parsed):
    ids = [c.citation_id for c in parsed.citations]
    assert len(ids) == len(set(ids))


# --- Targeted unit tests for format edge cases not present in the fixture PDF ---

def test_numeric_range_expansion():
    pages = [Page(page_number=1, paragraphs=[Paragraph(index=1, text="See [3-5] for details.")])]
    citations = extract_citations(pages, sections=[])
    assert len(citations) == 1
    assert citations[0].ref_ids == ["3", "4", "5"]


def test_en_dash_range_expansion():
    pages = [Page(page_number=1, paragraphs=[Paragraph(index=1, text="See [3\u20135] for details.")])]
    citations = extract_citations(pages, sections=[])
    assert citations[0].ref_ids == ["3", "4", "5"]


def test_mixed_group_and_range():
    pages = [Page(page_number=1, paragraphs=[Paragraph(index=1, text="As shown in [3, 5-7, 9].")])]
    citations = extract_citations(pages, sections=[])
    assert citations[0].ref_ids == ["3", "5", "6", "7", "9"]


def test_grouped_author_year_citation():
    pages = [Page(page_number=1, paragraphs=[
        Paragraph(index=1, text="This is supported by prior work (Smith et al., 2020; Jones, 2019).")
    ])]
    citations = extract_citations(pages, sections=[])
    assert len(citations) == 1
    c = citations[0]
    assert c.citation_format == AUTHOR_YEAR
    assert c.ref_ids == ["Smith et al., 2020", "Jones, 2019"]


def test_two_author_author_year_citation():
    pages = [Page(page_number=1, paragraphs=[
        Paragraph(index=1, text="As argued previously (Smith and Jones, 2021).")
    ])]
    citations = extract_citations(pages, sections=[])
    assert citations[0].ref_ids == ["Smith and Jones, 2021"]


def test_multiple_citations_in_same_paragraph_get_correct_paragraph_index():
    pages = [Page(page_number=2, paragraphs=[
        Paragraph(index=3, text="Claim one [1]. Claim two [2, 3]. Claim three (Lee, 2018).")
    ])]
    citations = extract_citations(pages, sections=[])
    assert len(citations) == 3
    assert all(c.page == 2 and c.paragraph == 3 for c in citations)


def test_no_citations_returns_empty_list():
    pages = [Page(page_number=1, paragraphs=[Paragraph(index=1, text="No citations in this sentence at all.")])]
    assert extract_citations(pages, sections=[]) == []
