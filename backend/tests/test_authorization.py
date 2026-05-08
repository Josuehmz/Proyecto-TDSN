from __future__ import annotations


def _query(client, token: str, q: str) -> dict:
    resp = client.post(
        "/query",
        json={"query": q},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_intern_cannot_access_confidential_contract(client, acme_intern_token):
    data = _query(client, acme_intern_token, "¿Cuál es el monto del contrato con Orion Dynamics?")
    txt = (data["answer"] + " " + " ".join(c["snippet"] for c in data["citations"])).upper()
    assert "42.000.000" not in txt
    assert "ORION" not in txt
    assert data["answered"] is False
    assert "no tengo" in data["answer"].lower()
    assert "autorizado" not in data["answer"].lower()


def test_legal_can_access_confidential_contract(client, acme_legal_token):
    data = _query(
        client,
        acme_legal_token,
        "¿Cuál es la cláusula de rescisión del contrato con Orion Dynamics?",
    )
    txt = (data["answer"] + " " + " ".join(c["snippet"] for c in data["citations"])).upper()
    assert data["retrieved"] > 0
    assert "SIGMA-9" in txt or data["answered"] is True


def test_finance_can_access_globex_financials(client, globex_finance_token):
    data = _query(
        client,
        globex_finance_token,
        "¿Cuál es la proyección de ingresos 2026 y el EBITDA?",
    )
    txt = (data["answer"] + " " + " ".join(c["snippet"] for c in data["citations"])).upper()
    assert "180.000.000" in txt or "EBITDA" in txt


def test_globex_employee_cannot_access_financials(client, globex_employee_token):
    data = _query(
        client,
        globex_employee_token,
        "¿Cuánto se reserva para adquirir TITANIUM-WORKS?",
    )
    txt = (data["answer"] + " " + " ".join(c["snippet"] for c in data["citations"])).upper()
    assert "12.000.000" not in txt
    assert data["answered"] is False
    assert "no tengo" in data["answer"].lower()
    assert "autorizado" not in data["answer"].lower()
