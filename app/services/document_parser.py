import os
import re
import pdfplumber
from typing import List, Dict, Any, Optional

class DocumentParser:
    """
    Parses an academic PDF or text document into structured paragraphs and sections.
    """
    def __init__(self, file_path: Optional[str] = None):
        self.file_path = file_path
        self.extracted_references: List[str] = []

    def parse_text(self, raw_text: str, source_name: str = "Pasted Text") -> Dict[str, Any]:
        """
        Parses raw text into structured paragraphs and extracts any inline references.
        """
        lines = [l.strip() for l in raw_text.split("\n") if l.strip()]

        ref_section_started = False
        references = []
        main_paragraphs = []
        current_section = "Body"

        ref_headers = re.compile(r'^(references|bibliography|works cited|literature cited)\s*$', re.IGNORECASE)
        section_headers = re.compile(r'^(?:section\s+\d+[:\.]?|\d+\.?\s+[A-Za-z]+|[A-Za-z\s]+:)', re.IGNORECASE)

        for line in lines:
            if ref_headers.match(line):
                ref_section_started = True
                continue

            if ref_section_started:
                references.append(line)
                continue

            if section_headers.match(line) and len(line) < 60 and not line.endswith('.'):
                current_section = line
                continue

            clean_text = " ".join(line.split()).strip()
            if len(clean_text) > 15:
                main_paragraphs.append({
                    "text": clean_text,
                    "page_number": 1,
                    "section": current_section
                })

        self.extracted_references = references
        return {
            "document_name": source_name,
            "paragraphs": main_paragraphs if main_paragraphs else [{"text": raw_text.strip(), "page_number": 1, "section": "Body"}],
            "references": references,
            "total_pages": 1
        }

    def parse(self, file_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Extracts text from the PDF, grouping it into paragraphs along with page numbers.
        Returns a dict containing paragraphs, references, and metadata.
        """
        path = file_path or self.file_path
        if not path:
            raise RuntimeError("No file path provided for DocumentParser.")

        paragraphs = []
        references = []
        ref_section_started = False
        ref_header_pattern = re.compile(r'^(references|bibliography|works cited)\b', re.IGNORECASE)
        total_pages = 0

        try:
            with pdfplumber.open(path) as pdf:
                total_pages = len(pdf.pages)
                total_raw_text = ""
                for page_idx, page in enumerate(pdf.pages):
                    page_num = page_idx + 1
                    text = page.extract_text()
                    if not text:
                        continue
                    total_raw_text += text

                    # Split by double newline to approximate paragraphs
                    blocks = text.split("\n\n")
                    for block in blocks:
                        clean_text = " ".join(block.split("\n")).strip()
                        if ref_header_pattern.match(clean_text):
                            ref_section_started = True
                            continue

                        if ref_section_started:
                            references.append(clean_text)
                        elif len(clean_text) > 20:
                            paragraphs.append({
                                "text": clean_text,
                                "page_number": page_num,
                                "section": "Body"
                            })

                if len(total_raw_text.strip()) < 50:
                    raise RuntimeError("No extractable text found. Is this a scanned image PDF?")

        except RuntimeError as err:
            raise err
        except Exception as e:
            raise RuntimeError(f"Failed to parse PDF {path}: {str(e)}")

        self.extracted_references = references
        doc_name = os.path.basename(path) if path else "Uploaded Document"
        return {
            "document_name": doc_name,
            "paragraphs": paragraphs,
            "references": references,
            "total_pages": total_pages
        }
