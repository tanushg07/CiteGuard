"""
Tests for Days 6-7: Sentence -> Citation Detection -> Claim Extraction ->
Claim-Citation Pair. Verifies the full pipeline end-to-end against the
synthetic test PDF, plus targeted unit tests for fan-out (multiple separate
citations in one sentence) and exclusion of uncited sentences.
"""

from pathlib import Path

import pytest

from citeguard.document_processing.claim_citation_pairing import build_claim_citation_pairs
from citeguard.document_processing.claim_extractor import extract_claims
from citeguard.document_processing.models import AUTHOR_YEAR, NUMBERED, Citation, Page, Paragraph
from citeguard.document_processing.parser import extract_claim_citation_pairs, parse_document

TEST_PDF = Path(__file__).parent.parent / "data" / "test_documents" / "doc_1_simple.pdf"


@pytest.fixture(scope="module")
def parsed():
    if not TEST_PDF.exists():
        pytest.skip(f"test fixture not found: {TEST_PDF} (run scripts/generate_test_pdf.py)")
    return parse_document(TEST_PDF)


# --- End-to-end against the real synthetic PDF ---

def test_claims_extracted_for_every_citation(parsed):
    # our fixture PDF has exactly one citation per cited sentence (no sentence
    # carries two separate citation mentions), so claim count == citation count
    assert len(parsed.claims) == len(parsed.citations) == 8


def test_claim_ids_are_unique_and_sequential(parsed):
    ids = [c.claim_id for c in parsed.claims]
    assert len(ids) == len(set(ids))
    assert ids == [f"claim_{i:03d}" for i in range(1, len(ids) + 1)]


def test_claim_text_has_citation_markers_stripped(parsed):
    for claim in parsed.claims:
        assert "[" not in claim.text
        assert "]" not in claim.text
        # author-year mention shouldn't leave a dangling "()" either
        assert "()" not in claim.text


def test_claim_text_is_non_trivial_and_ends_cleanly(parsed):
    for claim in parsed.claims:
        assert len(claim.text) > 10
        assert not claim.text.endswith(" ")
        assert not claim.text.startswith(" ")


def test_every_claim_references_a_real_citation(parsed):
    known_citation_ids = {c.citation_id for c in parsed.citations}
    for claim in parsed.claims:
        for cid in claim.citation_ids:
            assert cid in known_citation_ids


def test_claim_page_paragraph_match_its_citation(parsed):
    citations_by_id = {c.citation_id: c for c in parsed.citations}
    for claim in parsed.claims:
        for cid in claim.citation_ids:
            citation = citations_by_id[cid]
            assert claim.page == citation.page
            assert claim.paragraph == citation.paragraph


def test_uncited_sentences_are_not_claims(parsed):
    # e.g. the Abstract paragraph has no citations at all -- none of its
    # sentences should have produced a claim
    abstract_section = next(s for s in parsed.sections if s.name == "Abstract")
    for claim in parsed.claims:
        is_in_abstract_paragraph = (
            claim.page == abstract_section.start_page
            and claim.paragraph == abstract_section.start_paragraph + 1
        )
        assert not is_in_abstract_paragraph


# --- ClaimCitationPair output (the shared schema / Week 1 goal) ---

def test_pairs_match_claims_one_to_one_when_no_grouping(parsed):
    pairs = build_claim_citation_pairs(parsed.claims)
    assert len(pairs) == 8  # 1 citation per claim in this fixture


def test_pair_matches_exact_output_shape(parsed):
    pairs = build_claim_citation_pairs(parsed.claims)
    first = pairs[0].model_dump()
    assert set(first.keys()) == {"claim_id", "claim", "citation_id", "page", "paragraph"}
    assert first["claim_id"] == "claim_001"
    assert first["citation_id"] == "cit_001"
    assert first["page"] == 1


def test_full_pipeline_pdf_to_pairs():
    if not TEST_PDF.exists():
        pytest.skip("test fixture not found")
    pairs = extract_claim_citation_pairs(TEST_PDF)
    assert len(pairs) == 8
    assert all(p.claim.strip() for p in pairs)
    assert all(p.citation_id.startswith("cit_") for p in pairs)


# --- Targeted unit tests: fan-out and exclusion logic ---

def test_sentence_with_two_separate_citations_produces_two_pairs_same_claim():
    pages = [Page(page_number=5, paragraphs=[Paragraph(
        index=2,
        text="This result has been shown before [1] and also confirmed independently (Lee, 2019).",
    )])]
    citations = [
        Citation(citation_id="cit_a", raw_text="[1]", citation_format=NUMBERED, page=5, paragraph=2, ref_ids=["1"]),
        Citation(citation_id="cit_b", raw_text="(Lee, 2019)", citation_format=AUTHOR_YEAR, page=5, paragraph=2, ref_ids=["Lee, 2019"]),
    ]
    claims = extract_claims(pages, citations)
    assert len(claims) == 1
    assert claims[0].citation_ids == ["cit_a", "cit_b"]

    pairs = build_claim_citation_pairs(claims)
    assert len(pairs) == 2
    assert pairs[0].claim_id == pairs[1].claim_id == "claim_001"
    assert {p.citation_id for p in pairs} == {"cit_a", "cit_b"}


def test_grouped_citation_stays_as_one_pair_not_fanned_out():
    pages = [Page(page_number=1, paragraphs=[Paragraph(index=1, text="Many works agree on this [2, 3].")])]
    citations = [
        Citation(citation_id="cit_g", raw_text="[2, 3]", citation_format=NUMBERED, page=1, paragraph=1, ref_ids=["2", "3"]),
    ]
    claims = extract_claims(pages, citations)
    pairs = build_claim_citation_pairs(claims)
    # the group is preserved as ONE citation mention -> ONE pair, not two
    assert len(pairs) == 1
    assert pairs[0].citation_id == "cit_g"


def test_uncited_sentence_produces_no_claim():
    pages = [Page(page_number=1, paragraphs=[Paragraph(
        index=1, text="This sentence has a citation [1]. This one does not."
    )])]
    citations = [Citation(citation_id="cit_x", raw_text="[1]", citation_format=NUMBERED, page=1, paragraph=1, ref_ids=["1"])]
    claims = extract_claims(pages, citations)
    assert len(claims) == 1
    assert "does not" not in claims[0].text


def test_paragraph_with_no_citations_produces_no_claims():
    pages = [Page(page_number=1, paragraphs=[Paragraph(index=1, text="Nothing cited in this paragraph at all.")])]
    assert extract_claims(pages, citations=[]) == []
