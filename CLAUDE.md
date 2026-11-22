# CLAUDE.md — DeskPilot AI

Agente L1 de Service Desk para un banco ficticio ("Banco Altiplano"): Copilot Studio + Microsoft Fabric + API RAG (FastAPI, MCP).
Proyecto de portafolio para la vacante AI Developer Trainee; corre en modo local sin llaves de pago.

## Fuente de verdad (léela antes de actuar)
- `docs/odd/deskpilot-ai.md`: Specs (S#), Tasks (T#) y Log (L1–L4). Manda sobre cualquier resumen.
- `docs/requirements.md`: requerimientos v1.0, normativos. No se modifican.

## ODD (Organic Driven Development)
1. Autorizar: preguntas y revisiones son de solo lectura; no edites si no te lo piden.
2. Explorar: lee código y requisitos en proporción a la tarea.
3. Resolver incertidumbre: investiga; máximo una pregunta por decisión real; lo demás se decide y se anota en el Log.
4. Clasificar: pequeño o grande por riesgo y capacidad de retomar. Prueba del diff: si se retoma con el pedido + `git diff`, es pequeño.
5. Registrar antes de escribir: si es grande, primero el documento de feature.
6. Implementar tarea por tarea: test primero (RED → GREEN → REFACTOR); commits de ≤400 líneas.
7. Cerrar: reporta solo lo verificado, lo que falló y lo pendiente.

## Todo por subagentes
- El agente principal solo orquesta: lee y actualiza el doc ODD, asigna tareas, integra, hace commits/PR y reporta. No implementa.
- Un subagente a la vez, nunca en paralelo. Definiciones en `.claude/agents/` (8 roles).
- Cada subagente recibe la ruta `docs/odd/deskpilot-ai.md` y el ID de su tarea (nunca un resumen), más los archivos que puede tocar.
- Fallback (L3): si el rol no aparece como tipo, usa `general-purpose` con "lee `.claude/agents/<rol>.md` y actúa con ese rol".
- Tareas [ALTO RIESGO] terminan con revisión de `security-verifier` (solo lectura) antes del commit.

## Reglas del proyecto
- Git: desde T8 todo entra por PR (issue → rama `feat/tNN-nombre` → conventional commits en inglés → PR con plantilla → `gh pr merge --merge`). Nunca push directo a main.
- Cero desorden: nada fuera de la estructura; lo experimental va en `scratch/` (ignorado) y se borra al cerrar la tarea.
- Cero secretos: `.env` solo local; en el repo únicamente `.env.example` con placeholders.
- Cero alucinación: verifica en docs oficiales y ejecutando; cada fuente nueva va a `docs/sources.md`; lo no verificado se reporta como "no verificado".
- Datos 100% sintéticos (banco ficticio "Banco Altiplano"); nada real de bancos ni de Stefanini.
- Español en docs y conversación; código y commits en inglés.

## Estructura (L2)
- Raíz: README.md, requirements.txt, requirements-dev.txt, .env.example, .gitignore, config.yaml, main.py, pyproject.toml (solo herramientas), Dockerfile, .dockerignore, LICENSE, CHANGELOG.md, CONTRIBUTING.md, CLAUDE.md.
- `src/`: ingestion, chunking, embeddings, vectordb, retrieval, prompts, llm, api, utils (cada una con `__init__.py` y README.md).
- `tests/`: unit, integration, e2e, eval. `logs/`: solo .gitkeep.
- `data/`: knowledge_base, sample, raw (ignorado), vectordb (ignorado).
- `integrations/`: fabric (notebooks, sql) y copilot_studio. `docs/`: odd, adr, screenshots + documentos.
- `scripts/`, `.github/` (workflows, plantillas), `.claude/agents/`. Ninguna otra carpeta en la raíz.

## Comandos (PowerShell)
```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
ruff check .; ruff format --check .
mypy src main.py tests
pytest --cov=src --cov-report=term-missing
python main.py generate-data | load-db | index | serve | eval | export-openapi
```
