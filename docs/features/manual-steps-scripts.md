# Guía manual y scripts de verificación (T25, Fase B)

Feature T25 (rama `chore/t25-manual-steps`). Cubre S18 (guía manual) y S22 (Fase C en unas 6 horas). Datos sintéticos
(banco ficticio "Banco Altiplano").

## Qué contiene

- `docs/MANUAL_STEPS.md`: checklist de 46 pasos numerados en orden, de los prerrequisitos al tag `v0.1.0`, para T28 a T36.
  Cada paso trae dónde hacer clic (solo lo que está en documentación oficial; lo demás va como "⚠ verificar en pantalla"),
  archivo del repo, comandos exactos, cómo verificar, qué hacer si falla y link. Incluye alternativas de tenant sin el
  M365 Developer Program, la tabla "Si falla" con 10 problemas y el tiempo por sección.
- `scripts/check_fabric.py`: comprueba la conexión a Fabric por pasos. Se detiene en el primer fallo bloqueante: variables
  `FABRIC_*`/`AZURE_*` (solo nombres), driver ODBC 18, token de Entra, `SELECT COUNT(*) FROM dbo.tickets` en el SQL
  analytics endpoint, existencia de `dbo.tickets_nuevos` en el Warehouse y, con `--write-test`, un INSERT y DELETE de un
  ticket de prueba. Códigos de salida: 0 todo bien, 1 un chequeo falló, 2 configuración o uso inválido.
- `scripts/check_public_url.py URL`: comprueba https, `GET /health` 200, `POST /buscar_solucion` sin key 401 y con key 200
  con citas en español e inglés, `/docs`, `/redoc` y `/openapi.json` en 404, el host de `openapi.json` y la latencia (los
  dos últimos solo avisan). Lee la key de `DESKPILOT_API_KEY` (o la variable de `--api-key-env`) o de `.env`; nunca la imprime.
- `scripts/update_readme_results.py`: reescribe solo el bloque entre `<!-- RESULTS:START -->` y `<!-- RESULTS:END -->`
  del README con `tests/eval/results.summary.json` y, si existen, los resultados de la tabla T32 de
  `docs/testing-procedure.md` (columna "Pasó (sí/no)"). Es idempotente; `--check` no escribe y sale 1 si está desactualizado;
  `--dry-run` imprime el bloque.

## Bugs de los scripts corregidos antes de documentar

1. `check_fabric` podía imprimir el texto crudo de una excepción (con riesgo de cadena de conexión o token): ahora solo
   muestra el tipo y un SQLSTATE de 5 caracteres (`describe()`).
2. `check_fabric` dejaba `DESKPILOT_MODE=fabric` en el entorno del proceso: ahora lo restaura (sin definir, definido y
   ante una excepción).
3. `update_readme_results` aceptaba un README sin marcadores válidos y un resumen malformado: ahora valida un par
   START/END único y el esquema del resumen, y sale con 2 y un mensaje claro.

## Pruebas reales

97 pruebas en `tests/unit/test_scripts_check_fabric.py` (35), `test_scripts_check_public_url.py` (27) y
`test_scripts_update_readme_results.py` (35). Usan dobles: conexión y token falsos para Fabric, `httpx.MockTransport` para
la URL y archivos temporales para el README. Comprueban códigos de salida, que ninguna salida contenga secretos
y la idempotencia.

Resultados reales (2026-11-22, `.venv\Scripts\python`):

| Comando | Resultado |
| --- | --- |
| `python -m pytest --cov=src` | 1718 passed, 2 skipped, 33 deselected; cobertura de `src/` 98.24% (umbral 80%) |
| Solo las pruebas de `scripts/` con `--cov=scripts` | 97 passed; `check_fabric` 97%, `check_public_url` 100%, `update_readme_results` 94% |
| `ruff check .`, `ruff format --check .`, `mypy` | sin errores (202 archivos formateados, 112 de mypy) |

Verificación de `MANUAL_STEPS.md` con un script temporal (borrado): cada link relativo, cada ruta de repo, cada subcomando
y flag de `main.py` y de los tres scripts existe; cada URL externa está en `docs/sources.md` o en `docs/research/`.

## Limitaciones

- **Los scripts no se probaron contra un Fabric real ni contra una URL pública real.** Solo con dobles de prueba. El scope
  `https://database.windows.net/.default`, la ejecución del notebook en Spark, el DDL en un Warehouse y la precisión de
  `datetime2` (consulta 07) siguen sin verificar (T29/T30).
- Los clics de Copilot Studio, Fabric y Power BI se describen solo donde la documentación oficial los confirma; el resto va
  marcado "⚠ verificar en pantalla" (subir archivos como knowledge, MCP, tema por tema, Create > Lakehouse, tamaño de
  instrucciones, límites de Dev Tunnels).
- Los tiempos de la sección 0 y del cierre son estimaciones; el resto sale del roadmap (360 min).
- `ruff format` no procesa Markdown: sobre `MANUAL_STEPS.md` informa "1 file left unchanged".
