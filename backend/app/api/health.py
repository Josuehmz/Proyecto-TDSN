from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app.db.session import get_engine

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
def readyz() -> dict[str, str]:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        return {"status": "degraded", "detail": str(exc)}
    return {"status": "ready"}
