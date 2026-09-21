from typing import List, Dict, Any, Optional, Tuple
import logging
import math
import re
import functools
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import CrossEncoder
from app.core.schemas import ClaimCitationPair, RetrievedEvidence

logger = logging.getLogger(__name__)

@functools.lru_cache(maxsize=50)
def _compute_tfidf_cache(vectorizer, chunks_tuple: Tuple[str, ...]):
    return vectorizer.fit_transform(list(chunks_tuple))

class Retriever:
    """
    Two-stage Evidence Retriever:
    1. First stage: TF-IDF / BM25 candidate selection.
    2. Second stage: Cross-Encoder neural re-ranking.
    """
    def __init__(self, use_reranker: bool = True, chunk_size: int = 512, top_k: int = 3):
        self.vectorizer = TfidfVectorizer(
            stop_words='english',
            ngram_range=(1, 2),
            sublinear_tf=True
        )
        self.chunks: List[str] = []
        self.source_name: str = ""
        self.source_citations: Dict[int, str] = {}
        self.tfidf_matrix = None
        self.use_reranker = use_reranker
        self.chunk_size = chunk_size
        self.top_k = top_k

        if self.use_reranker:
            try:
                self.reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2', max_length=512)
            except Exception as e:
                logger.warning(f"Could not load CrossEncoder model ({e}). Using TF-IDF ranking.")
                self.reranker = None
                self.use_reranker = False
        else:
            self.reranker = None

    def clear(self):
        """Clears all indexed chunks."""
        self.chunks = []
        self.source_citations = {}
        self.tfidf_matrix = None

    def load_source(self, text: str, source_name: str, citation_info: str = ""):
        """
        Chunks the source text and builds the TF-IDF index.
        """
        self.source_name = source_name
        raw_chunks = [c.strip() for c in text.split('\n\n') if c.strip()]
        if not raw_chunks:
            raw_chunks = [c.strip() for c in text.split('\n') if c.strip()]

        self.chunks = []
        for chunk in raw_chunks:
            chunk_clean = chunk.replace('\n', ' ')
            if len(chunk_clean) > 10:
                # Naive chunking by words up to chunk_size
                words = chunk_clean.split()
                for i in range(0, len(words), self.chunk_size):
                    sub_chunk = " ".join(words[i:i+self.chunk_size])
                    self.chunks.append(sub_chunk)

        if not self.chunks:
            raise ValueError(f"Source document {source_name} yielded no valid chunks.")

        self.tfidf_matrix = self.vectorizer.fit_transform(self.chunks)

    def add_sources(self, sources: List[Dict[str, Any]]):
        """
        Loads multiple source documents into the retriever index.
        """
        all_chunks = []
        for src in sources:
            name = src.get("name", "Unknown Source")
            text = src.get("text", "")
            raw = [c.strip() for c in text.split('\n\n') if c.strip()]
            if not raw:
                raw = [c.strip() for c in text.split('\n') if c.strip()]
            for chunk in raw:
                clean = chunk.replace('\n', ' ').strip()
                if len(clean) > 10:
                    words = clean.split()
                    for i in range(0, len(words), self.chunk_size):
                        sub_chunk = " ".join(words[i:i+self.chunk_size])
                        idx = len(all_chunks)
                        all_chunks.append(sub_chunk)
                        self.source_citations[idx] = name

        self.chunks = all_chunks
        if self.chunks:
            self.source_name = sources[0].get("name", "Corpus")
            self.tfidf_matrix = _compute_tfidf_cache(self.vectorizer, tuple(self.chunks))

    def retrieve(self, claim: ClaimCitationPair, top_k: Optional[int] = None, candidate_k: int = 10) -> List[RetrievedEvidence]:
        """
        Retrieves top_k relevant chunks. Uses TF-IDF for candidates, then re-ranks with Cross-Encoder.
        """
        if self.tfidf_matrix is None or not self.chunks:
            raise RuntimeError("Source document not loaded. Call load_source() first.")
            
        k = top_k if top_k is not None else self.top_k

        clean_query = claim.text
        if claim.citation_marker:
            clean_query = clean_query.replace(claim.citation_marker, "").strip()

        query_vec = self.vectorizer.transform([clean_query if clean_query else claim.text])
        similarities = cosine_similarity(query_vec, self.tfidf_matrix).flatten()

        num_candidates = min(candidate_k, len(self.chunks))
        top_indices = similarities.argsort()[-num_candidates:][::-1]

        candidates = []
        for idx in top_indices:
            candidates.append((idx, float(similarities[idx])))

        if not candidates:
            return []

        # Cross-Encoder Re-ranking
        if self.use_reranker and self.reranker is not None:
            model_inputs = [[claim.text, self.chunks[idx]] for idx, _ in candidates]
            rerank_scores = self.reranker.predict(model_inputs)

            reranked_results = sorted(zip(candidates, rerank_scores), key=lambda x: x[1], reverse=True)

            results = []
            for (idx, _), score in reranked_results[:k]:
                doc_name = self.source_citations.get(idx, self.source_name)
                evidence = RetrievedEvidence(
                    claim_id=claim.id,
                    source_document=doc_name,
                    evidence_text=self.chunks[idx],
                    relevance_score=float(score),
                    source_citation=doc_name
                )
                results.append(evidence)
            return results
        else:
            results = []
            for idx, score in candidates:
                if score > 0.0:
                    doc_name = self.source_citations.get(idx, self.source_name)
                    evidence = RetrievedEvidence(
                        claim_id=claim.id,
                        source_document=doc_name,
                        evidence_text=self.chunks[idx],
                        relevance_score=score,
                        source_citation=doc_name
                    )
                    results.append(evidence)
                    if len(results) >= k:
                        break
            return results
