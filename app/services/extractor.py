import re
import uuid
from typing import List, Dict
from app.core.schemas import ClaimCitationPair

class Extractor:
    """
    Extracts claims and their associated citation markers from paragraphs.
    """
    def __init__(self):
        # Regex for bracketed numbers like [1], [1, 2], [1-3]
        self.bracket_pattern = re.compile(r'\[(\d+(?:\s*,\s*\d+)*|\d+\s*-\s*\d+)\]')
        # Regex for author-year like (Smith, 2020) or (Smith et al., 2020)
        self.author_year_pattern = re.compile(r'\([A-Za-z\s]+(?:et al\.)?,\s*\d{4}\)')

    def _split_sentences(self, text: str) -> List[str]:
        """
        Splits a paragraph into sentences using a simple regex heuristic.
        """
        # Split by period, question mark, or exclamation mark followed by a space and capital letter.
        # This is a naive but effective heuristic for MVP.
        sentences = re.split(r'(?<=[.!?]) +(?=[A-Z])', text)
        return [s.strip() for s in sentences if s.strip()]

    def extract(self, paragraphs: List[Dict[str, str]]) -> List[ClaimCitationPair]:
        """
        Finds sentences that contain citations and binds them as ClaimCitationPairs.
        """
        pairs = []
        
        for para in paragraphs:
            text = para["text"]
            page_number = para["page_number"]
            
            sentences = self._split_sentences(text)
            
            for sentence in sentences:
                # Find all citation markers in the sentence
                bracket_matches = self.bracket_pattern.findall(sentence)
                author_matches = self.author_year_pattern.findall(sentence)
                
                # We need the full marker text, e.g., "[1]" not just "1"
                all_markers = []
                for match in re.finditer(self.bracket_pattern, sentence):
                    all_markers.append(match.group(0))
                for match in re.finditer(self.author_year_pattern, sentence):
                    all_markers.append(match.group(0))
                
                # For every marker found, create a ClaimCitationPair
                for marker in all_markers:
                    # Clean the citation marker from the claim text to form the bare claim
                    # (Optional: Sometimes we want to keep it to preserve context, but for MVP we leave it in)
                    pair = ClaimCitationPair(
                        id=f"claim_{uuid.uuid4().hex[:8]}",
                        text=sentence,
                        citation_marker=marker,
                        page_number=page_number
                    )
                    pairs.append(pair)
                    
        return pairs
