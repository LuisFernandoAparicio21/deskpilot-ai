# Estructura propuesta del README

Fecha: 2026-11-22. Rama: `chore/readme-research`. Insumos: `docs/research/readme-for-recruiters.md` (criterios C1 a C20, fuentes citadas allí), `docs/diagnostics/readme-evaluation.md` (evaluación del README actual, "Eval") y el `README.md` actual solo como material de datos. Borrador completo: `scratch/README.draft.md` (ignorado por git). `README.md` no se editó.

Regla: cada decisión se traza a un criterio investigado. Lo que la investigación declara sin fuente (idioma, estructura narrativa, longitud óptima, tiempo de revisión) se deja abierto.

## 1. Orden y secciones

El orden sigue la lista de GitHub Docs (qué hace, por qué es útil, cómo empezar, ayuda, mantenedor; C1, C7) y Google (estado, ejemplos, enlace a docs; C3, C6, C7). Las limitaciones van antes del quickstart porque la única fuente directa las pide al inicio y en pocas líneas (C14). El orden fino entre secciones de evidencia no tiene fuente numérica y es una decisión de diseño, no un hallazgo.

| # | Sección (H2) | Criterio | Fuente (tipo) | Largo objetivo | Incumplimiento de Eval que corrige |
| --- | --- | --- | --- | --- | --- |
| 0 | Banner + `# DeskPilot AI` + bloque English (3 líneas) + nota de datos sintéticos + 6 badges | C1, C10, C19 | GitHub Docs, Google (oficial); Wei (opinión) | ~25 líneas | C10: faltaba `#` de título; C19/C20: 13 badges + typing-svg antes del primer contenido (ahora 4 de estado + 2 de plataforma, sin stack ni pytest estático) |
| 1 | Qué es | C1 | GitHub Docs, Google (oficial) | 6 líneas (tabla) | Ninguno (ya cumplía); se conserva |
| 2 | Por qué este proyecto | C1, C17 | GitHub Docs (oficial); Code Labs Academy (opinión) | 4 líneas | Ninguno; se conserva (contrato de test) |
| 3 | Estado y límites | C7, C13, C14, C9 | Google, GitHub Docs (oficial); Make a README (guía); idratherbewriting (opinión) | ~25 líneas | C14: límites estaban casi al final y con párrafos de 400 a 600 caracteres (ahora 4 viñetas cortas, detalle enlazado); C7 (estado); C9 (VALIDATION generado desde JSON) |
| 4 | Resultados en números | C9, C15, C18 | Google (oficial); kazkozdev, Code Labs Academy (opinión) | ~35 líneas | C9: cifras de tests desactualizadas (1946 y 1753 vs 1996 medidos); C15: evidencia reproducible con fuente por cifra |
| 5 | Quickstart (Setup, Comandos, pruebas) | C2, C5, C18 | Microsoft Learn (oficial) | ~40 líneas | C2: comandos verificados con `--help`, no se probó en clon limpio (se declara, no se oculta); C5: Docker/Fabric/MCP solo enlazados; C18: comando de tests explícito |
| 6 | Ejemplo de uso | C3, C15 | Microsoft Learn, Google (oficial); kazkozdev (opinión) | ~40 líneas (2 `<details>`) | C3: faltaba una consulta al agente con su respuesta; se usa salida real de `docs/user-flow.md` |
| 7 | Video | C15 | kazkozdev, Code Labs Academy (opinión) | 3 líneas | Se mantiene PLACEHOLDER (Fase C del usuario); contrato de test lo exige |
| 8 | Cómo funciona | C12, C11, C20 | GitHub Docs (oficial); Ladders (estudio extrapolado) | ~35 líneas | C12: se conservan 2 diagramas mermaid; el de decisión pasa a `<details>` para no saturar (C11) |
| 9 | Decisiones de diseño | C17 | Code Labs Academy, JSGuruJobs (opinión) | ~12 líneas | C17: antes no había resumen de decisiones ni enlace al learning log |
| 10 | Habilidades demostradas | C6, C20 | Google (oficial); Ladders (extrapolado) | ~20 líneas | C20: una sola tabla con columna Estado (antes tres tablas repetían Hecho/Pendiente, más un fragmento de tabla roto de 243-252) |
| 11 | Siguientes pasos | C13 | Make a README (guía) | 6 líneas | Ninguno |
| 12 | Documentación (`<details>`) | C5, C6, C11 | Microsoft Learn, Google, GitHub Docs (oficial) | ~20 líneas | C5/C6: estructura del repo plegada y enlaces a `docs/` |
| 13 | Mantenedor y contribución | C7, C8 | Google, GitHub Docs, Microsoft Learn (oficial) | 3 líneas | C7: mantenedor/contacto ausente; C8: faltaba "cómo reportar" (ahora enlace a issues) |
| 14 | Licencia | C8 | Microsoft Learn (oficial) | 1 línea | Ninguno; el ancla `#licencia` la exige un test |
| 15 | English summary | C1 | GitHub Docs (oficial) | 8 líneas | C9: "1753 tests" desactualizado; contrato de test lo exige |

