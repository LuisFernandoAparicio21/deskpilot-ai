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
