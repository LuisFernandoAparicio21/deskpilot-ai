# ADR-0002: ChromaDB coseno con índice versionado y puntero CURRENT

- **Estado:** aceptada
- **Fecha:** 2026-11-22

## Contexto

RF-15 pide reindexar la base de conocimiento sin detener la API. El Chroma Cookbook indica que Chroma "is not
process-safe for concurrent writers", y la documentación oficial no cubre ese caso. En Windows, además, no se
puede borrar un índice abierto.

## Decisión

Chroma local con `configuration={"hnsw": {"space": "cosine"}}` (similitud = `1 - d`, acotada a 0..1) detrás de
una interfaz `VectorStore`. `main.py index` escribe un índice nuevo en `data/vectordb/<ts>/` y mueve de forma
atómica el puntero `CURRENT` con `os.replace`; la poda respeta los índices abiertos. La API nunca indexa en una
petición: solo lee el índice al que apunta `CURRENT`. En Docker el índice se prepara al construir.

## Alternativas

- **Reindexar sobre la misma colección:** simple, pero con dos procesos arriesga corrupción.
- **FAISS:** opción válida sin servidor; Chroma ya guarda metadatos para el filtro por categoría (RF-12) y la interfaz `VectorStore` permite cambiar luego.

## Consecuencias

- Un lector hizo 3,841 consultas mientras otro proceso reindexaba, sin errores (L13).
- Ocupa más disco por versiones viejas hasta que la poda las borra.
- Los cambios de la base de conocimiento solo se ven tras `main.py index`.

## Fuentes

`docs/sources.md`, sección Embeddings y base vectorial (T14): Chroma Configure, Chroma Cookbook System
constraints, Python `os.replace`. ODD L13.
