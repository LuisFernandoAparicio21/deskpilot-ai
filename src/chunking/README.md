# chunking
`section_chunker.py` divide cada artículo en un chunk por sección (síntoma, causa, pasos, escalar) con id `KB-001#pasos#0`.
Subdivide las secciones mayores a `chunk_size` con `chunk_overlap` y guarda metadatos planos (artículo, sección, categoría, fuente).
