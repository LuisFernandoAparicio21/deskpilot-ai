# Nombres de ramas y commits (resumen operativo)

Fuente: `docs/research/branch-and-feature-naming.md` (Conventional Branch y Conventional Commits 1.0.0).

- Ramas: `feat/<nombre>`, `fix/<nombre>`, `chore/<nombre>`; kebab-case, solo a-z, dígitos, guiones y puntos; sin guiones consecutivos, iniciales ni finales.
- Documentación y mantenimiento: `chore/`. El prefijo `tNN` es opcional (`feat/tNN-nombre`).
- El tipo de la rama debe coincidir con el tipo principal de los commits.
- Commits: `<type>(<scope>): <descripción imperativa en inglés>`; tipos `feat, fix, docs, test, refactor, chore, ci`; `!` para cambios incompatibles.
- Pie: `Refs #n` y el trailer de coautoría vigente. Commits ≤400 líneas. Nunca push directo a `main`.
