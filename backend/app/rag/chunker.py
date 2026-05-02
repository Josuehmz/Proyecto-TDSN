from __future__ import annotations

from dataclasses import dataclass

import tiktoken

from app.config import get_settings


@dataclass(frozen=True)
class TextChunk:
    ordinal: int
    text: str
    token_count: int


_ENCODING_NAME = "cl100k_base"


def _encoder() -> tiktoken.Encoding:
    return tiktoken.get_encoding(_ENCODING_NAME)


def chunk_text(
    text: str,
    *,
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[TextChunk]:
    if not text or not text.strip():
        return []

    settings = get_settings()
    chunk_size = chunk_size or settings.chunk_size_tokens
    overlap = overlap if overlap is not None else settings.chunk_overlap_tokens
    if overlap >= chunk_size:
        raise ValueError("overlap debe ser menor que chunk_size")

    enc = _encoder()
    tokens = enc.encode(text)
    step = chunk_size - overlap

    chunks: list[TextChunk] = []
    for i, start in enumerate(range(0, len(tokens), step)):
        window = tokens[start : start + chunk_size]
        if not window:
            break
        chunk_str = enc.decode(window).strip()
        if not chunk_str:
            continue
        chunks.append(TextChunk(ordinal=i, text=chunk_str, token_count=len(window)))
        if start + chunk_size >= len(tokens):
            break
    return chunks
