# Requisitos de Copilot Studio para la definición OpenAPI (herramienta REST API)

## Pregunta
¿Qué requisitos exactos impone Microsoft Copilot Studio a una definición OpenAPI para añadir una herramienta REST API?

## Respuesta
- **Versión**: la especificación debe ser OpenAPI v2 (Swagger 2.0). Si se sube v3, "the creation process automatically translates it to a v2 specification" (Copilot Studio). La página de conectores personalizados es más estricta: "OpenAPI 3.0 format are not supported".
- **Formato**: Copilot Studio dice "must be a JSON file in v2 format". YAML no se menciona; ⚠ verificar en pantalla si acepta `.yaml`. Los ejemplos de conectores son JSON.
- **Tamaño**: la definición de un conector personalizado debe pesar menos de 1 MB. Copilot Studio no publica un límite propio; ⚠ verificar en pantalla.
- **Seguridad**: opciones None, API key y OAuth 2.0. Para API key se piden etiqueta, nombre del parámetro y ubicación (Header o Query). El ejemplo oficial usa `securityDefinitions: {api_key: {type: apiKey, in: header, name: ...}}` y `security: [{api_key: []}]`. Nombre y ubicación deben coincidir con lo que espera la API. Si hay varias definiciones de seguridad, el conector toma la primera. No se admite client credentials en OAuth.
- **Host y esquemas**: el conector usa `host` y `basePath` para llamar a la API; el ejemplo declara `"schemes": ["https"]` (en v3: `servers` con https). Que https sea obligatorio no está dicho expresamente; ⚠ verificar en pantalla.
- **operationId, summary y description**: el ejemplo oficial los incluye. Los nombres y descripciones de herramientas se precargan desde la especificación. En "Review your tool's parameters" las descripciones en blanco deben completarse antes de continuar. Que `operationId` sea obligatorio no se afirma; ⚠ verificar en pantalla.
- **Otros**: cabeceras solo ASCII; la función REST API está en preview ("not meant for production use"). No hay lista oficial de características no soportadas (`$ref` complejos, `oneOf`, etc.); ⚠ verificar en pantalla.

## Decisión recomendada
Exportar el OpenAPI de FastAPI (3.x), convertirlo a Swagger 2.0 en JSON (`swagger: "2.0"`, `host`, `schemes: [https]`, `securityDefinitions` apiKey in header, `security` global). Poner `operationId`, `summary` y `description` no vacíos en operaciones y en cada parámetro y propiedad de respuesta. Mantener el archivo bajo 1 MB. Probar la subida real en Copilot Studio y anotar en el Log lo marcado como ⚠.

## Fuentes (consultadas 2026-11-21)
- Extend your agent with tools from a REST API (preview) — https://learn.microsoft.com/microsoft-copilot-studio/agent-extend-action-rest-api (ms.date 2026-09-13)
- Create a custom connector from an OpenAPI definition — https://learn.microsoft.com/connectors/custom-connectors/define-openapi-definition (ms.date 2026-06-03)
