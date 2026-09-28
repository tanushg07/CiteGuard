# Implementation and validation report

Implemented 2026-09-27. Existing working components and pre-existing changes were retained; no example evidence or verdicts are injected into the app.

## Architecture

`one PDF → all-page structure → citation-bearing sentences → reference mapping → Crossref/OpenAlex/arXiv identity checks → accessible PDF retrieval → identity-checked page passages → source-specific BM25/TF-IDF → cross-encoder → NLI + numerical checks → canonical verdict → optional explanation → persisted research report`

The detailed architecture diagram and operational instructions are in [README](../README.md). Full document metadata, pages, sections, paragraphs, sentences and parsed bibliography are available in the JSON report. Candidate identification, access attempts, selected evidence, page/section/paragraph, retrieval and NLI scores, arithmetic and decision reasons remain separate.

## Files changed and why

The table covers the final working-tree edits and new implementation files. The existing `app/core/schemas.py` contract is consumed for document/source provenance, canonical verdict and numerical fields; it is not a pending diff against the current HEAD.

| File | What changed and why |
| --- | --- |
| `.env.example` | Adds optional OpenAlex authentication and bounded fetch settings; makes external access configurable. |
| `.gitignore` | Ignores source caches, local real-paper reports and temporary test directories; avoids committing fetched content. |
| `README.md` | Replaces the old manual-source workflow with the implemented pipeline, setup, canonical states and limitations. |
| `app/api/routes.py` | Exports canonical verdicts and reasons to CSV; prevents legacy labels misrepresenting final decisions. |
| `app/evaluation/evaluator.py` | Scores canonical final verdicts; abstentions no longer inherit legacy lexical support. |
| `app/services/document_parser.py` | Builds whole-document structure, reference identifiers and frontmatter metadata; retains every page and fixes reference/appendix boundaries. |
| `app/services/downloader.py` | Adds bounded streaming, validated redirects, publisher PDF discovery and SHA-256 caching; obtains actual public full text with an access audit. |
| `app/services/extractor.py` | Separates extraction from enrichment; adds stable claim groups, location, association and claim-type fields; abstains on navigation and flattened tables. |
| `app/services/orchestrator.py` | Connects single-PDF parsing through automatic source resolution, retrieval, verification and reporting; explicit failures and canonical verdict logic replace incomplete orchestration. |
| `app/services/reference_metadata.py` | Adds conservative match diagnostics, provider fallback, exact arXiv resolution and OA locations; rejects conflicting/ambiguous identities. |
| `app/services/retriever.py` | Carries source/page/paragraph/evidence provenance and separate lexical/rerank scores through chunk retrieval. |
| `app/services/verifier.py` | Exposes actual model/label mapping/truncation state and numerical results; supports explanation generation after final decisions. |
| `app/services/numerical.py` | New narrow percentage-change arithmetic with explicit unsupported cases; separates relative percent from percentage points. |
| `app/services/source_resolver.py` | New per-reference deduplicated resolver; validates downloaded identity and yields source states plus full-text passages. |
| `backend/config.py` | Validates source limits and optional OpenAlex secret; keeps missing credentials nonfatal. |
| `backend/modules/citation_extractor.py` | Adds configurable Crossref request budget and candidate match diagnostics for whole-paper lookup. |
| `backend/modules/nli_verifier.py` | Uses final verdict/reason when explaining; optional generated text cannot overwrite the decision. |
| `citeguard-frontend/src/App.tsx` | Restores persisted reports from job links and updates browser history; makes completed runs reopenable. |
| `citeguard-frontend/src/components/ClaimCard.tsx` | Shows canonical verdicts and claim provenance rather than legacy status. |
| `citeguard-frontend/src/components/DashboardView.tsx` | Replaces the former dashboard with claim/source/evidence inspection, filters and separate model/numerical outputs. |
| `citeguard-frontend/src/components/DocumentSummary.tsx` | Shows extracted title/authors, all-page counts, real verdict totals and document structure. |
| `citeguard-frontend/src/components/LandingView.tsx` | Provides one PDF upload and explicit Verify action; removes manual source inputs and demonstration content. |
| `citeguard-frontend/src/components/ProcessingView.tsx` | Reports actual changing pipeline stage names and progress. |
| `citeguard-frontend/src/types/index.ts` | Adds typed document, source, evidence and canonical verdict fields used by the report. |
| `tests/test_reference_metadata.py` | Import formatting only; keeps existing provider regression tests lint-clean. |
| `backend/tests/test_real_pipeline.py` | Adds regressions for whole-document mapping, source identity, fetch safety, deduplication, abstention and numerical semantics. |
| `scripts/e2e_pdf.py` | New arbitrary-PDF multipart API integration runner that waits for a real job and writes its report. |
| `docs/IMPLEMENTATION_REPORT.md` | Records architecture, file changes, measured validation and research limitations for review. |

