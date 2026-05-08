from __future__ import annotations

import sys

from sqlalchemy import text

from app.db.models import PlatformBase, Tenant, TenantBase
from app.db.session import get_engine, session_scope
from app.logging_config import configure_logging, get_logger
from app.tenancy.context import tenant_schema


def ensure_platform() -> None:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS platform"))
    PlatformBase.metadata.create_all(bind=engine)


def ensure_tenant_schema(slug: str) -> None:
    schema = tenant_schema(slug)
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
        # Incluir public: el tipo vector de pgvector vive ahí; si search_path solo
        # apunta al schema tenant, CREATE TABLE … VECTOR(n) falla.
        conn.execute(text(f'SET search_path TO "{schema}", public'))
        TenantBase.metadata.create_all(bind=conn)


def ensure_all_tenants() -> list[str]:
    slugs: list[str] = []
    with session_scope(None) as db:
        for tenant in db.query(Tenant).all():
            ensure_tenant_schema(tenant.slug)
            slugs.append(tenant.slug)
    return slugs


def main() -> int:
    configure_logging()
    logger = get_logger(__name__)

    ensure_platform()
    tenants = ensure_all_tenants()
    logger.info("init_db.done", existing_tenants=tenants)

    # Idempotente: omite usuarios y títulos de documento ya existentes.
    from app.scripts.seed_tenants import seed_demo

    seed_demo()
    return 0


if __name__ == "__main__":
    sys.exit(main())
