"""End-to-end pipeline boundaries and research-integrity regression cases."""
import socket
from unittest.mock import MagicMock

import httpx
import pytest

from app.core.schemas import ClaimCitationPair, ReferenceMetadata, RetrievedEvidence
from app.services.document_parser import DocumentParser, reference_record
from app.services.downloader import validate_url
from app.services.extractor import Extractor
from app.services.orchestrator import finalize
from app.services.reference_metadata import ArxivEnricher, BaseEnricher
from app.services.source_resolver import SourceResolver, identity_matches
from app.services.verifier import Verifier


def test_complete_paper_and_appendix_are_preserved():
    pages = ['Title\nAbstract\nThe full abstract describes the experimental evaluation.\n1 Introduction\nThe method improves accuracy [1].',
             'References\n[1] Smith. A reliable method. 2024.',
             'Appendix A\nThe method reduces latency [1].']
    result = DocumentParser()._structure(pages, 'paper')
    claims = Extractor().extract(result['paragraphs'],result['references'],enrich=False)
    assert result['total_pages'] == 3
    assert [c.page_number for c in claims] == [1,3]
    assert len(result['reference_records']) == 1
    assert all(c.sentence_index and c.claim_group_id and c.citation_id for c in claims)
    assert 'Appendix' not in result['references'][0]


def test_sentence_local_mapping_and_shared_claim_ids():
    parsed = DocumentParser().parse_text('The method reduces errors [1, 2]. Another method improves latency [3].')
    claims = Extractor().extract(parsed['paragraphs'],enrich=False)
    assert claims[0].claim_group_id == claims[1].claim_group_id
    assert claims[2].claim_group_id != claims[0].claim_group_id
    assert claims[2].citation_marker == '[3]'
    assert claims[0].association_confidence == 'uncertain'


def test_exact_arxiv_id_query_and_version_matching(monkeypatch):
    monkeypatch.setenv('ARXIV_ENABLED','true')
    xml = '''<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/abs/1607.06450v1</id><title>Layer Normalization</title><published>2016-07-21</published><author><name>Jimmy Ba</name></author><link title="pdf" href="https://arxiv.org/pdf/1607.06450v1"/></entry></feed>'''
    def handler(request):
        assert request.url.params['id_list'] == '1607.06450'
        assert 'search_query' not in request.url.params
        return httpx.Response(200,text=xml)
    result = ArxivEnricher(transport=httpx.MockTransport(handler)).enrich('Ba. Layer normalization. arXiv:1607.06450, 2016.')
    assert result.status == 'enriched'
    assert result.arxiv_id == '1607.06450v1'


def test_identifier_conflict_is_rejected():
    paper = {'title':'A reliable study', 'externalIds':{'DOI':'10.1234/wrong'},'year':2024,'authors':[{'name':'A Smith'}]}
    assert not BaseEnricher._matches(paper,'Smith. A reliable study. 2024.', '10.1234/right')
    assert not BaseEnricher._matches(paper,'Smith. A reliable study. 2023.', None)


def test_pdf_identity_cannot_match_only_its_bibliography():
    metadata = ReferenceMetadata(title='A reliable source study')
    parsed = {'pages':[{'text':'A different paper entirely'}, {'text':'References: A reliable source study'}]}
    assert identity_matches(metadata, parsed)[0] is False


@pytest.mark.asyncio
async def test_private_addresses_and_redirect_targets_are_blocked(monkeypatch):
    monkeypatch.setattr(socket,'getaddrinfo',lambda *a,**k: [(socket.AF_INET,socket.SOCK_STREAM,6,'',('127.0.0.1',443))])
    for url in ['http://127.0.0.1/secret','http://example.test/file.pdf','file:///etc/passwd','http://user:pass@example.com']:
        with pytest.raises(ValueError):
            await validate_url(url)


@pytest.mark.asyncio
async def test_duplicate_source_resolution_is_shared(monkeypatch):
    resolver = SourceResolver()
    async def resolved(raw):
        return {'status':'SOURCE_UNAVAILABLE'}, ReferenceMetadata(raw_reference=raw)
    called = MagicMock(side_effect=resolved)
    monkeypatch.setattr(resolver,'_resolve',called)
    import asyncio
    await asyncio.gather(resolver.resolve('reference'),resolver.resolve('reference'))
    assert called.call_count == 1


@pytest.mark.parametrize('claim, expected', [
    ('Accuracy improved by 12 percentage points.', 'PASSED'),
    ('Accuracy improved by 12%.', 'NUMERICAL_CHECK_UNSUPPORTED'),
    ('Accuracy improved by 16.9% relative to baseline.', 'PASSED'),
    ('Accuracy improved by 12% relative to baseline.', 'FAILED'),
])
def test_percentage_arithmetic(claim, expected):
    result = Verifier(False)._check_numerical_alignment(claim,'Accuracy improved from 71% to 83%.')
    assert result.status == expected
    assert result.calculation


def test_missing_model_does_not_make_lexical_match_a_final_support_verdict():
    claim = ClaimCitationPair(id='c',text='The dose was 2 mg.',citation_marker='[1]')
    evidence = RetrievedEvidence(claim_id='c',source_document='source',evidence_text=claim.text,relevance_score=1)
    result = Verifier(False).verify(claim,[evidence],False)
    finalize(result,claim,{'status':'FULL_TEXT','reason':'Retrieved source'})
    assert result.final_verdict == 'INSUFFICIENT_EVIDENCE'
    assert result.nli['status'] == 'MODEL_UNAVAILABLE'


@pytest.mark.parametrize('state',['SOURCE_UNAVAILABLE','SOURCE_METADATA_ONLY','EXTRACTION_FAILED'])
def test_source_state_never_becomes_unsupported_claim(state):
    claim = ClaimCitationPair(id='c',text='The dose was 2 mg.',citation_marker='[1]')
    result = Verifier(False).verify(claim,[],False)
    finalize(result,claim,{'status':state,'reason':'No readable original source'})
    assert result.final_verdict == state
    assert not result.evidence_list


def test_reference_identifier_normalization():
    record = reference_record('[12] Ba. Layer normalization. CoRR, abs/1607.06450, 2016.',12)
    assert record['arxiv_id'] == '1607.06450'
    assert record['citation_key'] == '[12]'
    assert record['reference_id'] == 'REF-012'


def test_navigation_and_flattened_tables_are_not_assertions():
    from app.services.extractor import Extractor
    assert Extractor._claim_type('In the following sections we will describe attention [1].') == 'not_verifiable'
    assert Extractor._claim_type('Results [1] BLEU 1 2 3 4 5 6 7 8 9 10 baseline') == 'not_verifiable'
    assert Extractor._claim_type('Accuracy increased from 71% to 83% [1].') == 'assertion_candidate'
