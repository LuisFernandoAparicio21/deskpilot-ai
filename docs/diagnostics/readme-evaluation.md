# Evaluación del README actual contra los 20 criterios

Fecha: 2026-11-22. Rama: `chore/readme-research`. Archivo evaluado: `README.md` (314 líneas). Criterios: sección "CRITERIOS VERIFICABLES" de `docs/research/readme-for-recruiters.md`. Solo lectura; no se editó nada fuera de `docs/diagnostics/`.

## Mediciones objetivas

| Verificación | Resultado |
| --- | --- |
| Tamaño | `wc -c README.md` = 19440 B = **18.98 KiB** (límite 500 KiB) |
| Encabezados | Sin `h1`; jerarquía `##` > `###` sin saltos (Quickstart tiene `###`, resto `##`). No existe `#` (título); el título está en el banner SVG |
| `<details>` | 0 ocurrencias (no se usan) |
| Mermaid | 2 bloques (líneas 69-85 y 205-214), sintaxis `flowchart` estándar; no se renderizó en GitHub (no verificado visualmente) |
| Links relativos | 30 resueltos con `os.path.exists`: **todos existen** (incluye banners, docs/, integrations/) |
| Links externos / imágenes / badges | `curl -I -L`: 19 URL con HTTP 200 (shields.io, readme-typing-svg, workflow CI, tags). `http://localhost:8000/health` es 000 esperado (local). El 200 de un badge no prueba que el CI esté en verde |
| Comandos del quickstart | `python main.py --help` lista `generate-data, load-db, index, serve, mcp, eval, export-openapi`: los 7 comandos del README existen. Flags no verificados uno a uno |
| Pytest (ejecutado) | `1993 passed, 2 skipped, 35 deselected, 1 failed` en 67 s. Fallo: `tests/unit/test_readme_visual.py::test_coverage_badge_matches_local_coverage_data_when_complete` (badge 98.02 vs `.coverage` local 98.12; causa no investigada, `.coverage` puede ser un dato local obsoleto) |
| Eval | `tests/eval/results.summary.json`: 30/30, p50 380.5, p95 801.6: **coinciden** con el README |
| `.env.example` | solo plantilla con comentarios; sin valores largos tipo secreto (`grep` de valores de 12+ caracteres: ninguno). `.env` existe local pero **no está versionado** (`git ls-files .env` vacío; `git check-ignore` lo confirma) |
| CI | `.github/workflows/ci.yml` con jobs `quality`, `eval-smoke`, `docker-build` |
| Capturas | `docs/screenshots/` solo contiene `.gitkeep`; el README no referencia PNG/GIF. Solo banners SVG |

## Evaluación por criterio

