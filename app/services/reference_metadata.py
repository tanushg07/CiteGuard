"""Optional bibliography enrichment via OpenAlex and arXiv. Metadata is never verification evidence."""
import html
import re
import time
from urllib.parse import quote
import xml.etree.ElementTree as ET

import httpx

from app.core.schemas import ReferenceMetadata
from backend.config import get_settings

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


class BaseEnricher:
    """Base class for all enrichers providing caching and matching logic."""
    def __init__(self, transport=None):
        self.settings = get_settings()
        self.transport = transport
        self.cache = {}
        self.disabled_reason = None
        self.deadline = time.monotonic() + 20
        self.requests = 0

    @staticmethod
    def _matches(paper, reference, doi):
        if doi:
            return str((paper.get('externalIds') or {}).get('DOI', '')).lower() == doi.lower()
        def tokens(text):
            return set(re.findall(r'[a-z0-9]+', text.lower())) - {'the', 'a', 'an', 'of', 'in', 'and', 'for', 'on'}
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


class OpenAlexEnricher(BaseEnricher):
    """Enriches references using OpenAlex API."""
    def enrich(self, raw_reference):
        fallback = ReferenceMetadata(raw_reference=raw_reference)
        if not raw_reference:
            return fallback
        if raw_reference in self.cache:
            return self.cache[raw_reference].model_copy(deep=True)
        if not self.settings.openalex_enabled:
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

        doi_match = DOI.search(raw_reference)
        doi = doi_match[0].rstrip('.,;') if doi_match else None
        
        base_url = "https://api.openalex.org/works"
        if doi:
            url = f"{base_url}/https://doi.org/{doi}"
            params = {}
        else:
            query = re.sub(r'^\s*(?:\[\d+\]|\d+[.)])\s*', '', raw_reference)[:1000]
            url = base_url
            params = {'search': query, 'per-page': 3}

        headers = {'User-Agent': f'CiteGuard/1.0 (mailto:{self.settings.api_contact_email})'}
        
        try:
            with httpx.Client(timeout=min(3.0, remaining), transport=self.transport) as client:
                response = client.get(url, params=params, headers=headers)
            
            if response.status_code in (429, 401, 403):
                self.disabled_reason = 'rate_limited' if response.status_code == 429 else 'api_unavailable'
                fallback.status = self.disabled_reason
            else:
                response.raise_for_status()
                payload = response.json()
                works = [payload] if doi else payload.get('results', [])
                papers = [self._normalize(work) for work in works]
                matches = [paper for paper in papers if self._matches(paper, raw_reference, doi)]
                
                if len(matches) == 1:
                    paper = matches[0]
                    fallback = ReferenceMetadata(
                        raw_reference=raw_reference, provider='openalex', status='enriched',
                        title=paper['title'], doi=paper['externalIds'].get('DOI'),
                        abstract=paper['abstract'], venue=paper['venue'], year=paper['year'],
                        authors=[author['name'] for author in paper['authors']]
                    )
                else:
                    fallback.status = 'ambiguous_match' if matches else 'not_found'
        except (httpx.HTTPError, ValueError, TypeError, AttributeError, KeyError):
            fallback.status = 'api_unavailable'
            
        self.cache[raw_reference] = fallback
        return fallback.model_copy(deep=True)

    @staticmethod
    def _normalize(work):
        abstract = ""
        inv_idx = work.get('abstract_inverted_index')
        if inv_idx:
            words = max((max(positions) for positions in inv_idx.values() if positions), default=-1) + 1
            if words > 0:
                abstract_arr = [""] * words
                for word, positions in inv_idx.items():
                    for pos in positions:
                        abstract_arr[pos] = word
                abstract = " ".join(abstract_arr)

        authorships = work.get('authorships') or []
        primary_loc = work.get('primary_location') or {}
        source = primary_loc.get('source') or {}
        doi_str = work.get('doi')
        if doi_str and doi_str.startswith('https://doi.org/'):
            doi_str = doi_str[16:]

        return {
            'title': work.get('title'),
            'externalIds': {'DOI': doi_str},
            'abstract': html.unescape(abstract.strip()) if abstract else None,
            'venue': source.get('display_name'),
            'year': work.get('publication_year'),
            'authors': [{'name': a.get('author', {}).get('display_name', '')} for a in authorships]
        }


