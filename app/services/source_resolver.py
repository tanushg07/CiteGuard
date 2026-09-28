"""Resolve each bibliography entry once and validate actual source identity."""
import asyncio
import hashlib
import re
from urllib.parse import urlsplit

from app.core.schemas import ReferenceMetadata
from app.services.document_parser import DocumentParser, reference_record
from app.services.downloader import fetch_pdf
from app.services.reference_metadata import CompositeEnricher
from backend.config import get_settings


def compact(text):
    return re.sub(r'[^a-z0-9]', '', text.lower())


def identity_matches(metadata, parsed):
    # Limit identity checks to front matter; a matching citation in its bibliography is not identity.
    front = '\n'.join(p['text'] for p in parsed['pages'][:1])
    if metadata.arxiv_id and metadata.arxiv_id.lower() in front.lower():
        return True, 'Exact arXiv identifier in source front matter.'
    if metadata.doi and metadata.doi.lower() in front.lower():
        return True, 'Exact DOI in source front matter.'
    title = compact(metadata.title or '')
    if len(title) >= 20 and title in compact(front):
        return True, 'Normalized title in source front matter.'
    return False, 'Downloaded content could not be matched to the identified paper.'


class SourceResolver:
    def __init__(self):
        self.config = get_settings()
        self.enricher = CompositeEnricher()
        self.semaphore = asyncio.Semaphore(self.config.source_concurrency)
        self.cache = {}
        self.parsed_cache = {}

    async def resolve(self, raw):
        if raw not in self.cache:
            self.cache[raw] = asyncio.create_task(self._resolve(raw))
        return await self.cache[raw]

    async def _resolve(self, raw):
        source_id = 'SRC-' + hashlib.sha256(raw.encode()).hexdigest()[:12]
        record = {'source_id': source_id, 'raw_reference': raw, 'status': 'SOURCE_UNAVAILABLE',
                  'reason': 'Source could not be reliably identified.', 'attempts': [], 'passages': []}
        if not raw:
            return record, ReferenceMetadata()
        async with self.semaphore:
            metadata = await asyncio.to_thread(self.enricher.enrich, raw)
            record['identification'] = metadata.identification
            record['metadata'] = metadata.model_dump()
            reference = reference_record(raw, 1)
            urls = list(dict.fromkeys([u for u in [metadata.pdf_url, *metadata.urls, *reference['urls']] if u]))
            if metadata.arxiv_id and self.config.arxiv_enabled:
                urls.insert(0, 'https://arxiv.org/pdf/' + metadata.arxiv_id)
            if metadata.status != 'enriched':
                # Exact arXiv identifiers still locate a source when the metadata API is down.
                if reference['arxiv_id'] and self.config.arxiv_enabled:
                    metadata.arxiv_id = reference['arxiv_id']
                    urls.insert(0, 'https://arxiv.org/pdf/' + reference['arxiv_id'])
                elif reference['doi']:
                    metadata.doi = reference['doi']
                    urls.append('https://doi.org/' + reference['doi'])
                elif urls:
                    metadata.title = reference['title']
                else:
                    record['reason'] += ' Provider status: ' + metadata.status
                    return record, metadata
            else:
                record['status'] = 'SOURCE_METADATA_ONLY'
                record['reason'] = 'Source identified, but full text could not be retrieved. Metadata is not evidence.'
                if metadata.doi:
                    urls.append('https://doi.org/' + metadata.doi)
            for url in list(dict.fromkeys(urls))[:5]:
                fetched = await fetch_pdf(url, self.config)
                record['attempts'].append({k:v for k,v in fetched.items() if k != 'path'})
                if not fetched.get('path'):
                    continue
                try:
                    digest = fetched['sha256']
                    if digest not in self.parsed_cache:
                        self.parsed_cache[digest] = await asyncio.wait_for(asyncio.to_thread(DocumentParser().parse, fetched['path']), 60)
                    parsed = self.parsed_cache[digest]
                    valid, reason = identity_matches(metadata, parsed)
                    location = urlsplit(fetched['url'])
                    if metadata.arxiv_id and location.hostname in ('arxiv.org', 'www.arxiv.org', 'export.arxiv.org') and location.path.removesuffix('.pdf') == '/pdf/' + metadata.arxiv_id:
                        valid, reason = True, 'PDF retrieved from the canonical arXiv endpoint for the exact cited identifier.'
                    if valid and metadata.status != 'enriched':
                        metadata.title = parsed['metadata']['title']
                        metadata.authors = parsed['metadata']['authors']
                        metadata.status, metadata.provider = 'enriched', 'source_pdf'
                        metadata.identification = {'status': 'MATCHED', 'method': 'exact_arxiv_url'}
                    if not valid:
                        record['attempts'][-1]['identity_error'] = reason
                        continue
                    record['identification'] = metadata.identification
                    record.update(status='FULL_TEXT', reason=reason, url=fetched['url'], sha256=digest,
                                  total_pages=parsed['total_pages'], metadata=metadata.model_dump())
                    record['passages'] = [{**p, 'name': metadata.title or metadata.doi or metadata.arxiv_id or source_id,
                                           'source_id': source_id, 'source_url': fetched['url']} for p in parsed['paragraphs']]
                    return record, metadata
                except (RuntimeError, ValueError, TimeoutError, OSError):
                    record['attempts'][-1]['parse_error'] = 'Unable to extract source text.'
                    record.update(status='EXTRACTION_FAILED', reason='Source PDF downloaded, but readable text could not be extracted.')
            return record, metadata
