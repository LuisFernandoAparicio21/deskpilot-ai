# Experimento de rechazo ("no lo sé") con mecanismos generales

> **Resumen vigente (2026-11-22).** `retrieval.rerank.min_score` = **0.01** (no 0.004 ni 0.02): las secciones con esos valores abajo son **histórico** y se conservan como registro del proceso. Vigente: reranker `bge-reranker-v2-m3-int8` puntuado pasaje a pasaje; el veto sobre el artículo de escalamiento obligatorio (KB-011) solo aplica con ruido claro (score < `min_score` x `mandatory_veto_factor` 0.1) y KB-011 se puntúa siempre aunque quede fuera de los candidatos. Resultado: `eval` 30/30, `rejection_cases` 8/8, held-out 39/40 (solo HO-29), 0 falsos rechazos.
> **Límite de la cadena de suministro:** el modelo se descarga de Hugging Face Hub sin fijar la revisión a un hash; una actualización del repositorio del modelo cambiaría los scores sin aviso. Mitigación parcial: `retrieval.rerank.model` se valida contra una allow-list (solo `BAAI/bge-reranker-v2-m3-int8`). Pendiente: fijar la revisión (commit hash) y verificar un checksum del `.onnx` tras la descarga; mientras tanto, repetir la medición si cambia el modelo o fastembed.


Fecha: 2026-11-22. Rama `feat/rejection-cases`. Cierra la parte experimental de P5 de `docs/diagnostics/2026-11-22-review.md` y prueba las hipótesis de `docs/research/rag-abstention-mechanisms.md`. Scripts y datos crudos vivían en `scratch/` (borrado al cerrar).

## Pregunta
¿Algún mecanismo general mejora el rechazo (umbral global 0.33 sobre el score coseno del top-1) sin falsos rechazos y sin bajar el top-3?

## Protocolo
Índice real (fastembed MiniLM multilingüe, 64 chunks), `retriever.search` con `top_k=5`.

| Conjunto | n | Etiqueta |
| --- | --- | --- |
| `cases.csv` rechazo (EV-15..18) | 4 | debe rechazar |
| `rejection_cases.csv` (RJ-01..08) | 8 | debe rechazar |
| Fuera de dominio adicionales (OOD-01..12, ES/EN, ajenas y cercanas: aire acondicionado, Instagram corporativo, tasa de ahorro, vacaciones, certificado web, chiste, vuelos, BGP Cisco, contadora de billetes, CEO, llanta, 2FA de Gmail) | 12 | debe rechazar |
| `cases.csv` articulo (EV-01..14) + seguridad EV-28/29 | 16 | debe responder |
| Control en dominio parafraseado con erratas y jerga (CT-01..12, ES/EN) | 12 | debe responder |
| EV-19..27 y EV-30 (escalamiento por palabras clave, tickets, CURP) | 10 | neutros: el pipeline decide antes o aparte de la recuperación, no cuentan como falso rechazo (se informa si el veto los tocaría) |

Total 62 consultas: 24 a rechazar, 28 a responder, 10 neutras. OOD y control se escribieron antes de ver ningún score. Validación: partición determinista dev/test por paridad dentro de cada grupo (31/31; 12 rechazos en cada mitad). El hiperparámetro de cada mecanismo se elige en dev como el que más rechaza con CERO falsos rechazos en dev y se reporta en test. No se ajustó nada por caso.

## Resultados

| Mecanismo | Rechazo correcto, todo (24) | Test (12), param elegido en dev | Falsos rechazos (de 28) | Top-3 artículo (14) | Latencia añadida | Dependencias / descarga |
| --- | --- | --- | --- | --- | --- | --- |
| Base: umbral 0.33 | 11/24 (46%) | 5/12 | 0 | 14/14 | 0 | ninguna |
| (4) Calibración del umbral | 20/24 con el valor de dev (0.45) | 9/12 | 1 (CT-02, score 0.43) | 14/14 | 0 | ninguna |
| (1) Cobertura léxica (prefijo de 5 letras, stopwords ES/EN) | sin valor válido | sin valor válido | ya con 0.05 rechaza EV-29 y CT-07 (cobertura 0.00); con valores mayores también EV-03/09/12 (EN contra KB en español, cobertura 0.20-0.33) | 14/14 | ~0 | ninguna |
| (2) Margen top1-top2 entre artículos | 11/24 (sin mejora) | 5/12 | 0 con p=0 | 14/14 | ~0 | ninguna |
| (3) Reranker `bge-reranker-v2-m3-int8`, mejor chunk de los 3 mejores artículos, sigmoide, p=0.003 | 24/24 (100%) | 12/12 | 0 | 14/14 (no reordena) | p50 0.66 s, p95 1.03 s (3 pares, CPU de esta máquina) | 0.57 GB (561 MB en disco); onnxruntime ya implícito en fastembed |

