# vectordb
`VectorStore` (Protocol) con `ChromaVectorStore` (coseno) e `InMemoryVectorStore`; `indexer.py` es `main.py index`, nunca una petición de la API.
Cada indexación escribe `data/vectordb/<timestamp>/`, valida el conteo y cambia `CURRENT` con `os.replace` (se conservan 2 versiones): Chroma no es process-safe con ruta compartida ([Chroma Cookbook](https://cookbook.chromadb.dev/core/system_constraints/)); la API reabre con `CurrentStore`.
