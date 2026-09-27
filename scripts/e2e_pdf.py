"""Upload a real PDF through the actual API and save its complete report."""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient

from app.main import app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('pdf', type=Path)
    parser.add_argument('--output', type=Path, default=Path('data/e2e-report.json'))
    args = parser.parse_args()
    with TestClient(app) as client:
        with args.pdf.open('rb') as document:
            response = client.post('/api/verify', files={'target_file': (args.pdf.name, document, 'application/pdf')})
        response.raise_for_status()
        job = response.json()['job_id']
        print('Uploaded:', args.pdf.name, 'Job:', job, flush=True)
        previous = None
        deadline = time.monotonic() + 1200
        while time.monotonic() < deadline:
            state = client.get('/api/jobs/' + job).json()
            if state['status'] in ('completed', 'error'):
                break
            detail = state.get('data', {}).get('detail', state['status'])
            if detail != previous:
                print(detail, flush=True)
                previous = detail
            time.sleep(1)
        else:
            raise TimeoutError('Analysis exceeded 20 minutes.')
        if state['status'] != 'completed':
            raise RuntimeError(state.get('message'))
        report = client.get('/api/results/' + job).json()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
        print(json.dumps(report['summary'], indent=2), flush=True)
        print('Saved:', args.output, flush=True)


if __name__ == '__main__':
    main()
