import pytest
from unittest.mock import patch, MagicMock
from app.services.retriever import Retriever
from app.core.schemas import ClaimCitationPair

def test_retriever_success():
    # Pass use_reranker=False to test pure TF-IDF without loading ML models
    retriever = Retriever(use_reranker=False)
    
    source_text = (
        "This is a dummy paragraph that doesn't talk about accuracy.\n\n"
        "Here is the second chunk. The model achieved an accuracy of 95.2% on the test set. "
        "This is very good.\n\n"
        "A final chunk talking about training parameters and learning rates."
    )
    
    retriever.load_source(source_text, "dummy_source.pdf")
    
    claim = ClaimCitationPair(
        id="claim_123",
        text="The model achieved 95% accuracy.",
        citation_marker="[1]",
        page_number=1
    )
    
    evidence = retriever.retrieve(claim, top_k=2)
    
    assert len(evidence) > 0
    # The most relevant chunk should be the second one about accuracy
    assert "95.2%" in evidence[0].evidence_text
    assert evidence[0].claim_id == "claim_123"
    assert evidence[0].source_document == "dummy_source.pdf"

def test_retriever_no_source_loaded():
    retriever = Retriever(use_reranker=False)
    claim = ClaimCitationPair(
        id="claim_123",
        text="Test claim",
        citation_marker="[1]",
        page_number=1
    )
    
    with pytest.raises(RuntimeError, match="Source document not loaded"):
        retriever.retrieve(claim)
        
def test_retriever_no_overlap():
    retriever = Retriever(use_reranker=False)
    source_text = "Apples and oranges are different types of fruits that people eat.\n\nCars drive on the road and require gasoline or electricity to run."
    retriever.load_source(source_text, "source.txt")
    
    claim = ClaimCitationPair(
        id="claim_1",
        text="Quantum physics is complex.",
        citation_marker="[1]",
        page_number=1
    )
    
    evidence = retriever.retrieve(claim)
    # Cosine similarity will be 0.0, so it should return an empty list
    assert len(evidence) == 0

@patch('app.services.retriever.CrossEncoder')
def test_retriever_with_reranker(mock_cross_encoder):
    mock_instance = MagicMock()
    
    def fake_predict(pairs):
        scores = []
        for query, doc in pairs:
            if "GPU" in doc:
                scores.append(9.9)
            else:
                scores.append(0.1)
        return scores
        
    mock_instance.predict.side_effect = fake_predict
    mock_cross_encoder.return_value = mock_instance
    
    retriever = Retriever(use_reranker=True)
    
    source_text = "Apples and oranges are fruit.\n\nDeep learning requires GPUs."
    retriever.load_source(source_text, "test.txt")
    
    claim = ClaimCitationPair(
        id="claim_x",
        text="Neural networks run on graphics cards.",
        citation_marker="[1]",
        page_number=1
    )
    
    evidence = retriever.retrieve(claim, top_k=1)
    
    assert len(evidence) == 1
    assert "Deep learning requires GPUs" in evidence[0].evidence_text
    assert evidence[0].relevance_score == 9.9
