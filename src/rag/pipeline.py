"""Top-level RAG entry point used by the API, dashboard, and evaluation script."""
from __future__ import annotations

import functools

from src.common.config import load_config
from src.common.logging_setup import get_logger
from src.rag.embeddings import embed_texts
from src.rag.generation import RagAnswer, compose_answer
from src.rag.vector_store import load_index, search

logger = get_logger("rag.pipeline")


@functools.lru_cache(maxsize=1)
def _get_index():
    return load_index()


def answer_question(question: str) -> RagAnswer:
    cfg = load_config()["rag"]
    index, chunks = _get_index()
    query_embedding = embed_texts([question])[0]
    retrieved = search(index, chunks, query_embedding, top_k=cfg["top_k"])
    logger.info(
        "RAG query=%r top_score=%.4f",
        question, retrieved[0][1] if retrieved else float("nan"),
    )
    return compose_answer(question, retrieved, min_similarity_score=cfg["min_similarity_score"])
