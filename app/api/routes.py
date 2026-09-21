import os
import io
import csv
import json
import asyncio
import tempfile
import uuid
import logging
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

from app.core.schemas import (
    AnalysisResponse,
    PipelineStepUpdate,
    VerificationLabel,
)
from app.services.orchestrator import Orchestrator, JOB_STORE
from app.evaluation.evaluator import CiteGuardEvaluator

logger = logging.getLogger(__name__)
router = APIRouter()
orchestrator = Orchestrator()

# Active WebSocket connections by job_id
ACTIVE_CONNECTIONS: dict[str, list[WebSocket]] = {}


class TextAnalysisRequest(BaseModel):
    document_title: str = "Pasted Academic Text"
    target_text: str
    source_title: Optional[str] = "Referenced Paper"
    source_text: Optional[str] = None


class JobResponse(BaseModel):
    job_id: str


async def _broadcast(job_id: str, payload: dict):
    """Send a JSON payload to all WebSocket clients connected to this job."""
    if job_id not in ACTIVE_CONNECTIONS:
        return
    dead = []
    for ws in ACTIVE_CONNECTIONS[job_id]:
        try:
            await ws.send_json(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        ACTIVE_CONNECTIONS[job_id].remove(ws)


async def _run_pipeline_async(
    job_id: str,
    target_path: Optional[str] = None,
    source_paths: Optional[List[str]] = None,
    document_title: str = "Uploaded Document",
    target_text: Optional[str] = None,
    source_texts: Optional[List[dict]] = None,
):
    """
    Coroutine that drives the pipeline on the running event loop.
    This is scheduled via asyncio.ensure_future from an endpoint so it
    runs concurrently without blocking, and can safely await WebSocket sends.
    """
    try:
        async def progress_callback(update: PipelineStepUpdate):
            await _broadcast(job_id, {"status": "update", "data": update.dict()})

        response = await orchestrator.run_pipeline(
            target_path=target_path,
            target_text=target_text,
            source_paths=source_paths,
            source_texts=source_texts,
            document_title=document_title,
            progress_callback=progress_callback,
            job_id=job_id,
        )

        await _broadcast(job_id, {"status": "completed", "data": response.dict()})

    except Exception as e:
        logger.exception(f"[{job_id}] Pipeline failed: {e}")
        await _broadcast(job_id, {"status": "error", "message": f"Pipeline Error: {str(e)}"})

    finally:
        # Clean up temp files
        for path in (source_paths or []):
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
        if target_path and os.path.exists(target_path):
            try:
                os.remove(target_path)
            except OSError:
                pass


@router.post("/verify", response_model=JobResponse)
async def verify_documents(
    target_file: UploadFile = File(..., description="Target academic manuscript PDF"),
    source_files: List[UploadFile] = File(default=[], description="Optional cited source PDFs"),
):
    """
    Main verification endpoint: Ingests target manuscript PDF and optional source PDFs,
    executes the 7-step citation verification pipeline, and returns a job_id.
    Connect to /api/ws/{job_id} immediately after to receive real-time progress.
    """
    if not target_file.filename or not target_file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Target document must be a PDF file.")

    try:
        # Save target file to temp
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_target:
            content = await target_file.read()
            tmp_target.write(content)
            target_path = tmp_target.name

        # Save source files to temp if provided
        source_paths: List[str] = []
        for s_file in source_files:
            if s_file.filename and s_file.filename.lower().endswith(".pdf"):
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_source:
                    s_content = await s_file.read()
                    tmp_source.write(s_content)
                    source_paths.append(tmp_source.name)

        job_id = f"job_{uuid.uuid4().hex[:10]}"

        # Schedule the async pipeline coroutine on the running event loop.
        # This is the CORRECT way to run an async background task in FastAPI
        # without breaking WebSocket communication.
        asyncio.ensure_future(
            _run_pipeline_async(
                job_id=job_id,
                target_path=target_path,
                source_paths=source_paths or None,
                document_title=target_file.filename,
            )
        )

        return {"job_id": job_id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline initiation failed: {str(e)}")


@router.post("/analyze-text", response_model=JobResponse)
async def analyze_text(request: TextAnalysisRequest):
    """
    Direct text analysis endpoint: Useful for instant testing, manual snippet submission,
    or pre-parsed LaTeX/plain text.
    """
    if not request.target_text.strip():
        raise HTTPException(status_code=400, detail="Target text cannot be empty.")

    source_texts = []
    if request.source_text and request.source_text.strip():
        source_texts.append({
            "name": request.source_title or "Referenced Document",
            "text": request.source_text,
            "citation": request.source_title or "Referenced Document",
        })

    job_id = f"job_{uuid.uuid4().hex[:10]}"

    asyncio.ensure_future(
        _run_pipeline_async(
            job_id=job_id,
            target_text=request.target_text,
            source_texts=source_texts or None,
            document_title=request.document_title,
        )
    )

    return {"job_id": job_id}


@router.get("/benchmark", response_model=AnalysisResponse)
async def run_benchmark():
    """
    Executes a comprehensive academic benchmark verifying 5 diverse claims.
    Runs the full pipeline synchronously and returns the complete result.
    """
    target_manuscript = """
    Section 1: Introduction and Prior Work

    The efficiency of modern deep learning architectures has become paramount. Specifically, training time was reduced by 40% when utilizing the novel sparse attention mechanism compared to the standard dense transformer baseline [12], corroborating earlier findings in scalable self-attention.

    Section 2: Environmental Vulnerability

    Coastal vulnerability models must account for extreme bounds of climate projections. Recent IPCC assessments indicate that global mean sea level is projected to rise by 2.5 meters by the year 2100 under the RCP8.5 emission scenario [4], necessitating immediate adaptive infrastructure planning.

    Section 3: Clinical Findings

    Previous pharmacological interventions yielded mixed results. However, in the latest Phase II clinical trial, the administration of 50mg of Compound X daily showed no statistically significant reduction in systemic inflammation markers after 6 weeks [21].

    Section 4: Structural Graph Bottlenecks

    While structurally expressive, message-passing architectures possess inherent limitations. Graph Neural Networks (GNNs) naturally struggle to capture long-range dependencies due to the over-squashing phenomenon [8], where exponential information is compressed into fixed-size vectors.

    Section 5: Macroeconomic Observations

    Historical precedents of market volatility show varied recovery trajectories. For instance, the economic impact of the 2008 financial crisis resulted in a 5% contraction of global GDP in the subsequent fiscal year [33], a figure that took nearly half a decade to recover.
    """

    source_corpora = [
        {
            "name": "Vaswani et al., 2017. Attention Is All You Need. arXiv:1706.03762.",
            "text": "In our experiments with sparse attention on the WMT 2014 English-to-German translation task, the model achieved comparable BLEU scores while reducing overall training time by exactly 40% relative to the dense self-attention baseline.",
        },
        {
            "name": "IPCC, 2021: Climate Change 2021: The Physical Science Basis.",
            "text": "Under the highest emission scenario (RCP8.5), global mean sea level rise is projected to be likely in the range of 0.63–1.01 meters by 2100. A rise approaching 2 meters cannot be ruled out due to deep uncertainty in ice-sheet processes, but 2.5 meters is not supported by current modeling consensus.",
        },
        {
            "name": "Smith & Jones (2023). Efficacy of Compound X in Autoimmune Disorders.",
            "text": "Over the 6-week trial period, patients receiving a 50mg daily dose of Compound X exhibited a marked, statistically significant decrease (p < 0.01) in key systemic inflammation markers, notably C-reactive protein (CRP) and Interleukin-6 (IL-6), compared to the placebo group.",
        },
        {
            "name": "Alon and Yahav (2021). On the Bottleneck of Graph Neural Networks and its Practical Implications.",
            "text": "We demonstrate that the primary bottleneck in standard message-passing GNNs is the over-squashing effect. When the computation graph expands exponentially with depth, the model fails to propagate information across distant nodes without significant loss, directly limiting the capture of long-range dependencies.",
        },
        {
            "name": "World Bank Group (2009). Global Economic Prospects: Crisis, Finance, and Growth.",
            "text": "The report details the regulatory failures that precipitated the 2008 housing market collapse, emphasizing the lack of oversight in derivative markets and subprime mortgage lending practices.",
        },
    ]

    response = await orchestrator.run_pipeline(
        target_text=target_manuscript,
        source_texts=source_corpora,
        document_title="Sample_Academic_Evaluation_Benchmark.pdf",
    )
    return response


@router.get("/results/{job_id}", response_model=AnalysisResponse)
async def get_results(job_id: str):
    """Retrieves previous analysis results by job ID."""
    if job_id not in JOB_STORE:
        raise HTTPException(status_code=404, detail="Analysis job not found.")
    return JOB_STORE[job_id]


@router.get("/export/{job_id}")
async def export_results(job_id: str, format: str = "json"):
    """Exports verification results as structured JSON or CSV."""
    if job_id not in JOB_STORE:
        raise HTTPException(status_code=404, detail="Analysis job not found.")

    job = JOB_STORE[job_id]

    if format.lower() == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Claim ID",
            "Citation Marker",
            "Claim Text",
            "Status",
            "Confidence (%)",
            "Source Document",
            "Retrieved Evidence",
            "Numerical Alignment",
        ])
        for c in job.claims:
            writer.writerow([
                c.id,
                c.citation_marker,
                c.text,
                c.status.value,
                c.confidence,
                c.source_document,
                c.evidence,
                c.numerical_check or "N/A",
            ])
        output.seek(0)
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode("utf-8")),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="citeguard_report_{job_id}.csv"'},
        )
    else:
        return JSONResponse(
            content=job.dict(),
            headers={"Content-Disposition": f'attachment; filename="citeguard_report_{job_id}.json"'},
        )


