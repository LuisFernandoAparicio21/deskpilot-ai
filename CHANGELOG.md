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
