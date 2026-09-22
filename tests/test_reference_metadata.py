import httpx
import pytest

from app.services.document_parser import DocumentParser
from app.services.extractor import Extractor
from app.services.orchestrator import Orchestrator
from app.services.reference_metadata import OpenAlexEnricher, ArxivEnricher, reference_for_marker

RAW = '[1] Smith (2020). Reliable citation verification methods. Example Journal.'
OPENALEX_PAPER = {
    'title': 'Reliable citation verification methods', 
    'publication_year': 2020,
    'doi': 'https://doi.org/10.1234/example',
    'abstract_inverted_index': {'A': [0], 'study': [1], 'abstract.': [2]},
    'primary_location': {'source': {'display_name': 'Example Journal'}},
    'authorships': [{'author': {'display_name': 'Alex Smith'}}]
}

def client(handler, enricher_cls):
    return enricher_cls(transport=httpx.MockTransport(handler))


def test_missing_settings_never_calls_api(monkeypatch):
    monkeypatch.setenv('OPENALEX_ENABLED', 'false')
    enricher = OpenAlexEnricher(transport=httpx.MockTransport(lambda _: pytest.fail('Network called')))
    result = enricher.enrich(RAW)
    assert result.raw_reference == RAW
    assert result.status == 'disabled'
    assert result.doi is None


def test_metadata_fields_and_duplicate_cache():
    requests = []
    def handler(request):
        requests.append(request)
        assert request.url.params['per-page'] == '3'
        return httpx.Response(200, json={'results': [OPENALEX_PAPER]})
    
    enricher = client(handler, OpenAlexEnricher)
    result = enricher.enrich(RAW)
    assert result.provider == 'openalex'
    assert (result.doi, result.abstract, result.venue, result.authors) == ('10.1234/example', 'A study abstract.', 'Example Journal', ['Alex Smith'])
    
    enricher.enrich(RAW)
    assert len(requests) == 1


@pytest.mark.parametrize('status', [429, 401, 403])
def test_rate_limit_and_auth_stop_document_requests(status):
    requests = []
    enricher = client(lambda request: requests.append(request) or httpx.Response(status), OpenAlexEnricher)
    first = enricher.enrich(RAW)
    second = enricher.enrich(RAW + ' Another reference.')
    assert first.provider == second.provider == 'bibliography'
    assert len(requests) == 1
    assert second.raw_reference == RAW + ' Another reference.'


@pytest.mark.parametrize('response', [httpx.Response(500), httpx.Response(200, text='bad json'), httpx.Response(200, json={'results': None}), httpx.Response(200, json={'results': [None]})])
def test_errors_keep_raw_reference(response):
    result = client(lambda _: response, OpenAlexEnricher).enrich(RAW)
    assert result.raw_reference == RAW
    assert result.provider == 'bibliography'


def test_timeout_fallback():
    def timeout(request):
        raise httpx.ReadTimeout('timeout', request=request)
    assert client(timeout, OpenAlexEnricher).enrich(RAW).status == 'api_unavailable'


def test_wrong_or_ambiguous_search_does_not_enrich():
    wrong = dict(OPENALEX_PAPER, title='An unrelated scientific study')
    assert client(lambda _: httpx.Response(200, json={'results': [wrong]}), OpenAlexEnricher).enrich(RAW).status == 'not_found'
    assert client(lambda _: httpx.Response(200, json={'results': [OPENALEX_PAPER, OPENALEX_PAPER]}), OpenAlexEnricher).enrich(RAW).status == 'ambiguous_match'
    
    wrong_year = dict(OPENALEX_PAPER, publication_year=2021)
    wrong_author = dict(OPENALEX_PAPER, authorships=[{'author': {'display_name': 'Alex Jones'}}])
    for wrong_doc in [wrong_year, wrong_author]:
        assert client(lambda _: httpx.Response(200, json={'results': [wrong_doc]}), OpenAlexEnricher).enrich(RAW).status == 'not_found'


def test_doi_lookup_and_null_optional_fields():
    def handler(request):
        assert 'doi.org/10.1234/example' in str(request.url)
        return httpx.Response(200, json=dict(OPENALEX_PAPER, abstract_inverted_index=None, primary_location=None))
    result = client(handler, OpenAlexEnricher).enrich(RAW + ' doi:10.1234/example')
    assert result.status == 'enriched'
    assert result.abstract is None
    assert result.venue is None


def test_bibliography_mapping_and_wrapped_entry():
    parsed = DocumentParser().parse_text('The method is reliable [1].\nReferences\n[1] Smith (2020).\nReliable citation verification methods.\nExample Journal.\n[10] Jones. Other paper.')
    assert reference_for_marker('[1]', parsed['references']) == RAW
    assert reference_for_marker('(Smith, 2020)', parsed['references']) == RAW
    assert reference_for_marker('[2]', parsed['references']) == ''
    assert reference_for_marker('[1]', [RAW, RAW]) == ''
    
    pairs = Extractor().extract(parsed['paragraphs'], parsed['references'], client(lambda _: httpx.Response(200, json={'results':[OPENALEX_PAPER]}), OpenAlexEnricher))
    assert pairs[0].reference_metadata.doi == '10.1234/example'


@pytest.mark.asyncio
async def test_pipeline_retains_fallback_in_serialized_report(monkeypatch):
    monkeypatch.setenv('OPENALEX_ENABLED', 'false')
    monkeypatch.setenv('CROSSREF_ENABLED', 'false')
    monkeypatch.setenv('ARXIV_ENABLED', 'false')
    result = await Orchestrator(use_models=False).run_pipeline(target_text='The method is reliable [1].\nReferences\n' + RAW)
    metadata = result.model_dump()['claims'][0]['reference_metadata']
    assert metadata['raw_reference'] == RAW
    assert metadata['status'] == 'disabled'
    assert not result.claims[0].evidence_list
