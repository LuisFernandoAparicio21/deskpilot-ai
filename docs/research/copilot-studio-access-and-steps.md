# Copilot Studio: acceso con cuenta universitaria y pasos de alto nivel

Fecha de consulta: 2026-11-22.

## Pregunta
Con una cuenta universitaria (Entra), ¿cómo se accede a Copilot Studio y cuáles son los pasos oficiales para crear un agente, agregar knowledge, agregar una herramienta REST API (OpenAPI v2, API key en header), probar, publicar/compartir y conectar MCP?

## Respuesta
**Acceso.** Entrar a https://copilotstudio.microsoft.com con la cuenta de trabajo o escuela (correo personal es rechazado). Se inicia una prueba gratuita individual; al vencer se extiende 30 días y el agente sigue funcionando hasta 90 días tras el vencimiento. La prueba permite crear y probar en el panel de prueba, pero NO publicar. Si el administrador del tenant deshabilitó el autoservicio, hay que pedirle que lo habilite. Publicar a canales exige suscripción standalone (o plan Teams, solo Teams, sin REST/premium). No aparece en estas páginas el programa "Microsoft 365 Developer Program / entorno developer" como vía para Copilot Studio: ⚠ verificar en pantalla (ver `fabric-access-without-m365-devprogram.md`).

**(a) Crear agente.** Home > describir el agente en lenguaje natural (hasta 1.024 caracteres) > se abre Overview; ajustar nombre, descripción e instrucciones.
**(b) Knowledge.** Overview > sección Knowledge > Add > Add to agent. La guía oficial solo demuestra una URL pública (documentación). Subir archivos propios: ⚠ verificar en pantalla (no confirmado en las fuentes).
**(c) Tool REST API.** Agent > Tools > Add tool > New tool > REST API > subir OpenAPI JSON (debe ser v2; una v3 se traduce a v2 automáticamente; función en preview) > descripción y solución > Authentication: None / API key / OAuth 2.0 > con API key indicar Parameter label, Parameter name (p. ej. `X-API-Key`) y Parameter location = Header > elegir operaciones, ajustar nombre y descripciones de tools y parámetros > Next/publicar > Create connection (el usuario da la API key al conectarse) > Add and configure.
**(d) Probar.** Panel "Test your agent" (chat de prueba); icono "Start new test session" reinicia. Disponible también en la prueba gratuita.
**(e) Publicar.** Publish > confirmar Publish > menú "..." > Go to demo website y compartir la URL. Teams y otros canales: ⚠ verificar en pantalla (la quickstart solo cubre demo website; detalles en "Publish an agent to a live or demo website" y publication-fundamentals-publish-channels).
**(f) MCP.** ⚠ verificar en pantalla: las páginas consultadas solo mencionan MCP de pasada (en la opción OAuth 2.0 del texto de REST API); no confirmé el procedimiento. Buscar en Tools > Add tool una opción de Model Context Protocol.

## Decisión recomendada
Usar la cuenta Entra universitaria para la prueba gratuita y construir/probar en el panel de prueba (agente + tool REST API con OpenAPI v2 JSON, API key en header). Para el demo, verificar en pantalla si el tenant permite Publish; si no, grabar el panel de prueba como evidencia. Confirmar en pantalla la subida de archivos como knowledge y la opción MCP.

## Fuentes
1. Get access to Copilot Studio (Microsoft Learn) - https://learn.microsoft.com/en-us/microsoft-copilot-studio/requirements-licensing-subscriptions - 2026-11-22
2. Extend your agent with tools from a REST API (preview) - https://learn.microsoft.com/en-us/microsoft-copilot-studio/agent-extend-action-rest-api - 2026-11-22
3. Quickstart: Create and deploy an agent with the standard harness - https://learn.microsoft.com/en-us/microsoft-copilot-studio/fundamentals-get-started - 2026-11-22