Variantes del reranker: puntuar todos los chunks de los 3 artículos (~11 pares) también da 24/24 pero cuesta p50 3.7 s y p95 4.8 s; puntuar solo el top-1 también da 24/24 pero es menos robusto. Se eligió el mejor chunk de 3 artículos.

Observaciones por mecanismo:
- Calibración: el mejor valor sin falsos rechazos usando todos los datos es 0.41 (18/24), pero el valor elegido solo con dev (0.45) ya rechaza CT-02 en test. Rangos que se solapan: respuestas legítimas con errata 0.43, rechazos cercanos hasta 0.60 (RJ-07, impresora Zebra). No generaliza.
- Léxica: la KB está en español; las consultas correctas en inglés comparten pocos términos. No separa (cobertura de respuestas 0.00-1.00, de rechazos 0.00-0.40).
- Margen: gap de rechazos 0.00-0.10, de respuestas 0.00-0.40; con varios chunks de un mismo artículo y consultas reales el margen no mide ausencia de evidencia.
- Reranker: separación clara. Máximo en rechazos 0.0012 (sigmoide del mejor chunk), mínimo en respuestas 0.0104 (CT-08). Banda sin falsos rechazos y 24/24: 0.002 a 0.010 (con 0.012 ya rechaza CT-08). Se fijó `min_score: 0.004` (punto medio en logit).

## Decisión: se implementa el reranker (histórico: min_score 0.004; vigente 0.01) (único que cumple el criterio)
Criterio: mejora el rechazo, ningún falso rechazo nuevo (canónicos ni control), top-3 14/14. Solo el reranker lo cumple de forma validada. Es el mecanismo más caro (modelo de 0.57 GB, ~0.7 s por búsqueda); los ligeros se probaron primero y no pasan la validación, por lo que no hay alternativa ligera que cumpla el criterio.

Implementación (`retrieval.rerank` en `config.yaml`, validado por Pydantic, apagable con `enabled: false`):
- Solo veto: no reordena ni sustituye artículos. Corre solo si el top-1 ya pasa el umbral coseno.
- Va después de RN-03 por palabras clave (nunca calla una escalación). La escalación por artículo (KB-011) exige además que el artículo obligatorio supere el `min_score` (así RJ-02, "autorizar acceso físico a la bóveda", ya no escala por ruido de KB-011).
- El modelo se descarga en `main.py index` (build time) y se carga al arrancar API/eval (`warm()`); nunca dentro de una petición. Con `embeddings.provider: fake` el reranker se desactiva solo (tests, CI sin descarga).
- Logs: solo `rerank_score` y `vetoed` numéricos; no hay texto de consulta.

Resultado con el servicio real: `main.py eval` 30/30 (rechazo 4/4, EV-16 ahora pasa, se quita de `eval.known_failures`), `rejection_cases.csv` 8/8, OOD 12/12 rechazadas, control 12/12 respondidas.

Impacto en Docker y CI:
- Imagen: +~0.56 GB por el modelo descargado en `RUN python main.py index` (antes ~0.25 GB de embeddings): el modelo pasa a ser ~0.8 GB de la imagen. Sigue sin red en runtime (`HF_HUB_OFFLINE=1`).
- CI: el paso `index` descarga el modelo; la caché `data/vectordb/models` usa la clave de `config.yaml`, que ahora cambia al tocar `retrieval.rerank`; la primera corrida tras el cambio descarga 0.57 GB.
- Inferencia en CPU: ~0.7 s p50 por búsqueda; el p50 de `eval` por caso pasó de ~0.45 s a ~0.45-0.8 s según el grupo.
- Alternativa de costo cero: `retrieval.rerank.enabled: false` vuelve al umbral solo (rechazo 11/24 en este conjunto).

