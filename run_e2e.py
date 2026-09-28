import asyncio
import json
import os
import sys

# Add the project root to sys.path so 'app' can be imported
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.orchestrator import Orchestrator

async def main():
    print("Initializing Orchestrator...")
    orchestrator = Orchestrator(use_models=False) # Use baseline mode for faster testing, or set True for neural if downloaded
    
    print("Running pipeline on attention.pdf...")
    response = await orchestrator.run_pipeline(
        target_path="attention.pdf",
        document_title="Attention is All You Need"
    )
    
    print("\n\n=== PIPELINE RESULTS ===")
    print("Summary:")
    print(response.summary.model_dump_json(indent=2))
    
    print("\nVerified Claims (First 5):")
    for claim in response.claims[:5]:
        print(f"\nClaim ID: {claim.id}")
        print(f"Marker: {claim.citation_marker}")
        print(f"Text: {claim.text}")
        if claim.reference_metadata:
            print(f"Reference Title: {claim.reference_metadata.title}")
            print(f"PDF URL: {claim.reference_metadata.pdf_url}")
        print(f"Verdict: {claim.status}")
        print(f"Confidence: {claim.confidence}%")
        print(f"Retrieved Evidence: {claim.evidence}")

if __name__ == "__main__":
    asyncio.run(main())
