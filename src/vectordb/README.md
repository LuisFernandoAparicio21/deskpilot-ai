# vectordb
`VectorStore` (Protocol) con `ChromaVectorStore` (coseno, similitud 0–1) e `InMemoryVectorStore` para tests; `indexer.py` es `main.py index`, nunca una petición de la API.
Cada indexación escribe `data/vectordb/<timestamp>/`, valida el conteo y cambia el puntero `CURRENT` con `os.replace`; se conservan las 2 versiones más recientes.
Así ningún proceso escribe en el índice que otro lee: Chroma no es process-safe con una ruta compartida ([Chroma Cookbook](https://cookbook.chromadb.dev/core/system_constraints/)); la API reabre sola con `CurrentStore`.
