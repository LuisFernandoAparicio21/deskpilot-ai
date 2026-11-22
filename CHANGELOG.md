# Changelog

Todos los cambios relevantes de este proyecto se documentan en este archivo.

El formato se basa en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y el proyecto sigue [Semantic Versioning](https://semver.org/lang/es/).

## [Unreleased]

## [0.1.1] - 2026-11-22

Pulido posterior a v0.1.0 (PL-1 a PL-11): README para reclutadores en inglés, diagramas de flujo, veto de reranker, contrato de exit de `eval` y estado de validación. Sigue sin validarse en un tenant real (Fabric, Copilot Studio, Power BI) ni grabarse el video.

### Added

- Política de seguridad (PL-11, #64): `.github/SECURITY.md` en inglés con reporte privado de vulnerabilidades de GitHub, alcance, versiones soportadas y qué no es una vulnerabilidad.
- README rediseñado (PL-10, #62, rama `chore/readme-redesign`; absorbe PL-9): un solo README en inglés con notas de datos sintéticos bilingües, resumen en español al final, orden y límites según `docs/research/readme-outline.md`, 6 badges (4 de estado y 2 de plataforma Microsoft), cifras con fuente (30/30 casos, 98.12% de cobertura). Decisiones y lo no verificado en `docs/features/readme-redesign.md`.
- Veto con reranker cross-encoder (PL-8, #60, rama `feat/rejection-cases`): `retrieval.rerank` (`BAAI/bge-reranker-v2-m3-int8`, `min_score` 0.01, puntuación pasaje a pasaje) convierte en "no lo sé" las respuestas sin pasaje relevante; `eval` pasa de 29/30 (exit 3) a 30/30 (exit 0) y `eval.known_failures` queda vacío. Casos `tests/eval/rejection_cases.csv` (RJ-01 a RJ-08) y held-out de 40 casos (`heldout_cases.csv`, 39/40: límite HO-29). Experimento de mecanismos en `docs/research/rejection-experiment.md` y [ADR-0009](docs/adr/0009-veto-con-reranker-cross-encoder.md). Costo: ~0.57 GB de descarga y ~0.5 a 1 s por consulta. No verificado: tamaño de la imagen Docker con el reranker, `docker run --network none` y CI.
- Flujo del usuario (PL-1, #46): `docs/user-flow.md` con diagrama de decisión, diagrama de secuencia, tablas paso-herramienta-RF-EV y ejemplos reales ES/EN; versión compacta en la sección "Cómo funciona" del README.
- Investigación del estilo visual del perfil y de los repos fijados (PL-2, #48): `docs/research/visual-style.md`.
- Renovación visual del README (PL-3, #50): banner terminal propio en SVG (`docs/assets/banner-dark.svg` y `banner-light.svg`, con `<picture>`), línea animada readme-typing-svg, resumen en inglés arriba, badges Shields.io agrupados (Fabric y Copilot Studio marcados como pendientes de validar), secciones con emoji en orden para reclutador, demo con salida real de `eval` y cifras actualizadas (1753 pruebas, 98.24% de cobertura).
- Diagnóstico de la revisión externa (PL-4, #52): `docs/diagnostics/2026-11-22-review.md` con los 5 problemas (P1 a P5), evidencia, causa raíz y soluciones.

### Changed

- Documentación alineada con los resultados reales de PL-8 (#60): README, business-case, testing-procedure, eval-e2e, architecture, user-flow, MANUAL_STEPS y ADR-0001 (30/30, rechazo 4/4, exit 0, p50 380.5 ms y p95 801.6 ms, 2028 tests, 98.12% de cobertura); EV-16 pasa a caso histórico.
- Contrato de exit codes de `main.py eval` (PL-7, #58, P4): 0 = todo cumple; 3 = mínimo global y seguridad cumplidos pero hay criterios no cumplidos o fallos conocidos; 1 = regresión (mínimo, seguridad o caso fuera de `known_failures`); 2 = error. **Cambio de contrato**: el 1 ya no significa "objetivo no cumplido" (ahora es 3). Nueva sección `eval:` en `config.yaml` (`thresholds`, `known_failures` con motivo) validada con Pydantic; `results.summary.json` añade `criteria`, `known_failures_hit`, `new_failures`, `exit_code` y `exit_reason`. El job `eval-smoke` acepta solo 0 o 3, anota los criterios no cumplidos como `::warning::` y elimina la comprobación ad hoc `passed >= 27`.
- Validado vs. pendiente (PL-6, #56): la tabla "Habilidades demostradas" del README separa lo validado en local (SQL, API REST/MCP, RAG con citas, pruebas, CI, Docker) de lo diseñado y probado con dobles, pendiente de validar en tenant real (Fabric, Copilot Studio, Power BI); se ajustan la línea animada, "Qué es" y el diagrama del README, `docs/job-fit.md` y `docs/business-case.md` (en condicional: el diseño prevé; validado solo en local).
- Roadmap de pulido posterior a v0.1.0 (PL-1 a PL-8) y agente `diagnostician` (#44).
- Changelog de v0.1.0 y notas de release (PL-5, #54).

## [0.1.0] - 2026-11-22

Fase A completa en modo local (tag `v0.1.0`, commit `bb06584`, PR #42). Fabric y Copilot Studio están diseñados y probados con dobles, pero no validados en un tenant real.

### Added

- Estructura base del repo ("production-style RAG project"): `src/` con ingestion, chunking, embeddings, vectordb, retrieval, prompts, llm, api y utils; `tests/`, `logs/`, `data/`, `integrations/`, `docs/` y `scripts/`. Incluye `config.yaml`, `.env.example` sin valores reales, `requirements.txt` y `requirements-dev.txt` con versiones fijadas (Python 3.13), `pyproject.toml` (ruff, pytest, mypy, coverage), CLI esqueleto en `main.py`, CI en GitHub Actions, plantillas de PR e issues, subagentes de Claude Code en `.claude/agents/`, documento ODD en `docs/odd/`, LICENSE (MIT), CONTRIBUTING.md y este CHANGELOG.
- Configuración Pydantic fail-fast, logging JSON con `request_id` y redacción de datos sensibles (T8, #2).
- Generador determinista de tickets sintéticos y comando `generate-data` (T9, #4).
- Carga a SQLite y 10 consultas SQL portables de negocio (T10, #6).
- Notebook PySpark/Delta, DDL del Warehouse y conexión a Fabric por Entra ID (T11, #8).
- 15 artículos de base de conocimiento de soporte bancario (T12, #10).
- Cargadores de ingesta MD/PDF/CSV y chunking por sección (T13, #12).
- Embeddings con fastembed, almacén Chroma versionado y comando `index` (T14, #14).
- Servicio RAG (T15, #16): retrieval con umbral, prompts, clientes LLM (none, Claude, OpenAI, Gemini) y respuesta extractiva con cita.
- Documentación de roadmap y estándar de nombres de ramas (#18).
- API REST (T16, #20): `/health`, `POST /buscar_solucion`, `GET /tickets/{id}`, `GET /metricas`, autenticación `X-API-Key`, errores uniformes con `request_id`, límites de cuerpo y timeout, comando `serve` y `api.max_body_bytes`. Ver `docs/features/api-rest.md`.
- `POST /tickets` (T17, #22, `crear_ticket`): valida la entrada, redacta datos sensibles (RN-05), clasifica categoría y prioridad con reglas (LLM opcional validado que no puede degradar un P1), aplica escalamiento obligatorio (RN-03), calcula el SLA (RN-01) y guarda en `tickets_nuevos` (SQLite o Warehouse). Ver `docs/features/crear-ticket.md`.
- Servidor MCP (T18, #24): `python main.py mcp` expone `buscar_solucion`, `consultar_estado_ticket`, `metricas_area` y `crear_ticket` sobre la misma capa de servicio que la API; transporte stdio (por defecto) o HTTP streamable con `X-API-Key` o Bearer; errores con mensajes fijos; sección `mcp:` en `config.yaml`. Ver `docs/features/mcp-server.md`.
- `export-openapi` (T19, #26): exporta `integrations/copilot_studio/openapi.json` en Swagger 2.0 JSON para Copilot Studio (`--host` configurable, `apiKey` `X-API-Key`, sin `/health`), con comprobaciones `check_swagger` y 46 pruebas. Ver `docs/features/openapi-export.md`.
- `Dockerfile` y `.dockerignore` (T19b, #28): imagen de una etapa en modo local, usuario no root, índice y modelo de embeddings preparados al construir, `HEALTHCHECK`, sin secretos; verificada con `docker build`/`run` (incluido `--network none`). Ver `docs/features/docker.md`.
- Diseño del agente de Copilot Studio (T20, #30): `integrations/copilot_studio/` con instrucciones, 8 temas ES/EN, `tools.md`, `escalation.md` y 18 conversaciones de prueba; pruebas de estructura y consistencia. Ver `docs/features/copilot-studio-agent.md`.
- Evaluación end-to-end (T21, #32): `python main.py eval` corre los 30 casos de `tests/eval/cases.csv` en modo local o HTTP (`--api-url`), calcula las métricas y escribe `results.csv` y `results.summary.json`; códigos de salida 0/1/2. Resultado real: 29/30 aprobados, EV-16 como limitación documentada. Ver `docs/features/eval-e2e.md` y `docs/testing-procedure.md`.
- CI y cobertura (T22, #34): mypy sobre `tests`, jobs `quality`, `eval-smoke` (caché del modelo fastembed, exige 30 casos y >=27 aprobados) y `docker-build` (buildx con caché). Cobertura 98.24%. Ver `docs/features/coverage-ci.md`.
- Caso de negocio (T23, #36): `docs/business-case.md` con cifras de las 10 consultas SQL sobre los datos sintéticos (39.92% repetitivo, 51.24% automatizable, factor de quincena 1.90, SLA 79.50% local contra 60.57% foráneo) y supuestos marcados como ilustrativos; ADR-0001 a ADR-0008 en `docs/adr/` con su índice.
- Documentación final de Fase A (T24, #38): README completo, `docs/architecture.md` con diagramas Mermaid, `docs/job-fit.md` y plantilla de `docs/learning-log.md`.
- Guía manual y scripts de verificación (T25, #40): `docs/MANUAL_STEPS.md` (46 pasos para T28 a T36), `scripts/check_fabric.py`, `scripts/check_public_url.py` y `scripts/update_readme_results.py` con 97 pruebas (dobles, sin Fabric ni URL real) y `docs/research/` de acceso a Fabric, Copilot Studio, URL pública y Power BI. Ver `docs/features/manual-steps-scripts.md`.

### Changed

- Escalamiento por artículo (KB-011) solo dentro de `retrieval.escalation_margin` (0.05) del top-1, para no sobre-escalar (T21, #32).
- Policy de escalamiento obligatorio (RN-03) ampliada con fraude, cargos no reconocidos, phishing, robo de identidad, cajero/ATM, caja fuerte, POS y actividad de inicio de sesión no reconocida (ES/EN), con pruebas (T21, #32; EV-20).
- Tests de integración duplicados renombrados (`test_api_create_ticket_flow.py`, `test_mcp_server_integration.py`) (T22, #34).

### Fixed

- ResourceWarning de sqlite corregido (T22, #34).
- Hallazgos de la revisión final (T27, #42): cifras de pruebas actualizadas (1724 passed, 98.24%), texto del placeholder del video, continuaciones `\` del Dockerfile restauradas (`docker build` verificado) y READMEs de `src/ingestion`, `src/embeddings` y `src/vectordb` reducidos a 3 líneas.

[Unreleased]: https://github.com/LuisFernandoAparicio21/deskpilot-ai/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/LuisFernandoAparicio21/deskpilot-ai/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/LuisFernandoAparicio21/deskpilot-ai/releases/tag/v0.1.0
