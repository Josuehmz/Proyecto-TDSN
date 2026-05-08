from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.config import get_settings
from app.rag.retriever import RetrievedChunk

SYSTEM_PROMPT = (
    "Eres un asistente corporativo. Responde EXCLUSIVAMENTE con la información "
    "del CONTEXTO. Si la pregunta no se puede responder con el contexto, "
    "responde literalmente: NO_ANSWER. Incluye citas con el formato [#n] "
    "donde n es el índice del fragmento usado (empezando en 1)."
)

ADMIN_INVENTORY_SYSTEM_PROMPT = (
    "Eres un asistente corporativo. Solo puedes usar el bloque "
    "INVENTARIO_AUTORIZADO; no inventes documentos ni atributos que no figuren ahí. "
    "Si el inventario está vacío, dilo con tono profesional breve en español. "
    "Si hay filas, responde en español de forma natural y conversacional, "
    "integrando cada documento listado sin omitir ninguno. Deja claro que son "
    "metadatos de catálogo (títulos, fragmentos, clearance, roles/departamentos); "
    "el texto completo de cada documento se obtiene con preguntas de contenido posteriores."
)


@dataclass(frozen=True)
class Generation:
    answer: str
    prompt_tokens_approx: int
    completion_tokens_approx: int


class LLMClient(Protocol):
    def generate(self, *, system: str, user: str) -> Generation: ...


def build_prompt(query: str, chunks: list[RetrievedChunk]) -> str:
    context_lines: list[str] = []
    for i, c in enumerate(chunks, start=1):
        header = f"[#{i}] ({c.document_title}, fragmento {c.ordinal})"
        context_lines.append(f"{header}\n{c.text}")
    context = "\n\n".join(context_lines) if context_lines else "(sin contexto)"
    multi = len(chunks) > 1
    multi_hint = ""
    if multi:
        multi_hint = (
            "\n- Hay varios fragmentos: sintetiza de forma cohesionada usando la información de "
            "cada uno que sea pertinente; no ignores un segundo documento sin motivo fuerte "
            "(cita [#n] por cada parte que tomes)."
        )
    return (
        f"PREGUNTA:\n{query}\n\n"
        f"CONTEXTO:\n{context}\n\n"
        "Reglas:\n"
        "- Usa únicamente el CONTEXTO para responder.\n"
        "- Cita cada afirmación sustantiva con [#n].\n"
        "- Si no hay información suficiente, responde 'NO_ANSWER'."
        f"{multi_hint}\n"
    )


class OpenAICompatibleChatLLM:
    """Chat completions vía API compatible con OpenAI (OpenAI, Groq, etc.)."""

    def __init__(self, model: str, api_key: str, *, base_url: str | None = None) -> None:
        from openai import OpenAI

        kw: dict = {"api_key": api_key, "timeout": 120.0}
        if base_url:
            kw["base_url"] = base_url.rstrip("/")
        self._client = OpenAI(**kw)
        self._model = model

    def generate(self, *, system: str, user: str) -> Generation:
        resp = self._client.chat.completions.create(
            model=self._model,
            temperature=0.1,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        choice = resp.choices[0].message.content or ""
        usage = resp.usage
        return Generation(
            answer=choice.strip(),
            prompt_tokens_approx=usage.prompt_tokens if usage else 0,
            completion_tokens_approx=usage.completion_tokens if usage else 0,
        )


_llm_client: LLMClient | None = None
_llm_build_key: tuple[object, ...] | None = None


def _llm_config_key(settings) -> tuple[object, ...]:
    return (
        settings.llm_provider,
        (settings.openai_api_key or "").strip(),
        (settings.groq_api_key or "").strip(),
        settings.openai_model,
        settings.groq_model,
        (settings.groq_base_url or "").strip(),
    )


def _instantiate_llm(settings) -> LLMClient:
    if settings.llm_provider == "openai":
        if not (settings.openai_api_key or "").strip():
            raise RuntimeError("OPENAI_API_KEY requerido para LLM_PROVIDER=openai")
        return OpenAICompatibleChatLLM(settings.openai_model, settings.openai_api_key.strip())
    if settings.llm_provider == "groq":
        key = (settings.groq_api_key or "").strip()
        if not key:
            raise RuntimeError("GROQ_API_KEY requerido para LLM_PROVIDER=groq")
        return OpenAICompatibleChatLLM(
            settings.groq_model,
            key,
            base_url=settings.groq_base_url,
        )
    raise RuntimeError(
        f"Proveedor LLM no soportado: {settings.llm_provider!r}. "
        "Use LLM_PROVIDER=openai | groq con su clave configurada."
    )


def get_llm_client() -> LLMClient:
    global _llm_client, _llm_build_key
    settings = get_settings()
    key_cfg = _llm_config_key(settings)
    if _llm_client is None or key_cfg != _llm_build_key:
        _llm_build_key = key_cfg
        _llm_client = _instantiate_llm(settings)
    return _llm_client


def reset_llm_client() -> None:
    global _llm_client, _llm_build_key
    _llm_client = None
    _llm_build_key = None
