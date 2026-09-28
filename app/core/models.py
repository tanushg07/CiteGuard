"""Lazy, shared model loading. Importing the API never downloads model weights."""
import os
from functools import lru_cache
from threading import Lock

from backend.config import get_settings

_model_lock = Lock()


def _configure_cpu():
    import torch
    torch.set_num_threads(max(1, int(os.getenv('CITEGUARD_TORCH_THREADS', '4'))))


@lru_cache(maxsize=1)
def cross_encoder():
    with _model_lock:
        return _cross_encoder()


@lru_cache(maxsize=1)
def _cross_encoder():
    _configure_cpu()
    from sentence_transformers import CrossEncoder
    return CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2', max_length=512,
                        local_files_only=not get_settings().citeguard_allow_download)


@lru_cache(maxsize=1)
def nli_pipeline():
    with _model_lock:
        return _nli_pipeline()


@lru_cache(maxsize=1)
def _nli_pipeline():
    _configure_cpu()
    from transformers import AutoModelForSequenceClassification, AutoTokenizer, pipeline
    name = 'typeform/distilbert-base-uncased-mnli'
    local = not get_settings().citeguard_allow_download
    tokenizer = AutoTokenizer.from_pretrained(name, local_files_only=local)
    model = AutoModelForSequenceClassification.from_pretrained(name, local_files_only=local)
    return pipeline('text-classification', model=model, tokenizer=tokenizer,
                    top_k=None, truncation=True, max_length=512)
