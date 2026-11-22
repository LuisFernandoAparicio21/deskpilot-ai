# ADR-0008: Docker de una etapa con el modelo en el build

- **Estado:** aceptada
- **Fecha:** 2026-11-22

## Contexto

La imagen debe correr en modo local sin red y sin secretos (RNF-10, RNF-03). Indexar o descargar el modelo en la
primera petición rompería el límite de tiempo y la garantía "no indexar en requests" (ADR-0002).

## Decisión

`Dockerfile` sobre `python:3.13-slim`, de una etapa y con usuario no root (uid 10001). Durante el build se
ejecutan `generate-data`, `load-db` e `index`, que de paso descargan el modelo a `data/vectordb/models`;
`HF_HUB_OFFLINE=1` en ejecución. La llave `DESKPILOT_API_KEY` se pasa en `docker run`. El modo fabric no está
soportado porque falta el ODBC Driver 18, cuya licencia debe aceptar quien construye.

## Alternativas

- **Multietapa:** copiaría de nuevo `site-packages` y los datos (~1 GB).
- **Descargar el modelo al arrancar:** necesita red y alarga el arranque.

## Consecuencias

- Verificado: corre sin root, responde con `--network none`, sin `.env` ni llave en la imagen; ocupa 1.47 GB en
  disco (L20, `docs/features/docker.md`).
- Verificado así antes del reranker. Con el modelo del reranker ([ADR-0009](0009-veto-con-reranker-cross-encoder.md)) el tamaño real está pendiente de medir y el run con `--network none` no se reverificó.
- Datos e índice quedan fijos hasta reconstruir la imagen.
- La imagen no sirve para Fabric sin añadir el driver.

## Fuentes

`docs/sources.md`: Docker Desktop WSL 2 (disco) y fastembed. ODD L19 y L20.
