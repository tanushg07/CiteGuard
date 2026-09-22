"""Reproducible fixture evaluation. Failed documents stay in the denominator."""
import json
import time
from pathlib import Path

from sklearn.metrics import accuracy_score, precision_recall_fscore_support

from app.services.orchestrator import Orchestrator

ROOT = Path(__file__).resolve().parents[2]

class CiteGuardEvaluator:
    def __init__(self, dataset_path='evaluation/golden_standard.json', orchestrator=None):
        path = Path(dataset_path)
        self.dataset_path = path if path.is_absolute() else ROOT / path
        self.orchestrator = orchestrator or Orchestrator()

    async def evaluate(self, chunk_size=512, top_k=5, entailment_threshold=.7, contradiction_threshold=.7):
        data = json.loads(self.dataset_path.read_text(encoding='utf-8'))
        if not data:
            raise ValueError('Evaluation dataset is empty.')
        self.orchestrator.retriever.chunk_size = chunk_size
        self.orchestrator.retriever.top_k = top_k
        self.orchestrator.verifier.entailment_threshold = entailment_threshold
        self.orchestrator.verifier.contradiction_threshold = contradiction_threshold
        gold_count = sum(len(item['claims']) for item in data)
        matched = exact = extracted = failures = 0
        reciprocal = precision3 = 0
        retrieval_count = 0
        hits = {1: 0, 3: 0, 5: 0}
        truth, predictions, durations, details = [], [], [], []
        engines = {}
        for item in data:
            start = time.perf_counter()
            error = None
            claims = []
            try:
                response = await self.orchestrator.run_pipeline(
                    target_text=item.get('target_text'),
                    source_texts=item.get('sources'),
                    target_path=str(ROOT / item['document_path']) if item.get('document_path') else None,
                    source_paths=[str(ROOT / p) for p in item.get('source_paths', [])],
                    document_title=item.get('id', 'Evaluation document'))
                claims = response.claims
                engines = response.engines
                extracted += len(claims)
            except Exception as exc:
                failures += 1
                error = str(exc)
            durations.append(time.perf_counter() - start)
            used = set()
            for gold in item['claims']:
                expected = gold['gold_label'].upper().replace(' ', '_')
                expected = {'UNRELATED': 'INSUFFICIENT', 'NUMERICAL_MISMATCH': 'CONTRADICTED'}.get(expected, expected)
                pred = next((c for c in claims if c.citation_marker == gold['citation_raw'] and c.id not in used), None)
                actual = 'MISSING'
                if pred:
                    used.add(pred.id)
                    matched += 1
                    def normalize(text):
                        return ' '.join(text.replace(gold['citation_raw'], '').split()).replace(' .', '.').strip()
                    exact += normalize(pred.text) == normalize(gold['claim_text'])
                    actual = {'Unrelated': 'INSUFFICIENT', 'Numerical Mismatch': 'CONTRADICTED'}.get(pred.status.value, pred.status.value.upper())
                evidence = gold.get('gold_evidence', '')
                if evidence:
                    retrieval_count += 1
                    relevant = [i for i, ev in enumerate(pred.evidence_list if pred else [], 1)
                                if ' '.join(evidence.split()) in ' '.join(ev.evidence_text.split()) and ev.source_document == gold['gold_reference']]
                    if relevant:
                        reciprocal += 1 / min(relevant)
                        for k in hits:
                            hits[k] += min(relevant) <= k
                        precision3 += sum(rank <= 3 for rank in relevant) / 3
                truth.append(expected)
                predictions.append(actual)
                details.append({'id': gold['claim_id'], 'expected': expected, 'predicted': actual, 'error': error})
        precision, recall, f1, _ = precision_recall_fscore_support(truth, predictions,
            labels=['SUPPORTED', 'CONTRADICTED', 'INSUFFICIENT'], average='macro', zero_division=0)
        return {
            'dataset_kind': 'synthetic controlled fixtures; requires independent human review and real-paper expansion',
            'documents': len(data), 'gold_claims': gold_count, 'engines': engines,
            'citation_recall': matched / gold_count if gold_count else 0,
            'claim_precision': exact / extracted if extracted else 0,
            **{f'recall_at_{k}': hits[k] / retrieval_count if retrieval_count else 0 for k in hits},
            'precision_at_3': precision3 / retrieval_count if retrieval_count else 0,
            'mrr_score': reciprocal / retrieval_count if retrieval_count else 0,
            'accuracy': float(accuracy_score(truth, predictions)) if truth else 0,
            'precision': float(precision), 'recall': float(recall), 'f1_score': float(f1),
            'avg_processing_time': sum(durations) / len(data),
            'avg_latency': sum(durations) / gold_count if gold_count else 0,
            'failure_rate': failures / len(data), 'details': details,
        }
