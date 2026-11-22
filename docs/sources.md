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
| MCP Python SDK | https://github.com/modelcontextprotocol/python-sdk | T18: SDK oficial `mcp==2.3.0`. |
| Migración del SDK a v2 (FastMCP renombrado a MCPServer) | https://py.sdk.modelcontextprotocol.io/v2/migration/#fastmcp-renamed-to-mcpserver | T18: en 2.x `mcp.server.fastmcp` ya no existe (lanza `ModuleNotFoundError` con este enlace). Se usa `from mcp.server.mcpserver import MCPServer`; verificado leyendo el paquete instalado (`server.py`): `@server.tool(name=, structured_output=)`, `run("stdio")`, `streamable_http_app(streamable_http_path=, host=, max_request_body_size=)` que devuelve una app Starlette (la servimos con uvicorn detrás de un middleware de API key), `ToolError` para errores esperados. Verificado además ejecutando un cliente real (`stdio_client` y `streamable_http_client`). La página de migración respondió HTTP 200 el 2026-11-21; su contenido no se leyó completo (no verificado). |

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

## Microsoft Fabric: conexión, Warehouse y notebook (T11)

Consultadas con WebFetch el 2026-11-21. "⚠" marca lo que las fuentes no confirman del todo.

| Título | URL | Para qué se usó |
| --- | --- | --- |
| Warehouse Connectivity (Microsoft Learn) | https://learn.microsoft.com/en-us/fabric/data-warehouse/connectivity | Aplica al SQL analytics endpoint y al Warehouse: endpoint TDS rotulado **SQL connection string**, puerto TCP 1433, solo usuarios y service principals de Microsoft Entra ID ("SQL Authentication isn't supported"), MARS no soportado, las conexiones inactivas se cierran a los 15 min y sin `InitialCatalog` se conecta a `master`. |
| How to Connect (Microsoft Learn) | https://learn.microsoft.com/en-us/fabric/data-warehouse/how-to-connect | Dónde se copia el host: **Settings** del warehouse o del SQL analytics endpoint > página **SQL connection string**; el nombre del item va como Initial Catalog/Database. "Use Microsoft Entra ID authentication. Only ODBC 18 or higher versions are supported." Host de ejemplo: `<unique identifier>.datawarehouse.fabric.microsoft.com`. |
| Microsoft Entra authentication in Fabric Data Warehouse (Microsoft Learn) | https://learn.microsoft.com/en-us/fabric/data-warehouse/entra-id-authentication | Para service principals el admin debe habilitar **Service principals can use Fabric APIs** (Developer settings) y dar acceso en el workspace. Cadenas ODBC 18 de ejemplo con `Authentication=ActiveDirectoryServicePrincipal` o `ActiveDirectoryInteractive`. |
| Service principals in Fabric Data Warehouse (Microsoft Learn) | https://learn.microsoft.com/en-us/fabric/data-warehouse/service-principals | Requisitos del service principal. Un SPN nuevo debe hacer primero una llamada a la REST API de Fabric para inicializar su token (sobre todo para `COPY INTO`/`OPENROWSET`). |
| Using Microsoft Entra ID with the ODBC Driver (Microsoft Learn) | https://learn.microsoft.com/en-us/sql/connect/odbc/using-azure-active-directory | Atributo pre-conexión `SQL_COPT_SS_ACCESS_TOKEN`: estructura `ACCESSTOKEN` (DWORD de longitud + bytes); el token se expande con un byte cero tras cada byte (UTF-16-LE de ASCII) y la longitud no incluye terminador. Con token, la cadena no puede llevar `UID`, `PWD`, `Authentication` ni `Trusted_Connection`. Valores de `Authentication` en ODBC: `ActiveDirectoryInteractive` (solo Windows), `ActiveDirectoryServicePrincipal` (17.7+), `ActiveDirectoryMsi` e `ActiveDirectoryIntegrated`. **`ActiveDirectoryDefault` no aparece en la lista del driver ODBC** (sí en el driver mssql-python). |
| ODBC DSN and Connection String Keywords (Microsoft Learn) | https://learn.microsoft.com/en-us/sql/connect/odbc/dsn-connection-string-attribute | El Driver 18 cifra por defecto (`Encrypt=yes`); formato `Server=tcp:<server>`; `SQL_COPT_SS_ACCESS_TOKEN` está disponible en Linux, macOS y Windows. La página no da el valor numérico del atributo. |
| SQL Server dialect: connecting with access tokens (SQLAlchemy docs) | https://docs.sqlalchemy.org/en/20/dialects/mssql.html | `SQL_COPT_SS_ACCESS_TOKEN = 1256` "defined in msodbcsql.h"; el token en UTF-16-LE se empaqueta con `struct.pack("<I...")` y se pasa en `attrs_before`. El valor 1256 se confirmó también en local: con ODBC Driver 18, `attrs_before={1256: ...}` más `Authentication=` hace que el driver responda `FA005 Cannot use Access Token with any of the following options: Authentication, ...`. |
| How to retrieve data from an SQL database using Python (Microsoft Q&A) | https://learn.microsoft.com/en-ca/answers/questions/5537089/how-to-retrieve-data-from-an-sql-database-using-py | Respuesta de un moderador voluntario, no documentación oficial: `SQL_COPT_SS_ACCESS_TOKEN = 1256`, scope `https://database.windows.net/.default` y `token.encode("utf-16-le")`. Solo como referencia secundaria. |
| Work with customer data in Microsoft Fabric (Microsoft Learn) | https://learn.microsoft.com/en-us/fabric/workload-development-kit/fabric-data-plane | Para conexiones SQL a un Warehouse el token se pide para el recurso de Azure SQL Database (scope delegado `https://database.windows.net//user_impersonation`). De aquí sale el recurso del scope `https://database.windows.net/.default`. ⚠ No verificado en un tenant real (T30). |
| Scopes and permissions: the `.default` scope (Microsoft identity platform) | https://learn.microsoft.com/en-us/entra/identity-platform/scopes-oidc | `{resource}/.default` es obligatorio en el flujo client credentials. Si un token se emite pero el recurso lo rechaza, Entra sugiere probar con doble barra (`https://database.windows.net//.default`). |
| azure.identity.DefaultAzureCredential (Azure SDK for Python) | https://learn.microsoft.com/en-us/python/api/azure-identity/azure.identity.defaultazurecredential | Orden de la cadena (variables de entorno, workload identity, managed identity, ..., Azure CLI, ...); `get_token(*scopes)` devuelve `AccessToken`; el navegador interactivo está excluido por defecto. Versión instalada: azure-identity 1.27.0. |
| pyodbc wiki: The pyodbc Module | https://github.com/mkleehammer/pyodbc/wiki/The-pyodbc-Module | `connect(..., autocommit=False, timeout=0, attrs_before=None, ...)`: `attrs_before` se aplica con SQLSetConnectAttr antes de conectar y acepta valores `bytes`; `timeout` fija SQL_ATTR_LOGIN_TIMEOUT; `drivers()` lista los drivers ODBC disponibles. |
| fabric-toolbox: pyodbc-dw-connectivity.py (Microsoft, enlazado desde Learn) | https://github.com/microsoft/fabric-toolbox/blob/d87627f96d7867d46e585f82fddb2f57c42d585d/data-warehousing/dw-connectivity/odbc/pyodbc-dw-connectivity.py | Alternativa oficial con `Authentication=ActiveDirectoryServicePrincipal` y `UID=<client_id>@<tenant_id>`. No se usó porque deja el secreto dentro de la cadena de conexión. |
| What is Fabric Data Warehouse? (Microsoft Learn) | https://learn.microsoft.com/en-us/fabric/data-warehouse/data-warehousing | **El endpoint es de solo lectura:** "With the SQL analytics endpoint, T-SQL commands can define and query data objects but not manipulate or modify the data." El Warehouse ofrece "full power and transactional capabilities (DDL and DML query support)" e `INSERT..SELECT`. Confirma la premisa de L3. |
| Data types in Fabric Data Warehouse (Microsoft Learn) | https://learn.microsoft.com/en-us/fabric/data-warehouse/data-types | Tipos del DDL: `varchar`/`char` (no hay `nvarchar`/`nchar`; se usa `varchar` con colación UTF-8), `datetime2` y `time` con máximo 6 decimales, sin `datetime`; `bit`, `int`, `bigint` y `float` soportados. Mapeo Delta→SQL endpoint: TIMESTAMP→datetime2, INT→int, DOUBLE→float, STRING→varchar(8000) con `Latin1_General_100_BIN2_UTF8`. |
| CREATE TABLE (Fabric Data Warehouse) (Microsoft Learn) | https://learn.microsoft.com/en-us/sql/t-sql/statements/create-table-azure-sql-data-warehouse?view=fabric | `datetime2(n)` exige precisión explícita de 0 a 6; las opciones de columna son solo `NULL`/`NOT NULL` y `COLLATE` (la sintaxis no tiene CHECK ni DEFAULT); `varchar(n)` se mide en bytes, n de 1 a 8000. |
| Primary, foreign, and unique keys (Microsoft Learn) | https://learn.microsoft.com/en-us/fabric/data-warehouse/table-constraints | PK solo con `NONCLUSTERED` y `NOT ENFORCED` y solo con `ALTER TABLE` (no en línea en `CREATE TABLE`); no hay constraints DEFAULT. |
| Tables in Fabric Data Warehouse (Microsoft Learn) | https://learn.microsoft.com/en-us/fabric/data-warehouse/tables | Colación por defecto `Latin1_General_100_BIN2_UTF8` (sensible a mayúsculas); IDENTITY soportado. |
| IDENTITY columns in Fabric Data Warehouse (Microsoft Learn) | https://learn.microsoft.com/en-us/fabric/data-warehouse/identity | IDENTITY solo con `bigint`, sin seed ni increment, valores únicos no secuenciales. No se usa: `ticket_id` lo genera la aplicación. |
| How to use notebooks (Microsoft Learn) | https://learn.microsoft.com/en-us/fabric/data-engineering/how-to-use-notebook | Fabric importa archivos `.ipynb` estándar desde el equipo local con la opción de importar del workspace. El lakehouse por defecto se fija con el pin del Lakehouse explorer y se monta en el directorio de trabajo; hay que reiniciar la sesión al cambiarlo. |
| Load data into your lakehouse with a notebook (Microsoft Learn) | https://learn.microsoft.com/en-us/fabric/data-engineering/lakehouse-notebook-load-data | Rutas relativas `Files/...` sobre el lakehouse por defecto ("Copy relative path for Spark") y escritura `df.write.mode("overwrite").format("delta").saveAsTable(nombre)`. |

