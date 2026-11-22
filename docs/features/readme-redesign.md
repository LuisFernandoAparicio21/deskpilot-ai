# Rediseño del README (PL-10)

Rama `chore/readme-redesign`. Absorbe PL-9 (accesibilidad en inglés). Insumos: `docs/research/readme-for-recruiters.md` (criterios C1 a C20), `docs/diagnostics/readme-evaluation.md` y `docs/research/readme-outline.md` (estructura y trazabilidad).

## Qué cambió y por qué

- `README.md` pasa a ser un único archivo en inglés (decisión del usuario, ver abajo). Se reordenó según la investigación: qué es, por qué, estado y límites antes del quickstart (C14), resultados con fuente por cifra (C9, C15), ejemplo real de uso (C3), diagramas (C12), decisiones (C17), habilidades en una tabla con columna Estado (C20).
- 6 badges con significado (CI, release, licencia, cobertura, y dos de plataforma Microsoft generados) en lugar de 13 más el typing-svg (C19, C20).
- Los bloques generados `RESULTS`, `VALIDATION` y `MSBADGES` se conservan y salen en inglés de `scripts.update_readme_results`; `--check` devuelve 0.
- La nota de datos sintéticos y la de "Banco Altiplano" van en inglés con el español textual debajo en `<sub>`. Sección final "Resumen en español" para reclutadores en México.
- Una línea explica que los nombres de herramientas y las respuestas del agente siguen en español (agente bilingüe) y otra que la mayoría de `docs/` está en español.

## Criterios investigados cumplidos, con evidencia

| Criterio | Evidencia |
| --- | --- |
| C1 qué hace en el primer vistazo | párrafo de introducción y tabla "What it is" |
| C14 límites cerca del inicio | sección "Status and limits" antes del Quickstart, 4 viñetas |
| C9, C15 cifras con fuente | tabla "Results in numbers" con columna Source; números en `docs/research/readme-outline.md`, sección 6 |
| C19 badges significativos | 6 imágenes remotas, sin badges de stack |
| C5 pasos complejos fuera | Docker, Fabric y MCP solo enlazados |
| C7, C8 mantenedor y cómo reportar | sección "Maintainer and contributing" con handle e issues |

## Decisiones del usuario

- Idioma: README único en inglés, notas bilingües, resumen en español al final, sin `README.es.md`. No tiene fuente de investigación (P7 no halló criterios): es del usuario.
- Longitud (decisión 2): provisional, la del borrador (298 líneas). Contacto (decisión 3): provisional, solo handle de GitHub e issues. El usuario no respondió.

## Cifras

`.venv\Scripts\python -m pytest --cov=src -q` (sin slow, 2026-11-22): 1982 passed, 17 failed, 3 skipped, 35 deselected; cobertura 98.12%. El README publica 1999 ejecutadas. Las 17 fallas son contratos de test que fijan el README anterior o el texto en español de los scripts; no se editó `tests/`. Pasan al qa-tester:

- `test_docs.py::test_readme_eval_figures_match_summary` (busca el texto en español) y `test_mermaid_blocks_are_balanced[docs/diagnostics/readme-evaluation.md]` (ya fallaba antes; el documento cita la apertura de un bloque mermaid en prosa).
- `test_readme_visual.py::test_unvalidated_platform_badges_say_pending...` (2, Fabric y Copilot Studio): esperan "pendiente" y los badges están en inglés.
- `test_scripts_update_readme_results.py` (7) y `test_validation_status.py` (6): esperan las etiquetas en español del script; el script se pasó al inglés en `bda3acf`.
- Además, `docs/testing-procedure.md` sigue con 1946 pasadas y 98.02%; hay que alinearlo.

## No verificado

- Quickstart en un clon limpio: no se repitió. El README lo declara.
- Render real de mermaid en GitHub: no se verificó; el orquestador revisará la vista previa del PR.
- "~0.57 GB", "HO-29 39/40" y las cifras del caso de negocio se copian de documentos previos sin re-medir.
