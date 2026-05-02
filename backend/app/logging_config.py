from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from typing import Any

import structlog

from app.config import get_settings

_tenant_id_ctx: ContextVar[str | None] = ContextVar("tenant_id", default=None)
_request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
_user_id_ctx: ContextVar[str | None] = ContextVar("user_id", default=None)


def bind_request_context(
    *,
    tenant_id: str | None = None,
    request_id: str | None = None,
    user_id: str | None = None,
) -> None:
    if tenant_id is not None:
        _tenant_id_ctx.set(tenant_id)
    if request_id is not None:
        _request_id_ctx.set(request_id)
    if user_id is not None:
        _user_id_ctx.set(user_id)


def _add_request_context(
    _logger: Any, _name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    if (tid := _tenant_id_ctx.get()) is not None:
        event_dict.setdefault("tenant_id", tid)
    if (rid := _request_id_ctx.get()) is not None:
        event_dict.setdefault("request_id", rid)
    if (uid := _user_id_ctx.get()) is not None:
        event_dict.setdefault("user_id", uid)
    return event_dict


def configure_logging() -> None:
    settings = get_settings()
    level = logging.getLevelName(settings.app_log_level.upper())

    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)

    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _add_request_context,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
