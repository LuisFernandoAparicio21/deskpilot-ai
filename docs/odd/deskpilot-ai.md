# DeskPilot AI — Documento de feature (ODD)

> Fuente de verdad para retomar el trabajo en cualquier sesión. Los subagentes reciben la RUTA de este documento y el ID de su tarea, nunca un resumen.
> Clasificación: **GRANDE — 36 tareas — varias sesiones, pasos manuales externos (Fabric/Copilot Studio), 2 zonas de alto riesgo (secretos, crear_ticket), requisitos que no sobreviven a la compactación de contexto.**

## Specs

### S1 — Estructura del repo
> "El repo respeta EXACTAMENTE la estructura \"production-style RAG project\" que te di (17 elementos, mismos nombres). Todo lo demás se acomoda DENTRO de esa estructura o en las pocas carpetas estándar de producción listadas abajo. Ninguna otra carpeta en la raíz."
> "Cada carpeta de src/ con __init__.py y README.md de 3 líneas sobre su responsabilidad."

Criterios de aceptación:
- [ ] `git ls-files` solo muestra en la raíz: README.md, requirements.txt, .gitignore, config.yaml, main.py, .env.example, requirements-dev.txt, pyproject.toml, Dockerfile, .dockerignore, LICENSE, CHANGELOG.md, CONTRIBUTING.md, CLAUDE.md y las carpetas src/, tests/, logs/, data/, integrations/, docs/, scripts/, .github/, .claude/.
- [ ] `.env` existe solo en local y está ignorado; `scratch/` está ignorado y nunca se versiona.
- [ ] src/ tiene exactamente ingestion, chunking, embeddings, vectordb, retrieval, prompts, llm, api, utils; cada una con `__init__.py` y `README.md` de 3 líneas.
- [ ] tests/ tiene unit/, integration/, e2e/, eval/. data/ tiene knowledge_base/, sample/, raw/ (ignorado), vectordb/ (ignorado). integrations/ tiene fabric/ (notebooks/, sql/) y copilot_studio/. docs/ tiene odd/, adr/, screenshots/.
- [ ] `pyproject.toml` solo contiene configuración de herramientas; dependencias en requirements*.txt.

### S2 — Subagentes
> "TODO se hace por subagentes, UNO A LA VEZ (secuencial, nunca en paralelo)."
> "Un archivo Markdown por subagente con frontmatter YAML: name, description (clara, para que sepas cuándo delegar), tools (mínimas necesarias) y system prompt."

Criterios de aceptación:
- [ ] `.claude/agents/` contiene repo-architect, data-engineer, rag-engineer, api-engineer, copilot-studio-designer, qa-tester, docs-writer, security-verifier (.md) con frontmatter válido.
- [ ] security-verifier no tiene herramientas de escritura (sin Write/Edit) y su prompt prohíbe modificar archivos.
- [ ] Cada tarea registra en el Log qué subagente la ejecutó.

### S3 — Datos sintéticos (C1)
> "5,000 tickets con semilla fija. Campos: ticket_id, fecha_apertura, fecha_cierre, categoria, subcategoria, prioridad, sucursal (ciudades de México), area, canal, sla_horas, sla_cumplido, solucion, es_repetitivo, idioma. Patrones: ~40% en 5 tipos repetitivos, picos de bloqueo en quincena, peor SLA en sucursales foráneas."

Criterios de aceptación:
- [ ] `python main.py generate-data` escribe `data/raw/tickets.csv` (5,000 filas) y `data/raw/sucursales.csv` (dimensión para JOIN); misma semilla ⇒ mismo hash de archivo.
- [ ] Contiene los 14 campos citados + derivados `horas_resolucion` y `anio_mes` (para SQL portable).
- [ ] `es_repetitivo` entre 35% y 45%, concentrado en 5 subcategorías.
- [ ] Tasa de tickets de bloqueo en días de quincena (14–16 y 29–31/1) ≥ 1.5× la del resto de días.
- [ ] % SLA cumplido en sucursales foráneas (fuera de CDMX/Guadalajara/Monterrey) ≥ 10 pp menor.
- [ ] `data/sample/tickets_sample.csv` con 200 filas versionado. Tests unitarios verifican todo lo anterior.

### S4 — Base de conocimiento (C2)
> "15 artículos: reseteo de contraseña, desbloqueo de usuario, token bancario, VPN, impresoras, acceso a SAP, correo, carpetas compartidas, Teams, equipo lento, etc. Formato: síntoma, causa, pasos, cuándo escalar."

Criterios de aceptación:
- [ ] 15 archivos `.md` en `data/knowledge_base/` con metadatos (id, título, categoría) y secciones Síntoma, Causa, Pasos, Cuándo escalar.
- [ ] Cubre todos los temas citados. Un test valida el formato de los 15.

### S5 — SQL de negocio
> "fabric/sql/ con 10 consultas comentadas (JOIN, GROUP BY, CTE, funciones de ventana), validadas en modo local y en Fabric."
> "10 consultas SQL comentadas (top incidencias, % SLA por área y sucursal, horas perdidas, tickets automatizables, tendencia mensual)."

Criterios de aceptación:
- [ ] 10 archivos `.sql` en `integrations/fabric/sql/`, cada uno con comentario de pregunta de negocio; en conjunto usan JOIN, GROUP BY, CTE y funciones de ventana.
- [ ] SQL portable SQLite / T-SQL (sin TOP ni LIMIT; ranking con ROW_NUMBER).
- [ ] Test de integración ejecuta las 10 sobre SQLite y todas devuelven filas.
- [ ] Validación en Fabric registrada en Fase C (manual).

### S6 — Microsoft Fabric (código)
> "[CÓDIGO] notebook PySpark a tabla Delta"
> "todo el código del modo 'fabric' listo esperando solo credenciales."

Criterios de aceptación:
- [ ] Notebook PySpark en `integrations/fabric/notebooks/` que lee el CSV de Files, limpia, tipa y escribe tablas Delta `tickets` y `sucursales`.
- [ ] DDL del Warehouse (`tickets_nuevos`) en `integrations/fabric/sql/`.
- [ ] Conexión al SQL analytics endpoint / Warehouse por variables de entorno, basada en documentación oficial (fuente en docs/sources.md), testeada con mocks.

### S7 — Pipeline RAG (C4)
> "ingestion → chunking → embeddings → ChromaDB → retrieval con umbral → prompt con cita → llm. Respuesta siempre con el artículo fuente; 'no lo sé, escalo a un agente humano' si no hay evidencia."

Criterios de aceptación:
- [ ] `python main.py index` construye índice Chroma persistente en `data/vectordb/`.
- [ ] Respuesta incluye id y título del artículo fuente; si la similitud no supera el umbral de config.yaml devuelve el mensaje de escalamiento.
- [ ] Embeddings multilingües locales (fastembed) sin llaves; embedder falso determinista para tests.
- [ ] LLM configurable none/Claude/OpenAI/Gemini; `none` funciona sin llaves.
- [ ] La indexación nunca corre dentro de una petición de la API. Test de integración indexar → buscar → responder / "no lo sé".

### S8 — API (C5)
> "Herramientas: buscar_solucion (RAG), consultar_estado_ticket, crear_ticket (clasifica categoría y prioridad), metricas_area. Modos 'local' (SQLite + Chroma) y 'fabric' (SQL endpoint por variables de entorno). OpenAPI listo para conectarse en Copilot Studio."
> "API: endpoint /health, auth con header X-API-Key, validación estricta de entradas, manejo global de errores con respuestas consistentes, timeouts, límites de longitud."

Criterios de aceptación:
- [ ] `/health` sin auth; resto exige `X-API-Key` (401 si falta o es inválida).
- [ ] buscar_solucion, consultar_estado_ticket, metricas_area con modelos Pydantic y límites de longitud.
- [ ] Errores con formato JSON consistente; header `X-Request-ID` en cada respuesta; timeout por petición.
- [ ] Repositorio local (SQLite) y fabric intercambiables por inyección de dependencias.
- [ ] `python main.py export-openapi` genera `integrations/copilot_studio/openapi.yaml` en la versión que acepta Copilot Studio (verificada en docs oficiales).

### S9 — crear_ticket [ALTO RIESGO]
> "Herramienta crear_ticket: escribe datos y clasifica prioridad"

Criterios de aceptación:
- [ ] Valida entradas (longitudes, enums), clasifica categoría y prioridad de forma determinista en modo `none`, persiste en SQLite (local) o Warehouse (fabric) y devuelve ticket_id.
- [ ] No registra datos personales ni secretos en logs.
- [ ] Tests cubren clasificación, validación, persistencia y entradas maliciosas. Revisión de security-verifier aprobada.

### S10 — Servidor MCP
> "Agente en Copilot Studio + API con herramientas + servidor MCP + RAG con citas; video demo."

Criterios de aceptación:
- [ ] Servidor MCP expone las 4 herramientas, reutilizando la misma capa de servicio que la API.
- [ ] Transporte y montaje verificados contra la documentación oficial del SDK de MCP; protegido por API key cuando se expone por HTTP.
- [ ] Test de integración lista herramientas y llama al menos una.

### S11 — Agente en Copilot Studio (C6)
> "[CÓDIGO] instrucciones, temas, frases y escalamiento. [MANUAL] crear agente, cargar base de conocimiento, conectar la API/MCP como herramienta, probar y exportar si se puede. Bilingüe español/inglés."

Criterios de aceptación:
- [ ] `integrations/copilot_studio/` con instrucciones del agente, temas con frases de activación ES/EN, mensajes de escalamiento y openapi.yaml.
- [ ] Pasos manuales en docs/MANUAL_STEPS.md con links oficiales.

### S12 — Pruebas
> "Pruebas unitarias de cada módulo de src/ y del generador de datos."
> "Pruebas de integración: pipeline RAG completo (indexar → buscar → responder con cita / \"no lo sé\"), API completa con TestClient (4 herramientas, auth con API key, errores), servidor MCP y las 10 consultas SQL sobre SQLite."
> "Prueba end-to-end local: genera datos → carga SQLite → indexa KB → levanta API → corre los 30 casos y guarda resultados."
> "Cobertura con pytest-cov, meta ≥80% en src/. Todo verde antes de cerrar la Fase A."

Criterios de aceptación:
- [ ] tests/unit con un archivo por módulo de src/; tests/integration con RAG, API, MCP y SQL; tests/e2e con el flujo completo.
- [ ] `tests/eval/` con 30 casos CSV (pregunta, intención, esperado, obtenido, pasó/falló, notas) y resultados de `python main.py eval`.
- [ ] Cobertura ≥80% en src/; ruff y mypy sin errores; CI verde.
- [ ] docs/testing-procedure.md documenta cómo se corre todo.

### S13 — Documentación y caso de negocio (C8)
> "README (español + resumen en inglés), arquitectura Mermaid, business-case.md con cifras del SQL (porcentaje repetitivo, contención estimada, horas ahorradas al mes), sources.md."
> "Nota visible en README y business-case.md: \"Datos sintéticos generados para este proyecto; las cifras son ilustrativas\"."

Criterios de aceptación:
- [ ] README con "Por qué este proyecto" (3 líneas, negocio), "Habilidades demostradas" con badges, setup, cómo correr, arquitectura, resultados, link de video (placeholder) y resumen en inglés.
- [ ] docs/architecture.md con diagramas Mermaid.
- [ ] docs/business-case.md con cifras calculadas por las consultas SQL sobre los datos locales (cada cifra cita su consulta), ADRs en docs/adr/.
- [ ] Nota de datos sintéticos visible en README y business-case.

### S14 — Entregables extra por la vacante
> "docs/job-fit.md: tabla 'Requisito/Responsabilidad de un AI Developer Trainee → evidencia en este repo (con links a archivos)'."
> "docs/learning-log.md (plantilla lista; yo agrego mis rutas e insignias)."
> "CONTRIBUTING.md, .github/pull_request_template.md, .github/ISSUE_TEMPLATE/ y CHANGELOG.md."