## Límites de la muestra
- n pequeño: 24 rechazos y 28 respuestas; un caso mueve ~4 puntos. 24/24 es observado, no una tasa de población.
- `min_score` final (0.004) se fijó con el punto medio de la brecha sobre las 62 consultas: el 24/24 es en muestra para ese valor. La cifra honesta de generalización es la de test (12/12) con el valor elegido solo en dev (0.003), y la banda segura 0.002-0.010 es estrecha (5x); un caso con paráfrasis más débil podría quedar por debajo.
- El conjunto OOD y el control los escribió el mismo autor del experimento; no son una muestra independiente ni de usuarios reales. Las consultas cercanas son pocas.
- Latencia medida en una sola máquina (CPU de escritorio), 62 consultas, sin carga concurrente ni arranque en frío del modelo (carga ~2 s tras la primera descarga).
- Un cross-encoder entrenado en otro dominio puede rechazar paráfrasis legítimas muy alejadas del texto (CT-08 queda a 0.0104 del corte). Recalibrar si cambia el modelo, la KB o se amplía el control.
- Los casos neutros EV-19/21/22/27/30 tendrían veto del reranker (scores 0.0001-0.001); no cambian el resultado porque la escalación por palabras clave, el ticket o la advertencia de dato sensible ocurren antes o aparte.
- No verificado: comportamiento con otros idiomas, KB mayor de 15 artículos y tamaño real de la imagen Docker (no se construyó).

## Actualizacion: min_score 0.02 tras la validacion independiente (2026-11-22) (histórico: reemplazado por 0.01)

- El qa-tester valido con un held-out de 40 casos (`tests/eval/heldout_cases.csv`): con reranker 0/20 falsos rechazos y 19/20 rechazos; sin reranker 9/20. Barrido de `min_score` 0.002/0.004/0.010/0.02: 0 falsos rechazos en todos. El minimo en dominio observado es 0.104.
- Decision: `retrieval.rerank.min_score = 0.02` (>=5x por debajo del minimo en dominio, por encima del ruido de los OOD cercanos ~0.003). HO-33 puntua 0.0032, demasiado cerca de 0.004.
- **El held-out se uso para elegir este valor, por lo que ya no es un conjunto ciego**: sus cifras (rechazo 19/20, 0 falsos rechazos) son en muestra para 0.02.
- Limitacion conocida, no ocultada en config: **HO-29** ("wifi de casa") recupera KB-001 con score 0.052, por encima de 0.02, y se responde en vez de rechazar. Subir el corte a >0.052 se acercaria al minimo en dominio; no se hizo. `eval.known_failures` es global y no se toco, por eso `eval --cases tests/eval/heldout_cases.csv` sale con exit 1 por HO-29.
- Medido con 0.02: `eval` 30/30 (exit 0, p50 420 ms, p95 1000 ms); `rejection_cases.csv` 8/8; `heldout_cases.csv` 39/40 (HO-29).

## Robustez a variantes de la consulta y causa del falso rechazo (2026-11-22)

Hallazgo: "no puedo entrar a mi cuenta, se me bloqueo la contrasena" (sin acentos) daba `no_evidence` con `min_score` 0.02 aunque el top-3 tenia KB-002; con acentos respondia. Se midio con variantes generadas automaticamente (sin escoger a mano) de las 35 consultas en dominio (cases + held-out + ese caso) y de los 32 rechazos (EV, RJ, HO): (a) sin acentos y n por n, (b) minusculas sin puntuacion, (c) un swap determinista de dos letras adyacentes de la palabra mas larga (semilla 7). Reranker real, lotes de 12 consultas.

**Causa.** No eran los acentos. El modelo int8 puntua un pasaje distinto segun los otros pasajes del batch (relleno hasta el mas largo): el mismo par (consulta, KB-002) da 0.0192 en un batch de 3 y 0.0481 solo, y el retriever los puntuaba en batch de 3. 0.0192 < 0.02 => veto. Los acentos si bajan el score (con acentos 0.159, sin ellos 0.048 solo), pero no lo llevan bajo el corte. Normalizar la consulta o el chunk no ayuda: la consulta normalizada sigue en 0.0192 en batch; el chunk normalizado (minusculas y sin acentos) hunde al cross-encoder (HO-02 0.0019, falso rechazo) y deja pasar OOD (HO-21 0.64).

Falsos rechazos atribuibles al reranker (de 35 en dominio, con coseno >= 0.33) y rechazos aceptados (de 32; HO-29 es el conocido):

| Variante | Batch (antes) FR / min score | Pasaje a pasaje FR / min score | Aceptados OOD (ambos) |
|---|---|---|---|
| original | 1 (Q1) / 0.0192 | 0 / 0.0481 | 1 (HO-29) |
| sin acentos | 1 (Q1) / 0.0192 | 0 / 0.0481 | 0 |
| minusculas sin puntuacion | 0 / 0.0611 | 0 / 0.0351 | 1 (HO-29) |
| errata | 0 / 0.0276 | 0 / 0.0205 | 0 |

La errata hace que HO-13 y HO-16 caigan bajo el umbral coseno (0.308, 0.222): es limite del embedder, igual sin reranker, y no un falso rechazo del veto. Mediana de score en dominio: 0.95 original, 0.92 sin acentos, 0.93 sin puntuacion, 0.77 errata. Maximo OOD (sin HO-29): 0.0035 en todas las variantes. Con otras configuraciones (consulta normalizada al buscar con el embedder: sin efecto relevante).

