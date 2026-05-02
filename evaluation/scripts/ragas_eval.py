from __future__ import annotations

import glob
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = ROOT / "evaluation" / "results"


def _latest_run() -> Path:
    files = sorted(glob.glob(str(RESULTS_DIR / "run_*.json")))
    if not files:
        raise SystemExit("No hay ejecuciones previas. Corre run_evaluation.py primero.")
    return Path(files[-1])


def _to_ragas_dataset(items: list[dict]):
    from datasets import Dataset

    questions, answers, contexts, gts = [], [], [], []
    for it in items:
        if not it.get("expected_answered", False):
            continue
        questions.append(it["query"])
        answers.append(it["answer"])
        contexts.append([c["snippet"] for c in it.get("citations", [])] or [""])
        gts.append(it["ground_truth"])

    return Dataset.from_dict(
        {
            "question": questions,
            "answer": answers,
            "contexts": contexts,
            "ground_truth": gts,
        }
    )


def run() -> int:
    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("Falta OPENAI_API_KEY en el entorno (requerido por RAGAS).")

    latest = _latest_run()
    items = json.loads(latest.read_text(encoding="utf-8"))
    dataset = _to_ragas_dataset(items)

    from ragas import evaluate
    from ragas.metrics import (
        answer_relevancy,
        context_precision,
        context_recall,
        faithfulness,
    )

    result = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
    )

    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    out = RESULTS_DIR / f"ragas_{ts}.json"
    out.write_text(
        json.dumps({k: float(v) for k, v in result.items()}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps({k: float(v) for k, v in result.items()}, indent=2, ensure_ascii=False))
    print(f"\nRAGAS => {out}")
    return 0


if __name__ == "__main__":
    sys.exit(run())