class ArxivEnricher(BaseEnricher):
    """Enriches references using arXiv API."""
    def enrich(self, raw_reference):
        fallback = ReferenceMetadata(raw_reference=raw_reference)
        if not raw_reference:
            return fallback
        if raw_reference in self.cache:
            return self.cache[raw_reference].model_copy(deep=True)
        if not self.settings.arxiv_enabled:
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

        doi_match = DOI.search(raw_reference)
        doi = doi_match[0].rstrip('.,;') if doi_match else None
        
        query = re.sub(r'^\s*(?:\[\d+\]|\d+[.)])\s*', '', raw_reference)[:1000]
        params = {'search_query': f'all:"{query}"', 'max_results': 3}

        headers = {'User-Agent': f'CiteGuard/1.0 (mailto:{self.settings.api_contact_email})'}
        
        try:
            with httpx.Client(timeout=min(3.0, remaining), transport=self.transport) as client:
                response = client.get("http://export.arxiv.org/api/query", params=params, headers=headers)
            
            if response.status_code in (429, 401, 403):
                self.disabled_reason = 'rate_limited' if response.status_code == 429 else 'api_unavailable'
                fallback.status = self.disabled_reason
            else:
                response.raise_for_status()
                root = ET.fromstring(response.text)
                ns = {'atom': 'http://www.w3.org/2005/Atom', 'arxiv': 'http://arxiv.org/schemas/atom'}
                
                works = root.findall('atom:entry', ns)
                papers = [self._normalize(work, ns) for work in works]
                matches = [paper for paper in papers if self._matches(paper, raw_reference, doi)]
                
                if len(matches) == 1:
                    paper = matches[0]
                    fallback = ReferenceMetadata(
                        raw_reference=raw_reference, provider='arxiv', status='enriched',
                        title=paper['title'], doi=paper['externalIds'].get('DOI'),
                        abstract=paper['abstract'], venue=paper['venue'], year=paper['year'],
                        authors=[author['name'] for author in paper['authors']]
                    )
                else:
                    fallback.status = 'ambiguous_match' if matches else 'not_found'
        except (httpx.HTTPError, ValueError, TypeError, AttributeError, KeyError, ET.ParseError):
            fallback.status = 'api_unavailable'
            
        self.cache[raw_reference] = fallback
        return fallback.model_copy(deep=True)

    @staticmethod
    def _normalize(work, ns):
        title = work.find('atom:title', ns)
        abstract = work.find('atom:summary', ns)
        published = work.find('atom:published', ns)
        authors = work.findall('atom:author/atom:name', ns)
        doi_elem = work.find('arxiv:doi', ns)
        
        return {
            'title': title.text.replace('\n', ' ').strip() if title is not None else None,
            'externalIds': {'DOI': doi_elem.text if doi_elem is not None else None},
            'abstract': abstract.text.replace('\n', ' ').strip() if abstract is not None else None,
            'venue': 'arXiv',
            'year': int(published.text[:4]) if published is not None and published.text else None,
            'authors': [{'name': a.text} for a in authors if a is not None]
        }


class CompositeEnricher:
    """Cascades through OpenAlex, Crossref, and arXiv to enrich a reference."""
    def __init__(self, transport=None, request=None):
        from backend.modules.citation_extractor import CrossrefEnricher
        self.openalex = OpenAlexEnricher(transport=transport)
        self.crossref = CrossrefEnricher(request=request)
        self.arxiv = ArxivEnricher(transport=transport)
    
    def enrich(self, raw_reference):
        # OpenAlex
        res = self.openalex.enrich(raw_reference)
        if res.status == 'enriched':
            return res
            
        # Crossref
        res_crossref = self.crossref.enrich(raw_reference)
        if res_crossref.status == 'enriched':
            return res_crossref
            
        # arXiv
        res_arxiv = self.arxiv.enrich(raw_reference)
        if res_arxiv.status == 'enriched':
            return res_arxiv
            
        # If none succeeded, return the OpenAlex failure response (since it's the primary one)
        return res
