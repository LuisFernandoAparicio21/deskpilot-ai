# Evaluadores open source de terceros para DeskPilot AI

Investigación del 2026-11-22 (paso 1: solo lectura, no se instaló ni se ejecutó nada).

## Método y alcance

- Los datos (estrellas, último commit, licencia, archivado) salieron de `gh api repos/...` y `gh search repos`; los README, de `gh api .../readme` y WebFetch. Lo que no se pudo confirmar dice "no verificado".
- "Último commit" es el commit más reciente de la rama por defecto (`commits?per_page=1`). Excepción: `microsoft/PyRIT`, donde solo se tiene la fecha de `pushed_at`.
- Criterio de inclusión: último commit desde 2025-11-22 y enlace verificado. Máximo 5 por categoría.
- Las estrellas y fechas cambian a diario: son una foto del 2026-11-22.

### Qué es DeskPilot (para juzgar aplicabilidad)

Leído de `README.md` y de la estructura del repo:

- Asistente de mesa de servicio TI nivel 1 para un banco ficticio. RAG **extractivo** (fastembed + Chroma, 15 artículos), responde con cita (`citations[].article_id`, `similarity`) y dice "no lo sé" sin evidencia. Modo local sin llaves (`LLM_PROVIDER=none`); un LLM es opcional (Anthropic, OpenAI o Gemini).
- API REST con FastAPI: `python main.py serve` (puerto 8000), autenticación por cabecera `X-API-Key`, `/docs` apagado. También servidor MCP (`python main.py mcp`).
- Ya tiene `tests/eval/` con `cases.csv` (30 casos), `heldout_cases.csv` (40, 39/40 según el README), `rejection_cases.csv`, `results.csv` y `results.summary.json`. También `tests/unit`, `integration` y `e2e`, CI en `.github/workflows/ci.yml`, Python 3.13, licencia MIT y 9 ADR.
- Consecuencia práctica: como la respuesta es extractiva, métricas de generación (fidelidad, relevancia de la respuesta) aportan poco. Lo que sí aplica es recuperación (¿citó el artículo correcto?), rechazo fuera de dominio, seguridad (inyección, fraude) y higiene del repo/README.

---

## Ficha de referencia: DeepAudit

| Campo | Dato |
| --- | --- |
| Link | https://github.com/lintsinghua/DeepAudit |
| Estrellas / último commit / licencia | 7,341 / 2026-11-16 / AGPL-3.0 |
| Mantenido | Sí (versión 3.0.4 según el badge del README, 98 issues abiertos, repo creado 2025-09-19) |
| Qué evalúa | Auditoría de seguridad y calidad de un repo completo. Modo **Agent** multi-agente (Orchestrator, Recon, Analysis, Verification) con RAG y verificación de PoC en sandbox Docker. Modos generales: análisis instantáneo y "cinco dimensiones" (bug, seguridad, rendimiento, estilo, mantenibilidad). 12 tipos de vulnerabilidad (SQLi, XSS, command injection, SSRF, secretos hardcodeados, etc.), reglas OWASP Top 10 personalizables |
| Reporte | Dashboard web y exportación a PDF, Markdown y JSON (hay un ejemplo HTML en `docs/`) |
| Instalación | Docker: `docker compose up -d` tras copiar `backend/env.example` a `backend/.env`, o el compose prebuilt de la v3.0.0. Desde fuente: Python 3.11+, Node 20+, PostgreSQL 15+, Redis (obligatorio para la cola de agentes) y Docker para el sandbox. Frontend en `localhost:3000` |
| Windows | Solo vía Docker Desktop (el README menciona Windows únicamente para configurar Docker Desktop). Soporte nativo: no documentado |
| Qué necesita | Un LLM: llave de proveedor (OpenAI, Claude, Gemini, DeepSeek, Qwen, etc., por LiteLLM) **o** Ollama local (`OLLAMA_BASE_URL`). Sin LLM no audita. La llave de pago es opcional si se usa Ollama (calidad con modelos chicos: no verificado) |
| Salvedades | El README presume 49 CVE y 6 GHSA hallados con una **versión de código cerrado**; lo público puede no igualar eso. La documentación principal está en chino (existe `README_EN.md`). Muy pesado para un repo de ~15 artículos |
| Aplicabilidad a DeskPilot | **Media.** Sirve como segunda opinión de seguridad y calidad del código (API, validación de entrada, secretos). La verificación PoC y el sandbox sobran para esta superficie pequeña, y exige Docker + Postgres + Redis + LLM |

