"""FAISS-backed vector store for the policy-document chunks.

Persisted to disk (data/vector_store/) so the index only needs to be built once (via
scripts/build_rag_index.py) and can be reloaded quickly afterward.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import faiss
import numpy as np

from src.common.config import get_paths
from src.rag.loader import DocumentChunk

INDEX_FILENAME = "policy_docs.faiss"
METADATA_FILENAME = "policy_docs_metadata.json"


def build_index(chunks: list[DocumentChunk], embeddings: np.ndarray) -> None:
    paths = get_paths()
    vector_store_dir: Path = paths["vector_store_dir"]
    vector_store_dir.mkdir(parents=True, exist_ok=True)

    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)  # inner product over normalized vectors == cosine similarity
    index.add(embeddings)
    faiss.write_index(index, str(vector_store_dir / INDEX_FILENAME))

    metadata = [asdict(chunk) for chunk in chunks]
    with open(vector_store_dir / METADATA_FILENAME, "w", encoding="utf-8") as fh:
        json.dump(metadata, fh, indent=2)


def load_index() -> tuple[faiss.Index, list[DocumentChunk]]:
    paths = get_paths()
    vector_store_dir: Path = paths["vector_store_dir"]
    index_path = vector_store_dir / INDEX_FILENAME
    metadata_path = vector_store_dir / METADATA_FILENAME

    if not index_path.exists() or not metadata_path.exists():
        raise FileNotFoundError(
            "RAG vector store not found. Run `python scripts/build_rag_index.py` first."
        )

    index = faiss.read_index(str(index_path))
    with open(metadata_path, "r", encoding="utf-8") as fh:
        raw_metadata = json.load(fh)
    chunks = [DocumentChunk(**item) for item in raw_metadata]
    return index, chunks


def search(index: faiss.Index, chunks: list[DocumentChunk], query_embedding: np.ndarray, top_k: int) -> list[tuple[DocumentChunk, float]]:
    scores, indices = index.search(query_embedding.reshape(1, -1), top_k)
    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx == -1:
            continue
        results.append((chunks[idx], float(score)))
    return results