Criterios de aceptación:
- [ ] job-fit.md cubre los 11 puntos de la matriz con links relativos que existen.
- [ ] learning-log.md con plantilla; CONTRIBUTING, PR template, issue templates y CHANGELOG presentes.

### S15 — Flujo Git por PR
> "Desde T8, TODO el código, tests y docs entran por PR, uno por tarea"
> "Nunca hagas push directo a main después de T7."

Criterios de aceptación:
- [ ] Cada tarea ≥T8 tiene issue (objetivo, criterios, S#), rama `feat/tNN-nombre`, commits ≤400 líneas en conventional commits, PR con plantilla completa y "Closes #n", merge con `--merge` y rama borrada.
- [ ] `git log --first-parent main` después de T7 solo muestra merge commits.

### S16 — Seguridad
> "Cero secretos en el repo: .env local ignorado y .env.example versionado."
> "Revisión de secretos por security-verifier antes de cada push."
> "Todos los datos son sintéticos; nada de datos reales de bancos ni de Stefanini."

Criterios de aceptación:
- [ ] .gitignore cubre .env, .venv, data/raw, data/vectordb, logs/*.log, scratch/.
- [ ] Revisión de security-verifier registrada antes del push de T7, en cada tarea [ALTO RIESGO] y al final.

### S17 — Nivel producción
> "Config: config.yaml + variables de entorno, validadas con Pydantic al arrancar; falla rápido con mensaje claro si falta algo."
> "Logging estructurado (JSON) a consola y a logs/, con request_id por petición. Nunca registra secretos ni datos personales."
> "Interfaces intercambiables (vectordb, llm, repositorio local/fabric) con inyección de dependencias, para poder testear con fakes."
> "Tipado completo; ruff y mypy sin errores; cobertura ≥80% en src/."
> "Dockerfile funcional: la API levanta en modo local dentro del contenedor (verifícalo con docker build y run si Docker está instalado; si no, márcalo como pendiente verificado en el Log, no lo des por hecho)."

Criterios de aceptación:
- [ ] Config inválida ⇒ error claro al arrancar (test).
- [ ] Logs JSON con request_id; test verifica que la API key no aparece en logs.
- [ ] Protocols/ABCs para vectordb, llm y repositorio; tests usan fakes.
- [ ] `docker build` + `docker run` + `curl /health` verificado y registrado en el Log.

### S18 — Fase B: guía manual
> "Antes de entregarme el control, el subagente docs-writer genera docs/MANUAL_STEPS.md: checklist numerado y en orden exacto de lo que me toca hacer"
> "En MANUAL_STEPS.md cada paso de interfaz de Microsoft viene de documentación oficial con su link; lo que no puedas confirmar va marcado \"⚠ verificar en pantalla\"."
> "Si no funciona, agrega en MANUAL_STEPS.md alternativas para conseguir un tenant, sin depender del M365 Developer Program."

Criterios de aceptación:
- [ ] Checklist numerado; cada paso: dónde hacer clic, archivo del repo, qué copiar/pegar, cómo verificar, qué hacer si falla, link oficial o "⚠ verificar en pantalla".
- [ ] Alternativas de tenant sin M365 Developer Program.
- [ ] scripts/check_fabric.py, scripts/check_public_url.py, scripts/update_readme_results.py funcionales y con tests.

### S19 — Cero alucinación
> "Duda de todo lo que no hayas verificado. No inventes APIs, parámetros, flags, versiones ni pasos de interfaz."
> "Verifica ejecutando: instala la versión real, corre el código y confirma la salida. Fija en requirements las versiones comprobadas."

Criterios de aceptación:
- [ ] requirements*.txt con versiones instaladas y probadas en el venv local.
- [ ] Cada tecnología investigada tiene entrada en docs/sources.md.
- [ ] Lo no verificable aparece en el Log como "no verificado".

### S20 — Cero desorden
> "Ningún archivo fuera de la estructura acordada. Nada temporal, duplicado ni de prueba en el repo."
> "Lo experimental va en scratch/ (en .gitignore) y se borra al cerrar cada tarea."
> "Cada PR solo toca los archivos de su tarea."

Criterios de aceptación:
- [ ] scratch/ vacío o inexistente al cerrar cada tarea; `git status` limpio tras cada merge.

### S21 — Prueba final "como reclutador"
> "Antes de cerrar la Fase A, el subagente security-verifier hace también una revisión 'como reclutador': recorre la matriz de evidencia y reporta qué punto de la vacante quedó débil o sin evidencia, para corregirlo antes de entregarme el control."

Criterios de aceptación:
- [ ] Reporte registrado en el Log; puntos débiles corregidos por PR o listados como pendientes.

### S22 — Fase C manual
> "La hago yo siguiendo docs/MANUAL_STEPS.md. Al volver, te paso resultados y capturas, y tú (por subagentes) actualizas README, business-case y testing-procedure con la evidencia real, y haces el push final."
> "Reporte de Power BI con KPIs y video demo de 2–3 minutos (YouTube no listado o Loom) enlazado en el README."

Criterios de aceptación:
- [ ] Tareas manuales caben en ~6 horas; cada una enlaza a su sección de MANUAL_STEPS.md.

### S23 — Documento de requerimientos normativo
> "guarda este documento en el repo"

Criterios de aceptación:
- [ ] `docs/requirements.md` versionado sin cambios respecto al texto del usuario.
- [ ] Cada RF/RNF/RN/HU tiene tarea asignada (ver L4) y al menos una prueba; las tareas cumplen los RF que les corresponden además de su S#.
- [ ] Métricas de la sección 12 calculadas por `python main.py eval` (recall@3, rechazo correcto, clasificación, seguridad, casos aprobados).

## Tasks

### Fase A: Claude Code (automática)

**Base del repo (directo a main, solo hasta T7)**
- T1 [CÓDIGO] Inicializar git con rama main en C:\Users\HP\Proyectos\deskpilot-ai — subagente: repo-architect — cubre S1 — commit: 7376681
- T2 [CÓDIGO] Crear `.claude/agents/` con los 8 subagentes — subagente: repo-architect — cubre S2 — commit: 7376681
- T3 [CÓDIGO] Estructura base: archivos raíz (README esqueleto, requirements*.txt verificados, .gitignore, config.yaml, main.py CLI esqueleto, .env.example, pyproject.toml, LICENSE, CHANGELOG, CONTRIBUTING), .github (ci.yml, PR template, ISSUE_TEMPLATE), carpetas con __init__/README/.gitkeep — subagente: repo-architect — cubre S1, S14, S16, S19 — commit: 7376681
- T4 [CÓDIGO] CLAUDE.md (ODD + todo por subagentes) y docs/sources.md — subagente: docs-writer — cubre S2, S19 — commit: 7376681
- T5 [CÓDIGO] Este documento de feature — subagente: orquestador — cubre todos — commit: 7376681
- T6 [CÓDIGO] [ALTO RIESGO] Revisión de la base: árbol vs S1, secretos, .gitignore, archivos sobrantes — subagente: security-verifier — cubre S1, S16, S20 — commit: 7376681
- T7 [CÓDIGO] Commit de la base, `gh repo create` público con descripción y topics, push — subagente: orquestador — cubre S15 — commit:

**Datos y SQL (por PR)**
- T8 [CÓDIGO] src/utils: config Pydantic (config.yaml + env, fail-fast), logging JSON con request_id, helpers — subagente: repo-architect — cubre S17 — commit: 177c447 (PR #2)
- T9 [CÓDIGO] Generador de tickets sintéticos en src/ingestion + `main.py generate-data` + data/sample (test primero) — subagente: data-engineer — cubre S3 — commit: 0de821b (PR #4)
- T10 [CÓDIGO] Carga a SQLite + `main.py load-db` + 10 consultas SQL portables + tests de integración SQL — subagente: data-engineer — cubre S5 — commit: da04fc0 (PR #6)
- T11 [CÓDIGO] [ALTO RIESGO] Notebook PySpark → Delta, DDL del Warehouse, conexión Fabric por variables de entorno (mocks) — subagente: data-engineer — cubre S6, S16 — commit: d567cb3 (PR #8)

**RAG (por PR)**
- T12 [CÓDIGO] 15 artículos de base de conocimiento + test de formato — subagente: docs-writer — cubre S4 — commit: f2752e2 (PR #10)
- T13 [CÓDIGO] src/ingestion (Markdown/PDF/CSV) + src/chunking por sección con metadatos — subagente: rag-engineer — cubre S7 — commit: e1ffbb6 (PR #12)
- T14 [CÓDIGO] src/embeddings (fastembed + fake) + src/vectordb (Chroma tras interfaz) + `main.py index` — subagente: rag-engineer — cubre S7, S17 — commit: c7a8a84 (PR #14)
- T15 [CÓDIGO] [ALTO RIESGO] src/retrieval (umbral) + src/prompts + src/llm (none/Claude/OpenAI/Gemini) + servicio de respuesta con cita + integración RAG — subagente: rag-engineer — cubre S7, S16 — commit: 309ee8e

**API, MCP y despliegue (por PR)**
- T16 [CÓDIGO] [ALTO RIESGO] FastAPI: /health, X-API-Key, errores, request_id, timeouts, buscar_solucion, consultar_estado_ticket, metricas_area, repositorio local/fabric, `main.py serve` — subagente: api-engineer — cubre S8, S17 — commit: 846d541 (PR #20)
- T17 [CÓDIGO] [ALTO RIESGO] crear_ticket con clasificación de categoría/prioridad y persistencia — subagente: api-engineer — cubre S9 — commit: merge del PR #22
- T18 [CÓDIGO] Servidor MCP con las 4 herramientas — subagente: api-engineer — cubre S10 — commit: merge del PR #24
- T19 [CÓDIGO] `main.py export-openapi` → openapi.json (Swagger 2.0) compatible con Copilot Studio; Dockerfile + .dockerignore pasaron a T19b (rama feat/t19b-dockerfile, mergeada en el PR #28) — subagente: api-engineer — cubre S8, S17 — commit: merge del PR #26; T19b (Dockerfile) = merge del PR #28

**Agente, pruebas y documentación (por PR)**
- T20 [CÓDIGO] integrations/copilot_studio: instrucciones, temas, frases ES/EN, escalamiento — subagente: copilot-studio-designer — cubre S11 — commit: merge del PR #30
- T21 [CÓDIGO] 30 casos de evaluación + `main.py eval` + resultados + test e2e + docs/testing-procedure.md — subagente: qa-tester — cubre S12 — commit: merge del PR #32
- T22 [CÓDIGO] Cobertura ≥80%, ruff/mypy limpios, huecos de tests, CI verde — subagente: qa-tester — cubre S12, S17 — commit: merge del PR #34
- T23 [CÓDIGO] docs/business-case.md con cifras del SQL + docs/adr/ — subagente: docs-writer — cubre S13 — commit: merge del PR #36
- T24 [CÓDIGO] README completo + docs/architecture.md + docs/job-fit.md + docs/learning-log.md + CHANGELOG — subagente: docs-writer — cubre S13, S14 — commit: merge del PR #38
- T25 [CÓDIGO] Fase B: docs/MANUAL_STEPS.md + scripts/check_fabric.py, check_public_url.py, update_readme_results.py — subagente: docs-writer — cubre S18 — commit:
- T26 [CÓDIGO] [ALTO RIESGO] Revisión final de secretos + revisión "como reclutador" — subagente: security-verifier — cubre S16, S21 — commit: (solo reporte)
- T27 [CÓDIGO] Correcciones de T26, suite completa, tag v0.1.0 — subagente: según hallazgo — cubre S12, S21 — commit:

### Fase C: Manual (usuario, ~6 h)
- T28 [MANUAL] Activar prueba de Fabric (cuenta universitaria), crear workspace, lakehouse y warehouse, subir CSV (45 min) — MANUAL_STEPS §Fabric — cubre S6, S22 — commit:
- T29 [MANUAL] Correr notebook y las 10 consultas en el SQL analytics endpoint, ejecutar DDL del Warehouse, capturas (45 min) — cubre S5, S6 — commit:
- T30 [MANUAL] Llenar .env, correr scripts/check_fabric.py, levantar API en modo fabric (30 min) — cubre S6, S8 — commit:
- T31 [MANUAL] Exponer la API con URL pública y correr scripts/check_public_url.py (20 min) — cubre S8 — commit:
- T32 [MANUAL] Crear agente en Copilot Studio, cargar instrucciones, temas y base de conocimiento, conectar la API como herramienta (75 min) — cubre S11 — commit:
- T33 [MANUAL] Correr los 30 casos en el chat de prueba, llenar CSV, capturas (60 min) — cubre S11, S12 — commit:
- T34 [MANUAL] Reporte de Power BI con KPIs (45 min) — cubre S22 — commit:
- T35 [MANUAL] Grabar video 2–3 min, completar learning-log (40 min) — cubre S14, S22 — commit:
- T36 [CÓDIGO] Con resultados del usuario: actualizar README, business-case y testing-procedure con evidencia real, push final por PR — subagente: docs-writer + security-verifier — cubre S22 — commit:

## Log

### L1 — Pedido original del usuario (sin editar)

```json
{
  "rol": "Actúa como Tech Lead orquestador y AI Engineer senior. Guías a un ingeniero en sistemas recién egresado para planear y construir un proyecto de portafolio usando Organic Driven Development (ODD), el protocolo de Gentle-AI (Gentleman Programming). TODO el trabajo se ejecuta mediante subagentes de Claude Code; tú coordinas.",
  "objetivo_de_esta_sesion": "Aplicar ODD a este pedido y construir TODO lo que Claude Code pueda hacer, de principio a fin, en tareas específicas ejecutadas por subagentes, sin detenerte entre bloques. Primero registras el documento de feature (ODD paso 5) y después implementas todas las tareas [CÓDIGO] hasta que el proyecto funcione completo en modo local, con tests pasando, documentación lista y repo subido. Las tareas [MANUAL] (Fabric, Copilot Studio, Power BI, video) NO se intercalan: se dejan TODAS para el final en una guía paso a paso para mí. Solo te detienes antes si una decisión realmente bloquea.",
  "objetivo_maestro": {
    "meta": "El objetivo de TODO el proyecto es demostrar que soy el candidato perfecto para la vacante AI Developer Trainee de Stefanini. Cada decisión, archivo y documento debe servir como evidencia de un requisito o responsabilidad. Si algo no aporta evidencia, no se hace.",
    "texto_vacante_literal": "Be a part of Stefanini! At Stefanini we are more than 30,000 geniuses, connected from more than 40 countries, we co-create a better future. Apply AI Developer Trainee! Requirements: Recent graduate or less than one year of experience in Engineering, Mathematics, Computer Science, Data Science, or a related field. Basic knowledge of programming, logical reasoning, and data management. Basic SQL knowledge. Demonstrated interest in Artificial Intelligence and AI agent development through academic, personal, or practical projects, courses, or internships. Analytical thinking, problem-solving skills, and willingness to learn new technologies and tools. Proactive mindset, teamwork skills, and commitment to professional growth. Responsibilities: Support the design, development, and testing of AI agents using Microsoft Copilot Studio. Query, process, and prepare data using SQL and Microsoft Fabric. Collaborate in identifying business processes and opportunities where AI solutions can add value. Document development activities, testing procedures, and project outcomes. Participate in training programs and learning paths, applying acquired knowledge to real-world projects. What's in for you: Fully remote, Company Equipment, Personnel Days, Multicultural experience, Path Career, Mentoring/Learning Platforms.",
    "matriz_de_evidencia": [
      {
        "punto": "REQ: Programación, razonamiento lógico y manejo de datos",
        "evidencia": "Código Python tipado y modular en src/, generador de datos con reglas de negocio, pipeline RAG limpio, tests."
      },
      {
        "punto": "REQ: SQL básico",
        "evidencia": "fabric/sql/ con 10 consultas comentadas (JOIN, GROUP BY, CTE, funciones de ventana), validadas en modo local y en Fabric."
      },
      {
        "punto": "REQ: Interés demostrado en IA y agentes",
        "evidencia": "Agente en Copilot Studio + API con herramientas + servidor MCP + RAG con citas; video demo."
      },
      {
        "punto": "REQ: Pensamiento analítico y resolución de problemas",
        "evidencia": "docs/business-case.md con análisis de los tickets, hipótesis, cifras y decisión de qué automatizar; ADRs breves con alternativas descartadas."
      },
      {
        "punto": "REQ: Disposición a aprender nuevas tecnologías",
        "evidencia": "docs/learning-log.md: qué aprendí de Copilot Studio, Fabric y MCP en este proyecto, problemas encontrados y cómo los resolví, rutas de Microsoft Learn completadas (las lleno yo)."
      },
      {
        "punto": "REQ: Proactividad, trabajo en equipo y crecimiento",
        "evidencia": "Flujo profesional de Git: issues por tarea, ramas y pull requests con descripción, CONTRIBUTING.md, plantilla de PR, CI; sección 'Siguientes pasos' con mejoras propuestas."
      },
      {
        "punto": "RESP: Diseñar, desarrollar y probar agentes con Copilot Studio",
        "evidencia": "copilot-studio/ (instrucciones, temas, escalamiento, guía de configuración, export) + 30 casos de prueba ejecutados en el chat de prueba + capturas."
      },
      {
        "punto": "RESP: Consultar, procesar y preparar datos con SQL y Microsoft Fabric",
        "evidencia": "Notebook PySpark que limpia y carga al lakehouse, tabla Delta, consultas en el SQL analytics endpoint, reporte Power BI."
      },
      {
        "punto": "RESP: Identificar procesos de negocio donde la IA agrega valor",
        "evidencia": "docs/business-case.md: proceso actual del service desk L1, cuellos de botella detectados con datos, oportunidades priorizadas por impacto y ahorro estimado en horas."
      },
      {
        "punto": "RESP: Documentar desarrollo, pruebas y resultados",
        "evidencia": "README, docs/architecture.md, docs/testing-procedure.md, resultados de evaluación, odd/tasks/deskpilot-ai.md con Log, CHANGELOG.md."
      },
      {
        "punto": "RESP: Programas y rutas de aprendizaje aplicados a proyectos reales",
        "evidencia": "docs/learning-log.md que conecta cada ruta de Microsoft Learn con la parte del proyecto donde se aplicó."
      }
    ],
    "entregables_extra_por_la_vacante": [
      "docs/job-fit.md: tabla 'Requisito/Responsabilidad de un AI Developer Trainee → evidencia en este repo (con links a archivos)'. Redactado de forma profesional y reutilizable para otras vacantes similares; menciona Microsoft Copilot Studio y Fabric como stack objetivo.",
      "docs/learning-log.md (plantilla lista; yo agrego mis rutas e insignias).",
      "CONTRIBUTING.md, .github/pull_request_template.md, .github/ISSUE_TEMPLATE/ y CHANGELOG.md.",
      "Cada tarea [CÓDIGO] se trabaja en su rama y se integra con PR vía 'gh pr create' + merge, para que el historial muestre flujo de equipo.",
      "README con una sección inicial 'Por qué este proyecto' en 3 líneas orientada a negocio, y una sección 'Habilidades demostradas' con badges: Copilot Studio, Microsoft Fabric, SQL, Python, RAG, AI Agents, Testing, Documentation."
    ],
    "prueba_final": "Antes de cerrar la Fase A, el subagente security-verifier hace también una revisión 'como reclutador': recorre la matriz de evidencia y reporta qué punto de la vacante quedó débil o sin evidencia, para corregirlo antes de entregarme el control."
  },
  "orden_de_trabajo": {
    "fase_A_automatica": "Todas las tareas [CÓDIGO], en orden de dependencias, delegadas a subagentes. El proyecto debe quedar 100% funcional en modo local (SQLite + ChromaDB, sin llaves de pago): datos generados, base de conocimiento, pipeline RAG, API + MCP, consultas SQL validadas localmente, tests y evaluación de los 30 casos corriendo, README, arquitectura, caso de negocio con cifras reales calculadas con el SQL sobre los datos locales, y todo el código del modo 'fabric' listo esperando solo credenciales.",
    "fase_B_preparacion_manual": "Antes de entregarme el control, el subagente docs-writer genera docs/MANUAL_STEPS.md: checklist numerado y en orden exacto de lo que me toca hacer (activar prueba de Fabric, crear workspace y lakehouse, subir CSV, correr notebook y SQL, llenar .env, exponer la API con una URL pública, crear el agente en Copilot Studio y conectarle la API, correr los 30 casos en el chat de prueba, Power BI, grabar video, tomar capturas). Cada paso con: dónde hacer clic, qué archivo del repo usar, qué copiar y pegar, cómo verificar que salió bien, y qué hacer si falla. Incluye scripts auxiliares donde ayuden (por ejemplo, verificar la conexión a Fabric, probar la URL pública, actualizar el README con mis resultados).",
    "fase_C_manual": "La hago yo siguiendo docs/MANUAL_STEPS.md. Al volver, te paso resultados y capturas, y tú (por subagentes) actualizas README, business-case y testing-procedure con la evidencia real, y haces el push final."
  },
  "proyecto": {
    "nombre_comercial": "DeskPilot AI",
    "tagline": "Agente L1 de Service Desk para banca con Copilot Studio, Microsoft Fabric y RAG",
    "nombre_repo": "deskpilot-ai",
    "ruta_local": "C:\\Users\\HP\\Proyectos\\deskpilot-ai",
    "descripcion_github": "AI L1 Service Desk agent for banking: Microsoft Copilot Studio + Microsoft Fabric (SQL/Lakehouse) + production-style RAG API (FastAPI, MCP). Tested, documented, with business case.",
    "topics_github": [
      "copilot-studio",
      "microsoft-fabric",
      "sql",
      "rag",
      "ai-agents",
      "mcp",
      "fastapi",
      "service-desk",
      "chromadb",
      "python"
    ],
    "pitch": "Agente L1 de service desk en Copilot Studio que resuelve incidencias repetitivas de empleados de un banco mexicano. Usa una API propia con un pipeline RAG de estilo producción (búsqueda de soluciones en la base de conocimiento) y herramientas para consultar y crear tickets almacenados en un lakehouse de Microsoft Fabric. Incluye analítica SQL, pruebas documentadas y un caso de negocio con ahorro estimado."
  },
  "metodologia": {
    "nombre": "Organic Driven Development (ODD)",
    "principio": "La ceremonia crece con el riesgo del cambio, no por costumbre. Primero se clasifica el pedido; la especificación es consecuencia del tamaño y del riesgo.",
    "protocolo_por_cada_pedido": [
      {
        "paso": 1,
        "nombre": "Autorizar",
        "regla": "Decide si el pedido permite cambios. Preguntas, revisiones y propuestas son de solo lectura: si te pido revisar algo, NO edites archivos."
      },
      {
        "paso": 2,
        "nombre": "Explorar",
        "regla": "Lee código y requisitos existentes en proporción a la tarea."
      },
      {
        "paso": 3,
        "nombre": "Resolver incertidumbre",
        "regla": "Investiga si hace falta. Máximo UNA pregunta enfocada por decisión real de producto y máximo UN cuestionamiento a una premisa riesgosa. Lo demás lo decides y lo registras en el Log."
      },
      {
        "paso": 4,
        "nombre": "Clasificar",
        "regla": "Pequeño o grande según entendimiento, riesgo y capacidad de retomarlo, nunca por número de archivos. Prueba del diff: si se puede retomar con el pedido original + git diff, es pequeño."
      },
      {
        "paso": 5,
        "nombre": "Registrar antes de escribir",
        "regla": "Si es grande, crea el documento de feature antes de cualquier línea de código y reporta en una línea cuántas tareas tiene."
      },
      {
        "paso": 6,
        "nombre": "Implementar tarea por tarea",
        "regla": "Test primero cuando haya test ejecutable y resultado esperado claro (RED → GREEN → REFACTOR). Commits de ~400 líneas cambiadas como máximo, registrados en Tasks."
      },
      {
        "paso": 7,
        "nombre": "Cerrar",
        "regla": "Reporta resultados verificados, chequeos fallidos o pendientes y siguiente paso. Nunca afirmes que algo funciona sin verificarlo."
      }
    ],
    "clasificacion_de_este_pedido": {
      "tamano": "GRANDE",
      "por_que": "Varias sesiones durante el fin de semana, esperas externas (pasos manuales en Copilot Studio y Fabric) y requisitos demasiado largos para sobrevivir a la compactación de contexto.",
      "riesgo_alto_en": [
        "Credenciales de Microsoft Fabric y de proveedores de LLM: riesgo de filtrar secretos al repo público",
        "Herramienta crear_ticket: escribe datos y clasifica prioridad"
      ],
      "escalamiento": "Las tareas [ALTO RIESGO] pasan por el subagente security-verifier, que revisa sin ver el razonamiento del implementador: busca secretos, datos sensibles y que los tests validen de verdad el requisito."
    },
    "documento_de_feature": {
      "ruta": "odd/tasks/deskpilot-ai.md",
      "secciones": {
        "## Specs": "Requisitos S1, S2… Cada uno CITA mis palabras literales (entre comillas) y debajo agrega criterios de aceptación verificables. No reformules mis palabras.",
        "## Tasks": "Una línea por tarea: 'T# [CÓDIGO|MANUAL] [ALTO RIESGO si aplica] descripción — subagente: <nombre> — cubre S# — commit: (vacío hasta hacerse)'. Tareas de 30–90 min, agrupadas en Fase A (Claude Code) y Fase C (Manual). Las [MANUAL] las hago yo y traen pasos claros.",
        "## Log": "L1 es MI PEDIDO ORIGINAL completo y sin editar (todo este JSON). Después L2, L3… con decisiones, respuestas, cambios de alcance y evidencia (salida de tests, capturas, links)."
      },
      "reglas": [
        "Los subagentes reciben la RUTA del documento de feature y el ID de su tarea, nunca un resumen.",
        "Si hay memoria persistente (Engram u otra), replica ahí el documento; si no, dilo explícitamente.",
        "El documento es la fuente de verdad para retomar el trabajo en otra sesión."
      ]
    }
  },
  "ejecucion_por_subagentes": {
    "regla_principal": "TODO se hace por subagentes, UNO A LA VEZ (secuencial, nunca en paralelo). Tú (agente principal) solo orquestas: lees y actualizas el documento de feature, asignas tareas, integras resultados, haces los commits y me reportas. No implementes código directamente en el contexto principal.",
    "como_delegar": [
      "Cada tarea T# se delega a UN subagente con: la ruta odd/tasks/deskpilot-ai.md, el ID de la tarea, los archivos que puede tocar y el criterio de terminado.",
      "UN SOLO SUBAGENTE A LA VEZ: nunca lances subagentes en paralelo. Espera a que uno termine, registra su resultado y luego lanza el siguiente. Esto es para controlar el consumo de tokens.",
      "Ahorro de tokens: pasa a cada subagente solo la ruta del documento de feature, el ID de su tarea y los archivos que puede tocar; pide reportes breves (archivos cambiados, tests, pendientes) sin pegar código completo ni logs largos; no releas archivos que no cambiaron.",
      "Cada subagente devuelve: archivos cambiados, comandos ejecutados, salida de tests y pendientes. Tú lo registras en el Log.",
      "Las tareas [ALTO RIESGO] terminan con una revisión del subagente security-verifier antes del commit."
    ],
    "subagentes_a_crear": {
      "ubicacion": ".claude/agents/ (subagentes de proyecto, versionados en el repo)",
      "formato": "Un archivo Markdown por subagente con frontmatter YAML: name, description (clara, para que sepas cuándo delegar), tools (mínimas necesarias) y system prompt.",
      "lista": [
        {
          "name": "repo-architect",
          "responsable_de": "Crear carpetas, archivos raíz, config.yaml, .gitignore, pyproject/requirements, CI de GitHub Actions y CLAUDE.md."
        },
        {
          "name": "data-engineer",
          "responsable_de": "Generador de tickets sintéticos, notebook PySpark para Fabric, 10 consultas SQL de negocio, modo local con SQLite."
        },
        {
          "name": "rag-engineer",
          "responsable_de": "src/ingestion, chunking, embeddings, vectordb, retrieval, prompts y llm: pipeline RAG sobre la base de conocimiento."
        },
        {
          "name": "api-engineer",
          "responsable_de": "src/api con FastAPI y servidor MCP: buscar_solucion (RAG), consultar_estado_ticket, crear_ticket, metricas_area; OpenAPI para Copilot Studio."
        },
        {
          "name": "copilot-studio-designer",
          "responsable_de": "Instrucciones del agente, temas, frases de activación, mensajes de escalamiento y guía paso a paso [MANUAL] para configurarlo en Copilot Studio."
        },
        {
          "name": "qa-tester",
          "responsable_de": "Tests unitarios e integración (pytest), 30 casos de prueba del agente, script de evaluación y docs/testing-procedure.md."
        },
        {
          "name": "docs-writer",
          "responsable_de": "README, arquitectura en Mermaid, caso de negocio con cifras salidas del SQL, docs/sources.md."
        },
        {
          "name": "security-verifier",
          "responsable_de": "Revisión independiente de tareas [ALTO RIESGO] y revisión de secretos antes de cada push. Solo lectura; no edita, reporta hallazgos."
        }
      ]
    }
  },
  "estructura_repo": {
    "fuente": "Estructura 'production-style RAG project' de una publicación de LinkedIn compartida por el usuario, adaptada a este proyecto. Ver docs/sources.md.",
    "arbol": {
      "archivos_raiz": {
        "README.md": "Guía de instalación, cómo correrlo, arquitectura, resultados y link al video.",
        "requirements.txt": "Dependencias de Python (puede convivir con pyproject.toml para ruff/pytest).",
        ".env": "Llaves y secretos LOCALES. NUNCA se sube a GitHub (en .gitignore).",
        ".env.example": "Plantilla de variables sin valores reales; esta sí se sube.",
        ".gitignore": "Ignora .env, .venv, __pycache__, logs/*.log, data/raw completa, data/vectordb, exports sensibles.",
        "config.yaml": "Modelos, tamaño de chunk, overlap, top_k, rutas, modo de datos (local|fabric), ajustes de BD.",
        "main.py": "Punto de entrada: levantar la API, indexar la base de conocimiento o correr evaluaciones por argumentos de CLI.",
        "LICENSE": "MIT.",
        "CLAUDE.md": "Reglas mínimas de ODD y del proyecto para Claude Code."
      },
      "src": {
        "ingestion/": "Carga de datos desde PDFs, Markdown, CSV y del lakehouse de Fabric.",
        "chunking/": "División de artículos en chunks por estructura (síntoma, causa, pasos, escalar) con metadatos.",
        "embeddings/": "Conversión de chunks a embeddings (modelo configurable; por defecto uno multilingüe local para no requerir llaves).",
        "vectordb/": "Operaciones sobre ChromaDB (local, persistente); interfaz que permita cambiar a FAISS u otro.",
        "retrieval/": "Búsqueda por similitud con top_k, filtros por categoría y umbral para responder 'no lo sé'.",
        "prompts/": "Plantillas de prompts versionadas (respuesta con cita, clasificación de ticket).",
        "llm/": "Cliente para Claude, OpenAI o Gemini, configurable por config.yaml y variables de entorno; modo sin LLM para tests.",
        "api/": "FastAPI + servidor MCP con las herramientas para Copilot Studio.",
        "utils/": "Logging, carga de config, helpers comunes."
      },
      "tests_logs": {
        "tests/": "Unitarios e integración (pytest) + casos de prueba del agente en CSV.",
        "logs/": "Logs de depuración y monitoreo (solo .gitkeep en el repo; los .log se ignoran)."
      },
      "carpetas_propias_del_proyecto": {
        "data/": "sample/ (200 filas que sí se suben), raw/ (CSV completo, ignorado), vectordb/ (ignorado).",
        "data-generator/": "Script de tickets sintéticos con semilla fija.",
        "knowledge-base/": "15 artículos Markdown de soporte bancario.",
        "fabric/": "notebooks/ (PySpark) y sql/ (10 consultas de negocio).",
        "copilot-studio/": "Instrucciones del agente, temas, guía de configuración y export de la solución si el entorno lo permite.",
        "docs/": "architecture.md, business-case.md, testing-procedure.md, sources.md, screenshots/.",
        "odd/tasks/": "Documento de feature de ODD.",
        ".claude/agents/": "Definiciones de los subagentes del proyecto.",
        ".github/workflows/": "ci.yml con lint y tests."
      }
    },
    "regla": "Cada carpeta de src/ tiene __init__.py y un README.md de 3 líneas explicando su responsabilidad. Las carpetas vacías al inicio llevan .gitkeep."
  },
  "contexto": {
    "yo": "Ingeniero en sistemas, recién egresado, con otros proyectos de portafolio. Windows, terminal y Claude Code. Todo en un repo público de GitHub.",
    "vacante": {
      "puesto": "AI Developer Trainee",
      "empresa": "Stefanini (consultora global de TI; fuerte en service desk, outsourcing y clientes de banca, retail, telecom e industria en México)",
      "modalidad": "Remoto, México",
      "requisitos": [
        "Recién egresado o menos de 1 año de experiencia",
        "Conocimientos básicos de programación, razonamiento lógico y manejo de datos",
        "SQL básico",
        "Interés demostrado en IA y desarrollo de agentes mediante proyectos"
      ],
      "responsabilidades": [
        "Diseñar, desarrollar y probar agentes de IA con Microsoft Copilot Studio",
        "Consultar, procesar y preparar datos con SQL y Microsoft Fabric",
        "Identificar procesos de negocio donde la IA agregue valor",
        "Documentar desarrollo, procedimientos de prueba y resultados",
        "Participar en programas y rutas de aprendizaje"
      ]
    },
    "regla_de_oro": "Cada spec debe ser evidencia de una responsabilidad de la vacante. Lo que no suma va a 'fuera de alcance' en el Log."
  },
  "componentes": [
    {
      "id": "C1",
      "nombre": "Datos sintéticos",
      "subagente": "data-engineer",
      "tipo": "CÓDIGO",
      "detalle": "5,000 tickets con semilla fija. Campos: ticket_id, fecha_apertura, fecha_cierre, categoria, subcategoria, prioridad, sucursal (ciudades de México), area, canal, sla_horas, sla_cumplido, solucion, es_repetitivo, idioma. Patrones: ~40% en 5 tipos repetitivos, picos de bloqueo en quincena, peor SLA en sucursales foráneas."
    },
    {
      "id": "C2",
      "nombre": "Base de conocimiento",
      "subagente": "docs-writer",
      "tipo": "CÓDIGO",
      "detalle": "15 artículos: reseteo de contraseña, desbloqueo de usuario, token bancario, VPN, impresoras, acceso a SAP, correo, carpetas compartidas, Teams, equipo lento, etc. Formato: síntoma, causa, pasos, cuándo escalar."
    },
    {
      "id": "C3",
      "nombre": "Microsoft Fabric",
      "subagente": "data-engineer",
      "tipo": "MIXTO",
      "detalle": "[MANUAL] activar prueba, crear workspace y lakehouse, subir CSV. [CÓDIGO] notebook PySpark a tabla Delta; 10 consultas SQL comentadas (top incidencias, % SLA por área y sucursal, horas perdidas, tickets automatizables, tendencia mensual)."
    },
    {
      "id": "C4",
      "nombre": "Pipeline RAG",
      "subagente": "rag-engineer",
      "tipo": "CÓDIGO",
      "detalle": "ingestion → chunking → embeddings → ChromaDB → retrieval con umbral → prompt con cita → llm. Respuesta siempre con el artículo fuente; 'no lo sé, escalo a un agente humano' si no hay evidencia."
    },
    {
      "id": "C5",
      "nombre": "API + MCP",
      "subagente": "api-engineer",
      "tipo": "CÓDIGO",
      "riesgo": "ALTO",
      "detalle": "Herramientas: buscar_solucion (RAG), consultar_estado_ticket, crear_ticket (clasifica categoría y prioridad), metricas_area. Modos 'local' (SQLite + Chroma) y 'fabric' (SQL endpoint por variables de entorno). OpenAPI listo para conectarse en Copilot Studio."
    },
    {
      "id": "C6",
      "nombre": "Agente en Copilot Studio",
      "subagente": "copilot-studio-designer",
      "tipo": "MIXTO",
      "detalle": "[CÓDIGO] instrucciones, temas, frases y escalamiento. [MANUAL] crear agente, cargar base de conocimiento, conectar la API/MCP como herramienta, probar y exportar si se puede. Bilingüe español/inglés."
    },
    {
      "id": "C7",
      "nombre": "Pruebas",
      "subagente": "qa-tester",
      "tipo": "CÓDIGO",
      "detalle": "pytest (test primero), 30 casos del agente en CSV (pregunta, intención, esperado, obtenido, pasó/falló, notas), script de evaluación y procedimiento documentado."
    },
    {
      "id": "C8",
      "nombre": "Documentación y caso de negocio",
      "subagente": "docs-writer",
      "tipo": "CÓDIGO",
      "detalle": "README (español + resumen en inglés), arquitectura Mermaid, business-case.md con cifras del SQL (porcentaje repetitivo, contención estimada, horas ahorradas al mes), sources.md."
    },
    {
      "id": "C9",
      "nombre": "Dashboard y demo",
      "subagente": "ninguno",
      "tipo": "MANUAL",
      "detalle": "Reporte de Power BI con KPIs y video demo de 2–3 minutos (YouTube no listado o Loom) enlazado en el README."
    }
  ],
  "fuentes": {
    "instruccion": "Guarda TODAS estas fuentes en docs/sources.md (título, URL, para qué se usó) y menciónalas en el Log. Agrega ahí cualquier fuente nueva que consulten los subagentes.",
    "lista": [
      {
        "titulo": "Estructura de repo 'production-style RAG project' (publicación de LinkedIn compartida por el usuario)",
        "url": "No disponible (texto pegado por el usuario)",
        "uso": "Estructura de carpetas raíz, src/, tests/, logs/ y main.py"
      },
      {
        "titulo": "ODD vs SDD: Organic vs Spec Driven Development con IA (Web Reactiva)",
        "url": "https://www.webreactiva.com/blog/odd-vs-sdd",
        "uso": "Protocolo ODD de 7 pasos, documento de feature, prueba del diff, verificador independiente"
      },
      {
        "titulo": "Gentle-AI (Gentleman Programming)",
        "url": "https://github.com/Gentleman-Programming/gentle-ai",
        "uso": "Origen de ODD"
      },
      {
        "titulo": "Claude Code: Create custom subagents",
        "url": "https://code.claude.com/docs/en/sub-agents",
        "uso": "Definición de subagentes en .claude/agents/ con frontmatter YAML"
      },
      {
        "titulo": "Building effective agents (Anthropic)",
        "url": "https://www.anthropic.com/research/building-effective-agents",
        "uso": "Patrón orquestador-trabajadores y diseño de herramientas para agentes"
      },
      {
        "titulo": "Microsoft Fabric trial capacity (Microsoft Learn)",
        "url": "https://learn.microsoft.com/fabric/get-started/fabric-trial",
        "uso": "Prueba gratuita de 60 días de Fabric"
      },
      {
        "titulo": "Sign up for a Copilot Studio trial (Microsoft Learn)",
        "url": "https://learn.microsoft.com/microsoft-copilot-studio/sign-up-individual",
        "uso": "Prueba de Copilot Studio y sus limitaciones"
      },
      {
        "titulo": "Model Context Protocol specification",
        "url": "https://modelcontextprotocol.io/specification/latest",
        "uso": "Servidor MCP con herramientas"
      },
      {
        "titulo": "Lewis et al. 2020, Retrieval-Augmented Generation",
        "url": "https://arxiv.org/abs/2005.11401",
        "uso": "Fundamento del pipeline RAG"
      }
    ]
  },
  "restricciones": {
    "tiempo": "Ya es sábado por la tarde. Ordena Tasks en dos grupos: 'Fase A: Claude Code (automática)' con todas las [CÓDIGO] y 'Fase C: Manual (usuario)' con todas las [MANUAL]. Mi parte manual debe caber en ~6 horas del domingo.",
    "alcance_minimo_viable": "Si falta tiempo: C1 + C2 + C3 (SQL) + C4 + C5 solo con buscar_solucion + C6 + C7 + C8. crear_ticket, MCP y Power BI pasan a 'siguientes pasos' en el Log.",
    "plataforma": "Windows. Comandos para PowerShell o CMD. Python 3.11+ con uv o venv.",
    "limitaciones_conocidas": [
      "Claude Code no puede manejar las interfaces web de Copilot Studio ni de Fabric: esas tareas son [MANUAL] con instrucciones paso a paso para mí.",
      "La prueba de Copilot Studio requiere cuenta de trabajo o escuela y no permite publicar; el video es la evidencia principal.",
      "La prueba de Fabric dura 60 días; el proyecto debe correr también en modo local sin llaves de pago."
    ],
    "seguridad": [
      "Cero secretos en el repo: .env local ignorado y .env.example versionado.",
      "Revisión de secretos por security-verifier antes de cada push.",
      "Todos los datos son sintéticos; nada de datos reales de bancos ni de Stefanini."
    ],
    "calidad": [
      "Python tipado, Pydantic, ruff, pytest.",
      "GitHub Actions con lint y tests en cada push.",
      "Commits de ~400 líneas máximo, conventional commits, en inglés, registrados en Tasks.",
      "Lo más simple que funcione; nada que no aporte a la vacante."
    ],
    "github": "Usa la CLI 'gh' (ya autenticada) para crear el repo público 'deskpilot-ai' con la descripción y topics de arriba, y hacer push."
  },
  "tareas_iniciales_obligatorias": [
    {
      "id": "T1",
      "subagente": "repo-architect",
      "descripcion": "Crear la carpeta C:\\Users\\HP\\Proyectos\\deskpilot-ai (crear también C:\\Users\\HP\\Proyectos si no existe) e inicializar git con rama main."
    },
    {
      "id": "T2",
      "subagente": "repo-architect",
      "descripcion": "Crear .claude/agents/ con los 8 subagentes definidos arriba."
    },
    {
      "id": "T3",
      "subagente": "repo-architect",
      "descripcion": "Crear la estructura completa del repo con archivos raíz, carpetas, __init__.py, .gitkeep y README de cada carpeta de src/."
    },
    {
      "id": "T4",
      "subagente": "docs-writer",
      "descripcion": "Crear CLAUDE.md con reglas mínimas de ODD y la regla de 'todo por subagentes', y docs/sources.md con todas las fuentes."
    },
    {
      "id": "T5",
      "subagente": "orquestador (tú)",
      "descripcion": "Crear odd/tasks/deskpilot-ai.md con Specs, Tasks (todas las del proyecto, agrupadas en Fase A y Fase C, con subagente asignado) y Log (L1 = este JSON completo)."
    },
    {
      "id": "T6",
      "subagente": "security-verifier",
      "descripcion": "Revisar que no haya secretos y que .gitignore cubra .env, data/raw, data/vectordb y logs."
    },
    {
      "id": "T7",
      "subagente": "orquestador (tú)",
      "descripcion": "Commit 'chore: scaffold project structure, subagents and ODD feature doc', crear repo público con gh y push."
    },
    {
      "id": "T8+",
      "subagente": "según componente",
      "descripcion": "Continúa SIN detenerte con todas las tareas [CÓDIGO] del documento de feature, una por subagente, commit por tarea, hasta cerrar la Fase A. Luego genera docs/MANUAL_STEPS.md (Fase B), corre la suite completa, revisión final de security-verifier y push."
    }
  ],
  "formato_de_trabajo": {
    "idioma": "Español para documentos y conversación; código y commits en inglés.",
    "interaccion": [
      "Empieza con la línea de clasificación 'GRANDE — N tareas — motivo' y, en máximo 5 líneas, lo que entendiste.",
      "Ejecuta T1–T7 y continúa directo con todas las tareas [CÓDIGO] delegando a subagentes. No me pidas aprobación entre tareas ni entre bloques.",
      "Muestra una línea de avance por tarea terminada: 'T# ✓ — subagente — commit'.",
      "Si una decisión de producto realmente bloquea, haz una sola pregunta con tu opción recomendada; si no bloquea, decide y regístralo en el Log.",
      "Si algo falla, el subagente lo corrige y reintenta; si tras 2 intentos sigue fallando, regístralo como pendiente y sigue con lo demás.",
      "Al terminar la Fase A y B, entrégame: árbol del repo, resultados de tests y de los 30 casos en modo local, link del repo en GitHub, y la ruta a docs/MANUAL_STEPS.md. Ahí entro yo."
    ],
    "criterio_de_exito_global": "Un reclutador de Stefanini abre el repo y en 2 minutos entiende el problema de negocio, ve el agente funcionando en el video, ve SQL sobre Fabric, ve un pipeline RAG limpio y ordenado, pruebas documentadas y un caso de negocio con números."
  }
}
```

### L2 — Ajustes obligatorios del usuario (sin editar)

Mensaje 1:

```text
go, con estos ajustes obligatorios (registralos en el Log como L2):

1. BASE DEL REPO PRIMERO, LUEGO TODO POR PR
- T1–T6: arma la base del repo en local en C:\Users\HP\Proyectos\deskpilot-ai (estructura de carpetas, archivos raíz, config, CI, plantillas, CLAUDE.md, .claude/agents/, docs/sources.md, doc ODD). Sin código de lógica todavía.
- Antes de subir: verifica que la base esté limpia y ordenada (git status limpio, árbol revisado por security-verifier, sin archivos sobrantes ni secretos).
- T7: commit de la base a main, gh repo create público con descripción y topics, y push. Main queda solo con la base.
- Desde T8, TODO el código, tests y docs entran por PR, uno por tarea:
  gh issue create (objetivo, criterios de aceptación, spec S# que cubre)
  → rama feat/tNN-nombre
  → commits ≤400 líneas, conventional commits en inglés
  → tests de la tarea pasando en local y CI verde
  → gh pr create con descripción completa usando la plantilla: Qué cambia, Por qué (S# y punto de la vacante que evidencia), Cómo se probó (comandos y resultados), Capturas o salida relevante, Checklist, "Closes #n"
  → gh pr merge --merge (conserva commits) y borra la rama.
- Nunca hagas push directo a main después de T7.

2. CERO DESORDEN EN ARCHIVOS
- Ningún archivo fuera de la estructura acordada. Nada temporal, duplicado ni de prueba en el repo.
- Lo experimental va en scratch/ (en .gitignore) y se borra al cerrar cada tarea.
- Cada PR solo toca los archivos de su tarea.

3. EL PROYECTO DEBE QUEDAR LISTO; YO SOLO HAGO LA PARTE MANUAL
- Pruebas unitarias de cada módulo de src/ y del generador de datos.
- Pruebas de integración: pipeline RAG completo (indexar → buscar → responder con cita / "no lo sé"), API completa con TestClient (4 herramientas, auth con API key, errores), servidor MCP y las 10 consultas SQL sobre SQLite.
- Prueba end-to-end local: genera datos → carga SQLite → indexa KB → levanta API → corre los 30 casos y guarda resultados.
- Cobertura con pytest-cov, meta ≥80% en src/. Todo verde antes de cerrar la Fase A.
- Mi parte se limita a Fabric, Copilot Studio, Power BI, video y capturas.

4. CERO ALUCINACIÓN
- Duda de todo lo que no hayas verificado. No inventes APIs, parámetros, flags, versiones ni pasos de interfaz.
- Si no sabes cómo funciona algo (fastembed, ChromaDB, FastMCP, conexión al SQL endpoint y Warehouse de Fabric, OpenAPI para Copilot Studio, dev tunnels), investiga primero en documentación oficial y anota la fuente en docs/sources.md.
- Verifica ejecutando: instala la versión real, corre el código y confirma la salida. Fija en requirements las versiones comprobadas.
- En MANUAL_STEPS.md cada paso de interfaz de Microsoft viene de documentación oficial con su link; lo que no puedas confirmar va marcado "⚠ verificar en pantalla".
- Lo que no se pueda verificar se reporta como tal; nunca como hecho.

Cuenta: usaré la de mi universidad. Si no funciona, agrega en MANUAL_STEPS.md alternativas para conseguir un tenant, sin depender del M365 Developer Program.
Nota visible en README y business-case.md: "Datos sintéticos generados para este proyecto; las cifras son ilustrativas".
No configures el badge de caveman.
```

Mensaje 2 (estructura obligatoria):

```text
REGLA: El repo respeta EXACTAMENTE la estructura "production-style RAG project" que te di (17 elementos, mismos nombres). Todo lo demás se acomoda DENTRO de esa estructura o en las pocas carpetas estándar de producción listadas abajo. Ninguna otra carpeta en la raíz.

deskpilot-ai/
│
│  # 1–5 ROOT FILES (de la estructura)
├── README.md              # setup, cómo correr, arquitectura, resultados, video
├── requirements.txt       # dependencias de producción con versiones verificadas y fijadas
├── .env                   # secretos locales, NUNCA se sube (en .gitignore)
├── .gitignore
├── config.yaml            # modelos, chunk_size, overlap, top_k, umbral, modo local|fabric, BD
│
│  # 6–14 SRC/ · THE RAG PIPELINE (de la estructura)
├── src/
│   ├── ingestion/         # carga de Markdown/PDF/CSV y del lakehouse de Fabric; generador de tickets sintéticos
│   ├── chunking/          # chunks por sección (síntoma/causa/pasos/escalar) con metadatos
│   ├── embeddings/        # fastembed multilingüe + embedder falso determinista para tests
│   ├── vectordb/          # operaciones ChromaDB detrás de una interfaz intercambiable
│   ├── retrieval/         # búsqueda por similitud, filtros, umbral de "no lo sé"
│   ├── prompts/           # plantillas versionadas (respuesta con cita, clasificación de ticket)
│   ├── llm/               # cliente none/Claude/OpenAI/Gemini según config.yaml + .env
│   ├── api/               # FastAPI + servidor MCP: buscar_solucion, consultar_estado_ticket, crear_ticket, metricas_area
│   └── utils/             # config validada con Pydantic, logging estructurado, helpers, conexión SQLite/Fabric
│
│  # 15–17 TEST · LOG · RUN (de la estructura)
├── tests/
│   ├── unit/              # un archivo por módulo de src/
│   ├── integration/       # pipeline RAG completo, API con TestClient, MCP, 10 SQL sobre SQLite
│   ├── e2e/               # main.py de punta a punta en modo local
│   └── eval/              # 30 casos del agente (CSV) + resultados
├── logs/                  # solo .gitkeep en el repo; los .log se ignoran
├── main.py                # CLI: generate-data | load-db | index | serve | eval | export-openapi
│
│  # ESTÁNDAR DE PRODUCCIÓN (únicas carpetas extra permitidas en la raíz)
├── data/
│   ├── knowledge_base/    # 15 artículos .md
│   ├── sample/            # 200 tickets (sí se sube)
│   ├── raw/               # CSV completo (ignorado)
│   └── vectordb/          # índice Chroma (ignorado)
├── integrations/
│   ├── fabric/            # notebooks/ (PySpark) y sql/ (10 consultas comentadas + DDL del Warehouse)
│   └── copilot_studio/    # instrucciones, temas, frases, openapi.yaml compatible, export de la solución
├── docs/                  # architecture.md, business-case.md, testing-procedure.md, MANUAL_STEPS.md,
│   │                      # job-fit.md, learning-log.md, sources.md, adr/, screenshots/
│   └── odd/               # deskpilot-ai.md (documento de feature ODD)
├── scripts/               # check_fabric.py, check_public_url.py, update_readme_results.py
├── .github/               # workflows/ci.yml, pull_request_template.md, ISSUE_TEMPLATE/
├── .claude/agents/        # 8 subagentes
│
│  # ARCHIVOS RAÍZ ESTÁNDAR DE PRODUCCIÓN
├── .env.example           # plantilla sin valores reales
├── requirements-dev.txt   # pytest, pytest-cov, ruff, mypy
├── pyproject.toml         # SOLO configuración de herramientas (ruff, pytest, mypy, coverage); las dependencias viven en requirements*.txt
├── Dockerfile             # imagen de la API lista para desplegar
├── .dockerignore
├── LICENSE                # MIT
├── CHANGELOG.md
├── CONTRIBUTING.md
└── CLAUDE.md

NIVEL PRODUCCIÓN (criterios que debe cumplir el código):
- Config: config.yaml + variables de entorno, validadas con Pydantic al arrancar; falla rápido con mensaje claro si falta algo.
- Logging estructurado (JSON) a consola y a logs/, con request_id por petición. Nunca registra secretos ni datos personales.
- API: endpoint /health, auth con header X-API-Key, validación estricta de entradas, manejo global de errores con respuestas consistentes, timeouts, límites de longitud.
- Separación clara: la indexación (ingestion → vectordb) nunca corre dentro de una petición de la API.
- Interfaces intercambiables (vectordb, llm, repositorio local/fabric) con inyección de dependencias, para poder testear con fakes.
- Tipado completo; ruff y mypy sin errores; cobertura ≥80% en src/.
- Dockerfile funcional: la API levanta en modo local dentro del contenedor (verifícalo con docker build y run si Docker está instalado; si no, márcalo como pendiente verificado en el Log, no lo des por hecho).
- Cada carpeta de src/ con __init__.py y README.md de 3 líneas sobre su responsabilidad.

Actualiza el documento ODD (Specs y Tasks) y docs/sources.md con esta estructura antes de seguir. La base (T1–T7) se arma con esta estructura exacta, se revisa y se sube; después todo entra por PR como acordamos.
```

Mensaje 3 (texto de la publicación de LinkedIn que define la estructura):

```text
Most RAG demos work. Most RAG repos are a mess.
Here is a clean, production-style RAG project structure, folder by folder 👇
ROOT FILES
1. README.md — setup guide, how to run, architecture.
2. requirements.txt — all Python dependencies.
3. env — API keys and secrets (never push to GitHub).
4. gitignore — what Git should ignore.
5. config.yaml — models, chunk size, DB settings.
SRC/ · THE RAG PIPELINE
6. ingestion/ — load data from PDFs, CSVs, websites.
7. chunking/ — split text into small chunks.
8. embeddings/ — turn chunks into embeddings.
9. vectordb/ — ChromaDB, Pinecone or FAISS operations.
10. retrieval/ — find relevant chunks with similarity search.
11. prompts/ — store prompt templates.
12. llm/ — OpenAI, Claude or Gemini calls.
13. api/ — FastAPI or Flask endpoints.
14. utils/ — helper functions and common utilities.
TEST · LOG · RUN
15. tests/ — unit and integration tests.
16. logs/ — debugging and monitoring.
17. main.py — entry point of the application.
```

Instrucción adicional del usuario: "NO PARES HASTA TERMINAR".

### L3 — Decisiones del orquestador (no bloqueantes)

- **Rutas:** la estructura de L2 reemplaza a la de L1. Equivalencias: `odd/tasks/` → `docs/odd/`; `data-generator/` → `src/ingestion/`; `knowledge-base/` → `data/knowledge_base/`; `fabric/` → `integrations/fabric/`; `copilot-studio/` → `integrations/copilot_studio/`.
- **Orden:** T5 (este documento) se ejecuta antes que T1–T4, por ODD paso 5 y para que los subagentes reciban la ruta del documento.
- **Entorno verificado (2026-11-21):** Python 3.13.2, sin `uv` ⇒ se usa `venv` (`.venv/`, ignorado). Git 2.51.0, gh 2.89.0 autenticado, Docker 29.0.1 disponible ⇒ la verificación del Dockerfile es obligatoria.
- **Subagentes:** los archivos de `.claude/agents/` se crean en una carpeta distinta al directorio de arranque de la sesión, así que Claude Code no los registra como tipos. Se usa el agente `general-purpose` con la instrucción "lee `.claude/agents/<rol>.md` y actúa con ese rol". El resultado es equivalente.
- **Commits:** el orquestador crea issue y rama. El subagente implementa y hace los commits (≤400 líneas, conventional, en inglés) en esa rama y deja el cuerpo del PR en `scratch/pr-body.md`. El orquestador hace push, crea el PR, espera el CI, hace el merge (`--merge --delete-branch`) y borra `scratch/`.
- **Actualización de este documento:** como main no admite push directo después de T7, el resultado de la tarea N (commit/PR en Tasks y la entrada del Log) entra como commit `docs(odd): ...` en la rama de la tarea N+1. La última actualización entra en T27.
- **Premisa corregida:** el SQL analytics endpoint del lakehouse es de solo lectura (⚠ confirmar en docs oficiales en T11). `crear_ticket` en modo fabric escribe en un Fabric Warehouse (`dbo.tickets_nuevos`) del mismo workspace.
- **Embeddings:** fastembed con un modelo multilingüe (⚠ confirmar en T14 que el modelo está soportado). Los tests y el CI usan un embedder falso determinista.
- **LLM por defecto `none`:** respuesta extractiva con plantilla y cita. Claude, OpenAI y Gemini se activan por `.env`.
- **SQL portable:** el generador precalcula `horas_resolucion` y `anio_mes`, y no se usan TOP ni LIMIT. Los mismos `.sql` corren en SQLite y en T-SQL.
- **JOIN:** dimensión `sucursales` (ciudad, región, es_foranea) generada junto con los tickets.
- **Cuenta:** el usuario usará su cuenta universitaria. MANUAL_STEPS.md incluirá alternativas de tenant sin el M365 Developer Program.
- **Memoria persistente:** no hay Engram. La memoria local de Claude Code guarda solo un puntero a este documento; el contenido no se replica, este archivo es la fuente de verdad.
- **Fuera de alcance:** badge de statusline de caveman (el usuario lo pidió explícitamente).

### L4 — Documento de requerimientos del usuario

El usuario entregó el documento de requerimientos v1.0 con la indicación literal "guarda este documento en el repo". Se guardó sin cambios en `docs/requirements.md` y queda como normativo (S23). Cada tarea debe leer las secciones que le tocan. Trazabilidad:

| Requerimiento | Tarea(s) |
| --- | --- |
| RF-01–RF-09, RNF-12, HU-01–HU-04 | T20 (diseño del agente), T21 (casos de evaluación), T33 (manual) |
| RF-10, RN-05, HU-05 | T17 (detecta y redacta datos sensibles en crear_ticket y logs), T20, T21 |
| RF-11, RF-12 | T13, T14, T15 |
| RF-13, RN-04, RF-14 | T15 |
| RF-15, HU-08 | T14 (reindexar sin detener la API; ⚠ verificar comportamiento de Chroma con dos procesos) |
| RF-16, RN-01, RN-02, RN-03 | T17 |
| RF-17, RF-19, RF-26 | T16 |
| RF-18 | T11 (conexión Fabric), T16 (lectura), T17 (escritura en Warehouse) |
| RF-20, RN-06, HU-06, HU-07 | T10 (las 10 consultas que lista RF-20) |
| RF-21 | T34 (manual) |
| RF-22 + patrones de la sección 11 (incluye `estado` y ~10% en inglés) | T9 |
| RF-23 | T11 |
| RF-24 | T8–T21 (cada tarea agrega su comando a main.py) |
| RF-25 | T19 |
| RNF-01 | T21 (medición de p95 en e2e) |
| RNF-02–RNF-06 | T16, T17 |
| RNF-07 | T8 |
| RNF-08, RNF-09 | T22 |
| RNF-10 | T19 |
| RNF-11 | T3, T9 |
| RNF-13 | T24 |
| Sección 12 (métricas) | T21 |
| Nombre ficticio "Banco Altiplano" | T12, T20, T23, T24 |

### L5 — Resultados T1–T5 (base)

- **T5** (orquestador): este documento y `docs/requirements.md`.
- **T1+T2** (repo-architect): `git init -b main` (user.name y email de la config global) y 8 subagentes en `.claude/agents/`, con frontmatter `name`/`description`/`tools` verificado en https://code.claude.com/docs/en/sub-agents. security-verifier es de solo lectura y reporta sus hallazgos en la respuesta, no en `scratch/`.
- **T3** (repo-architect): estructura base de L2. Versiones fijadas (`pip freeze`, Python 3.13.2): fastapi 0.165.0, uvicorn 0.54.0, pydantic 2.14.4, pydantic-settings 2.16.3, PyYAML 6.0.4, httpx 0.28.1, chromadb 1.5.9, fastembed 0.9.1, mcp 2.3.0, pypdf 7.1.1, pyodbc 5.5.0, azure-identity 1.27.0, anthropic 2.12.0, openai 3.57.0, google-genai 3.6.1. Dev: pytest 9.2.0, pytest-cov 7.1.0, ruff 0.17.6, mypy 2.4.1. CI usa actions/checkout@v7 y setup-python@v7. Verificación local: ruff check y format OK, mypy strict OK, pytest 8 passed con 100% de cobertura (`skip_empty`). Pendientes: el modelo de fastembed no se ha descargado (T14); pyodbc necesita unixODBC en Linux (T11).
- **T4** (docs-writer): `CLAUDE.md` y `docs/sources.md`. Las 8 URLs de L1 responden. Notas: la URL del trial de Fabric tiene forma canónica nueva, la de Copilot Studio sign-up redirige a "requirements-licensing-subscriptions" y la de la spec de MCP "latest" apunta a la revisión 2026-07-28.
- **Hallazgos para tareas siguientes (verificados en docs):** las REST API tools de Copilot Studio piden OpenAPI v2 en JSON (una v3 se traduce sola), lo que afecta T19. El Warehouse de Fabric solo acepta autenticación Microsoft Entra ID, lo que afecta T11.

### L6 — T6 revisión de la base y T7 publicación

- **T6** (security-verifier): **APROBADO**. Árbol conforme a S1/L2 (62 archivos), sin secretos y `.gitignore` completo; el CI usa `permissions: contents: read` y no usa `pull_request_target`. Hallazgos: (1, media) el `user.email` global es el correo universitario y quedaría público para siempre en la historia; (2, baja) `.gitignore` no cubría variantes como `.env.local`.
- **Correcciones del orquestador:** (2) se agregaron `.env.*` y `!.env.example` y se verificó con `git check-ignore`. (1) Decisión no bloqueante: `user.email` local del repo = correo noreply de GitHub. Evita publicar el correo personal y mantiene los commits ligados a la cuenta. Se puede cambiar con `git config user.email`.
- **T7:** commit de la base en main, repo público con `gh repo create` y push. Desde aquí, todo entra por PR.

- **T7** ✓ `7376681`: https://github.com/LuisFernandoAparicio21/deskpilot-ai (público, 10 topics). CI de main verde (run 44956376221).

### L7 — T8 utils (repo-architect) · PR #2 · merge b7e8196
- `src/utils/config.py` (Pydantic + pydantic-settings, fail-fast), `logging.py` (JSON, request_id ContextVar, rotación `deskpilot.N.log`), `redaction.py` (contraseña/NIP, tarjeta con Luhn, CURP, tokens). 90 tests, cobertura total 98.65%, ruff/mypy limpios; CI verde.
- Reglas agregadas: fallo al arrancar si `LLM_PROVIDER` ≠ none y falta su llave o su modelo; la API key debe tener ≥16 caracteres.
- No verificado: regex de CURP contra el instructivo oficial de RENAPO; no se valida el dígito verificador.

### L8 — T9 generador (data-engineer) · PR #4 · merge c4be8f4
- `src/ingestion/ticket_generator.py` + `ticket_catalog.py` (120 sucursales en 45 ciudades, de ellas 80 foráneas; 20 subcategorías, 15 con artículo de KB y 5 sin artículo). `main.py generate-data [--seed --n]`. Muestra sistemática de 1 de cada 25 filas en `data/sample/tickets_sample.csv`.
- Cifras reales (semilla 42): repetitivo 39.9%, desbloqueo en quincena 1.90×, SLA 85.8% en CDMX/Guadalajara/Monterrey vs 69.9% en foráneas (brecha 15.9 pp), inglés 9.6%, 14 abiertos. 127 tests, 99.10% de cobertura. Hash reproducible verificado.
- Nota: con `core.autocrlf` local la copia de trabajo puede tener CRLF; no afecta lo que se versiona (LF).

### L9 — T10 SQLite + SQL (data-engineer) · PR #6 · merge 941923b
- `src/utils/db.py`, `src/ingestion/sqlite_loader.py` (tablas tickets, sucursales y tickets_nuevos; `tickets_nuevos` = 17 columnas + descripcion), `main.py load-db [--run-sql]`, 10 consultas en `integrations/fabric/sql/` parseadas sin errores por sqlglot 30.33.0 como tsql y sqlite. 210 tests, 99.25% de cobertura.
- Corrección durante la revisión del orquestador: los automatizables daban 76.68% (el generador casi no escalaba a L2) ⇒ tasas de escalamiento por subcategoría (repetitivas 8–12%, resto con artículo 60–65%, sin artículo 70–85%, caja y fraude 100% por RN-03).
- Cifras finales (semilla 42): repetitivo 39.9%, automatizables 51.24% (2,562), quincena 1.90×, SLA 79.5% local vs 60.6% foránea (brecha 18.9 pp), inglés 9.6%.
- RN-06 implementado como: subcategoría con artículo de KB (CTE `kb`) + estado resuelto/cerrado + solución que no empieza con "Escalado a L2".
- Pendientes: (T11) flags como enteros 0/1 en Delta; (T29) la consulta 07 usa SUBSTRING(CAST(fecha_apertura AS VARCHAR(19)),9,2) — ⚠ verificar en Fabric que la columna llega como datetime2.

### L10 — T11 Fabric (data-engineer + security-verifier) · PR #8 · merge 6dc6c90
- `src/utils/fabric.py`: token de Entra ID (azure-identity) pasado por `attrs_before` (1256), sin secretos en la cadena de conexión; `ClientSecretCredential` si están las 3 variables AZURE_*, si no `DefaultAzureCredential`; validación fail-fast; imports perezosos. `integrations/fabric/sql/warehouse_ddl.sql` (varchar, datetime2(6), PK NONCLUSTERED NOT ENFORCED). Notebook `01_load_tickets_delta.ipynb` (flags como int 0/1). 269 tests, 99.34% de cobertura.
- Verificado en Microsoft Learn: el SQL analytics endpoint es de solo lectura y el Warehouse admite INSERT; solo Entra ID con ODBC 18; tipos del Warehouse. Local: ODBC Driver 17 y 18 instalados.
- ⚠ No verificado: scope `https://database.windows.net/.default` contra un tenant real (T30); ejecución del notebook en Spark (T29); DDL en el Warehouse (T29); precisión del datetime2 que expone Delta.
- security-verifier: **APROBADO**. Bajas: (#4) faltaba un assert de que el texto AADSTS no aparece en FabricAuthError → corregido por el orquestador (commit test(fabric)); (#3) en T16/T17, registrar los errores de Fabric sin `exc_info`.
- La unicidad de ticket_id en el Warehouse (PK NOT ENFORCED) la debe garantizar T17.

### L11 — T12 base de conocimiento (docs-writer) · PR #10
- 15 artículos `data/knowledge_base/KB-001…KB-015` (260–324 palabras): contraseña, desbloqueo, token, VPN, impresoras, SAP, core bancario, carpetas compartidas, equipo lento, escáner de cheques, sistema de caja, correo, Teams, telefonía, software. Front matter con palabras_clave ES/EN.
- RN-01 (prioridad sugerida), RN-03 (KB-011 caja y la sospecha de acceso no autorizado escalan siempre) y RN-05 (identidad por número de empleado, advertencia de no compartir) verificados por `tests/unit/test_knowledge_base.py`. 367 tests, 99.34% de cobertura.

### L12 — T13 ingestion + chunking (rag-engineer) · PR #12
- `src/ingestion/documents.py` (KBArticle; loaders de Markdown, PDF con pypdf 7.1.1 y CSV), `src/chunking/section_chunker.py` (chunk por sección, ids `KB-001#pasos#0`, subdivisión con overlap). La KB real da 64 chunks (sección más larga: 735 caracteres, menor que chunk_size 800). 420 tests, 100% de cobertura en los módulos nuevos.
- Decisión: el texto anterior al primer `##` se guarda como sección "introduccion", porque ahí están las advertencias de RN-05 (KB-001, 002, 003, 011). El orquestador la mantiene.

### L13 — T14 embeddings + vectordb (rag-engineer) · PR #14
- `src/embeddings` (Protocol, FakeEmbedder por hashing de tokens, FastEmbedEmbedder normalizado) y `src/vectordb` (Protocol, InMemory, Chroma coseno con `configuration={"hnsw":{"space":"cosine"}}`, similitud = clamp(1−d,0,1), índice versionado `data/vectordb/<ts>/` + puntero atómico `CURRENT` + poda que respeta índices abiertos en Windows). `main.py index`. 492 tests, 99.31% de cobertura. Test `slow` con el modelo real pasa en local.
- Verificado: modelo de 384 dimensiones, unos 241 MB, corta a 128 tokens. Index real: 15 artículos → 64 chunks en 66.7 s la primera vez (con descarga) y 4.2 s después. Concurrencia: la doc oficial de Chroma no la cubre y el Chroma Cookbook dice "not process-safe for concurrent writers" ⇒ diseño de versión nueva + puntero. Prueba real: un lector hizo 3841 consultas mientras otro proceso reindexaba, sin errores (RF-15).
- Similitudes: "se bloqueó mi usuario de Windows" → KB-002 0.683; "my VPN does not connect" → KB-004 0.814; dentro del dominio ≥0.57, fuera ≤0.16 ⇒ calibrar el umbral en T15.
- Caché del modelo en `data/vectordb/models` (ignorado). Pendientes: `CurrentStore.from_settings` en la API (T16), modelo en Docker (T19).

### L14 — T15 retrieval + prompts + LLM + respuesta (rag-engineer + security-verifier) · PR #16 · merge 309ee8e
- El subagente original murió por límite de uso (429) a mitad; el orquestador revisó la rama, la encontró coherente (retriever/prompts/llm commiteados, `answer_service` sin commit) y continuó desde ahí. Un test frágil (consulta con "password" sí recupera KB) se corrigió por el orquestador.
- Umbral calibrado con fastembed real: mínimo dentro del dominio 0.428, máximo fuera 0.236 ⇒ `retrieval.similarity_threshold: 0.33`. Modo extractivo por defecto; LLM opcional (none/Claude/OpenAI/Gemini).
- security-verifier: CHANGES REQUESTED (0 altos, 3 medios, 4 bajos) ⇒ todos corregidos: RN-03 ampliado con tests ±, KB-011 en cualquier posición escala, ids KB de la salida del LLM validados contra la evidencia, salida del LLM filtrada con `contains_sensitive`, `categoria` en lista blanca (ValueError), test de logs con centinela, timeouts de SDK verificados (son por fase, no totales; documentado).
- 602 tests, 99% cobertura, ruff/mypy limpios.
- Nueva directiva del usuario (ciclo por feature): a partir de T16 el ciclo por feature separa desarrollo (sin tocar tests/) y qa-tester independiente; roadmap en docs/roadmap.md; researcher antes de cualquier duda.

### L15 — T16 API REST (api-engineer + qa-tester + security-verifier) · PR #20 · merge 846d541
- Ciclo separado por directiva: api-engineer implementó sin tocar `tests/`, qa-tester escribió y ejecutó los tests de forma independiente y security-verifier revisó (ALTO RIESGO). FastAPI con `/health`, `buscar_solucion`, `consultar_estado_ticket`, `metricas_area`, X-API-Key, errores uniformes con `request_id`, límites de cuerpo y timeout, repo local/Fabric y `serve`. 828 tests, 98.80% de cobertura.
- Hallazgos del security-verifier M1, M2, B1 y B2 corregidos en ciclos de corrección (commits `fix(api)`, `feat(config)`); detalle en `docs/features/api-rest.md`. Fabric no probado contra tenant real (T30).

### L16 — T17 crear_ticket (api-engineer + qa-tester + security-verifier) · PR #22
- Mismo ciclo: api-engineer implementó `POST /tickets` (redacción de datos sensibles, clasificación por reglas con LLM opcional validado, SLA, persistencia en `tickets_nuevos`), qa-tester escribió 206 tests en 5 archivos y security-verifier dio **APROBADO** tras los ciclos de corrección. 1034 tests, 98.79% de cobertura.
- Hallazgos: M1 el LLM podía degradar un P1 de reglas (corregido: un P1 de reglas nunca cambia); M2 riesgo residual de unicidad de `ticket_id` en el Warehouse (PK NOT ENFORCED, ~1/900k por par concurrente), aceptado como riesgo conocido; baja: una contraseña sin separador no se redacta. Detalle en `docs/features/crear-ticket.md`.

### L17 — T18 servidor MCP (api-engineer + qa-tester + security-verifier) · PR #24
- Mismo ciclo: api-engineer implementó `python main.py mcp` (4 herramientas sobre la capa de servicio de la API; stdio por defecto, HTTP streamable con API key), qa-tester escribió 122 tests en 4 archivos y security-verifier dio **APROBADO**. Suite completa: 1156 tests, 98.72% de cobertura.
- QA encontró 3 bugs, corregidos: argumentos extra aceptados, eco de `categoria`/`canal` inválidos y mensaje de config que nombraba `serve`. Hallazgos bajos aceptados: símbolos privados de `app.py` y `_tool_manager` del SDK, `--host 0.0.0.0` sin aviso ni TLS, `X-API-Key` gana sobre Bearer, falta test de Host/Origin inválido.
- SDK `mcp` 2.3.0: `FastMCP` pasó a `MCPServer` (anotado en `docs/sources.md`). Verificado con clientes reales por stdio y HTTP (401 sin llave); `data/deskpilot.db` intacta. Detalle en `docs/features/mcp-server.md`.

### L18 — T18 cierre (api-engineer + qa-tester + security-verifier) · PR #24 mergeada
- security-verifier dio **APROBADO**. QA encontró 3 bugs, corregidos: argumentos extra aceptados, eco de `categoria`/`canal` inválidos y mensaje de config que nombraba `serve`. Mergeada el 2026-11-21 (commit de T18 = merge del PR #24). Detalle en L17.

### L19 — T19 export-openapi (api-engineer + qa-tester) · documentada
- `main.py export-openapi` genera Swagger 2.0 JSON para Copilot Studio; 1200 pruebas pasan, 1 omitida (validador externo opcional), cobertura 98.33%. Validado con `openapi-spec-validator` 0.9.0 en un venv temporal. Detalle en `docs/features/openapi-export.md`.
- **Incidencia de disco**: el disco C: se llenó al construir la imagen Docker. Se purgó el pip cache (6 GB) y Docker se moverá a D:, pendiente. El Dockerfile y `.dockerignore` se separaron como T19b (rama `feat/t19b-dockerfile`), sin verificar en Docker.
- **Limitación**: D: es lento y rompe 2 tests de concurrencia SQLite por el timeout de 5 s; no es un fallo de lógica.

### L20 — T19b Dockerfile (api-engineer + qa-tester) · PR #28 mergeada
- Docker verificado: `docker build` y `docker run` correctos, el contenedor corre sin root, funciona con `--network none` (modelo e índice ya en la imagen) y la imagen ocupa 1.47 GB en disco. Cierra la verificación que L19 dejó pendiente. Detalle en `docs/features/docker.md`.

### L21 — T20 diseño del agente Copilot Studio (copilot-studio-designer + qa-tester + docs-writer) · PR #30 mergeada
- `integrations/copilot_studio/`: instrucciones, 8 temas ES/EN, `tools.md`, `escalation.md` y 18 conversaciones de prueba (CT-01 a CT-18). El uso real en Copilot Studio es manual (T32); los pasos irán en `docs/MANUAL_STEPS.md` (T25, pendiente).
- QA encontró 6 frases de escalamiento no cubiertas por RN-03; se amplió la policy (`src/retrieval/policy.py`) y se añadieron pruebas. También se agregó el marcador "⚠ verificar en pantalla" para idiomas soportados.
- Límite conocido: en inglés "POS is not working" sin "terminal" no se detecta. Detalle en `docs/features/copilot-studio-agent.md`.

### L22 — T21 evaluación end-to-end (qa-tester + security-verifier + docs-writer) · documentada
- `main.py eval` con 30 casos (`tests/eval/cases.csv`), modo local y HTTP (aviso de tickets reales), métricas de la sección 12 y exit 0/1/2. Pruebas en `tests/unit/test_evaluation*.py`, `test_escalation_policy.py`, `tests/integration/test_escalation_by_article.py` y `tests/e2e/test_e2e.py`.
- **Ciclos de corrección**: (1) QA encontró sobre-escalamiento por KB-011 en cualquier posición (EV-05, EV-07, EV-09); se añadió `retrieval.escalation_margin` = 0.05. (2) EV-20 no escalaba; se detecta actividad de acceso no reconocida. (3) Patrones RN-03 de caja y acceso no autorizado ampliados (ES/EN). (4) security pidió avisar por stderr que `--api-url` crea tickets reales.
- **Métricas reales (local, índice real)**: 29/30 aprobados (96.7%), top-3 14/14, rechazo 3/4 (75%), clasificación 5/5, seguridad 3/3, p50 12.9 ms y p95 27.3 ms; `data/deskpilot.db` intacta (sha256 igual). Pytest: 1479 passed, 2 skipped, cobertura 98.24%; ruff y mypy limpios.
- **Decisión**: EV-16 (responde KB-003 con score 0.525 > umbral 0.33) se deja como limitación documentada (umbral global sin rerank) y xfail estricto, en lugar de subir el umbral y arriesgar casos legítimos. Por eso `eval` sale con 1. Detalle en `docs/features/eval-e2e.md` y `docs/testing-procedure.md`; los resultados en Copilot Studio son T32 (manual, pendiente).

### L23 — Estructura de docs/ (decisión)
- `docs/features/` y `docs/research/` se añaden a la estructura L2 por la directiva del usuario de ciclo por feature (un documento por feature y las investigaciones previas). Los `.md` de research ya estaban en `docs/research/` (no había nada que mover desde `docs/odd/`). Registrado en CLAUDE.md y CONTRIBUTING.md.

### L24 — T22 cobertura y CI (qa-tester + docs-writer) · documentada
- mypy sobre `src`, `main.py` y `tests` (`explicit_package_bases`); dos tests de integración renombrados (`test_api_create_ticket_flow.py`, `test_mcp_server_integration.py`); ResourceWarning de sqlite corregido; CI con jobs `quality`, `eval-smoke` (caché del modelo, acepta exit 1 por EV-16 y exige 30 casos con >=27 aprobados) y `docker-build` (buildx con caché gha).
- **Resultados reales (local)**: 1479 passed, 2 skipped, 33 deselected; cobertura 98.24%; ruff y mypy limpios. Los jobs nuevos de CI no se han ejecutado: ver resultado del PR. Limitación: ResourceWarning de anyio del cliente MCP. Detalle en `docs/features/coverage-ci.md`.

### L25 — T23 caso de negocio y ADRs (docs-writer) · documentada
- `docs/business-case.md` con cifras reales de las 10 consultas SQL (copia temporal de `data/deskpilot.db`, que no se modificó): repetitivo 39.92% (1,996), automatizable RN-06 51.24% (2,562; 88.53% dentro de las 5 repetitivas), quincena 1.90x, SLA 79.50% local contra 60.57% foráneo (brecha 18.93 pp), inglés 9.62%, backlog 16. Horas ahorradas al mes: 35.6 / 53.4 / 71.2 con 10 / 15 / 20 min por ticket, marcados SUPUESTO ILUSTRATIVO (no salen de los datos).
- Métricas de `main.py eval` leídas de `tests/eval/results.summary.json`: 29/30, top-3 14/14, rechazo 3/4 (EV-16), clasificación 5/5, seguridad 3/3, p50 13.8 ms y p95 31.5 ms (difiere del L22 por ser otra corrida).
- ADR-0001 a ADR-0008 en `docs/adr/` con README e índice. `ruff format` no procesa Markdown (no hay cambios que aplicar). Pendiente: la validación de las consultas en Fabric (T29) y las métricas en Copilot Studio (T33/T36).

### L26 — T24 README, arquitectura, job-fit y learning-log (docs-writer) · documentada
- README completo en español (badges de CI, Python 3.13, MIT y ruff, todos apuntando a recursos existentes; sin badge de cobertura porque no se genera), `docs/architecture.md` (componentes, consulta RAG, `crear_ticket`, despliegue), `docs/job-fit.md` (11 puntos de la matriz con estado honesto) y plantilla de `docs/learning-log.md` sin logros inventados. CHANGELOG y roadmap al día (T23 mergeada en el PR #36).
- **Resultados reales (local, 2026-11-22)**: pytest 1528 passed, 2 skipped, 33 deselected; cobertura 98.24%; eval 29/30 desde `tests/eval/results.summary.json`. Setup no repetido en un clon limpio (lo cubre `eval-smoke` del CI). Pendiente manual: Fabric real, Copilot Studio, Power BI, video y learning log (T28-T35); T25 sigue pendiente.

### L27 — T25 guía manual y scripts de Fase B (docs-writer) · documentada
- `docs/MANUAL_STEPS.md` (46 pasos numerados para T28 a T36, cuenta universitaria, alternativas de tenant sin M365 Developer Program, tabla "Si falla", tiempos), `scripts/check_fabric.py`, `scripts/check_public_url.py`, `scripts/update_readme_results.py` con 97 pruebas y `docs/research/` de Fabric, Copilot Studio, URL pública y Power BI. Commit de T24 = merge del PR #38.
- **3 bugs de los scripts corregidos**: (1) `check_fabric` imprimía texto crudo de excepciones (ahora tipo y SQLSTATE); (2) no restauraba `DESKPILOT_MODE`; (3) `update_readme_results` no validaba marcadores ni esquema del resumen (ahora sale con 2).
- **Resultados reales (local, 2026-11-22)**: pytest 1718 passed, 2 skipped, 33 deselected; cobertura de `src/` 98.24%; scripts 96% (97 pruebas); ruff y mypy limpios. Detalle en `docs/features/manual-steps-scripts.md`.
- **No verificado**: los scripts no se probaron contra un Fabric real ni contra una URL pública real (solo dobles de prueba); scope `database.windows.net/.default`, notebook en Spark, DDL en Warehouse y `datetime2` de la consulta 07 (T29/T30); subida de archivos como knowledge, MCP y clics no confirmados de Copilot Studio (marcados "⚠ verificar en pantalla").
