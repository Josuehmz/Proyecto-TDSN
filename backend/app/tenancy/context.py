from __future__ import annotations

import re

_TENANT_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_]{1,62}$")
_RESERVED = {"public", "platform", "pg_catalog", "information_schema"}


class InvalidTenantSlug(ValueError):
    pass


def validate_tenant_slug(slug: str) -> str:
    slug = (slug or "").strip().lower()
    if not _TENANT_SLUG_RE.match(slug):
        raise InvalidTenantSlug(
            f"Slug de tenant inválido: {slug!r}. Debe coincidir con "
            "^[a-z0-9][a-z0-9_]{1,62}$."
        )
    if slug in _RESERVED:
        raise InvalidTenantSlug(f"Slug reservado por el sistema: {slug!r}")
    return slug


def tenant_schema(slug: str) -> str:
    return f"tenant_{validate_tenant_slug(slug)}"
