# Fuentes

Registro de todas las fuentes consultadas en DeskPilot AI (S19). Cada tecnología investigada debe tener aquí su entrada; los subagentes agregan cada fuente nueva que consulten.

Verificación de URLs: cada enlace externo se abrió con WebFetch el 2026-11-21. Si la URL redirige, se anota el destino; la URL original no se cambia.

## Metodología y estructura

| Título | URL | Para qué se usó |
| --- | --- | --- |
| Estructura de repo "production-style RAG project" (publicación de LinkedIn compartida por el usuario) | No disponible (texto pegado por el usuario) | Estructura de archivos raíz, `src/`, `tests/`, `logs/` y `main.py`. Ver la nota de mapeo más abajo. Texto literal en `docs/odd/deskpilot-ai.md`, L2, mensaje 3. |
| ODD vs SDD: Organic vs Spec Driven Development con IA (Web Reactiva) | https://www.webreactiva.com/blog/odd-vs-sdd | Protocolo ODD de 7 pasos, documento de feature, prueba del diff, verificador independiente. Verificada: responde y lista los 7 pasos. |
| Gentle-AI (Gentleman Programming) | https://github.com/Gentleman-Programming/gentle-ai | Origen de ODD. Verificada: responde y menciona Organic Driven Development. |
| Building effective agents (Anthropic) | https://www.anthropic.com/research/building-effective-agents | Patrón orquestador-trabajadores y diseño de herramientas para agentes. Verificada: responde. |
| Lewis et al. 2020, Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks | https://arxiv.org/abs/2005.11401 | Fundamento del pipeline RAG. Verificada: responde. |

### Nota: mapeo de la publicación de LinkedIn al repo

Los 17 elementos de la publicación se conservan con el mismo nombre:

| # | Elemento de la publicación | En este repo |
| --- | --- | --- |
| 1 | README.md | `README.md` |
| 2 | requirements.txt | `requirements.txt` (versiones fijadas y verificadas) |
| 3 | env | `.env` solo en local, ignorado por git; se versiona `.env.example` |
| 4 | gitignore | `.gitignore` |
| 5 | config.yaml | `config.yaml` |
| 6–14 | ingestion/, chunking/, embeddings/, vectordb/, retrieval/, prompts/, llm/, api/, utils/ | `src/<carpeta>/`, cada una con `__init__.py` y `README.md` |
| 15 | tests/ | `tests/` con `unit/`, `integration/`, `e2e/` y `eval/` |
| 16 | logs/ | `logs/` (solo `.gitkeep`; los `.log` se ignoran) |
| 17 | main.py | `main.py` (CLI: generate-data, load-db, index, serve, eval, export-openapi) |

Lo que agregó el usuario (L2) como estándar de producción, únicas adiciones permitidas en la raíz:
- Carpetas: `data/` (knowledge_base, sample, raw, vectordb), `integrations/` (fabric, copilot_studio), `docs/` (odd, adr, screenshots), `scripts/`, `.github/`, `.claude/agents/`.
- Archivos: `.env.example`, `requirements-dev.txt`, `pyproject.toml` (solo configuración de herramientas), `Dockerfile`, `.dockerignore`, `LICENSE`, `CHANGELOG.md`, `CONTRIBUTING.md`, `CLAUDE.md`.

## Fuente interna

| Título | URL | Para qué se usó |
| --- | --- | --- |
| DeskPilot AI · Documento de requerimientos v1.0 (del usuario) | `docs/requirements.md` | Requerimientos normativos (RF, RNF, RN, HU, métricas). Se guardó sin cambios (S23). La trazabilidad a tareas está en `docs/odd/deskpilot-ai.md`, L4. |

## Claude Code

| Título | URL | Para qué se usó |
| --- | --- | --- |
| Claude Code: Create custom subagents | https://code.claude.com/docs/en/sub-agents | Formato de los subagentes en `.claude/agents/`: frontmatter YAML con `name` y `description` obligatorios y `tools` opcional (T2). Verificada: responde. |

## Microsoft

