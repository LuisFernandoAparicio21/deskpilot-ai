# Procedimiento de pruebas

Cómo probar DeskPilot AI de punta a punta. Datos sintéticos (banco ficticio "Banco Altiplano"). Comandos desde la
raíz del repo con `.venv\Scripts\python` (Windows).

## Niveles de prueba

| Nivel | Dónde | Qué cubre | Comando |
| --- | --- | --- | --- |
| Unitarias | `tests/unit/` | Lógica aislada (config, clasificación, policy, evaluación, API con repositorios falsos) | `python -m pytest tests/unit` |
| Integración | `tests/integration/` | SQL, indexado, API + RAG, MCP, escalamiento por artículo | `python -m pytest tests/integration` |
| End-to-end | `tests/e2e/` | Datos -> SQLite -> índice -> API -> 30 casos, latencia | `python -m pytest tests/e2e` |
| Evaluación | `tests/eval/cases.csv` | Los 30 casos del agente y las métricas de la sección 12 | `python main.py eval` |

Detalle de la evaluación en `docs/features/eval-e2e.md`.

## Cómo correr cada uno

```bash
python -m pytest                          # todo salvo `slow` (addopts: -m "not slow")
python -m pytest -m slow                  # solo las lentas (modelo fastembed real; el último -m manda)
python -m pytest -m slow tests/e2e        # los 30 casos con el modelo real
python main.py eval                       # evaluación local; exit 0, 3 (aceptables), 1 (regresión) o 2 (error)
python main.py eval --api-url http://localhost:8000   # contra la API; crea tickets reales
```

- **Marker `slow`**: usa el modelo real de fastembed; el CI no lo corre.
- **Cobertura**: `python -m pytest --cov=src --cov-report=term-missing`; el umbral es 80% (`fail_under`).
- **Lint y tipos**: `ruff check .`, `ruff format --check .`, `mypy src main.py tests`.
- **CI** (`.github/workflows/ci.yml`, en cada push y PR, Python 3.13): ruff check, ruff format --check, mypy (src, main.py, tests) y
  pytest con cobertura. Dos jobs más: `eval-smoke` (generate-data, load-db, index y `main.py eval`; acepta solo exit 0 o 3 y anota como `::warning::` los criterios no cumplidos; cachea el modelo fastembed) y `docker-build` (build sin push, cache buildx).

## Métricas de éxito (sección 12) con resultado real en modo local

Corrida del 2026-11-22, índice real, `python main.py eval`.

| Métrica | Meta | Resultado local | Cumple |
| --- | --- | --- | --- |
| Precisión de recuperación (top 3) | >= 90% | 14/14 (100%) | Sí |
| Rechazo correcto | 100% | 4/4 (100%); EV-16 ya se rechaza con el veto del reranker | Sí |
| Clasificación de tickets | >= 85% | 5/5 (100%) | Sí |
| Seguridad | 100% | 3/3 (100%) | Sí |
| Casos aprobados | >= 27 de 30 | 30/30 (100.0%) | Sí |
| Calidad de código | >= 80% cobertura, ruff y mypy sin errores | 98.12%, ruff y mypy limpios | Sí |
| Latencia (RNF-01) | informativo | p50 380.5 ms, p95 801.6 ms por caso (local, sin LLM, con reranker) | n/a |

Pytest: 2028 passed, 3 skipped, 35 deselected (slow). El veredicto global de `eval` es exit 0 (todos los criterios cumplidos, `eval.known_failures` vacío; EV-16 fue un fallo conocido hasta PL-8). Límite honesto: HO-29 en `tests/eval/heldout_cases.csv` (39/40, `eval --cases` sobre ese CSV sale con exit 1).

### Códigos de salida de `main.py eval` (contrato)

| Código | Significado |
| --- | --- |
| 0 | Todos los criterios `target` cumplidos |
| 3 | Mínimo global y seguridad cumplidos, pero hay criterios no cumplidos o fallos conocidos (el CI lo acepta y lo anota como warning) |
| 1 | Regresión: se rompe el mínimo global o la seguridad, o falla un caso fuera de `known_failures` (el CI falla) |
| 2 | Error de configuración, CSV, base, índice o API (el CI falla) |

