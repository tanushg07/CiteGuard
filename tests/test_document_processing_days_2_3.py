"""
Tests for Days 2-3: PDF text extraction, page/paragraph preservation,
section detection, reference extraction -- against the synthetic
single-column academic PDF in data/test_documents/doc_1_simple.pdf.
"""

from pathlib import Path

import pytest

from citeguard.document_processing.parser import parse_document

TEST_PDF = Path(__file__).parent.parent / "data" / "test_documents" / "doc_1_simple.pdf"

EXPECTED_SECTIONS = [
    "Abstract",
    "Introduction",
    "Related Work",
    "Methodology",
    "Results",
    "Discussion",
    "Conclusion",
    "References",
]


@pytest.fixture(scope="module")
def parsed():
    if not TEST_PDF.exists():
        pytest.skip(f"test fixture not found: {TEST_PDF} (run scripts/generate_test_pdf.py)")
    return parse_document(TEST_PDF)


def test_extracts_all_pages(parsed):
    assert len(parsed.pages) == 3


def test_preserves_page_numbers_in_order(parsed):
    assert [p.page_number for p in parsed.pages] == [1, 2, 3]


def test_preserves_paragraphs_with_content(parsed):
    page1 = parsed.pages[0]
    assert len(page1.paragraphs) > 0
    # paragraph indices restart per page and are sequential
    assert [p.index for p in page1.paragraphs] == list(range(1, len(page1.paragraphs) + 1))


def test_finds_known_paragraph_text(parsed):
    all_text = " ".join(p.text for page in parsed.pages for p in page.paragraphs)
    assert "hybrid verification architecture" in all_text
    assert "Citation misuse is a persistent problem" in all_text


def test_detects_expected_sections_in_order(parsed):
    detected = [s.name for s in parsed.sections]
    assert detected == EXPECTED_SECTIONS


def test_section_page_numbers_are_plausible(parsed):
    by_name = {s.name: s for s in parsed.sections}
    # Abstract/Introduction should be on page 1, References on the last page
    assert by_name["Abstract"].start_page == 1
    assert by_name["Introduction"].start_page == 1
    assert by_name["References"].start_page == parsed.pages[-1].page_number or \
        by_name["References"].start_page == 2  # references heading itself is on page 2


def test_extracts_all_references(parsed):
    assert len(parsed.references) == 10
    assert [r.ref_id for r in parsed.references] == [str(i) for i in range(1, 11)]


def test_reference_text_is_captured(parsed):
    ref1 = next(r for r in parsed.references if r.ref_id == "1")
    assert "Citation accuracy in scientific literature" in ref1.raw_text

    ref10 = next(r for r in parsed.references if r.ref_id == "10")
    assert "DeBERTa" in ref10.raw_text


def test_references_split_across_page_boundary(parsed):
    # refs 1-2 are on page 2 (with the heading), refs 3-10 continue on page 3 --
    # extraction must not lose or duplicate entries at that boundary
    ref_ids = [r.ref_id for r in parsed.references]
    assert len(ref_ids) == len(set(ref_ids)), "duplicate reference ids across page break"


def test_heading_at_page_boundary_still_detected(parsed):
    # "3. Methodology" lands as the very last block on page 1 in our fixture --
    # regression test for the heading/paragraph merge bug found during dev
    assert "Methodology" in [s.name for s in parsed.sections]
