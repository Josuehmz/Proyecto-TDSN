# Plataforma Empresarial RAG Multi-Tenant

> Prototipo ejecutable del artículo *“Plataforma Empresarial RAG Multi-Tenant
> para la Gestión del Conocimiento: arquitectura cloud, aislamiento por
> inquilino, Zero Trust y evaluación”* (Mayo 2026).
>
> **Autores**: Stiven Esneider Pardo Gutiérrez · Josué David Hernández Martínez
> · Allan Steef Contreras Rodríguez.
>
> El artículo será presentado en el *workshop de arquitectura empresarial y
> transformación digital* del tercer tercio del curso. Este repositorio
> contiene el **prototipo delimitado** y los **planes de evaluación
> cualitativa y cuantitativa** (medición de atributos de calidad) exigidos
> por el requisito del workshop.

---

## 1. Qué hace este prototipo

Una plataforma *Retrieval-Augmented Generation* (RAG) multi-tenant que
valida, en un entorno ejecutable y reproducible, los **tres riesgos técnicos
críticos** que el artículo identifica en su arquitectura empresarial:

| Riesgo | Propiedad          | Dónde se valida                                         |
| ------ | ------------------ | ------------------------------------------------------- |
| **V1** | P1 · Aislamiento   | Schema por tenant + tests `test_isolation.py`           |
| **V2** | P2 · Autorización  | Policy Engine ABAC *pre-retrieval* + `test_authorization.py` |
| **V3** | P3 · Grounding     | `no-answer` por umbral + citas + RAGAS                  |

Sobre esas tres garantías se añaden la delimitación por latencia (P4) y la
auditoría correlacionable por `tenant_id` + `request_id` (RNF5 del
artículo).

## 2. Arquitectura del prototipo

Réplica del diagrama de la *Figura 3* del artículo:

```
 Usuario (tenant T1/T2)
        │
        ▼
┌─────────────────┐   ┌─────────────┐
│ Frontend Next.js│──▶│   FastAPI   │─┐
└─────────────────┘   └─────────────┘ │
                                      ▼
              ┌───────────────────────────────────────────────┐
              │          RAG Orchestrator (LangChain)          │
              │  1. AuthN/Z (JWT) ─► 2. Policy Engine (ABAC)   │
              │  3. Retrieval filtrado ─► 4. Reranker          │
              │  5. Umbral no-answer ─► 6. LLM ─► 7. Auditoría │
              └───────────────────────────────────────────────┘
                  │             │             │
                  ▼             ▼             ▼
         pgvector (schema:   LLM API     Logs + Auditoría
         tenant_<slug>)    (OpenAI/mock) (platform.audit_events)
```

Mapeo prototipo ↔ arquitectura cloud (Sección 4.2 del artículo):

| Componente cloud (AWS)                     | Equivalente local del prototipo                 |
| ------------------------------------------ | ----------------------------------------------- |
| CloudFront + WAF + Cognito + API Gateway   | Middleware FastAPI (CORS, JWT HS256, rate-limit)|
| ECS Fargate (`orchestrator`)               | Proceso Uvicorn                                 |
| OpenSearch kNN *index-per-tenant*          | Postgres + pgvector con *schema-per-tenant*     |
| DynamoDB (metadata)                        | Tablas SQL por tenant                           |
| Bedrock / OpenAI                           | `LLM_PROVIDER=openai` o `mock` (determinista)   |
| KMS                                        | Cifrado en tránsito TLS + contraseñas bcrypt    |
| CloudWatch + X-Ray                         | `structlog` JSON + `audit_events`               |
| S3 + SQS + Workers ECS (ingesta)           | Pipeline síncrono `ingest_document()`           |

## 3. Estructura del repositorio