## SQL portable y SQLite (T10)

| Título | URL | Para qué se usó |
| --- | --- | --- |
| sqlglot — `sqlglot.errors` (API docs) | https://sqlglot.com/sqlglot/errors.html | Validación de portabilidad en `tests/unit/test_sql_files.py`. `ErrorLevel` tiene IGNORE ("Ignore all errors"), WARN ("Log all errors"), RAISE ("Collect all errors and raise a single exception") e IMMEDIATE ("Immediately raise an exception on the first error found"); los errores llegan como `ParseError` con la lista `errors`. Se usa `error_level=ErrorLevel.RAISE`. Versión instalada y fijada: `sqlglot==30.33.0` (comprobado en `.venv`). |
| CAST and CONVERT (Transact-SQL) — Microsoft Learn | https://learn.microsoft.com/en-us/sql/t-sql/functions/cast-and-convert-transact-sql | Aplica al SQL analytics endpoint y al Warehouse de Fabric. El estilo 121 (`yyyy-MM-dd HH:mm:ss.fff`) es el predeterminado para **datetime2**; `07_efecto_quincena.sql` usa `SUBSTRING(CAST(fecha_apertura AS VARCHAR(19)), 9, 2)` para el día del mes. ⚠ Verificar en T29 que la columna Delta llegue al endpoint como datetime2 (con **datetime** el estilo predeterminado es 0 y la consulta fallaría). |
| SQLite — Built-in scalar SQL functions | https://sqlite.org/lang_corefunc.html | "substring() is an alias for substr() beginning with SQLite version 3.34" (el `.venv` trae SQLite 3.45.3). `round(X,Y)` devuelve un número de punto flotante. |