Largo total del borrador: 300 líneas, 17.8 KiB (límite oficial 500 KiB, C10). No hay fuente con una longitud óptima: la reducción de líneas por sección se justifica solo con C5 (pasos complejos fuera) y C20 (escaneable), y el borrador no es más corto que el actual en conjunto; se reordena y se quitan duplicados.

## 2. Qué se quitó y por qué

- Badges de stack (8) y pytest estático: C19 pide badges significativos, no decorativos (opinión, Wei); el de pytest era el desactualizado (C9).
- readme-typing-svg: decorativo; sin criterio que lo respalde (C19, C20).
- Secciones duplicadas "Demo"/"Video" y las dos tablas Hecho/Pendiente: C20.
- Fragmento huérfano de tabla (líneas 243-252) y `---` dobles: solo afectan C20 (no hay criterio de corrección Markdown).
- Párrafos de 440 a 630 caracteres sobre el reranker: C5 y C14 (el detalle ya está en ADR-0009 y `docs/research/rejection-experiment.md`).

## 3. Capturas, GIF y video (C4, C15)

El proyecto es API/CLI sin UI propia, así que C4 (condicional "si hay UI") no obliga. Si se quiere un visual real, solo de ejecución real:

- Captura de terminal de `python main.py eval` y de la consulta `curl` a `/buscar_solucion` con el servidor local (los mismos comandos de la sección 6), tomada de la corrida real, sin retocar.
- GIF: grabación de esa misma sesión (por ejemplo con una herramienta de grabación de terminal); no se genera ninguno en el borrador.
- Pendiente del usuario (Fase C): chat en Copilot Studio, reporte de Power BI y video de la demo. Mientras tanto el README mantiene el PLACEHOLDER y los badges en gris.

`docs/screenshots/` está vacío; no se inventó ninguna captura.

## 4. Decisiones abiertas

### DECISIÓN DEL USUARIO, sin fuente: idioma del README (RESUELTA, ver sección 8)

La investigación (P7) declara que no hay criterio sobre idioma de un README de portafolio. El borrador mantiene el estado actual (cuerpo en español, bloque English de 3 líneas, English summary al final) solo como línea base provisional, no como recomendación.

| Opción | Consecuencias |
| --- | --- |
| A. Español con resumen en inglés (actual) | Cero cambios de tests ni de docs. Cuerpo no legible para quien solo lea inglés; mezcla de idiomas ya señalada en Eval. |
| B. Inglés completo | Mayor alcance según Adejumo et al. (preprint, solo resumen leído) y Devlane, pero ninguna fuente habla del README de un candidato. Cambia los contratos de test (encabezados "Por qué este proyecto", "Habilidades demostradas", nota en español) y exige traducir el README sin tocar docs/ en español. |
| C. Dos archivos, `README.md` y `README.es.md` | Cada uno coherente en su idioma; duplica mantenimiento y riesgo de cifras desfasadas (C9). Exige que los scripts y tests apunten a uno u otro. |

