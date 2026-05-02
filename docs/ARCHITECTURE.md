# Arquitectura del prototipo — trazabilidad con el artículo

Esta nota traza cada decisión del artículo a su implementación concreta en
el código, para que el lector (y el evaluador del workshop) pueda verificar
rápidamente que el prototipo cumple lo prometido.

## Mapeo Sección del artículo ↔ módulo del código

| Sección del artículo                                        | Módulo / archivo                                                |
| ----------------------------------------------------------- | --------------------------------------------------------------- |
| §2.1 P1 Aislamiento                                         | `app/db/session.py` (`search_path`), `app/tenancy/context.py`   |
| §2.1 P2 Autorización                                        | `app/policy/engine.py`, `app/rag/retriever.py`                  |
| §2.1 P3 Grounding                                           | `app/rag/orchestrator.py` (umbral `no-answer` + citas)          |
| §2.1 P4 Latencia                                            | `app/main.py` (header `X-Response-Time-Ms`), `tests/test_latency.py` |
| §2.2 Modelo de amenazas                                     | `docs/SECURITY.md`, tests `test_red_team.py`                    |
| §3 SOTA                                                     | Comentarios en módulos RAG, `README.md` §2                      |
| §4 Arquitectura cloud                                       | README §2 (mapeo AWS ↔ local)                                   |
| §5.1 Aislamiento de índices (Decisión 1)                    | Schema por tenant (`tenant_<slug>`)                             |
| §5.2 Motor vectorial (Decisión 2)                           | pgvector (Tier A del prototipo)                                 |
| §5.3 Chunking (Decisión 3)                                  | `app/rag/chunker.py` (384/64, top-k 20→5)                       |
| §5.4 Control de acceso (Decisión 4)                         | `app/policy/engine.py` (ABAC *pre*)                             |
| §5.5 Ubicación del LLM (Decisión 5)                         | `app/rag/generator.py` (`mock` / `openai`)                      |
| §6 Pruebas (Tabla 6)                                        | `backend/tests/test_*.py`                                       |
| §7 Plan de evaluación                                       | `evaluation/`                                                   |

## Flujos detallados

### Consulta (online) — Sección 4.4 del artículo

1. **AuthN** JWT (HS256) validado en `deps.get_principal` — en la nube se
   reemplaza por OIDC + JWKS de Cognito sin cambiar el contrato.
2. **Rate limit** y contexto de auditoría — middleware de `main.py`
   (`X-Request-Id`, contextvars de `structlog`).
3. **Policy Engine** (`policy/engine.py`):
   - Rechaza principales sin roles.
   - Traduce atributos a *obligations* SQL que filtran `chunks` por
     `required_clearance`, `allowed_roles` y `allowed_departments`.
4. **Búsqueda vectorial** (`rag/retriever.py`) — `pgvector` con
   `cosine_distance` + filtros ABAC aplicados **antes** del ORDER BY.
5. **Reranker** opcional (`rag/reranker.py`) — cross-encoder MS-MARCO.
6. **Umbral no-answer** (`rag/orchestrator.py`) — evita alucinaciones
   cuando no hay contexto suficiente.
7. **Generación** (`rag/generator.py`) — `mock` determinista o proveedor
   real. El `SYSTEM_PROMPT` está aislado y explícitamente prohíbe salir
   del contexto.
8. **Auditoría** (`audit/logger.py` + `QueryLog`) — doble registro: uno en
   `platform.audit_events` (global) y otro en `query_log` (por tenant).

### Ingesta — Sección 4.4 del artículo

Flujo síncrono equivalente al asíncrono S3→SQS→Workers de producción:

```
upload → ingest_document
          ├─ extract (txt / pdf / docx / html)
          ├─ chunk (tiktoken, 384/64)
          ├─ embed (sentence-transformers / openai)
          └─ persist (documents + chunks con ACL denormalizada)
```

La ACL se denormaliza en `chunks` para que el filtro ABAC pueda aplicarse
directamente durante la búsqueda vectorial, sin un `JOIN` adicional que
podría abrir la ventana a un *bug* de filtrado.

## Capas de aislamiento ya implementadas (Tier A)

1. **Schema por tenant** → `CREATE SCHEMA tenant_<slug>` + `SET search_path`.
2. **Slug validado** con expresión regular (anti-inyección DDL).
3. **Tests automatizados** que prueban el *happy path* y el *adversarial*
   (prompt injection).
4. **Auditoría transversal** por `tenant_slug` + `request_id`.

Los Tiers B (BYOK con KMS por tenant) y C (silo por cuenta AWS) están
descritos en §4.3 del artículo y se abordan en
[`docs/NEXT_STEPS.md`](NEXT_STEPS.md).
