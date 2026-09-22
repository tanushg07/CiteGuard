"""
Tests for Days 8-10 (Week 2 hardening): improved citation extraction
(narrative author-year format + reference resolution), fixed claim
boundaries (abbreviation-safe sentence splitting), and clean structured
output for the backend.
"""

from pathlib import Path

import pytest

from citeguard.document_processing.backend_output import to_backend_payload, write_backend_payload
from citeguard.document_processing.citation_extractor import extract_citations, resolve_citation_sources
from citeguard.document_processing.claim_extractor import extract_claims
from citeguard.document_processing.models import (
    AUTHOR_YEAR,
    NARRATIVE_AUTHOR_YEAR,
    NUMBERED,
    Page,
    Paragraph,
    Reference,
)
from citeguard.document_processing.parser import parse_document

TEST_PDF = Path(__file__).parent.parent / "data" / "test_documents" / "doc_1_simple.pdf"


@pytest.fixture(scope="module")
def parsed():
    if not TEST_PDF.exists():
        pytest.skip(f"test fixture not found: {TEST_PDF}")
    return parse_document(TEST_PDF)


# --- Narrative citation extraction ---

def test_narrative_single_author():
    pages = [Page(page_number=1, paragraphs=[Paragraph(index=1, text="Smith (2020) showed this effect.")])]
    citations = extract_citations(pages, sections=[])
    assert len(citations) == 1
    assert citations[0].citation_format == NARRATIVE_AUTHOR_YEAR
    assert citations[0].raw_text == "Smith (2020)"
    assert citations[0].ref_ids == ["Smith, 2020"]


def test_narrative_et_al():
    pages = [Page(page_number=1, paragraphs=[Paragraph(index=1, text="Smith et al. (2020) showed this effect.")])]
    citations = extract_citations(pages, sections=[])
    assert citations[0].raw_text == "Smith et al. (2020)"
    assert citations[0].ref_ids == ["Smith et al., 2020"]


def test_narrative_two_authors():
    pages = [Page(page_number=1, paragraphs=[Paragraph(index=1, text="Jones and Lee (2019) confirmed this.")])]
    citations = extract_citations(pages, sections=[])
    assert citations[0].raw_text == "Jones and Lee (2019)"
    assert citations[0].ref_ids == ["Jones and Lee, 2019"]


def test_narrative_and_parenthetical_dont_double_match():
    # a narrative citation right next to a parenthetical one in the same
    # sentence should produce exactly two citations, not three+ overlapping
    pages = [Page(page_number=1, paragraphs=[Paragraph(
        index=1, text="Smith (2020) agrees with prior work (Jones, 2019)."
    )])]
    citations = extract_citations(pages, sections=[])
    assert len(citations) == 2
    formats = {c.citation_format for c in citations}
    assert formats == {NARRATIVE_AUTHOR_YEAR, AUTHOR_YEAR}


# --- Reference resolution ---

def test_resolve_numbered_citation_single():
    citations = extract_citations(
        [Page(page_number=1, paragraphs=[Paragraph(index=1, text="This was shown [1].")])], sections=[]
    )
    references = [Reference(ref_id="1", raw_text="J. Doe, \"A paper,\" 2020.")]
    resolve_citation_sources(citations, references)
    assert citations[0].source_refs == ["J. Doe, \"A paper,\" 2020."]


def test_resolve_numbered_citation_group_resolves_each_member():
    citations = extract_citations(
        [Page(page_number=1, paragraphs=[Paragraph(index=1, text="Several works agree [1, 2].")])], sections=[]
    )
    references = [
        Reference(ref_id="1", raw_text="A. Author, \"Paper one,\" 2020."),
        Reference(ref_id="2", raw_text="B. Author, \"Paper two,\" 2021."),
    ]
    resolve_citation_sources(citations, references)
    assert len(citations[0].source_refs) == 2


def test_resolve_numbered_citation_missing_reference_returns_empty():
    citations = extract_citations(
        [Page(page_number=1, paragraphs=[Paragraph(index=1, text="This was shown [99].")])], sections=[]
    )
    resolve_citation_sources(citations, references=[])
    assert citations[0].source_refs == []


