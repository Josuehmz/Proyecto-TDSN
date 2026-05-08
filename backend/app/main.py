from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import auth, documents, health, query
from app.config import get_settings
from app.logging_config import bind_request_context, configure_logging, get_logger
from app.rag import generator as rag_generator

configure_logging()
logger = get_logger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        cfg = get_settings()
        cli = rag_generator.get_llm_client()
        logger.info(
            "app.llm_startup",
            llm_provider=cfg.llm_provider,
            llm_impl=type(cli).__name__,
        )
        yield

    app = FastAPI(
        title="Plataforma RAG Multi-Tenant",
        description=(
            "Prototipo que valida los tres riesgos críticos del artículo: "
            "(V1) aislamiento por tenant, (V2) autorización ABAC pre-retrieval, "
            "(V3) grounding con citas."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def correlation_and_timing(request: Request, call_next):
        request_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex[:16]
        request.state.request_id = request_id
        bind_request_context(request_id=request_id)
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-Id"] = request_id
        response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.1f}"
        logger.info(
            "http.request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            elapsed_ms=round(elapsed_ms, 1),
        )
        return response

    @app.exception_handler(Exception)
    async def unhandled_error(_request: Request, exc: Exception) -> JSONResponse:
        logger.error("http.unhandled_error", error=str(exc))
        return JSONResponse(status_code=500, content={"detail": "internal_error"})

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(documents.router)
    app.include_router(query.router)

    return app


app = create_app()
