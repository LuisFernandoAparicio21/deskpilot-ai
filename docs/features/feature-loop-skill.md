# Skill feature-loop (PL-12)

Feature PL-12 (rama `feat/feature-loop-skill`). Skill de proyecto que automatiza el ciclo a–f por feature. Investigación: [docs/research/project-skills.md](../research/project-skills.md).

## Qué es
`.claude/skills/feature-loop/SKILL.md` es una skill de Claude Code que guía al agente principal (orquestador) por el ciclo: a) branching, b) desarrollo, c) testing independiente, d) verificación, e) documentación, f) merge. Delega todo a los subagentes de `.claude/agents/`.

## Cómo se usa
1. Inicia Claude Code en el repo (o ejecuta `/reload-skills`).
2. Escribe `/feature-loop <nombre o # de la feature>` (por ejemplo `/feature-loop PL-12`).
3. Si la feature no está en `docs/roadmap.md`, la skill se detiene y pide aclaración.
4. Tras cada paso verás una línea de avance: `F# <feature> · paso c ✓ · N tests, 0 fallos`.
5. Tras cada merge, roadmap y Log del ODD quedan al día para retomar.

## Argumentos
`$ARGUMENTS` = nombre o # de la feature del roadmap. `argument-hint` lo muestra al autocompletar.

## Archivos
- `.claude/skills/feature-loop/SKILL.md`: reglas y pasos (< 500 líneas).
- `templates/feature-doc.md` (incluye "Pruebas realizadas"), `templates/pr-checklist.md` (seis secciones de la plantilla del PR + ítems a-f): plantillas de apoyo.
- `reference/agents.md`, `reference/branch-naming.md`: tabla de roles y resumen del estándar de ramas.

Frontmatter usado (todo documentado): `name`, `description`, `argument-hint`, `disable-model-invocation: true` (solo manual, para que un ciclo con merges no se dispare solo).

## Límites
Verificado en la documentación oficial (consulta 2026-11-22): ubicación `.claude/skills/<nombre>/SKILL.md`, campos de frontmatter, `$ARGUMENTS`, archivos de apoyo por referencia, límite de 500 líneas y de 1,536 caracteres en descripción.

- ⚠ no confirmado: que el cuerpo de una skill pueda pedir al agente principal usar la herramienta Agent con un subagente de `.claude/agents/` (la documentación solo trata `context: fork` + `agent`). Por eso la skill no usa `context: fork`.
- ⚠ no confirmado: que una carpeta `.claude/skills/` nueva creada a mitad de sesión se detecte; usa `/reload-skills` o reinicia.
- No verificado: ejecución real de un ciclo completo con la skill.

## Cómo probarla en seco
1. Reinicia Claude Code en el repo y ejecuta `/skills`: debe aparecer `feature-loop`.
2. `/feature-loop inexistente-xyz`: debe detenerse y pedir aclaración sin crear ramas.
3. `/feature-loop PL-12` en una rama de prueba y pídele solo el paso a; revisa que delegue a un subagente y emita la línea de avance. Descarta la rama después.
4. Opcional: `/skill-doctor` para ver el costo de contexto.

## Prueba en seco (2026-11-22)
- La sesión de Claude Code ya abierta NO detecta una carpeta `.claude/skills/` nueva (`Unknown skill: feature-loop`); una sesión nueva sí la carga (Claude Code 2.1.285).
- Por ser `disable-model-invocation: true`, la skill no aparece en la lista que ve el modelo; se invoca escribiendo `/feature-loop <feature>` en el prompt de Claude Code.
- Prueba real con una sesión nueva (`claude -p "/feature-loop PL-999 feature-that-does-not-exist"`, solo herramientas de lectura): leyó `docs/roadmap.md`, aplicó la regla de entrada (la feature no existe) y se detuvo pidiendo aclaración, sin crear rama, issue ni subagentes.
- Ojo en Git Bash: `/feature-loop` se convierte en una ruta de Windows; escribe el comando desde el prompt de Claude Code, no desde un shell.
- Las delegaciones a subagentes (pasos a–f completos) las ejercita el uso real del ciclo; la delegación desde el cuerpo de una skill sigue marcada como no confirmada en la documentación oficial, pero el propio ciclo del proyecto ya funciona delegando con la herramienta Agent.

