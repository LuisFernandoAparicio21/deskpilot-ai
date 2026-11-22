# ADR-0005: API REST y MCP sobre una sola capa de servicio

- **Estado:** aceptada
- **Fecha:** 2026-11-22

## Contexto

Copilot Studio consume las herramientas por REST (OpenAPI) y, como alternativa, por MCP. Las dos entradas deben
comportarse igual en validación, redacción, escalamiento y errores.

## Decisión

FastAPI y el servidor MCP (`python main.py mcp`, SDK `mcp` 2.3.0, stdio por defecto y HTTP con llave) son
adaptadores delgados sobre la misma capa de servicio: `buscar_solucion`, `consultar_estado_ticket`,
`crear_ticket` y `metricas_area`. Las reglas viven en la capa de servicio y no se repiten en cada adaptador.

## Alternativas

- **Solo REST:** menos código, pero sin la alternativa MCP si el conector falla (riesgo de `docs/requirements.md`,
  sección 14).
- **Dos implementaciones independientes:** riesgo de que difieran en RN-03 o RN-05.

## Consecuencias

- Las pruebas de seguridad (RN-03, RN-05) cubren las dos entradas con la misma base de datos real (L17).
- El MCP depende de símbolos internos de la API; es una deuda aceptada (L17, hallazgos bajos).
- En el SDK 2.x `FastMCP` pasó a `MCPServer`.

## Fuentes

`docs/sources.md`, sección MCP (especificación, SDK de Python y guía de migración a v2). ODD L15 a L18.
