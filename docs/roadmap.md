# Roadmap DeskPilot AI

**Objetivo:** llevar DeskPilot AI de T15 (RAG completo) a la release `v0.1.0`: API REST, MCP, despliegue, agente Copilot Studio, evaluación, documentación y revisión final. Fuente de verdad: `docs/odd/deskpilot-ai.md` (Tasks T#, Specs S#) y `docs/requirements.md` (RF/RNF).

## Regla de nombres
Ver [docs/research/branch-and-feature-naming.md](research/branch-and-feature-naming.md).
- Ramas: `feat/<nombre>`, `fix/<nombre>`, `chore/<nombre>` (kebab-case, minúsculas).
- El prefijo `tNN` es opcional; se usa `feat/tNN-nombre` para continuidad con T8–T15.
- Commits convencionales en inglés; todo entra por PR (nunca push directo a main).

## Leyenda de estados
`pendiente` -> `en desarrollo` -> `en pruebas` -> `documentada` -> `mergeada`
- en desarrollo: implementa el subagente desarrollador (sin tocar `tests/` desde T16).
- en pruebas: `qa-tester` valida; [ALTO RIESGO] además pasa por `security-verifier` (solo lectura).
- documentada: README/CHANGELOG/docs de la feature al día, PR listo.

## Hecho
| # | Feature | Rama | Descripción | Specs/RF | Subagente | Estado | PR | Fecha |
|---|---|---|---|---|---|---|---|---|
| T1-T7 | Investigación, base del repo, CLAUDE.md, ODD, revisión de base, publicación | (commit directo previo a T8) | Estructura base y repo público | S1, S2, S14-S16, S19, S20 | repo-architect / docs-writer / security-verifier | mergeada | - | - |
| T8 | config-logging | feat/t08-utils-config-logging | Config Pydantic fail-fast y logging JSON con request_id | S17 | repo-architect | mergeada | #2 | 2026-11-21 |
| T9 | generate-data | feat/t09-ticket-generator | Generador de tickets sintéticos + `generate-data` | S3 | data-engineer | mergeada | #4 | 2026-11-21 |
| T10 | load-db-sql | feat/t10-sqlite-sql-queries | Carga a SQLite + 10 consultas SQL portables | S5 | data-engineer | mergeada | #6 | 2026-11-21 |
| T11 | fabric-delta [ALTO RIESGO] | feat/t11-fabric-notebook-connection | Notebook PySpark/Delta, DDL Warehouse, conexión Fabric por env | S6, S16, RF-18 | data-engineer | mergeada | #8 | 2026-11-21 |
| T12 | knowledge-base | feat/t12-knowledge-base | 15 artículos KB + test de formato | S4 | docs-writer | mergeada | #10 | 2026-11-21 |
| T13 | ingestion-chunking | feat/t13-ingestion-chunking | Ingesta MD/PDF/CSV + chunking por sección | S7, RF-11/12 | rag-engineer | mergeada | #12 | 2026-11-21 |
| T14 | embeddings-vectordb | feat/t14-embeddings-vectordb | fastembed + Chroma tras interfaz + `index` | S7, S17 | rag-engineer | mergeada | #14 | 2026-11-21 |
| T15 | rag-service [ALTO RIESGO] | feat/t15-retrieval-llm-answer | Retrieval con umbral, prompts, LLM none/Claude/OpenAI/Gemini, respuesta con cita | S7, S16, RF-13/14, RN-04 | rag-engineer + security-verifier | mergeada | #16 | 2026-11-21 |

## Pendiente (código)
Orden por dependencias; un subagente a la vez.

| # | Feature | Rama | Descripción | Specs/RF | Subagente desarrollador | Estado | PR | Fecha |
|---|---|---|---|---|---|---|---|---|
| T16 | api-rest [ALTO RIESGO] | feat/t16-api-rest | FastAPI completo: /health, X-API-Key, errores, request_id, timeouts, buscar_solucion, consultar_estado_ticket, metricas_area, repo local/fabric, `serve` | S8, S17, RF-17/19/26, RNF-02-06 | api-engineer | mergeada | #20 | 2026-11-21 |
| T17 | crear-ticket [ALTO RIESGO] | feat/t17-crear-ticket | crear_ticket con clasificación categoría/prioridad, redacción de datos sensibles y persistencia (depende de T16) | S9, RF-10/16/18, RN-01-03/05 | api-engineer | mergeada | #22 | 2026-11-21 |
| T18 | mcp-server | feat/t18-mcp-server | Servidor MCP con las 4 herramientas (depende de T16-T17) | S10 | api-engineer | mergeada | #24 | 2026-11-21 |
| T19 | openapi-docker | feat/t19-openapi-docker | `export-openapi` (OpenAPI v2 JSON compatible con Copilot Studio). Dockerfile separado como T19b (ver fila siguiente) | S8, S17, RF-25, RNF-10 | api-engineer | mergeada | #26 | 2026-11-22 |
| T19b | docker-image | feat/t19b-dockerfile | Dockerfile y .dockerignore de una etapa (modo local, no root, modelo e índice en el build), verificados con docker build/run | S17, RNF-10 | api-engineer | mergeada | #28 | 2026-11-22 |
| T20 | copilot-studio-design | feat/t20-copilot-studio | Instrucciones, temas, frases ES/EN y escalamiento del agente | S11, RF-01-09, RNF-12 | copilot-studio-designer | mergeada | #30 | 2026-11-22 |
| T21 | eval-e2e | feat/t21-eval-e2e | 30 casos de evaluación, comando `eval`, resultados, test e2e (p95), testing-procedure.md | S12, RNF-01 | qa-tester | mergeada | #32 | 2026-11-22 |
| T22 | coverage-ci | chore/t22-coverage-ci | Cobertura >=80%, ruff/mypy limpios, huecos de tests, CI verde | S12, S17, RNF-08/09 | qa-tester | mergeada | #34 | 2026-11-22 |
| T23 | business-case-adrs | chore/t23-business-case-adrs | business-case.md con cifras del SQL + ADRs en docs/adr | S13 | docs-writer | mergeada | #36 | 2026-11-22 |
| T24 | docs-readme | chore/t24-docs-readme | README completo, architecture.md, job-fit.md, learning-log.md, CHANGELOG | S13, S14, RNF-13 | docs-writer | mergeada | #38 | 2026-11-22 |
| T25 | manual-steps-scripts (Fase B) | chore/t25-manual-steps | MANUAL_STEPS.md + scripts check_fabric.py, check_public_url.py, update_readme_results.py | S18 | docs-writer | mergeada | #40 | 2026-11-22 |
| T26 | revision-final [ALTO RIESGO] | (sin rama: solo reporte) | Revisión final de secretos/seguridad y revisión "como reclutador" | S16, S21 | security-verifier (solo lectura) | documentada | - | 2026-11-22 |
| T27 | release-v0.1.0 | fix/t27-final-review-findings | Correcciones de T26, suite completa y tag `v0.1.0` | S12, S21 | según hallazgo (testing: qa-tester) | mergeada | #42 | 2026-11-22 |

## Pulido posterior a v0.1.0 (pedido del usuario, 2026-11-22)

Orden: bloque 1 (PL-1), bloque 2 (PL-2, PL-3), bloque 3 (PL-4 y correcciones PL-5..PL-8). Cada feature con el ciclo a–f.

| # | Feature | Rama | Descripción | Specs/RF | Subagente desarrollador | Estado | PR | Fecha |
|---|---|---|---|---|---|---|---|---|
| PL-1 | user-flow | chore/user-flow-diagram | docs/user-flow.md: diagrama de decisión y de secuencia del MVP desde el usuario + ejemplo real ES/EN; versión compacta en README | S13, RF de búsqueda/ticket/escalamiento | docs-writer (qa-tester valida) | documentada | - | - |
| PL-2 | visual-style-research | chore/visual-style-research | Investigación del estilo visual del perfil y repos del usuario (docs/research/visual-style.md) | S13 | researcher | mergeada | #48 | 2026-11-22 |
| PL-3 | readme-visual-refresh | chore/readme-visual-refresh | Banner SVG, typing-svg, badges agrupados, resumen EN arriba, resultados en números, orden para reclutador | S13, S14 | docs-writer (qa-tester valida) | documentada | - | - |
| PL-4 | diagnostics-review | chore/diagnostics-review | Diagnóstico de 5 problemas de la revisión externa (docs/diagnostics/2026-11-22-review.md) | S12, S14 | diagnostician | mergeada | #52 | 2026-11-22 |
| PL-5 | github-release-v0.1.0 | chore/release-v0.1.0-notes | P1: GitHub Release v0.1.0 con notas generadas de los PRs | S15 | docs-writer | mergeada | #54 | 2026-11-22 |
| PL-6 | validated-vs-pending | chore/validated-vs-pending | P3: separar Validado de Pendiente de validar en tenant real en README y job-fit | S14 | docs-writer (qa-tester valida) | documentada | - | 2026-11-22 |
| PL-7 | eval-exit-contract | fix/eval-exit-contract | P4: contrato explícito del exit code de eval en config.yaml y CI sin tolerar errores genéricos | S12, S17 | rag-engineer (qa-tester valida) | pendiente | - | - |
| PL-8 | rejection-cases | feat/rejection-cases | P5: 6–8 casos nuevos de rechazo fuera de dominio y, si se justifica, mecanismo general de rechazo | S12, RN rechazo | qa-tester + rag-engineer | pendiente | - | - |
| PL-9 | english-accessibility | chore/english-accessibility | P2: resumen en inglés ampliado con tabla de habilidades y límites; alinear conteos de pruebas entre README, resumen EN y job-fit | S13, S14 | docs-writer (qa-tester valida) | pendiente | - | - |

## Fase manual (usuario)
Las ejecuta el usuario siguiendo `docs/MANUAL_STEPS.md` (T25). Dependen de T16-T25.

| # | Feature | Rama | Descripción | Specs/RF | Responsable | Estado | PR | Fecha |
|---|---|---|---|---|---|---|---|---|
| T28 | fabric-setup | - | Prueba de Fabric, workspace, lakehouse, warehouse, subir CSV (45 min) | S6, S22 | usuario | pendiente | - | - |
| T29 | fabric-queries | - | Notebook + 10 consultas en SQL endpoint + DDL Warehouse + capturas (45 min) | S5, S6 | usuario | pendiente | - | - |
| T30 | fabric-env-check | - | Llenar .env, `check_fabric.py`, API en modo fabric (30 min) | S6, S8 | usuario | pendiente | - | - |
| T31 | public-url | - | URL pública y `check_public_url.py` (20 min) | S8 | usuario | pendiente | - | - |
| T32 | copilot-agent | - | Crear agente en Copilot Studio, instrucciones, temas, KB, API como herramienta (75 min) | S11 | usuario | pendiente | - | - |
| T33 | eval-manual | - | Correr 30 casos en el chat, llenar CSV, capturas (60 min) | S11, S12 | usuario | pendiente | - | - |
| T34 | powerbi | - | Reporte Power BI con KPIs (45 min) | S22, RF-21 | usuario | pendiente | - | - |
| T35 | video-learning-log | - | Video 2-3 min y learning-log (40 min) | S14, S22 | usuario | pendiente | - | - |
| T36 | evidencia-final | feat/t36-evidencia-real | Con resultados del usuario: actualizar README, business-case y testing-procedure; push final por PR | S22 | docs-writer + security-verifier | pendiente | - | - |
