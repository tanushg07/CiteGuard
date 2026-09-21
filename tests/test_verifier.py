import pytest
from unittest.mock import patch, MagicMock
from app.services.verifier import Verifier
from app.core.schemas import ClaimCitationPair, RetrievedEvidence, VerificationLabel

def test_verifier_no_evidence():
    verifier = Verifier(use_nli=False)
    claim = ClaimCitationPair(id="1", text="Test", citation_marker="[1]", page_number=1)
    
    result = verifier.verify(claim, [])
    
    assert result.nli_label == VerificationLabel.INSUFFICIENT
    assert result.numerical_match is None

def test_verifier_numerical_match_success():
    verifier = Verifier(use_nli=False)
    claim = ClaimCitationPair(id="1", text="Accuracy is 95.5%.", citation_marker="[1]", page_number=1)
    evidence = [
        RetrievedEvidence(claim_id="1", source_document="doc", evidence_text="We got 95.5% accuracy.", relevance_score=0.9)
    ]
    
    result = verifier.verify(claim, evidence)
    
    assert result.numerical_match is True

def test_verifier_numerical_match_failure():
    verifier = Verifier(use_nli=False)
    claim = ClaimCitationPair(id="1", text="Accuracy is 95.5%.", citation_marker="[1]", page_number=1)
    evidence = [
        RetrievedEvidence(claim_id="1", source_document="doc", evidence_text="We got 88.0% accuracy.", relevance_score=0.9)
    ]
    
    result = verifier.verify(claim, evidence)
    
    assert result.numerical_match is False

@patch('app.services.verifier.pipeline')
def test_verifier_with_nli_entailment(mock_pipeline):
    mock_model = MagicMock()
    # Mocking pipeline output
    mock_model.return_value = [{'label': 'ENTAILMENT', 'score': 0.99}, {'label': 'CONTRADICTION', 'score': 0.01}]
    mock_pipeline.return_value = mock_model
    
    verifier = Verifier(use_nli=True)
    claim = ClaimCitationPair(id="1", text="The sky is blue.", citation_marker="[1]", page_number=1)
    evidence = [
        RetrievedEvidence(claim_id="1", source_document="doc", evidence_text="The sky appears blue.", relevance_score=0.9)
    ]
    
    result = verifier.verify(claim, evidence)
    
    assert result.nli_label == VerificationLabel.SUPPORTED
    assert result.nli_confidence == 0.99

@patch('app.services.verifier.pipeline')
def test_verifier_numerical_override(mock_pipeline):
    # Test that a numerical contradiction overrides an NLI Entailment
    mock_model = MagicMock()
    mock_model.return_value = [{'label': 'ENTAILMENT', 'score': 0.99}]
    mock_pipeline.return_value = mock_model
    
    verifier = Verifier(use_nli=True)
    claim = ClaimCitationPair(id="1", text="We found 100 cats.", citation_marker="[1]", page_number=1)
    evidence = [
        RetrievedEvidence(claim_id="1", source_document="doc", evidence_text="We found 50 cats.", relevance_score=0.9)
    ]
    
    result = verifier.verify(claim, evidence)
    
    # NLI says entailment, but numbers (100 != 50) contradict!
    assert result.numerical_match is False
    assert result.nli_label == VerificationLabel.CONTRADICTED
