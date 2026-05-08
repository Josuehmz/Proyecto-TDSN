from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class LoginRequest(BaseModel):
    tenant: str = Field(..., description="Slug del tenant (ej. 'acme').")
    # No usamos EmailStr: email-validator rechaza TLD reservados (.test) y el
    # seed usa admin@acme.test, etc. para el prototipo.
    email: str = Field(..., min_length=3, max_length=200)
    password: str = Field(..., min_length=8)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        s = v.strip().lower()
        if s.count("@") != 1:
            raise ValueError("email inválido")
        local, domain = s.split("@", 1)
        if not local or not domain or "." not in domain:
            raise ValueError("email inválido")
        return s


class PrincipalOut(BaseModel):
    user_id: UUID
    tenant: str
    email: str
    roles: list[str]
    clearance: str
    departments: list[str]


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_min: int
    principal: "PrincipalOut"


class DocumentOut(BaseModel):
    id: UUID
    title: str
    source: str
    required_clearance: str
    allowed_roles: list[str]
    allowed_departments: list[str]
    byte_size: int
    chunk_count: int | None = None


class DocumentListOut(BaseModel):
    documents: list[DocumentOut]


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=4000)


class CitationOut(BaseModel):
    index: int
    chunk_id: UUID
    document_id: UUID
    document_title: str
    ordinal: int
    score: float
    snippet: str


class QueryResponse(BaseModel):
    request_id: str
    answered: bool
    answer: str
    citations: list[CitationOut]
    policy_reasons: list[str]
    retrieved: int
    top_score: float
    latency_ms: float
    tokens: dict[str, int]


TokenResponse.model_rebuild()