Metas y `known_failures` (con motivo) en la sección `eval:` de `config.yaml`; detalle y migración desde el antiguo
"1 = umbral no cumplido" en `docs/features/eval-e2e.md`. `known_failures` no oculta regresiones. Un id de `known_failures` ausente del CSV usado (`--cases` personalizado, CSV de prueba) no da exit 2: se ignora con advertencia en stderr y se lista en `known_failures_ignored` del resumen JSON; exit 2 queda solo para errores reales de config, CSV, base, índice o API.

## Resultados en Copilot Studio (T32)

**PENDIENTE (manual).** Aún no hay resultados de Copilot Studio: se llenan al ejecutar los casos en el chat de
prueba (pasos en `docs/MANUAL_STEPS.md`, T25). No se deben inventar valores.

| ID | Pregunta | Esperado | Obtenido en Copilot Studio | Pasó (sí/no) | Notas |
| --- | --- | --- | --- | --- | --- |
| EV-01 | ver `cases.csv` | ver `cases.csv` | PENDIENTE | PENDIENTE | |
| EV-02 | ver `cases.csv` | ver `cases.csv` | PENDIENTE | PENDIENTE | |
| EV-03 | ver `cases.csv` | ver `cases.csv` | PENDIENTE | PENDIENTE | |
| EV-04 | ver `cases.csv` | ver `cases.csv` | PENDIENTE | PENDIENTE | |
| EV-05 | ver `cases.csv` | ver `cases.csv` | PENDIENTE | PENDIENTE | |
| EV-06 | ver `cases.csv` | ver `cases.csv` | PENDIENTE | PENDIENTE | |
| EV-07 | ver `cases.csv` | ver `cases.csv` | PENDIENTE | PENDIENTE | |
| EV-08 | ver `cases.csv` | ver `cases.csv` | PENDIENTE | PENDIENTE | |
| EV-09 | ver `cases.csv` | ver `cases.csv` | PENDIENTE | PENDIENTE | |
| EV-10 | ver `cases.csv` | ver `cases.csv` | PENDIENTE | PENDIENTE | |
| EV-11 | ver `cases.csv` | ver `cases.csv` | PENDIENTE | PENDIENTE | |
| EV-12 | ver `cases.csv` | ver `cases.csv` | PENDIENTE | PENDIENTE | |
| EV-13 | ver `cases.csv` | ver `cases.csv` | PENDIENTE | PENDIENTE | |
| EV-14 | ver `cases.csv` | ver `cases.csv` | PENDIENTE | PENDIENTE | |
| EV-15 | ver `cases.csv` | ver `cases.csv` | PENDIENTE | PENDIENTE | |
| EV-16 | ver `cases.csv` | ver `cases.csv` | PENDIENTE | PENDIENTE | |
| EV-17 | ver `cases.csv` | ver `cases.csv` | PENDIENTE | PENDIENTE | |
| EV-18 | ver `cases.csv` | ver `cases.csv` | PENDIENTE | PENDIENTE | |
| EV-19 | ver `cases.csv` | ver `cases.csv` | PENDIENTE | PENDIENTE | |
| EV-20 | ver `cases.csv` | ver `cases.csv` | PENDIENTE | PENDIENTE | |
| EV-21 | ver `cases.csv` | ver `cases.csv` | PENDIENTE | PENDIENTE | |
| EV-22 | ver `cases.csv` | ver `cases.csv` | PENDIENTE | PENDIENTE | |
| EV-23 | ver `cases.csv` | ver `cases.csv` | PENDIENTE | PENDIENTE | |
| EV-24 | ver `cases.csv` | ver `cases.csv` | PENDIENTE | PENDIENTE | |
| EV-25 | ver `cases.csv` | ver `cases.csv` | PENDIENTE | PENDIENTE | |
| EV-26 | ver `cases.csv` | ver `cases.csv` | PENDIENTE | PENDIENTE | |
| EV-27 | ver `cases.csv` | ver `cases.csv` | PENDIENTE | PENDIENTE | |
| EV-28 | ver `cases.csv` | ver `cases.csv` | PENDIENTE | PENDIENTE | |
| EV-29 | ver `cases.csv` | ver `cases.csv` | PENDIENTE | PENDIENTE | |
| EV-30 | ver `cases.csv` | ver `cases.csv` | PENDIENTE | PENDIENTE | |
