from __future__ import annotations

import os

# Fuerza valores de test antes de cargar Settings / modelos (Docker puede inyectar MOCK del .env).
os.environ["LLM_PROVIDER"] = "groq"
os.environ["GROQ_API_KEY"] = "pytest-stub-no-remote-calls"
os.environ["RERANKER_ENABLED"] = "false"
os.environ["NO_ANSWER_THRESHOLD"] = "0.1"

from app.config import get_settings

get_settings.cache_clear()

import app.rag.generator as rag_generator  # noqa: E402
from tests.llm_stub import TEST_PIPELINE_LLM_STUB  # noqa: E402

rag_generator.get_llm_client = lambda: TEST_PIPELINE_LLM_STUB

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="session")
def app():
    from app.main import create_app
    from app.scripts.init_db import ensure_all_tenants, ensure_platform
    from app.scripts.seed_tenants import seed_demo

    ensure_platform()
    ensure_all_tenants()
    seed_demo()
    return create_app()


@pytest.fixture()
def client(app):
    with TestClient(app) as c:
        yield c


def _login(client: TestClient, tenant: str, email: str, password: str) -> str:
    resp = client.post(
        "/auth/login",
        json={"tenant": tenant, "email": email, "password": password},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture()
def acme_admin_token(client) -> str:
    return _login(client, "acme", "admin@acme.test", "Acme_Admin_2026!")


@pytest.fixture()
def acme_legal_token(client) -> str:
    return _login(client, "acme", "legal@acme.test", "Acme_Legal_2026!")


@pytest.fixture()
def acme_intern_token(client) -> str:
    return _login(client, "acme", "intern@acme.test", "Acme_Intern_2026!")


@pytest.fixture()
def globex_admin_token(client) -> str:
    return _login(client, "globex", "admin@globex.test", "Globex_Admin_2026!")


@pytest.fixture()
def globex_finance_token(client) -> str:
    return _login(client, "globex", "finance@globex.test", "Globex_Fin_2026!")


@pytest.fixture()
def globex_employee_token(client) -> str:
    return _login(client, "globex", "employee@globex.test", "Globex_Emp_2026!")
