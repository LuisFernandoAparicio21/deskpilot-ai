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
| `aprobados` | Los 30 casos | >= 27 de 30 |

Una métrica sin casos se muestra "n/a" y no falla. Códigos de salida: **0** todos los umbrales se cumplen,
**1** algún umbral no se cumple, **2** error de configuración o infraestructura (CSV inválido, sin índice o
base, `--out` igual al archivo de casos, clave HTTP rechazada 401/403, servidor inalcanzable).

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

Corrida de `python main.py eval` (modo local, índice real, `--out scratch\results.csv`) el 2026-11-22:

```text
retrieval_top3  14/14  100.0%  (meta >= 90%)   ok
rechazo         3/4    75.0%   (meta >= 100%)  BELOW
clasificacion   5/5    100.0%  (meta >= 85%)   ok
seguridad       3/3    100.0%  (meta >= 100%)  ok
aprobados       29/30  96.7%   (meta >= 90%)   ok
latencia por caso: p50 12.9 ms, p95 27.3 ms
casos que fallan: EV-16
veredicto: umbrales NO cumplidos (exit code 1)
```

El sha256 de `data/deskpilot.db` fue idéntico antes y después
(`5ba63078969746c734194ed876ee05299be3818b10bec6678313e1ec5e0d10cd`). La corrida versionada en
`tests/eval/results.summary.json` da las mismas métricas con p50 13.8 ms y p95 31.5 ms (la latencia varía por corrida).

**Caso que falla: solo EV-16** ("My badge reader at the vault door shows error 77."). El esperado es `rechazo`,
pero el sistema responde `answered` citando KB-003 con score 0.525, por encima del umbral global 0.33. Es una
**limitación documentada**: el umbral de evidencia es global y no hay rerank. Se decidió dejarlo como caso fallido
visible (xfail estricto en e2e) en lugar de ajustar el umbral, que arriesga casos legítimos. Por eso el rechazo es
3/4 (75%) y el veredicto global es exit 1.

### Pruebas y calidad

`pytest --cov=src --cov-report=term`: **1479 passed, 2 skipped, 33 deselected (slow)**, cobertura total
**98.24%** (meta >= 80%). Los 2 omitidos: un test sin parámetros y el validador opcional `openapi-spec-validator`.
`pytest -m slow tests/e2e`: 30 passed, 2 xfailed (EV-16 y el umbral global), 10 deselected. `ruff check .`: sin
errores. `mypy src main.py`: sin errores en 53 archivos.

## Cómo verificarlo paso a paso

```bash
.venv\Scripts\python main.py index                      # índice real (si aún no existe)
certutil -hashfile data\deskpilot.db SHA256             # anotar el hash
.venv\Scripts\python main.py eval --out scratch\results.csv
echo %ERRORLEVEL%                                       # 1 por EV-16
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
  real (el ruido queda a 0.29-0.33 del top-1).
- **EV-20** ("inicios de sesión de mi cuenta a las 3 am que yo no hice") no escalaba: se añadió la detección de
  actividad de acceso no reconocida como `unauthorized_access`.
- **Patrones RN-03 ampliados**: caja caída, POS, "nadie puede cobrar", "alguien robó mi cuenta", "acceso
  indebido" (ES/EN, con y sin acentos), con negativos para evitar falsos positivos ("caja de ahorro").
- El modo HTTP avisa por stderr que crea tickets reales.

## Limitaciones

- EV-16: rechazo 3/4 por umbral global sin rerank; la meta de rechazo (100%) no se cumple.
- Los 30 casos son pocos y los redactó el equipo: miden regresión, no generalización.
- En modo HTTP el top 3 se reduce al artículo citado y no se verifica persistencia ni logs.
- La latencia es de la capa local (sin LLM ni red); no representa la de Copilot Studio.
- El comportamiento real del agente en Copilot Studio no está medido aquí: ver T32 en `docs/testing-procedure.md`.
