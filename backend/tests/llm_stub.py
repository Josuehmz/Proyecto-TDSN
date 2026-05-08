"""Solo tests: LLM estable sin llamar a APIs remotas."""

from __future__ import annotations

import re

from app.rag.generator import Generation


class DeterministicPipelineStubLLM:
    """Misma superficie que el cliente real (`generate`): respuestas fijas solo para pytest."""

    def generate(self, *, system: str, user: str) -> Generation:
        _ = system
        if "INVENTARIO_AUTORIZADO:" in user:
            return self._inventory_stub(user)
        ctx_marker = "CONTEXTO:\n"
        if ctx_marker not in user:
            return Generation(answer="NO_ANSWER", prompt_tokens_approx=0, completion_tokens_approx=0)
        context = user.split(ctx_marker, 1)[1]
        if context.strip().startswith("(sin contexto)"):
            return Generation(answer="NO_ANSWER", prompt_tokens_approx=0, completion_tokens_approx=0)
        blocks = [b.strip() for b in context.split("\n\n") if b.strip()]
        if not blocks:
            return Generation(answer="NO_ANSWER", prompt_tokens_approx=0, completion_tokens_approx=0)
        parts_out: list[str] = []
        for i, first_block in enumerate(blocks[:6], start=1):
            body = first_block.split("\n", 1)[1] if "\n" in first_block else first_block
            words = body.split()
            snippet = " ".join(words[:40])
            parts_out.append(f"{snippet} [#{i}]")
        answer = "(pytest_stub) Sintético multi-documento · " + " · ".join(parts_out)
        return Generation(
            answer=answer,
            prompt_tokens_approx=len(user.split()),
            completion_tokens_approx=len(answer.split()),
        )

    def _inventory_stub(self, user: str) -> Generation:
        block = user.split("INVENTARIO_AUTORIZADO:", 1)[1]
        qtag = "PREGUNTA_DEL_USUARIO:"
        body = block.split(qtag, 1)[0] if qtag in block else block
        lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
        if not lines or lines[0].lower().startswith("(vacío"):
            answer = (
                "Con las reglas actuales de tu sesión no hay documentos en el inventario autorizado."
            )
            return Generation(
                answer=answer,
                prompt_tokens_approx=len(user.split()),
                completion_tokens_approx=len(answer.split()),
            )
        titles: list[str] = []
        pat = re.compile(r"^\[#\d+\]\s*titulo=(.+?)\s*\|")
        for ln in lines:
            m = pat.match(ln)
            if m:
                titles.append(m.group(1).strip())
        if not titles:
            return Generation(answer="NO_ANSWER", prompt_tokens_approx=0, completion_tokens_approx=0)
        mention = ", ".join(f"«{t}»" for t in titles)
        answer = (
            f"[pytest_stub] Inventario sintético: {mention}. "
            "Son metadatos; pregunta por contenido cuando quieras detalle."
        )
        return Generation(
            answer=answer,
            prompt_tokens_approx=len(user.split()),
            completion_tokens_approx=len(answer.split()),
        )


TEST_PIPELINE_LLM_STUB = DeterministicPipelineStubLLM()
