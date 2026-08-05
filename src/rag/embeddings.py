"""Local embedding model wrapper (sentence-transformers, no API key required)."""
from __future__ import annotations

import functools

import numpy as np

from src.common.config import load_config


@functools.lru_cache(maxsize=1)
def _get_model():
    from sentence_transformers import SentenceTransformer  # imported lazily: slow to load

    cfg = load_config()
    return SentenceTransformer(cfg["rag"]["embedding_model"])


def embed_texts(texts: list[str]) -> np.ndarray:
    """Returns an (n, dim) float32 array of L2-normalized embeddings (so inner product
    search is equivalent to cosine similarity)."""
    model = _get_model()
    embeddings = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False)
    return embeddings.astype("float32")
