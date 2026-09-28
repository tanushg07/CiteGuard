"""Whole-document representation; layout heuristics retain all pages and raw text."""
import os
import re

import pdfplumber

REFERENCE = re.compile(r'^(?:\d+[. ]+)?(?:references|bibliography|works cited|literature cited)\s*$', re.I)
SECTION = re.compile(r'^(?:(?i:section\s+\d+[:.]?.*)|[1-9]\d?(?:\.\d+)*\.?\s+[A-Z][A-Za-z -]{3,80}|(?i:abstract|introduction|related work|methodology|methods|experiments|results|discussion|conclusions?|limitations|acknowledg(?:e)?ments|appendi(?:x|ces)(?:\s+.*)?))$')
ARXIV = re.compile(r'(?:arxiv\s*:\s*|arxiv\.org/(?:abs|pdf)/|\babs/)(\d{4}\.\d{4,5}(?:v\d+)?|[a-z-]+/\d{7}(?:v\d+)?)', re.I)
DOI = re.compile(r'10\.\d{4,9}/[^\s<>"\]]+', re.I)


def reference_record(raw, index, page=None):
    doi = DOI.search(raw)
    arxiv = ARXIV.search(raw)
    urls = re.findall(r'https?://[^\s<>]+', raw)
    year = re.search(r'\b(?:19|20)\d{2}\b', raw)
    number = re.match(r'^\s*(\[\d+\]|\d+[.)])', raw)
    # Bibliographic fields are best-effort; keep unknowns null rather than inventing them.
    body = re.sub(r'^\s*(?:\[\d+\]|\d+[.)])\s*', '', raw)
    parts = re.split(r'(?<=[.])\s+(?=[A-Z])', body)
    title = next((part.strip(' .') for part in parts[1:] if len(part.split()) >= 3 and not part.startswith(('In ', 'http'))), None)
    return {'reference_id': f'REF-{index:03d}', 'citation_key': f'[{re.search(r"\d+", number[0])[0]}]' if number else None,
            'raw_reference': raw, 'page': page, 'title': title, 'authors': [parts[0]] if len(parts) > 1 else [],
            'year': int(year[0]) if year else None, 'doi': doi[0].rstrip('.,;') if doi else None,
            'urls': [u.rstrip('.,;') for u in urls], 'arxiv_id': arxiv[1] if arxiv else None,
            'venue': None, 'publisher': None, 'volume': None, 'issue': None, 'pages': None,
            'parsing_method': 'bibliography_heuristic'}


