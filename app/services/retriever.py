import logging
import functools
from typing import List, Optional, Dict, Any, Tuple

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import CrossEncoder

from app.core.schemas import ClaimCitationPair, RetrievedEvidence

logger = logging.getLogger(__name__)


class Retriever:
    """
    Two-stage Evidence Retriever:
    1. First stage: TF-IDF candidate selection (index built ONCE per document set).
    2. Second stage: Cross-Encoder neural re-ranking.
    """

    def __init__(self, use_reranker: bool = True, chunk_size: int = 512, top_k: int = 3):
        self.chunk_size = chunk_size
        self.top_k = top_k
        self.use_reranker = use_reranker

        # These are set by add_sources() and reused across all retrieve() calls
        self.chunks: List[str] = []
        self.source_citations: Dict[int, str] = {}
        self._tfidf_matrix = None
        self._vectorizer: Optional[TfidfVectorizer] = None

        if self.use_reranker:
            try:
                self.reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2", max_length=512)
            except Exception as e:
                logger.warning(f"Could not load CrossEncoder model ({e}). Using TF-IDF ranking only.")
                self.reranker = None
                self.use_reranker = False
        else:
            self.reranker = None

    def clear(self):
        """Clears all indexed chunks and resets the TF-IDF index."""
        self.chunks = []
        self.source_citations = {}
        self._tfidf_matrix = None
        self._vectorizer = None

    def add_sources(self, sources: List[Dict[str, Any]]):
        """
        Chunks all source documents and builds a single shared TF-IDF index.
        This MUST be called once before any retrieve() calls.
        Building the index per-claim is O(N*M) and is forbidden.
        """
        all_chunks: List[str] = []
        citation_map: Dict[int, str] = {}

        for src in sources:
            name = src.get("name", "Unknown Source")
            text = src.get("text", "")
            if not text.strip():
                logger.warning(f"Source '{name}' has empty text, skipping.")
                continue

            raw = [c.strip() for c in text.split("\n\n") if c.strip()]
            if not raw:
                raw = [c.strip() for c in text.split("\n") if c.strip()]

            for chunk in raw:
                clean = chunk.replace("\n", " ").strip()
                if len(clean) < 15:
                    continue
                words = clean.split()
                for i in range(0, len(words), self.chunk_size):
                    sub = " ".join(words[i : i + self.chunk_size])
                    if len(sub) >= 15:
                        idx = len(all_chunks)
                        all_chunks.append(sub)
                        citation_map[idx] = name

        if not all_chunks:
            logger.error("No valid chunks extracted from any source document.")
            return

        self.chunks = all_chunks
        self.source_citations = citation_map

        # Build the TF-IDF index ONCE here. retrieve() will only call transform(), never fit().
        self._vectorizer = TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2),
            sublinear_tf=True,
        )
        self._tfidf_matrix = self._vectorizer.fit_transform(self.chunks)
        logger.info(f"Retrieval index built: {len(self.chunks)} chunks from {len(sources)} sources.")

    def retrieve(
        self,
        claim: ClaimCitationPair,
        top_k: Optional[int] = None,
        candidate_k: int = 10,
    ) -> List[RetrievedEvidence]:
        """
        Retrieves top-k relevant evidence chunks for a claim.
        Uses TF-IDF for candidates (O(1) — index already built), then Cross-Encoder re-ranking.
        """
        if self._tfidf_matrix is None or self._vectorizer is None or not self.chunks:
            raise RuntimeError(
                "Retrieval index not initialized. Call add_sources() before retrieve()."
            )

        k = top_k if top_k is not None else self.top_k

        # Strip citation markers from query for cleaner retrieval
        clean_query = claim.text
        if claim.citation_marker:
            clean_query = clean_query.replace(claim.citation_marker, "").strip()
        if not clean_query:
            clean_query = claim.text

        # Only transform (never fit) — O(V) where V is vocabulary size
        query_vec = self._vectorizer.transform([clean_query])
        similarities = cosine_similarity(query_vec, self._tfidf_matrix).flatten()

        num_candidates = min(candidate_k, len(self.chunks))
        top_indices = similarities.argsort()[-num_candidates:][::-1]
        candidates = [(int(idx), float(similarities[idx])) for idx in top_indices]

        if not candidates:
            return []

        # Cross-Encoder Re-ranking
        if self.use_reranker and self.reranker is not None:
            model_inputs = [[claim.text, self.chunks[idx]] for idx, _ in candidates]
            try:
                rerank_scores = self.reranker.predict(model_inputs)
            except Exception as e:
                logger.warning(f"Cross-encoder failed for claim {claim.id}: {e}. Falling back to TF-IDF scores.")
                rerank_scores = [score for _, score in candidates]

            reranked = sorted(
                zip(candidates, rerank_scores), key=lambda x: x[1], reverse=True
            )

            results = []
            for (idx, _), score in reranked[:k]:
                doc_name = self.source_citations.get(idx, "Unknown Source")
                results.append(
                    RetrievedEvidence(
                        claim_id=claim.id,
                        source_document=doc_name,
                        evidence_text=self.chunks[idx],
                        relevance_score=float(score),
                        source_citation=doc_name,
                    )
                )
            return results
        else:
            results = []
            for idx, score in candidates:
                if score <= 0.0:
                    continue
                doc_name = self.source_citations.get(idx, "Unknown Source")
                results.append(
                    RetrievedEvidence(
                        claim_id=claim.id,
                        source_document=doc_name,
                        evidence_text=self.chunks[idx],
                        relevance_score=score,
                        source_citation=doc_name,
                    )
                )
                if len(results) >= k:
                    break
            return results
