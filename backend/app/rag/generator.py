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
    return (
        f"PREGUNTA:\n{query}\n\n"
        f"CONTEXTO:\n{context}\n\n"
        "Reglas:\n"
        "- Usa únicamente el CONTEXTO para responder.\n"
        "- Cita cada afirmación con [#n].\n"
        "- Si no hay información suficiente, responde 'NO_ANSWER'."
    )


class MockLLM:
    """LLM determinista: responde con un snippet del primer chunk citado."""

    def generate(self, *, system: str, user: str) -> Generation:
        ctx_marker = "CONTEXTO:\n"
        if ctx_marker not in user:
            return Generation(answer="NO_ANSWER", prompt_tokens_approx=0, completion_tokens_approx=0)
        context = user.split(ctx_marker, 1)[1]
        if context.strip().startswith("(sin contexto)"):
            return Generation(answer="NO_ANSWER", prompt_tokens_approx=0, completion_tokens_approx=0)
        first_block = context.split("\n\n", 1)[0]
        body = first_block.split("\n", 1)[1] if "\n" in first_block else first_block
        words = body.split()
        snippet = " ".join(words[:60])
        answer = f"{snippet} [#1]"
        return Generation(
            answer=answer,
            prompt_tokens_approx=len(user.split()),
            completion_tokens_approx=len(answer.split()),
        )


class OpenAILLM:
    def __init__(self, model: str, api_key: str) -> None:
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key)
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


def get_llm_client() -> LLMClient:
    global _llm_client
    if _llm_client is not None:
        return _llm_client
    settings = get_settings()
    if settings.llm_provider == "openai":
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY requerido para LLM=openai")
        _llm_client = OpenAILLM(settings.openai_model, settings.openai_api_key)
    else:
        _llm_client = MockLLM()
    return _llm_client


def reset_llm_client() -> None:
    global _llm_client
    _llm_client = None
