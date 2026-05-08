from __future__ import annotations


def _query(client, token: str, q: str) -> dict:
    resp = client.post(
        "/query",
        json={"query": q},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_supported_question_is_answered_with_citations(client, acme_admin_token):
    data = _query(client, acme_admin_token, "¿Dónde está la oficina principal de Acme?")
    assert data["answered"] is True
    assert len(data["citations"]) >= 1
    for citation in data["citations"]:
        assert "chunk_id" in citation
        assert "document_title" in citation
        assert citation["score"] >= 0.0


def test_unsupported_question_returns_no_answer(client, acme_admin_token):
    data = _query(
        client,
        acme_admin_token,
        (
            "zzUniqueNoCorpMatch8391 — ¿Cuál es la temperatura promedio del "
            "océano Pacífico en el año 1873 según registros NOAA inexistentes?"
        ),
    )
    assert data["answered"] is False
    assert data["citations"] == []
    assert "NO_ANSWER" not in data["answer"]
    assert "No encuentro" in data["answer"] or "no encuentro" in data["answer"]


def test_citations_are_present_when_answered(client, acme_legal_token):
    data = _query(client, acme_legal_token, "Cláusula SIGMA-9")
    if data["answered"]:
        assert len(data["citations"]) >= 1
