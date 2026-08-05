"""Answer composition: extractive-from-retrieved-content, not a hosted LLM call."""
from __future__ import annotations

from dataclasses import dataclass

from src.rag.loader import DocumentChunk

NOT_FOUND_MESSAGE = (
    "I don't have information about that in the lending-policy documents I have access to."
)


@dataclass
class RagAnswer:
    question: str
    answer: str
    is_answerable: bool
    citations: list[dict]
    retrieved_passages: list[dict]


def compose_answer(
    question: str,
    retrieved: list[tuple[DocumentChunk, float]],
    min_similarity_score: float,
    max_passages_in_answer: int = 2,
) -> RagAnswer:
    retrieved_passages = [
        {"document_name": c.document_name, "section_title": c.section_title, "text": c.text, "score": round(s, 4)}
        for c, s in retrieved
    ]

    relevant = [(c, s) for c, s in retrieved if s >= min_similarity_score]
    if not relevant:
        return RagAnswer(
            question=question, answer=NOT_FOUND_MESSAGE, is_answerable=False,
            citations=[], retrieved_passages=retrieved_passages,
        )

    seen = set()
    selected = []
    for chunk, score in relevant:
        key = (chunk.document_name, chunk.section_title)
        if key in seen:
            continue
        seen.add(key)
        selected.append((chunk, score))
        if len(selected) >= max_passages_in_answer:
            break

    answer_text = "\n\n".join(chunk.text for chunk, _ in selected)
    citations = [
        {"document_name": chunk.document_name, "section_title": chunk.section_title, "similarity_score": round(score, 4)}
        for chunk, score in selected
    ]

    return RagAnswer(
        question=question, answer=answer_text, is_answerable=True,
        citations=citations, retrieved_passages=retrieved_passages,
    )
