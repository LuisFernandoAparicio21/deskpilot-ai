# Mecanismos de abstención ("sin evidencia") en RAG pequeño

Fecha de consulta: 2026-11-22. Contexto: 15 artículos, ~64 chunks, fastembed paraphrase-multilingual-MiniLM-L12-v2, Chroma coseno, umbral global 0.33.

## Pregunta
¿Qué mecanismos generales y documentados existen para decidir "sin evidencia" mejor que un umbral global de similitud?

## Respuesta (resumen)
- (a) Reranker cross-encoder: SÍ existe en fastembed 0.9.1 (`fastembed.rerank.cross_encoder.TextCrossEncoder`). Verificado ejecutando `list_supported_models()` en `.venv` (llamada ligera, sin descargar modelos):
  - Xenova/ms-marco-MiniLM-L-6-v2 (0.08 GB, apache-2.0) y L-12-v2 (0.12 GB, apache-2.0): solo inglés.
  - jinaai/jina-reranker-v1-tiny-en (0.13 GB) y turbo-en (0.15 GB), apache-2.0: solo inglés.
  - BAAI/bge-reranker-base (1.04 GB, MIT): chino/inglés (según la ficha del modelo familia BGE; no verificado aquí).
  - BAAI/bge-reranker-v2-m3 (2.27 GB, apache-2.0) y variante int8 (0.57 GB, apache-2.0): multilingüe. Aparecen en el paquete instalado pero NO en la página pública de modelos soportados consultada (la doc va por detrás del paquete).
  - jinaai/jina-reranker-v2-base-multilingual (1.11 GB, CC-BY-NC-4.0): multilingüe, pero licencia no comercial.
  - Para es/en la opción práctica es bge-reranker-v2-m3-int8 (0.57 GB, Apache 2.0). Los ms-marco/jina-v1 son solo inglés: no sirven para consultas en español.
  - Semántica de scores: la ficha de bge-reranker-v2-m3 indica scores crudos no acotados (ejemplos -8.19 a 5.26) y `normalize=True` aplica sigmoide a 0-1; ejemplos 0.0003 (irrelevante) vs 0.9948 (relevante). No da umbral recomendado. Sentence-Transformers describe el cross-encoder como más preciso que el bi-encoder porque aplica atención conjunta consulta-documento, y su flujo recomendado es recuperar candidatos y reordenar; NO habla de abstención ni de umbrales.
  - Costo: descarga 0.57 GB (int8) y dependencia onnxruntime (ya implícita en fastembed); latencia por par consulta-chunk en CPU, con 5-10 candidatos es del orden de cientos de ms (no medido aquí: no verificado). Riesgo: la salida de un reranker mide relevancia relativa; el umbral sobre su score también requiere calibración con el set de evaluación propio, y modelos entrenados con otro dominio pueden rechazar paráfrasis legítimas.
- (b) Cobertura léxica / BM25 como segundo filtro: ninguna de las fuentes consultadas lo documenta como método de abstención. Es una heurística de ingeniería (p. ej. exigir que algún término de contenido de la consulta, tras quitar stopwords y normalizar acentos, aparezca en el chunk top). Costo: casi nulo (sin descarga; `rank_bm25` o código propio). Riesgo alto de falsos rechazos en paráfrasis y sinónimos ("no puedo entrar" vs "acceso"), que es justo lo que los embeddings resuelven; sirve mejor como veto de consultas fuera de dominio con cero solape que como filtro general. Sin respaldo en fuentes: tratar como hipótesis a validar con el eval.
- (c) Umbral por categoría / calibración de scores: no hay fuente oficial consultada que lo respalde para este modelo. La ficha de bge y SBERT no dan umbrales. Con 64 chunks, calibrar por categoría arriesga sobreajuste al set de evaluación. Alternativa válida y barata: calibrar el umbral global (o uno por artículo/categoría) sobre `tests/eval/cases.csv`, eligiendo el valor que maximice recall en casos positivos con precisión aceptable en casos de rechazo; reportar la curva, no un punto. Riesgo: distribución de scores del MiniLM multilingüe depende del idioma y de la longitud de la consulta.
- (d) Margen top1-top2 (gap): ninguna fuente consultada lo documenta para abstención. Con 64 chunks de pocos artículos, varios chunks del mismo artículo son relevantes a la vez, así que un gap pequeño NO implica ausencia de evidencia (falsos rechazos en consultas bien cubiertas por un artículo largo). Usable solo si se calcula entre artículos distintos (agrupando chunks) y como señal secundaria. Costo cero. Sin respaldo en fuentes.

## Decisión recomendada
1. Mantener el umbral de similitud como filtro primario, pero calibrarlo con el eval propio (c) y reportar la curva.
2. Si hace falta más precisión de rechazo: añadir reranker `BAAI/bge-reranker-v2-m3-int8` solo sobre top-k y decidir por su score normalizado, tras medir latencia y descarga reales (0.57 GB). Evitar jina-v2 (CC-BY-NC) y los modelos solo-inglés.
3. Tratar (b) y (d) como heurísticas sin respaldo en fuentes; probarlas en el eval antes de adoptarlas y solo como señales secundarias.

## Qué NO está respaldado por las fuentes
Cobertura léxica/BM25 para abstención, gap top1-top2, umbrales por categoría y latencia real del reranker: no hay evidencia primaria consultada.

## Fuentes
1. FastEmbed, Supported Models (TextCrossEncoder): https://qdrant.github.io/fastembed/examples/Supported_Models/ (2026-11-22). Más inspección local de fastembed 0.9.1 en `.venv`.
2. Sentence-Transformers, Retrieve & Re-Rank: https://sbert.net/examples/applications/retrieve_rerank/README.html (2026-11-22).
3. BAAI/bge-reranker-v2-m3 (ficha del modelo): https://huggingface.co/BAAI/bge-reranker-v2-m3 (2026-11-22).
