from __future__ import annotations

import json
import os
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

BASE = os.environ.get("RAG_API_URL", "http://localhost:8000")
ROOT = Path(__file__).resolve().parents[2]
QUESTIONS_PATH = ROOT / "evaluation" / "test_questions.json"
RESULTS_DIR = ROOT / "evaluation" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


PASSWORDS = {
    "admin@acme.test": "Acme_Admin_2026!",
    "legal@acme.test": "Acme_Legal_2026!",
    "intern@acme.test": "Acme_Intern_2026!",
    "admin@globex.test": "Globex_Admin_2026!",
    "finance@globex.test": "Globex_Fin_2026!",
    "employee@globex.test": "Globex_Emp_2026!",
}


def _login(client: httpx.Client, tenant: str, email: str) -> str:
    resp = client.post(
        f"{BASE}/auth/login",
        json={"tenant": tenant, "email": email, "password": PASSWORDS[email]},
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def _query(client: httpx.Client, token: str, q: str) -> dict:
    resp = client.post(
        f"{BASE}/query",
        json={"query": q},
        headers={"Authorization": f"Bearer {token}"},
        timeout=120.0,
    )
    resp.raise_for_status()
    return resp.json()


def run() -> int:
    with QUESTIONS_PATH.open("r", encoding="utf-8") as fh:
        bank = json.load(fh)

    items = bank["items"]
    results: list[dict] = []
    latencies: list[float] = []
    token_cache: dict[tuple[str, str], str] = {}

    with httpx.Client() as client:
        for q in items:
            key = (q["tenant"], q["user"])
            if key not in token_cache:
                token_cache[key] = _login(client, q["tenant"], q["user"])
            token = token_cache[key]

            t0 = time.perf_counter()
            response = _query(client, token, q["query"])
            elapsed_ms = (time.perf_counter() - t0) * 1000
            latencies.append(elapsed_ms)

            results.append(
                {
                    **q,
                    "answer": response["answer"],
                    "answered": response["answered"],
                    "retrieved": response["retrieved"],
                    "top_score": response["top_score"],
                    "citations": response["citations"],
                    "latency_ms": response["latency_ms"],
                    "policy_reasons": response["policy_reasons"],
                    "client_latency_ms": elapsed_ms,
                }
            )

    latencies.sort()
    n = len(latencies)
    summary = {
        "total": n,
        "p50_ms": statistics.median(latencies) if n else 0,
        "p95_ms": latencies[int(0.95 * n) - 1] if n else 0,
        "avg_ms": statistics.mean(latencies) if n else 0,
        "pct_answered": sum(1 for r in results if r["answered"]) / n if n else 0,
        "pct_expected_answered_match": (
            sum(1 for r in results if r["answered"] == r["expected_answered"]) / n if n else 0
        ),
        "pct_no_answer_correct": (
            sum(1 for r in results if r["category"] == "no-answer" and not r["answered"]) / max(
                1, sum(1 for r in results if r["category"] == "no-answer")
            )
        ),
        "pct_denied_correct": (
            sum(
                1
                for r in results
                if r["category"] in ("denied", "cross-tenant") and not r["answered"]
            )
            / max(1, sum(1 for r in results if r["category"] in ("denied", "cross-tenant")))
        ),
    }

    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    dataset_path = RESULTS_DIR / f"run_{ts}.json"
    summary_path = RESULTS_DIR / f"summary_{ts}.json"
    dataset_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\nDataset => {dataset_path}")
    print(f"Summary => {summary_path}")
    return 0


if __name__ == "__main__":
    sys.exit(run())
