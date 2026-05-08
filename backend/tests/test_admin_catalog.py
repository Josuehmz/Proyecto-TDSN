from __future__ import annotations


def _query(client, token: str, q: str) -> dict:
    resp = client.post(
        "/query",
        json={"query": q},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_admin_document_inventory_via_query(client, acme_admin_token):
    data = _query(client, acme_admin_token, "¿Qué documentos tienes?")
    assert data["answered"] is True
    assert "document_catalog" in data["policy_reasons"]
    assert data["retrieved"] == 0
    assert "manual de onboarding acme" in data["answer"].lower()
    assert "política de gastos" in data["answer"].lower() or "politica de gastos" in data["answer"].lower()
    assert "orion" not in data["answer"].lower()


def test_listado_todos_los_documentos_triggers_catalog(client, acme_admin_token):
    data = _query(client, acme_admin_token, "Dame un listado de todos los documentos")
    assert data["answered"] is True
    assert "document_catalog" in data["policy_reasons"]


def test_any_user_lists_only_accessible_documents(client, acme_intern_token):
    """Cualquier rol: inventario filtrado por ABAC (no solo admin)."""
    data = _query(client, acme_intern_token, "¿Qué documentos tienes?")
    assert data["answered"] is True
    assert "document_catalog" in data["policy_reasons"]
    assert "manual de onboarding" in data["answer"].lower()
    assert "orion" not in data["answer"].lower()
    assert "contrato" not in data["answer"].lower()


def test_partial_document_title_finds_content(client, acme_intern_token):
    data = _query(client, acme_intern_token, "El calendario corporativo")
    assert data["answered"] is True
    blob = (data["answer"] + " " + " ".join(c["snippet"] for c in data["citations"])).lower()
    assert "diciembre" in blob or "noviembre" in blob or "asamblea" in blob


def test_generic_wording_finds_manual_by_title_globex(client, globex_employee_token):
    """Pregunta genérica alineada al título; el rerank por cuerpo puede fallar sin ancla por título."""
    data = _query(
        client,
        globex_employee_token,
        "¿De qué trata el manual operativo?",
    )
    assert data["answered"] is True
    blob = (data["answer"] + " " + " ".join(c["snippet"] for c in data["citations"])).lower()
    assert "helios" in blob or "basilisk" in blob or "recarga" in blob or "bater" in blob


def test_summary_named_document_even_if_embedding_weak(client, acme_admin_token):
    """Nombre del documento en la pregunta debe superar embeddings débiles (mock/demo)."""
    data = _query(
        client,
        acme_admin_token,
        "Dame un resumen del Manual de onboarding Acme.",
    )
    assert data["answered"] is True
    blob = (data["answer"] + " " + " ".join(c["snippet"] for c in data["citations"])).upper()
    assert "ACME" in blob or "MISI" in blob


def test_vague_dual_doc_summary_globex(client, globex_admin_token):
    """Resumen agregado sin nombres explícitos (usa org + alivio de gate)."""
    data = _query(client, globex_admin_token, "Dame un resumen de ambos documentos")
    assert data["answered"] is True
    blob = (data["answer"] + " " + " ".join(c["snippet"] for c in data["citations"])).lower()
    assert "helios" in blob or "nebula" in blob or "basilisk" in blob or "catalogo" in blob
