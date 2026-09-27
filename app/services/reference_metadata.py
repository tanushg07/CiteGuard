"""Optional bibliography enrichment via OpenAlex and arXiv. Metadata is never verification evidence."""
import html
import re
import time
import xml.etree.ElementTree as ET
from threading import Lock

import httpx

from app.core.schemas import ReferenceMetadata
from backend.config import get_settings

_ARXIV_LOCK = Lock()
_ARXIV_LAST = 0.0

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
        self.deadline = float('inf')
        self.requests = 0

    @staticmethod
    def match_details(paper, reference, doi):
        def normalize(text):
            return re.sub(r'[^a-z0-9]', '', str(text).lower())
        candidate_doi = str((paper.get('externalIds') or {}).get('DOI') or '').lower()
        if doi:
            return {'accepted': candidate_doi == doi.lower(), 'doi_match': candidate_doi == doi.lower(),
                    'method': 'exact_doi', 'title': paper.get('title'), 'doi': candidate_doi}
        title = normalize(paper.get('title') or '')
        title_match = len(title) >= 15 and title in normalize(reference)
        years = re.findall(r'\b(?:19|20)\d{2}\b', reference)
        year_match = bool(years) and str(paper.get('year')) in years
        surnames = [a.get('name', '').split()[-1] for a in paper.get('authors', []) if a.get('name', '').strip()]
        overlap = sum(normalize(name) in normalize(reference) for name in surnames) / max(1,len(surnames))
        return {'accepted': title_match and overlap > 0 and year_match, 'method': 'title_author_year',
                'title': paper.get('title'), 'doi': candidate_doi, 'title_containment': title_match,
                'author_overlap': overlap, 'year_match': year_match,
                'score': .7 * title_match + .2 * overlap + .1 * year_match}

    @staticmethod
    def _matches(paper, reference, doi):
        return BaseEnricher.match_details(paper, reference, doi)['accepted']


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
        if self.requests >= 200 or remaining <= 0:
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
        if self.settings.openalex_api_key.get_secret_value():
            headers['Authorization'] = 'Bearer ' + self.settings.openalex_api_key.get_secret_value()
        
        try:
            with httpx.Client(timeout=min(10.0, remaining), follow_redirects=True, transport=self.transport) as client:
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
                        authors=[author['name'] for author in paper['authors']],
                        pdf_url=paper.get('pdf_url'), urls=paper.get('urls', [])
                    )
                else:
                    fallback.status = 'ambiguous_match' if matches else 'not_found'
        except (httpx.HTTPError, ValueError, TypeError, AttributeError, KeyError):
            fallback.status = 'api_unavailable'
            
        if 'papers' in locals():
            fallback.identification['candidates'] = [self.match_details(p, raw_reference, doi) for p in papers]
        self.cache[raw_reference] = fallback
        return fallback.model_copy(deep=True)

    @staticmethod
    def _normalize(work):
        abstract = ""
        inv_idx = work.get('abstract_inverted_index')
        if inv_idx:
            words = max((max(positions) for positions in inv_idx.values() if positions), default=-1) + 1
            if 0 < words <= 20000:
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

        locations = [work.get('best_oa_location'), primary_loc, *(work.get('locations') or [])]
        urls = [loc['pdf_url'] for loc in locations if isinstance(loc, dict) and loc.get('pdf_url')]
        return {
            'title': work.get('title'),
            'externalIds': {'DOI': doi_str},
            'abstract': html.unescape(abstract.strip()) if abstract else None,
            'venue': source.get('display_name'),
            'year': work.get('publication_year'),
            'authors': [{'name': a.get('author', {}).get('display_name', '')} for a in authorships],
            'pdf_url': urls[0] if urls else (work.get('open_access') or {}).get('oa_url'),
            'urls': list(dict.fromkeys(urls)),
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
        if self.requests >= 200 or remaining <= 0:
            fallback.status = 'budget_exceeded'
            return fallback
        self.requests += 1

        doi_match = DOI.search(raw_reference)
        doi = doi_match[0].rstrip('.,;') if doi_match else None
        
        query = re.sub(r'^\s*(?:\[\d+\]|\d+[.)])\s*', '', raw_reference)[:1000]
        query_words = [w for w in re.findall(r'[a-zA-Z0-9]+', query) if len(w) > 3][:6]
        search_str = " AND ".join(f"all:{w}" for w in query_words)
        params = {'search_query': search_str, 'max_results': 3}
        from app.services.document_parser import ARXIV
        arxiv_match = ARXIV.search(raw_reference)
        if arxiv_match:
            params = {'id_list': arxiv_match[1], 'max_results': 1}
        elif 'arxiv' not in raw_reference.lower() and 'corr' not in raw_reference.lower():
            fallback.status = 'not_applicable'
            return fallback
        
        try:
            with httpx.Client(timeout=min(10.0, remaining), follow_redirects=True, transport=self.transport) as client:
                global _ARXIV_LAST
                with _ARXIV_LOCK:
                    if self.transport is None:
                        time.sleep(max(0, 3 - (time.monotonic() - _ARXIV_LAST)))
                    response = client.get("https://export.arxiv.org/api/query", params=params,
                        headers={'User-Agent': f'CiteGuard/1.0 (mailto:{self.settings.api_contact_email})'})
                    _ARXIV_LAST = time.monotonic()
            
            if response.status_code in (429, 401, 403):
                self.disabled_reason = 'rate_limited' if response.status_code == 429 else 'api_unavailable'
                fallback.status = self.disabled_reason
            else:
                response.raise_for_status()
                root = ET.fromstring(response.text)
                ns = {'atom': 'http://www.w3.org/2005/Atom', 'arxiv': 'http://arxiv.org/schemas/atom'}
                
                works = root.findall('atom:entry', ns)
                papers = [self._normalize(work, ns) for work in works]
                matches = [paper for paper in papers if
                           (re.sub(r'v\d+$', '', paper.get('arxiv_id', '')) == re.sub(r'v\d+$', '', arxiv_match[1]) if arxiv_match else self._matches(paper, raw_reference, doi))]
                
                if len(matches) == 1:
                    paper = matches[0]
                    fallback = ReferenceMetadata(
                        raw_reference=raw_reference, provider='arxiv', status='enriched',
                        title=paper['title'], doi=paper['externalIds'].get('DOI'),
                        abstract=paper['abstract'], venue=paper['venue'], year=paper['year'],
                        authors=[author['name'] for author in paper['authors']],
                        pdf_url=paper.get('pdf_url'), arxiv_id=paper.get('arxiv_id')
                    )
                else:
                    fallback.status = 'ambiguous_match' if matches else 'not_found'
        except (httpx.HTTPError, ValueError, TypeError, AttributeError, KeyError, ET.ParseError):
            fallback.status = 'api_unavailable'
            
        if 'papers' in locals():
            fallback.identification['candidates'] = [self.match_details(p, raw_reference, doi) for p in papers]
        self.cache[raw_reference] = fallback
        return fallback.model_copy(deep=True)

    @staticmethod
    def _normalize(work, ns):
        title = work.find('atom:title', ns)
        abstract = work.find('atom:summary', ns)
        published = work.find('atom:published', ns)
        authors = work.findall('atom:author/atom:name', ns)
        doi_elem = work.find('arxiv:doi', ns)
        
        pdf_url = None
        for link in work.findall('atom:link', ns):
            if link.get('title') == 'pdf':
                pdf_url = link.get('href')
                break
        
        return {
            'title': title.text.replace('\n', ' ').strip() if title is not None else None,
            'arxiv_id': (work.findtext('atom:id', '', ns).split('/abs/')[-1]),
            'externalIds': {'DOI': doi_elem.text if doi_elem is not None else None},
            'abstract': abstract.text.replace('\n', ' ').strip() if abstract is not None else None,
            'venue': 'arXiv',
            'year': int(published.text[:4]) if published is not None and published.text else None,
            'authors': [{'name': a.text} for a in authors if a is not None],
            'pdf_url': pdf_url
        }


class CompositeEnricher:
    """Identify by exact identifiers first and only merge consistent provider records."""
    def __init__(self, transport=None, request=None):
        from backend.modules.citation_extractor import CrossrefEnricher
        self.openalex = OpenAlexEnricher(transport=transport)
        self.crossref = CrossrefEnricher(request=request)
        self.arxiv = ArxivEnricher(transport=transport)
        self.crossref.deadline = float('inf')
        self.crossref.max_requests = 500

    def enrich(self, raw_reference):
        from app.services.document_parser import ARXIV
        if not raw_reference:
            return ReferenceMetadata()
        providers = [self.arxiv, self.crossref, self.openalex] if ARXIV.search(raw_reference) else [self.crossref, self.openalex, self.arxiv]
        selected = None
        attempts = []
        for provider in providers:
            query = raw_reference + ' doi:' + selected.doi if selected and selected.doi and provider is self.openalex else raw_reference
            result = provider.enrich(query)
            result.raw_reference = raw_reference
            attempts.append({'provider': type(provider).__name__, 'status': result.status,
                             'candidates': result.identification.get('candidates', [])})
            if result.status != 'enriched':
                continue
            if selected and selected.doi and result.doi and selected.doi.lower() != result.doi.lower():
                attempts[-1]['status'] = 'identifier_conflict'
                continue
            if selected is None:
                selected = result
            else:
                selected.urls = list(dict.fromkeys([*selected.urls, *result.urls, *([result.pdf_url] if result.pdf_url else [])]))
                selected.pdf_url = selected.pdf_url or result.pdf_url
            if selected.pdf_url:
                break
        final = selected or result
        final.identification = {'status': 'MATCHED' if selected else 'UNRESOLVED', 'providers': attempts,
                                'method': 'exact_arxiv' if final.arxiv_id else 'exact_doi' if DOI.search(raw_reference) else 'title_author_year'}
        return final
