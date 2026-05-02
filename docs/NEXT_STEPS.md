# Plan hasta la finalización — workshop del tercer tercio

Este documento describe, partiendo del estado actual del prototipo, el
**camino explícito hasta la entrega final** (artículo + proyecto
presentados en el *workshop de arquitectura empresarial y transformación
digital*). Cumple el requisito expreso del enunciado del curso
— evaluaciones cualitativas y cuantitativas con mediciones de atributos
de calidad del prototipo.

## 0. Estado actual (qué ya quedó implementado)

- Backend FastAPI con el pipeline RAG completo (retriever filtrado, rerank,
  no-answer, generator con modo mock y OpenAI).
- Aislamiento multi-tenant via `schema-per-tenant` en Postgres/pgvector.
- Policy Engine ABAC pre-retrieval (Decisión 4 del artículo).
- Auditoría global (`platform.audit_events`) + log por tenant
  (`query_log`).
- Frontend Next.js con login y chat con citas.
- Seed de dos tenants (Acme, Globex) con usuarios y documentos que cubren
  casos público / interno / confidencial.
- Suite de tests que automatiza T1.1, T1.2, T2.1, T2.2, T3.1, T3.2, T4.1.
- `docker compose` que levanta todo en un comando.
- Carpeta `evaluation/` con banco de preguntas, corredor de pruebas,
  evaluación con RAGAS y baterías de red-team.

## 1. Fases restantes hasta la entrega

### Fase A — *Calidad de datos y corpus* (Semana 1)

Objetivo: reemplazar el corpus sintético por **documentos reales o
realistas** para que las métricas RAGAS sean representativas.

- [ ] Sustituir los tres documentos por 20–30 por tenant (políticas,
      procedimientos, artículos técnicos). Idealmente mezclar `.pdf`,
      `.docx`, `.html`.
- [ ] Revisar y enriquecer `evaluation/test_questions.json` hasta 30–50
      preguntas por tenant (Sección 7 del artículo).
- [ ] Añadir preguntas *multi-documento* (requieren unir información de
      varios fragmentos) para estresar `context_recall`.

### Fase B — *Mediciones cuantitativas iniciales* (Semana 1)

Objetivo: generar el **primer set de números** para la sección de
resultados del artículo.

- [ ] Ejecutar `run_evaluation.py` con `LLM_PROVIDER=openai` (requiere
      API key) y `RERANKER_ENABLED=true`.
- [ ] Ejecutar `ragas_eval.py` y guardar el JSON de métricas.
- [ ] Ejecutar `security_eval.py` y adjuntar el reporte.
- [ ] Llenar la *Tabla de resultados* del artículo con faithfulness,
      answer_relevancy, context_precision/recall, P50/P95, block_rate.

### Fase C — *Ablation study* (Semana 2)

Objetivo: respaldar empíricamente la Decisión 3 (384/64, top-k 20→5).

- [ ] Barrer el grid `{chunk_size, overlap, top-k, reranker}` descrito en
      `docs/EVALUATION.md`.
- [ ] Consolidar resultados en gráficos (`matplotlib`) y agregarlos al
      artículo.
- [ ] Justificar la curva de Pareto *calidad vs. costo*.

### Fase D — *Endurecimiento de seguridad* (Semana 2)

Objetivo: elevar el prototipo a un punto razonable para presentación.

- [ ] Rate limit real por tenant (hoy es global). Sugerencia:
      `slowapi` con llave `request.state.principal.tenant_slug`.
- [ ] Sanitización de documentos antes de indexar (regex anti-prompt
      injection y *zero-width chars*).
- [ ] Redacción PII antes de llamar al LLM (requisito de Decisión 5 del
      artículo). Librería sugerida: `presidio`.
- [ ] CORS restringido a la URL del frontend de producción.
- [ ] Pre-commit hook con `bandit` y `ruff`.

### Fase E — *Observabilidad y costo* (Semana 2)

- [ ] Exponer métricas Prometheus (`prometheus-fastapi-instrumentator`).
- [ ] Correlacionar `request_id` entre frontend, backend y Postgres logs.
- [ ] Dashboards básicos (Grafana o similar) con latencia, errores,
      `pct_answered`, `pct_no_answer_correct`.
- [ ] Contabilidad de tokens por tenant para el cálculo de costo por
      consulta (alimenta el cuadro de la Sección 4.5 del artículo).

### Fase F — *Despliegue cloud de demostración* (Semana 3)

Opcional pero **fuertemente recomendado** para el workshop: subir al menos
un Tier A a AWS.

- [ ] Terraform con módulos: VPC, RDS Postgres con `pgvector`, ECS Fargate
      (backend), CloudFront (frontend estático o ECS), Cognito para OIDC,
      Secrets Manager para claves, CloudWatch para logs/métricas.
- [ ] Pipeline CI/CD (GitHub Actions) que corra tests + `security_eval.py`
      en cada PR y despliegue `main` a un entorno *staging*.
- [ ] KMS con una *key* por tenant (Tier B) como prueba de concepto.

### Fase G — *Artículo final y presentación* (Semana 3)

- [ ] Integrar todos los números de las fases B y C.
- [ ] Redactar *Discusión* comparando RAGAS vs. muestreo manual (κ de
      Cohen).
- [ ] Grabar/preparar demo en vivo: login como *intern*, *legal* y
      *admin*, preguntas que muestren aislamiento y bloqueo ABAC.
- [ ] Repasar los *anti-patterns* a mencionar: filtrado post-retrieval,
      índice compartido con `tenant_id`, LLM sin proxy de PII.
- [ ] Entregar el artículo con bibliografía completa (el `.tex` ya está
      listo).

## 2. Cronograma sugerido (3 semanas efectivas)

| Semana | Entregable                                                        |
| ------ | ------------------------------------------------------------------ |
| 1      | Corpus ampliado · Banco de preguntas v1 · Primer run RAGAS         |
| 2      | Ablation completa · Seguridad reforzada · Observabilidad básica    |
| 3      | Despliegue AWS opcional · Artículo final · Ensayo de presentación  |

## 3. Riesgos del plan

1. **Dependencia de `OPENAI_API_KEY`** para RAGAS y LLM real. *Mitigación:*
   subvencionar con créditos académicos o reemplazar por un *LLM-juez*
   local (Llama-3-70B en SageMaker o Ollama).
2. **Derivas del corpus** (documentos de muestra sesgados). *Mitigación:*
   revisar proporciones de categorías y tenants.
3. **Pruebas de aislamiento falsos negativos**. *Mitigación:* ampliar la
   lista de términos exclusivos por tenant en `test_isolation.py` y
   `security_eval.py`.
4. **Tiempo de ejecución de la ablation**. *Mitigación:* correr en paralelo
   el grid con `pytest-xdist` o GitHub Actions matrix.

## 4. Definición de *hecho* para el workshop

El proyecto se considera **listo para presentar** cuando:

1. `pytest -q` pasa 100 % en un entorno limpio.
2. `python evaluation/scripts/security_eval.py` retorna `exit-code 0` y
   `block_rate = 1.0`.
3. `faithfulness ≥ 0.70` y `context_precision ≥ 0.60` en al menos una
   configuración reportada.
4. P50 y P95 medidos y justificados (aun si el prototipo local no alcanza
   los SLO cloud, se explica la diferencia).
5. El artículo incluye el bloque *Resultados cuantitativos* y el bloque
   *Evaluación cualitativa* (muestreo manual + red-team).
6. Existe una demo en vivo reproducible paso a paso.

Al completar estos seis puntos, el equipo estará en posición de
presentar en el workshop sin riesgo técnico residual.
