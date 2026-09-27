"""Bounded public-document fetcher with redirect validation and content-addressed cache."""
import asyncio
import hashlib
import ipaddress
import json
import socket
import time
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

import httpx

from backend.config import ROOT, get_settings

CACHE = ROOT / 'data' / 'sources'


async def validate_url(url):
    parsed = urlsplit(url)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Only public HTTP(S) source URLs are allowed.')
    if parsed.port not in (None, 80, 443):
        raise ValueError('Nonstandard source port blocked.')
    addresses = await asyncio.to_thread(socket.getaddrinfo, parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(address[4][0]).is_global for address in addresses):
        raise ValueError('Private or reserved source address blocked.')


async def fetch_pdf(url, settings=None):
    config = settings or get_settings()
    try:
        return await asyncio.wait_for(_fetch(url, config), timeout=45)
    except (httpx.HTTPError, ValueError, OSError, TimeoutError):
        return {'status': 'SOURCE_UNAVAILABLE', 'reason': 'Full-text request failed, timed out, exceeded limits, or used a blocked address.', 'url': url}


async def _fetch(url, config):
    original = url
    key = hashlib.sha256(url.encode()).hexdigest()
    CACHE.mkdir(parents=True, exist_ok=True)
    manifest = CACHE / (key + '.json')
    if manifest.exists():
        record = json.loads(manifest.read_text(encoding='utf-8'))
        path = CACHE / (record['sha256'] + '.pdf')
        if path.exists() and time.time() - record['fetched_at'] < 7 * 86400:
            if hashlib.sha256(path.read_bytes()).hexdigest() == record['sha256']:
                return {**record, 'path': str(path), 'cached': True}
    headers = {'User-Agent': f'CiteGuard/1.0 (mailto:{config.api_contact_email})'}
    async with httpx.AsyncClient(timeout=config.source_timeout_seconds, follow_redirects=False, trust_env=False) as client:
        for _ in range(6):
            await validate_url(url)
            async with client.stream('GET', url, headers=headers) as response:
                if response.status_code in (301, 302, 303, 307, 308):
                    url = urljoin(url, response.headers.get('location', ''))
                    continue
                if response.status_code != 200:
                    return {'status': 'SOURCE_UNAVAILABLE', 'reason': f'Full-text server returned HTTP {response.status_code}.', 'url': url}
                if int(response.headers.get('content-length', '0')) > config.source_max_bytes:
                    raise ValueError('Source exceeds size limit.')
                chunks, size = [], 0
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > config.source_max_bytes:
                        raise ValueError('Source exceeds size limit.')
                    chunks.append(chunk)
                content = b''.join(chunks)
                if not content.startswith(b'%PDF-'):
                    # Follow only publisher-declared PDF links, not arbitrary page links.
                    html = content[:1_000_000].decode('utf-8', errors='replace')
                    class PDFLinks(HTMLParser):
                        def __init__(self):
                            super().__init__()
                            self.links = []
                        def handle_starttag(self, tag, attrs):
                            attr = dict(attrs)
                            if tag == 'meta' and attr.get('name', attr.get('property')) == 'citation_pdf_url' and attr.get('content'):
                                self.links.append(attr['content'])
                    parser = PDFLinks()
                    parser.feed(html)
                    links = parser.links
                    if links:
                        url = urljoin(url, links[0])
                        continue
                    return {'status': 'SOURCE_UNAVAILABLE', 'reason': 'Accessible location did not provide a PDF or publisher PDF link.', 'url': url}
                digest = hashlib.sha256(content).hexdigest()
                path = CACHE / (digest + '.pdf')
                await asyncio.to_thread(path.write_bytes, content)
                record = {'status': 'FETCHED', 'url': url, 'requested_url': original, 'sha256': digest, 'bytes': size, 'fetched_at': time.time()}
                await asyncio.to_thread(manifest.write_text, json.dumps(record), encoding='utf-8')
                return {**record, 'path': str(path), 'cached': False}
    return {'status': 'SOURCE_UNAVAILABLE', 'reason': 'Source redirect limit exceeded.', 'url': url}


async def download_source_pdf(url: str, title: str = '') -> str | None:
    """Compatibility helper; cached PDFs belong to the cache, not to the caller."""
    return (await fetch_pdf(url)).get('path')
