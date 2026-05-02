from __future__ import annotations

import statistics

import pytest


@pytest.mark.perf
def test_p50_p95_latency(client, acme_admin_token):
    n = 30
    latencies = []
    for _ in range(n):
        resp = client.post(
            "/query",
            json={"query": "¿Cuál es la palabra clave pública?"},
            headers={"Authorization": f"Bearer {acme_admin_token}"},
        )
        assert resp.status_code == 200
        latencies.append(resp.json()["latency_ms"])

    latencies.sort()
    p50 = statistics.median(latencies)
    p95 = latencies[int(0.95 * n) - 1]

    assert p50 < 5000, f"P50 muy alta: {p50} ms"
    assert p95 < 8000, f"P95 muy alta: {p95} ms"
