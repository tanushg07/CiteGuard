import os
import tempfile
from typing import List
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.core.schemas import VerificationResult
from app.services.document_parser import DocumentParser
from app.services.extractor import Extractor
from app.services.retriever import Retriever
from app.services.verifier import Verifier

router = APIRouter()

# Initialize global singletons for ML models to avoid reloading on every request
# In a real production app, this would use dependency injection or app state
extractor = Extractor()
retriever = Retriever(use_reranker=True)
verifier = Verifier(use_nli=True)

@router.post("/verify", response_model=List[VerificationResult])
async def verify_document(
    target_file: UploadFile = File(...),
    source_file: UploadFile = File(...)
):
    """
    1. Parses the target document to find claims.
    2. Parses the source document to act as the evidence base.
    3. Retrieves top evidence for each claim.
    4. Verifies each claim against its evidence.
    """
    if not target_file.filename.endswith('.pdf') or not source_file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported for MVP.")

    # Save uploaded files to temporary files for processing
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_target:
        tmp_target.write(await target_file.read())
        target_path = tmp_target.name
        
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_source:
        tmp_source.write(await source_file.read())
        source_path = tmp_source.name

    try:
        # Step 1: Parse the target document
        target_parser = DocumentParser(target_path)
        target_paragraphs = target_parser.parse()
        
        # Step 2: Extract claims
        claims = extractor.extract(target_paragraphs)
        if not claims:
            return [] # No claims found
            
        # Step 3: Parse the source document to extract raw text
        source_parser = DocumentParser(source_path)
        source_paragraphs = source_parser.parse()
        
        # Combine source paragraphs into a single text block for the retriever
        source_text = "\n\n".join([p["text"] for p in source_paragraphs])
        
        # Load the text into the retriever
        retriever.load_source(source_text, source_file.filename)
        
        # Step 4 & 5: Retrieve and Verify
        results = []
        for claim in claims:
            evidence = retriever.retrieve(claim, top_k=1)
            result = verifier.verify(claim, evidence)
            results.append(result)
            
        return results

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Clean up temporary files
        if os.path.exists(target_path):
            os.remove(target_path)
        if os.path.exists(source_path):
            os.remove(source_path)
