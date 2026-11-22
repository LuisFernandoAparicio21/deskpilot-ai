# API REST (T16, T17)

> Datos sintéticos generados para este proyecto; las cifras son ilustrativas. "Banco Altiplano" es ficticio.

## Qué hace

Servicio FastAPI (`src/api`, arranque con `python main.py serve`) que expone las herramientas del agente para Copilot Studio:

| Endpoint | Auth | Función |
|---|---|---|
| `GET /health` | anónimo | Solo devuelve `status` (`ok` / `degraded`); sondeo cacheado. |
| `POST /buscar_solucion` | `X-API-Key` | Búsqueda RAG en la base de conocimiento (`query`, `categoria` opcional). |
| `POST /tickets` | `X-API-Key` | Crea un ticket (`crear_ticket`, T17); ver [crear-ticket.md](crear-ticket.md). |
| `GET /tickets/{ticket_id}` | `X-API-Key` | Estado de un ticket (`consultar_estado_ticket`). |
| `GET /metricas?area=` o `?sucursal=` | `X-API-Key` | Métricas de un área o sucursal (`metricas_area`). |

Características: llave comparada en tiempo constante, errores JSON uniformes con `request_id`, validación estricta (límites de longitud, enums, caracteres de control, `extra="forbid"`), límite de cuerpo (`api.max_body_bytes`, 413), timeout por petición (`api.request_timeout_s`, 504), repositorio SQLite o Fabric inyectado, y `/docs`, `/redoc` y `/openapi.json` apagados.

## Specs y requerimientos que cubre

- S8 (API REST) y S17 (seguridad de la API).
- RF-17 (consultar estado de ticket), RF-19 (métricas por área/sucursal), RF-26 (health check).
- RNF-02 (X-API-Key obligatoria), RNF-03 (sin secretos en el repo), RNF-04 (validación estricta), RNF-05 (logs sin secretos ni datos personales), RNF-06 (errores consistentes).

## Pruebas realizadas

224 tests de la API (ejecución real del 2026-11-21 en `feat/t16-api-rest`):

| Archivo | Tests | Qué valida |
|---|---|---|
| `tests/unit/test_api_security.py` | 35 | 401 sin llave o con llave incorrecta, 401 antes que 422, comparación en tiempo constante (`keys_match`, tope de bytes), la llave nunca aparece en logs. |
| `tests/unit/test_api_validation.py` | 90 | Límites de `query`, categorías conocidas, caracteres de control, path traversal en `ticket_id`, exactamente uno de `area`/`sucursal`, inyección y abuso en nombres, nombres legítimos recortados. |
| `tests/unit/test_api_errors.py` | 31 | Errores uniformes con `X-Request-ID` (se regenera si es inválido), 413, 500 sin filtrar texto, 503, 504 por timeout, el texto del usuario no llega a los logs, access log sin query string. |
| `tests/unit/test_api_health.py` | 19 | `/health` solo con `status`, `degraded` (no 500) si la sonda falla o expira, caché anónima que no golpea la BD y se recupera, modo Fabric, arranque que falla sin llave válida. |
| `tests/unit/test_api_repository.py` | 15 | `SqlTicketRepository` con conexiones DB-API falsas: fallo de Fabric -> `RepositoryUnavailableError` sin traza ni texto. |
| `tests/unit/test_main_serve.py` | 9 | `main.py serve`: sale con código 1 con config inválida, sin llave o con llave corta (sin imprimirla); uvicorn con opciones seguras; la llave no llega al archivo de log. |
| `tests/integration/test_api.py` | 21 | API sobre el dataset generado cargado en SQLite: estado de cada ticket coincide con la BD, bandera SLA coherente con la fecha de cierre, SQL injection en `ticket_id` y en área/sucursal sin efecto. |
| `tests/integration/test_api_rag.py` | 4 | API con servicios reales sobre un índice con embeddings falsos (`/buscar_solucion` de punta a punta). |

## Resultados reales

Comando: `.venv\Scripts\python -m pytest --cov -q` (suite completa):

```
src\api\app.py          169  3  12  0   98%   203-205
src\api\errors.py        45  0   2  0  100%
src\api\middleware.py    71  1  22  5   94%
src\api\repository.py   117  2  16  1   98%
src\api\schemas.py       72  1   6  1   97%
src\api\security.py      26  0   4  0  100%
TOTAL                  2435 17 408 15   99%

Required test coverage of 80.0% reached. Total coverage: 98.80%
828 passed, 1 deselected in 48.58s
```

## Cómo verificarla paso a paso

Desde la raíz del repo, con el entorno virtual activo y `.env` creado desde `.env.example`.

```powershell
# 0. Llave de la API (>=16 caracteres), solo para esta sesión
$env:DESKPILOT_API_KEY = "cambia-esta-llave-local-123"

# 1-3. Pipeline de datos
.venv\Scripts\python main.py generate-data
.venv\Scripts\python main.py load-db
.venv\Scripts\python main.py index

# 4. Servir (127.0.0.1:8000 por defecto)
.venv\Scripts\python main.py serve
```

En otra terminal:

```powershell
$k = "cambia-esta-llave-local-123"
curl.exe http://127.0.0.1:8000/health
curl.exe -X POST http://127.0.0.1:8000/buscar_solucion -H "X-API-Key: $k" -H "Content-Type: application/json" -d '{\"query\":\"no puedo conectarme a la VPN\"}'
curl.exe http://127.0.0.1:8000/tickets/TCK-000001 -H "X-API-Key: $k"
curl.exe "http://127.0.0.1:8000/metricas?area=Caja" -H "X-API-Key: $k"
# Debe responder 401:
curl.exe -i http://127.0.0.1:8000/tickets/TCK-000001
```

Resultado esperado: `/health` devuelve solo `{"status":"ok"}`; los endpoints con llave devuelven JSON; sin llave, 401 con el formato de error uniforme. Tests: `.venv\Scripts\python -m pytest tests/unit/test_api_*.py tests/unit/test_main_serve.py tests/integration/test_api*.py`.

## Decisiones de seguridad

Revisión del security-verifier (ALTO RIESGO); hallazgos M1, M2, B1 y B2 corregidos (commits `fix(api)`, `feat(config)`; ver `git log`):

- `/health` es anónimo pero solo devuelve `status`, sin detalles internos; el sondeo se cachea para que llamadas anónimas no carguen la BD.
- `/docs`, `/redoc` y `/openapi.json` apagados (el OpenAPI se exporta con `export-openapi`, T19).
- Llave comparada en tiempo constante, mínimo 16 y máximo 256 bytes validados al arrancar (`serve` falla rápido).
- 422 nunca refleja nombres de campos del cliente; `fullmatch` en los patrones; 413 también para cuerpos chunked.
- Sin llave ni texto del usuario en logs; errores de BD solo con el tipo, sin traza; access log sin query string.

## Limitaciones conocidas

- El modo Fabric no se ha probado contra un tenant real (solo con conexiones falsas); queda para la fase manual.
- Sin rate limiting (se espera delegarlo a una capa frontal).
- Tras un 504 el hilo que ejecutaba la consulta queda abandonado hasta que termine.
- `metricas_area` solo consulta la tabla `tickets`.
