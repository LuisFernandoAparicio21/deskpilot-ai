# Formato de una skill de proyecto de Claude Code

## Pregunta
¿Cuál es el formato vigente de una skill de PROYECTO (ubicación, frontmatter, invocación, argumentos, archivos de apoyo, delegación a subagentes, verificación y límites)?

## Respuesta
(a) **Ubicación**: `.claude/skills/<nombre>/SKILL.md` en el repo; carga en sesiones iniciadas en ese repo y se comparte al commitearla. Los cambios en `~/.claude/skills/`, `.claude/skills/` o `--add-dir` se detectan en la sesión sin reiniciar. ⚠ no confirmado: si crear una carpeta `.claude/skills/` nueva a mitad de sesión se detecta; usar `/reload-skills` o reiniciar.

(b) **Frontmatter** (YAML entre `---` en la primera línea; todos opcionales, `description` recomendada):
- `name` (por defecto, nombre de la carpeta; define `/name`), `description`, `when_to_use` (se anexa a `description`).
- `argument-hint`, `arguments` (nombrados, lista o texto con espacios), `disable-model-invocation` (def. false), `user-invocable` (def. true).
- `allowed-tools` (preaprueba solo para ese turno; texto separado por espacios/comas o lista), `disallowed-tools`.
- `model` (o `inherit`), `effort` (low, medium, high, xhigh, max).
- `context` (`fork`), `agent` (`Explore`, `Plan`, `general-purpose` o un agente de `.claude/agents/`), `background` (con fork; def. true).
- `hooks`, `paths` (globs de activación), `shell` (`bash` o `powershell`), `metadata`, `license`, `compatibility` (máx. 500 caracteres; Claude Code los acepta y no actúa).
- **Reglas de nombre**: la página NO declara longitud máxima ni patrón positivo (⚠ no confirmado el límite de 64 caracteres/minúsculas de la spec Agent Skills). Solo rechaza: espacio de ancho cero o carácter de control, caracteres de uso privado o sin asignar, modificadores de dirección del texto, espacios que no sean uno simple entre palabras, y `<` o `>`. Recomendación propia: kebab-case en minúsculas.

(c) **Invocación**: manual con `/nombre args` al inicio del mensaje; automática cuando la `description` encaja con la conversación (salvo `disable-model-invocation: true`). Argumentos: `$ARGUMENTS` (todo), `$ARGUMENTS[N]` o `$N` (base 0), `$nombre` (de `arguments`). Variables: `${CLAUDE_SKILL_DIR}`, `${CLAUDE_PROJECT_DIR}`, `${CLAUDE_SESSION_ID}`, `${CLAUDE_EFFORT}`. Inyección dinámica con `` !`comando` `` o bloque ```` ```! ````. Se pueden apilar hasta 6 skills al inicio del mensaje.

(d) **Archivos de apoyo**: viven en la carpeta de la skill (`reference.md`, `examples.md`, `scripts/...`); se referencian con un enlace relativo desde `SKILL.md` y se cargan bajo demanda. Solo los archivos cargados cuentan en el contexto.

(e) **Subagentes**: documentado `context: fork` + `agent: <tipo>`; el cuerpo de la skill pasa a ser el prompt del subagente, sin historial de conversación; se admiten agentes personalizados de `.claude/agents/`. `background: false` para esperar el resultado en el mismo turno. Lo inverso (subagente que precarga skills) usa el campo `skills` de los subagentes (detalle en sub-agents, ⚠ no leído). ⚠ no confirmado: que el cuerpo de una skill pueda pedir al agente principal usar la herramienta Agent con un subagente (la página no lo trata).

(f) **Verificación**: `/skills` abre el menú con todas las skills cargadas. Además `/skill-doctor` (v2.1.252+) muestra costo de contexto y frecuencia de uso, y `/reload-skills` recarga. `skillOverrides` en `.claude/settings.local.json` (`on`, `name-only`, `user-invocable-only`, `off`) y reglas `Skill(nombre)` en `/permissions` controlan el acceso.

(g) **Límites**: `SKILL.md` por debajo de 500 líneas (el resto, en archivos de apoyo). `description` + `when_to_use` se truncan a 1,536 caracteres en el listado (lo importante primero; sin tope propio de `description`). Las descripciones cargan en cada turno; el contenido completo solo al invocar. Tras la compactación se conservan los primeros 5,000 tokens de cada skill dentro de un presupuesto combinado de 25,000 tokens.

## Verificación en esta instalación (2026-11-22)
- `claude --version`: 2.1.285 (Claude Code).
- `~/.claude/skills`: 21st-ai, 21st-ui-build, 21st-ui-review, apply-job, aprende, aws-s3-security, aws-s3-troubleshoot, aws-serverless-eda, aws-ses, aws-solution-architect, caveman, deploy-to-vercel-v2, git-workflow, graphify, react-doctor, react-expert, react-nextjs-development, scikit-learn, senior-data-engineer, synced, the-homepage, ui-ux-pro-max, ui-ux-pro-max-skill, vercel-composition-patterns; enlaces: archify, dbt-data-transformation, sqlserver-expert.
- `.claude/skills` del proyecto: no existe todavía.

## Decisión recomendada
Crear `.claude/skills/feature-loop/SKILL.md` con `name`, `description` (clave primero, <1,536 caracteres), `argument-hint` y, si debe ser solo manual, `disable-model-invocation: true`. Para delegar a un rol de `.claude/agents/`, usar `context: fork` + `agent: <rol>` con `background: false`, o dejar que la skill oriente al agente principal (esto último ⚠ no confirmado en la documentación). Verificar con `/skills` tras `/reload-skills`.

## Fuentes (consulta 2026-11-22)
- Extend Claude with skills (Claude Code Docs): https://code.claude.com/docs/en/skills
- Create custom subagents (referenciada, no releída): https://code.claude.com/docs/en/sub-agents
