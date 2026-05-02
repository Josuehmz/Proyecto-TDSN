from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.schemas import CitationOut, QueryRequest, QueryResponse
from app.audit.logger import audit
from app.deps import Principal, get_principal, get_request_id, get_tenant_db
from app.rag.orchestrator import run_query

router = APIRouter(prefix="/query", tags=["query"])


@router.post("", response_model=QueryResponse)
def query_endpoint(
    payload: QueryRequest,
    db: Annotated[Session, Depends(get_tenant_db)],
    principal: Annotated[Principal, Depends(get_principal)],
    request_id: Annotated[str, Depends(get_request_id)],
) -> QueryResponse:
    result = run_query(db, principal=principal, query=payload.query, request_id=request_id)

    audit(
        action="query",
        tenant_slug=principal.tenant_slug,
        user_id=principal.user_id,
        request_id=request_id,
        decision="allow" if result.answered else "no_answer",
        detail={
            "query_len": len(payload.query),
            "retrieved": result.retrieved,
            "top_score": round(result.top_score, 3),
            "latency_ms": round(result.latency_ms, 1),
            "citations": [str(c.chunk_id) for c in result.citations],
        },
    )

    return QueryResponse(
        request_id=result.request_id,
        answered=result.answered,
        answer=result.answer,
        citations=[
            CitationOut(
                index=c.index,
                chunk_id=c.chunk_id,
                document_id=c.document_id,
                document_title=c.document_title,
                ordinal=c.ordinal,
                score=c.score,
                snippet=c.snippet,
            )
            for c in result.citations
        ],
        policy_reasons=result.policy_reasons,
        retrieved=result.retrieved,
        top_score=result.top_score,
        latency_ms=result.latency_ms,
        tokens=result.tokens,
    )
