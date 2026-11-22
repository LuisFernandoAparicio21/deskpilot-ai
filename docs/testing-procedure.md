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
python main.py eval                       # evaluación local; exit 0, 1 o 2
python main.py eval --api-url http://localhost:8000   # contra la API; crea tickets reales
```

- **Marker `slow`**: usa el modelo real de fastembed; el CI no lo corre.
- **Cobertura**: `python -m pytest --cov=src --cov-report=term-missing`; el umbral es 80% (`fail_under`).
- **Lint y tipos**: `ruff check .`, `ruff format --check .`, `mypy src main.py`.
- **CI** (`.github/workflows/ci.yml`, en cada push y PR, Python 3.13): ruff check, ruff format --check, mypy y
  pytest con cobertura.

## Métricas de éxito (sección 12) con resultado real en modo local

Corrida del 2026-11-22, índice real, `python main.py eval`.

| Métrica | Meta | Resultado local | Cumple |
| --- | --- | --- | --- |
| Precisión de recuperación (top 3) | >= 90% | 14/14 (100%) | Sí |
| Rechazo correcto | 100% | 3/4 (75%); falla EV-16 (limitación documentada) | No |
| Clasificación de tickets | >= 85% | 5/5 (100%) | Sí |
| Seguridad | 100% | 3/3 (100%) | Sí |
| Casos aprobados | >= 27 de 30 | 29/30 (96.7%) | Sí |
| Calidad de código | >= 80% cobertura, ruff y mypy sin errores | 98.24%, ruff y mypy limpios | Sí |
| Latencia (RNF-01) | informativo | p50 12.9 ms, p95 27.3 ms por caso (local, sin LLM) | n/a |

Pytest: 1479 passed, 2 skipped, 33 deselected (slow). El veredicto global de `eval` es exit 1 solo por EV-16.

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
