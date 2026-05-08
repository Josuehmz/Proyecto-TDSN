from __future__ import annotations

import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Chunk, Document
from app.deps import Principal
from app.policy.engine import document_accessible_predicate
from app.rag.conversation import fold_text


def looks_like_document_catalog_query(query: str) -> bool:
    raw = query.strip()
    if len(raw) > 380:
        return False
    f = fold_text(raw)
    # Pistas de contenido (no inventario administrativo).
    if re.search(r"\bque\s+documentos\s+sobre\b", f):
        return False
    if "documentos que" in f and not re.search(
        r"\bdocumentos\s+que\s+(hay|tienes|tiene|existen|tienen|de)\b",
        f,
    ):
        return False
    if "todos los documentos" in f and ("resumen" in f or "resume" in f):
        return False
    if re.search(r"\bque\s+documentos\b", f) and (
        re.search(r"\bque\s+documentos\s+(hay|tienes|tiene|existen|tienen|de)\b", f)
    ):
        return True
    if re.search(r"\b(lista|listado)\b.*\bdocumentos\b", f):
        return True
    if re.search(r"\bdocumentos\b.*\b(lista|listado)\b", f):
        return True
    if "todos los documentos" in f and re.search(
        r"\b(dame|muestrame|ensename|listado|lista|quiero ver|ver los|mostrar|enumera|listar|cuales son|pasame)\b",
        f,
    ):
        return True
    if "listado de documentos" in f or "lista de documentos" in f:
        return True
    if "documentos disponibles" in f or "archivos disponibles" in f:
        return True
    if ("muestrame" in f or "ensename" in f) and "documentos" in f:
        return True
    # "que documentos tienes", "documentos tienes/hay"
    if "documentos tienes" in f or "documentos hay" in f or "documentos tiene" in f:
        return True
    if "archivos tienes" in f or "archivos hay" in f:
        return True
    if "cuales son los documentos" in f or "cuantas documentos" in f:
        return True
    if re.search(r"\b(inventario|catalogo)\b", f) and "documentos" in f:
        return True
    if re.search(r"\bdocumentos?\b.*\b(inventario|catalogo)\b", f):
        return True
    if re.search(r"\b(enumera|enumerar|listar)\s+(los\s+)?documentos\b", f):
        return True
    return False


looks_like_admin_catalog_query = looks_like_document_catalog_query


def fetch_accessible_documents_catalog(
    db: Session,
    principal: Principal,
) -> list[tuple[Document, int]]:
    pred = document_accessible_predicate(principal)
    stmt = (
        select(Document, func.count(Chunk.id).label("chunk_count"))
        .outerjoin(Chunk, Chunk.document_id == Document.id)
        .where(pred)
        .group_by(Document.id)
        .order_by(Document.created_at.desc())
    )
    rows = db.execute(stmt).all()
    return [(doc, int(count or 0)) for doc, count in rows]


def build_admin_inventory_user_message(
    org: str,
    user_query: str,
    rows: list[tuple[Document, int]],
) -> str:
    """Hechos de catálogo para el LLM (sin prosa fija en backend)."""

    lines: list[str] = [f"ORGANIZACIÓN: {org}", "", "INVENTARIO_AUTORIZADO:"]
    if not rows:
        lines.append("(vacío — ningún documento cumple políticas para tu sesión)")
    else:
        for i, (doc, nchunks) in enumerate(rows, start=1):
            r = ",".join(doc.allowed_roles) if doc.allowed_roles else "-"
            d = ",".join(doc.allowed_departments) if doc.allowed_departments else "-"
            lines.append(
                f"[#{i}] titulo={doc.title} | fragmentos={nchunks} | "
                f"clearance={doc.required_clearance} | roles={r} | departamentos={d}"
            )
    lines.extend(["", f"PREGUNTA_DEL_USUARIO:\n{user_query.strip()}"])
    return "\n".join(lines)
