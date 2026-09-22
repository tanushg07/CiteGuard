"""
Days 8-10: "Pass clean structured output to backend."

This is the actual handoff point between Document Processing (this module)
and everything downstream (Tanush's backend, and transitively Evidence
Retrieval / Verification). Nobody else should be reaching into ParsedDocument
directly -- they should call to_backend_payload() and get back plain,
JSON-serializable data that matches the agreed contract.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Union

from citeguard.document_processing.claim_citation_pairing import build_claim_citation_pairs
from citeguard.document_processing.parser import parse_document


def to_backend_payload(pdf: Union[str, Path, bytes], document_id: str | None = None) -> dict:
    """
    Args:
        pdf: path to a PDF file, or raw PDF bytes.
        document_id: identifier the backend uses for this document. Defaults
            to the filename (without extension) when pdf is a path; callers
            passing raw bytes should supply their own.

    Returns:
        A plain dict, safe to json.dumps() directly:
        {
          "document_id": "...",
          "claim_citation_pairs": [ {claim_id, claim, citation_id, page, paragraph}, ... ],
          "stats": {"pages": N, "sections": N, "references": N, "citations": N, "claims": N}
        }
    """
    if document_id is None:
        document_id = Path(pdf).stem if isinstance(pdf, (str, Path)) else "document"

    doc = parse_document(pdf)
    pairs = build_claim_citation_pairs(doc.claims)

    return {
        "document_id": document_id,
        "claim_citation_pairs": [p.model_dump() for p in pairs],
        "stats": {
            "pages": len(doc.pages),
            "sections": len(doc.sections),
            "references": len(doc.references),
            "citations": len(doc.citations),
            "claims": len(doc.claims),
        },
    }


def write_backend_payload(
    pdf: Union[str, Path, bytes], output_path: Union[str, Path], document_id: str | None = None
) -> Path:
    """Convenience wrapper: builds the payload and writes it as formatted JSON."""
    payload = to_backend_payload(pdf, document_id=document_id)
    output_path = Path(output_path)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return output_path
