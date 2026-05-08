from __future__ import annotations

import re
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
from app.rag.admin_catalog import (
    build_admin_inventory_user_message,
    fetch_accessible_documents_catalog,
    looks_like_document_catalog_query,
)
from app.rag.conversation import (
    MSG_NO_CORPUS_MATCH,
    MSG_OTHER_TENANT,
    MSG_UNAUTHORIZED,
    conversation_reply,
    fold_text,
    get_tenant_display_name,
    looks_like_other_tenant_probe,
)
from app.rag import generator as rag_generator
from app.rag.query_semantics import lexical_overlap_count, lexical_relatedness_score
from app.rag.reranker import get_reranker
from app.rag.retriever import (
    RetrievedChunk,
    retrieve,
    retrieve_chunks_by_title_match,
    retrieve_within_tenant_ignore_abac,
)

logger = get_logger(__name__)

_DOC_TITLE_LEX_WEIGHT = 0.06
_TEXT_BODY_LEX_WEIGHT = 0.012


def _merge_rerank_respecting_title_hits(
    *,
    retrieved: list[RetrievedChunk],
    reranked_pool: list[RetrievedChunk],
    title_match_ids: set[UUID],
    lex_ctx: str,
    top_k: int,
) -> tuple[list[RetrievedChunk], bool]:
    """Incluye siempre fragmentos de docs cuyo título acotó la búsqueda; el rerank suele
    depender del cuerpo y puede descartar el documento correcto si la pregunta es genérica."""

    seen: set[UUID] = set()
    candidates: list[RetrievedChunk] = []
    for c in retrieved:
        if c.chunk_id in title_match_ids and c.chunk_id not in seen:
            seen.add(c.chunk_id)
            candidates.append(c)
    for c in reranked_pool:
        if c.chunk_id not in seen:
            seen.add(c.chunk_id)
            candidates.append(c)
    top = sorted(
        candidates,
        key=lambda c: _adjusted_embedding_score(c, lex_ctx=lex_ctx),
        reverse=True,
    )[:top_k]
    if title_match_ids:
        title_candidates = [c for c in retrieved if c.chunk_id in title_match_ids]
        if title_candidates:
            best_t = max(
                title_candidates,
                key=lambda c: _adjusted_embedding_score(c, lex_ctx=lex_ctx),
            )
            rest = [c for c in top if c.chunk_id != best_t.chunk_id]
            top = [best_t] + rest[: top_k - 1]
    title_in_top = bool(title_match_ids and any(c.chunk_id in title_match_ids for c in top))
    return top, title_in_top


def _vague_aggregate_summary_query(query: str) -> bool:
    """P. ej. 'resumen de ambos documentos' sin citar nombres (Globex demo)."""

    f = fold_text(query)
    if "resumen" not in f and "resume" not in f:
        return False
    return bool(
        re.search(
            r"\b("
            r"ambos|(las|los)\s+dos|cada\s+uno|conjunto|"
            r"todos\s+los\s+documentos|"
            r"(estos|esos)\s+documentos|"
            r"(todos|todas)\s+(los|las)\s+(documentos|informes)"
            r")\b",
            f,
        )
    )