@router.websocket("/ws/{job_id}")
async def websocket_pipeline_progress(websocket: WebSocket, job_id: str):
    """
    WebSocket endpoint streaming pipeline step updates and final status.
    The client must connect to this endpoint immediately after POSTing to /verify.
    All pipeline progress events are pushed here in real time.
    """
    await websocket.accept()
    if job_id not in ACTIVE_CONNECTIONS:
        ACTIVE_CONNECTIONS[job_id] = []
    ACTIVE_CONNECTIONS[job_id].append(websocket)

    # If the job is already done (client reconnected), push result immediately
    if job_id in JOB_STORE:
        try:
            await websocket.send_json({"status": "completed", "data": JOB_STORE[job_id].dict()})
        except Exception:
            pass

    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"status": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        if job_id in ACTIVE_CONNECTIONS and websocket in ACTIVE_CONNECTIONS[job_id]:
            ACTIVE_CONNECTIONS[job_id].remove(websocket)


@router.get("/metrics")
async def get_metrics():
    """
    Runs the evaluator against the golden dataset (or loads cached evaluation_results.json)
    and returns quantitative metrics for the dashboard.
    """
    eval_file = "evaluation_results.json"
    if os.path.exists(eval_file):
        with open(eval_file, "r") as f:
            return json.load(f)

    evaluator = CiteGuardEvaluator("evaluation/golden_standard.json", orchestrator=orchestrator)
    results = await evaluator.evaluate()
    with open(eval_file, "w") as f:
        json.dump(results, f, indent=4)
    return results
