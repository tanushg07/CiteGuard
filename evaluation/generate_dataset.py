"""Create uploadable PDF demo fixtures from the checked-in synthetic dataset.

This does not overwrite gold labels or claim that fixtures are published papers.
"""
import json
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def write_pdf(path, text):
    lines = [line for paragraph in text.splitlines() for line in (textwrap.wrap(paragraph, 85) or [''])]
    if len(lines) > 48:
        raise ValueError('Demo fixture exceeds one page')
    escape = lambda value: value.replace('\\', '\\\\').replace('(', r'\(').replace(')', r'\)')
    stream = ('BT /F1 11 Tf 40 750 Td 14 TL\n' + '\n'.join(f'({escape(line)}) Tj T*' for line in lines) + '\nET').encode('ascii')
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>', b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>', b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>', b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>', b'<< /Length '+str(len(stream)).encode()+b' >>\nstream\n'+stream+b'\nendstream']
    data = b'%PDF-1.4\n'
    offsets = []
    for i, obj in enumerate(objects, 1):
        offsets.append(len(data))
        data += f'{i} 0 obj\n'.encode()+obj+b'\nendobj\n'
    xref = len(data)
    data += b'xref\n0 6\n0000000000 65535 f \n'
    data += b''.join(f'{offset:010d} 00000 n \n'.encode() for offset in offsets)
    data += f'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF'.encode()
    path.write_bytes(data)


if __name__ == '__main__':
    dataset = json.loads((ROOT / 'evaluation/golden_standard.json').read_text(encoding='utf-8'))
    output = ROOT / 'data/demo'
    output.mkdir(parents=True, exist_ok=True)
    write_pdf(output / 'manuscript.pdf', '\n\n'.join(item['target_text'] for item in dataset))
    for item in dataset:
        source = item['sources'][0]
        write_pdf(output / f"{source['markers'][0]} {source['name']}.pdf", source['text'])
    print(f'Demo manuscript and {len(dataset)} source PDFs written to {output}')
