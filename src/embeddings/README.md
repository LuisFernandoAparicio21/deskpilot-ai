# embeddings
Protocol `Embedder` con `FastEmbedEmbedder` (`paraphrase-multilingual-MiniLM-L12-v2`, 384 dim, local, vectores L2; modelo cargado perezosamente, ~250 MB en `embeddings.cache_dir`) y `FakeEmbedder`.
`FakeEmbedder` es determinista (hash de tokens sin acentos) para tests y CI sin descargas; `build_embedder` elige por `embeddings.provider`.
