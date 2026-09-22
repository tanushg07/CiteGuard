import logging
import math
import re
from collections import Counter
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.core.models import cross_encoder
from app.core.schemas import ClaimCitationPair, RetrievedEvidence


def CrossEncoder(*args, **kwargs):
    return cross_encoder()


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
        self.chunks: list[str] = []
        self.source_citations: dict[int, str] = {}
        self.source_pages: dict[int, int] = {}
        self._tfidf_matrix = None
        self._vectorizer: TfidfVectorizer | None = None

        if self.use_reranker:
            try:
                self.reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2", max_length=512)
            except Exception as e:
                logger.warning(f"Could not load CrossEncoder model ({e}). Using TF-IDF ranking only.")
                self.reranker = None
                self.use_reranker = False
        else:
            self.reranker = None

    def load_source(self, text, name):
        self.add_sources([{ "name": name, "text": text }])

    def clear(self):
        """Clears all indexed chunks and resets the TF-IDF index."""
        self.chunks = []
        self.source_citations = {}
        self.source_pages = {}
        self._tfidf_matrix = None
        self._vectorizer = None

    def add_sources(self, sources: list[dict[str, Any]]):
        """
        Chunks all source documents and builds a single shared TF-IDF index.
        This MUST be called once before any retrieve() calls.
        Building the index per-claim is O(N*M) and is forbidden.
        """
        self.clear()
        all_chunks: list[str] = []
        citation_map: dict[int, str] = {}

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
                        self.source_pages[idx] = src.get('page_number', 1)

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
        try:
            self._tfidf_matrix = self._vectorizer.fit_transform(self.chunks)
        except ValueError:
            self.clear()
        logger.info(f"Retrieval index built: {len(self.chunks)} chunks from {len(sources)} sources.")

    def retrieve(
        self,
        claim: ClaimCitationPair,
        top_k: int | None = None,
        candidate_k: int = 10,
    ) -> list[RetrievedEvidence]:
        """
        Retrieves top-k relevant evidence chunks for a claim.
        Uses TF-IDF for candidates (O(1) — index already built), then Cross-Encoder re-ranking.
        """
        if self._tfidf_matrix is None or self._vectorizer is None or not self.chunks:
            raise RuntimeError(
                "Source document not loaded; retrieval index not initialized. Call add_sources() before retrieve()."
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
        # BM25 adds term saturation and passage-length normalization to TF-IDF.
        docs = [Counter(re.findall(r'\w+', chunk.lower())) for chunk in self.chunks]
        query = set(re.findall(r'\w+', clean_query.lower()))
        lengths = [sum(doc.values()) for doc in docs]
        average = sum(lengths) / len(lengths) or 1
        bm25 = np.zeros(len(docs))
        for term in query:
            df = sum(term in doc for doc in docs)
            idf = math.log(1 + (len(docs) - df + .5) / (df + .5))
            for i, doc in enumerate(docs):
                frequency = doc[term]
                bm25[i] += idf * frequency * 2.5 / (frequency + 1.5 * (.25 + .75 * lengths[i] / average))
        if bm25.max() > 0:
            similarities = .5 * similarities + .5 * bm25 / bm25.max()

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
                        page_number=self.source_pages.get(idx, 1),
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
                        page_number=self.source_pages.get(idx, 1),
                    )
                )
                if len(results) >= k:
                    break
            return results
