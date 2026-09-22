# CiteGuard

Citation extraction, source passage retrieval, and evidence alignment for academic PDFs and text. This repository implements the local application and evaluation tooling through week 3.

## Run on this machine

The repaired environment is `.venv312` (the original `.venv` points to a missing Python 3.10 installation). From this project folder in PowerShell:

```powershell
.\start.ps1
```

Open **http://127.0.0.1:8000**. The launcher builds the React app and serves it together with FastAPI. Keep the terminal running; Ctrl+C stops it. If port 8000 is already occupied by CiteGuard, use the running app or stop that terminal first.

## Fresh installation

Use Python 3.12 and Node.js 22.12+ (tested with Node 24). No API key is required.

```powershell
py -3.12 -m venv .venv312
.\.venv312\Scripts\python.exe -m pip install -r requirements.txt
npm.cmd ci --prefix citeguard-frontend
.\.venv312\Scripts\python.exe scripts/prepare_models.py
.\start.ps1
```

`prepare_models.py` explicitly downloads the MS-MARCO MiniLM cross-encoder and DistilBERT MNLI model. Normal startup uses cached weights, loads them on the first analysis, and does not attempt downloads. First analysis can take longer. If weights are unavailable, the response and dashboard warn that a conservative lexical baseline ran. To intentionally use that mode, set `$env:CITEGUARD_MODE = 'baseline'` before starting. `.env.example` documents shell settings; it is not automatically loaded.

For frontend development, start the API with `.\.venv312\Scripts\python.exe -m uvicorn app.main:app --reload`, and run `npm.cmd run dev --prefix citeguard-frontend` in another terminal. Vite proxies `/api` to the backend.

## Try it

- Click **Run Synthetic Demo** for nine controlled examples.
- Use **Direct Text / LaTeX Input**, with manuscript `The dose was 2 mg [1].` and source `The dose was 2 mg.`
- For PDFs, run `.\.venv312\Scripts\python.exe evaluation/generate_dataset.py`. Upload `data/demo/manuscript.pdf` and all nine source PDFs from that folder.
- For your own papers, upload the target PDF plus its cited source PDFs. With several sources, prefix each filename with its citation marker, for example `[2] Study.pdf`. Bibliography/title matching is also attempted. A single supplied source is treated as the source selected by the user for the analysis. For more precise text mapping, the API accepts `sources: [{name, text, markers: ['[2]']}]`.

Missing/unmapped sources produce **insufficient evidence**, never self-verification. Citation markers such as `[1]`, `[1, 3-5]`, `(Smith et al., 2020)`, and `Smith (2020)` are supported. Groups produce one result per citation. The API retains `Unrelated` as the legacy wire label for insufficient evidence.

## Pipeline and API

### Optional Semantic Scholar metadata

Set `SEMANTIC_SCHOLAR_API_KEY` in the backend process environment before starting
CiteGuard (PowerShell: `$env:SEMANTIC_SCHOLAR_API_KEY = '<your key>'`). As with
the other settings, `.env.example` is documentation; `.env` files are not
automatically loaded. Never commit your key.

Extracted citation markers are matched to bibliography entries. The extractor
uses the [Semantic Scholar Academic Graph API](https://api.semanticscholar.org/api-docs/snippets)
to look up a DOI directly, or search bibliographic text and require an
unambiguous title/author/year match. Results include DOI, abstract, venue,
authors, title and year when the service provides them. The original entry is
always retained in `reference_metadata.raw_reference`, including in saved JSON
reports, and displayed in the claim detail view.

Missing keys make no network requests. Timeouts, invalid responses, unmatched
papers and unavailable fields do not interrupt verification. HTTP 429 or an
authentication failure stops further enrichment requests for that document;
raw bibliography text remains available. Lookups are cached per extraction and
limited to 20 requests with a 20-second request-admission budget and a maximum
3-second timeout per network operation. Only bibliography text/DOIs are sent
to Semantic Scholar; claims and uploaded PDF contents are not sent wholesale.
Metadata and abstracts are descriptive and are **not added as evidence** or
used to change verification labels. Missing bibliography mappings remain empty
instead of guessing a source from a numeric marker.

PDF/text parsing with page provenance → claim/citation pairs → supplied-source mapping → combined BM25 and TF-IDF candidates → cross-encoder reranking → NLI over multiple passages → numerical comparison → results.

- `POST /api/verify`: multipart `target_file` and optional repeated `source_files`; returns job ID.
- `POST /api/analyze-text`: JSON text submission; returns job ID.
- `GET /api/jobs/{id}`: queued/progress/completed/error, used by the UI.
- `GET /api/results/{id}`: completed report; 409 while pending, 422 on failure.
- `GET /api/export/{id}?format=json|csv`: export a completed report.
- `WS /api/ws/{id}`: replay current state and stream progress, including terminal errors.
- `GET /api/metrics`: run the evaluation dataset.
- `GET /api/health`: API health; interactive docs at `/docs`.

Results and terminal errors persist in `data/jobs`; interrupted pending jobs are reported after restart. Source indexes are isolated per job and reused within that job. Model weights are shared. This is a single-process local prototype; do not run multiple server workers against its in-memory job state.

## Tests and week-3 evaluation

```powershell
.\.venv312\Scripts\python.exe -m pytest -q
npm.cmd run build --prefix citeguard-frontend
.\.venv312\Scripts\python.exe -m app.evaluation.run_evaluation
```

The evaluation writes `evaluation_results.json` with extraction recall/precision, retrieval Recall@1/3/5, Precision@3, MRR, three-class accuracy and macro precision/recall/F1, average processing time, per-citation latency and failure rate. Failed documents remain in the denominator. Numerical mismatches map to CONTRADICTED for the plan's three-label evaluation. Precision@3 uses a fixed denominator of three; missing ranks count as nonrelevant. Empty gold evidence is excluded from retrieval metrics.

`evaluation/golden_standard.json` contains **nine synthetic fixtures**, with provenance, source mappings, evidence and expected labels. They check integration and basic behavior; they are not real-paper accuracy measurements or an independently human-reviewed benchmark. The team still needs to review labels and add representative real papers before reporting research results. Threshold/retrieval sweep scripts under `app/evaluation` are exploratory; do not tune and report accuracy on the same fixtures as if they were held-out data.

## Boundaries

- Source full texts are supplied locally; optional Semantic Scholar enrichment resolves bibliographic metadata, but does not download papers, bypass paywalls or perform OCR.
- Basic layouts are supported. Complex two-column reading order, cross-page sentence continuations, unusual citation styles and tables can require correction or pasted text.
- MNLI is a small general-domain model. It can abstain on complex claims or make errors. Scores are model confidence, not calibrated probabilities of truth.
- Numerical checks compare exact values and common units (including simple mg/g/kg and cm/m/km conversion). They do not fully reason about ranges, statistical significance, entity-role swaps or tables.
- Week-4 deployment, user accounts, large-scale benchmarking and production hardening are outside this repair.

The active frontend is `citeguard-frontend`; the older `frontend` directory is retained only as legacy code.
