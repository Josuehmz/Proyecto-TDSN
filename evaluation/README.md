# Evaluación del prototipo

Esta carpeta contiene los artefactos necesarios para la **evaluación cuantitativa
y cualitativa** del prototipo, exigida por el artículo y por el requisito del
workshop de arquitectura empresarial y transformación digital.

## Estructura

- `test_questions.json` — Conjunto de preguntas clasificadas por tenant,
  categoría (factual / síntesis / multi-documento / sin respuesta) y con
  respuesta esperada (*ground truth*).
- `scripts/run_evaluation.py` — Ejecuta las preguntas contra el backend con el
  token correspondiente, recoge respuestas y métricas operativas.
- `scripts/ragas_eval.py` — Aplica RAGAS sobre el `dataset` generado para
  medir *faithfulness*, *answer relevancy* y *context precision/recall*.
- `scripts/security_eval.py` — Ejecuta las baterías de red-team y cross-tenant
  descritas en la Sección 7 del artículo. Cualquier fuga invalida la entrega.
- `results/` — Reportes JSON/CSV (ignorados por git salvo `.gitkeep`).

## Métricas reportadas

| Métrica                       | Umbral objetivo            | Origen          |
|------------------------------|----------------------------|-----------------|
| Faithfulness                 | ≥ 0.70                     | RAGAS           |
| Answer relevancy             | ≥ 0.70                     | RAGAS           |
| Context precision            | ≥ 0.60                     | RAGAS           |
| Context recall               | ≥ 0.60                     | RAGAS           |
| Tasa de bloqueo cross-tenant | 100 %                      | security_eval   |
| Tasa de deny correctos (ABAC)| 100 %                      | security_eval   |
| P50 latencia                 | ≤ 1.5 s (cloud)            | run_evaluation  |
| P95 latencia                 | ≤ 4.0 s (cloud)            | run_evaluation  |
| Tasa de `no-answer` correcto | ≥ 90 %                     | run_evaluation  |

> En el prototipo local las metas de latencia son orientativas; los valores
> reales se miden y reportan en la sección de resultados del artículo.

## Cómo ejecutar

```bash
docker compose up -d
# Esperar a que backend/postgres estén saludables
python evaluation/scripts/run_evaluation.py
python evaluation/scripts/ragas_eval.py   # requiere OPENAI_API_KEY
python evaluation/scripts/security_eval.py
```
