from __future__ import annotations

import re
import unicodedata

from sqlalchemy import select

from app.db.models import Tenant
from app.db.session import session_scope
from app.deps import Principal

# Respuestas fijas (no filtran datos; no citan documentos).
# Misma redacción ante ABAC, política e indicios de otro tenant: no revelar que existen datos ocultos.
MSG_PLAUSIBLE_DENIAL = "Lo siento, pero no tengo esa información."
MSG_UNAUTHORIZED = MSG_PLAUSIBLE_DENIAL
MSG_OTHER_TENANT = MSG_PLAUSIBLE_DENIAL
MSG_NO_CORPUS_MATCH = (
    "No encuentro información sobre eso en los documentos de tu organización "
    "a los que puedo acceder."
)

# Pistas de que el usuario pide explícitamente datos propios de otro tenant demo
# (heurística conservadora: subcadenas en texto normalizado).
_CROSS_TENANT_HINTS: dict[str, tuple[str, ...]] = {
    "acme": (
        "globex",
        "globex industries",
        "helios",
        "helios-mk3",
        "helios mk3",
        "nebula",
        "red-basilisk",
        "titanium-works",
        "nueva austral",
    ),
    "globex": (
        "acme corp",
        "acme ",
        "bluefalcon",
        "neo-caldas",
        "quasar",
        "sigma-9",
        "supernova",
    ),
}


def fold_text(s: str) -> str:
    """Minúsculas y sin acentos para comparaciones simples."""
    nfkd = unicodedata.normalize("NFD", s.casefold())
    return "".join(c for c in nfkd if unicodedata.category(c) != "Mn")


def get_tenant_display_name(slug: str) -> str:
    with session_scope(None) as db:
        name = db.execute(select(Tenant.name).where(Tenant.slug == slug)).scalar_one_or_none()
    return name or slug


def looks_like_other_tenant_probe(query: str, tenant_slug: str) -> bool:
    q = fold_text(query)
    hints = _CROSS_TENANT_HINTS.get(tenant_slug, ())
    return any(h in q for h in hints)


_IDENTITY_PATTERNS = (
    re.compile(
        r"\b(a que empresa|a qué empresa|que empresa|qué empresa|mi empresa|"
        r"pertenezco|pertenesco|mi organizacion|mi organización|mi tenant|"
        r"donde trabajo|dónde trabajo|quien soy|quién soy)\b",
        re.IGNORECASE,
    ),
)


def looks_like_identity_question(query: str) -> bool:
    q = query.strip()
    if len(q) > 200:
        return False
    return any(p.search(q) for p in _IDENTITY_PATTERNS)


_THANKS = frozenset(
    {
        "gracias",
        "muchas gracias",
        "mil gracias",
        "te lo agradezco",
        "agradecido",
        "agradecida",
    }
)

_GREETING_STARTS = (
    "hola",
    "hey",
    "hi",
    "hello",
    "buenos dias",
    "buenos días",
    "buenas tardes",
    "buenas noches",
    "buenas",
    "saludos",
    "qué tal",
    "que tal",
    "como estas",
    "cómo estás",
)


def looks_like_light_chitchat(query: str) -> bool:
    raw = query.strip()
    if not raw or len(raw) > 120:
        return False
    f = fold_text(raw)
    if f in _THANKS:
        return True
    if f in ("ok", "vale", "de acuerdo", "entendido", "perfecto"):
        return True
    for g in _GREETING_STARTS:
        if f == g or f.startswith(g + " ") or f.startswith(g + ",") or f.startswith(g + "!"):
            return True
    return False


def build_chitchat_reply(principal: Principal) -> str:
    org = get_tenant_display_name(principal.tenant_slug)
    return (
        f"Hola. Soy el asistente de conocimiento de **{org}**. "
        "Puedo ayudarte con preguntas basadas en los documentos internos a los que tienes "
        "acceso según tu rol y tu nivel de clearance. ¿En qué puedo apoyarte?"
    )


def build_identity_reply(principal: Principal) -> str:
    org = get_tenant_display_name(principal.tenant_slug)
    return (
        f"Según tu sesión, perteneces a **{org}**, "
        f"con nivel de clearance **{principal.clearance}** y roles: "
        f"{', '.join(principal.roles) or '—'}."
    )


def build_thanks_reply(principal: Principal) -> str:
    org = get_tenant_display_name(principal.tenant_slug)
    return f"¡De nada! Si surge algo más sobre **{org}**, aquí estaré."


def conversation_reply(principal: Principal, query: str) -> str | None:
    """Respuesta conversacional segura (solo metadatos del principal / saludo)."""

    if looks_like_identity_question(query):
        return build_identity_reply(principal)
    f = fold_text(query.strip())
    if f in _THANKS or f.rstrip("!.") in _THANKS:
        return build_thanks_reply(principal)
    if looks_like_light_chitchat(query):
        return build_chitchat_reply(principal)
    return None
