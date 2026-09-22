"""Asynchronous jobs with replayable state and persisted results."""
import asyncio
import csv
import io
import json
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.evaluation.evaluator import CiteGuardEvaluator
from app.services.orchestrator import Orchestrator

router = APIRouter()
orchestrator = Orchestrator()
ROOT = Path(__file__).resolve().parents[2]
JOBS = ROOT / 'data' / 'jobs'
STATES = {}
TASKS = set()
MAX_BYTES = 25 * 1024 * 1024

class SourceText(BaseModel):
    name: str
    text: str
    markers: list[str] = Field(default_factory=list)

class TextAnalysisRequest(BaseModel):
    document_title: str = 'Pasted Academic Text'
    target_text: str = Field(max_length=2_000_000)
    source_title: str | None = 'Referenced Paper'
    source_text: str | None = Field(default=None, max_length=2_000_000)
    sources: list[SourceText] = Field(default_factory=list)


def persist(job_id, state):
    JOBS.mkdir(parents=True, exist_ok=True)
    temporary = JOBS / f'{job_id}.tmp'
    temporary.write_text(json.dumps(state), encoding='utf-8')
    temporary.replace(JOBS / f'{job_id}.json')


def state_for(job_id):
    if not __import__('re').fullmatch(r'job_[a-f0-9]{10}', job_id):
        raise HTTPException(404, 'Analysis job not found.')
    if job_id in STATES:
        return STATES[job_id]
    path = JOBS / f'{job_id}.json'
    if path.exists():
        state = json.loads(path.read_text(encoding='utf-8'))
        if state['status'] not in ('completed', 'error'):
            state = {'status': 'error', 'message': 'Server restarted during analysis. Please retry.'}
        return state
    raise HTTPException(404, 'Analysis job not found.')


async def run_job(job_id, cleanup, kwargs):
    try:
        async def progress(update):
            STATES[job_id] = {'status': 'update', 'data': update.model_dump()}
        result = await orchestrator.run_pipeline(job_id=job_id, progress_callback=progress, **kwargs)
        STATES[job_id] = {'status': 'completed', 'data': result.model_dump(mode='json')}
    except Exception as exc:
        STATES[job_id] = {'status': 'error', 'message': str(exc)}
    finally:
        persist(job_id, STATES[job_id])
        for path in cleanup:
            Path(path).unlink(missing_ok=True)


def submit(cleanup=(), **kwargs):
    job_id = f'job_{uuid.uuid4().hex[:10]}'
    STATES[job_id] = {'status': 'queued'}
    persist(job_id, STATES[job_id])
    task = asyncio.create_task(run_job(job_id, cleanup, kwargs))
    TASKS.add(task)
    task.add_done_callback(TASKS.discard)
    return {'job_id': job_id}


@router.get('/health')
def health():
    return {'status': 'healthy', 'mode': 'neural' if orchestrator.use_models else 'baseline'}


@router.post('/analyze-text', status_code=202)
async def analyze_text(request: TextAnalysisRequest):
    if not request.target_text.strip():
        raise HTTPException(400, 'Target text cannot be empty.')
    sources = [s.model_dump() for s in request.sources]
    if request.source_text and request.source_text.strip():
        sources.append({'name': request.source_title or 'Referenced Source', 'text': request.source_text})
    return submit(target_text=request.target_text, source_texts=sources, document_title=request.document_title)


@router.post('/verify', status_code=202)
async def verify_documents(target_file: UploadFile = File(...), source_files: list[UploadFile] = File(default=[])):
    paths = []
    try:
        if len(source_files) > 30:
            raise HTTPException(400, 'At most 30 source PDFs are allowed.')
        for upload in [target_file, *source_files]:
            if not upload.filename or not upload.filename.lower().endswith('.pdf'):
                raise HTTPException(400, 'All documents must be PDF files.')
            content = await upload.read(MAX_BYTES + 1)
            if len(content) > MAX_BYTES:
                raise HTTPException(413, 'Each PDF must be at most 25 MB.')
            if not content.startswith(b'%PDF-'):
                raise HTTPException(400, 'Invalid PDF content.')
            # Retain original names for source matching, without trusting filesystem paths.
            with tempfile.NamedTemporaryFile(delete=False, suffix='_' + Path(upload.filename.replace('\\', '/')).name) as temp:
                temp.write(content)
                paths.append(temp.name)
        return submit(cleanup=paths, target_path=paths[0], source_paths=paths[1:], source_names=[Path(f.filename.replace('\\', '/')).name for f in source_files], document_title=target_file.filename)
    except Exception:
        for path in paths:
            Path(path).unlink(missing_ok=True)
        raise


@router.get('/jobs/{job_id}')
def get_job(job_id: str):
    return state_for(job_id)


@router.get('/results/{job_id}')
def get_results(job_id: str):
    state = state_for(job_id)
    if state['status'] == 'error':
        raise HTTPException(422, state['message'])
    if state['status'] != 'completed':
        raise HTTPException(409, 'Analysis is still processing.')
    return state['data']


@router.get('/export/{job_id}')
def export(job_id: str, format: str = 'json'):
    data = get_results(job_id)
    if format == 'json':
        return Response(json.dumps(data, indent=2), media_type='application/json', headers={'Content-Disposition': f'attachment; filename={job_id}.json'})
    if format != 'csv':
        raise HTTPException(400, 'Format must be json or csv.')
    output = io.StringIO()
    writer = csv.writer(output)
    fields = ['id', 'citation_marker', 'text', 'status', 'confidence', 'source_document', 'evidence', 'numerical_check']
    writer.writerow(fields)
    for claim in data['claims']:
        writer.writerow([str(claim.get(f) or '') for f in fields])
    return Response(output.getvalue(), media_type='text/csv', headers={'Content-Disposition': f'attachment; filename={job_id}.csv'})


@router.websocket('/ws/{job_id}')
async def progress_socket(websocket: WebSocket, job_id: str):
    await websocket.accept()
    previous = None
    try:
        while True:
            state = state_for(job_id)
            if state != previous:
                await websocket.send_json(state)
                previous = state
            if state['status'] in ('completed', 'error'):
                break
            await asyncio.sleep(0.3)
    except (WebSocketDisconnect, RuntimeError):
        pass
    except HTTPException:
        await websocket.send_json({'status': 'error', 'message': 'Unknown job.'})
    finally:
        await websocket.close()


@router.get('/benchmark')
async def benchmark():
    dataset = json.loads((ROOT / 'evaluation/golden_standard.json').read_text(encoding='utf-8'))
    target = '\n\n'.join(item['target_text'] for item in dataset)
    sources = [source for item in dataset for source in item['sources']]
    result = await orchestrator.run_pipeline(target_text=target, source_texts=sources, document_title='Synthetic demonstration benchmark')
    state = {'status': 'completed', 'data': result.model_dump(mode='json')}
    STATES[result.job_id] = state
    persist(result.job_id, state)
    return result


@router.get('/metrics')
async def metrics():
    # Separate configuration from interactive jobs; never serve an unversioned stale cache.
    evaluator = CiteGuardEvaluator(str(ROOT / 'evaluation/golden_standard.json'))
    return await evaluator.evaluate()
