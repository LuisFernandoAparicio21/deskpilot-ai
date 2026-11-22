# Evaluación end-to-end (T21)

Feature T21 (rama `feat/t21-eval-e2e`). Cubre S12, RNF-01 y las métricas de la sección 12 de `docs/requirements.md`.
Los datos son sintéticos (banco ficticio "Banco Altiplano"); las cifras son ilustrativas.

## Qué hace

`python main.py eval` ejecuta los 30 casos de `tests/eval/cases.csv` contra las herramientas del agente
(`buscar_solucion` y `crear_ticket`), compara cada resultado con lo `esperado`, calcula las métricas de la
sección 12 y escribe `tests/eval/results.csv` más `tests/eval/results.summary.json`.

```bash
.venv\Scripts\python main.py eval                                  # modo local, índice real
.venv\Scripts\python main.py eval --cases otra.csv --out scratch\r.csv
.venv\Scripts\python main.py eval --api-url http://localhost:8000   # modo HTTP (clave en DESKPILOT_API_KEY)
```

### Formato de `cases.csv`

UTF-8, con encabezado: `id,pregunta,intencion,esperado,obtenido,resultado,notas`. `id`, `pregunta`,
`intencion` y `esperado` son entradas; `obtenido`, `resultado` y `notas` los llena la corrida (se sobrescriben).
`results.csv` tiene las mismas columnas más `latencia_ms`; `resultado` vale `pasó` o `falló`. La pregunta se
escribe ya redactada (RN-05): un secreto pegado nunca llega a los resultados.

### Valores de `esperado`

| Valor | Pasa cuando |
| --- | --- |
| `articulo:KB-004` | El artículo está en el top 3 y el estado es `answered` |
| `rechazo` | El estado es `no_evidence` ("no lo sé", RN-04) |
| `escalamiento` | El estado es `mandatory_escalation` (RN-03) |
| `ticket:categoria=Accesos;prioridad=P1` | `crear_ticket` (con la pregunta como descripción) devuelve cada `clave=valor`; claves: `categoria`, `subcategoria`, `prioridad`, `escalado`; sin distinguir mayúsculas |
| `seguridad` | Respuesta y ticket advierten del secreto y este no aparece en respuestas, ticket persistido ni logs (en proceso) |

Composición de los 30 casos: 14 de artículo (EV-01 a EV-14), 4 de rechazo (EV-15 a EV-18), 4 de escalamiento
(EV-19 a EV-22), 5 de ticket (EV-23 a EV-27) y 3 de seguridad (EV-28 a EV-30); hay variantes en inglés.

### Umbrales (sección 12) y códigos de salida

| Métrica | Mide | Meta |
| --- | --- | --- |
| `retrieval_top3` | Casos `articulo` aprobados | >= 90% |
| `rechazo` | Casos `rechazo` aprobados | 100% |
| `clasificacion` | Casos `ticket` aprobados | >= 85% |
| `seguridad` | Casos `seguridad` aprobados | 100% |
| `aprobados` (`min_passed`) | Los 30 casos | >= 27 de 30 (90%) |

Una métrica sin casos se muestra "n/a" y no falla. Las metas viven en `config.yaml` (sección `eval:`) y son las de
la sección 12 de `docs/requirements.md`; no se bajan para que pase una corrida.

### Contrato de códigos de salida

| Código | Significado | Cuándo |
| --- | --- | --- |
| **0** | Todo cumple | Todos los criterios `target` cumplidos y ningún caso falla |
| **3** | Objetivo no cumplido, sin regresión | El mínimo global (`min_passed`) y la seguridad (`security_pct` = 100) se cumplen y ningún caso nuevo falla, pero algún criterio no se cumple o falla un caso de `known_failures` |
| **1** | Regresión | Se rompe el mínimo global o la seguridad, o falla un caso que NO está en `known_failures` |
| **2** | Error de configuración o infraestructura | `config.yaml` inválido, CSV inválido, sin índice o base, `--out` igual al archivo de casos, clave HTTP rechazada 401/403, servidor inalcanzable |

El reporte por consola y `results.summary.json` separan los criterios no cumplidos, los fallos conocidos que
fallaron (`known_failures_hit`, con su motivo), los fallos nuevos (`new_failures`) y los fallos conocidos que ya
pasan (`known_failures_fixed`: hay que quitarlos de la config). El JSON añade `known_failures_ignored` (ids de `known_failures` que no están en el CSV usado, p. ej. un `--cases` personalizado o CSV de prueba: se ignoran con una advertencia en stderr, `known failure EV-16 not in this cases file; ignored`, y no dan exit 2), `criteria` (por criterio: `target`,
`actual`, `met`), `exit_code` y `exit_reason`.

**Estado actual (PL-8):** `main.py eval` sale con **exit 0** (30/30, `known_failures: []`, `exit_reason` "all target criteria met"). El exit 3 sigue en el contrato para futuros fallos conocidos, pero hoy ninguna corrida normal lo produce. Con `--cases tests/eval/heldout_cases.csv` sale con exit 1 por HO-29 (consulta fuera de dominio que se responde; ver Limitaciones).

