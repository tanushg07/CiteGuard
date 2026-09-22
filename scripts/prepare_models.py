"""Explicit one-time model download, separate from starting the web server."""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ['CITEGUARD_ALLOW_DOWNLOAD'] = '1'
from app.core.models import cross_encoder, nli_pipeline

if __name__ == '__main__':
    cross_encoder()
    nli_pipeline()
    print('Both models are ready for offline use.')
