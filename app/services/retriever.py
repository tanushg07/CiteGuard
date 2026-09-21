from typing import List
import logging
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import CrossEncoder
from app.core.schemas import ClaimCitationPair, RetrievedEvidence

logger = logging.getLogger(__name__)

class Retriever:
    """
    Retrieves the most relevant chunks from a source document for a given claim.
    Uses TF-IDF for initial candidate retrieval, followed by Cross-Encoder re-ranking.
    """
    def __init__(self, use_reranker: bool = True):
        self.vectorizer = TfidfVectorizer(stop_words='english')
        self.chunks = []
        self.source_name = ""
        self.tfidf_matrix = None
        self.use_reranker = use_reranker
        
        # Load a small, fast cross-encoder model for MVP
        if self.use_reranker:
            logger.info("Loading CrossEncoder model...")
            self.reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2', max_length=512)
        else:
            self.reranker = None

    def load_source(self, text: str, source_name: str):
        """
        Chunks the source text and builds the TF-IDF index.
        """
        self.source_name = source_name
        raw_chunks = [c.strip() for c in text.split('\n\n') if c.strip()]
        if not raw_chunks:
            raw_chunks = [c.strip() for c in text.split('\n') if c.strip()]
            
        self.chunks = [chunk.replace('\n', ' ') for chunk in raw_chunks if len(chunk) > 10]
        
        if not self.chunks:
            raise ValueError(f"Source document {source_name} yielded no valid chunks.")
            
        self.tfidf_matrix = self.vectorizer.fit_transform(self.chunks)

    def retrieve(self, claim: ClaimCitationPair, top_k: int = 3, candidate_k: int = 10) -> List[RetrievedEvidence]:
        """
        Retrieves top_k relevant chunks. Uses TF-IDF to get candidate_k chunks,
        then re-ranks them using a Cross-Encoder if enabled.
        """
        if self.tfidf_matrix is None or not self.chunks:
            raise RuntimeError("Source document not loaded. Call load_source() first.")
            
        # 1. TF-IDF Initial Retrieval (Candidate Generation)
        query_vec = self.vectorizer.transform([claim.text])
        similarities = cosine_similarity(query_vec, self.tfidf_matrix).flatten()
        
        # Get up to candidate_k top indices
        num_candidates = min(candidate_k, len(self.chunks))
        top_indices = similarities.argsort()[-num_candidates:][::-1]
        
        candidates = []
        for idx in top_indices:
            # We always add candidates to let the reranker decide, 
            # unless we aren't using a reranker and the score is 0.0
            candidates.append((idx, float(similarities[idx])))
                
        if not candidates:
            return []
            
        # 2. Cross-Encoder Re-ranking
        if self.use_reranker and self.reranker is not None:
            # Prepare pairs: (Query, Passage)
            model_inputs = [[claim.text, self.chunks[idx]] for idx, _ in candidates]
            # Predict relevance scores
            rerank_scores = self.reranker.predict(model_inputs)
            
            # Combine scores with indices and sort descending
            reranked_results = sorted(zip(candidates, rerank_scores), key=lambda x: x[1], reverse=True)
            
            results = []
            for (idx, _), score in reranked_results[:top_k]:
                # We can return negative/low scores from reranker, it's up to Verification
                evidence = RetrievedEvidence(
                    claim_id=claim.id,
                    source_document=self.source_name,
                    evidence_text=self.chunks[idx],
                    relevance_score=float(score)
                )
                results.append(evidence)
            return results
            
        else:
            # Fallback: Just return TF-IDF results, filtering out 0.0 scores
            results = []
            for idx, score in candidates:
                if score > 0.0:
                    evidence = RetrievedEvidence(
                        claim_id=claim.id,
                        source_document=self.source_name,
                        evidence_text=self.chunks[idx],
                        relevance_score=score
                    )
                    results.append(evidence)
                    if len(results) >= top_k:
                        break
            return results
