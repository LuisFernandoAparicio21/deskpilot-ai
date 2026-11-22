# Exportación OpenAPI para Copilot Studio (T19)

## Qué hace

`main.py export-openapi` genera `integrations/copilot_studio/openapi.json`, una definición **Swagger 2.0 en JSON** de las 4 herramientas del agente (`buscar_solucion`, `consultar_estado_ticket`, `metricas_area`, `crear_ticket`). Se construye desde la app FastAPI, sin arrancar el servidor y sin llave real.

- **Host configurable** con `--host` (solo el nombre, sin `https://` ni ruta). Sin él queda el marcador `your-deskpilot-host.example.com`.
- **Seguridad**: `securityDefinitions` de tipo `apiKey`, en la cabecera `X-API-Key`, aplicada a todas las operaciones.
- **Esquema** `https`; `/health` no se incluye (no es una herramienta).
- Cada operación, parámetro y propiedad lleva descripción no vacía; los campos opcionales usan `x-nullable`; los POST declaran el 413.
- Rechaza un host inválido (código de salida 3) y no escribe archivos de 1 MB o más.

## Specs y vacante

- **S8** (API REST) y **RF-25**: contrato de la API consumible por el agente. T19 cubre además S17.
- **Vacante (Stefanini / Copilot Studio)**: evidencia que la API se integra como herramienta del agente.
- Requisitos de Copilot Studio: [docs/research/copilot-studio-openapi-requirements.md](../research/copilot-studio-openapi-requirements.md). Lo no confirmado queda marcado tal cual en ese documento:
  - Formato: "YAML no se menciona; ⚠ verificar en pantalla si acepta `.yaml`".
  - Tamaño: "Copilot Studio no publica un límite propio; ⚠ verificar en pantalla".
  - Esquemas: "Que https sea obligatorio no está dicho expresamente; ⚠ verificar en pantalla".
  - `operationId`: "Que `operationId` sea obligatorio no se afirma; ⚠ verificar en pantalla".
  - Características no soportadas (`$ref` complejos, `oneOf`, etc.): "⚠ verificar en pantalla".

## Pruebas

Archivo: `tests/unit/test_openapi_export.py` (46 pruebas, usan la app y la CLI reales).

| Grupo | Qué valida |
|---|---|
| Versión y tamaño | Es Swagger 2.0 (no OpenAPI 3), se serializa como JSON y pesa menos de 1 MB. |
| Operaciones | Exactamente las 4 herramientas, sin `/health`; `operationId` esperados. |
| Seguridad y host | `apiKey` en `X-API-Key` en cada operación; `https` y host marcador por defecto; host configurable. |
| Descripciones | `summary` y `description` en español en cada operación; descripción en cada parámetro y propiedad. |
| Compatibilidad v2 | Sin restos de OpenAPI 3, sin `$ref` rotos, `x-nullable` en campos opcionales. |
| Errores | Respuestas de error definidas por operación y 413 en los POST; cuerpos como parámetros `body`. |
| `check_swagger` (negativas) | Acepta el export y rechaza `anyOf` sin traducir, `$ref` roto o estilo v3, descripciones vacías, versión errónea, host ausente, esquema `http` y operación faltante. |
| Host y escritura | `validate_host` rechaza URLs, rutas y basura; no se escribe un archivo de 1 MB o más; escribe UTF-8 y devuelve el tamaño. |
| CLI | Funciona sin API key y respeta `--out`; host propio sin tocar el archivo por defecto; una URL como host sale con código 3. |
| Sin deriva | `openapi.json` versionado coincide con lo que genera el código hoy y pasa `check_swagger`. |
| Validador externo | Valida con `openapi-spec-validator` si está instalado; si no, se omite (opcional). |

## Resultados reales

Ejecutado en esta rama (2026-11-22) con `.venv\Scripts\python -m pytest -q --cov=src --cov-report=term-missing`:

```text
1200 passed, 1 skipped, 1 deselected, 5 warnings in 81.58s (0:01:21)
Required test coverage of 80.0% reached. Total coverage: 98.33%
src\api\openapi_export.py   191   8   110   10   94%
```

- El `skipped` es la prueba del validador externo (`openapi-spec-validator` no está instalado en el venv del repo, es opcional).
- El `deselected` es la prueba marcada `slow` (descarga el modelo real), excluida por `addopts`.

## Validación externa

`openapi-spec-validator` 0.9.0 en un venv temporal (no es dependencia del repo). Resultado sobre `integrations/copilot_studio/openapi.json`: **OK** (`swagger` 2.0, 4 rutas).

## Cómo verificar paso a paso

1. Exportar con un host de prueba, a un archivo temporal:

   ```powershell
   .venv\Scripts\python main.py export-openapi --host mi-api.example.com --out $env:TEMP\openapi.json
   ```

   Salida esperada: `... (Swagger 2.0, <bytes> bytes)` con `host: mi-api.example.com  schemes: https`. En esta verificación fueron 25130 bytes.

2. Revisar el tamaño (debe ser menor de 1 MB, es decir, 1 048 576 bytes):

   ```powershell
   (Get-Item $env:TEMP\openapi.json).Length
   ```

3. Validar con una herramienta externa en un venv aparte:

   ```powershell
   python -m venv $env:TEMP\v
   & $env:TEMP\v\Scripts\python -m pip install openapi-spec-validator==0.9.0
   & $env:TEMP\v\Scripts\python -c "import json; from openapi_spec_validator import validate; validate(json.load(open('integrations/copilot_studio/openapi.json', encoding='utf-8')))"
   ```

   Sin salida ni excepción significa que es válido.

4. Correr las pruebas: `.venv\Scripts\python -m pytest tests/unit/test_openapi_export.py`.

## Importarlo en Copilot Studio

Los pasos en la interfaz de Copilot Studio se documentarán en `docs/MANUAL_STEPS.md` (T25, pendiente, fase manual T32). Este documento no los describe. Antes de subir el archivo hay que reexportarlo con el host público real.

## Limitaciones

- **YAML**: no soportado ni confirmado; solo se exporta JSON.
- **https obligatorio**: no confirmado por Microsoft (⚠ verificar en pantalla); el export usa siempre `https`.
- **Host**: marcador `your-deskpilot-host.example.com` hasta que exista la URL pública (T31).
- Volver a exportar cada vez que cambie la API; la prueba de deriva falla si `openapi.json` queda desactualizado.
- Una importación real en Copilot Studio aún no se ha probado.
- El Dockerfile se separó como T19b (rama `feat/t19b-dockerfile`) y no forma parte de esta feature.
