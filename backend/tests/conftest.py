from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session", autouse=True)
def _prepare_env() -> None:
    os.environ.setdefault("LLM_PROVIDER", "mock")
    os.environ.setdefault("RERANKER_ENABLED", "false")
    os.environ.setdefault("NO_ANSWER_THRESHOLD", "0.1")


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
