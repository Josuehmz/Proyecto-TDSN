from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum

from sqlalchemy import ColumnElement, and_, or_

from app.db.models import Chunk
from app.deps import Principal


class ClearanceLevel(IntEnum):
    public = 0
    internal = 1
    confidential = 2
    restricted = 3

    @classmethod
    def from_str(cls, value: str) -> "ClearanceLevel":
        try:
            return cls[value.lower()]
        except KeyError as exc:
            raise ValueError(f"Clearance desconocido: {value}") from exc


@dataclass(frozen=True)
class PolicyDecision:
    allow: bool
    obligations: list[ColumnElement] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)


def evaluate_query_policy(principal: Principal) -> PolicyDecision:
    """Traduce los atributos ABAC del principal a filtros SQL pre-retrieval."""

    reasons: list[str] = []
    if not principal.roles:
        return PolicyDecision(allow=False, reasons=["principal sin roles asignados"])

    user_clearance = ClearanceLevel.from_str(principal.clearance)
    allowed_clearance = [lvl.name for lvl in ClearanceLevel if lvl <= user_clearance]

    obligations: list[ColumnElement] = [
        Chunk.required_clearance.in_(allowed_clearance),
        or_(Chunk.allowed_roles == [], Chunk.allowed_roles.overlap(principal.roles)),
        or_(
            Chunk.allowed_departments == [],
            Chunk.allowed_departments.overlap(principal.departments),
        ),
    ]
    reasons.append(
        f"clearance≤{user_clearance.name}; roles⊇{principal.roles}; "
        f"departments⊇{principal.departments}"
    )
    return PolicyDecision(allow=True, obligations=obligations, reasons=reasons)


def obligations_to_sqlalchemy(obligations: list[ColumnElement]) -> ColumnElement:
    if not obligations:
        # Deny-by-default defensivo.
        return Chunk.id.is_(None)
    return and_(*obligations)
