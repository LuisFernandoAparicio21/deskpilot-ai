# Checklist del PR (copiar a la sección Checklist de la plantilla)

- [ ] Toca solo los archivos de su feature (nada de `scratch/`).
- [ ] Pruebas escritas por un qa-tester distinto del desarrollador, pasando en local.
- [ ] Sin `skip`/`xfail` sin justificación escrita; ningún test debilitado para pasar.
- [ ] `ruff check`, `ruff format --check` y `mypy` sin errores.
- [ ] Cobertura de `src/` ≥ 80%.
- [ ] security-verifier aprobó (si es [ALTO RIESGO] o toca auth, datos sensibles, escalamiento, modelos o CI).
- [ ] Sin secretos ni datos reales.
- [ ] Commits ≤400 líneas, conventional commits en inglés, con trailer.
- [ ] `docs/features/<feature>.md`, CHANGELOG [Unreleased] y roadmap actualizados.
- [ ] Fuentes nuevas en `docs/sources.md`.
- [ ] CI verde antes del merge; `Closes #n` añadido por el orquestador.
