import asyncio
import json
import os
import sys

# Ensure the root of the project is in the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.evaluation.evaluator import CiteGuardEvaluator


async def main():
    print("=" * 60)
    print(" CiteGuard End-to-End Evaluation Framework")
    print("=" * 60)
    print("Loading Golden Standard Dataset...")
    
    evaluator = CiteGuardEvaluator("evaluation/golden_standard.json")
    
    print("Running Pipeline against Ground Truth...")
    results = await evaluator.evaluate()
    
    # Save results
    output_path = "evaluation_results.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=4)
        
    print(f"\nEvaluation Complete! Results saved to {output_path}\n")
    print("=" * 60)
    print(" EVALUATION METRICS REPORT")
    print("=" * 60)
    print("--- Extraction Metrics ---")
    print(f"Citation Recall:     {results['citation_recall']:.2f}")
    print(f"Claim Precision:     {results['claim_precision']:.2f}")
    print("\n--- Retrieval Metrics ---")
    print(f"Recall@1:            {results['recall_at_1']:.2f}")
    print(f"Recall@3:            {results['recall_at_3']:.2f}")
    print(f"Precision@3:         {results['precision_at_3']:.2f}")
    print(f"Mean Reciprocal Rank:{results['mrr_score']:.2f}")
    print("\n--- Verification Metrics ---")
    print(f"Accuracy:            {results['accuracy']:.2f}")
    print(f"Precision:           {results['precision']:.2f}")
    print(f"Recall:              {results['recall']:.2f}")
    print(f"F1-Score:            {results['f1_score']:.2f}")
    print("\n--- System Metrics ---")
    print(f"Avg Processing Time: {results['avg_processing_time']:.2f}s per document")
    print(f"Avg Latency:         {results['avg_latency']:.2f}s per citation")
    print(f"Failure Rate:        {results['failure_rate']:.2f}")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
