import httpx
import pytest
from app.services.reference_metadata import ReferenceEnricher, reference_for_marker
from app.services.extractor import Extractor
from app.services.document_parser import DocumentParser
from app.services.orchestrator import Orchestrator

RAW = '[1] Smith (2020). Reliable citation verification methods. Example Journal.'
PAPER = {'title': 'Reliable citation verification methods', 'year': 2020,
         'externalIds': {'DOI': '10.1234/example'}, 'abstract': 'A study abstract.',
         'venue': 'Example Journal', 'authors': [{'name': 'Alex Smith'}]}


def client(handler, key='test-key'):
    return ReferenceEnricher(api_key=key, transport=httpx.MockTransport(handler))


def test_missing_key_never_calls_api(monkeypatch):
    monkeypatch.delenv('SEMANTIC_SCHOLAR_API_KEY', raising=False)
    enricher = ReferenceEnricher(transport=httpx.MockTransport(lambda _: pytest.fail('Network called')))
    result = enricher.enrich(RAW)
    assert result.raw_reference == RAW
    assert result.status == 'missing_key'
    assert result.doi is None


def test_metadata_fields_and_duplicate_cache():
    requests = []
    def handler(request):
        requests.append(request)
        assert request.headers['x-api-key'] == 'test-key'
        assert 'abstract' in request.url.params['fields']
        return httpx.Response(200, json={'data': [PAPER]})
    enricher = client(handler)
    result = enricher.enrich(RAW)
    assert result.provider == 'semantic_scholar'
    assert (result.doi, result.abstract, result.venue, result.authors) == ('10.1234/example', 'A study abstract.', 'Example Journal', ['Alex Smith'])
    enricher.enrich(RAW)
    assert len(requests) == 1


@pytest.mark.parametrize('status', [429, 401, 403])
def test_rate_limit_and_auth_stop_document_requests(status):
    requests = []
    enricher = client(lambda request: requests.append(request) or httpx.Response(status))
    first = enricher.enrich(RAW)
    second = enricher.enrich(RAW + ' Another reference.')
    assert first.provider == second.provider == 'bibliography'
    assert len(requests) == 1
    assert second.raw_reference == RAW + ' Another reference.'


@pytest.mark.parametrize('response', [httpx.Response(500), httpx.Response(200, text='bad json'), httpx.Response(200, json={'data': None}), httpx.Response(200, json={'data': [None]})])
def test_errors_keep_raw_reference(response):
    result = client(lambda _: response).enrich(RAW)
    assert result.raw_reference == RAW
    assert result.provider == 'bibliography'


def test_timeout_fallback():
    def timeout(request):
        raise httpx.ReadTimeout('timeout', request=request)
    assert client(timeout).enrich(RAW).status == 'api_unavailable'


def test_wrong_or_ambiguous_search_does_not_enrich():
    wrong = dict(PAPER, title='An unrelated scientific study')
    assert client(lambda _: httpx.Response(200, json={'data': [wrong]})).enrich(RAW).status == 'not_found'
    assert client(lambda _: httpx.Response(200, json={'data': [PAPER, PAPER]})).enrich(RAW).status == 'ambiguous_match'
    for wrong in [dict(PAPER, year=2021), dict(PAPER, authors=[{'name': 'Alex Jones'}])]:
        assert client(lambda _: httpx.Response(200, json={'data': [wrong]})).enrich(RAW).status == 'not_found'


def test_doi_lookup_and_null_optional_fields():
    def handler(request):
        assert '/paper/DOI:10.1234/example' in str(request.url.copy_with(query=None)).replace('%3A', ':').replace('%2F', '/')
        return httpx.Response(200, json=dict(PAPER, abstract=None, venue=None))
    result = client(handler).enrich(RAW + ' doi:10.1234/example')
    assert result.status == 'enriched'
    assert result.abstract is None


def test_bibliography_mapping_and_wrapped_entry():
    parsed = DocumentParser().parse_text('The method is reliable [1].\nReferences\n[1] Smith (2020).\nReliable citation verification methods.\nExample Journal.\n[10] Jones. Other paper.')
    assert reference_for_marker('[1]', parsed['references']) == RAW
    assert reference_for_marker('(Smith, 2020)', parsed['references']) == RAW
    assert reference_for_marker('[2]', parsed['references']) == ''
    assert reference_for_marker('[1]', [RAW, RAW]) == ''
    pairs = Extractor().extract(parsed['paragraphs'], parsed['references'], client(lambda _: httpx.Response(200, json={'data':[PAPER]})))
    assert pairs[0].reference_metadata.doi == '10.1234/example'


@pytest.mark.asyncio
async def test_pipeline_retains_fallback_in_serialized_report(monkeypatch):
    monkeypatch.delenv('SEMANTIC_SCHOLAR_API_KEY', raising=False)
    result = await Orchestrator(use_models=False).run_pipeline(target_text='The method is reliable [1].\nReferences\n' + RAW)
    metadata = result.model_dump()['claims'][0]['reference_metadata']
    assert metadata['raw_reference'] == RAW
    assert metadata['status'] == 'missing_key'
    assert not result.claims[0].evidence_list
