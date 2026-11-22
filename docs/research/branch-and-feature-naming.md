# Nombres de ramas y mensajes de commit

## Pregunta
¿Cuál es el estándar oficial para nombrar ramas (Conventional Branch) y mensajes (Conventional Commits), y cómo se aplica a este repo, que ya usa `feat/tNN-nombre` y commits convencionales en inglés?

## Respuesta
- Conventional Commits 1.0.0: `<type>[scope opcional][!]: <description>`, cuerpo y pies opcionales. Solo `feat` (MINOR) y `fix` (PATCH) son obligatorios en la especificación; `docs`, `test`, `refactor`, etc. están permitidos. Cambio incompatible: `!` o pie `BREAKING CHANGE:` (MAJOR).
- Conventional Branch: `<type>/<description>`. Prefijos: `feature/` o `feat/`, `bugfix/` o `fix/`, `hotfix/`, `release/`, `chore/`. También lista prefijos de agentes de IA (`ai/`, `claude/`, `codex/`, `copilot/`, `cursor/`). Ramas troncales sin prefijo: `main`, `master`, `develop`.
- Reglas de nombre: solo minúsculas a-z, dígitos, guiones y puntos; sin guiones/puntos consecutivos, iniciales o finales; sin mayúsculas, guiones bajos ni espacios. Incluir el número de ticket si aplica.
- `feat/tNN-nombre` cumple: `feat/` es prefijo válido, `tNN` es el ticket en minúsculas y el nombre va en kebab-case.
- La rama actual `docs/roadmap-and-naming` usa el prefijo `docs/`, que NO está en la lista de Conventional Branch (el equivalente es `chore/`, que cubre "documentación" en esa especificación). Sí cumple las reglas de caracteres.
- El estándar no dice nada de ramas de tipo `test/`, `refactor/` o `ci/`; no se verificó que las prohíba, pero tampoco las lista.

## Decisión recomendada
1. Mantener `feat/tNN-nombre` para tareas de código y `fix/tNN-nombre` para correcciones.
2. Para documentación y mantenimiento usar `chore/<nombre>` (estándar) o documentar en CONTRIBUTING.md que `docs/` se admite como extensión del repo. Elegir una y anotarla en el Log ODD.
3. Commits: `<type>(<scope>): <descripción imperativa en inglés>`, con tipos `feat, fix, docs, test, refactor, chore, ci`; el scope puede ser el módulo de `src/` o `tNN`. Pie `Refs #issue`; `!` para cambios incompatibles.
4. Alinear el tipo de la rama con el tipo principal de los commits de la rama.

## Fuentes (consultadas 2026-11-21)
- Conventional Commits 1.0.0: https://www.conventionalcommits.org/en/v1.0.0/
- Conventional Branch: https://conventional-branch.github.io/ (redirige 301 a https://conventionalbranch.org/)
