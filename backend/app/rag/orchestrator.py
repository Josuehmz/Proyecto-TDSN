from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import QueryLog
from app.deps import Principal
from app.logging_config import get_logger
from app.policy.engine import evaluate_query_policy
from app.rag.generator import SYSTEM_PROMPT, build_prompt, get_llm_client
from app.rag.reranker import get_reranker
from app.rag.retriever import RetrievedChunk, retrieve

logger = get_logger(__name__)


@dataclass
class Citation:
    index: int
    chunk_id: UUID
    document_id: UUID
    document_title: str
    ordinal: int
    score: float
    snippet: str


@dataclass
class QueryResult:
    request_id: str
    answered: bool
    answer: str
    citations: list[Citation]
    policy_reasons: list[str]
    retrieved: int
    top_score: float
    latency_ms: float
    tokens: dict[str, int]

    def to_public_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["citations"] = [
            {**c, "chunk_id": str(c["chunk_id"]), "document_id": str(c["document_id"])}
            for c in data["citations"]
        ]
        return data


def run_query(
    db: Session,
    *,
    principal: Principal,
    query: str,
    request_id: str,
) -> QueryResult:
    settings = get_settings()
    t0 = time.perf_counter()

    decision = evaluate_query_policy(principal)
    if not decision.allow:
        result = QueryResult(
            request_id=request_id,
            answered=False,
            answer="NO_ANSWER",
            citations=[],
            policy_reasons=decision.reasons,
            retrieved=0,
            top_score=0.0,
            latency_ms=(time.perf_counter() - t0) * 1000,
            tokens={"prompt": 0, "completion": 0},
        )
        _persist_query_log(db, principal=principal, query=query, result=result)
        return result

    retrieved = retrieve(db, query=query, policy=decision, top_k=settings.retrieval_top_k)

    reranker = get_reranker()
    top = reranker.rerank(query, retrieved, settings.rerank_top_k)
    top_score = top[0].score if top else 0.0

    if not top or top_score < settings.no_answer_threshold:
        result = QueryResult(
            request_id=request_id,
            answered=False,
            answer="NO_ANSWER",
            citations=[],
            policy_reasons=decision.reasons
            + [f"top_score={top_score:.3f} < umbral={settings.no_answer_threshold}"],
            retrieved=len(retrieved),
            top_score=top_score,
            latency_ms=(time.perf_counter() - t0) * 1000,
            tokens={"prompt": 0, "completion": 0},
        )
        _persist_query_log(db, principal=principal, query=query, result=result)
        return result

    user_prompt = build_prompt(query, top)
    gen = get_llm_client().generate(system=SYSTEM_PROMPT, user=user_prompt)

    answered = gen.answer.strip().upper() != "NO_ANSWER"
    citations = [_to_citation(i + 1, c) for i, c in enumerate(top)]

    result = QueryResult(
        request_id=request_id,
        answered=answered,
        answer=gen.answer,
        citations=citations if answered else [],
        policy_reasons=decision.reasons,
        retrieved=len(retrieved),
        top_score=top_score,
        latency_ms=(time.perf_counter() - t0) * 1000,
        tokens={
            "prompt": gen.prompt_tokens_approx,
            "completion": gen.completion_tokens_approx,
        },
    )
    _persist_query_log(db, principal=principal, query=query, result=result)
    logger.info(
        "rag.query.done",
        answered=answered,
        retrieved=len(retrieved),
        top_score=round(top_score, 3),
        latency_ms=round(result.latency_ms, 1),
    )
    return result


def _to_citation(index: int, chunk: RetrievedChunk) -> Citation:
    return Citation(
        index=index,
        chunk_id=chunk.chunk_id,
        document_id=chunk.document_id,
        document_title=chunk.document_title,
        ordinal=chunk.ordinal,
        score=chunk.score,
        snippet=chunk.text[:400],
    )


def _persist_query_log(
    db: Session,
    *,
    principal: Principal,
    query: str,
    result: QueryResult,
) -> None:
    entry = QueryLog(
        user_id=principal.user_id,
        request_id=result.request_id,
        query_text=query[:4000],
        latency_ms=result.latency_ms,
        retrieved=result.retrieved,
        answered=result.answered,
        top_score=result.top_score,
        citations=[str(c.chunk_id) for c in result.citations],
    )
    db.add(entry)
