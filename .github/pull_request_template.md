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

Closes #
