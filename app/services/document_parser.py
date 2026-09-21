import pdfplumber
from typing import List, Dict

class DocumentParser:
    """
    Parses an academic PDF document into structured paragraphs.
    """
    def __init__(self, file_path: str):
        self.file_path = file_path

    def parse(self) -> List[Dict[str, str]]:
        """
        Extracts text from the PDF, grouping it roughly into paragraphs
        along with the page number where they appear.
        
        Returns:
            A list of dicts: [{"text": str, "page_number": int}]
        """
        paragraphs = []
        
        try:
            with pdfplumber.open(self.file_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text()
                    if text:
                        # Split by double newline to approximate paragraphs
                        blocks = text.split("\n\n")
                        for block in blocks:
                            clean_text = " ".join(block.split("\n")).strip()
                            if len(clean_text) > 20:
                                paragraphs.append({
                                    "text": clean_text,
                                    "page_number": i + 1  # 1-indexed
                                })
        except Exception as e:
            raise RuntimeError(f"Failed to parse PDF {self.file_path}: {str(e)}")
            
        return paragraphs