### DECISIÓN DEL USUARIO, sin fuente: longitud objetivo (PROVISIONAL: el usuario no respondió; se usó la longitud del borrador)

No hay fuente con longitud óptima (P6); las fuentes divergen (Make a README: más largo es mejor; Microsoft: lo esencial y enlazar). El borrador queda en 300 líneas / 17.8 KiB. Opciones: (a) quedarse así; (b) recortar a ~150 líneas moviendo Decisiones, Habilidades y Documentación a `docs/` (más escaneable por C20 y C5, pero pierde evidencia visible en el primer vistazo); (c) mantener 300 y plegar más con `<details>`. Ninguna tiene respaldo numérico.

### Contacto del mantenedor (C7, oficial) (PROVISIONAL: el usuario no respondió; solo handle de GitHub e issues)

C7 exige contacto o mantenedor. El borrador solo pone el handle de GitHub (`@LuisFernandoAparicio21`, el que ya está en las URLs del repo) y los issues. Nombre completo, correo o LinkedIn no se inventan: el usuario decide si los publica.

## 5. Contratos de test que la estructura propuesta contradice (no se editaron)

Verificado ejecutando las funciones de test contra el borrador (script en el scratchpad, `README.md` intacto). Pasan 12 de 16 comprobaciones. Fallan:

| Test | Por qué falla | Qué cambiar si se adopta la estructura |
| --- | --- | --- |
| `test_readme_visual.py::test_all_remote_images_are_https_from_allowed_hosts` | Exige `>= 12` imágenes remotas; el borrador tiene 6 (C19) | Bajar el umbral a 6 (o quitarlo: es un detector de "al menos hay badges") |
| `test_readme_visual.py::test_static_shields_badges_have_label_message_color` | Exige `>= 8` badges `/badge/`; hay 3 | Bajar el umbral a 3 |
| `test_readme_visual.py::test_coverage_badge_matches_last_declared_measurement` | Badge 98.12% vs `docs/testing-procedure.md` (98.02%) | No es de estructura: actualizar `docs/testing-procedure.md` a 98.12% |
| `test_readme_visual.py::test_pytest_totals_match_testing_procedure` | README 1996/3/35 vs procedimiento 1946/2/35, y exige badge `pytest-N%20tests` (se quitó, C9/C19) | Actualizar `docs/testing-procedure.md` línea 47 y quitar la comprobación del badge |

Contratos que se respetan sin cambios: nota sintética en bold dentro de las primeras 25 líneas; bloque English de 3 líneas antes de "Por qué"; H2 "Por qué este proyecto", "Habilidades demostradas", "English summary" (prefijo emoji opcional), "Video" con PLACEHOLDER y sin `http`; anclas `setup`, `licencia`, `por-qué-este-proyecto`; los 7 subcomandos citados como `python main.py <cmd>` con flags reales; fila `Casos de evaluación` y `Latencia por caso` tras `RESULTS:END`; "Casos fallidos: ninguno."; `{passed}/{total} cases pass` en el resumen inglés; badges de Fabric y Copilot Studio en gris con "pendiente"; fila `Cobertura de src/ | NN%`; imágenes del banner y `<picture>`; dos bloques mermaid. Notas: el test de nota exige la forma `**texto.**`; la sección `English summary` duplica el bloque English de arriba por contrato (se podría fusionar si se cambian los tests).

## 6. Cifras: número, fuente, comando

Todas verificadas el 2026-11-22. Pytest se ejecutó una sola vez, sin `slow`, sin Docker.

