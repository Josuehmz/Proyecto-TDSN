from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.auth.security import decode_token
from app.db.session import session_scope
from app.tenancy.context import validate_tenant_slug


@dataclass(frozen=True)
class Principal:
    user_id: UUID
    tenant_slug: str
    email: str
    roles: list[str]
    clearance: str
    departments: list[str]


def _extract_bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falta cabecera Authorization: Bearer …",
        )
    return authorization.split(" ", 1)[1].strip()


def get_principal(
    authorization: Annotated[str | None, Header()] = None,
) -> Principal:
    token = _extract_bearer(authorization)
    try:
        claims = decode_token(token)
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Token expirado") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Token inválido") from exc

    try:
        tenant = validate_tenant_slug(claims["tenant"])
    except Exception as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Tenant inválido") from exc

    try:
        user_id = UUID(str(claims["sub"]))
    except Exception as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="sub inválido") from exc

    return Principal(
        user_id=user_id,
        tenant_slug=tenant,
        email=str(claims.get("email", "")),
        roles=list(claims.get("roles", [])),
        clearance=str(claims.get("clearance", "public")),
        departments=list(claims.get("departments", [])),
    )


def get_tenant_db(
    principal: Annotated[Principal, Depends(get_principal)],
) -> Session:
    with session_scope(principal.tenant_slug) as session:
        yield session


def get_platform_db() -> Session:
    with session_scope(None) as session:
        yield session


def get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")
