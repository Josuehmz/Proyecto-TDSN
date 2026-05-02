from __future__ import annotations

import math
from functools import lru_cache

from app.config import get_settings
from app.logging_config import get_logger
from app.rag.retriever import RetrievedChunk

logger = get_logger(__name__)


class _NoopReranker:
    def rerank(
        self, query: str, chunks: list[RetrievedChunk], top_k: int
    ) -> list[RetrievedChunk]:
        return sorted(chunks, key=lambda c: c.score, reverse=True)[:top_k]


class _CrossEncoderReranker:
    def __init__(self, model_name: str) -> None:
        from sentence_transformers import CrossEncoder

        logger.info("reranker.load", model=model_name)
        self._model = CrossEncoder(model_name)

    def rerank(
        self, query: str, chunks: list[RetrievedChunk], top_k: int
    ) -> list[RetrievedChunk]:
        if not chunks:
            return []
        pairs = [(query, c.text) for c in chunks]
        scores = self._model.predict(pairs, show_progress_bar=False).tolist()
        norm = [1.0 / (1.0 + math.exp(-s)) for s in scores]
        reranked = [
            RetrievedChunk(
                chunk_id=c.chunk_id,
                document_id=c.document_id,
                document_title=c.document_title,
                ordinal=c.ordinal,
                text=c.text,
                score=float(n),
            )
            for c, n in zip(chunks, norm, strict=True)
        ]
        reranked.sort(key=lambda c: c.score, reverse=True)
        return reranked[:top_k]


@lru_cache(maxsize=1)
def get_reranker():
    settings = get_settings()
    if not settings.reranker_enabled:
        return _NoopReranker()
    try:
        return _CrossEncoderReranker(settings.reranker_model)
    except Exception as exc:  # pragma: no cover
        logger.warning("reranker.fallback_noop", error=str(exc))
        return _NoopReranker()