```
.
├── README.md                    ← este archivo
├── docker-compose.yml
├── .env.example
├── infra/postgres/init.sql
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py              ← FastAPI
│   │   ├── config.py            ← pydantic-settings
│   │   ├── deps.py              ← Principal, DB por tenant
│   │   ├── logging_config.py    ← logs JSON + contexto
│   │   ├── tenancy/context.py   ← resolución de schema
│   │   ├── db/{session,models}.py
│   │   ├── auth/security.py     ← JWT + bcrypt
│   │   ├── policy/engine.py     ← ABAC pre-retrieval
│   │   ├── rag/{chunker,embeddings,retriever,reranker,generator,orchestrator}.py
│   │   ├── ingest/pipeline.py
│   │   ├── audit/logger.py
│   │   ├── api/{auth,documents,query,health,schemas}.py
│   │   └── scripts/{init_db,seed_tenants}.py
│   └── tests/                   ← V1, V2, V3, red-team, latencia
├── frontend/                    ← Next.js 14 (App Router + Tailwind)
│   ├── Dockerfile
│   ├── app/{layout,page,chat/page}.tsx
│   └── lib/api.ts
├── evaluation/
│   ├── test_questions.json
│   ├── scripts/{run_evaluation,ragas_eval,security_eval}.py
│   └── results/
└── docs/
    ├── ARCHITECTURE.md
    ├── EVALUATION.md
    ├── SECURITY.md
    └── NEXT_STEPS.md
```

## 4. Requisitos

- Docker Desktop (Windows/macOS) o Docker Engine + Compose v2.
- *(Opcional)* Python 3.11 y Node 20 si se quiere correr fuera de contenedor.
- *(Opcional)* `OPENAI_API_KEY` para activar RAGAS y/o LLM real.

## 5. Puesta en marcha

```powershell
# 1. Clonar y preparar el .env
Copy-Item .env.example .env

# 2. Levantar todo (Postgres + backend + frontend)
docker compose up --build

# 3. Abrir el frontend
start http://localhost:3000
```

La primera vez que arranca el backend ejecuta:

1. `CREATE EXTENSION vector` + schema `platform`.
2. Creación de tablas globales.
3. **Seed idempotente** de dos tenants de demo (`acme` y `globex`) con sus
   usuarios, documentos y ACLs.
4. Arranque de Uvicorn.

### Usuarios de demo

| Tenant | Email                    | Password            | Roles               | Clearance     |
| ------ | ------------------------ | ------------------- | ------------------- | ------------- |
| acme   | admin@acme.test          | `Acme_Admin_2026!`  | admin, employee     | restricted    |
| acme   | legal@acme.test          | `Acme_Legal_2026!`  | legal, employee     | confidential  |
| acme   | intern@acme.test         | `Acme_Intern_2026!` | employee            | public        |
| globex | admin@globex.test        | `Globex_Admin_2026!`| admin, employee     | restricted    |
| globex | finance@globex.test      | `Globex_Fin_2026!`  | finance, employee   | confidential  |
| globex | employee@globex.test     | `Globex_Emp_2026!`  | employee            | internal      |

> **El token JWT** se emite al hacer login y **debe** portarse en
> `Authorization: Bearer <token>` en los demás endpoints. El frontend lo
> gestiona automáticamente.

## 6. API (rutas principales)

| Método | Ruta              | Descripción                                                   |
| ------ | ----------------- | ------------------------------------------------------------- |
| GET    | `/healthz`        | Liveness                                                      |
| GET    | `/readyz`         | Readiness (valida Postgres)                                   |
| POST   | `/auth/login`     | Emite JWT con claims (`tenant`, `roles`, `clearance`, …)      |
| GET    | `/documents`      | Lista documentos *visibles* para el principal                 |
| POST   | `/documents`      | Ingesta un documento (rol `admin` requerido)                  |
| POST   | `/query`          | Ejecuta el pipeline RAG end-to-end                            |

La documentación OpenAPI interactiva está en
`http://localhost:8000/docs`.

## 7. Cómo validar los riesgos

### V1 · Aislamiento (P1)

Inicia sesión con `admin@acme.test` y pregunta en el chat:

> *“¿Cuál es la palabra clave pública de la organización?”*

La respuesta citará únicamente documentos del schema `tenant_acme`
(nunca `HELIOS`, `NEBULA` ni otras referencias de Globex). Si pregunta
cualquier término exclusivo de Globex, el sistema deberá responder
`NO_ANSWER`. El test `backend/tests/test_isolation.py` automatiza
esta validación con un prompt adversarial (`T1.2`).

### V2 · Autorización pre-retrieval (P2)

Inicia sesión con `intern@acme.test` (clearance `public`) y pregunta:

> *“¿Cuál es el monto del contrato con Orion Dynamics?”*

