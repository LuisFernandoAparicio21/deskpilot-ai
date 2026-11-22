# Changelog

Todos los cambios relevantes de este proyecto se documentan en este archivo.

El formato se basa en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y el proyecto sigue [Semantic Versioning](https://semver.org/lang/es/).

## [Unreleased]

### Added

- Estructura base del repo ("production-style RAG project"): `src/` con ingestion, chunking, embeddings, vectordb, retrieval, prompts, llm, api y utils; `tests/`, `logs/`, `data/`, `integrations/`, `docs/` y `scripts/`.
- `config.yaml` con la configuración del pipeline y `.env.example` sin valores reales.
- `requirements.txt` y `requirements-dev.txt` con versiones fijadas y verificadas en Python 3.13.
- `pyproject.toml` con la configuración de ruff, pytest, mypy y coverage.
- CLI esqueleto en `main.py` (generate-data, load-db, index, serve, eval, export-openapi).
- CI en GitHub Actions (ruff, mypy, pytest con cobertura), plantilla de PR y plantillas de issues.
- Subagentes de Claude Code en `.claude/agents/` y documento de feature ODD en `docs/odd/`.
- LICENSE (MIT), CONTRIBUTING.md y este CHANGELOG.
- API REST (T16): `/health`, `POST /buscar_solucion`, `GET /tickets/{id}`, `GET /metricas`, autenticación `X-API-Key`, errores uniformes con `request_id`, límites de cuerpo y timeout, comando `serve` y `api.max_body_bytes`. Ver `docs/features/api-rest.md`.
- `POST /tickets` (T17, `crear_ticket`): valida la entrada, redacta datos sensibles (RN-05), clasifica categoría y prioridad con reglas (LLM opcional validado que no puede degradar un P1), aplica escalamiento obligatorio (RN-03), calcula el SLA (RN-01) y guarda en `tickets_nuevos` (SQLite o Warehouse). Ver `docs/features/crear-ticket.md`.
- Servidor MCP (T18): `python main.py mcp` expone `buscar_solucion`, `consultar_estado_ticket`, `metricas_area` y `crear_ticket` sobre la misma capa de servicio que la API; transporte stdio (por defecto) o HTTP streamable con `X-API-Key` o Bearer; errores con mensajes fijos; sección `mcp:` en `config.yaml`. Ver `docs/features/mcp-server.md`.
- `export-openapi` (T19): exporta `integrations/copilot_studio/openapi.json` en Swagger 2.0 JSON para Copilot Studio (`--host` configurable, `apiKey` `X-API-Key`, sin `/health`), con comprobaciones `check_swagger` y 46 pruebas. Ver `docs/features/openapi-export.md`. El Dockerfile se separó como T19b.
- `Dockerfile` y `.dockerignore` (T19b): imagen de una etapa en modo local, usuario no root, índice y modelo de embeddings preparados al construir, `HEALTHCHECK`, sin secretos; verificada con `docker build`/`run` (incluido `--network none`). Modo Fabric sin driver ODBC 18. Ver `docs/features/docker.md`.
- Diseño del agente de Copilot Studio (T20): `integrations/copilot_studio/` con instrucciones, 8 temas ES/EN, `tools.md`, `escalation.md` y 18 conversaciones de prueba; pruebas de estructura y consistencia (`tests/unit/test_copilot_studio.py`). Ver `docs/features/copilot-studio-agent.md`.
- Evaluación end-to-end (T21): `python main.py eval` corre los 30 casos de `tests/eval/cases.csv` en modo local o HTTP (`--api-url`, con aviso de tickets reales), calcula las métricas de la sección 12 y escribe `results.csv` y `results.summary.json`; códigos de salida 0/1/2. Pruebas unitarias, de integración y e2e (incluye p95). Resultado real: 29/30 aprobados, EV-16 como limitación documentada. Ver `docs/features/eval-e2e.md` y `docs/testing-procedure.md`.

### Changed

- Escalamiento por artículo (KB-011) solo dentro de `retrieval.escalation_margin` (0.05) del top-1, para no sobre-escalar (T21); patrones RN-03 de caja y acceso no autorizado ampliados, incluida actividad de inicio de sesión no reconocida (EV-20).
- Policy de escalamiento obligatorio (RN-03) ampliada con frases de fraude, cargos no reconocidos, phishing, robo de identidad, cajero/ATM, caja fuerte y POS (ES/EN), con pruebas.
