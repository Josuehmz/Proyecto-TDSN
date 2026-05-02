from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.schemas import DocumentListOut, DocumentOut
from app.audit.logger import audit
from app.db.models import Chunk, Document
from app.deps import Principal, get_principal, get_request_id, get_tenant_db
from app.ingest.pipeline import ingest_document
from app.policy.engine import ClearanceLevel

router = APIRouter(prefix="/documents", tags=["documents"])


def _require_role(principal: Principal, role: str) -> None:
    if role not in principal.roles:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail=f"Se requiere el rol '{role}' para esta operación",
        )


@router.get("", response_model=DocumentListOut)
def list_documents(
    db: Annotated[Session, Depends(get_tenant_db)],
    principal: Annotated[Principal, Depends(get_principal)],
) -> DocumentListOut:
    max_level = ClearanceLevel.from_str(principal.clearance)
    allowed = {lvl.name for lvl in ClearanceLevel if lvl <= max_level}

    stmt = (
        select(Document, func.count(Chunk.id).label("chunk_count"))
        .join(Chunk, Chunk.document_id == Document.id, isouter=True)
        .where(Document.required_clearance.in_(allowed))
        .group_by(Document.id)
        .order_by(Document.created_at.desc())
    )
    rows = db.execute(stmt).all()
    items = [
        DocumentOut(
            id=doc.id,
            title=doc.title,
            source=doc.source,
            required_clearance=doc.required_clearance,
            allowed_roles=list(doc.allowed_roles or []),
            allowed_departments=list(doc.allowed_departments or []),
            byte_size=doc.byte_size,
            chunk_count=int(count or 0),
        )
        for doc, count in rows
    ]
    return DocumentListOut(documents=items)


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
def upload_document(
    db: Annotated[Session, Depends(get_tenant_db)],
    principal: Annotated[Principal, Depends(get_principal)],
    request_id: Annotated[str, Depends(get_request_id)],
    file: UploadFile = File(...),
    title: str = Form(...),
    required_clearance: str = Form("public"),
    allowed_roles: str = Form(""),
    allowed_departments: str = Form(""),
) -> DocumentOut:
    _require_role(principal, "admin")

    content = file.file.read()
    if not content:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Archivo vacío")

    roles_list = [r.strip() for r in allowed_roles.split(",") if r.strip()]
    dep_list = [d.strip() for d in allowed_departments.split(",") if d.strip()]

    try:
        result = ingest_document(
            db,
            title=title,
            filename=file.filename or "upload",
            content=content,
            mime_type=file.content_type or "application/octet-stream",
            required_clearance=required_clearance,
            allowed_roles=roles_list,
            allowed_departments=dep_list,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    audit(
        action="documents.upload",
        tenant_slug=principal.tenant_slug,
        user_id=principal.user_id,
        request_id=request_id,
        decision="allow",
        detail={
            "document_id": str(result.document_id),
            "chunks": result.chunk_count,
            "required_clearance": required_clearance,
        },
    )

    return DocumentOut(
        id=result.document_id,
        title=result.title,
        source=file.filename or "upload",
        required_clearance=required_clearance,
        allowed_roles=roles_list,
        allowed_departments=dep_list,
        byte_size=len(content),
        chunk_count=result.chunk_count,
    )