## Ingestión y chunking (T13)

| Título | URL | Para qué se usó |
| --- | --- | --- |
| pypdf — Extract Text from a PDF | https://pypdf.readthedocs.io/en/stable/user/extract-text.html | `src/ingestion/documents.py`: `PdfReader(path)`, `reader.pages` y `page.extract_text()`. Comprobado con pypdf 7.1.1 instalado: `PdfReader.metadata` expone `title`, `modification_date` y `creation_date`; los errores de lectura heredan de `pypdf.errors.PyPdfError`; `PdfWriter.add_blank_page(width, height)` crea la página sin texto del test. El PDF con texto del test se escribe a mano (xref calculado), sin binarios versionados. |


## Embeddings y base vectorial (T14)

| Título | URL | Para qué se usó |
| --- | --- | --- |
| FastEmbed — Supported Models | https://qdrant.github.io/fastembed/examples/Supported_Models/ | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` está soportado: 384 dimensiones, multilingüe, 0.22 GB. Comprobado con fastembed 0.9.1 instalado (`TextEmbedding.list_supported_models()`): trunca la entrada a 128 tokens y no usa prefijos de consulta/documento. `TextEmbedding(model_name, cache_dir)`; `embed` y `query_embed` devuelven generadores de `numpy.ndarray` float32 sin normalizar; `get_embedding_size(model)` da la dimensión sin cargar el modelo. Descarga real: ~241 MB en disco, ~60 s. |
| Chroma — Configure (collections) | https://docs.trychroma.com/docs/collections/configure | En 1.x el espacio se declara con `configuration={"hnsw": {"space": "cosine"}}`; distancia coseno `d = 1 - cos(A, B)`. Comprobado con chromadb 1.5.9: la clave antigua de metadata `hnsw:space` también funciona, `query` devuelve distancias en 0..2 y el nombre de colección necesita 3–512 caracteres. |
| Chroma — Metadata filtering | https://docs.trychroma.com/docs/querying-collections/metadata-filtering | `where={"campo": "valor"}` equivale a `$eq`; varias condiciones se combinan con `{"$and": [...]}` (así lo traduce `chroma_where`). |
| Chroma — Python client reference | https://docs.trychroma.com/reference/python/client | `PersistentClient(path, settings, tenant, database)`: "This client is intended for local development and testing. For production, prefer a server-backed Chroma instance." La documentación oficial no dice nada sobre varios procesos con la misma ruta. Comprobado con 1.5.9: un segundo cliente en la misma ruta con otros `Settings` falla, `Client.close()` libera los archivos y, en Windows, un índice abierto no se puede renombrar ni borrar (WinError 32). |
| Chroma Cookbook — System constraints (Amikos Tech, colaboradores de Chroma; no es la documentación oficial) | https://cookbook.chromadb.dev/core/system_constraints/ | "Chroma is thread-safe" y "Chroma is not process-safe for concurrent writers sharing the same local persistence path". Por eso RF-15 usa directorios versionados y un puntero `CURRENT` atómico: ningún proceso escribe donde otro lee. |
| Python — `os.replace` | https://docs.python.org/3/library/os.html#os.replace | "If *dst* exists and is a file, it will be replaced silently if the user has permission" y "If successful, the renaming will be an atomic operation (this is a POSIX requirement)". Se usa para publicar el puntero `CURRENT`; la atomicidad solo está documentada para POSIX, así que en Windows el lector tolera un puntero ausente o inválido y `write_current` reintenta si el archivo está en uso. |