**Migración (cambio de contrato).** Antes: 0 = umbrales cumplidos, 1 = algún umbral no cumplido, 2 = error.
Ahora el 1 significa solo regresión y "objetivo no cumplido" pasó a ser el 3. Quien tolerara el 1 (el CI lo hacía
por EV-16) debe pasar a aceptar 0 y 3, y tratar 1 y 2 como fallo. Un script que solo conozca 0/1/2 verá 3 como
"código desconocido": decide explícitamente.

### Configuración (`config.yaml`)

```yaml
eval:
  thresholds:                 # en %, rango 0-100
    retrieval_top3_pct: 90
    rejection_pct: 100
    classification_pct: 85
    security_pct: 100
    min_passed: 90            # mínimo global: % de casos aprobados
  known_failures: []          # vacío desde PL-8; EV-16 estuvo aquí hasta que el veto del reranker lo resolvió
```

Histórico: hasta PL-8 la lista contenía `EV-16` ("rechazo: umbral global sin rerank, score 0.525 vs umbral 0.33").

Se valida con Pydantic al arrancar (fail-fast, exit 2): rangos 0-100, `id` con formato `EV-NN`, `reason` no vacío, ids
sin duplicar y existentes en el CSV de casos.

**Cómo añadir un `known_failures`.** Solo para una limitación real y diagnosticada, no para una regresión:
1. Identifica la causa raíz del fallo y documéntala (feature doc o diagnóstico).
2. Añade `id` y un `reason` que nombre la causa en `config.yaml`, en un PR revisable.
3. Quita la entrada cuando el caso pase (la corrida lo avisa).

`known_failures` **NO** se usa para ocultar regresiones: un caso que falla y no está en la lista sale con 1, y el CI
imprime siempre los criterios no cumplidos como `::warning::`; el exit 3 nunca se presenta como verde silencioso.

### Modos

- **Local (por defecto)**: todo en proceso. `AnswerService` sobre el índice `CURRENT` y `TicketService` sobre una
  copia temporal de la base SQLite; nunca se toca `data/deskpilot.db`. Con `llm.provider: none` no necesita clave.
- **HTTP (`--api-url`)**: llama a la API con `X-API-Key`. **Advertencia: crea tickets reales** en la base del
  servidor (los casos de ticket y seguridad crean tickets); el comando lo avisa por stderr. Además, el top 3 es
  solo el artículo citado (la API devuelve uno) y la persistencia y los logs no se pueden verificar.

## Specs y requerimientos

S12 (evaluación), RNF-01 (p95 en e2e), RF-05/RN-04 (rechazo), RN-03 (escalamiento), RN-01 (clasificación),
RN-05 (datos sensibles) y las métricas de la sección 12. Los logs de la corrida llevan ids, conteos y estados,
nunca preguntas ni respuestas.

## Pruebas realizadas

| Archivo | Qué valida |
| --- | --- |
| `tests/unit/test_evaluation_cases.py` | Parseo de `esperado`, carga del CSV (BOM, columnas faltantes, duplicados, vacío), veredictos por tipo, un caso con error no detiene la corrida, y que `cases.csv` tiene 30 casos válidos con las columnas documentadas |
| `tests/unit/test_evaluation.py` | Veredicto `seguridad` (fuga en respuesta, ticket, persistido o logs; tarjeta sin espacios), cabecera exacta de `results.csv`, sobrescritura de `obtenido`, resumen JSON, umbrales (27/30, 90% redondeado hacia arriba, 100%, 85%), código de salida y percentiles de latencia |
| `tests/unit/test_evaluation_cli.py` | Códigos 0/1/2 del CLI, `--out` igual a `--cases` (también con alias de ruta), backend HTTP (401/403 abortan sin imprimir la clave, 5xx falla solo el caso, respuestas mal formadas, servidor inalcanzable), URL sin esquema, clave obligatoria y advertencia de tickets reales en stderr (ausente en modo local) |
| `tests/unit/test_escalation_policy.py` | Patrones RN-03 de caja (`cash_system`) y acceso no autorizado (`unauthorized_access`), con y sin acentos, positivos y negativos, y que `crear_ticket` crea un ticket P1 escalado |
| `tests/integration/test_escalation_by_article.py` | Una consulta de caja sin palabra clave escala por KB-011 solo si KB-011 es top-1; sin KB-011 arriba no escala |
| `tests/e2e/test_e2e.py` | Datos generados -> SQLite -> índice -> API -> los 30 casos en un directorio temporal. Rápidas (embedder falso): escalamiento por policy, clasificación, secretos, base del repo intacta (sha256), modo HTTP con los mismos veredictos, clave incorrecta y falta de índice como error de configuración. `slow` (modelo fastembed real): cada caso y los umbrales; EV-16 es `xfail` estricto |

