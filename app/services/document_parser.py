"""PDF/text extraction with page provenance and bibliography separation."""
import os
import re
from typing import Optional
import pdfplumber

REFERENCE = re.compile(r'^(?:\d+[. ]+)?(?:references|bibliography|works cited|literature cited)\s*$', re.I)
SECTION = re.compile(r'^(?:section\s+\d+[:.]?.*|\d+(?:\.\d+)*\.?\s+[A-Z].*|abstract|introduction|methods|results|discussion|conclusion)$', re.I)

class DocumentParser:
    def __init__(self, file_path: Optional[str] = None):
        self.file_path = file_path
        self.extracted_references = []

    def _structure(self, pages, name):
        paragraphs, references = [], []
        in_references = False
        section = 'Body'
        for page_number, text in enumerate(pages, 1):
            block = []
            def flush():
                clean = ' '.join(' '.join(block).split())
                block.clear()
                if len(clean) > 15:
                    paragraphs.append({'text': clean, 'page_number': page_number,
                                       'paragraph': len(paragraphs) + 1, 'section': section})
            for line in text.splitlines():
                line = line.strip()
                if REFERENCE.fullmatch(line):
                    flush()
                    in_references = True
                elif in_references:
                    if not line:
                        continue
                    if re.match(r'^\[\d+\]|^\d+\.', line) or not references:
                        references.append(line)
                    elif references and (re.match(r'^\[\d+\]|^\d+\.', references[-1]) or not references[-1].endswith('.')):
                        references[-1] += ' ' + line
                    else:
                        references.append(line)
                elif SECTION.fullmatch(line) and len(line) < 80 and not line.endswith('.'):
                    flush()
                    section = line
                elif not line:
                    flush()
                else:
                    block.append(line)
            flush()
        self.extracted_references = references
        return {'document_name': name, 'paragraphs': paragraphs,
                'references': references, 'total_pages': len(pages)}

    def parse_text(self, raw_text, source_name='Pasted Text'):
        return self._structure([raw_text], source_name)

    def parse(self, file_path=None):
        path = file_path or self.file_path
        if not path:
            raise RuntimeError('No file path provided for DocumentParser.')
        try:
            with pdfplumber.open(path) as pdf:
                pages = [page.extract_text() or '' for page in pdf.pages]
            if not any(text.strip() for text in pages):
                raise RuntimeError('No extractable text found. Scanned PDFs require OCR before upload.')
            return self._structure(pages, os.path.basename(path))
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(f'Failed to parse PDF {path}: {exc}') from exc