class DocumentParser:
    def __init__(self, file_path=None):
        self.file_path = file_path
        self.extracted_references = []

    def _structure(self, pages, name, metadata=None):
        from app.services.extractor import Extractor
        paragraphs, references, reference_pages, sections = [], [], [], []
        in_references, section = False, 'Front matter'
        splitter = Extractor()
        for page_number, text in enumerate(pages, 1):
            if in_references and not re.search(r'^\s*(?:\[\d+\]|\d+[.)]\s)', text, re.M) and re.search(r'^Figure \d', text, re.M):
                in_references, section = False, 'Post-reference figures / appendix'
                sections.append({'title': section, 'page': page_number})
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
                    in_references, section = True, 'References'
                    sections.append({'title': section, 'page': page_number})
                elif in_references and re.match(r'^(?:appendi(?:x|ces)\b|[A-Z]\s+[A-Z][a-z])', line, re.I if line.lower().startswith('append') else 0):
                    in_references = False
                    section = line
                    sections.append({'title': section, 'page': page_number})
                elif in_references:
                    if not line or re.fullmatch(r'\d+', line):
                        continue
                    numeric_start = re.match(r'^\[\d+\]|^\d+[.)]\s', line)
                    author_start = re.match(r'^[A-Z][\w-]+,\s+(?:[A-Z]\.|[A-Z][a-z]+)', line)
                    if numeric_start or not references or (author_start and not re.match(r'^\[\d+\]|^\d+[.)]', references[-1])):
                        references.append(line)
                        reference_pages.append(page_number)
                    else:
                        references[-1] += ' ' + line
                elif section.lower() == 'abstract' and re.match(r'^[∗†‡]|^\d+(?:st|nd|rd|th) Conference', line):
                    flush()
                    section = 'Front matter notes'
                    block.append(line)
                elif SECTION.fullmatch(line) and len(line) < 100 and not line.endswith('.'):
                    flush()
                    section = line
                    sections.append({'title': section, 'page': page_number})
                elif not line:
                    flush()
                elif not re.fullmatch(r'\d+', line):
                    block.append(line)
            flush()
        sentences = []
        for para in paragraphs:
            for sentence in splitter._split_sentences(para['text']):
                sentences.append({'text': sentence, 'sentence_index': len(sentences)+1,
                                  'page': para['page_number'], 'section': para['section'], 'paragraph': para['paragraph']})
        self.extracted_references = references
        md = metadata or {}
        first_lines = [line.strip() for line in (pages[0] if pages else '').splitlines() if line.strip()]
        title = md.get('Title') if isinstance(md.get('Title'), str) else None
        title = title or (first_lines[0] if first_lines else name)
        author = md.get('Author') if isinstance(md.get('Author'), str) else None
        front = '\n'.join(first_lines[:30])
        title_pos = next((i for i,line in enumerate(first_lines) if title in line), -1)
        abstract_pos = next((i for i,line in enumerate(first_lines) if line.lower() == 'abstract'), min(len(first_lines), 15))
        author_lines = first_lines[title_pos+1:abstract_pos] if title_pos >= 0 else []
        authors = [name.strip() for line in author_lines if '@' not in line and not re.search(r'university|institute|google|research|department|brain',line,re.I) for name in re.split(r'[∗†‡]|\s{2,}',line) if len(name.strip().split()) >= 2]
        affiliations = [line for line in first_lines[:30] if re.search(r'\b(university|institute|laboratory|research|google|department)\b', line, re.I)]
        return {'document_name': name, 'metadata': {'title': title, 'authors': [author] if author else authors,
                    'affiliations': affiliations, 'abstract': ' '.join(p['text'] for p in paragraphs if p['section'].lower() == 'abstract') or None,
                    'keywords': md.get('Keywords') if isinstance(md.get('Keywords'), str) else None,
                    'publication_information': None, 'front_matter': front, 'method': 'PDF metadata and heading heuristics'},
                'pages': [{'page': i+1, 'text': t} for i,t in enumerate(pages)],
                'sections': sections, 'paragraphs': paragraphs, 'sentences': sentences,
                'reference_records': [reference_record(r,i+1,reference_pages[i]) for i,r in enumerate(references)],
                'references': references, 'total_pages': len(pages)}

    def parse_text(self, raw_text, source_name='Pasted Text'):
        return self._structure([raw_text], source_name)

    def parse(self, file_path=None):
        path = file_path or self.file_path
        if not path:
            raise RuntimeError('No file path provided for DocumentParser.')
        try:
            with pdfplumber.open(path) as pdf:
                pages = [page.extract_text(x_tolerance=1) or '' for page in pdf.pages]
                metadata = dict(pdf.metadata) if isinstance(pdf.metadata, dict) else {}
                first = pdf.pages[0]
                if isinstance(first.chars, list) and first.chars:
                    sizes = [c['size'] for c in first.chars if c.get('upright', True) and c.get('text','').isalpha()]
                    if sizes:
                        largest = max(sizes)
                        title_chars = [c for c in first.chars if c.get('size',0) >= largest-.5]
                        if title_chars:
                            box = (min(c['x0'] for c in title_chars), min(c['top'] for c in title_chars),
                                   max(c['x1'] for c in title_chars), max(c['bottom'] for c in title_chars))
                            title_text = first.crop(box).extract_text(x_tolerance=1)
                            if title_text and len(title_text) > 8:
                                metadata['Title'] = title_text.replace('\n',' ')
            if not any(text.strip() for text in pages):
                raise RuntimeError('Unable to extract text from this PDF. Scanned PDFs require OCR before upload.')
            return self._structure(pages, os.path.basename(path), metadata)
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(f'Failed to parse PDF {path}: {exc}') from exc
