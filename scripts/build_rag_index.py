#!/usr/bin/env python3
"""Builds the FAISS vector index over the lending-policy documents.

Run once (and any time the documents in data/policy_documents/ change):
    python scripts/build_rag_index.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.common.logging_setup import get_logger
from src.rag.embeddings import embed_texts
from src.rag.loader import load_and_chunk_documents
from src.rag.vector_store import build_index

logger = get_logger("build_rag_index")


def main() -> None:
    chunks = load_and_chunk_documents()
    logger.info("Loaded %s chunk(s) from policy documents", len(chunks))

    embeddings = embed_texts([c.text for c in chunks])
    logger.info("Computed embeddings: shape=%s", embeddings.shape)

    build_index(chunks, embeddings)
    logger.info("Vector index built and persisted to data/vector_store/")


if __name__ == "__main__":
    main()
