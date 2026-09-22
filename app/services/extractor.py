import re
from typing import Any

from app.core.schemas import ClaimCitationPair


class Extractor:
    """
    Extracts citation-bearing claims from document paragraphs and pairs them with
    their full paragraph context and citation markers.

    Key fix: deduplicates claims at the sentence level — a sentence is extracted
    at most ONCE even if it contains multiple citation patterns.
    """

    def __init__(self):
        # Bracketed numbers: [1], [1, 2], [1-3], [12, 14, 18]
        self.bracket_pattern = re.compile(r"\[\s*\d+(?:\s*[,–-]\s*\d+)*\s*\]")
        # Author-year: (Smith, 2020), (Smith et al., 2020), (Alon and Yahav, 2021)
        self.author_year_pattern = re.compile(r"\([A-Za-z\s]+(?:et al\.)?,\s*\d{4}[a-z]?\)")
        # Inline: Vaswani et al. (2017)
        self.inline_author_year = re.compile(r"\b[A-Z][a-zA-Z\-]+(?:\s+(?:et al\.|and [A-Z][a-zA-Z]+))?\s*\(\d{4}[a-z]?\)")

    def _split_sentences(self, text: str) -> list[str]:
        """Splits paragraph into sentences using period/question/exclamation boundaries."""
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
            ("al.", "AL_TOKEN"),
        ]
        for orig, rep in replacements:
            protected = protected.replace(orig, rep)

        raw_sentences = re.split(r"(?:(?<=[.!?])\s+(?=[A-Z0-9\"\'(\[])|(?<=[.!?])\n+)", protected)

        sentences = []
        for s in raw_sentences:
            s_clean = s
            for orig, rep in replacements:
                s_clean = s_clean.replace(rep, orig)
            s_clean = s_clean.strip()
            if len(s_clean) > 10:
                sentences.append(s_clean)

        return sentences

    def _has_citation(self, sentence: str) -> bool:
        """Returns True if the sentence contains at least one citation pattern."""
        return bool(
            self.bracket_pattern.search(sentence)
            or self.author_year_pattern.search(sentence)
            or self.inline_author_year.search(sentence)
        )

    def _primary_marker(self, sentence: str) -> str:
        """Returns the first citation marker found in the sentence."""
        for pat in [self.bracket_pattern, self.author_year_pattern, self.inline_author_year]:
            m = pat.search(sentence)
            if m:
                return m.group(0)
        return ""

    def extract(self, paragraphs: list[dict[str, Any]], references=None, enricher=None) -> list[ClaimCitationPair]:
        """
        Scans paragraphs for claims that contain academic citations.
        Each cited SENTENCE is extracted exactly ONCE (deduplicated), paired with
        its primary citation marker and paragraph context.
        """
        pairs: list[ClaimCitationPair] = []
        seen_sentences: set[str] = set()

        for para in paragraphs:
            if para.get("section", "").lower().strip() in {"references", "bibliography", "works cited"}:
                continue

            para_text = para["text"]
            page_number = para.get("page_number", 1)
            section = para.get("section", "Body")

            sentences = self._split_sentences(para_text)

            for sentence in sentences:
                if not self._has_citation(sentence):
                    continue

                markers = []
                for pattern in (self.bracket_pattern, self.author_year_pattern, self.inline_author_year):
                    for match in pattern.finditer(sentence):
                        marker = match.group(0)
                        if marker.startswith('['):
                            for part in marker[1:-1].split(','):
                                nums = re.findall(r'\d+', part)
                                if len(nums) == 2:
                                    markers.extend(f'[{n}]' for n in range(int(nums[0]), min(int(nums[1]), int(nums[0]) + 100) + 1))
                                else:
                                    markers.append(f'[{nums[0]}]')
                        else:
                            markers.append(marker)
                for marker in dict.fromkeys(markers):
                    key = (sentence, marker, page_number)
                    if key in seen_sentences:
                        continue
                    seen_sentences.add(key)
                    pairs.append(ClaimCitationPair(id=f'claim_{len(pairs)+1:04d}', text=sentence,
                        context=para_text, citation_marker=marker, page_number=page_number, section=section))
        from app.services.reference_metadata import reference_for_marker, CompositeEnricher
        enricher = enricher or CompositeEnricher()
        for pair in pairs:
            raw = reference_for_marker(pair.citation_marker, references or [])
            pair.reference_metadata = enricher.enrich(raw)
        return pairs