Candidatos evaluados:
- (i) normalizar la consulta para el reranker: Q1 sigue en 0.0192 (1 FR) y la errata añade HO-03 (0.0186). Descartado.
- (ii) normalizar tambien el chunk: HO-02 falso rechazo en todas las variantes y OOD aceptados (HO-21). Descartado.
- (iii) doble evidencia (vetar solo si score < min y coseno < C): para salvar Q1 (coseno 0.511) hace falta C <= 0.51, y entonces se aceptan 6 OOD (EV-16, HO-28, HO-33, HO-36, RJ-07 ...), con C=0.6 solo HO-29/HO-33 pero Q1 vuelve a vetarse. Descartado.
- Elegido: puntuar pasaje a pasaje (sin dependencia del batch; mas rapido: 0.48 s vs 0.71 s para 3 pasajes) y `min_score` 0.01, punto medio geometrico entre el maximo OOD (0.0035) y el minimo en dominio con variantes (0.0205). Con 0.02 el margen de la errata era 1.03x.

Resultado con el servicio real y `min_score` 0.01: `eval` 30/30 (rechazo 4/4, exit 0, p50 368 ms), `rejection_cases.csv` 8/8, `heldout_cases.csv` 39/40 (OOD 19/20, solo HO-29), top-3 sin cambios (el reranker no reordena). Q1 y su version con acentos ya se responden (0.048 y 0.130). `eval.known_failures` queda `[]`.

Limites: variantes automaticas y sencillas (una errata por consulta); el held-out ya no es ciego; HO-29 sigue aceptado (0.052, por encima del corte); n de 35 en dominio. Si se cambia de modelo o de version de fastembed, repetir esta medicion.

## Veto y KB-011 (RN-03): factor del ruido claro (2026-11-22)

Hallazgo de seguridad: el veto excluía KB-011 de `relevant` si su score era < `min_score`; una consulta de caja parafraseada sin las palabras de la regex `cash_system` podía perder la red semántica. Además KB-011 solo se puntuaba si estaba entre los 3 candidatos. Cambio: KB-011 se puntúa siempre que aparezca en los resultados, y se descarta solo con score < `min_score` x `mandatory_veto_factor`; el margen de coseno sigue siendo el criterio base.

Medición (reranker real, 12 paráfrasis de caja ES/EN sin palabras de la regex en `scratch/`, ya borradas, más los 30 canónicos, 8 de rechazo y 40 held-out). Factores 1.0 (comportamiento anterior), 0.5, 0.25, 0.1 y 0.0 (sin veto):

| Caso | Score KB-011 | Relación con min_score | Resultado |
| --- | --- | --- | --- |
| RJ-02 (bóveda, ruido; KB-011 dentro del margen) | 0.00005 | 0.005x | rechaza con factor >= 0.1; con 0.0 escala (falla) |
| EV-16 (bóveda, ruido; fuera del margen) | 0.00107 | 0.107x | rechaza con cualquier factor |
| Paráfrasis de caja (dentro del margen): CA-01/03/04/05/06/09/11/12 | 0.011 a 0.96 | 1.1x a 96x | escalan con cualquier factor |
| CA-07 y CA-08 (EN, fuera del margen) | 0.0022 y 0.0045 | 0.22x y 0.45x | no escalan con ninguno: los filtra el margen de coseno, no el veto |
| CA-02 y CA-10 | 0.758 y no recuperado | - | no escalan con ninguno (margen; CA-10 sin KB-011 en el top-5) |

Elegido: **0.1**. Los resultados son idénticos entre 0.1 y 1.0 en estos conjuntos; 0.1 deja el ruido medido (RJ-02 0.005x, EV-16 0.107x) bajo o en el corte y mantiene en escalamiento todo caso de caja con score >= 0.1x, por el lado seguro. Resultado: `eval` 30/30, `rejection_cases` 8/8, held-out 39/40 (19/20 rechazos, 0 falsos rechazos); ningún caso existente cambia de veredicto. Escalan 8 de 12 paráfrasis; las 4 que no escalan (CA-02, CA-07, CA-08, CA-10) fallan por la regla de margen de coseno (KB-011 a más de 0.05 del top-1), igual con y sin veto: es un límite de la regla base, no del veto (n pequeño, mismas manos que escribieron los casos). Posible mejora no aplicada: tratar KB-011 como relevante si su score del reranker es alto (CA-02: 0.758), pendiente de validar con más datos.
