# ADR-0007: Swagger 2.0 en JSON para Copilot Studio

- **Estado:** aceptada
- **Fecha:** 2026-11-22

## Contexto

FastAPI genera OpenAPI 3.x, pero Copilot Studio pide para sus REST API tools una definición v2 en JSON (una v3
se traduce sola, función en preview). Los conectores personalizados aceptan solo OpenAPI 2.0 y menos de 1 MB.

## Decisión

`main.py export-openapi` genera `integrations/copilot_studio/openapi.json` en Swagger 2.0: `apiKey` en el header
`X-API-Key`, host configurable (`--host`), sin `/health` y con 4 rutas. Un test falla si el archivo versionado se
desvía de lo que genera el código, y el export se valida con `openapi-spec-validator` 0.9.0 (en un venv temporal,
no es dependencia de runtime).

## Alternativas

- **Subir el OpenAPI 3 de FastAPI:** depende de la traducción automática, en preview.
- **Escribir el Swagger a mano:** se desincroniza del código.

## Consecuencias

- El archivo versionado siempre coincide con la API.
- El `anyOf` de OpenAPI 3 se traduce o se rechaza en el export.
- No verificado: la importación real en Copilot Studio (T32, manual).

## Fuentes

`docs/sources.md`, secciones *Requisitos OpenAPI de Copilot Studio* y *Validación del Swagger 2.0 exportado*
(T19). `docs/research/copilot-studio-openapi-requirements.md`. ODD L5 y L19.
