
import pytest

from app.core.schemas import VerificationLabel
from app.services.orchestrator import Orchestrator


@pytest.mark.asyncio
async def test_orchestrator_benchmark():
    orchestrator = Orchestrator()
    
    target_manuscript = """
    Section 1: Attention Experiments
    Specifically, training time was reduced by 40% when utilizing the novel sparse attention mechanism compared to the standard dense transformer baseline [12].

    Section 2: Clinical Trial
    However, in the latest Phase II clinical trial, the administration of 50mg of Compound X daily showed no statistically significant reduction in systemic inflammation markers after 6 weeks [21].
    """

    source_corpora = [
        {
            "markers": ["[12]"],
            "name": "Vaswani et al., 2017. Attention Is All You Need.",
            "text": "In our experiments with sparse attention on the WMT 2014 English-to-German translation task, the model achieved comparable BLEU scores while reducing overall training time by exactly 40% relative to the dense self-attention baseline."
        },
        {
            "markers": ["[21]"],
            "name": "Smith & Jones (2023). Efficacy of Compound X.",
            "text": "Over the 6-week trial period, patients receiving a 50mg daily dose of Compound X exhibited a marked, statistically significant decrease (p < 0.01) in key systemic inflammation markers, notably C-reactive protein (CRP) and Interleukin-6 (IL-6), compared to the placebo group."
        }
    ]

    steps_recorded = []
    async def on_progress(step_update):
        steps_recorded.append(step_update)

    response = await orchestrator.run_pipeline(
        target_text=target_manuscript,
        source_texts=source_corpora,
        document_title="Test_Paper.pdf",
        progress_callback=on_progress
    )

    assert response is not None
    assert response.status == "completed"
    assert response.summary.total_claims == 2
    assert len(response.claims) == 2
    assert len(steps_recorded) >= 7

    # First claim (Sparse attention reduction)
    claim1 = response.claims[0]
    assert "40%" in claim1.text
    assert claim1.status == VerificationLabel.SUPPORTED
    assert claim1.numerical_comparison.is_match is True

    # Second claim (Compound X)
    claim2 = response.claims[1]
    assert "50mg" in claim2.text
    # The small MNLI model may abstain on this complex clinical sentence.
    # It must never falsely mark the negated claim as supported.
    assert claim2.status in (VerificationLabel.CONTRADICTED, VerificationLabel.NUMERICAL_MISMATCH, VerificationLabel.INSUFFICIENT)
