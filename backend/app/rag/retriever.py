from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Chunk, Document
from app.policy.engine import PolicyDecision, obligations_to_sqlalchemy
from app.rag.embeddings import get_embeddings_model


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: UUID
    document_id: UUID
    document_title: str
    ordinal: int
    text: str
    score: float


def retrieve(
    db: Session,
    *,
    query: str,
    policy: PolicyDecision,
    top_k: int,
) -> list[RetrievedChunk]:
    if not policy.allow:
        return []

    model = get_embeddings_model()
    [query_embedding] = model.embed([query])

    where_clause = obligations_to_sqlalchemy(policy.obligations)
    cosine_distance = Chunk.embedding.cosine_distance(query_embedding)

    stmt = (
        select(
            Chunk.id,
            Chunk.document_id,
            Chunk.ordinal,
            Chunk.text,
            cosine_distance.label("distance"),
            Document.title.label("document_title"),
        )
        .join(Document, Document.id == Chunk.document_id)
        .where(where_clause)
        .order_by(cosine_distance.asc())
        .limit(top_k)
    )
    rows = db.execute(stmt).all()
    return [
        RetrievedChunk(
            chunk_id=r.id,
            document_id=r.document_id,
            document_title=r.document_title,
            ordinal=r.ordinal,
            text=r.text,
            score=max(0.0, 1.0 - float(r.distance)),
        )
        for r in rows
    ]