Las URLs de abajo respondieron con WebFetch el 2026-11-21. Todavía no se usaron: cada tarea debe confirmar el detalle técnico y pasar la fila a su sección.

| Tecnología | URL | Tarea | Nota |
| --- | --- | --- | --- |
| OpenAPI para Copilot Studio (REST API tools) | https://learn.microsoft.com/microsoft-copilot-studio/agent-extend-action-rest-api | T19 | Función en preview. La página dice que la especificación debe ser OpenAPI v2 en JSON y que una v3 se traduce automáticamente a v2. Hay que confirmarlo al generar `openapi.yaml`. |
| Microsoft dev tunnels | https://learn.microsoft.com/azure/developer/dev-tunnels/overview | T25 | Exponer la API con una URL pública (Fase B/C). Está en public preview; los comandos de la CLI no están verificados. |

## Nombres de ramas y commits

| Título | URL | Para qué se usó |
| --- | --- | --- |
| Conventional Commits 1.0.0 | https://www.conventionalcommits.org/en/v1.0.0/ | Formato `<type>[scope]: <description>`, tipos `feat`/`fix` obligatorios, `!` y `BREAKING CHANGE`, relación con SemVer. Verificada 2026-11-21: responde. Ver `docs/research/branch-and-feature-naming.md`. |
| Conventional Branch | https://conventional-branch.github.io/ | Formato `<type>/<description>`, prefijos `feat/`, `fix/`, `hotfix/`, `release/`, `chore/` y reglas de caracteres. Verificada 2026-11-21: redirige (301) a https://conventionalbranch.org/. |

