from __future__ import annotations

from functools import lru_cache
from typing import Protocol

from app.config import get_settings
from app.logging_config import get_logger

logger = get_logger(__name__)


class EmbeddingModel(Protocol):
    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class SentenceTransformersEmbeddings:
    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer

        logger.info("embeddings.load", provider="sentence-transformers", model=model_name)
        self._model = SentenceTransformer(model_name)
        self.dim = int(self._model.get_sentence_embedding_dimension())

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self._model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [v.tolist() for v in vectors]


class OpenAIEmbeddings:
    def __init__(self, model_name: str, api_key: str) -> None:
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key)
        self._model_name = model_name
        self.dim = get_settings().embeddings_dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        resp = self._client.embeddings.create(model=self._model_name, input=texts)
        return [d.embedding for d in resp.data]


@lru_cache(maxsize=1)
def get_embeddings_model() -> EmbeddingModel:
    settings = get_settings()
    provider = settings.embeddings_provider
    if provider == "sentence-transformers":
        return SentenceTransformersEmbeddings(settings.embeddings_model)
    if provider == "openai":
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY requerido para embeddings OpenAI")
        return OpenAIEmbeddings(settings.embeddings_model, settings.openai_api_key)
    raise RuntimeError(f"Proveedor de embeddings desconocido: {provider}")
