# embeddings
Protocol `Embedder` con `FastEmbedEmbedder` (fastembed, `paraphrase-multilingual-MiniLM-L12-v2`, 384 dimensiones, local y sin llaves) y `FakeEmbedder`.
El modelo se carga perezosamente y se descarga una vez (~250 MB) en `embeddings.cache_dir`; los vectores salen normalizados (L2).
`FakeEmbedder` es determinista (hash de tokens sin acentos), para que los tests y el CI no descarguen modelos; `build_embedder` elige por `embeddings.provider`.