def test_resolve_author_year_citation_by_surname_and_year():
    citations = extract_citations(
        [Page(page_number=1, paragraphs=[Paragraph(index=1, text="This was shown (Smith et al., 2020).")])],
        sections=[],
    )
    references = [Reference(ref_id="1", raw_text="J. Smith, K. Doe, \"Some paper,\" Journal X, 2020.")]
    resolve_citation_sources(citations, references)
    assert citations[0].source_refs == ["J. Smith, K. Doe, \"Some paper,\" Journal X, 2020."]


def test_resolve_author_year_citation_no_match_returns_empty():
    citations = extract_citations(
        [Page(page_number=1, paragraphs=[Paragraph(index=1, text="This was shown (Nobody, 2099).")])],
        sections=[],
    )
    references = [Reference(ref_id="1", raw_text="J. Smith, \"Some paper,\" 2020.")]
    resolve_citation_sources(citations, references)
    assert citations[0].source_refs == []


def test_full_pdf_pipeline_resolves_known_citations(parsed):
    numbered = [c for c in parsed.citations if c.citation_format == NUMBERED]
    assert all(c.source_refs for c in numbered), "every numbered citation in the fixture has a real reference"

    dangling = next(c for c in parsed.citations if c.raw_text == "(Smith et al., 2020)")
    assert dangling.source_refs == [], "no 'Smith' reference exists in the fixture -- should not fabricate a match"


# --- Claim boundary fixes: abbreviation-safe sentence splitting ---

def test_et_al_before_narrative_year_does_not_split_sentence():
    pages = [Page(page_number=1, paragraphs=[Paragraph(
        index=1, text="Smith et al. (2020) showed this effect. A second sentence follows [2]."
    )])]
    citations = extract_citations(pages, sections=[])
    claims = extract_claims(pages, citations)
    assert len(claims) == 2
    assert claims[0].text == "Smith et al. showed this effect."
    assert claims[1].text == "A second sentence follows."


def test_dr_abbreviation_does_not_split_sentence():
    pages = [Page(page_number=1, paragraphs=[Paragraph(
        index=1, text="Dr. Smith reported this finding [1]. Confirmation came later [2]."
    )])]
    citations = extract_citations(pages, sections=[])
    claims = extract_claims(pages, citations)
    assert len(claims) == 2
    assert claims[0].text == "Dr. Smith reported this finding."


def test_real_sentence_boundary_after_bracket_citation_still_splits():
    # regression guard: the abbreviation fix must not stop normal splitting
    pages = [Page(page_number=1, paragraphs=[Paragraph(
        index=1, text="Claim one is true [1]. Claim two is also true [2]."
    )])]
    citations = extract_citations(pages, sections=[])
    claims = extract_claims(pages, citations)
    assert len(claims) == 2


def test_narrative_claim_text_keeps_author_as_subject():
    # regression guard for the bug caught during development: stripping the
    # full "Author (year)" span destroys the sentence's grammatical subject
    pages = [Page(page_number=1, paragraphs=[Paragraph(index=1, text="Jones and Lee (2019) confirmed it.")])]
    citations = extract_citations(pages, sections=[])
    claims = extract_claims(pages, citations)
    assert claims[0].text == "Jones and Lee confirmed it."
    assert "(2019)" not in claims[0].text


# --- Backend output (clean structured output) ---

def test_backend_payload_shape(parsed, tmp_path):
    payload = to_backend_payload(TEST_PDF, document_id="doc_1_simple")
    assert set(payload.keys()) == {"document_id", "claim_citation_pairs", "stats"}
    assert payload["document_id"] == "doc_1_simple"
    assert len(payload["claim_citation_pairs"]) == len(parsed.claims)
    assert payload["stats"]["pages"] == len(parsed.pages)
    assert payload["stats"]["citations"] == len(parsed.citations)


def test_backend_payload_pairs_are_plain_json_serializable():
    import json
    payload = to_backend_payload(TEST_PDF)
    json.dumps(payload)  # raises if anything isn't plain JSON-serializable


def test_backend_payload_defaults_document_id_to_filename():
    payload = to_backend_payload(TEST_PDF)
    assert payload["document_id"] == "doc_1_simple"


def test_write_backend_payload_creates_valid_json_file(tmp_path):
    import json
    out_path = tmp_path / "output.json"
    result_path = write_backend_payload(TEST_PDF, out_path)
    assert result_path == out_path
    assert out_path.exists()
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert "claim_citation_pairs" in data
