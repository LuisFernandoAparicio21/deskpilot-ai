# Cómo contribuir a DeskPilot AI

Gracias por tu interés. Este proyecto sigue un flujo ODD (documento de feature en `docs/odd/deskpilot-ai.md`) y todo cambio entra por pull request.

## Requisitos

- Python 3.13 (el código apunta a compatibilidad con 3.11+).
- Git y, opcionalmente, GitHub CLI (`gh`).
- Para el modo fabric: ODBC Driver 18 for SQL Server.

## Preparar el entorno (PowerShell)

```powershell
git clone <url-del-repo>
cd deskpilot-ai
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
Copy-Item .env.example .env   # luego llena solo las variables que uses
```

Si PowerShell bloquea la activación del venv, ejecuta una vez
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

## Flujo de trabajo (ODD)

1. **Issue:** crea un issue con la plantilla "Tarea" (objetivo, criterios de aceptación, specs/RF que cubre).
2. **Rama:** desde `main` actualizado, crea `feat/tNN-nombre-corto` (por ejemplo `feat/t09-ticket-generator`).
3. **Commits:** pequeños (≤400 líneas cada uno), en inglés y con [Conventional Commits](https://www.conventionalcommits.org/es/v1.0.0/): `feat:`, `fix:`, `test:`, `docs:`, `chore:`, `refactor:`, `ci:`.
4. **Pruebas primero** cuando el resultado esperado está claro (RED → GREEN → REFACTOR).
5. **Pull request:** usa la plantilla completa (Qué cambia, Por qué, Cómo se probó, Salida relevante, Checklist, `Closes #n`). El CI debe quedar en verde.
6. **Merge:** `gh pr merge --merge --delete-branch` (se conservan los commits y se borra la rama). Nunca se hace push directo a `main`.

Lo experimental va en `scratch/` (ignorado por git) y se borra al cerrar la tarea. Cada PR toca solo los archivos de su tarea.

## Estructura de docs/ y tests/

- `docs/odd/`: documento ODD (specs, tasks y log). `docs/adr/`: decisiones de arquitectura.
- `docs/features/`: un documento por feature (qué cambió, resultados, cómo verificar, limitaciones).
- `docs/research/`: investigaciones previas a cada feature. `docs/screenshots/`: capturas.
- `.claude/skills/`: skills de proyecto (`feature-loop`, ciclo a–f; se usa con `/feature-loop <feature>`).
- `tests/unit/`, `tests/integration/`, `tests/e2e/` y `tests/eval/` (casos y resultados de la evaluación).
  Los módulos de test deben tener nombres únicos entre carpetas (mypy los analiza todos juntos).

## Comandos de calidad

Los mismos que corre el CI; deben pasar antes de abrir el PR:

```powershell
ruff check .
ruff format --check .
mypy
pytest --cov=src --cov-report=term-missing
```

Para corregir formato e imports automáticamente: `ruff format .` y `ruff check --fix .`.

## Seguridad y datos

- Nunca subas `.env` ni secretos; solo `.env.example` con placeholders.
- Todos los datos son sintéticos ("Banco Altiplano" es ficticio). No agregues datos reales de personas, bancos ni empresas.
