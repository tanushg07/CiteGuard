import asyncio
import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.evaluation.evaluator import CiteGuardEvaluator

async def main():
    print("=" * 60)
    print(" Retrieval Optimization - Grid Search")
    print("=" * 60)
    
    evaluator = CiteGuardEvaluator("evaluation/golden_standard.json")
    
    chunk_sizes = [256, 512, 1024]
    top_ks = [10, 20, 50]
    
    results_table = []
    
    for chunk in chunk_sizes:
        for k in top_ks:
            print(f"Testing chunk_size={chunk}, top_k={k}...")
            # We fix NLI thresholds for retrieval tuning
            start = time.time()
            res = await evaluator.evaluate(
                chunk_size=chunk, 
                top_k=k, 
                entailment_threshold=0.7, 
                contradiction_threshold=0.7
            )
            elapsed = time.time() - start
            
            results_table.append({
                "chunk_size": chunk,
                "top_k": k,
                "mrr": res["mrr_score"],
                "recall_at_3": res["recall_at_3"],
                "time_s": round(elapsed, 1)
            })
            
    print("\n" + "=" * 60)
    print(f"{'Chunk Size':<12} | {'Top K':<8} | {'MRR':<8} | {'Recall@3':<10} | {'Time (s)':<8}")
    print("-" * 60)
    for r in results_table:
        print(f"{r['chunk_size']:<12} | {r['top_k']:<8} | {r['mrr']:<8.3f} | {r['recall_at_3']:<10.3f} | {r['time_s']:<8.1f}")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
