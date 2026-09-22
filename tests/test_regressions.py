import asyncio
import time

import pytest
from fastapi.testclient import TestClient

from app.api import routes
from app.core.schemas import ClaimCitationPair, RetrievedEvidence, VerificationLabel
from app.main import app
from app.services.extractor import Extractor
from app.services.orchestrator import Orchestrator
from app.services.verifier import Verifier


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(routes, 'JOBS', tmp_path / 'jobs')
    monkeypatch.setattr(routes, 'orchestrator', Orchestrator(use_models=False))
    routes.STATES.clear()
    with TestClient(app) as session:
        yield session


def wait_job(client, job):
    for _ in range(100):
        response = client.get('/api/jobs/' + job)
        assert response.status_code == 200
        state = response.json()
        if state['status'] in ('completed', 'error'):
            return state
        time.sleep(.02)
    pytest.fail('Job did not finish')


def test_text_job_persistence_and_exports(client):
    response = client.post('/api/analyze-text', json={'target_text': 'The dose was 2 mg [1].', 'source_text': 'The dose was 2 mg.'})
    assert response.status_code == 202
    job = response.json()['job_id']
    state = wait_job(client, job)
    assert state['status'] == 'completed'
    assert state['data']['claims'][0]['status'] == 'Supported'
    routes.STATES.clear()
    assert client.get('/api/results/' + job).status_code == 200
    assert client.get('/api/export/' + job).json()['job_id'] == job
    assert 'The dose' in client.get('/api/export/' + job + '?format=csv').text
    assert client.get('/api/export/' + job + '?format=bad').status_code == 400
    with client.websocket_connect('/api/ws/' + job) as socket:
        assert socket.receive_json()['status'] == 'completed'


def test_invalid_upload_and_failed_job_replay(client):
    assert client.post('/api/verify', files={'target_file': ('bad.pdf', b'not a pdf')}).status_code == 400
    response = client.post('/api/verify', files={'target_file': ('bad.pdf', b'%PDF-1.4\ncorrupt')})
    job = response.json()['job_id']
    assert wait_job(client, job)['status'] == 'error'
    assert client.get('/api/results/' + job).status_code == 422
    with client.websocket_connect('/api/ws/' + job) as socket:
        assert socket.receive_json()['status'] == 'error'


@pytest.mark.asyncio
async def test_no_self_verification_or_invented_citation():
    runner = Orchestrator(use_models=False)
    result = await runner.run_pipeline(target_text='The dose was 2 mg [1].')
    assert result.claims[0].status == VerificationLabel.INSUFFICIENT
    assert not result.claims[0].evidence_list
    result = await runner.run_pipeline(target_text='This sentence contains no citations at all.')
    assert result.summary.total_claims == 0


@pytest.mark.asyncio
async def test_concurrent_jobs_and_source_isolation():
    runner = Orchestrator(use_models=False)
    async def analyze(word):
        return await runner.run_pipeline(target_text=f'The experiment studied {word} [1].', source_texts=[{'name':word, 'text':f'The experiment studied {word}.', 'markers':['[1]']}])
    results = await asyncio.gather(analyze('apples'), analyze('oranges'))
    assert results[0].claims[0].source_document == 'apples'
    assert results[1].claims[0].source_document == 'oranges'
    result = await runner.run_pipeline(target_text='The experiment studied apples [2].', source_texts=[{'name':'wrong', 'text':'The experiment studied apples.', 'markers':['[1]']}])
    assert result.claims[0].status == VerificationLabel.INSUFFICIENT


def test_groups_and_ranges():
    pairs = Extractor().extract([{'text':'The experiment studied apples [1, 3-5].', 'page_number':2}])
    assert [p.citation_marker for p in pairs] == ['[1]', '[3]', '[4]', '[5]']
    assert all(p.page_number == 2 for p in pairs)


@pytest.mark.parametrize('claim,evidence,match', [('2 mg','20 mg',False), ('5%','50%',False), ('2 mg','2 g',False), ('1 kg','1000 g',True), ('2.5 meters','2.5 meters',True), ('2020','2021',False)])
def test_exact_quantities(claim, evidence, match):
    assert Verifier(False)._check_numerical_match(claim, evidence) is match


def test_nli_threshold_and_multi_evidence():
    verifier = Verifier(False)
    verifier.use_nli = True
    verifier.nli_model = lambda pair: [{'label':'ENTAILMENT','score': .99 if 'blue' in pair['text'] else .45}, {'label':'NEUTRAL','score': .01 if 'blue' in pair['text'] else .55}]
    claim = ClaimCitationPair(id='c', text='The sky is blue.', citation_marker='[1]')
    evidence = [RetrievedEvidence(claim_id='c', source_document='s', evidence_text=text, relevance_score=.8) for text in ['The sky is discussed.', 'The sky is blue.']]
    assert verifier.verify(claim,evidence[:1]).status == VerificationLabel.INSUFFICIENT
    assert verifier.verify(claim,evidence).status == VerificationLabel.SUPPORTED
    assert verifier.verify(claim,evidence).evidence == 'The sky is blue.'


def test_pdf_upload_real_bytes(client):
    # Minimal valid one-page PDF, exercising actual extraction rather than a mock.
    stream = b'BT /F1 12 Tf 40 750 Td (The dose was 2 mg [1].) Tj ET'
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>', b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>', b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>', b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>', b'<< /Length '+ str(len(stream)).encode()+b' >>\nstream\n'+stream+b'\nendstream']
    data = b'%PDF-1.4\n'
    offsets = [0]
    for i, obj in enumerate(objects,1):
        offsets.append(len(data))
        data += f'{i} 0 obj\n'.encode()+obj+b'\nendobj\n'
    xref = len(data)
    data += b'xref\n0 6\n0000000000 65535 f \n'
    data += b''.join(f'{offset:010d} 00000 n \n'.encode() for offset in offsets[1:])
    data += f'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF'.encode()
    response = client.post('/api/verify', files=[('target_file',('manuscript.pdf',data)),('source_files',('[1] source.pdf',data))])
    state = wait_job(client,response.json()['job_id'])
    assert state['status'] == 'completed'
    assert state['data']['summary']['document_name'] == 'manuscript.pdf'
    assert state['data']['claims'][0]['page_number'] == 1
    assert state['data']['claims'][0]['evidence_list'][0]['page_number'] == 1
