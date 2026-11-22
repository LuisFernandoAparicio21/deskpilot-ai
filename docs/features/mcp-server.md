# Servidor MCP (T18)

> Datos sintéticos generados para este proyecto; las cifras son ilustrativas. "Banco Altiplano" es ficticio.

## Qué hace

`python main.py mcp` (código en `src/api/mcp_server.py`) expone las mismas cuatro herramientas de la API REST como servidor MCP, para que cualquier agente o cliente compatible con MCP las use. Reutiliza la capa de servicio de la API (`ApiServices`, `AnswerService`, `TicketRepository`, `TicketService`) y los mismos modelos de petición/respuesta, así que límites, redacción (RN-05), escalamiento (RN-03) y clasificación son los de la API.

| Herramienta | Equivale a | Argumentos |
|---|---|---|
| `buscar_solucion` | `POST /buscar_solucion` | `query`, `categoria` (opcional) |
| `consultar_estado_ticket` | `GET /tickets/{id}` | `ticket_id` |
| `metricas_area` | `GET /metricas` | exactamente uno de `area` / `sucursal` |
| `crear_ticket` | `POST /tickets` | `descripcion`, `area`, `sucursal`, `canal` (por defecto Teams) |

Transportes (sección `mcp:` de `config.yaml`):

- `stdio` (por defecto): proceso hijo local, sin red ni llave. Nada se escribe en stdout (es el canal del protocolo); los logs van a stderr y `logs/`.
- `http` (streamable HTTP, `--transport http`, por defecto `127.0.0.1:8001/mcp`): exige `DESKPILOT_API_KEY`; cada petición lleva `X-API-Key: <llave>` o `Authorization: Bearer <llave>`, comparada en tiempo constante. Sin llave, 401.

Los errores llegan al cliente como `ToolError` con mensaje fijo: nunca texto de excepción, la entrada ni rutas.

## Specs que cubre

S10 (servidor MCP): las 4 herramientas sobre la misma capa de servicio; transporte y montaje verificados contra la documentación oficial del SDK (`docs/sources.md`, sección MCP); protección por API key en HTTP; pruebas de integración que listan herramientas y las llaman. También toca RNF-02 (X-API-Key), RNF-04 (validación estricta), RNF-05 (logs sin secretos) y RN-03/RN-05.

## Pruebas realizadas

122 tests del MCP (ejecución real del 2026-11-21 en `feat/t18-mcp-server`), todos en verde:

| Archivo | Qué valida |
|---|---|
| `tests/unit/test_mcp_server.py` | Lista exactamente las 4 herramientas con descripciones y esquemas de entrada; las instrucciones prohíben secretos en argumentos; cada herramienta devuelve respuesta estructurada (citas, estado, métricas por área o sucursal, ticket creado, canal por defecto Teams); RN-03 da P1; validación (query vacía o demasiado larga, `categoria`/`canal`/`ticket_id`/nombres inválidos) con mensajes fijos y sin eco de la entrada; argumento obligatorio faltante y argumentos extra rechazados; herramienta desconocida; fallos del índice, de la BD y timeouts mapeados a mensajes fijos; el log solo lleva herramienta y clase de excepción; RN-05 (el secreto no se guarda, devuelve ni registra). |
| `tests/unit/test_mcp_auth.py` | `ApiKeyMiddleware` y `build_http_app`: sin credenciales o con llave incorrecta, 401 sin llegar a la app; llave en query string no autentica; `X-API-Key` o Bearer válidos pasan; un `X-API-Key` incorrecto gana sobre un Bearer válido (comportamiento documentado); llave no ASCII da 401, no 500; los rechazos se registran sin las llaves; falla al arrancar sin llave válida. |
| `tests/unit/test_main_mcp.py` | CLI `main.py mcp`: sale con 1 con config inválida sin arrancar nada; HTTP sin llave válida sale con 1 sin imprimirla y el mensaje nombra `mcp` (no `serve`); stdio por defecto sin llave y cierra servicios (también si el servidor falla); host/puerto/ruta desde config y overrides por CLI; argumentos inválidos rechazados; sección `mcp` de la config (defaults locales, rangos de puerto, `config.yaml` real válido). |
| `tests/integration/test_mcp_server.py` | Sobre SQLite temporal (nunca toca `data/deskpilot.db`): cliente en proceso lista y llama las 4 herramientas; RN-05 y RN-03 con BD real; los errores de validación no escriben nada; HTTP real: rechaza sin llave o con llave errónea, acepta ambas formas válidas, un cliente MCP real lista y llama con llave y no conecta sin ella; stdio con proceso hijo real (`main.py mcp`): sirve las herramientas, stdout solo lleva JSON-RPC, y sale con 1 con config rota sin imprimir la llave. |

## Resultados reales

Comando: `.venv\Scripts\python -m pytest --cov -q` (suite completa):

```
src\api\mcp_server.py                    137      4     16      0    97%   270, 275-279
TOTAL                                   2819     23    470     17    99%

Required test coverage of 80.0% reached. Total coverage: 98.72%
1156 passed, 1 deselected, 5 warnings in 68.62s (0:01:08)
```