def _adjusted_embedding_score(chunk: RetrievedChunk, *, lex_ctx: str) -> float:
    """Combina embedding con solapamiento de título y cuerpo bajo lex_ctx."""

    t_ov = lexical_overlap_count(lex_ctx, chunk.document_title)
    b_ov = lexical_overlap_count(lex_ctx, chunk.text)
    b_capped = min(b_ov, 14)
    return min(
        1.0,
        chunk.score
        + _DOC_TITLE_LEX_WEIGHT * t_ov
        + _TEXT_BODY_LEX_WEIGHT * b_capped,
    )


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
            answer=MSG_UNAUTHORIZED,
            citations=[],
            policy_reasons=list(decision.reasons),
            retrieved=0,
            top_score=0.0,
            latency_ms=(time.perf_counter() - t0) * 1000,
            tokens={"prompt": 0, "completion": 0},
        )
        _persist_query_log(db, principal=principal, query=query, result=result)
        return result

    if looks_like_other_tenant_probe(query, principal.tenant_slug):
        result = QueryResult(
            request_id=request_id,
            answered=False,
            answer=MSG_OTHER_TENANT,
            citations=[],
            policy_reasons=list(decision.reasons) + ["probable_other_tenant_marker"],
            retrieved=0,
            top_score=0.0,
            latency_ms=(time.perf_counter() - t0) * 1000,
            tokens={"prompt": 0, "completion": 0},
        )
        _persist_query_log(db, principal=principal, query=query, result=result)
        return result

    if looks_like_document_catalog_query(query):
        org = get_tenant_display_name(principal.tenant_slug)
        rows = fetch_accessible_documents_catalog(db, principal)
        user_inv = build_admin_inventory_user_message(org, query, rows)
        logger.info(
            "rag.llm.invoke",
            request_id=request_id,
            route="document_catalog",
            doc_rows=len(rows),
        )
        gen = rag_generator.get_llm_client().generate(
            system=rag_generator.ADMIN_INVENTORY_SYSTEM_PROMPT,
            user=user_inv,
        )
        llm_refused = gen.answer.strip().upper() == "NO_ANSWER"
        answer_text = MSG_NO_CORPUS_MATCH if llm_refused else gen.answer.strip()
        result = QueryResult(
            request_id=request_id,
            answered=not llm_refused,
            answer=answer_text,
            citations=[],
            policy_reasons=list(decision.reasons) + ["document_catalog"],
            retrieved=0,
            top_score=0.0,
            latency_ms=(time.perf_counter() - t0) * 1000,
            tokens={
                "prompt": gen.prompt_tokens_approx,
                "completion": gen.completion_tokens_approx,
            },
        )
        _persist_query_log(db, principal=principal, query=query, result=result)
        return result

    conv = conversation_reply(principal, query)
    if conv is not None:
        result = QueryResult(
            request_id=request_id,
            answered=True,
            answer=conv,
            citations=[],
            policy_reasons=list(decision.reasons),
            retrieved=0,
            top_score=0.0,
            latency_ms=(time.perf_counter() - t0) * 1000,
            tokens={"prompt": 0, "completion": 0},
        )
        _persist_query_log(db, principal=principal, query=query, result=result)
        return result

    retrieved = retrieve(db, query=query, policy=decision, top_k=settings.retrieval_top_k)
    title_extra = retrieve_chunks_by_title_match(
        db, principal=principal, query=query, policy=decision
    )
    title_match_ids = {c.chunk_id for c in title_extra}
    if title_extra:
        seen_t = {c.chunk_id for c in retrieved}
        for c in title_extra:
            if c.chunk_id not in seen_t:
                seen_t.add(c.chunk_id)
                retrieved.append(c)
    probe_k = max(60, settings.retrieval_top_k * 4)
    tenant_wide = retrieve_within_tenant_ignore_abac(db, query=query, top_k=probe_k)

    filtered_ids = {c.chunk_id for c in retrieved}
    hid_better_abac = False
    hidden_score = 0.0
    for cand in tenant_wide:
        if cand.chunk_id in filtered_ids:
            continue
        rel = lexical_relatedness_score(query, cand.text)
        if rel >= 4:
            hid_better_abac = True
            hidden_score = cand.score
            break
        if rel >= 3 and cand.score >= settings.no_answer_threshold:
            hid_better_abac = True
            hidden_score = cand.score
            break
    if hid_better_abac:
        result = QueryResult(
            request_id=request_id,
            answered=False,
            answer=MSG_UNAUTHORIZED,
            citations=[],
            policy_reasons=list(decision.reasons)
                + ["blocked_chunk_lexically_related_outside_visible_set"],
            retrieved=len(retrieved),
            top_score=hidden_score,
            latency_ms=(time.perf_counter() - t0) * 1000,
            tokens={"prompt": 0, "completion": 0},
        )
        _persist_query_log(db, principal=principal, query=query, result=result)
        return result

    if not retrieved:
        result = QueryResult(
            request_id=request_id,
            answered=False,
            answer=MSG_NO_CORPUS_MATCH,
            citations=[],
            policy_reasons=list(decision.reasons)
            + (
                ["sin_candidatos_semanticos_en_tenant"]
                if not tenant_wide
                else ["sin_fragmentos_autorizados_por_encima_del_umbral"]
            ),
            retrieved=0,
            top_score=tenant_wide[0].score if tenant_wide else 0.0,
            latency_ms=(time.perf_counter() - t0) * 1000,
            tokens={"prompt": 0, "completion": 0},
        )
        _persist_query_log(db, principal=principal, query=query, result=result)
        return result

    org_disp = get_tenant_display_name(principal.tenant_slug)
    vague_agg = _vague_aggregate_summary_query(query)
    lex_ctx = query.strip()
    if vague_agg:
        lex_ctx = f"{query.strip()} {org_disp} contenido sintesis documentacion".strip()
    ambiguous_multi = vague_agg and len({c.document_id for c in retrieved}) >= 2

    reranker = get_reranker()
    pool_k = min(
        len(retrieved),
        max(settings.rerank_top_k * 4, 24),
    )
    reranked_pool = reranker.rerank(query, retrieved, pool_k)
    top, title_in_top = _merge_rerank_respecting_title_hits(
        retrieved=retrieved,
        reranked_pool=reranked_pool,
        title_match_ids=title_match_ids,
        lex_ctx=lex_ctx,
        top_k=settings.rerank_top_k,
    )

    top_raw_score = top[0].score if top else 0.0
    gate_score = (
        max((_adjusted_embedding_score(c, lex_ctx=lex_ctx) for c in top), default=0.0)
        if top
        else 0.0
    )
    aggregate_gate_relief = bool(ambiguous_multi and top and top_raw_score >= 1e-5)
    title_anchor_relief = title_in_top

    if not top or (
        gate_score < settings.no_answer_threshold
        and not aggregate_gate_relief
        and not title_anchor_relief
    ):
        result = QueryResult(
            request_id=request_id,
            answered=False,
            answer=MSG_NO_CORPUS_MATCH,
            citations=[],
            policy_reasons=list(decision.reasons)
            + [
                f"gate_score={gate_score:.3f} (emb={top_raw_score:.3f}) < umbral={settings.no_answer_threshold}"
            ],
            retrieved=len(retrieved),
            top_score=gate_score,
            latency_ms=(time.perf_counter() - t0) * 1000,
            tokens={"prompt": 0, "completion": 0},
        )
        _persist_query_log(db, principal=principal, query=query, result=result)
        return result

    user_prompt = rag_generator.build_prompt(query, top)
    logger.info(
        "rag.llm.invoke",
        request_id=request_id,
        route="grounded_rag",
        prompt_chars=len(user_prompt),
        chunks=len(top),
        gate_score=round(gate_score, 4),
    )
    gen = rag_generator.get_llm_client().generate(
        system=rag_generator.SYSTEM_PROMPT, user=user_prompt
    )

    llm_refused = gen.answer.strip().upper() == "NO_ANSWER"
    answer_text = MSG_NO_CORPUS_MATCH if llm_refused else gen.answer.strip()
    answered = not llm_refused
    citations = [] if llm_refused else [_to_citation(i + 1, c) for i, c in enumerate(top)]

    result = QueryResult(
        request_id=request_id,
        answered=answered,
        answer=answer_text,
        citations=citations if answered else [],
        policy_reasons=list(decision.reasons),
        retrieved=len(retrieved),
        top_score=gate_score,
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
        top_score=round(gate_score, 3),
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
