# crear_ticket (T17)

> Datos sintéticos generados para este proyecto; las cifras son ilustrativas. "Banco Altiplano" es ficticio.

## Qué hace

`POST /tickets` (herramienta `crear_ticket` del agente) crea un ticket de soporte L1 desde Copilot Studio:

1. Valida la entrada (`descripcion` de 5 al máximo configurado, `sucursal`, `area`, `canal` opcional con valor por defecto `Teams`; campos desconocidos rechazados).
2. Redacta datos sensibles de la descripción (contraseñas, tarjetas, etc.) **antes** de guardar, loguear o enviar al LLM.
3. Clasifica categoría, subcategoría y prioridad con reglas deterministas (ES/EN). Si hay LLM configurado, su respuesta se valida y solo puede mover la prioridad un nivel; nunca baja ni cambia un P1 de reglas.
4. Aplica el escalamiento obligatorio (RN-03): fraude, sospecha de acceso no autorizado o sistema de caja => P1 y `escalado: true`, sin consultar al LLM.
5. Calcula el SLA por prioridad (P1 4 h, P2 8 h, P3 24 h, P4 72 h) y guarda el ticket en `tickets_nuevos` (SQLite local o Warehouse de Fabric) con un `ticket_id` `TCK-NNNNNN`.
6. Responde 201 con el ticket (nunca devuelve la descripción). `GET /tickets/{id}` lo consulta después.

## Specs y requerimientos que cubre

- S9 (crear_ticket) y, por la API, S8 y S17.
- RF-10, RF-16 (crear ticket con clasificación y SLA), RF-18 (persistencia en SQLite o Warehouse).
- RN-01 (prioridad y SLA), RN-03 (escalamiento obligatorio), RN-05 (datos sensibles).

## Pruebas realizadas

206 tests nuevos escritos por qa-tester (ejecución real del 2026-11-21 en `feat/t17-crear-ticket`):

| Archivo | Tests | Qué valida |
|---|---|---|
| `tests/unit/test_classification.py` | 84 | Reglas ES/EN por categoría, orden P1 > P2 > P3, sin coincidencia => General P4, escalamiento obligatorio P1, LLM: respuesta válida, JSON en bloque de código, salida inválida o fallo => reglas (sin texto en logs), salto de más de un nivel o subida a P1 rechazados, un P1 de reglas nunca cambia, inyección de prompt, escape del marcado en el prompt. |
| `tests/unit/test_ticket_service.py` | 21 | SLA por prioridad y desde configuración, fecha límite = apertura + SLA, escalamiento sin consultar al LLM, modo `rules`/`llm`, campos guardados, idioma, un secreto no llega a la fila, respuesta, logs ni LLM, varios secretos, recorte al límite, log solo con metadatos, fallo del repositorio => no disponible. |
| `tests/unit/test_api_create_ticket.py` | 49 | 201 con los campos documentados, la respuesta no devuelve la descripción, canal por defecto, 401 sin llave (antes del 422), 422 y nada guardado, límites de longitud, no se refleja el texto rechazado, SQL injection como texto inerte, JSON mal formado, content-type incorrecto, 413, 405, 503 sin traza, 500 genérico, access log sin cuerpo ni llave, 504 por lentitud. |
| `tests/unit/test_repository_create.py` | 13 | INSERT parametrizado (el texto del usuario nunca va en el SQL), commit/rollback, reintento con un id nuevo si está tomado, id libre en todas las tablas, reintentos agotados sin insertar, error de Fabric => no disponible sin traza ni texto, formato `TCK-` no secuencial, escritura en el Warehouse. |
| `tests/integration/test_api_create_ticket.py` | 39 | Sobre SQLite temporal: el ticket guardado coincide con la respuesta y se consulta con `GET`, tickets históricos intactos, SLA 4/8/24/72 h en la fila, escalamiento guardado como P1 sin LLM, modo LLM, LLM no confiable no cambia la prioridad, secreto ausente de BD/respuesta/logs/prompt, SQL injection, 400 inserciones concurrentes con ids únicos, colisiones forzadas con reintento y 503 si no cesan, BD inaccesible o tabla ausente => 503. |

## Resultados reales

Comando: `.venv\Scripts\python -m pytest --cov -q` (suite completa):

```
src\api\app.py             186  3  14  0   98%   213-215
src\api\classification.py   96  1  30  1   98%   169
src\api\repository.py      186  2  28  1   99%   137, 373
src\api\schemas.py          97  2   8  2   96%   22, 26
src\api\ticket_service.py   33  0   0  0  100%
TOTAL                     2676 19 454 17   99%

Required test coverage of 80.0% reached. Total coverage: 98.79%
1034 passed, 1 deselected, 5 warnings in 57.32s
```

## Cómo verificarla paso a paso

Ejecutado de verdad el 2026-11-21 (modo local, `serve` con una llave de prueba; BD ya generada con `generate-data`, `load-db` e `index`). Los cuerpos JSON van en archivo con `--data-binary` para conservar UTF-8 en Windows.

```bash
export DESKPILOT_API_KEY="clave-de-prueba-local-12345"
.venv/Scripts/python main.py serve        # 127.0.0.1:8000
curl http://127.0.0.1:8000/health          # {"status":"ok"}
```

