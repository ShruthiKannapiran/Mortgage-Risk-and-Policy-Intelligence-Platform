"""Loads and cleans the lending-policy documents, then splits them into chunks.

Chunking follows the documents' own Markdown section structure (`## Section N: ...`)
rather than a blind fixed-size split, so each chunk is a semantically meaningful unit
(one policy section) — this is what "meaningful chunks" means here. A section is only
further split on a fixed-size/overlap basis if it exceeds `chunk_size_chars`, which none
of the current 7 documents do.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from src.common.config import get_paths, load_config


@dataclass
class DocumentChunk:
    chunk_id: str
    document_name: str
    section_title: str
    text: str


def _clean_text(text: str) -> str:
    text = re.sub(r"\r\n", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _split_into_sections(document_text: str) -> list[tuple[str, str]]:
    """Returns [(section_title, section_body), ...], including a leading 'Overview'
    section (everything before the first '## ' heading, if any)."""
    lines = document_text.split("\n")
    sections: list[tuple[str, list[str]]] = []
    current_title = "Overview"
    current_body: list[str] = []

    for line in lines:
        if line.startswith("## "):
            if current_body:
                sections.append((current_title, current_body))
            current_title = line[3:].strip()
            current_body = []
        elif line.startswith("# "):
            continue  # document title, not a section
        else:
            current_body.append(line)
    if current_body:
        sections.append((current_title, current_body))

    return [(title, "\n".join(body).strip()) for title, body in sections if "\n".join(body).strip()]


def _chunk_long_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    if len(text) <= chunk_size:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = end - overlap
    return chunks


def load_and_chunk_documents() -> list[DocumentChunk]:
    cfg = load_config()
    paths = get_paths()
    policy_dir: Path = paths["policy_documents_dir"]
    chunk_size = cfg["rag"]["chunk_size_chars"]
    overlap = cfg["rag"]["chunk_overlap_chars"]

    chunks: list[DocumentChunk] = []
    for path in sorted(policy_dir.glob("*.md")):
        raw_text = _clean_text(path.read_text(encoding="utf-8"))
        title_match = re.search(r"^# (.+)$", raw_text, flags=re.MULTILINE)
        doc_title = title_match.group(1).strip() if title_match else path.stem

        for section_title, section_body in _split_into_sections(raw_text):
            sub_chunks = _chunk_long_text(section_body, chunk_size, overlap)
            for i, sub_text in enumerate(sub_chunks):
                suffix = f" (part {i + 1})" if len(sub_chunks) > 1 else ""
                chunks.append(
                    DocumentChunk(
                        chunk_id=f"{path.stem}::{section_title}{suffix}",
                        document_name=doc_title,
                        section_title=f"{section_title}{suffix}",
                        text=f"{doc_title} — {section_title}\n{sub_text}",
                    )
                )
    return chunks