| Número | Fuente | Comando |
| --- | --- | --- |
| 30/30, top-3 14/14, rechazo 4/4, clasificación 5/5, seguridad 3/3 | `tests/eval/results.summary.json` | `python main.py eval` (el JSON versionado se leyó, no se regeneró) |
| p50 380.5 ms, p95 801.6 ms | `tests/eval/results.summary.json` | idem |
| 1996 passed, 3 skipped, 35 deselected | salida de pytest | `.venv\Scripts\python -m pytest --cov=src -q` (92 s; 1 failed: ver nota) |
| Cobertura 98.12% (umbral 80%) | salida de pytest | idem (`Total coverage: 98.12%`) |
| 39.92%, 51.24%, 1.90 veces, 79.50% contra 60.57%, 35.6 / 53.4 / 71.2 h | `docs/business-case.md` (cada cifra cita su consulta `01`, `05`, `07`, `08`) | `python main.py load-db --run-sql` (no se re-ejecutó; se copian del documento) |
| 7 comandos | `python main.py --help` | verificado por `test_docs.py` |
| 39/40 held-out, 0.57 GB, 0.5 a 1 s | README actual y ADR-0009 | no re-medido |
| Pendientes (Fabric, Copilot Studio, Power BI, video) | `docs/validation-status.json` | `python -m scripts.update_readme_results --check` |
| 9 ADR | `docs/adr/` | `ls docs/adr` |

Notas sobre cifras: (1) el "1 failed" proviene de `test_docs.py::test_mermaid_blocks_are_balanced[docs/diagnostics/readme-evaluation.md]`: ese archivo cita la apertura de un bloque mermaid en prosa (entre comillas invertidas triples) y los tests de docs lo leen como bloque sin cerrar; corregirlo en el documento de diagnóstico (no se tocó). El README declara 1996 passed tal como se midió. (2) "3 skipped" frente a "2" del texto anterior: con `--cov` el test de coherencia con `.coverage` se omite ("no .coverage data file"); depende de cómo se invoque. (3) "~0.57 GB" y "HO-29 39/40" se arrastran del README actual sin re-medir; la validación en clon limpio sigue sin hacerse y el borrador lo declara.

## 7. Validación del borrador

Script en el scratchpad (no se commitea): tamaño 17.78 KiB; 4 `<details>` abiertos y cerrados, cada uno con `<summary>`; fences balanceados; 2 bloques mermaid con corchetes balanceados (sintaxis idéntica a la ya usada en el README y en `docs/user-flow.md`; no se renderizó en GitHub, no verificado); 0 enlaces o imágenes relativas rotas; marcadores RESULTS, VALIDATION y MSBADGES presentes con su contenido actual; los 3 bloques de texto exacto presentes sin cambios.

## 8. Decisión del usuario sobre el idioma (registrada el 2026-11-22)

Decisión: un solo `README.md` en inglés; no se crea `README.es.md`. Las dos notas de datos sintéticos van en inglés con el original en español textual debajo en `<sub>`. El README termina con la sección "Resumen en español" (4 líneas) para reclutadores en México. Los nombres de herramientas y las respuestas del agente siguen en español en los ejemplos (el agente es bilingüe), explicado en una línea; los documentos de `docs/` siguen en español y el README lo avisa.

Trazabilidad: esta decisión no tiene fuente. Es del usuario. La investigación (P7) no encontró criterios sobre idioma de un README de portafolio, así que no se cita ninguno. Equivale a la opción B con los matices anteriores. Decisiones 2 (longitud) y 3 (contacto): provisionales, sin respuesta del usuario.

Cambios respecto del borrador: se tradujo todo el texto; se quitó la etiqueta "English:" del párrafo de introducción (texto conservado); "English summary" se reemplazó por "Resumen en español"; el encabezado de licencia pasa a "License". Los bloques `RESULTS`, `VALIDATION` y `MSBADGES` ya se generan en inglés por `scripts.update_readme_results` (`--check` devuelve 0).

Cifras re-medidas con `.venv\Scripts\python -m pytest --cov=src -q` (sin slow, 105 s): 1982 passed, 17 failed, 3 skipped, 35 deselected; cobertura 98.12%. El README publica "1999 run" (passed + failed). Las 17 fallas son contratos que fijan el README anterior o el texto en español de los scripts (nueva fila de la tabla de la sección 6: número 1999/3/35, fuente salida de pytest, comando anterior). Las lista el qa-tester: `test_docs.py` (cifras del README y mermaid de `readme-evaluation.md`), `test_readme_visual.py` (badges de plataforma en inglés), `test_scripts_update_readme_results.py` (7) y `test_validation_status.py` (6).
