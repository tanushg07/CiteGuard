"""Crossref bibliography enrichment; never supplies verification evidence."""
import html
import re
import time
from urllib.parse import quote

import requests

from app.core.schemas import ReferenceMetadata
from app.services.reference_metadata import DOI, BaseEnricher
from backend.config import get_settings


class CrossrefEnricher:
    def __init__(self, settings=None, request=None):
        self.settings = settings or get_settings()
        self.request = request or requests.get
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
        if not self.settings.crossref_enabled:
            fallback.status = 'disabled'
            return fallback
        if self.disabled_reason:
            fallback.status = self.disabled_reason
            return fallback
        remaining = self.deadline - time.monotonic()
        if self.requests >= 20 or remaining <= 0:
            fallback.status = 'budget_exceeded'
            return fallback
        self.requests += 1
        match = DOI.search(raw_reference)
        doi = match[0].rstrip('.,;') if match else None
        url = 'https://api.crossref.org/works'
        params = {} if doi else {'query.bibliographic': raw_reference[:1000], 'rows': 3}
        if doi:
            url += '/' + quote(doi, safe='')
        try:
            response = self.request(url, params=params,
                headers={'User-Agent': f'CiteGuard/1.0 (mailto:{self.settings.api_contact_email})'},
                timeout=min(self.settings.crossref_timeout_seconds, remaining))
            if response.status_code in (429, 401, 403):
                self.disabled_reason = 'rate_limited' if response.status_code == 429 else 'api_unavailable'
                fallback.status = self.disabled_reason
            else:
                response.raise_for_status()
                payload = response.json()['message']
                works = [payload] if doi else payload.get('items', [])
                papers = [self._normalize(work) for work in works]
                matches = [paper for paper in papers if BaseEnricher._matches(paper, raw_reference, doi)]
                if len(matches) == 1:
                    paper = matches[0]
                    fallback = ReferenceMetadata(raw_reference=raw_reference, provider='crossref',
                        status='enriched', title=paper['title'], doi=paper['externalIds']['DOI'],
                        abstract=paper['abstract'], venue=paper['venue'], year=paper['year'],
                        authors=[author['name'] for author in paper['authors']])
                else:
                    fallback.status = 'ambiguous_match' if matches else 'not_found'
        except (requests.RequestException, ValueError, TypeError, AttributeError, KeyError, IndexError):
            fallback.status = 'api_unavailable'
        self.cache[raw_reference] = fallback
        return fallback.model_copy(deep=True)

    @staticmethod
    def _normalize(work):
        dates = (work.get('published') or work.get('issued') or {}).get('date-parts') or []
        abstract = work.get('abstract')
        return {
            'title': (work.get('title') or [None])[0],
            'externalIds': {'DOI': work.get('DOI')},
            'abstract': html.unescape(re.sub(r'<[^>]+>', '', abstract)) if abstract else None,
            'venue': (work.get('container-title') or [None])[0],
            'year': dates[0][0] if dates and dates[0] else None,
            'authors': [{'name': ' '.join(filter(None, [a.get('given'), a.get('family')])) or a.get('name', '')}
                        for a in (work.get('author') or [])],
        }