## API REST (T16)

Comportamiento verificado ejecutando FastAPI 0.165.0, Starlette 1.10.0 y uvicorn 0.54.0 instalados (scratch con TestClient y `main.py serve` real), no solo leyendo documentación.

| Tema | URL | Qué se confirmó |
| --- | --- | --- |
| Dependencias de seguridad (`APIKeyHeader`, `Security`) | https://fastapi.tiangolo.com/reference/security/ | `auto_error=False` deja el control del 401 a la app y declara el esquema `apiKey` en OpenAPI. |
| Manejadores de excepciones | https://fastapi.tiangolo.com/tutorial/handling-errors/ | `RequestValidationError` y `HTTPException` de Starlette se reemplazan con `add_exception_handler`. |
| `uvicorn.run` | https://www.uvicorn.org/settings/ | Con `log_config=None` los logs de uvicorn se propagan al logging JSON del proyecto; `access_log=False` y `server_header=False` verificados con la firma instalada. |
| SQLite `mode=ro` | https://www.sqlite.org/uri.html | URI `file:...?mode=ro` abre solo lectura y no crea el archivo si falta (verificado). |

## Requisitos OpenAPI de Copilot Studio (T19)

| Título | URL | Qué se confirmó (consulta 2026-11-21) |
| --- | --- | --- |
| Extend your agent with tools from a REST API (preview) | https://learn.microsoft.com/microsoft-copilot-studio/agent-extend-action-rest-api | Debe ser JSON en v2; una v3 se traduce a v2. Autenticación None / API key (Header o Query) / OAuth 2.0. Descripciones vacías de parámetros bloquean el asistente. Preview. Ver `docs/research/copilot-studio-openapi-requirements.md`. |
| Create a custom connector from an OpenAPI definition | https://learn.microsoft.com/connectors/custom-connectors/define-openapi-definition | Menos de 1 MB; solo OpenAPI 2.0 ("3.0 not supported"); ejemplo con `schemes: [https]`, `securityDefinitions` apiKey in header y `operationId`; con varias definiciones de seguridad se toma la primera. |
