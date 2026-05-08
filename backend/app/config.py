from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BeforeValidator, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Siempre junto al paquete `app` (…/backend/.env), más la raíz del repo si existe (…/.env).
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_ENV_FILE_CANDIDATES = (_BACKEND_DIR / ".env", _BACKEND_DIR.parent / ".env")
_RESOLVED_ENV_FILES = tuple(str(p) for p in _ENV_FILE_CANDIDATES if p.is_file())


def _coerce_deprecated_llm_provider(v: object) -> object:
    if v is None:
        return v
    s = str(v).strip().lower()
    # Valores antiguos (README/.env locales) que antes usaban modo mock determinista en app.
    if s == "mock":
        return "groq"
    return v


CoercedLiteralLlmProvider = Annotated[
    Literal["openai", "groq"],
    BeforeValidator(_coerce_deprecated_llm_provider),
]


class Settings(BaseSettings):
    app_env: Literal["dev", "staging", "prod"] = "dev"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_log_level: str = "INFO"

    database_url: str = Field(
        default="postgresql+psycopg://rag_admin:change_me_strong_password@postgres:5432/rag_platform"
    )

    jwt_secret: str = "replace_me_with_a_long_random_string_min_32_chars"
    jwt_alg: str = "HS256"
    jwt_expire_min: int = 60

    llm_provider: CoercedLiteralLlmProvider = "groq"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"

    groq_api_key: str | None = None
    groq_model: str = "llama-3.3-70b-versatile"
    groq_base_url: str = "https://api.groq.com/openai/v1"

    embeddings_provider: Literal["sentence-transformers", "openai"] = "sentence-transformers"
    embeddings_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embeddings_dim: int = 384

    reranker_enabled: bool = True
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    chunk_size_tokens: int = 384
    chunk_overlap_tokens: int = 64
    retrieval_top_k: int = 20
    rerank_top_k: int = 5
    no_answer_threshold: float = 0.15
    faithfulness_threshold: float = 0.7

    rate_limit_per_min: int = 120
    cors_allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    model_config = SettingsConfigDict(
        env_file=_RESOLVED_ENV_FILES if _RESOLVED_ENV_FILES else None,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
