import re
import uuid
from typing import List, Dict, Any
from app.core.schemas import ClaimCitationPair

class Extractor:
    """
    Extracts citation-bearing claims from document paragraphs and pairs them with
    their full paragraph context and citation markers.
    """
    def __init__(self):
        # Bracketed numbers: [1], [1, 2], [1-3], [12, 14, 18]
        self.bracket_pattern = re.compile(r'\[\s*\d+(?:\s*[,-]\s*\d+)*\s*\]')
        # Author-year: (Smith, 2020), (Smith et al., 2020), (Alon and Yahav, 2021)
        self.author_year_pattern = re.compile(r'\([A-Za-z\s]+(?:et al\.)?,\s*\d{4}[a-z]?\)')
        # Secondary author year format: Vaswani et al. (2017)
        self.inline_author_year = re.compile(r'\b[A-Za-z\s]+(?:et al\.)?\s*\(\d{4}[a-z]?\)')

    def _split_sentences(self, text: str) -> List[str]:
        """
        Splits paragraph into sentences using a period/question/exclamation boundary.
        """
        # Protect common academic abbreviations
        protected = text
        replacements = [
            ("et al.", "ET_AL_TOKEN"),
            ("i.e.", "I_E_TOKEN"),
            ("e.g.", "E_G_TOKEN"),
            ("Fig.", "FIG_TOKEN"),
            ("Tab.", "TAB_TOKEN"),
            ("Ref.", "REF_TOKEN"),
            ("vs.", "VS_TOKEN"),
            ("approx.", "APPROX_TOKEN"),
        ]
        for orig, rep in replacements:
            protected = protected.replace(orig, rep)

        # Split on sentence terminals followed by space, or newlines
        raw_sentences = re.split(r'(?:(?<=[.!?])\s+(?=[A-Z0-9"\'\(\[])|\n+)', protected)

        sentences = []
        for s in raw_sentences:
            s_clean = s
            for orig, rep in replacements:
                s_clean = s_clean.replace(rep, orig)
            s_clean = s_clean.strip()
            if len(s_clean) > 10:
                sentences.append(s_clean)

        return sentences

    def extract(self, paragraphs: List[Dict[str, Any]]) -> List[ClaimCitationPair]:
        """
        Scans paragraphs for claims that contain academic citations.
        Returns a list of ClaimCitationPair objects with surrounding context.
        """
        pairs: List[ClaimCitationPair] = []

        for para in paragraphs:
            if para.get("section") == "References":
                continue

            para_text = para["text"]
            page_number = para.get("page_number", 1)
            section = para.get("section", "Body")

            sentences = self._split_sentences(para_text)

            for sentence in sentences:
                all_markers = []
                for match in self.bracket_pattern.finditer(sentence):
                    all_markers.append(match.group(0))
                for match in self.author_year_pattern.finditer(sentence):
                    all_markers.append(match.group(0))
                for match in self.inline_author_year.finditer(sentence):
                    all_markers.append(match.group(0))

                for marker in all_markers:
                    claim_id = f"claim_{uuid.uuid4().hex[:8]}"
                    pair = ClaimCitationPair(
                        id=claim_id,
                        text=sentence,
                        context=para_text,
                        citation_marker=marker,
                        page_number=page_number,
                        section=section
                    )
                    pairs.append(pair)

        return pairs
