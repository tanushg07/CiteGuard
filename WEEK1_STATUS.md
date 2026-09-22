# Week 1 — Jagadish — Document Processing + Citation Extraction

Status: **Complete**

## Delivered

- Days 2-3: PDF text extraction, page/paragraph preservation, section detection, reference extraction
- Days 4-5: in-text citation extraction (single, grouped, ranges, author-year), mapped to page/paragraph
- Days 6-7: claim extraction (sentence-level, citation-triggered) + claim-citation pairing

## Week 1 Goal — verified

Academic PDF -> Claim-Citation Pairs

Example output (from data/test_documents/doc_1_simple.pdf):

\`\`\`json
{
"claim_id": "claim_001",
"claim": "Citation misuse is a persistent problem in scientific writing.",
"citation_id": "cit_001",
"page": 1,
"paragraph": 6
}
\`\`\`

## Tests

39/39 passing across tests/test_document_processing_days_2_3.py,
tests/test_citation_extraction_days_4_5.py, tests/test_claim_extraction_days_6_7.py,
tests/test_pipeline_stubs.py

Run: `pytest tests/ -v`
