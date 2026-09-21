import asyncio
import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.evaluation.evaluator import CiteGuardEvaluator

async def main():
    print("=" * 60)
    print(" NLI Optimization - Grid Search")
    print("=" * 60)
    
    evaluator = CiteGuardEvaluator("evaluation/golden_standard.json")
    
    thresholds = [0.5, 0.6, 0.7, 0.8]
    
    results_table = []
    
    for t in thresholds:
        print(f"Testing entailment_threshold={t}, contradiction_threshold={t}...")
        # We fix retrieval parameters for NLI tuning
        start = time.time()
        res = await evaluator.evaluate(
            chunk_size=512, 
            top_k=20, 
            entailment_threshold=t, 
            contradiction_threshold=t
        )
        elapsed = time.time() - start
        
        results_table.append({
            "threshold": t,
            "accuracy": res["accuracy"],
            "f1_score": res["f1_score"],
            "time_s": round(elapsed, 1)
        })
            
    print("\n" + "=" * 60)
    print(f"{'Threshold':<12} | {'Accuracy':<10} | {'F1-Score':<10} | {'Time (s)':<8}")
    print("-" * 60)
    for r in results_table:
        print(f"{r['threshold']:<12} | {r['accuracy']:<10.3f} | {r['f1_score']:<10.3f} | {r['time_s']:<8.1f}")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