| # | Criterio (fuente, tipo) | Veredicto | Evidencia |
| --- | --- | --- | --- |
| 1 | Qué hace y por qué es útil en las primeras líneas ([GitHub Docs](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes); [Google](https://google.github.io/styleguide/docguide/READMEs.html), oficial) | **Cumple** | Líneas 13-15 (párrafo en inglés) y tabla "Qué es" (48-55); "Por qué este proyecto" 59-63 |
| 2 | Cómo empezar y funciona desde clon limpio ([Microsoft Learn](https://learn.microsoft.com/en-us/azure/devops/repos/git/create-a-readme?view=azure-devops), oficial) | **Parcial** | Requisitos y comandos en 150-188; los 7 comandos existen en `--help`. Pero línea 168 admite: "No se repitió en un clon limpio para este README"; no ejecuté el flujo (se prohibió lo pesado). Descarga de ~250 MB indicada |
| 3 | Ejemplo de uso con salida esperada ([Microsoft Learn](https://learn.microsoft.com/en-us/azure/devops/repos/git/create-a-readme?view=azure-devops); [Google](https://google.github.io/styleguide/docguide/READMEs.html), oficial) | **Parcial** | Líneas 130-140: salida real de `python main.py eval`. No hay ejemplo de una consulta al agente (p. ej. petición a `/` o tool MCP) con su respuesta; `curl.exe .../health` (187) sin salida esperada. Ejemplos reales están en `docs/user-flow.md`, solo enlazados |
| 4 | Captura o GIF en la intro, si hay UI ([Microsoft Learn](https://learn.microsoft.com/en-us/azure/devops/repos/git/create-a-readme?view=azure-devops), oficial; [Make a README](https://www.makeareadme.com/), guía) | **Parcial** | No hay captura ni GIF reales; hay banner SVG ilustrativo (3-7) y typing-svg (10). El proyecto es API/CLI sin UI propia, por lo que el criterio es condicional; "Demo: próximamente" (130) y PLACEHOLDER de video (146) |
| 5 | Pasos complejos en docs enlazadas ([Microsoft Learn](https://learn.microsoft.com/en-us/azure/devops/repos/git/create-a-readme?view=azure-devops), oficial) | **Parcial** | Docker, Fabric, MCP, arquitectura y manual enlazados a `docs/`. Pero 3 líneas del README son muy densas (10: 488 caracteres, 291: 631, 292: 446) con detalle de reranker/HO-29 que tiene doc propia |
| 6 | Enlaza a la documentación detallada ([Google](https://google.github.io/styleguide/docguide/READMEs.html), oficial) | **Cumple** | Enlaces a `docs/architecture.md`, `user-flow.md`, `business-case.md`, `job-fit.md`, `roadmap.md`, ADR, features; los 30 relativos resuelven |
| 7 | Estado del proyecto y contacto o mantenedor ([Google](https://google.github.io/styleguide/docguide/READMEs.html); [GitHub Docs](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes), oficial) | **Parcial** | Estado: sección "Estado de validación" (256-275) y "Siguientes pasos". Contacto/mantenedor: no hay nombre, correo ni enlace de perfil en el README (grep de `mailto`/linkedin: ninguno; solo aparece el usuario en URLs del repo) |
| 8 | Licencia y cómo contribuir o reportar ([Microsoft Learn](https://learn.microsoft.com/en-us/azure/devops/repos/git/create-a-readme?view=azure-devops), oficial) | **Cumple** | Línea 301: MIT con `LICENSE` y `CONTRIBUTING.md` (ambos existen); plantillas de issues/PR mencionadas (201). No hay una línea explícita de "cómo reportar un bug" en el README |
| 9 | Sin información desactualizada ([Google](https://google.github.io/styleguide/docguide/READMEs.html), oficial) | **No cumple** | Badge y tabla dicen 1946 passed (35, 116); `pytest` hoy: 1993 passed (+1 fallo). Resumen en inglés (312): "1753 tests". Cobertura 98.02% vs 98.12% en `.coverage` local y test de coherencia rojo. Cifras de eval sí coinciden. Además restos de una tabla antigua duplicada (243-252) |
| 10 | < 500 KiB y encabezados jerárquicos ([GitHub Docs](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes), oficial) | **Parcial** | Tamaño: 18.98 KiB, cumple. Jerarquía: no hay `#` de título, y "Estructura del repo" y "Arquitectura" (190, 203) quedan bajo Quickstart sin separador; hay un `---` doble (285-287). El índice automático funciona con `##` |
| 11 | `<details>` con `<summary>` si se usa ([GitHub Docs](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/organizing-information-with-collapsed-sections), oficial) | **Cumple (no aplica)** | 0 `<details>`; el criterio es condicional |
| 12 | Diagramas con sintaxis que GitHub renderiza ([GitHub Docs](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/creating-diagrams), oficial) | **Cumple** | 2 bloques ```` ```mermaid ```` con `flowchart`; render no verificado en GitHub (no hay navegador usado) |
| 13 | Roadmap, estado o trabajo pendiente ([Make a README](https://www.makeareadme.com/), guía) | **Cumple** | "Siguientes pasos" (279-283), enlace a `docs/roadmap.md` (275), "Pendiente manual" (258-262) |
| 14 | Limitaciones principales, concisas ([idratherbewriting](https://idratherbewriting.com/2010/12/16/known-limitations/), opinión) | **Parcial** | Existe "Límites conocidos" (289-295) y los honestos "pendiente de validar" arriba. Pero está casi al final, no al inicio, y los 2 primeros puntos son largos (631 y 446 caracteres) con detalle de implementación |
| 15 | Demo/despliegue o evidencia reproducible ([kazkozdev](https://dev.to/kazkozdev/i-studied-how-github-readmes-are-actually-evaluated-here-are-the-5-things-that-matter-2epd); [Code Labs Academy](https://codelabsacademy.com/en/blog/github-portfolio-junior-developers-what-to-include-remove), opinión) | **Parcial** | Sin demo desplegada ni video ("próximamente", PLACEHOLDER 146). Sí hay evidencia reproducible: salida de `eval` (132-140), JSON versionado y CI |
| 16 | `.env.example` y ningún secreto en el repo ([Code Labs Academy](https://codelabsacademy.com/en/blog/github-portfolio-junior-developers-what-to-include-remove), opinión) | **Cumple** | `.env.example` presente, sin valores sensibles; `.env` no versionado. El README lo indica (161). Historial de git no auditado |
| 17 | Decisiones y trade-offs ([Code Labs Academy](https://codelabsacademy.com/en/blog/github-portfolio-junior-developers-what-to-include-remove); [JSGuruJobs](https://dev.to/jsgurujobs/portfolio-code-that-gets-you-hired-what-recruiters-actually-see-in-your-github-h9n), opinión) | **Parcial** | Hay decisiones enlazadas (ADR-0001, ADR-0009, 228) y trade-off del reranker (292). No hay sección "qué aprendí" ni resumen de decisiones en el README; `docs/learning-log.md` no está enlazado |
| 18 | Tests y CI y comandos para ejecutarlos ([Microsoft Learn](https://learn.microsoft.com/en-us/azure/devops/repos/git/create-a-readme?view=azure-devops), oficial; [kazkozdev](https://dev.to/kazkozdev/i-studied-how-github-readmes-are-actually-evaluated-here-are-the-5-things-that-matter-2epd), opinión) | **Parcial** | CI y tests visibles (badges 22, 35; 116, 124; ci.yml con 3 jobs). Comando de tests explícito: el quickstart no incluye `pytest`; solo aparece como `pytest --cov=src` en la columna Fuente (116) |
| 19 | Badges significativos ([Wei](https://dev.to/iris1031/github-readme-best-practices-how-to-write-a-readme-that-gets-stars-2gb2), opinión) | **Parcial** | Significativos: CI, release, licencia, estado Copilot/Fabric (pendiente en gris). Estáticos y desactualizables: `pytest-1946 tests` (desfasado) y `coverage-98.02%` (a mano, test rojo). Hay 8 badges de stack más 5 de estado: ruido decorativo |
| 20 | Escaneable: encabezados, tablas, listas cortas ([HR Dive / Ladders](https://www.hrdive.com/news/eye-tracking-study-shows-recruiters-look-at-resumes-for-7-seconds/541582/), estudio sobre CV, extrapolado) | **Parcial** | Muchas tablas y encabezados claros. Pero 314 líneas, 13 badges + typing-svg antes del primer contenido, un fragmento de tabla roto (243-252) y secciones duplicadas "Demo"/"Video" |

## Resumen

Conteo (20 criterios): **cumple 7** (1, 6, 8, 11 [no aplica, condicional], 12, 13, 16) · **parcial 12** (2, 3, 4, 5, 7, 10, 14, 15, 17, 18, 19, 20) · **no cumple 1** (9).

Los 5 incumplimientos más relevantes:

1. **Criterio 9 (no cumple, oficial Google):** cifras de tests desactualizadas (README 1946 y 1753 vs 1993 medidos) y fallo del test de coherencia de cobertura (98.02 vs 98.12).
2. **Criterio 2 (parcial, oficial Microsoft):** quickstart no verificado desde clon limpio; el propio README lo admite (168).
3. **Criterio 4 (parcial, oficial Microsoft / guía Make a README):** sin captura o GIF reales; `docs/screenshots/` vacío; demo y video en PLACEHOLDER.
4. **Criterio 7 (parcial, oficial Google/GitHub Docs):** estado presente pero sin contacto ni mantenedor.
5. **Criterio 3 (parcial, oficial Microsoft/Google):** el único ejemplo con salida es `eval`; falta una consulta de ejemplo al agente con su respuesta.

(Criterios 14, 17 y 18 también parciales, pero de fuente opinión.)

## Observaciones sin criterio investigado (no cuentan)

- Líneas 243-252: fragmento huérfano de una tabla anterior (`--- | --- | --- |` sin cabecera) y párrafo "La tabla completa..." repetido (241, 252): error de maquetación visible. No hay criterio específico de corrección de Markdown; solo incide en el 20.
- Secciones "Demo" y "Video" con el mismo icono y `---` duplicado (285, 287).
- Mezcla de idiomas (párrafo inicial y resumen en inglés, cuerpo en español); la investigación declara que no hay criterio sobre idioma (P7).
- Longitud total (314 líneas): no hay criterio sobre longitud óptima (P6); solo el límite de 500 KiB.
- Que el título principal esté solo en un SVG (sin `#`) afecta accesibilidad/SEO, pero no hay criterio investigado.
- El estado Hecho/Pendiente se repite en tres tablas (habilidades, "Estado de validación" y bloque VALIDATION).
- Cuenta de usuario en el remoto (`LuisFernandoAparicio21`) y no verificada contra otro perfil; no hay criterio.

## No verificado

Render real en GitHub de mermaid y `<picture>`; historial de git en busca de secretos; flujo del quickstart en clon limpio; docker build; causa del test rojo de cobertura.
