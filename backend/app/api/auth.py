from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import LoginRequest, PrincipalOut, TokenResponse
from app.audit.logger import audit
from app.auth.security import create_access_token, verify_password
from app.config import get_settings
from app.db.models import Tenant, User
from app.deps import get_platform_db
from app.tenancy.context import validate_tenant_slug

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    db: Annotated[Session, Depends(get_platform_db)],
) -> TokenResponse:
    try:
        tenant_slug = validate_tenant_slug(payload.tenant)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    tenant = db.execute(select(Tenant).where(Tenant.slug == tenant_slug)).scalar_one_or_none()
    if tenant is None:
        audit(
            action="auth.login",
            tenant_slug=tenant_slug,
            user_id=None,
            request_id=None,
            decision="deny",
            detail={"reason": "tenant_not_found"},
        )
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")

    user = db.execute(
        select(User).where(User.tenant_id == tenant.id, User.email == payload.email.lower())
    ).scalar_one_or_none()

    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        audit(
            action="auth.login",
            tenant_slug=tenant_slug,
            user_id=user.id if user else None,
            request_id=None,
            decision="deny",
            detail={"reason": "bad_credentials"},
        )
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")

    token = create_access_token(
        subject=str(user.id),
        tenant_slug=tenant.slug,
        roles=list(user.roles or []),
        clearance=user.clearance,
        departments=list(user.departments or []),
        extra={"email": user.email},
    )
    audit(
        action="auth.login",
        tenant_slug=tenant_slug,
        user_id=user.id,
        request_id=None,
        decision="allow",
        detail={"email": user.email},
    )
    return TokenResponse(
        access_token=token,
        expires_in_min=get_settings().jwt_expire_min,
        principal=PrincipalOut(
            user_id=user.id,
            tenant=tenant.slug,
            email=user.email,
            roles=list(user.roles or []),
            clearance=user.clearance,
            departments=list(user.departments or []),
        ),
    )
