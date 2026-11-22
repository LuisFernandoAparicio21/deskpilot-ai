---
name: feature-loop
description: Úsala para desarrollar cualquier feature del roadmap de DeskPilot AI de punta a punta con el ciclo a–f.
argument-hint: "<nombre o # de la feature de docs/roadmap.md>"
disable-model-invocation: true
---

# feature-loop: ciclo a–f por feature

Entrada: `$ARGUMENTS` = nombre o # de la feature en `docs/roadmap.md` (por ejemplo `PL-12` o `feature-loop-skill`).
Si no existe en el roadmap, detente y pide aclaración. No inventes la feature.

## Reglas del orquestador (tú, el agente principal)
- Delega TODO a subagentes de `.claude/agents/` (tabla en [reference/agents.md](reference/agents.md)), uno a la vez, nunca en paralelo.
  Si el rol no aparece como tipo, usa `general-purpose` con "lee `.claude/agents/<rol>.md` y actúa con ese rol".
- Pide reportes de ≤10 líneas. Tras cada paso emite UNA línea: `F# <feature> · paso c ✓ · N tests, 0 fallos`.
- Nunca escribas código, tests ni investigación en el chat principal. Tú orquestas, ejecutas la verificación (paso d), haces commits de integración, PR y merge.
- Nunca push directo a `main`. Cero secretos. Cero alucinación: lo no verificado se reporta como "no verificado".
- Cada subagente recibe la ruta `docs/odd/deskpilot-ai.md`, la fila del roadmap y los archivos que puede tocar (nunca un resumen).

## Regla estricta de investigación
Ante cualquier duda sobre una API, versión, flag, estándar o paso de interfaz: subagente `researcher` con ≤3 fuentes oficiales;
resultado en `docs/research/<tema>.md` y fuente en `docs/sources.md`. Si la confianza queda baja, no se avanza: se reporta y se pregunta.

## Pasos exactos

### a) Branching
1. `git checkout main && git pull`.
2. Rama con el estándar de [reference/branch-naming.md](reference/branch-naming.md): `feat/`, `fix/` o `chore/` + kebab-case.
3. Issue: `gh issue create` (objetivo, criterios de aceptación, specs/RF).
4. `docs/roadmap.md`: estado `en desarrollo` y rama.

### b) Desarrollo
- Subagente del área (api-engineer, rag-engineer, data-engineer, copilot-studio-designer, docs-writer, repo-architect).
- Prohibido tocar `tests/`. Commits pequeños (≤400 líneas), conventional commits en inglés, con el trailer de coautoría vigente.
- Reporte ≤10 líneas con la interfaz pública (funciones, comandos, endpoints) para que el tester trabaje desde el contrato.

### c) Testing independiente
- `qa-tester` DISTINTO del desarrollador, desde los criterios de aceptación y `docs/requirements.md` (no desde la implementación).
- Anti-falseo: sin asserts triviales; sin `skip`/`xfail` sin justificación escrita; si falla se corrige el CÓDIGO, no la prueba.
- Solo el `qa-tester` cambia pruebas y lo justifica. Un bug de código se documenta con `xfail(strict=True)` y entra al ciclo de corrección (el desarrollador corrige).
- Roadmap: `en pruebas`.

### d) Verificación (la ejecutas tú)
`pytest --cov=src --cov-report=term-missing`, `ruff check .`, `ruff format --check .`, `mypy`.
- Máximo 2 ciclos de corrección; si persisten fallas, marca `bloqueada` en el roadmap con el motivo en el Log del ODD y para.
- `security-verifier` es obligatorio si la feature es [ALTO RIESGO] o toca auth, datos sensibles, escalamiento, descarga de modelos o CI.

### e) Documentación
- `docs-writer`: `docs/features/<feature>.md` con [templates/feature-doc.md](templates/feature-doc.md): resultados REALES copiados de ejecuciones,
  cómo verificar paso a paso, limitaciones y "no verificado". Además CHANGELOG `[Unreleased]` y roadmap `documentada`.
- Deja el cuerpo del PR en `scratch/pr-body.md` (plantilla de `.github/pull_request_template.md`).

### f) Merge
1. PR con la plantilla completa y las seis secciones y el checklist de [templates/pr-checklist.md](templates/pr-checklist.md); `Closes #n` lo pones tú.
2. Espera CI verde (`gh pr checks`). Si falla, vuelve a d.
3. `gh pr merge --merge --delete-branch`; luego `git checkout main && git pull`.
4. Roadmap `mergeada` con # de PR y fecha; entrada nueva en el Log del ODD (L#).

## Checkpoint y parada limpia
- Tras cada merge, roadmap y Log quedan al día para poder retomar con solo `/feature-loop <siguiente>`.
- Si se acerca el límite de uso: termina el paso en curso, deja roadmap y Log con el estado exacto (rama, paso, pendientes), commitea en la rama y avisa. No dejes trabajo a medias sin registrar.

## Entorno de este repo
- RAM y disco limitados: un proceso pesado a la vez; no Docker ni reranker en paralelo.
- `pytest` sin `slow` por defecto; usa `.venv\Scripts\python -m pytest` (PowerShell) y análogos para ruff/mypy.
- No hay helpers propios del flujo en `scripts/` (los existentes son de la fase manual de Fabric/URL pública).
- Experimentos solo en `scratch/` (ignorado por git); se borran al cerrar, salvo `scratch/pr-body.md`.
