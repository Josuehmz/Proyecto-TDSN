from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import AuditEvent
from app.db.session import session_scope


def audit(
    *,
    action: str,
    tenant_slug: str | None,
    user_id: UUID | None,
    request_id: str | None,
    decision: str | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    """Persiste un evento de auditoría; falla silenciosa para no romper el request."""

    try:
        with session_scope(None) as db:
            _audit_in_session(
                db,
                action=action,
                tenant_slug=tenant_slug,
                user_id=user_id,
                request_id=request_id,
                decision=decision,
                detail=detail,
            )
    except Exception:  # pragma: no cover
        pass


def _audit_in_session(
    db: Session,
    *,
    action: str,
    tenant_slug: str | None,
    user_id: UUID | None,
    request_id: str | None,
    decision: str | None,
    detail: dict[str, Any] | None,
) -> None:
    db.add(
        AuditEvent(
            action=action,
            tenant_slug=tenant_slug,
            user_id=user_id,
            request_id=request_id,
            decision=decision,
            detail=detail or {},
        )
    )