Cada cuerpo se guarda en un archivo (`t1.json`, ...) con la forma `{"descripcion":"...","sucursal":"Centro","area":"Caja","canal":"Teams"}` y se envía con:

```bash
curl -i -X POST http://127.0.0.1:8000/tickets -H "X-API-Key: $DESKPILOT_API_KEY" -H "Content-Type: application/json; charset=utf-8" --data-binary @t1.json
```

**1. Descripción normal** (`"No puedo conectarme a la VPN desde casa, me da error al iniciar sesión"`):

```
HTTP/1.1 201 Created
{"ticket_id":"TCK-575708","estado":"abierto","categoria":"Conectividad","subcategoria":"VPN","prioridad":"P2","sla_horas":8,"fecha_apertura":"2026-11-22T04:26:25","fecha_limite_sla":"2026-11-22T12:26:25","escalado":false,"motivo_escalamiento":null,"sensitive_data_warning":false,"mode":"rules"}
```

**2. Dato sensible** (`"No puedo entrar al correo, mi contraseña: Hola123"`):

```
HTTP/1.1 201 Created
{"ticket_id":"TCK-681809","estado":"abierto","categoria":"Accesos","subcategoria":"Reseteo de contrasena","prioridad":"P2","sla_horas":8,"fecha_apertura":"2026-11-22T04:26:25","fecha_limite_sla":"2026-11-22T12:26:25","escalado":false,"motivo_escalamiento":null,"sensitive_data_warning":true,"mode":"rules"}
```

En la BD la descripción quedó `No puedo entrar al correo, mi contraseña: [REDACTED:password]`, y `Hola123` no aparece en el log del servidor (0 coincidencias).

**3. Tarjeta** (`"Mi tarjeta 4111 1111 1111 1111 no funciona en la terminal"`): `201`, `sensitive_data_warning: true`, categoría General, P4, 72 h. En BD: `Mi tarjeta [REDACTED:card] no funciona en la terminal`; el número tampoco aparece en el log.

**4. Fraude** (`"Hubo un posible fraude en una transferencia de un cliente y no la reconozco"`):

```
HTTP/1.1 201 Created
{"ticket_id":"TCK-961514","estado":"abierto","categoria":"General","subcategoria":"Sospecha de fraude","prioridad":"P1","sla_horas":4,"fecha_apertura":"2026-11-22T04:26:25","fecha_limite_sla":"2026-11-22T08:26:25","escalado":true,"motivo_escalamiento":"fraud","sensitive_data_warning":false,"mode":"rules"}
```

**5. Sin llave**:

```
HTTP/1.1 401 Unauthorized
{"code":"unauthorized","message":"Missing or invalid API key.","request_id":"b2361f4f85bd45d896c2606c7f7a6988","details":null}
```

**6. Consultar** (`GET /tickets/TCK-681809` y `GET /tickets/TCK-961514` con la llave):

```
{"ticket_id":"TCK-681809","estado":"abierto","prioridad":"P2","fecha_apertura":"2026-11-22T04:26:25","fecha_cierre":null,"sla_horas":8,"fecha_limite_sla":"2026-11-22T12:26:25","sla_cumplido":null}
{"ticket_id":"TCK-961514","estado":"abierto","prioridad":"P1","fecha_apertura":"2026-11-22T04:26:25","fecha_cierre":null,"sla_horas":4,"fecha_limite_sla":"2026-11-22T08:26:25","sla_cumplido":null}
```

Al terminar se detuvo el servidor (`/health` dejó de responder) y se borraron de `tickets_nuevos` los 4 tickets de prueba. Para repetir solo los tests:

```powershell
.venv\Scripts\python -m pytest tests/unit/test_classification.py tests/unit/test_ticket_service.py tests/unit/test_api_create_ticket.py tests/unit/test_repository_create.py tests/integration/test_api_create_ticket.py
```

## Decisiones de seguridad

security-verifier (ALTO RIESGO): **APROBADO** tras los ciclos de corrección.

- **M1 (corregido):** el LLM podía degradar un P1 de reglas. Ahora un P1 de reglas nunca cambia y el LLM no se consulta en escalamientos obligatorios; además solo puede mover un nivel.
- **M2 (riesgo conocido, aceptado):** en el Warehouse la PK es NOT ENFORCED, por lo que la unicidad de `ticket_id` depende de la aplicación (ids aleatorios `TCK-NNNNNN`, comprobación y reintento). Queda un riesgo residual de ~1/900.000 por par de peticiones concurrentes.
- **Baja:** una contraseña escrita sin separador (por ejemplo "mi contraseña Hola123") no se redacta.
- Entradas parametrizadas, descripción redactada antes de guardar/loguear/enviar al LLM, texto del usuario y secretos fuera de logs, 422/500/503 sin reflejar texto ni trazas.

## Limitaciones conocidas

- La marca de escalamiento (`escalado`, `motivo_escalamiento`) se devuelve en la respuesta pero no se guarda en la BD (solo queda la prioridad P1).
- La clasificación por reglas cubre ES/EN pero no es exhaustiva; lo no reconocido cae en General / P4.
- Fabric (Warehouse) no se ha probado contra un tenant real, solo con conexiones falsas; queda para la fase manual.
- Ver también las limitaciones de [api-rest.md](api-rest.md) (sin rate limiting, hilo abandonado tras un 504).
