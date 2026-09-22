import asyncio
import copy
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from app.core.schemas import (
    AnalysisResponse,
    DocumentSummary,
    PipelineStepUpdate,
    RetrievedEvidence,
    VerificationLabel,
    VerificationResult,
)
from app.services.document_parser import DocumentParser
from app.services.extractor import Extractor
from app.services.retriever import Retriever
from app.services.verifier import Verifier
from backend.config import get_settings

logger = logging.getLogger(__name__)

# Global storage for jobs
JOB_STORE: dict[str, AnalysisResponse] = {}

class Orchestrator:
    """
    CiteGuard Pipeline Orchestrator.
    Executes the 7-step citation verification pipeline end-to-end with real-time telemetry.
    """
    def __init__(self, use_models=None):
        self.parser = DocumentParser()
        self.extractor = Extractor()
        self.use_models = use_models if use_models is not None else get_settings().citeguard_mode == 'neural'
        self.retriever = Retriever(use_reranker=False)
        self.verifier = Verifier(use_nli=False)
    async def run_pipeline(
        self,
        target_path: str | None = None,
        target_text: str | None = None,
        source_paths: list[str] | None = None,
        source_names: list[str] | None = None,
        source_texts: list[dict[str, str]] | None = None,
        document_title: str = "Uploaded Document",
        progress_callback: Callable[[PipelineStepUpdate], Awaitable[None]] | None = None,
        job_id: str | None = None
    ) -> AnalysisResponse:
        """
        Runs the full 7-step pipeline asynchronously.
        """
        start_time = time.time()
        retriever = await asyncio.to_thread(Retriever, self.use_models, self.retriever.chunk_size, self.retriever.top_k)
        verifier = await asyncio.to_thread(Verifier, self.use_models, self.verifier.entailment_threshold, self.verifier.contradiction_threshold)
        warnings = []
        if not verifier.use_nli:
            warnings.append("NLI unavailable: conservative lexical baseline used; results are not neural verification.")
        if not retriever.use_reranker:
            warnings.append("Cross-encoder unavailable: lexical ranking used.")
        job_id = job_id or f"job_{uuid.uuid4().hex[:10]}"

        async def notify(step_id: int, name: str, status: str, detail: str = "", claims_found: int = 0, pct: int = 0):
            if progress_callback:
                update = PipelineStepUpdate(
                    step_id=step_id,
                    name=name,
                    status=status,
                    detail=detail,
                    claims_found=claims_found,
                    progress_percentage=pct
                )
                try:
                    await progress_callback(update)
                except Exception as e:
                    logger.debug(f"Progress callback error: {e}")

        try:
            # Step 1: PDF Ingestion & Parsing
            await notify(1, "PDF Ingestion & Parsing", "loading", "Extracting document structure and reference sections...", pct=10)
            
            if target_path:
                parsed_doc = await asyncio.wait_for(asyncio.to_thread(self.parser.parse, target_path), timeout=60.0)
                doc_name = document_title
            elif target_text:
                parsed_doc = await asyncio.wait_for(asyncio.to_thread(self.parser.parse_text, target_text, document_title), timeout=60.0)
                doc_name = document_title
            else:
                raise ValueError("Either target_path or target_text must be provided.")

            paragraphs = parsed_doc.get("paragraphs", [])
            references = parsed_doc.get("references", [])
        
            await notify(1, "PDF Ingestion & Parsing", "complete", f"Extracted {len(paragraphs)} paragraphs across {parsed_doc.get('total_pages', 1)} pages.", pct=20)

            # Step 2: Claim Extraction
            await notify(2, "Claim Extraction", "loading", "Scanning for bracketed and author-year citation markers...", pct=25)
        
            claims = await asyncio.to_thread(self.extractor.extract, paragraphs, references)
        
            await notify(2, "Claim Extraction", "complete", f"Identified {len(claims)} claim-citation pairs for verification.", claims_found=len(claims), pct=35)

            # Step 3: Source Identification
            await notify(3, "Source Identification", "loading", "Mapping citation markers to source documents and reference entries...", claims_found=len(claims), pct=45)
        
            sources_to_index: list[dict[str, Any]] = []

            # Ingest uploaded source files
            if source_paths:
                for source_index, s_path in enumerate(source_paths):
                    try:
                        s_parsed = await asyncio.wait_for(asyncio.to_thread(self.parser.parse, s_path), timeout=60.0)
                        for paragraph in s_parsed.get('paragraphs', []):
                            sources_to_index.append({
                                'name': source_names[source_index] if source_names else s_parsed.get('document_name', 'Source PDF'),
                                'text': paragraph['text'],
                                'page_number': paragraph['page_number'],
                            })
                    except Exception as e:
                        raise ValueError(f"Could not read uploaded source: {e}") from e

            # Ingest text sources
            if source_texts:
                for st in source_texts:
                    sources_to_index.append({
                        "name": st.get("name", "Referenced Paper"),
                        "text": st.get("text", ""),
                        "citation": st.get("citation", st.get("name", "Referenced Paper")),
                        "markers": st.get("markers", [])
                    })

            if not sources_to_index:
                warnings.append("No source documents supplied. Upload cited sources to verify claims.")
            # Each claim searches only explicitly mapped sources. A sole source is
            # the user's selected source; multiple sources require a marker/title match.
            from app.services.sources import sources_for_claim
            claim_sources = {c.id: sources_for_claim(c, sources_to_index, references) for c in claims}
            await asyncio.to_thread(retriever.add_sources, sources_to_index)
            if any(not selected for selected in claim_sources.values()) and sources_to_index:
                warnings.append("Some citations could not be mapped. Name source PDFs with their marker, e.g. [2] Study.pdf, or bibliography title.")
            if not claims:
                warnings.append("No supported citation formats were detected. No citations were invented.")

            await notify(3, "Source Identification", "complete", f"Indexed {len(sources_to_index)} source corpora with {len(retriever.chunks)} evidence passages.", claims_found=len(claims), pct=55)

            # Step 4: Evidence Retrieval
            await notify(4, "Evidence Retrieval", "loading", "Retrieving candidate evidence passages via BM25/TF-IDF...", claims_found=len(claims), pct=65)
        
            retrieved_map: dict[str, list[RetrievedEvidence]] = {}
            indexes = {}
            for index, claim in enumerate(claims, 1):
                await notify(4, "Evidence Retrieval", "loading", f"Retrieving evidence for citation {index}/{len(claims)}...", claims_found=len(claims), pct=65)
                selected = claim_sources[claim.id]
                key = tuple((source["name"], source["text"], source.get("page_number", 1)) for source in selected)
                if key not in indexes:
                    local = copy.copy(retriever)
                    await asyncio.to_thread(local.add_sources, selected)
                    indexes[key] = local
                local = indexes[key]
                candidates = await asyncio.to_thread(local.retrieve, claim, local.top_k, max(10, local.top_k)) if local.chunks else []
                retrieved_map[claim.id] = candidates

            await notify(4, "Evidence Retrieval", "complete", f"Retrieved candidate passages for all {len(claims)} claims.", claims_found=len(claims), pct=75)

            # Step 5: Cross-Encoder Re-ranking
            await notify(5, "Cross-Encoder Re-ranking", "loading", "Computing fine-grained semantic alignment scores...", claims_found=len(claims), pct=80)
            # Reranking is integrated into retriever.retrieve(); simulate fast validation checkpoint
            await notify(5, "Cross-Encoder Re-ranking", "complete", "Cross-encoder ranking complete." if retriever.use_reranker else "Lexical ranking only (cross-encoder unavailable).", claims_found=len(claims), pct=85)

            # Step 6: NLI Verification
            await notify(6, "NLI Verification", "loading", "Evaluating textual entailment, contradiction, and neutral alignment...", claims_found=len(claims), pct=90)

            verified_results: list[VerificationResult] = []
            for index, claim in enumerate(claims, 1):
                await notify(6, "NLI Verification", "loading", f"Verifying citation {index}/{len(claims)}...", claims_found=len(claims), pct=90)
                ev_list = retrieved_map.get(claim.id, [])
                v_res = await asyncio.to_thread(verifier.verify, claim, ev_list)
                v_res.reference_metadata = claim.reference_metadata
                verified_results.append(v_res)

            await notify(6, "NLI Verification", "complete", "NLI inference complete." if verifier.use_nli else "Conservative baseline complete; NLI unavailable.", claims_found=len(claims), pct=95)

            # Step 7: Numerical Verification & Summary
            await notify(7, "Numerical Verification", "loading", "Cross-referencing statistical values, metrics, and percentages...", claims_found=len(claims), pct=98)

            # Calculate summary statistics
            total = len(verified_results)
            supported = sum(1 for r in verified_results if r.status == VerificationLabel.SUPPORTED)
            contradicted = sum(1 for r in verified_results if r.status == VerificationLabel.CONTRADICTED)
            unrelated = sum(1 for r in verified_results if r.status == VerificationLabel.INSUFFICIENT)
            num_mismatch = sum(1 for r in verified_results if r.status == VerificationLabel.NUMERICAL_MISMATCH)

            supported_pct = round((supported / total * 100), 1) if total > 0 else 0.0
            avg_conf = round(sum(r.confidence for r in verified_results) / total, 1) if total > 0 else 0.0
            elapsed = round(time.time() - start_time, 2)

            summary = DocumentSummary(
                document_name=doc_name,
                total_claims=total,
                supported_count=supported,
                contradicted_count=contradicted,
                unrelated_count=unrelated,
                numerical_mismatch_count=num_mismatch,
                supported_percentage=supported_pct,
                average_confidence=avg_conf,
                processing_time_seconds=elapsed
            )

            response = AnalysisResponse(
                job_id=job_id,
                summary=summary,
                claims=verified_results,
                status="completed",
                warnings=warnings,
                engines={"retrieval": "bm25+tfidf", "reranker": "cross-encoder" if retriever.use_reranker else "lexical", "verification": "nli" if verifier.use_nli else "baseline"}
            )

            JOB_STORE[job_id] = response

            await notify(7, "Numerical Verification", "complete", f"Analysis finished in {elapsed}s. {supported}/{total} claims supported.", claims_found=total, pct=100)

            return response
        except Exception as e:
            error_msg = f"Pipeline Error: {str(e)}"
            await notify(99, "Error", "error", error_msg, pct=0)
            raise e