## Resultados reales

Corrida de `python main.py eval` (modo local, índice real, reranker activo, `retrieval.rerank.min_score` 0.01) el 2026-11-22, valores de `tests/eval/results.summary.json`:

```text
retrieval_top3  14/14  100.0%  (meta >= 90%)   ok
rechazo         4/4    100.0%  (meta >= 100%)  ok
clasificacion   5/5    100.0%  (meta >= 85%)   ok
seguridad       3/3    100.0%  (meta >= 100%)  ok
aprobados       30/30  100.0%  (meta >= 90%)   ok
latencia por caso: p50 380.5 ms, p95 801.6 ms
veredicto: exit 0 (all target criteria met)
```

**Caso histórico: EV-16** ("My badge reader at the vault door shows error 77."). El esperado es `rechazo`. Antes de PL-8 el sistema respondía `answered` citando KB-003 con score coseno 0.525, por encima del umbral global 0.33 (no había rerank), y el rechazo era 3/4 con exit 3. El veto del reranker cross-encoder (puntuación pasaje a pasaje; [ADR-0009](../adr/0009-veto-con-reranker-cross-encoder.md), [experimento](../research/rejection-experiment.md)) lo rechaza, `EV-16` salió de `eval.known_failures` y la corrida da exit 0. La latencia por caso subió (antes ~13 a 14 ms con embedder; ahora p50 380.5 ms) porque incluye el reranker.

### Pruebas y calidad

`pytest --cov=src --cov-report=term`: **1946 passed, 2 skipped, 35 deselected (slow)** (corrida completa del 2026-11-22), cobertura total
**98.02%** (meta >= 80%). Los 2 omitidos: un test sin parámetros y el validador opcional `openapi-spec-validator`. En esa corrida 3 tests de contrato fallan (fijan EV-16 y exactamente 8 ADR; no se editaron).
`pytest -m slow tests/e2e` (histórico, antes de PL-8): 30 passed, 2 xfailed (EV-16 y el umbral global); no se reejecutó con el reranker en esta corrida (no verificado). `ruff check .` y `mypy src main.py` no se reejecutaron en la actualización de docs.

## Cómo verificarlo paso a paso

```bash
.venv\Scripts\python main.py index                      # índice real (si aún no existe)
certutil -hashfile data\deskpilot.db SHA256             # anotar el hash
.venv\Scripts\python main.py eval --out scratch\results.csv
echo %ERRORLEVEL%                                       # 0 (todos los criterios cumplidos)
certutil -hashfile data\deskpilot.db SHA256             # debe ser igual
.venv\Scripts\python -m pytest --cov=src --cov-report=term
.venv\Scripts\python -m pytest -m slow tests/e2e        # modelo real
.venv\Scripts\ruff check .
.venv\Scripts\mypy src main.py
```

## Hallazgos de QA y seguridad

- **Sobre-escalamiento por KB-011**: escalaba si KB-011 aparecía en cualquier posición del top, lo que escalaba
  EV-05, EV-07 y EV-09. Ahora solo escala si KB-011 está a menos de `retrieval.escalation_margin` (0.05) del
  top-1; fuera del margen se descarta de la evidencia (no se cita ni llega al LLM). El margen se calibró con la KB
  real (el ruido queda a 0.29-0.33 del top-1). Con el reranker, KB-011 siempre se puntúa si aparece en los
  resultados (aunque quede fuera de los 3 candidatos) y solo se descarta por el veto si su score es < `min_score` x
  `mandatory_veto_factor` (0.1), es decir, ruido claro; RN-03 prima sobre la precisión.
- **EV-20** ("inicios de sesión de mi cuenta a las 3 am que yo no hice") no escalaba: se añadió la detección de
  actividad de acceso no reconocida como `unauthorized_access`.
- **Patrones RN-03 ampliados**: caja caída, POS, "nadie puede cobrar", "alguien robó mi cuenta", "acceso
  indebido" (ES/EN, con y sin acentos), con negativos para evitar falsos positivos ("caja de ahorro").
- El modo HTTP avisa por stderr que crea tickets reales.

## Limitaciones

- EV-16 ya no falla (histórico, PL-8). El límite honesto actual es HO-29 ("wifi de casa"): score de reranker 0.052, sobre el corte 0.01, se responde en vez de rechazar; `heldout_cases.csv` da 39/40 y ya no es un conjunto ciego.
- El reranker añade ~0.57 GB de descarga (2 modelos con el de embeddings) y ~0.5 a 1 s por consulta; el CI y `docker run --network none` con el reranker no se verificaron.
- Los 30 casos son pocos y los redactó el equipo: miden regresión, no generalización.
- En modo HTTP el top 3 se reduce al artículo citado y no se verifica persistencia ni logs.
- La latencia es de la capa local (sin LLM ni red); no representa la de Copilot Studio.
- El comportamiento real del agente en Copilot Studio no está medido aquí: ver T32 en `docs/testing-procedure.md`.
