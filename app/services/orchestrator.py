"""Whole-paper analysis followed by independently traced citation verification."""
import asyncio
import copy
import hashlib
import time
import uuid
from collections import Counter
from pathlib import Path

from app.core.schemas import AnalysisResponse, DocumentSummary, PipelineStepUpdate, VerificationLabel
from app.services.document_parser import DocumentParser
from app.services.extractor import Extractor
from app.services.reference_metadata import reference_for_marker
from app.services.retriever import Retriever
from app.services.source_resolver import SourceResolver
from app.services.sources import sources_for_claim
from app.services.verifier import Verifier
from backend.config import get_settings

JOB_STORE = {}


def finalize(result, claim, source):
    result.claim_group_id = claim.claim_group_id
    result.citation_id = claim.citation_id
    result.section = claim.section
    result.sentence_index = claim.sentence_index
    result.association_confidence = claim.association_confidence
    result.reference_metadata = claim.reference_metadata
    result.source_identification = {k:v for k,v in source.items() if k != 'passages'}
    result.retrieval = {'status': 'SUCCESS' if result.evidence_list else 'NO_EVIDENCE',
                        'top_k': len(result.evidence_list),
                        'top_rerank_score': max((e.rerank_score for e in result.evidence_list if e.rerank_score is not None), default=None)}
    verdict, reason = 'INSUFFICIENT_EVIDENCE', 'Retrieved evidence does not establish the complete claim.'
    if claim.claim_type == 'not_verifiable':
        verdict, reason = 'NOT_VERIFIABLE', 'This citation-bearing text is navigational, an acknowledgement, or a flattened table without a safely isolated assertion; inspect the original PDF.'
    elif source['status'] != 'FULL_TEXT':
        verdict, reason = source['status'], source['reason']
    elif not result.evidence_list:
        reason = 'Evidence retrieval failed for this citation or found no relevant passages.'
    elif result.nli.get('status') != 'SUCCESS':
        reason = 'NLI verification unavailable. Prepare the cached models with scripts/prepare_models.py; lexical overlap is not proof.'
    elif result.nli.get('truncated'):
        reason = 'The claim or evidence exceeded the NLI context window; full-claim support cannot be established.'
    elif result.confidence == 0:
        reason = 'Candidate passages give conflicting support and contradiction decisions.'
    elif result.status == VerificationLabel.CONTRADICTED:
        verdict, reason = 'CONTRADICTED', 'The NLI model finds contradiction in the selected source passage.'
    elif result.numerical_comparison and result.numerical_comparison.status == 'FAILED':
        verdict, reason = 'CONTRADICTED', 'An explicit numerical change disagrees with the claim; inspect the calculation.'
    elif result.numerical_comparison and result.numerical_comparison.status in ('NUMERICAL_CHECK_UNSUPPORTED', 'VALUES_MISSING'):
        reason = 'Numerical support is unresolved; missing values alone do not prove contradiction.'
    elif result.status == VerificationLabel.SUPPORTED:
        verdict, reason = 'SUPPORTED', 'NLI entails the claim and applicable numerical checks do not conflict.'
    result.final_verdict, result.decision_reason = verdict, reason
    return result