## Automated checks

- Pytest: **83 passed in 11.44 seconds** (`--basetemp .pytest-tmp-final2`). Includes the existing suite and new actual-pipeline regressions. Provider unit tests use controlled transports; they are not presented as live network tests.
- Ruff: **all checks passed** across app, backend, tests and the integration runner.
- Frontend: TypeScript project build, Vite production build and Oxlint completed successfully. Existing dependencies were used directly because this shell has Node but no npm executable.
- Real PDF integration: see the measured run below. This is separate from unit fixtures and invokes actual scholarly services and cached local neural models.

## Interpretation and limitations

Source coverage is a measured outcome; model verdict counts are not accuracy metrics. No human gold-label benchmark was collected for the real PDF. Every contradiction/support prediction still requires source review. A network-blocked dry run correctly produced unavailable states; the final live run used authorized network access. Subsequent runs may reuse fetched PDFs and can differ as providers throttle or change availability.

Supported styles are numbered brackets/ranges and common author-year forms. Complex grouped author-year, superscripts, footnotes and unnumbered reference lists remain incomplete. There is no OCR for scanned PDFs. Layout reading order, tables/equations, bibliography metadata, sentence-level attribution and clause splitting remain heuristic. Full-text failures and ambiguous identities are explicit, never filled with abstract-only evidence. NLI models are general-purpose and may make scientific errors. Numeric checks handle explicit values and narrow percent arithmetic, not general statistical or equation reasoning. This is a local single-process research tool, not a production multi-user service.

## Measured real-paper run

Input: local `attention.pdf`, *Attention Is All You Need*. SHA-256: `bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697`. Job: `job_0f9b3d48ca`.

A real multipart POST to `/api/verify` ran the full pipeline, including public network source identification and full-text retrieval, cached cross-encoder reranking, local NLI and numerical checks. No source papers were supplied in the request. Existing source PDF caches from preceding live validation were reusable.

15 pages; 40 bibliography entries; 37 distinct citation-bearing sentence candidates; 76 claim-citation pairs; 147.67 seconds. The 41 source resolution records include an unresolved citation mapping and are not 41 unique bibliography entries.

| Final verdict | Citation pairs |
| --- | ---: |
| SOURCE_METADATA_ONLY | 10 |
| INSUFFICIENT_EVIDENCE | 16 |
| SOURCE_UNAVAILABLE | 17 |
| PARTIALLY_SUPPORTED | 4 |
| CONTRADICTED | 15 |
| SUPPORTED | 5 |
| NOT_VERIFIABLE | 9 |

Source-resolution records: SOURCE_UNAVAILABLE: 12, SOURCE_METADATA_ONLY: 7, FULL_TEXT: 22.

Full raw artifact: `data/e2e-attention-final.json` (local and Git-ignored). Persisted report: [open in running local app](http://127.0.0.1:8765/?job=job_0f9b3d48ca). Browser inspection confirmed summary totals, verdict filtering, actual ACL PDF link, page-tagged passages and separate lexical/rerank/NLI outputs. The displayed two-column source text also exposes a known reading-order limitation; it must not be taken as faithful layout reconstruction.
