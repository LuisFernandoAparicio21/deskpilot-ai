# Herramientas del agente DeskPilot L1

Las 4 herramientas tienen el mismo nombre en `openapi.json` (campo `operationId`, herramienta REST de Copilot Studio) y en el servidor MCP (`python main.py mcp`). Banco Altiplano es ficticio; datos sintéticos. Longitud máxima de nombre y descripción: no publicada ⚠ verificar en pantalla (Copilot Studio precarga ambos desde el OpenAPI).

| operationId = nombre MCP | REST | Argumentos | Cuándo usarla |
|---|---|---|---|
| `buscar_solucion` | `POST /buscar_solucion` | `query` (obligatorio), `categoria` (opcional) | Siempre primero ante un problema técnico |
| `crear_ticket` | `POST /tickets` | `descripcion`, `sucursal`, `area` (obligatorios), `canal` (portal, correo, teléfono, Teams; por defecto Teams) | Tras `no_evidence`, `mandatory_escalation`, problema no resuelto o petición de una persona, y con confirmación |
| `consultar_estado_ticket` | `GET /tickets/{ticket_id}` | `ticket_id` (TCK-NNNNNN) | El usuario da un folio |
| `metricas_area` | `GET /metricas` | exactamente uno de `area` / `sucursal` | Métricas de UN área o UNA sucursal |

Nota: en MCP la herramienta `consultar_estado_ticket` equivale a `GET /tickets/{id}` y `metricas_area` a `GET /metricas` (ver `docs/features/mcp-server.md`).

## buscar_solucion
- Descripción para el agente: "Busca en la base de conocimiento de TI de Banco Altiplano la solución a un problema técnico y la devuelve con citas (id y título del artículo). Úsala siempre primero cuando el empleado describa un problema, antes de crear un ticket. Envía el problema tal como lo dijo, sin contraseñas ni PIN."
- Respuesta clave: `status` (`answered` | `no_evidence` | `mandatory_escalation`), `text`, `citations[]` (`article_id`, `titulo`), `language` (es/en), `sensitive_data_warning`, `mode`.
- Manejo: `answered` presenta pasos y cita; `no_evidence` va a `topics/no-lo-se.md`; `mandatory_escalation` va a `topics/escalamiento-obligatorio.md`.

## crear_ticket
- Descripción: "Crea un ticket de soporte de TI. Categoría y prioridad (P1-P4) se clasifican automáticamente y devuelve el SLA. Acción que escribe datos: úsala solo con confirmación del empleado y una vez por problema. Resume el problema sin contraseñas, PIN ni tarjetas."
- Respuesta clave: `ticket_id`, `estado`, `categoria`, `prioridad`, `sla_horas`, `fecha_limite_sla`, `escalado`, `motivo_escalamiento`, `sensitive_data_warning`. Nunca devuelve la descripción.
- Esperado en escalamiento obligatorio: `prioridad` P1, `escalado` true, `sla_horas` 4.

## consultar_estado_ticket
- Descripción: "Devuelve el estado de un ticket existente a partir de su folio (por ejemplo TCK-000123): estado, prioridad, fechas y si cumple el SLA. Si no existe responde 404: pide verificar el folio, no adivines."
- Respuesta clave: `estado` (abierto, en_proceso, resuelto, cerrado), `prioridad`, `fecha_apertura`, `fecha_cierre`, `sla_horas`, `fecha_limite_sla`, `sla_cumplido`.

## metricas_area
- Descripción: "Devuelve métricas de tickets de UN área (por ejemplo Caja) o de UNA sucursal: total, cerrados, % dentro de SLA, horas promedio de resolución y categorías más frecuentes. Envía solo `area` o solo `sucursal`."
- Respuesta clave: `scope`, `name`, `total_tickets`, `closed_tickets`, `sla_cumplido_pct`, `avg_horas_resolucion`, `top_categorias[]`.

## Errores
Formato común `{code, message, request_id}`: 401 sin llave, 404 folio o nombre inexistente, 422 argumentos inválidos, 503 servicio no disponible. El agente nunca muestra `request_id` ni detalles técnicos; usa los mensajes de cada tema.

## Autenticación
`X-API-Key` (REST). La llave real va solo en la configuración de la conexión en Copilot Studio; nunca en estos archivos. Pasos de conexión: `docs/MANUAL_STEPS.md` (T25).