Los 5 warnings son `ResourceWarning: unclosed database` de conexiones SQLite en tests; no fallan. Solo los 4 archivos MCP: `122 passed in 12.65s`.

## Cómo verificarlo paso a paso

Desde la raíz, con `data/deskpilot.db` e índice ya generados (`generate-data`, `load-db`, `index`). Salidas copiadas de la ejecución real del 2026-11-21.

### 1. stdio con un cliente Python

```python
import anyio, json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    params = StdioServerParameters(command=".venv/Scripts/python.exe", args=["main.py", "mcp"])
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            for t in (await s.list_tools()).tools:
                print(t.name, "->", sorted(t.input_schema.get("properties", {})))
            res = await s.call_tool("buscar_solucion", {"query": "no puedo conectarme a la VPN"})
            print(res.is_error, json.dumps(res.structured_content, ensure_ascii=False, indent=1))
            bad = await s.call_tool("buscar_solucion", {"query": "x", "extra": 1})
            print(bad.is_error, bad.content[0].text)
anyio.run(main)
```

Salida (en el SDK 2.x los campos del cliente son `input_schema`, `is_error`, `structured_content`):

```
buscar_solucion -> ['categoria', 'query']
consultar_estado_ticket -> ['ticket_id']
metricas_area -> ['area', 'sucursal']
crear_ticket -> ['area', 'canal', 'descripcion', 'sucursal']
is_error: False
{ "status": "answered", "language": "es", "citations": [ { "article_id": "KB-004",
  "titulo": "La VPN no conecta o se desconecta sola", "seccion": "sintoma", "similarity": 0.7657 } ],
  "sensitive_data_warning": false, "mode": "extractive", "text": "Sigue estos pasos del artículo KB-004 ..." }
extra args is_error: True Error executing tool buscar_solucion: Invalid arguments: unexpected fields.
```

Los logs JSON salen por stderr; en consolas Windows el texto puede verse con la codificación cambiada.

### 2. HTTP con llave

```powershell
$env:DESKPILOT_API_KEY = "clave-de-prueba-local-123"   # solo de prueba, >=16 caracteres
.venv\Scripts\python main.py mcp --transport http      # escucha en 127.0.0.1:8001/mcp
```

En otra terminal, con `curl` enviando un `initialize` JSON-RPC a `http://127.0.0.1:8001/mcp` (cabeceras `Accept: application/json, text/event-stream` y `Content-Type: application/json`):

```
sin llave  -> HTTP/1.1 401 Unauthorized, www-authenticate: Bearer, X-API-Key
              {"code": "unauthorized", "message": "Missing or invalid API key."}
llave mala -> 401
X-API-Key  -> 200
Bearer     -> 200
```

Un cliente `streamable_http_client` con la cabecera `X-API-Key` listó `['buscar_solucion', 'consultar_estado_ticket', 'metricas_area', 'crear_ticket']` y `buscar_solucion` devolvió `answered KB-004`.

Al terminar, detén el servidor (Ctrl+C, o `Stop-Process` del PID que escucha en el 8001). En la verificación se comprobó que el puerto quedó libre y que el SHA-256 de `data/deskpilot.db` no cambió (no se llamó `crear_ticket`; si lo pruebas contra la BD real, bórralo después).

## Decisiones de seguridad

security-verifier (ALTO RIESGO): **APROBADO**. Medidas: stdio sin red; HTTP solo con llave en tiempo constante (mínimo 16, máximo 256 bytes, validado al arrancar); la llave en query string no cuenta; mensajes de error fijos sin eco; logs sin llave ni texto del usuario; `--host` por defecto `127.0.0.1`.

Hallazgos bajos aceptados:

- El servidor importa símbolos privados de `src/api/app.py` (`_Runner`, `_to_response`) y usa `_tool_manager` del SDK; un cambio interno podría romperlos (los tests lo detectarían).
- `--host 0.0.0.0` se acepta sin aviso y sin TLS.
- Si llegan `X-API-Key` y Bearer, gana `X-API-Key` (documentado en test).
- Falta un test de `Host`/`Origin` inválido.

Bugs encontrados por QA y corregidos (commits `fix(mcp)` y `fix(config)`, ver `git log`):

1. Los argumentos extra se aceptaban en silencio: ahora se rechazan ("unexpected fields").
2. `categoria` y `canal` inválidos se reflejaban en el error: ahora se validan con mensaje fijo y, en `crear_ticket`, sin escribir nada.
3. El mensaje de llave faltante decía `serve` al arrancar `mcp`: ahora nombra el comando que falló.

## Limitaciones conocidas

- El SDK `mcp` 2.3.0 renombró `FastMCP` a `MCPServer` (`mcp.server.mcpserver`); `mcp.server.fastmcp` ya no existe. Se usa la API 2.x y la fuente está en `docs/sources.md`.
- HTTP sin TLS: para exponerlo fuera de localhost, usar un proxy inverso con TLS y no abrir `0.0.0.0` directamente.
- Sin rate limiting ni test de `Host`/`Origin` inválido.
- La conexión desde Copilot Studio es manual (T20/T25) y no se verificó aquí.
