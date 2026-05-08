from __future__ import annotations

import re

from app.rag.conversation import fold_text

_WORD_RE = re.compile(r"[a-z0-9]{4,}")


def lexical_overlap_count(query: str, text: str) -> int:
    q = set(_WORD_RE.findall(fold_text(query.replace("-", " "))))
    t = set(_WORD_RE.findall(fold_text(text.replace("-", " "))))
    return len(q & t)


def document_title_matches_query(query: str, title: str) -> bool:
    """True si la pregunta alinea lo suficiente con el título (sin nombre literal completo)."""

    q = set(_WORD_RE.findall(fold_text(query.replace("-", " "))))
    significant = {t for t in q if len(t) >= 4}
    if not significant:
        return False
    o = lexical_overlap_count(query, title)
    if len(significant) == 1:
        return o >= 1
    return o >= 2


def lexical_relatedness_score(query: str, text: str) -> int:
    """Overlap de tokens + refuerzos mínimos para marcas/expresiones demo."""
    n = lexical_overlap_count(query, text)
    fq = fold_text(query)
    ft = fold_text(text)
    if "orion" in fq and "orion" in ft and "dynamics" in ft:
        n += 2
    if "titanium" in fq and "titanium" in ft and ("works" in ft or "works" in fq):
        n += 2
    return n
