"""Recalcula embeddings de todos los chunks con título + cuerpo (tras cambios en pipeline).

Uso: docker compose exec backend python -m app.scripts.reembed_chunks
"""

from __future__ import annotations

import sys

from sqlalchemy import select

from app.db.models import Chunk, Document, Tenant
from app.db.session import session_scope
from app.ingest.pipeline import embedding_input_text
from app.logging_config import configure_logging, get_logger
from app.rag.embeddings import get_embeddings_model
from app.scripts.init_db import ensure_platform


def _reembed_tenant(slug: str, *, batch_size: int = 48) -> int:
    model = get_embeddings_model()
    n = 0
    with session_scope(slug) as db:
        stmt = select(Chunk, Document.title).join(Document, Document.id == Chunk.document_id)
        rows = db.execute(stmt).all()
        for i in range(0, len(rows), batch_size):
            batch = rows[i : i + batch_size]
            texts = [embedding_input_text(title, ch.text) for ch, title in batch]
            vectors = model.embed(texts)
            for (ch, _), vec in zip(batch, vectors, strict=True):
                ch.embedding = vec
                n += 1
    return n


def main() -> int:
    configure_logging()
    logger = get_logger(__name__)
    ensure_platform()
    with session_scope(None) as db:
        slugs = list(db.execute(select(Tenant.slug).order_by(Tenant.slug)).scalars().all())
    total = 0
    for slug in slugs:
        n = _reembed_tenant(slug, batch_size=48)
        logger.info("reembed.tenant.done", slug=slug, chunks=n)
        total += n
    logger.info("reembed.all.done", tenants=len(slugs), chunks=total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
