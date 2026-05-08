from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.tenancy.context import tenant_schema

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine, _SessionLocal
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
            future=True,
        )
        _SessionLocal = sessionmaker(
            bind=_engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
            class_=Session,
        )
    return _engine


def _get_session_factory() -> sessionmaker[Session]:
    get_engine()
    assert _SessionLocal is not None
    return _SessionLocal


@contextmanager
def session_scope(tenant_slug: str | None = None) -> Iterator[Session]:
    """Sesión con search_path fijado al schema del tenant (aislamiento P1)."""

    session_factory = _get_session_factory()
    session: Session = session_factory()
    try:
        if tenant_slug is not None:
            schema = tenant_schema(tenant_slug)
            session.execute(text(f'SET LOCAL search_path TO "{schema}", platform, public'))
        else:
            session.execute(text("SET LOCAL search_path TO platform"))
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def fastapi_tenant_db(tenant_slug: str | None) -> Iterator[Session]:
    with session_scope(tenant_slug) as s:
        yield s


@event.listens_for(Engine, "connect")
def _register_pgvector(dbapi_connection, _connection_record):  # pragma: no cover
    try:
        from pgvector.psycopg import register_vector  # type: ignore[import-untyped]

        register_vector(dbapi_connection)
    except Exception:
        pass
