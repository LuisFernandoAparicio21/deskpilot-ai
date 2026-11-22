# ADR-0009: Veto con reranker cross-encoder

- **Estado:** aceptada
- **Fecha:** 2026-11-22

## Contexto

El rechazo ("no lo sé", RF-05) dependía de un umbral global de similitud coseno (0.33) sobre el top-1. En el
experimento de `docs/research/rejection-experiment.md` (62 consultas: 24 a rechazar, 28 a responder, 10 neutras)
ese umbral solo rechaza 11 de 24 consultas fuera de dominio. EV-16 ("badge reader at the vault door") recupera
KB-003 con score 0.525 y se respondía en vez de rechazar, por eso `eval` salía con código 3. Los rangos de
respuestas legítimas con errata (0.43) y de rechazos cercanos (hasta 0.60) se solapan.

## Decisión

Un veto con el cross-encoder `BAAI/bge-reranker-v2-m3-int8` (fastembed `TextCrossEncoder`, Apache-2.0), configurado
en `retrieval.rerank` (`enabled`, `min_score` 0.01, `candidates` 3). Solo veta: no reordena ni sustituye
artículos. Corre únicamente si el top-1 ya supera el umbral coseno, puntúa el mejor chunk de los 3 mejores
artículos **pasaje a pasaje** y, si el máximo queda bajo `min_score`, la respuesta es `no_evidence`. Va después de
las palabras clave de RN-03 (nunca calla una escalación) y la escalación por artículo (KB-011) exige además que
ese artículo supere `min_score`. El modelo se descarga en `main.py index` y se carga al arrancar; con
`embeddings.provider: fake` se desactiva solo. Resultado: `eval` 30/30 con código 0 y `eval.known_failures: []`.

## Alternativas

Medidas en el experimento (24 rechazos, 28 respuestas legítimas; falsos rechazos entre paréntesis):

- **Umbral global calibrado (0.45):** 20/24 con el valor elegido en dev, pero 9/12 en test y 1 falso rechazo
  (CT-02, 0.43). No generaliza; el mejor valor sin falsos rechazos (0.41) da 18/24.
- **Cobertura léxica (prefijo de 5 letras):** sin valor válido; la KB está en español y las consultas correctas en
  inglés comparten pocos términos (cobertura de respuestas 0.00 a 1.00, de rechazos 0.00 a 0.40).
- **Margen top1-top2 (gap):** 11/24, sin mejora; con varios chunks de un mismo artículo el margen no mide
  ausencia de evidencia.
- **Doble evidencia (vetar solo si score < min y coseno < C):** para salvar un caso legítimo (coseno 0.511) hace
  falta C <= 0.51 y entonces se aceptan 6 consultas fuera de dominio (EV-16, HO-28, HO-33, HO-36, RJ-07...).
- **Normalizar consulta o chunk antes del reranker:** con la consulta normalizada el caso Q1 sigue en 0.0192 y
  la errata añade un falso rechazo (HO-03, 0.0186); normalizar también el chunk produce un falso rechazo (HO-02).
- **Sin reranker (`enabled: false`):** sigue disponible como alternativa de costo cero; rechazo 11/24.

## Consecuencias

- Rechazo en el experimento: 24/24 en muestra (12/12 en test con el valor elegido en dev); `eval` 30/30 con p50
  380.5 ms y p95 801.6 ms; top-3 sin cambios (no reordena); 0 falsos rechazos en las 35 consultas en dominio.
- **Hallazgo del batch:** el modelo int8 puntúa un pasaje distinto según los otros del batch (relleno al más
  largo): el mismo par da 0.0192 en un batch de 3 y 0.0481 solo, y vetaba una consulta legítima sin acentos. Por
  eso se puntúa pasaje a pasaje y `min_score` es 0.01 (punto medio geométrico entre el máximo fuera de dominio,
  0.0035, y el mínimo en dominio con variantes, 0.0205). Si cambia el modelo o la versión de fastembed, repetir
  la medición.
- Costo: ~0.57 GB de descarga (2 modelos con el de embeddings), ~0.5 a 1 s por consulta en CPU y más RAM. Docker:
  el modelo se descarga en el build; el tamaño de la imagen con el reranker está pendiente de medir y el run con
  `--network none` no se verificó. CI: la primera corrida tras tocar `retrieval.rerank` descarga 0.57 GB (cambia la
  clave de caché); no verificado en GitHub Actions.
- **Escalamiento obligatorio (RN-03):** KB-011 se puntúa siempre que aparezca en los resultados (aunque quede fuera de
  los 3 candidatos) y el veto solo lo descarta con ruido claro (score < `min_score` x `mandatory_veto_factor` 0.1);
  el margen de coseno sigue siendo el criterio base. RN-03 prima sobre la precisión: ante duda, escalar.
- **Cadena de suministro (límite):** el modelo se baja del Hugging Face Hub sin fijar la revisión a un hash, así que
  una actualización del repositorio cambiaría los scores sin aviso. `retrieval.rerank.model` se valida contra una
  allow-list (hoy solo `BAAI/bge-reranker-v2-m3-int8`) y falla al arrancar con un mensaje claro. Pendiente: fijar la
  revisión (hash de commit) y verificar el checksum del `.onnx` tras la descarga.
- Límite honesto: **HO-29** ("wifi de casa", score 0.052) se sigue respondiendo; el held-out de 40 casos ya no es
  ciego porque se usó para elegir el corte (39/40). La muestra es pequeña y la escribió el mismo autor.

## Fuentes

`docs/research/rejection-experiment.md` y `docs/research/rag-abstention-mechanisms.md`; ODD L36.