El retriever aplica `required_clearance ≤ public` **antes** del ANN, de
modo que el *chunk* confidencial nunca llega al prompt y la respuesta
es `NO_ANSWER`. Luego inicia sesión con `legal@acme.test` (rol `legal`,
clearance `confidential`) y formula la misma pregunta: ahora sí
responderá citando la cláusula `SIGMA-9`.

### V3 · Grounding con citas (P3)

Cada respuesta afirmativa incluye un arreglo `citations[]` con
`document_title`, `ordinal` y `snippet`. Si el *top-score* del reranker
queda por debajo del umbral (`NO_ANSWER_THRESHOLD`, 0.15 por defecto),
el sistema devuelve `NO_ANSWER` sin llamar al LLM.

## 8. Evaluación (atributos de calidad)

La carpeta `evaluation/` contiene todo el instrumental para las mediciones
cualitativas y cuantitativas que exige el workshop:

```powershell
# 1. Ejecuta el banco de preguntas y mide P50/P95, %answered, %denied_correct
python evaluation/scripts/run_evaluation.py

# 2. Calcula faithfulness, answer_relevancy, context_precision/recall
$env:OPENAI_API_KEY = "sk-…"   # requerido por RAGAS
python evaluation/scripts/ragas_eval.py

# 3. Red-team + cross-tenant (cualquier fuga ⇒ exit code 1)
python evaluation/scripts/security_eval.py
```

Métricas reportadas (detalle en `evaluation/README.md`):

- **Funcionales**: faithfulness, answer relevancy, context precision/recall
  (RAGAS).
- **Seguridad**: tasa de bloqueo cross-tenant (meta 100 %), tasa de deny
  correcto por ABAC (meta 100 %).
- **Desempeño**: P50, P95, throughput y tasa de `no-answer` correcto.
- **Costo** (proxy): tokens consumidos por request cuando `LLM_PROVIDER=openai`.

Los resultados se persisten en `evaluation/results/*.json` para adjuntarlos
a la sección *Resultados* del artículo.

## 9. Pruebas unitarias / integración

```powershell
# Con los contenedores corriendo:
docker compose exec backend pytest -q
```

Incluye las pruebas exigidas por la Tabla 6 del artículo:

- `test_isolation.py`    → T1.1 y T1.2
- `test_authorization.py`→ T2.1 y T2.2
- `test_grounding.py`    → T3.1 y T3.2
- `test_red_team.py`     → baterías cross-tenant y jailbreak
- `test_latency.py`      → T4.1 (marcado `perf`)

## 10. Variables de configuración relevantes

| Variable                   | Por defecto                                           | Para qué sirve                                         |
| -------------------------- | ----------------------------------------------------- | ------------------------------------------------------ |
| `LLM_PROVIDER`             | `mock`                                                | Determinista para CI; cambia a `openai` para RAGAS     |
| `OPENAI_API_KEY`           | —                                                     | Requerido si `LLM_PROVIDER=openai` o para RAGAS        |
| `EMBEDDINGS_PROVIDER`      | `sentence-transformers`                               | `all-MiniLM-L6-v2` local sin costo                     |
| `CHUNK_SIZE_TOKENS`        | 384                                                   | Decisión 3 del artículo                                |
| `CHUNK_OVERLAP_TOKENS`     | 64                                                    | Idem                                                   |
| `RETRIEVAL_TOP_K`          | 20                                                    | Idem                                                   |
| `RERANK_TOP_K`             | 5                                                     | Idem                                                   |
| `NO_ANSWER_THRESHOLD`      | 0.15                                                  | Umbral para P3                                         |
| `RERANKER_ENABLED`         | true                                                  | Cross-encoder MS-MARCO. Desactiva en entornos sin red. |

## 11. Documentación adicional

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — justificación y mapeo de
  decisiones del artículo al código.
- [`docs/SECURITY.md`](docs/SECURITY.md) — modelo de amenazas y
  contramedidas implementadas.
- [`docs/EVALUATION.md`](docs/EVALUATION.md) — protocolo reproducible de
  evaluación cuantitativa y cualitativa.
- [`docs/NEXT_STEPS.md`](docs/NEXT_STEPS.md) — **plan de trabajo desde hoy
  hasta la entrega final del workshop del tercer tercio**.

## 12. Licencia

Uso académico, curso de Transformación Digital y Sistemas en la Nube (TDSN),
Mayo 2026.
