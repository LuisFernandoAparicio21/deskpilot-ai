# Imagen Docker de la API (T19b)

## Qué hace

El `Dockerfile` empaqueta la API de DeskPilot AI en **modo local** (SQLite + Chroma) con datos 100% sintéticos de "Banco Altiplano". Es de una sola etapa a propósito: una multi-etapa copiaría otra vez `site-packages` y los datos (~1 GB).

- Base `python:3.13-slim`, usuario no root `app` (uid 10001).
- Todo se prepara al construir, nunca dentro de una petición: `generate-data`, `load-db` e `index` (RF-15), más el modelo de embeddings `paraphrase-multilingual-MiniLM-L12-v2` descargado una vez a `data/vectordb/models`.
- `HF_HUB_OFFLINE=1`: en ejecución el contenedor no necesita red.
- Ningún secreto en la imagen: `.env` queda fuera por `.dockerignore` y `DESKPILOT_API_KEY` se pasa en `docker run`.
- `HEALTHCHECK` contra `/health`.

## Cómo construir y ejecutar

```powershell
docker build -t deskpilot-ai .
docker run -d --name deskpilot -p 8000:8000 -e DESKPILOT_API_KEY=<clave de 16+ caracteres> deskpilot-ai
curl.exe http://localhost:8000/health
curl.exe -H "X-API-Key: <clave>" -H "Content-Type: application/json" --data-binary "@consulta.json" http://localhost:8000/buscar_solucion
```

Usa `--data-binary @archivo` para que el UTF-8 de las tildes llegue intacto.

## Resultados reales (verificación, 2026-11-22)

Construcción con `docker build --progress=plain` (primer paso lento: descarga del modelo, 94 s de `index`):

```text
generate-data: seed=42 -> 5000 tickets, 120 sucursales
load-db: data/deskpilot.db (5000 tickets, 120 sucursales, 0 tickets_nuevos)
index: 15 articles -> 64 chunks, fastembed paraphrase-multilingual-MiniLM-L12-v2 (dim 384)
```

Ejecución (`docker run -d ... -e DESKPILOT_API_KEY=verify-key-0123456789-abcdef`):

| Comprobación | Resultado |
|---|---|
| `GET /health` | 200 `{"status":"ok"}` |
| `POST /buscar_solucion` (ES: "usuario bloqueado") | 200, `answered`, `language: es`, cita KB-002 |
| `POST /buscar_solucion` (EN: "VPN keeps disconnecting") | 200, `answered`, `language: en`, cita KB-004 |
| Sin `X-API-Key` | 401 `{"code":"unauthorized",...}` |
| `POST /tickets` | 201 `TCK-854688`, Hardware/Impresoras, P4, SLA 72 h |
| `whoami` / `id` | `app` / `uid=10001(app) gid=10001(app)` (no root) |
| `import pyodbc` | `pyodbc 5.5.0` |
| SQLite y logs escribibles | `/app/data/deskpilot.db` (app:app) con 1 fila en `tickets_nuevos`; `touch /app/logs/x` OK; `deskpilot.log` creado |
| HEALTHCHECK | `healthy` |
| `--network none` | búsqueda ES y EN responde 200 (`KB-002`, `KB-004`) sin red: `socket.create_connection` falla con `OSError` |
| `docker image inspect` (Env) | sin `DESKPILOT_API_KEY` ni `.env`; `find / -name ".env*"` sin resultados |
| `docker history --no-trunc` | sin secretos; la única coincidencia es `GPG_KEY`, huella pública de la imagen base de Python |
| Tamaño | 423 MB de contenido, 1.47 GB en disco (`docker images`); capas: `pip install` 653 MB, `generate-data/load-db/index` 257 MB |
| Logs del contenedor | sin trazas ni nivel ERROR |

El `data/deskpilot.db` del repo no se tocó (0 filas en `tickets_nuevos`): el contenedor usa su propia copia.

## Estrategia del modelo y del índice

El índice (`data/vectordb/<versión>` + `CURRENT`) y el modelo fastembed (241 MB en `data/vectordb/models`) se generan en una capa del build, como usuario `app`, para no duplicar archivos con `chown -R`. En ejecución `HF_HUB_OFFLINE=1` impide cualquier descarga; la prueba con `--network none` lo confirma. Si cambia la base de conocimiento hay que reconstruir la imagen.

## Limitaciones

- **Modo Fabric no soportado**: la imagen trae `pyodbc` y `libodbc2`, pero no el **Microsoft ODBC Driver 18 for SQL Server**, cuya licencia debe aceptar quien construya la imagen (ver el encabezado del `Dockerfile`). Sin él `DESKPILOT_MODE=fabric` no puede conectarse.
- La `DESKPILOT_API_KEY` es obligatoria (16+ caracteres) y no tiene valor por defecto.
- La imagen pesa ~1.5 GB en disco por `site-packages` (630 MB) y el modelo.
- SQLite vive dentro del contenedor: se pierde al borrarlo salvo que se monte un volumen en `/app/data`.
- Puntos no verificados: ejecución en Linux nativo (solo se probó Docker Desktop en Windows) y el build en CI.