class Orchestrator:
    def __init__(self, use_models=None):
        self.parser = DocumentParser()
        self.extractor = Extractor()
        self.use_models = use_models if use_models is not None else get_settings().citeguard_mode == 'neural'
        self.retriever = Retriever(use_reranker=False)
        self.verifier = Verifier(use_nli=False)

    async def run_pipeline(self, target_path=None, target_text=None, source_paths=None, source_names=None,
                           source_texts=None, document_title='Uploaded Document', progress_callback=None, job_id=None):
        started = time.monotonic()
        job_id = job_id or f'job_{uuid.uuid4().hex[:10]}'
        warnings = []
        async def notify(step, name, status, detail, count=0, pct=0):
            if progress_callback:
                await progress_callback(PipelineStepUpdate(step_id=step, name=name, status=status,
                    detail=detail, claims_found=count, progress_percentage=pct))
        await notify(1, 'Analyzing whole paper', 'loading', 'Reading all pages and constructing the document structure.', pct=5)
        parser = DocumentParser()
        if target_path:
            document = await asyncio.wait_for(asyncio.to_thread(parser.parse, target_path), 120)
            target_digest = await asyncio.to_thread(lambda: hashlib.sha256(Path(target_path).read_bytes()).hexdigest())
        elif target_text:
            document = await asyncio.to_thread(parser.parse_text, target_text, document_title)
            target_digest = None
        else:
            raise ValueError('Either a PDF or target text is required.')
        await notify(1, 'Analyzing whole paper', 'complete', f"Read {document['total_pages']} pages and {len(document['sentences'])} sentences.", pct=15)
        await notify(2, 'Extracting citations', 'loading', 'Associating citation markers with local sentences.', pct=20)
        claims = self.extractor.extract(document['paragraphs'], document['references'], enrich=False)
        await notify(2, 'Extracting citations', 'complete', f'{len(claims)} claim-citation pairs detected.', len(claims),25)
        if not claims:
            warnings.append('No supported citation patterns were detected.')
        supplied = list(source_texts or [])
        for index, path in enumerate(source_paths or []):
            parsed = await asyncio.to_thread(DocumentParser().parse, path)
            supplied.extend({**p, 'name': source_names[index] if source_names else parsed['document_name']}
                            for p in parsed['paragraphs'])
        resolver = SourceResolver()
        source_records, claim_sources, source_states = {}, {}, {}
        await notify(3, 'Identifying source papers', 'loading', 'Matching references and retrieving accessible full text.', len(claims),30)
        raw_by_claim = {c.id: reference_for_marker(c.citation_marker, document['references']) for c in claims}
        # Schedule independent reference resolution with bounded concurrency and one task per reference.
        pending = {}
        for c in claims:
            local = sources_for_claim(c, supplied, document['references'])
            if local:
                claim_sources[c.id] = local
                source_states[c.id] = {'status': 'FULL_TEXT', 'source_id': 'USER-SUPPLIED', 'reason': 'Explicitly supplied source.', 'passages': local}
            elif raw_by_claim[c.id] not in pending:
                raw = raw_by_claim[c.id]
                pending[raw] = asyncio.create_task(resolver.resolve(raw))
        completed = 0
        # as_completed keeps progress moving even when an early reference is slow.
        async def identified(raw, task):
            try:
                return raw, await task
            except Exception:
                from app.core.schemas import ReferenceMetadata
                return raw, ({'status': 'SOURCE_UNAVAILABLE', 'reason': 'Source resolution failed for this reference.',
                              'source_id': 'SRC-' + hashlib.sha256(raw.encode()).hexdigest()[:12], 'passages': []}, ReferenceMetadata(raw_reference=raw))
        for task in asyncio.as_completed([identified(raw, task) for raw,task in pending.items()]):
            raw, (record, metadata) = await task
            if target_digest and record.get('sha256') == target_digest:
                record.update(status='SOURCE_UNAVAILABLE', reason='The resolved PDF is the submitted manuscript; self-verification is blocked.', passages=[])
            source_records[raw] = record
            for c in claims:
                if c.id not in claim_sources and raw_by_claim[c.id] == raw:
                    c.reference_metadata = metadata
                    claim_sources[c.id] = record.get('passages', [])
                    source_states[c.id] = record
            completed += 1
            await notify(3, 'Identifying source papers', 'loading', f'Resolved {completed}/{len(pending)} references: {record["status"]}.', len(claims),30+int(25*completed/max(1,len(pending))))
        await notify(3, 'Identifying source papers', 'complete', f'{sum(r["status"] == "FULL_TEXT" for r in source_records.values())} automatically retrieved source papers.',len(claims),55)
        await notify(4, 'Retrieving evidence', 'loading', 'Preparing local evidence indexes and available models.',len(claims),60)
        retriever = await asyncio.to_thread(Retriever, self.use_models, min(self.retriever.chunk_size, 250), self.retriever.top_k)
        verifier = await asyncio.to_thread(Verifier, self.use_models, self.verifier.entailment_threshold, self.verifier.contradiction_threshold)
        if not verifier.use_nli:
            warnings.append('MODEL_UNAVAILABLE: NLI verification unavailable; lexical matches cannot establish support. Run scripts/prepare_models.py.')
        if not retriever.use_reranker:
            warnings.append('MODEL_UNAVAILABLE: cross-encoder unavailable; using lexical retrieval.')
        indexes, retrieved = {}, {}
        for i,c in enumerate(claims,1):
            selected = claim_sources.get(c.id, [])
            key = tuple((s.get('source_id'),s['name'],s['text'],s.get('page_number',1)) for s in selected)
            try:
                if key not in indexes:
                    index = copy.copy(retriever)
                    await asyncio.to_thread(index.add_sources, selected)
                    indexes[key] = index
                index = indexes[key]
                retrieved[c.id] = await asyncio.to_thread(index.retrieve,c,index.top_k,10) if index.chunks else []
            except Exception:
                retrieved[c.id] = []
                warnings.append(f'Evidence retrieval failed for {c.id}.')
            await notify(4,'Retrieving evidence','loading',f'Retrieved candidates for {i}/{len(claims)} citations.',len(claims),60+int(15*i/max(1,len(claims))))
        await notify(4,'Retrieving evidence','complete','Evidence retrieval finished.',len(claims),75)
        await notify(5,'Reranking evidence','complete','Cross-encoder scores retained separately from lexical scores.' if retriever.use_reranker else 'Lexical ranking only; model unavailable.',len(claims),80)
        results = []
        for i,c in enumerate(claims,1):
            await notify(6,'Verifying claims','loading',f'Verifying {i}/{len(claims)} against source passages.',len(claims),80+int(15*i/max(1,len(claims))))
            try:
                result = await asyncio.to_thread(verifier.verify,c,retrieved.get(c.id,[]),False)
                finalize(result,c,source_states[c.id])
                # Partial support requires separately supported clauses, never a midrange confidence score.
                if result.final_verdict == 'INSUFFICIENT_EVIDENCE' and result.nli.get('status') == 'SUCCESS' and result.evidence_list:
                    import re
                    clauses = re.split(r';|\band\b', c.text)
                    if 1 < len(clauses) <= 3 and all(len(part.split()) >= 5 for part in clauses):
                        component_results = []
                        for part in clauses:
                            subclaim = c.model_copy(update={'text': part.strip()})
                            sub = await asyncio.to_thread(verifier.verify,subclaim,result.evidence_list,False)
                            finalize(sub,subclaim,source_states[c.id])
                            component_results.append({'text':part.strip(),'verdict':sub.final_verdict,'nli':sub.nli})
                        result.nli['components'] = component_results
                        verdicts = [r['verdict'] for r in component_results]
                        if 'SUPPORTED' in verdicts and 'INSUFFICIENT_EVIDENCE' in verdicts and 'CONTRADICTED' not in verdicts:
                            result.final_verdict = 'PARTIALLY_SUPPORTED'
                            result.decision_reason = 'At least one independently checked clause is supported; another remains unresolved.'
                result = await asyncio.to_thread(verifier.reasoner.explain,result,verifier.use_nli)
            except Exception:
                result = verifier._verify_one(c,[])
                finalize(result,c,source_states[c.id])
                result.final_verdict = 'INSUFFICIENT_EVIDENCE'
                result.decision_reason = 'Verification failed for this citation; no successful verdict was inferred.'
            results.append(result)
        await notify(6,'Verifying claims','complete','NLI and numerical decisions recorded.',len(claims),95)
        counts = Counter(r.final_verdict for r in results)
        summary = DocumentSummary(document_name=document_title,total_claims=len(results),
            total_pages=document['total_pages'],total_references=len(document['references']),
            unique_claims=len({c.claim_group_id for c in claims}),verdict_counts=dict(counts),
            supported_count=counts['SUPPORTED'],contradicted_count=counts['CONTRADICTED'],
            unrelated_count=counts['INSUFFICIENT_EVIDENCE'],numerical_mismatch_count=sum(r.numerical_comparison is not None and r.numerical_comparison.status=='FAILED' for r in results),
            supported_percentage=round(100*counts['SUPPORTED']/len(results),1) if results else 0,
            average_confidence=round(sum(r.confidence for r in results)/len(results),1) if results else 0,
            processing_time_seconds=round(time.monotonic()-started,2))
        response = AnalysisResponse(job_id=job_id,summary=summary,claims=results,document=document,
            sources=[{k:v for k,v in r.items() if k!='passages'} for r in source_records.values()],warnings=warnings,
            engines={'retrieval':'bm25+tfidf','reranker':'cross-encoder' if retriever.use_reranker else 'lexical',
                     'verification':'nli' if verifier.use_nli else 'MODEL_UNAVAILABLE'})
        JOB_STORE[job_id] = response
        await notify(7,'Report complete','complete',f'Analyzed {len(results)} citations across {document["total_pages"]} pages.',len(claims),100)
        return response
