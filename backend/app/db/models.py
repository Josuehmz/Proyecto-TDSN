from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.config import get_settings


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PlatformBase(DeclarativeBase):
    __table_args__ = {"schema": "platform"}


class Tenant(PlatformBase):
    __tablename__ = "tenants"
    __table_args__ = {"schema": "platform"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    tier: Mapped[str] = mapped_column(String(16), default="A", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    users: Mapped[list["User"]] = relationship(back_populates="tenant", cascade="all, delete")


class User(PlatformBase):
    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_tenant_email", "tenant_id", "email", unique=True),
        {"schema": "platform"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("platform.tenants.id", ondelete="CASCADE"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(200), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    roles: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    clearance: Mapped[str] = mapped_column(String(32), default="public", nullable=False)
    departments: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    tenant: Mapped[Tenant] = relationship(back_populates="users")


class AuditEvent(PlatformBase):
    __tablename__ = "audit_events"
    __table_args__ = {"schema": "platform"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    tenant_slug: Mapped[str | None] = mapped_column(String(64), index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    request_id: Mapped[str | None] = mapped_column(String(64), index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    decision: Mapped[str | None] = mapped_column(String(32))
    detail: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class TenantBase(DeclarativeBase):
    """Tablas por tenant; el schema se resuelve vía search_path en cada sesión."""


class Document(TenantBase):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(400), nullable=False)
    source: Mapped[str] = mapped_column(String(400), default="upload")
    required_clearance: Mapped[str] = mapped_column(String(32), default="public", nullable=False)
    allowed_roles: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    allowed_departments: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), default="text/plain")
    byte_size: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    chunks: Mapped[list["Chunk"]] = relationship(back_populates="document", cascade="all, delete")


class Chunk(TenantBase):
    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    # ACL denormalizada: evita JOIN durante el filtrado ABAC del retriever.
    required_clearance: Mapped[str] = mapped_column(String(32), default="public", nullable=False)
    allowed_roles: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    allowed_departments: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    embedding = mapped_column(Vector(get_settings().embeddings_dim))

    document: Mapped[Document] = relationship(back_populates="chunks")


class QueryLog(TenantBase):
    __tablename__ = "query_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    request_id: Mapped[str | None] = mapped_column(String(64), index=True)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    retrieved: Mapped[int] = mapped_column(Integer, default=0)
    answered: Mapped[bool] = mapped_column(Boolean, default=False)
    top_score: Mapped[float] = mapped_column(Float, default=0.0)
    citations: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
