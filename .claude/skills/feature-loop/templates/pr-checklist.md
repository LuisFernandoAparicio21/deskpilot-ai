# Plantilla del PR (copiar al cuerpo del PR; incluye las seis secciones de .github/pull_request_template.md y los ítems del ciclo a-f)

## Qué cambia

<!-- Resumen breve de los cambios de este PR (una tarea T# por PR). -->

## Por qué

<!-- Tarea T#, specs S# y requerimientos (RF/RNF/RN/HU de docs/requirements.md) que cubre,
     y el punto de la vacante que evidencia (ver docs/job-fit.md). -->

- Tarea:
- Specs:
- Requerimientos:
- Punto de la vacante:

## Cómo se probó

<!-- Comandos ejecutados y su resultado. -->

```text
ruff check .
ruff format --check .
mypy
pytest --cov=src --cov-report=term-missing
```

## Capturas o salida relevante

<!-- Salida de consola, capturas o enlaces que muestren el resultado. -->

## Checklist

- [ ] Toca solo los archivos de su tarea (nada en `scratch/` ni archivos temporales).
- [ ] Pruebas nuevas o actualizadas, y pasando en local.
- [ ] `ruff check`, `ruff format --check` y `mypy` sin errores.
- [ ] Cobertura de `src/` ≥ 80%.
- [ ] Sin secretos ni datos reales (solo `.env.example` con placeholders; datos sintéticos).
- [ ] Commits ≤400 líneas en Conventional Commits (inglés).
- [ ] Documentación y CHANGELOG actualizados si aplica.
- [ ] Fuentes nuevas anotadas en `docs/sources.md`.

<!-- Ítems del ciclo feature-loop (a-f) -->
- [ ] (a) Investigación y plan hechos; rama `feat/<feature>` creada desde main.
- [ ] (b) Implementación hecha por el desarrollador, con test primero.
- [ ] (c) Pruebas escritas por un qa-tester distinto del desarrollador; sin `skip`/`xfail` sin justificación ni tests debilitados.
- [ ] (d) `pytest --cov=src`, `ruff check` y `mypy` verdes (máx. 2 ciclos); security-verifier aprobó si es [ALTO RIESGO].
- [ ] (e) `docs/features/<feature>.md` con resultados reales, CHANGELOG [Unreleased] y roadmap actualizados.
- [ ] (f) CI verde antes del merge; `Closes #n` lo añade el orquestador.

Closes #
