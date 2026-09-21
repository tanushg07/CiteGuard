import json
import time
import os
import re
from typing import List, Dict, Any, Tuple
from app.services.orchestrator import Orchestrator
from app.core.schemas import VerificationLabel

class CiteGuardEvaluator:
    def __init__(self, dataset_path: str = "evaluation/golden_standard.json"):
        self.dataset_path = dataset_path
        self.orchestrator = Orchestrator()
        
    def _token_overlap(self, text1: str, text2: str) -> float:
        t1 = set(re.findall(r'\b\w+\b', text1.lower()))
        t2 = set(re.findall(r'\b\w+\b', text2.lower()))
        if not t1 or not t2:
            return 0.0
        return len(t1.intersection(t2)) / len(t1)

    async def evaluate(self, chunk_size: int = 512, top_k: int = 3, entailment_threshold: float = 0.7, contradiction_threshold: float = 0.7) -> Dict[str, Any]:
        with open(self.dataset_path, "r", encoding="utf-8") as f:
            dataset = json.load(f)

        # Apply parameters
        self.orchestrator.retriever.chunk_size = chunk_size
        self.orchestrator.retriever.top_k = top_k
        self.orchestrator.verifier.entailment_threshold = entailment_threshold
        self.orchestrator.verifier.contradiction_threshold = contradiction_threshold

        total_claims = 0
        extracted_claims_total = 0
        citation_matches = 0
        claim_matches = 0
        
        # Retrieval
        rank_sum = 0
        recall_at_1 = 0
        recall_at_3 = 0
        recall_at_5 = 0
        precision_at_3_sum = 0

        # Verification
        y_true = []
        y_pred = []

        # System
        processing_times = []
        failures = 0
        total_extracted_citations = 0

        for item in dataset:
            start_time = time.time()
            try:
                # Use PDF paths
                target_path = item["document_path"]
                source_paths = item["source_paths"]
                
                response = await self.orchestrator.run_pipeline(
                    target_path=target_path,
                    source_paths=source_paths,
                    document_title=os.path.basename(target_path)
                )
                
                proc_time = time.time() - start_time
                processing_times.append(proc_time)
                
                pred_claims = response.claims
                extracted_claims_total += len(pred_claims)
                total_extracted_citations += len(pred_claims)

                for gold_claim in item["claims"]:
                    total_claims += 1
                    
                    # 1. Extraction metrics
                    # Find best matching predicted claim by citation and text overlap
                    best_match = None
                    best_overlap = 0.0
                    for pc in pred_claims:
                        if gold_claim["citation_raw"] in pc.citation_marker:
                            overlap = self._token_overlap(gold_claim["claim_text"], pc.text)
                            if overlap > best_overlap:
                                best_overlap = overlap
                                best_match = pc
                                
                    if best_match:
                        citation_matches += 1
                        if best_overlap > 0.8:
                            claim_matches += 1
                            
                        # 2. Retrieval metrics
                        gold_evidence = gold_claim["gold_evidence"]
                        rank = 0
                        found_rank = -1
                        for ev in best_match.evidence_list:
                            rank += 1
                            if self._token_overlap(gold_evidence, ev.evidence_text) > 0.35 or self._token_overlap(ev.evidence_text, gold_evidence) > 0.35:
                                found_rank = rank
                                break
                                
                        if found_rank > 0:
                            rank_sum += (1.0 / found_rank)
                            if found_rank <= 1: recall_at_1 += 1
                            if found_rank <= 3: 
                                recall_at_3 += 1
                                precision_at_3_sum += (1.0 / min(3, len(best_match.evidence_list)))
                            if found_rank <= 5: recall_at_5 += 1
                            
                        # 3. Verification metrics
                        y_true.append(gold_claim["gold_label"].upper())
                        y_pred.append(best_match.status.value.upper().replace(" ", "_"))
                    else:
                        # Missed claim entirely
                        y_true.append(gold_claim["gold_label"].upper())
                        y_pred.append("INSUFFICIENT")

            except Exception as e:
                failures += 1
                processing_times.append(time.time() - start_time)
                print(f"Failed to process {item['document_path']}: {e}")

        # Compute aggregates
        citation_recall = citation_matches / total_claims if total_claims else 0
        claim_precision = claim_matches / extracted_claims_total if extracted_claims_total else 0
        
        mrr = rank_sum / total_claims if total_claims else 0
        r_at_1 = recall_at_1 / total_claims if total_claims else 0
        r_at_3 = recall_at_3 / total_claims if total_claims else 0
        r_at_5 = recall_at_5 / total_claims if total_claims else 0
        p_at_3 = precision_at_3_sum / total_claims if total_claims else 0
        
        # Verification (Micro Average for simplicity)
        correct = sum(1 for yt, yp in zip(y_true, y_pred) if yt == yp)
        accuracy = correct / len(y_true) if y_true else 0
        
        # Binary F1 treating SUPPORTED / CONTRADICTED as positive classes
        tp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == yp and yt in ["SUPPORTED", "CONTRADICTED"])
        fp = sum(1 for yt, yp in zip(y_true, y_pred) if yt != yp and yp in ["SUPPORTED", "CONTRADICTED"])
        fn = sum(1 for yt, yp in zip(y_true, y_pred) if yt != yp and yt in ["SUPPORTED", "CONTRADICTED"])
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        
        avg_time = sum(processing_times) / len(processing_times) if processing_times else 0
        avg_latency = sum(processing_times) / total_extracted_citations if total_extracted_citations else 0
        failure_rate = failures / len(dataset) if dataset else 0

        return {
            "citation_recall": round(citation_recall, 3),
            "claim_precision": round(claim_precision, 3),
            "recall_at_1": round(r_at_1, 3),
            "recall_at_3": round(r_at_3, 3),
            "recall_at_5": round(r_at_5, 3),
            "precision_at_3": round(p_at_3, 3),
            "mrr_score": round(mrr, 3),
            "accuracy": round(accuracy, 3),
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1_score": round(f1_score, 3),
            "avg_processing_time": round(avg_time, 3),
            "avg_latency": round(avg_latency, 3),
            "failure_rate": round(failure_rate, 3)
        }