Categoría A: se incluye también abajo como candidato A.

---

## Categoría A: auditores de repositorios con IA

Calidad real: **solo DeepAudit es un auditor de repo con IA maduro y autoalojable.** Los otros son de pentest (dinámico), no de calidad general, o son herramientas no IA muy reconocidas que sirven de complemento.

| # | Proyecto | Estrellas | Último commit | Licencia | Mantenido | Qué evalúa y reporte | Instalación y Windows | Necesita | Aplicabilidad |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | [lintsinghua/DeepAudit](https://github.com/lintsinghua/DeepAudit) | 7,341 | 2026-11-16 | AGPL-3.0 | Sí | Ver ficha de referencia. Dashboard + PDF/MD/JSON | Docker compose; Windows solo vía Docker Desktop | LLM de pago (llave) u Ollama local | Media |
| 2 | [ossf/scorecard](https://github.com/ossf/scorecard) (no IA) | 5,857 | 2026-11-19 | Apache-2.0 | Sí (v5.7.0) | Puntaje 0 a 10 por chequeo y agregado: Branch-Protection, CI-Tests, Code-Review, Security-Policy, Pinned-Dependencies, SAST, Vulnerabilities, License, Maintained, Dangerous-Workflow, etc. Salida en consola o JSON, con `--show-details` | Binario Go (hay `scorecard_5.7.0_windows_amd64.tar.gz` en releases) o Docker `ghcr.io/ossf/scorecard`. El README advierte que en Windows "puede haber problemas" | `GITHUB_AUTH_TOKEN` (token de GitHub gratis). Sin LLM | **Alta** para higiene del repo público (varios chequeos son de seguridad de la cadena de suministro, algunos no aplican a un portafolio) |
| 3 | [usestrix/strix](https://github.com/usestrix/strix) | 77,078 | 2026-11-22 | Apache-2.0 | Sí (620 issues abiertos) | Pentest autónomo con agentes IA: ejecuta el código, encuentra vulnerabilidades y las valida con PoC. Resultados en `strix_runs/<run>`, con parches y reportes | Instalador `curl -sSL https://strix.ai/install \| bash` (CLI) o pip/pipx/uv (`strix-agent`); requiere Docker. Windows: **no verificado** (los docs que se leyeron no lo mencionan) | Llave de LLM de cualquier proveedor (de pago) o modelo local vía `LLM_API_BASE` (Ollama/LM Studio, según README). Hay versión cloud/enterprise de pago aparte | Media: ataca la API en marcha (`X-API-Key`); poca superficie |
| 4 | [KeygraphHQ/shannon](https://github.com/KeygraphHQ/shannon) | 52,188 | 2026-11-20 | AGPL-3.0 | Sí | Pentester autónomo de apps web y APIs: lee el código, planea ataques y ejecuta exploits reales ("no exploit, no report"). Reportes PDF y SARIF | `npx @keygraph/shannon@latest`; Docker y Node 22+. Windows **solo por WSL2** (Windows nativo y Git Bash no soportados, según `docs/platforms.md`) | Llave BYOK (Anthropic, OpenAI, xAI, Bedrock) o modelo local vía Ollama/vLLM/LM Studio. Hay ediciones Pro y Enterprise de pago | Media-baja: necesita la app corriendo y WSL2 |
| 5 | [use-charter/charter](https://github.com/use-charter/charter) | 7 | 2026-07-07 | Otra (no reconocida por GitHub; no verificada) | Joven (repo creado 2026-05-22, v1.0.0, 7 issues) | Puntaje 0 a 100 de "preparación para agentes IA": 18 reglas en 9 categorías (contexto para agentes, MCP sin fijar versión, secretos, compuertas de CI). Determinista, sin LLM, sin red | Binario firmado para Windows amd64/arm64 (`charter_<ver>_windows_amd64.zip`), o brew/go install. `charter doctor` | Nada (sin LLM, sin red) | Media-baja: mide algo distinto a "vista de reclutador"; **experimental, pocas estrellas** |

Vistos y descartados de A: `kodustech/kodus-ai` (1,646 estrellas, 2026-11-22, licencia "Other"): revisor de **pull requests** que hay que desplegar con base de datos y LLM propio, no audita un repo completo; `The-PR-Agent/pr-agent` (16,567, MIT, 2026-11-22): revisa PRs y pide llave de LLM; `reposwarm/reposwarm` (321, Apache-2.0): genera documentos de arquitectura (no puntúa) y exige Temporal, Docker y Anthropic/Bedrock/LiteLLM; `Joopinhontas/claude-repo-audit` (2 estrellas, repo creado y con último commit el mismo día 2026-08-14): calidad dudosa y además es otra herramienta basada en Claude. Complementos no IA conocidos (solo estadísticas verificadas, instalación no verificada): `PyCQA/bandit` (8,399, Apache-2.0, 2026-11-09) y `gitleaks/gitleaks` (31,257, MIT, 2026-10-28).

---

## Categoría B: evaluadores de portafolio y "vista de reclutador"

**Categoría floja.** No hay ningún proyecto maduro: todos son proyectos de hackathon o de una persona, con 0 a 28 estrellas, casi todos nacidos en 2026. Se listan solo los que existen y están activos; ninguno tiene respaldo comunitario. Úsense como heurística, no como verdad.

| # | Proyecto | Estrellas | Último commit | Licencia | Mantenido | Qué evalúa y reporte | Instalación y Windows | Necesita | Aplicabilidad |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | [mohsen-niksirat/Repodest](https://github.com/mohsen-niksirat/Repodest) | 19 | 2026-11-12 | MIT | Activo (repo creado 2026-09-01) | Analizador de un repo público: "health score" de 10 chequeos ponderados (licencia, README, tests, CI, docs, frescura), commits, lenguajes, y un resumen listo para LLM. Corre 100% en el navegador | Sitio en vivo en GitHub Pages (sin instalar nada); instalación local: no verificado. Independiente de SO | Nada ("sin backend, sin tracking, sin llave") | **Media-alta**: es lo más parecido a señales de reclutador; **experimental** |
| 2 | [Shreeja-88/github-portfolio-analyzer](https://github.com/Shreeja-88/github-portfolio-analyzer) ("GitGrade") | 10 | 2026-02-21 | MIT | Sin actividad desde febrero (dentro de la ventana, 9 meses) | Simula la mirada de un hiring manager sobre un **perfil** de GitHub: puntaje 0 a 100, nota A+ a D, señales de contratación, riesgos y plan a 30 días. Mide documentación, profundidad, consistencia, impacto, completitud | Node: `npm install`, `.env` con `GITHUB_TOKEN`, `npm start`. Windows: no verificado (es Node) | Token de GitHub (opcional, evita límites). Si usa un LLM: no verificado | Media: evalúa perfil más que un repo; **proyecto de hackathon** |
| 3 | [ammar31mawassi/repo-health-analyzer](https://github.com/ammar31mawassi/repo-health-analyzer) | 0 | 2026-06-01 | MIT | Poco claro (un solo autor, sin issues) | Puntaje **determinista** de "legibilidad para reclutadores": README, instrucciones de uso, capturas o demo, tests visibles, stack, actividad reciente | Next.js: `npm install && npm run dev`; también desplegado como página estática. Windows: no verificado | Nada (sin variables de entorno; API pública de GitHub) | Media-alta por criterios; **calidad dudosa (0 estrellas)** |
| 4 | [Sajiree-2005/RecruitLens](https://github.com/Sajiree-2005/RecruitLens) | 1 | 2026-07-25 | **Sin licencia** | Poco claro | "Recruiter Signal Score" transparente por dimensiones y puntaje 0 a 100 del README, con impacto estimado de cada mejora | Next/Node: `npm install && npm run dev` | No verificado | Baja-media; **sin licencia: no reutilizable legalmente, experimental** |
| 5 | [hkhan701/RepoRoast](https://github.com/hkhan701/RepoRoast) | 28 | 2026-10-10 | **Sin licencia** | Activo | "Roast" humorístico de un repo hecho por un LLM (README, commits y archivos clave). Es más entretenimiento que evaluación | Sitio web de su autor; autoalojar: no verificado | Un LLM propio si se autoaloja (no verificado) | Baja; **calidad dudosa para evaluar** |

Recomendación práctica para B: no hay que apostar por una sola herramienta. Combinar Repodest (señales de salud) con OpenSSF Scorecard (categoría A) y una revisión manual con `gh`.

---

## Categoría C: evaluadores de sistemas RAG y agentes

Categoría fuerte. Recordar que DeskPilot es extractivo sin LLM en modo local, así que los "jueces con LLM" (fidelidad, relevancia de respuesta) dicen poco y exigen llave u Ollama; lo útil es evaluar contra la API real y la recuperación.

| # | Proyecto | Estrellas | Último commit | Licencia | Mantenido | Qué evalúa y reporte | Instalación y Windows | Necesita | Aplicabilidad |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | [promptfoo/promptfoo](https://github.com/promptfoo/promptfoo) | 27,549 | 2026-11-22 | MIT | Sí. El README dice que "ahora es parte de OpenAI" y que sigue siendo open source con MIT | Evals y red teaming de apps LLM. Proveedor **HTTP** (POST con cabeceras y JSON, `transformResponse`) apto para `POST /buscar_solucion`. Aserciones deterministas (`contains`, `javascript`) funcionan **sin ninguna llave** (verificado en la documentación del proveedor HTTP). Red team: inyección de prompt, etc. Reporte: `promptfoo view` (UI web local), salidas JSON/CSV, informe de vulnerabilidades | `npm install -g promptfoo`, `npx promptfoo@latest`, `brew install promptfoo` o `pip install promptfoo`. Windows: no verificado explícitamente, es Node/CLI | Evals deterministas: nada. Red team: por defecto usa tu llave de OpenAI si existe y **si no hay llave manda la generación a la API de promptfoo** (los textos de ataque salen de tu máquina). Se puede desactivar con `PROMPTFOO_DISABLE_REDTEAM_REMOTE_GENERATION=true` y usar Ollama (`ollama:chat:...`). No se requiere cuenta para uso open source | **Alta** |
| 2 | [vibrantlabsai/ragas](https://github.com/vibrantlabsai/ragas) (antes `explodinggradients/ragas`) | 16,402 | 2026-11-14 | Apache-2.0 | Sí | Métricas RAG y agentes: precisión y recall de contexto, fidelidad, relevancia. Hay variantes **sin LLM**: `NonLLMContextPrecision/Recall` y `IDBasedContextPrecision/Recall` (comparan IDs de contexto, verificado en sus docs). Salida: puntajes por muestra en Python | `pip install ragas`; plantilla `ragas quickstart` con `rag_eval`. Windows: no verificado (es Python) | Métricas con LLM: llave (el ejemplo del README usa `OPENAI_API_KEY`) o modelo propio. Métricas por IDs/strings: nada. Telemetría activada por defecto (se apaga con `RAGAS_DO_NOT_TRACK=true`) | Media-alta, solo para recuperación (el `article_id` de `citations` permite medir IDs) |
| 3 | [confident-ai/deepeval](https://github.com/confident-ai/deepeval) | 19,594 | 2026-11-22 | Apache-2.0 | Sí | "Pytest para LLMs": métricas RAG (answer relevancy, faithfulness, contextual recall, precision, relevancy), de agentes (task completion, tool correctness) y **MCP** (MCP use, task completion). Hay G-Eval personalizado. Reporte en pytest o consola; panel opcional en Confident AI | `pip install -U deepeval`; `deepeval login` es opcional. Windows: no verificado | Juez por defecto con `OPENAI_API_KEY` (de pago); alternativa 100% local con Ollama (`deepeval set-ollama --model=...`, verificado en docs). Telemetría: no verificado | Media: métricas MCP y de recuperación útiles; las de generación aportan poco al modo extractivo |
| 4 | [Giskard-AI/giskard-oss](https://github.com/Giskard-AI/giskard-oss) | 5,969 | 2026-11-22 | Apache-2.0 | Sí. La v3 es una reescritura y **v2 ya no se mantiene** | `giskard-checks`: escenarios y aserciones (de simples a LLM-juez), verificación de respuestas ancladas al contexto. `giskard-scan`: escaneo de vulnerabilidades y calidad RAG (inyección de prompt, jailbreak, contenido dañino) | `pip install giskard` o `pip install "giskard[scan]"`; requiere Python 3.12+ (DeskPilot usa 3.13). Windows: no verificado | Proveedor LLM para juez y generación (extras `openai`, `anthropic`, etc.): de pago u otro compatible. Telemetría opcional (`DO_NOT_TRACK=1`) | Media |
| 5 | [NVIDIA/garak](https://github.com/NVIDIA/garak) | 10,134 | 2026-11-18 | Apache-2.0 | Sí | Escáner de vulnerabilidades de LLM (sondas de inyección de prompt, codificaciones, fuga de datos, etc.) con detectores. Generador **REST** para apuntar a cualquier endpoint que devuelva texto o JSON | `python -m pip install -U garak`. Windows: tiene workflow de pruebas en Windows (`test_windows.yml`), uso real no verificado | Para un objetivo REST no pide llave de proveedor; si los detectores usan un LLM juez: no verificado | Media-baja: sus sondas apuntan a un LLM generativo; DeskPilot en modo local no tiene |

Vistos y no incluidos en el top 5 de C: `truera/trulens` (3,667, MIT, 2026-11-19; trazas OpenTelemetry y jueces LLM), `UKGovernmentBEIS/inspect_ai` (3,310, MIT, 2026-11-22; framework general de evals, no específico de RAG), `confident-ai/deepteam` (3,118, Apache-2.0, 2026-10-23; red teaming), `Arize-ai/phoenix` (12,376, 2026-11-22, licencia no estándar "NOASSERTION"), `comet-ml/opik` (23,487, Apache-2.0, 2026-11-20), `microsoft/PyRIT` (5,029, MIT, pushed 2026-11-22; red teaming, no se revisó el README). **Fuera de ventana o inactivos:** `amazon-science/RAGChecker` (último commit 2024-12-13) y `stanford-futuredata/ARES` (2025-03-28). `Azure/PyRIT` es una copia archivada, no usar.

---

## Categoría D: verificadores de documentación y README

Categoría **media-floja**: no hay un "puntuador de README" maduro. Lo sólido son linters genéricos (prosa, enlaces, Markdown); lo específico de README son proyectos diminutos.

| # | Proyecto | Estrellas | Último commit | Licencia | Mantenido | Qué evalúa y reporte | Instalación y Windows | Necesita | Aplicabilidad |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | [lycheeverse/lychee](https://github.com/lycheeverse/lychee) | 4,155 | 2026-11-12 | Apache-2.0 | Sí (v0.24.2) | Verificador de enlaces rotos en Markdown/HTML (incluye relativos y externos). Lista de enlaces fallidos por archivo | Binario Rust; Windows con `winget install --id lycheeverse.lychee`, `scoop install lychee` o zip `lychee-x86_64-pc-windows-msvc` | Nada (un `GITHUB_TOKEN` opcional ayuda con límites: no verificado) | **Alta**: el README y los docs tienen muchos enlaces entre archivos |
| 2 | [vale-cli/vale](https://github.com/vale-cli/vale) | 6,419 | 2026-11-21 | MIT | Sí (v3.28.1) | Linter de prosa configurable por estilos (claridad, jerga, consistencia). Alertas con línea y severidad en consola o JSON. Existe el paquete `tbhb/vale-ai-tells` (139 estrellas, MIT, 2026-10-11) que busca "marcas" de texto escrito por IA (no revisado a fondo) | Binario Go sin dependencias; zip para Windows 64 bits y arm64; paquete Chocolatey | Nada. Requiere `.vale.ini` y un conjunto de estilos (cómo se descargan: no verificado) | Media: los estilos están pensados para inglés y los docs de DeskPilot están sobre todo en español |
| 3 | [DavidAnson/markdownlint-cli2](https://github.com/DavidAnson/markdownlint-cli2) (motor: [markdownlint](https://github.com/DavidAnson/markdownlint), 6,447 estrellas) | 986 | 2026-11-20 | MIT | Sí | Estructura y estilo del Markdown (encabezados, listas, HTML embebido, líneas). Reporta regla y línea | `npm install markdownlint-cli2 --global` (Node). Windows: no verificado, es Node | Nada | Media: el README usa HTML y emojis a propósito, saldrán avisos de estilo |
| 4 | [scarletkc/seiso](https://github.com/scarletkc/seiso) | 196 | 2026-10-13 | MIT | Sí, pero joven (v0.4.0; la especificación es "provisional antes de 1.0.0") | Linter de una convención de docs: cada documento declara un tipo, cada hecho tiene un solo lugar, evita valores que cambian rápido (versiones, conteos, estado) en páginas duraderas. Cada diagnóstico dice dónde y cómo arreglarlo | `uv tool install seiso`, `pipx install seiso`, `cargo install seiso` o npm; binarios para Windows x64 y arm64 | Nada | Media: opina sobre el estilo de docs; el README de DeskPilot lleva muchas cifras que lo dispararían |
| 5 | [getdocrot/docrot](https://github.com/getdocrot/docrot) | 5 | 2026-07-04 | MIT | Poco claro (repo creado 2026-07-03, un solo autor); **experimental** | Verifica ejemplos de código, imports, enlaces, anclas e imágenes del Markdown contra el código real (`missing-export`, `broken-link`, `missing-anchor`, `missing-script`...). Pensado sobre todo para proyectos JS/TS; sintaxis Python solo si hay intérprete | `npx docrot-cli` (Node). Windows: no verificado | Nada | Media-baja: enlaces y anclas sí aplican; chequeos de exports/npm no |

Vistos y descartados de D: `Thomaszhou22/better-readme` (11 estrellas, sin licencia, 2026-11-15), `tahaefekusoglu/Readme-Health-Checker` (1 estrella, MIT, 2026-04-13), `willbyers1/README-SCORER` (3, sin licencia, 2026-03-23) y `kamarajendra/readme-roast-fixer` (0, MIT, 2026-06-01; puntúa 7 categorías de README con reglas): todos diminutos y de un solo autor; `agent-ecosystem/afdocs` (114, MIT, 2026-11-01): evalúa **sitios** de docs por URL con una especificación 0.x, no sirve para un README suelto; `jeduden/mdsmith` (21, licencia no reconocida, 2026-10-04): linter de Markdown sin ventaja sobre markdownlint.

---

## TOP recomendado para correr sobre DeskPilot

Orden por valor y bajo costo. Marcado con (LLM) lo que pide llave de pago o modelo local.

1. **promptfoo** (categoría C). Evalúa la API real con las preguntas de `tests/eval/` (`cases.csv`, `heldout_cases.csv`, `rejection_cases.csv`): artículo citado correcto, rechazo fuera de dominio, escalamiento de fraude, y cadenas de inyección de prompt como aserciones deterministas. Se corre así: levantar `python main.py serve`, definir un proveedor `https` hacia `POST /buscar_solucion` con la cabecera `X-API-Key`, y ejecutar `npx promptfoo@latest eval` y `promptfoo view`. **No necesita llave ni cuenta** para las aserciones deterministas. Ojo: el módulo `redteam` por defecto envía la generación de ataques a la API de promptfoo si no hay llave de OpenAI; desactivar con `PROMPTFOO_DISABLE_REDTEAM_REMOTE_GENERATION=true` o usar Ollama.
2. **OpenSSF Scorecard** (A, no IA). Evalúa el repo público como lo vería alguien de seguridad o un reclutador técnico: protección de ramas, CI, política de seguridad, dependencias fijadas, SAST, vulnerabilidades, licencia y mantenimiento. Se corre con `scorecard --repo=github.com/LuisFernandoAparicio21/deskpilot-ai --show-details` (binario de Windows en releases; el README avisa de posibles problemas en Windows, alternativa Docker). Necesita un `GITHUB_AUTH_TOKEN` gratuito. **Sin LLM.**
3. **lychee** (D). Revisa enlaces rotos del README y de `docs/` (el README apunta a muchos archivos y a un tablero de badges). Se corre con `winget install --id lycheeverse.lychee` y `lychee README.md docs/**/*.md`. **Nada de llaves.**
4. **Ragas, solo métricas sin LLM** (C). Mide recuperación con `IDBasedContextPrecision/Recall` o `NonLLMContext*`, tomando el `article_id` de `citations` y el artículo esperado de `cases.csv`. `pip install ragas` en un venv aparte; apagar telemetría con `RAGAS_DO_NOT_TRACK=true`. **Sin llave** para estas métricas; las métricas con LLM (fidelidad, relevancia) sí piden llave u Ollama y aportan poco a un RAG extractivo.
5. **DeepAudit** (A, referencia). Auditoría de seguridad y calidad del código con reporte PDF, Markdown o JSON. Se corre clonando, copiando `backend/env.example` a `backend/.env`, `docker compose up -d`, y abriendo `localhost:3000`; con Docker Desktop en Windows. **(LLM)** Necesita llave de LLM de pago **o** Ollama local, además de Postgres y Redis (los levanta el compose). Es el más pesado de la lista; hacerlo solo si se acepta Docker y un LLM.

Alternativas si se acepta llave de pago u Ollama: **DeepEval** (métricas de recuperación y de uso de MCP, `deepeval set-ollama` para correrlo local) y **Giskard** (escaneo de vulnerabilidades y calidad RAG). Opción rápida sin instalación para "vista de reclutador": **Repodest** en su sitio de GitHub Pages (experimental).

## Datos no verificados (resumen)

- Soporte nativo de Windows de promptfoo, Ragas, DeepEval, Giskard, markdownlint-cli2, docrot, Strix y DeepAudit (solo Docker Desktop en este último; WSL2 en Shannon sí verificado).
- Si los detectores de garak o la telemetría de DeepEval requieren LLM o red.
- Calidad de DeepAudit con modelos pequeños de Ollama; si GitGrade o RecruitLens usan un LLM; cómo Vale descarga sus estilos.
- Instalación local de Repodest; licencia exacta de Charter y de Kodus (GitHub las clasifica como "Other"/no reconocida).
- Estas herramientas no se ejecutaron: los puntajes que den al correrse sobre DeskPilot son una heurística de cada herramienta, no una verdad.
