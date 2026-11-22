# Integración con Copilot Studio

## openapi.json

Definición Swagger 2.0 (JSON) de las 4 herramientas del agente: `buscar_solucion`, `consultar_estado_ticket`, `metricas_area` y `crear_ticket`. Copilot Studio solo acepta OpenAPI v2 en JSON; se genera desde la app FastAPI, sin arrancar el servidor ni usar una llave real:

```powershell
.venv\Scripts\python main.py export-openapi --host <host-publico-de-la-api>
```

- `--host`: solo el nombre del host (sin `https://`). Sin él queda el marcador `your-deskpilot-host.example.com`: reemplázalo antes de subir el archivo.
- `--out`: otra ruta de salida (por defecto `integrations/copilot_studio/openapi.json`).
- Seguridad: `apiKey` en la cabecera `X-API-Key`; esquema `https`; `/health` no se incluye (no es una herramienta).
- Volver a exportar cada vez que cambie la API. Validado con `openapi-spec-validator` (solo para verificar, no es dependencia) y pesa menos de 1 MB.
- Puntos "verificar en pantalla" (rechazo de YAML, tamaño máximo propio, `https` obligatorio) en `docs/research/copilot-studio-openapi-requirements.md`.
- Detalle, pruebas y verificación paso a paso: [docs/features/openapi-export.md](../../docs/features/openapi-export.md). Los pasos de importación en Copilot Studio irán en `docs/MANUAL_STEPS.md` (T25, pendiente).
