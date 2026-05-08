from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Chunk, Document
from app.deps import Principal
from app.policy.engine import PolicyDecision, document_accessible_predicate, obligations_to_sqlalchemy
from app.rag.embeddings import get_embeddings_model
from app.rag.query_semantics import document_title_matches_query


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
    return retrieve_with_optional_abac_filters(
        db,
        query=query,
        top_k=top_k,
        obligations_where=obligations_to_sqlalchemy(policy.obligations),
    )


def retrieve_within_tenant_ignore_abac(db: Session, *, query: str, top_k: int) -> list[RetrievedChunk]:
    """ANN sin filtros clearance/roles/dept dentro del mismo schema tenant."""

    return retrieve_with_optional_abac_filters(db, query=query, top_k=top_k, obligations_where=None)


def retrieve_chunks_by_title_match(
    db: Session,
    *,
    principal: Principal,
    query: str,
    policy: PolicyDecision,
    max_documents: int = 6,
    chunks_per_document: int = 4,
    synthetic_score: float = 0.32,
) -> list[RetrievedChunk]:
    """Candidatos por alineación léxica pregunta↔título (misma política ABAC que el ANN)."""

    if not policy.allow:
        return []
    doc_stmt = (
        select(Document.id, Document.title)
        .where(document_accessible_predicate(principal))
        .order_by(Document.created_at.desc())
    )
    doc_rows = db.execute(doc_stmt).all()
    matched: list[UUID] = []
    for doc_id, title in doc_rows:
        if document_title_matches_query(query, title):
            matched.append(doc_id)
        if len(matched) >= max_documents:
            break
    if not matched:
        return []
    ow = obligations_to_sqlalchemy(policy.obligations)
    stmt = (
        select(
            Chunk.id,
            Chunk.document_id,
            Chunk.ordinal,
            Chunk.text,
            Document.title.label("document_title"),
        )
        .join(Document, Document.id == Chunk.document_id)
        .where(Chunk.document_id.in_(matched))
        .where(ow)
        .order_by(Chunk.document_id, Chunk.ordinal)
    )
    rows = db.execute(stmt).all()
    per_doc: dict[UUID, int] = {}
    out: list[RetrievedChunk] = []
    for r in rows:
        n = per_doc.get(r.document_id, 0)
        if n >= chunks_per_document:
            continue
        per_doc[r.document_id] = n + 1
        out.append(
            RetrievedChunk(
                chunk_id=r.id,
                document_id=r.document_id,
                document_title=r.document_title,
                ordinal=r.ordinal,
                text=r.text,
                score=synthetic_score,
            )
        )
    return out


def retrieve_with_optional_abac_filters(
    db: Session,
    *,
    query: str,
    top_k: int,
    obligations_where: Any | None,
) -> list[RetrievedChunk]:
    model = get_embeddings_model()
    [query_embedding] = model.embed([query])

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
        .order_by(cosine_distance.asc())
        .limit(top_k)
    )
    if obligations_where is not None:
        stmt = stmt.where(obligations_where)

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
