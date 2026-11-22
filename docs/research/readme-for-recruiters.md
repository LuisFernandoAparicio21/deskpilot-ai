# README de portafolio para reclutadores: investigación

Fecha de consulta de todas las fuentes: 2026-11-22. Rama: `chore/readme-research`. Alcance: 8 preguntas, máx. 3-4 fuentes por pregunta. Tipos: **oficial**, **guía reconocida**, **estudio/encuesta**, **opinión de autor**. Lo que no tiene fuente no entra; las lagunas se declaran. Cuando una recomendación es solo opinión se marca **[OPINIÓN]**.

Hallazgo transversal: casi no hay estudios empíricos sobre cómo revisan los reclutadores un repositorio. Lo oficial define qué debe tener un README; lo que dice qué valoran los reclutadores es, casi todo, opinión de autor.

## 1. Qué debe contener un README y qué no

- GitHub Docs: qué hace el proyecto, por qué es útil, cómo empezar, dónde obtener ayuda, quién lo mantiene. Se trunca sobre 500 KiB. Genera tabla de contenidos desde los encabezados. [oficial] ([GitHub Docs, About READMEs](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes))
- Microsoft Learn: introducción breve con captura o GIF si hay UI, dependencias declaradas, pasos mínimos para arrancar, pasos complejos fuera del README y enlazados, comprobar las instrucciones desde un clon limpio, cómo contribuir y licencia. [oficial] ([Microsoft Learn](https://learn.microsoft.com/en-us/azure/devops/repos/git/create-a-readme?view=azure-devops))
- Google: qué contiene y para qué sirve, contacto, estado, ejemplos de uso, enlace a docs; evitar información desactualizada. [oficial] ([Google style guide](https://google.github.io/styleguide/docguide/READMEs.html))
- Make a README: nombre, descripción, badges, visuales, instalación, uso, soporte, roadmap, contribución, licencia, estado del proyecto. [guía reconocida comunitaria] ([makeareadme.com](https://www.makeareadme.com/))

Qué no: las fuentes oficiales no listan "qué evitar" salvo información desactualizada (Google) y pasos densos dentro del README (Microsoft). No hay fuente oficial que prohíba secciones concretas.

**Divergencia (se reportan ambas posturas):** Make a README afirma "too long is better than too short"; Microsoft pide mantenerse en lo esencial y mover lo complejo a otra página.

## 2. Cómo revisan reclutadores y hiring managers

- Eye-tracking de Ladders (2018): 7.4 s de media en el primer filtro de un **currículo** (6 s en 2012); rinden mejor layouts simples con títulos claros y peor los saturados. [estudio, sobre CV, no sobre repos; muestra no indicada en el artículo] ([HR Dive](https://www.hrdive.com/news/eye-tracking-study-shows-recruiters-look-at-resumes-for-7-seconds/541582/))
- Crítica a esa cifra: no es generalizable; el tiempo depende del puesto y del reclutador. [opinión de autor, Gygax, 2020-10-20] ([ERE](https://www.ere.net/articles/is-the-6-second-resume-scan-a-myth))
- Underdog.io (2026-06-19): escaneo inicial de ~30 s; miran README, claridad de commits, alcance y que el trabajo sea funcional y demostrable. [opinión, blog de bolsa de empleo; sin datos propios] ([Underdog.io](https://underdog.io/blog/what-hiring-managers-look-for-on-github))
- kazkozdev (2026-04-04): el README funciona como "superficie de filtrado"; pesan tests/CI, demos y originalidad frente a clones de tutorial. [opinión; sin datos cuantitativos] ([dev.to](https://dev.to/kazkozdev/i-studied-how-github-readmes-are-actually-evaluated-here-are-the-5-things-that-matter-2epd))

**Laguna:** no encontré una encuesta con porcentajes sobre cuántos reclutadores abren un repo, cuánto tiempo le dedican ni qué buscan en perfiles trainee. La búsqueda dirigida no devolvió ninguna. Las cifras de 7.4 s y 30 s no son medidas sobre repositorios; las dos fuentes difieren y no elijo una.

## 3. Cómo contar un proyecto de portafolio

- Estructura de case study (diseño UX): antecedentes, problema, usuarios, ideación, solución y decisiones, siguientes pasos y aprendizajes. [guía reconocida, de UX, no de desarrollo] ([CareerFoundry](https://careerfoundry.com/en/blog/ux-design/ux-case-study/))
- Para juniors: problema en una frase, demo, sección "what I learned" con decisiones y trade-offs, instrucciones de arranque, tests. [opinión, bootcamp] ([Code Labs Academy](https://codelabsacademy.com/en/blog/github-portfolio-junior-developers-what-to-include-remove))
- STAR (Situation, Task, Action, Result) es un método de **respuesta en entrevista**; la fuente no lo aplica a READMEs. [guía, entrevistas] ([Salesforce, 2025-08-13](https://www.salesforce.com/blog/use-the-star-method-to-ace-your-next-job-interview/))
- JSGuruJobs: lo que penalizan es la falta de decisiones visibles, no la falta de profundidad técnica. [opinión, 2026-02-06] ([dev.to](https://dev.to/jsgurujobs/portfolio-code-that-gets-you-hired-what-recruiters-actually-see-in-your-github-h9n))

**Laguna:** no hay fuente sólida (oficial o estudio) que recomiende una estructura narrativa concreta para un README de repositorio. Lo que existe es de UX o de entrevistas. Aplicarlas a un README sería una extrapolación, no una recomendación sustentada.

## 4. Qué resta puntos

- Demo roto o código que no corre; pasos de instalación poco claros; secretos subidos; sin documentación de propósito; commits tipo "final final"; binarios pesados. [opinión, bootcamp] ([Code Labs Academy](https://codelabsacademy.com/en/blog/github-portfolio-junior-developers-what-to-include-remove))
- README que solo lista tecnologías sin contexto; commits sin intención ("Fix", "asdfasdf"). [opinión, experiencia personal, no encuesta] ([JSGuruJobs](https://dev.to/jsgurujobs/portfolio-code-that-gets-you-hired-what-recruiters-actually-see-in-your-github-h9n))
- Vaguedad, falta de enlace de despliegue, ausencia de tests/CI. [opinión] ([kazkozdev](https://dev.to/kazkozdev/i-studied-how-github-readmes-are-actually-evaluated-here-are-the-5-things-that-matter-2epd))
- Información desactualizada. [oficial] ([Google](https://google.github.io/styleguide/docguide/READMEs.html))

No hay fuente empírica; salvo la de Google, todo es opinión.

## 5. Limitaciones y trabajo pendiente

- Documentar limitaciones al inicio, en pocas líneas, sin listar cada bug; esto genera confianza. [opinión de autor, redactor técnico, 2010] ([idratherbewriting](https://idratherbewriting.com/2010/12/16/known-limitations/))
- Make a README sugiere secciones "Roadmap" y "Project status" (indicar si el desarrollo se ralentizó). [guía reconocida] ([makeareadme.com](https://www.makeareadme.com/))
- bia-bob incluye descargos sobre verificar el código generado y los datos que se envían al proveedor LLM. [ejemplo en lista comunitaria] ([bia-bob](https://github.com/haesleinhuepf/bia-bob))
- Code Labs Academy y kazkozdev piden "what I learned" y presentar el proyecto como punto de partida. [opinión]

**Laguna:** no hay fuente oficial ni estudio sobre limitaciones en READMEs de portafolio. Solo una fuente directa (2010) y es opinión; el resto es indirecto.

## 6. Largo, visuales y organización

- GitHub: tabla de contenidos automática desde encabezados; límite 500 KiB. [oficial] ([About READMEs](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes))
- `<details>`/`<summary>` para secciones colapsadas, con `open` para abrirlas por defecto. [oficial] ([GitHub Docs](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/organizing-information-with-collapsed-sections))
- Mermaid y otros diagramas se renderizan en Markdown. [oficial] ([GitHub Docs](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/creating-diagrams))
- Microsoft: captura o GIF en la introducción; enlazar docs externas para lo complejo. [oficial]
- Make a README recomienda visuales (capturas, GIF, vídeo) y badges. [guía reconocida]
- Wei: badges solo si son significativos, características en tabla, quick start corto. [opinión; orientado a estrellas, no a reclutadores] ([dev.to, 2026-03-29](https://dev.to/iris1031/github-readme-best-practices-how-to-write-a-readme-that-gets-stars-2gb2))
- Ladders: la jerarquía visual simple ayuda al escaneo, pero es de currículos. [estudio, extrapolado]

**Laguna:** ninguna fuente fija una longitud numérica óptima. El único límite objetivo es 500 KiB. La divergencia largo/corto está en la pregunta 1.

## 7. Idioma (español, inglés o bilingüe)

- CodersLink (2026-04-14): 47.4% de profesionales tech en México con inglés avanzado; el inglés avanzado se asocia a mayor salario; la comunicación es crítica para multinacionales. [informe interno de empresa de reclutamiento, no verificable] ([CodersLink](https://coderslink.com/employers/blog/english-fluency-among-mexicos-tech-professionals))
- Devlane (2025-07-16): la escritura técnica en inglés mejora la credibilidad. [opinión de empresa] ([Devlane](https://www.devlane.com/blog/mastering-english-for-a-career-in-it-a-guide-for-latam-software-developers))
- Adejumo et al. (arXiv, 2026-01-05): los proyectos OSS suelen carecer de README en idiomas distintos al inglés; es una barrera. [preprint; solo se leyó el resumen] ([arXiv](https://arxiv.org/pdf/2508.02497v2))

**Laguna importante:** no encontré ninguna fuente que diga qué idioma debe tener el README de un portafolio para vacantes en multinacionales, ni si un README bilingüe se valora más o menos. Los tres hallazgos hablan del inglés en el mercado laboral o de la accesibilidad, no del README de un candidato. No se puede concluir nada sobre español vs. inglés vs. bilingüe.

## 8. Ejemplos reales de README de IA/agentes

Fuente de selección: lista comunitaria [awesome-readme](https://github.com/matiassingers/awesome-readme) (guía reconocida; ~21.8k estrellas; consultada 2026-11-22). Solo encontré 2 proyectos de LLM/agentes allí; el RAG puro no aparece como tal. Los demás candidatos (Dify, Ollama, RAGFlow) los citan blogs de comparación como proyectos populares, no como READMEs ejemplares, por lo que no los incluyo.

1. **Clean-Coder-AI** ([link](https://github.com/Grigorij-Dudnik/Clean-Coder-AI), consultado 2026-11-22): titular directo; GIF animado; diagrama de arquitectura; miniatura de vídeo; quick start en pocos comandos con enlace a docs y Docker; tabla comparativa con alternativas; canal de reporte de bugs. Nota: el titular es de marketing ("probably the most intelligent AI coder"), no apto como modelo de tono para un trainee.
2. **bia-bob** ([link](https://github.com/haesleinhuepf/bia-bob), consultado 2026-11-22): descripción en una línea; banner y GIFs de uso; badges (PyPI, licencia, Colab); instalación con conda/pip; configuración por proveedor; descargos sobre verificar el código generado y el envío de datos al proveedor LLM.
3. **xrays-and-gradcam** (también en awesome-readme; aprendizaje profundo, no LLM): no se leyó el README, no se describe. Sin verificación.

Qué hacen bien en común (observado en las dos lecturas): evidencia visual al inicio, instalación corta, enlace a docs largos y, en bia-bob, transparencia sobre los límites del uso de LLM. Ambos son herramientas reales, no portafolios de trainee: la comparación es indicativa. No se alcanzaron 3-5 ejemplos verificados de IA/RAG/agentes; solo 2.

## CRITERIOS VERIFICABLES (para evaluar un README)

Cada criterio se responde sí / no / parcial. Tipo de fuente entre corchetes.

1. Dice en las primeras líneas qué hace el proyecto y por qué es útil. [oficial] [GitHub Docs](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes); [Google](https://google.github.io/styleguide/docguide/READMEs.html)
2. Indica cómo empezar (requisitos y comandos mínimos) y esos pasos funcionan desde un clon limpio. [oficial] [Microsoft Learn](https://learn.microsoft.com/en-us/azure/devops/repos/git/create-a-readme?view=azure-devops)
3. Incluye un ejemplo de uso con salida esperada. [oficial] [Microsoft Learn](https://learn.microsoft.com/en-us/azure/devops/repos/git/create-a-readme?view=azure-devops); [Google](https://google.github.io/styleguide/docguide/READMEs.html)
4. Hay al menos una captura o GIF en la introducción (si hay UI). [oficial] [Microsoft Learn](https://learn.microsoft.com/en-us/azure/devops/repos/git/create-a-readme?view=azure-devops); [guía reconocida] [Make a README](https://www.makeareadme.com/)
5. Los pasos complejos están en docs enlazadas, no dentro del README. [oficial] [Microsoft Learn](https://learn.microsoft.com/en-us/azure/devops/repos/git/create-a-readme?view=azure-devops)
6. Enlaza a la documentación detallada (docs/). [oficial] [Google](https://google.github.io/styleguide/docguide/READMEs.html)
7. Declara estado del proyecto y contacto o mantenedor. [oficial] [Google](https://google.github.io/styleguide/docguide/READMEs.html); [GitHub Docs](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes)
8. Indica licencia y cómo contribuir o reportar. [oficial] [Microsoft Learn](https://learn.microsoft.com/en-us/azure/devops/repos/git/create-a-readme?view=azure-devops)
9. Ninguna información está desactualizada (versiones, comandos y capturas coinciden con el código). [oficial] [Google](https://google.github.io/styleguide/docguide/READMEs.html)
10. Pesa menos de 500 KiB y usa encabezados jerárquicos (para el índice automático). [oficial] [GitHub Docs](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes)
11. Si usa secciones colapsables, `<details>` tiene `<summary>` y renderiza en GitHub. [oficial] [GitHub Docs](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/organizing-information-with-collapsed-sections)
12. Si incluye diagramas, usan sintaxis que GitHub renderiza (mermaid). [oficial] [GitHub Docs](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/creating-diagrams)
13. Incluye roadmap, estado o una sección de trabajo pendiente. [guía reconocida] [Make a README](https://www.makeareadme.com/)
14. Declara las limitaciones principales de forma concisa, sin listar todos los bugs. [opinión de autor] [idratherbewriting](https://idratherbewriting.com/2010/12/16/known-limitations/) (única fuente directa)
15. Hay un enlace de demo o despliegue, o evidencia reproducible (GIF, vídeo, salida real). [opinión] [kazkozdev](https://dev.to/kazkozdev/i-studied-how-github-readmes-are-actually-evaluated-here-are-the-5-things-that-matter-2epd); [Code Labs Academy](https://codelabsacademy.com/en/blog/github-portfolio-junior-developers-what-to-include-remove)
16. Hay `.env.example` y ningún secreto en el repo. [opinión] [Code Labs Academy](https://codelabsacademy.com/en/blog/github-portfolio-junior-developers-what-to-include-remove)
17. Explica decisiones y trade-offs ("what I learned"), no solo lista tecnologías. [opinión] [Code Labs Academy](https://codelabsacademy.com/en/blog/github-portfolio-junior-developers-what-to-include-remove); [JSGuruJobs](https://dev.to/jsgurujobs/portfolio-code-that-gets-you-hired-what-recruiters-actually-see-in-your-github-h9n)
18. Muestra señales de disciplina (tests, CI) y los comandos para ejecutarlos. [oficial para comandos de test] [Microsoft Learn](https://learn.microsoft.com/en-us/azure/devops/repos/git/create-a-readme?view=azure-devops); [opinión para CI como señal] [kazkozdev](https://dev.to/kazkozdev/i-studied-how-github-readmes-are-actually-evaluated-here-are-the-5-things-that-matter-2epd)
19. Los badges son significativos (estado real de CI, versión, licencia), no decorativos. [opinión] [Wei](https://dev.to/iris1031/github-readme-best-practices-how-to-write-a-readme-that-gets-stars-2gb2)
20. El README es escaneable: encabezados claros, tablas o listas cortas, jerarquía visual. [estudio sobre CV, extrapolado] [HR Dive / Ladders](https://www.hrdive.com/news/eye-tracking-study-shows-recruiters-look-at-resumes-for-7-seconds/541582/)

Sin criterio por falta de fuente sólida: idioma del README (P7), estructura narrativa concreta para README (P3), longitud óptima (P6), tiempo de revisión real de repos (P2). Cualquier regla sobre esos puntos sería opinión sin respaldo.
