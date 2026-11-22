# Cobertura y CI (T22)

Feature T22 (rama `chore/t22-coverage-ci`). Cubre S12 (pruebas) y S17 (nivel producción), RNF-08 y RNF-09.
Los datos son sintéticos (banco ficticio "Banco Altiplano"); las cifras son ilustrativas.

## Qué cambió

- **mypy sobre `src`, `main.py` y `tests`**: en `pyproject.toml`, `files = ["src", "main.py", "tests"]` y
  `explicit_package_bases = true`. Los tests quedaron tipados con `strict = true`.
- **Dos tests duplicados renombrados**: `tests/integration/test_api_create_ticket.py` pasó a
  `test_api_create_ticket_flow.py` y `tests/integration/test_mcp_server.py` a `test_mcp_server_integration.py`.
  Tenían el mismo nombre de módulo que sus pares de `tests/unit/`, y mypy los analiza todos juntos. Se corrigieron
  los enlaces en `docs/features/crear-ticket.md` y `docs/features/mcp-server.md`.
- **ResourceWarning de sqlite corregido**: el test de fuga de secretos en `test_api_create_ticket_flow.py` ya
  cierra su conexión.
- **CI (`.github/workflows/ci.yml`) con tres jobs**:
  - `quality`: `ruff check`, `ruff format --check`, `mypy src main.py tests` y `pytest --cov=src` (umbral 80%).
  - `eval-smoke`: instala solo `requirements.txt`, cachea el modelo de fastembed (`data/vectordb/models`, clave con
    `hashFiles('config.yaml')`), corre `generate-data`, `load-db`, `index` y `main.py eval`. Acepta código de
    salida 1 (EV-16 es una limitación documentada) y falla con cualquier otro distinto de 0; luego exige 30 casos
    y al menos 27 aprobados según `results.summary.json`. Sube `results.csv` y el resumen como artefacto.
  - `docker-build`: `docker/build-push-action` con `push: false` y caché de buildx (`type=gha`).

## Specs

- **S12**: cobertura de líneas y ramas >= 80% (`fail_under = 80`), ruff y mypy limpios, evaluación como humo en CI.
- **S17**: el CI verifica también que la imagen Docker construye y que el índice real responde a los casos.

## Resultados reales

Ejecutados en local (Windows, Python 3.13, rama `chore/t22-coverage-ci`):

```text
pytest --cov=src --cov-report=term-missing
TOTAL                                   3434     41    656     29    98%
Required test coverage of 80.0% reached. Total coverage: 98.24%
1479 passed, 2 skipped, 33 deselected in 99.35s

ruff check .           -> Ruff: No issues found
ruff format --check .  -> 174 files already formatted
mypy src main.py tests -> mypy: No issues found
```

Los 2 omitidos: un test con parámetros vacíos en `test_main.py` y la validación opcional de
`openapi-spec-validator`. Los 33 deseleccionados son los `slow` (descargan el modelo real).

## Cómo verificar paso a paso

1. Activa el entorno: `.\.venv\Scripts\Activate.ps1` e instala `pip install -r requirements-dev.txt`.
2. `ruff check .` y `ruff format --check .`: sin errores.
3. `mypy src main.py tests`: sin errores.
4. `pytest --cov=src --cov-report=term-missing`: todo en verde y cobertura >= 80%.
5. Evaluación como en el CI: `python main.py generate-data`, `python main.py load-db`, `python main.py index` y
   `python main.py eval`. Debe salir con código 0 o 1 y `tests/eval/results.summary.json` con `total` 30 y
   `passed` >= 27 (en local salió 29).
6. Imagen: `docker build -t deskpilot-ai:ci .`.
7. Jobs de CI: en el PR, pestaña Checks (`quality`, `eval-smoke`, `docker-build`).

## Limitaciones

- Un `ResourceWarning` de `anyio` proveniente del cliente MCP sigue apareciendo en algunos tests; no se corrigió
  porque viene de la librería y no de este código.
- `eval-smoke` y `docker-build` son jobs nuevos y no se han ejecutado en GitHub Actions: ver resultado del PR.
- EV-16 sigue siendo un fallo conocido (ver `docs/features/eval-e2e.md`), por eso el umbral es >= 27/30 y no 30/30.
