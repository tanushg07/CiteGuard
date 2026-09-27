import httpx
import tempfile
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

async def download_source_pdf(url: str, title: str) -> str | None:
    """
    Downloads a PDF from a URL and saves it to a temporary file.
    Returns the path to the temporary file, or None if failed.
    """
    if not url:
        return None
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            headers = {
                'User-Agent': 'CiteGuard/2.0 (Academic Verification System)'
            }
            # For arXiv, ensure we use pdf extension
            if 'arxiv.org' in url and not url.endswith('.pdf'):
                url = url.replace('/abs/', '/pdf/')
                if not url.endswith('.pdf'):
                    url += '.pdf'
                    
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                # Basic check if it's a PDF
                content_type = response.headers.get('content-type', '')
                if 'pdf' not in content_type.lower() and not response.content.startswith(b'%PDF-'):
                    logger.warning(f"URL {url} did not return a PDF.")
                    return None
                    
                safe_title = "".join(c for c in title if c.isalnum() or c in " ._-").strip()[:50] or "source"
                suffix = f"_{safe_title}.pdf"
                
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp:
                    temp.write(response.content)
                    return temp.name
            else:
                logger.warning(f"Failed to download {url}: Status {response.status_code}")
    except Exception as e:
        logger.error(f"Error downloading {url}: {e}")
    return None
