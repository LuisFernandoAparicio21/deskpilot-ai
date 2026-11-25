# Final audit (FA-1)

Feature FA-1 (rama `docs/final-audit-checklist`). Cubre S13, S16, S21, S22. Datos sintéticos (banco ficticio "Banco Altiplano").

## Qué es / Qué cambió

Runbook ejecutable de auditoría final (`docs/final-audit-checklist.md`) y skill de orquestación (`.claude/skills/final-audit/SKILL.md`). Se ejecuta **después de que la Fase C esté mergeada**, antes de postular o compartir el repo.

Archivos añadidos:

- `docs/final-audit-checklist.md` — 441 líneas, 7 secciones (0 Preparación, 1 Auditoría de seguridad con la skill vulnerability-scanner, 2 Evaluadores de código abierto, 3 Servicios externos, 4 Revisión independiente, 5 Consolidación y correcciones, 6 Sign-off). Cada sección tiene: Agente, Tiempo estimado, ¿Necesita a Luis?, pasos con comandos exactos, Archivo de salida y Stop point.
- `.claude/skills/final-audit/SKILL.md` — Skill de proyecto que orquesta el runbook sección a sección, un subagente a la vez, con los stop points obligatorios de cada sección.
- `docs/evaluations/oss-evaluators.md` — Evaluación comparativa de herramientas OSS (promptfoo, OpenSSF Scorecard, lychee, Ragas, DeepAudit), con criterios de selección, ventajas, limitaciones y «TOP recomendado».
- `docs/research/vulnerability-scanner-skill.md` — Revisión de la skill `security/vulnerability-scanner` del catálogo claude-code-templates: SKILL.md (128 líneas), referencias (107 + 97 líneas), CLI (descarga desde `main`, telemetría anónima con opt-out `CCT_NO_TRACKING=true`), herramientas complementarias (gitleaks, osv-scanner, pip-audit, zizmor, semgrep).

Archivos modificados:

- `docs/roadmap.md` — Sección «Final audit (after Phase C)» añadida; PL-13 corregida a «mergeada \| #68 \| 2026-11-22».
- `docs/sources.md` — 6 entradas nuevas: promptfoo, OpenSSF Scorecard, SonarQube Cloud, GitRoll, vulnerability-scanner skill (aitmpl.com + github.com/davila7), gitleaks/osv-scanner/pip-audit/zizmor/semgrep.

## Interfaz pública

- Skill: `.claude/skills/final-audit/SKILL.md` → el usuario escribe «ejecuta final-audit»; el orquestador lee el runbook y delega por secciones.
- Runbook: `docs/final-audit-checklist.md` → referencia de pasos, comandos y archivos de salida para la auditoría.
- Todo lo que se instala o almacena va en `D:\tools-eval\`; nada pesado en `C:`.

## Specs / RF que cubre

- S13 (documentación completa), S16 (seguridad del repo), S21 (revisión final), S22 (evidencia para la entrega del proyecto).
- No cubre RF/RNF de código: es solo documentación de proceso.

## Pruebas realizadas

Esta feature es docs-only (runbook + skill). El ciclo de QA aplica a:

- **Revisión manual del checklist:** verificado que ninguna sección del runbook ejecuta una instalación al leer el archivo (todos los `pip install`, `npm install`, etc. están dentro de bloques de código del runbook, que se ejecutarán en su momento por el subagente indicado).
- **Verificación de links internos:** `Select-String -Pattern '\[.*?\]\(((?!http)[^)]+)\)'` no devolvió ningún link roto.
- **Verificación de fuentes:** todos los comandos tienen URL de fuente en el texto o en `docs/sources.md`.
- `ruff check .`: `All checks passed!`
- `ruff format --check .`: `246 files already formatted`
- `mypy`: `Success: no issues found in 122 source files`
- `pytest -q`: `2093 passed, 2 skipped, 35 deselected in 84.76s`

## Resultados reales

```text
# 2026-11-24 — verificación de links internos
# Comando: Select-String -Path docs/final-audit-checklist.md -Pattern '\[.*?\]\((...)\)' | ...
# Resultado: (vacío — 0 links internos rotos)

# 2026-11-24 — verificación de comandos de instalación directa
# Comando: Select-String -Path docs/final-audit-checklist.md -Pattern "winget install|pip install|npm install|choco install|scoop install"
# Resultado: líneas dentro de bloques de código del runbook (secciones 1 y 2),
#            no ejecutadas al leer el archivo. ✓
```

## Cómo verificar (paso a paso)

1. `git checkout docs/final-audit-checklist && git log --oneline -3` — confirma los commits de la feature.
2. `Test-Path docs/final-audit-checklist.md` → `True`.
3. `Test-Path .claude/skills/final-audit/SKILL.md` → `True`.
4. `(Get-Content docs/final-audit-checklist.md | Measure-Object -Line).Lines` → 441 líneas.
5. `Get-Content docs/final-audit-checklist.md | Select-String "^# "` → 7 secciones (0 a 6).
6. CI verde en GitHub Actions.

## Decisiones

- **Solo documentación ahora, ejecución después de Fase C:** el runbook documenta el proceso completo sin ejecutar ninguna herramienta. Mantiene la separación entre planificación (esta PR) y ejecución (cuando Luis diga «ejecuta final-audit» tras la Fase C).
- **vulnerability-scanner se documenta, no se instala:** la skill complementaria se revisa y documenta en `docs/research/vulnerability-scanner-skill.md`, pero no se instala en `.claude/skills/` hasta el momento de la auditoría (sección 1.1 del runbook). Decisión de Luis (instrucción go del 2026-11-24).
- **Todo en `D:\`:** el runbook exige que todas las instalaciones y cachés de herramientas de auditoría vayan en `D:\tools-eval\`, con variables de entorno (`PIP_CACHE_DIR`, `HF_HOME`, `OLLAMA_MODELS`, etc.) definidas en `D:\tools-eval\env.ps1`. Fuentes en `docs/sources.md`.
- **Un subagente a la vez:** la RAM es limitada (7.8 GB); el runbook prohíbe dos procesos pesados en paralelo.

Ver Log del ODD: L41.

## Limitaciones

- El runbook no ejecuta ninguna herramienta; solo documenta los pasos y comandos.
- Algunos comandos están marcados `⚠ verify` (flags, nombres de assets de release, comportamiento en Windows) porque no se ejecutaron al escribirlos. Se verifican al ejecutar la auditoría.
- La sección 3 (SonarQube Cloud, GitRoll) requiere la intervención manual de Luis (OAuth, clics).
- DeepAudit (sección 2.6) requiere autorización explícita de Luis antes de correr.

## No verificado

- Que `npx claude-code-templates@latest --skill security/vulnerability-scanner` funcione en modo no interactivo (subagente sin TTY); alternativa: copiar los 3 archivos a mano desde GitHub.
- Nombres exactos de los assets de release de gitleaks, osv-scanner, scorecard y lychee en la fecha de ejecución (pueden cambiar entre versiones).
- Soporte nativo de Windows para semgrep (su README solo muestra Linux/macOS y pipx).
- Que `promptfoo eval` funcione con el shim `.cmd` de npm en Windows.
- Comportamiento del flag `--offline` de zizmor y el subcomando exacto (`audit` vs. la raíz).
