from __future__ import annotations


def _query(client, token: str, q: str) -> dict:
    resp = client.post(
        "/query",
        json={"query": q},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_light_greeting_returns_conversation(client, acme_admin_token):
    data = _query(client, acme_admin_token, "Hola")
    assert data["answered"] is True
    assert data["citations"] == []
    assert "asistente" in data["answer"].lower() or "hola" in data["answer"].lower()


def test_identity_question_uses_principal_not_rag(client, acme_admin_token):
    data = _query(client, acme_admin_token, "¿A qué empresa pertenezco?")
    assert data["answered"] is True
    assert data["citations"] == []
    assert "acme" in data["answer"].lower()
