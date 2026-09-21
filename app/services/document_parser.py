import fitz  # PyMuPDF
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
            doc = fitz.open(self.file_path)
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                blocks = page.get_text("blocks")
                
                # Each block is a tuple, typically: (x0, y0, x1, y1, "text", block_no, block_type)
                # block_type == 0 means text
                for b in blocks:
                    if b[6] == 0:
                        text = b[4].strip()
                        # Simple heuristic: ignore very short blocks that might be headers/footers
                        if len(text) > 20: 
                            # Replace internal newlines with spaces to form a continuous paragraph
                            clean_text = " ".join(text.split("\n")).strip()
                            paragraphs.append({
                                "text": clean_text,
                                "page_number": page_num + 1  # 1-indexed
                            })
            doc.close()
        except Exception as e:
            raise RuntimeError(f"Failed to parse PDF {self.file_path}: {str(e)}")
            
        return paragraphs
