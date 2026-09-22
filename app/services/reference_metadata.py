"""Optional bibliography enrichment. Metadata is never verification evidence."""
import os
import re
import time
from urllib.parse import quote

import httpx
from app.core.schemas import ReferenceMetadata

BASE_URL = 'https://api.semanticscholar.org/graph/v1'
FIELDS = 'title,externalIds,abstract,venue,authors,year'
DOI = re.compile(r'10\.\d{4,9}/[^\s<>"\]]+', re.I)


def reference_for_marker(marker, references):
    """Match explicit numbering or an unambiguous author/year entry, never position."""
    number = re.fullmatch(r'\[(\d+)\]', marker)
    if number:
        pattern = re.compile(r'^\s*(?:\[\s*' + number[1] + r'\s*\]|' + number[1] + r'[.)])\s*')
        matches = [entry for entry in references if pattern.match(entry)]
    else:
        year = re.search(r'\b(?:19|20)\d{2}[a-z]?\b', marker)
        author = re.search(r'[A-Za-z][A-Za-z-]+', marker)
        matches = [entry for entry in references if year and author
                   and re.search(r'\b' + re.escape(year[0]) + r'\b', entry)
                   and re.search(r'\b' + re.escape(author[0]) + r'\b', entry, re.I)]
    return matches[0] if len(matches) == 1 else ''


class ReferenceEnricher:
    """One instance per extraction: bounded latency, duplicate cache and 429 circuit breaker."""
    def __init__(self, api_key=None, transport=None):
        self.api_key = (os.getenv('SEMANTIC_SCHOLAR_API_KEY', '') if api_key is None else api_key).strip()
        self.transport = transport
        self.cache = {}
        self.disabled_reason = None
        self.deadline = time.monotonic() + 20
        self.requests = 0

    def enrich(self, raw_reference):
        fallback = ReferenceMetadata(raw_reference=raw_reference)
        if not raw_reference:
            return fallback
        if raw_reference in self.cache:
            return self.cache[raw_reference].model_copy(deep=True)
        if not self.api_key:
            fallback.status = 'missing_key'
            return fallback
        if self.disabled_reason:
            fallback.status = self.disabled_reason
            return fallback
        remaining = self.deadline - time.monotonic()
        if self.requests >= 20 or remaining <= 0:
            fallback.status = 'budget_exceeded'
            return fallback
        self.requests += 1
        doi_match = DOI.search(raw_reference)
        doi = doi_match[0].rstrip('.,;') if doi_match else None
        path = '/paper/' + quote('DOI:' + doi, safe='') if doi else '/paper/search'
        params = {'fields': FIELDS}
        if not doi:
            params.update(query=re.sub(r'^\s*(?:\[\d+\]|\d+[.)])\s*', '', raw_reference)[:1000], limit=3)
        try:
            with httpx.Client(timeout=min(3.0, remaining), transport=self.transport) as client:
                response = client.get(BASE_URL + path, params=params,
                                      headers={'x-api-key': self.api_key, 'User-Agent': 'CiteGuard/1.0'})
            if response.status_code in (429, 401, 403):
                self.disabled_reason = 'rate_limited' if response.status_code == 429 else 'authentication_failed'
                fallback.status = self.disabled_reason
            else:
                response.raise_for_status()
                payload = response.json()
                papers = [payload] if doi else payload.get('data', [])
                matches = [paper for paper in papers if self._matches(paper, raw_reference, doi)]
                if len(matches) == 1:
                    paper = matches[0]
                    fallback = ReferenceMetadata(raw_reference=raw_reference, provider='semantic_scholar',
                        status='enriched', title=paper.get('title'),
                        doi=(paper.get('externalIds') or {}).get('DOI'), abstract=paper.get('abstract'),
                        venue=paper.get('venue') or None, year=paper.get('year'),
                        authors=[author['name'] for author in paper.get('authors', []) if author.get('name')])
                else:
                    fallback.status = 'ambiguous_match' if matches else 'not_found'
        except (httpx.HTTPError, ValueError, TypeError, AttributeError, KeyError):
            # Do not log exceptions containing request headers/keys or document contents.
            fallback.status = 'api_unavailable'
        self.cache[raw_reference] = fallback
        return fallback.model_copy(deep=True)

    @staticmethod
    def _matches(paper, reference, doi):
        if doi:
            return str((paper.get('externalIds') or {}).get('DOI', '')).lower() == doi.lower()
        tokens = lambda text: set(re.findall(r'[a-z0-9]+', text.lower())) - {'the', 'a', 'an', 'of', 'in', 'and', 'for', 'on'}
        title_words = tokens(paper.get('title') or '')
        # Relevance order alone is not a reliable bibliographic identity match.
        if len(title_words) < 3 or not title_words.issubset(tokens(reference)):
            return False
        years = re.findall(r'\b(?:19|20)\d{2}\b', reference)
        if years and str(paper.get('year')) not in years:
            return False
        authors = paper.get('authors') or []
        surnames = [author.get('name', '').split()[-1] for author in authors if author.get('name', '').strip()]
        return any(tokens(surname) and tokens(surname).issubset(tokens(reference)) for surname in surnames)
