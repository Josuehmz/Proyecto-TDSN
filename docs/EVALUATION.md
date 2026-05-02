# Protocolo de evaluación reproducible

Este documento describe el **experimento reproducible** con el que se
sustentarán las secciones *Resultados* y *Evaluación* del artículo y la
presentación del workshop.

## Objetivos

1. **Cuantificar** la calidad del pipeline RAG (faithfulness, answer
   relevancy, context precision/recall).
2. **Cuantificar** las garantías de seguridad (tasa de bloqueo
   cross-tenant y tasa de *deny* correcto del ABAC).
3. **Cuantificar** los atributos operativos: P50, P95, throughput, costo
   por consulta (tokens × precio).
4. **Cualificar** mediante muestreo manual y un *LLM-juez* calibrado, para
   mitigar los sesgos de RAGAS detectados por ARES.

## Hipótesis

- H1: *faithfulness* ≥ 0.70 con el pipeline default (384/64, top-k 20→5,
  reranker on).
- H2: **100 %** de bloqueo en las baterías cross-tenant y red-team.
- H3: el modo `NO_ANSWER` activa correctamente en ≥ 90 % de las preguntas
  etiquetadas como *sin-soporte*.
- H4: P50 ≤ 1.5 s y P95 ≤ 4 s *en la arquitectura cloud*; en el prototipo
  local se reportan sin comparación directa al SLO.

## Diseño experimental

### Variables independientes (ablation)

| Variable           | Valores                     |
| ------------------ | --------------------------- |
| `CHUNK_SIZE_TOKENS`| 256, 384, 512               |
| `CHUNK_OVERLAP_TOKENS` | 0, 64, 128              |
| `RETRIEVAL_TOP_K`  | 5, 10, 20                   |
| `RERANKER_ENABLED` | true, false                 |
| `LLM_PROVIDER`     | mock, openai (gpt-4o-mini)  |

Cada combinación se ejecuta sobre `evaluation/test_questions.json`
(30–50 preguntas por tenant, distribuidas en *factuales*, *síntesis*,
*multi-documento*, *denegadas* y *no-answer*).

### Variables dependientes

- RAGAS: `faithfulness`, `answer_relevancy`, `context_precision`,
  `context_recall`.
- Seguridad: `block_rate` cross-tenant, `deny_rate` ABAC.
- Operación: P50/P95/avg ms, `pct_answered`, `pct_no_answer_correct`,
  tokens promedio (cuando `LLM_PROVIDER=openai`).

## Procedimiento

1. `docker compose up --build` y espera a `readyz = ready`.
2. `python evaluation/scripts/run_evaluation.py` — genera
   `results/run_<ts>.json` y `results/summary_<ts>.json`.
3. `python evaluation/scripts/security_eval.py` — exit-code ≠ 0 ⇒ falla.
4. Si `OPENAI_API_KEY` está disponible:
   `python evaluation/scripts/ragas_eval.py` — produce
   `results/ragas_<ts>.json`.
5. Para cada variación del grid: ajusta variables en `.env`, reinicia el
   backend (`docker compose restart backend`), repite pasos 2–4.

## Reporte

Los resultados se consolidan en una tabla resumen (artículo) y en gráficos
`boxplot` por variable. La selección de configuración final para producción
se justifica con la curva de Pareto *calidad vs. costo* a partir de los
tokens consumidos por consulta y la latencia P95.

## Muestreo manual (cualitativo)

Para mitigar el sesgo del LLM-juez (Sección 8 del artículo), un revisor
humano etiqueta 10 respuestas aleatorias por variación:

- **Correcta** (cita soporta la afirmación).
- **Incorrecta** (alucinación detectada).
- **Parcial** (cubre solo parte de la pregunta).

Se compara el etiquetado humano con las puntuaciones de `faithfulness` y
`answer_relevancy` para reportar la *agreement* (Cohen κ).