| Título | URL | Para qué se usó |
| --- | --- | --- |
| Microsoft Fabric trial capacity (Microsoft Learn) | https://learn.microsoft.com/fabric/get-started/fabric-trial | Prueba gratuita de 60 días de Fabric. Verificada: responde, pero la URL canónica de la página es https://learn.microsoft.com/en-us/fabric/fundamentals/fabric-trial (redirige). |
| Sign up for a Copilot Studio trial (Microsoft Learn) | https://learn.microsoft.com/microsoft-copilot-studio/sign-up-individual | Prueba de Copilot Studio y sus limitaciones (no permite publicar; requiere cuenta de trabajo o escuela). Verificada: redirige a "Get access to Copilot Studio", URL canónica https://learn.microsoft.com/en-us/microsoft-copilot-studio/requirements-licensing-subscriptions. |

## MCP

| Título | URL | Para qué se usó |
| --- | --- | --- |
| Model Context Protocol specification | https://modelcontextprotocol.io/specification/latest | Servidor MCP con herramientas. Verificada: responde; hoy "latest" apunta a la revisión 2026-07-28. |

## Base del repo (T2/T3)

| Título | URL | Para qué se usó |
| --- | --- | --- |
| actions/checkout (GitHub) | https://github.com/actions/checkout | Versión `actions/checkout@v7` en `.github/workflows/ci.yml`. Verificada: los ejemplos usan v7. |
| actions/setup-python (GitHub) | https://github.com/actions/setup-python | Versión `actions/setup-python@v7` y opciones `cache: pip` y `cache-dependency-path` en CI. Verificada. |
| fastembed (qdrant/fastembed) | https://github.com/qdrant/fastembed | Librería de embeddings locales sin llaves. Verificada: responde. |
| FastEmbed: Supported Models | https://qdrant.github.io/fastembed/examples/Supported_Models/ | Catálogo de modelos; `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (el de `config.yaml`) aparece en la lista. La carga real se confirma ejecutando en T14. |
| PyPI — versiones verificadas con pip freeze el 2026-11-21 | https://pypi.org/ | Origen de cada dependencia fijada en `requirements.txt` y `requirements-dev.txt`. Instaladas en `.venv` (Python 3.13.2) y fijadas con la salida de `pip freeze`. Ejemplo comprobado: https://pypi.org/project/fastembed/ muestra 0.9.1 como versión actual. |
| pydantic-settings (Pydantic docs) | https://pydantic.dev/docs/validation/latest/concepts/pydantic_settings/ | T8: carga de secretos y del modo desde variables de entorno y `.env` con `SecretStr`. |
| python-stdnum — `stdnum/mx/curp.py` | https://github.com/arthurdejong/python-stdnum/blob/master/stdnum/mx/curp.py | T8: lista de claves de estado para la regex de CURP en `src/utils/redaction.py`. No verificado contra el instructivo oficial de RENAPO (DOF); no se valida el dígito verificador. |

## Fuentes por agregar en tareas siguientes

Las URLs de abajo respondieron con WebFetch el 2026-11-21. Todavía no se usaron: cada tarea debe confirmar el detalle técnico y pasar la fila a su sección.

| Tecnología | URL | Tarea | Nota |
| --- | --- | --- | --- |
| ChromaDB | https://docs.trychroma.com/ | T14 | Cliente persistente local. Falta confirmar la API exacta y el comportamiento con dos procesos (RF-15). |
| MCP Python SDK | https://github.com/modelcontextprotocol/python-sdk | T18 | SDK oficial ("Python SDK for Model Context Protocol servers and clients"). |
| FastMCP | (por verificar en T18) | T18 | La página del repo del SDK no menciona FastMCP. Hay que confirmar con `mcp==2.3.0` instalado cuál es la API para declarar herramientas y montar el servidor por HTTP. |
| Conexión al SQL analytics endpoint y al Warehouse de Fabric | https://learn.microsoft.com/fabric/data-warehouse/connectivity | T11 | "Warehouse Connectivity": endpoint TDS en el puerto 1433, solo autenticación Microsoft Entra ID (sin SQL auth), MARS no soportado. Falta el ejemplo de conexión con pyodbc/azure-identity y la confirmación de que el endpoint es de solo lectura. |
| OpenAPI para Copilot Studio (REST API tools) | https://learn.microsoft.com/microsoft-copilot-studio/agent-extend-action-rest-api | T19 | Función en preview. La página dice que la especificación debe ser OpenAPI v2 en JSON y que una v3 se traduce automáticamente a v2. Hay que confirmarlo al generar `openapi.yaml`. |
| Microsoft dev tunnels | https://learn.microsoft.com/azure/developer/dev-tunnels/overview | T25 | Exponer la API con una URL pública (Fase B/C). Está en public preview; los comandos de la CLI no están verificados. |
