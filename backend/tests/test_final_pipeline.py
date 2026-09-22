"""Week 4 regression suite: external services are deterministic test doubles."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import requests
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.api import routes
from app.core.schemas import ClaimCitationPair, RetrievedEvidence, VerificationLabel
from app.main import app
from app.services.orchestrator import Orchestrator
from app.services.verifier import Verifier
from backend.config import Settings
from backend.modules.citation_extractor import CrossrefEnricher
from backend.modules.nli_verifier import ReasoningGenerator

RAW = '[1] Smith (2020). Reliable citation verification methods. Example Journal.'
WORK = {'title': ['Reliable citation verification methods'], 'DOI': '10.1234/example',
        'container-title': ['Example Journal'], 'author': [{'given': 'Alex', 'family': 'Smith'}],
        'published': {'date-parts': [[2020]]}, 'abstract': '<jats:p>A study &amp; results.</jats:p>'}


@pytest.fixture(autouse=True)
def no_live_apis(monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY', '')
    monkeypatch.setenv('CROSSREF_ENABLED', 'false')


def settings(**kwargs):
    return Settings(_env_file=None, **kwargs)


def response(payload, status=200):
    result = MagicMock(status_code=status)
    result.json.return_value = payload
    if status >= 400:
        result.raise_for_status.side_effect = requests.HTTPError()
    return result


def test_settings_load_file_and_environment(tmp_path, monkeypatch):
    path = tmp_path / '.env'
    path.write_text('GROQ_API_KEY=local-test-value\nCROSSREF_ENABLED=true\n')
    monkeypatch.delenv('GROQ_API_KEY')
    monkeypatch.delenv('CROSSREF_ENABLED')
    config = Settings(_env_file=path)
    assert config.groq_api_key.get_secret_value() == 'local-test-value'
    assert 'local-test-value' not in repr(config)
    monkeypatch.setenv('GROQ_API_KEY', 'shell-test-value')
    assert Settings(_env_file=path).groq_api_key.get_secret_value() == 'shell-test-value'


def test_crossref_requires_no_key_and_caches():
    request = MagicMock(return_value=response({'message': {'items': [WORK]}}))
    enricher = CrossrefEnricher(settings(crossref_enabled=True), request)
    result = enricher.enrich(RAW)
    assert result.provider == 'crossref'
    assert result.doi == WORK['DOI']
    assert result.authors == ['Alex Smith']
    assert result.venue == 'Example Journal'
    assert result.abstract == 'A study & results.'
    result.authors.clear()
    assert enricher.enrich(RAW).authors == ['Alex Smith']
    assert request.call_count == 1
    assert 'CiteGuard/1.0' in request.call_args.kwargs['headers']['User-Agent']
    assert request.call_args.kwargs['timeout'] <= 3


@pytest.mark.parametrize('failure', [requests.Timeout(), requests.ConnectionError(), ValueError('invalid JSON')])
def test_crossref_failure_preserves_raw(failure):
    enricher = CrossrefEnricher(settings(crossref_enabled=True), MagicMock(side_effect=failure))
    result = enricher.enrich(RAW)
    assert result.raw_reference == RAW
    assert result.status == 'api_unavailable'
    assert result.provider == 'bibliography'


@pytest.mark.parametrize('payload', [{'message': None}, {'message': {'items': [None]}}, {}, {'message': {'items': 'invalid'}}])
def test_crossref_malformed_response(payload):
    assert CrossrefEnricher(settings(crossref_enabled=True), MagicMock(return_value=response(payload))).enrich(RAW).status == 'api_unavailable'


def test_crossref_rate_limit_budget_and_ambiguity():
    request = MagicMock(return_value=response({}, 429))
    enricher = CrossrefEnricher(settings(crossref_enabled=True), request)
    assert enricher.enrich(RAW).status == 'rate_limited'
    assert enricher.enrich(RAW + ' different').status == 'rate_limited'
    assert request.call_count == 1
    enricher = CrossrefEnricher(settings(crossref_enabled=True), request)
    enricher.requests = 20
    assert enricher.enrich(RAW).status == 'budget_exceeded'
    ambiguous = MagicMock(return_value=response({'message': {'items': [WORK, WORK]}}))
    assert CrossrefEnricher(settings(crossref_enabled=True), ambiguous).enrich(RAW).status == 'ambiguous_match'


def test_crossref_doi_and_wrong_title():
    request = MagicMock(return_value=response({'message': WORK}))
    result = CrossrefEnricher(settings(crossref_enabled=True), request).enrich('doi:10.1234/example')
    assert result.doi == WORK['DOI']
    assert request.call_args.args[0].endswith('10.1234%2Fexample')
    request.return_value = response({'message': {'items': [dict(WORK, title=['An unrelated title'])]}})
    assert CrossrefEnricher(settings(crossref_enabled=True), request).enrich(RAW).status == 'not_found'


def verified():
    claim = ClaimCitationPair(id='c', text='The dose was 2 mg.', citation_marker='[1]')
    evidence = RetrievedEvidence(claim_id='c', source_document='source', evidence_text=claim.text, relevance_score=1)
    return Verifier(False).verify(claim, [evidence])


def test_missing_keys_use_template_without_client():
    factory = MagicMock(side_effect=AssertionError('Network must not be called'))
    generator = ReasoningGenerator(settings(groq_api_key=''), factory)
    result = generator.explain(verified(), False)
    assert result.reasoning_provider == 'template'
    assert 'lexical baseline' in result.reasoning
    factory.assert_not_called()


def test_groq_success_preserves_verdict_and_numerical_results():
    factory = MagicMock()
    client = factory.return_value.__enter__.return_value
    client.chat.completions.create.return_value = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
        content='The evidence contains the stated dose. The numerical value agrees with the claim.'))])
    result = verified()
    original = result.model_dump()
    generator = ReasoningGenerator(settings(groq_api_key='test-key'), factory)
    generator.explain(result, False)
    assert result.reasoning_provider == 'groq'
    assert result.status == original['status']
    assert result.numerical_comparison.model_dump() == original['numerical_comparison']
    assert client.chat.completions.create.call_args.kwargs['model'] == 'llama-3.1-8b-instant'
    assert factory.call_args.kwargs['max_retries'] == 0


@pytest.mark.parametrize('content', [None, '', 'Only one sentence.', 'x' * 2000])
def test_groq_invalid_output_falls_back(content):
    factory = MagicMock()
    factory.return_value.__enter__.return_value.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))])
    result = ReasoningGenerator(settings(groq_api_key='test-key'), factory).explain(verified(), False)
    assert result.reasoning_provider == 'template'


def test_groq_failure_disables_further_calls():
    factory = MagicMock(side_effect=RuntimeError('service unavailable'))
    generator = ReasoningGenerator(settings(groq_api_key='test-key'), factory)
    for _ in range(2):
        assert generator.explain(verified(), False).reasoning_provider == 'template'
    assert factory.call_count == 1


@pytest.mark.parametrize('filename,content', [('test.txt', b'plain text'), ('fake.pdf', b'not a PDF')])
def test_non_pdf_returns_400(filename, content):
    with TestClient(app) as client:
        assert client.post('/api/verify', files={'target_file': (filename, content)}).status_code == 400


def test_pipeline_websocket_closes_after_analysis(tmp_path, monkeypatch):
    monkeypatch.setattr(routes, 'JOBS', tmp_path)
    monkeypatch.setattr(routes, 'orchestrator', Orchestrator(use_models=False))
    with TestClient(app) as client:
        submitted = client.post('/api/analyze-text', json={
            'target_text': 'The dose was 2 mg [1].', 'source_text': 'The dose was 2 mg.'})
        assert submitted.status_code == 202
        job = submitted.json()['job_id']
        with client.websocket_connect('/api/ws/' + job) as socket:
            while True:
                event = socket.receive_json()
                if event['status'] == 'completed':
                    break
                assert event['status'] != 'error'
            assert event['data']['claims'][0]['reasoning_provider'] == 'template'
            with pytest.raises(WebSocketDisconnect) as closed:
                socket.receive_json()
            assert closed.value.code == 1000
        assert client.get('/api/results/' + job).status_code == 200


def test_unknown_job_websocket_closes_cleanly():
    with TestClient(app) as client, client.websocket_connect('/api/ws/job_0000000000') as socket:
        assert socket.receive_json()['status'] == 'error'
        with pytest.raises(WebSocketDisconnect) as closed:
            socket.receive_json()
        assert closed.value.code == 1000


@pytest.mark.asyncio
async def test_missing_env_full_pipeline(monkeypatch, tmp_path):
    monkeypatch.setattr(Settings, 'model_config', {**Settings.model_config, 'env_file': tmp_path / 'missing.env'})
    result = await Orchestrator(False).run_pipeline(target_text='The dose was 2 mg [1].\nReferences\n' + RAW)
    assert result.claims[0].status == VerificationLabel.INSUFFICIENT
    assert result.claims[0].reference_metadata.raw_reference == RAW
    assert result.claims[0].reasoning
