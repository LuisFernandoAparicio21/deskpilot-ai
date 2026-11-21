# DeskPilot AI · Documento de requerimientos

> **Escenario ficticio.** "Banco Altiplano" es un banco inventado para este proyecto. Todos los datos son sintéticos y las cifras son ilustrativas.

**Versión:** 1.0 · **Estado:** aprobado para desarrollo · **Metodología:** ODD (Organic Driven Development)

---

## 1. Contexto

Banco Altiplano tiene unos 6,000 empleados repartidos en 120 sucursales de México y en oficinas corporativas. Su mesa de servicio de TI (service desk) atiende cerca de 5,000 tickets al mes por portal, correo, teléfono y Teams. El nivel 1 (L1) lo opera un equipo de agentes humanos, en un modelo de outsourcing típico de consultoras como Stefanini.

## 2. Problema de negocio

1. **Volumen repetitivo.** Cerca del 40% de los tickets son de 5 tipos que se resuelven con pasos conocidos: contraseña, desbloqueo de usuario, token bancario, VPN e impresoras. Ocupan a los agentes L1 en trabajo sin valor agregado.
2. **Picos predecibles sin capacidad.** En quincena y cierre de mes suben los bloqueos de usuario y se rompe el SLA, justo cuando las sucursales más necesitan operar.
3. **SLA desigual.** Las sucursales foráneas tienen peor cumplimiento de SLA que las de CDMX, Guadalajara y Monterrey.
4. **Conocimiento disperso.** Las soluciones viven en documentos sueltos y en la cabeza de los agentes; cada agente resuelve distinto.
5. **Sin visibilidad.** La coordinación no tiene métricas confiables para saber qué automatizar primero ni cuánto se ahorraría.

**Impacto:** tiempo perdido de empleados de sucursal (que no pueden atender clientes), costo operativo del L1 y penalizaciones por incumplir SLA.

## 3. Objetivos de negocio (ilustrativos)

| ID | Objetivo | Meta |
| --- | --- | --- |
| OB-1 | Resolver sin agente humano los tickets L1 repetitivos | Contención ≥ 50% de los 5 tipos repetitivos |
| OB-2 | Reducir el tiempo de resolución de incidencias simples | De horas a minutos para casos con artículo en la base de conocimiento |
| OB-3 | Dar visibilidad para decidir qué automatizar | Dashboard con top incidencias, SLA por área y sucursal, horas perdidas |
| OB-4 | Estandarizar respuestas | 100% de respuestas del agente basadas en un artículo citado |
| OB-5 | Cuantificar el valor | Caso de negocio con horas ahorradas al mes calculadas con datos |

## 4. Usuarios e interesados

| Rol | Necesidad | Cómo lo usa |
| --- | --- | --- |
| Empleado de sucursal o corporativo | Resolver su problema rápido, en su idioma | Conversa con el agente en Copilot Studio |
| Agente L1 humano | Recibir solo lo que no se pudo automatizar, bien clasificado | Recibe tickets escalados con categoría y prioridad |
| Coordinador del service desk | Saber qué falla, dónde y cuánto cuesta | Dashboard de Power BI y consultas SQL |
| Administrador de TI | Mantener la base de conocimiento y la configuración | Edita artículos, reindexa, cambia config.yaml |
| Gerente de operaciones (cliente) | Ver el retorno de la inversión | Caso de negocio |

## 5. Alcance

**Dentro del alcance**
- Agente L1 conversacional en Microsoft Copilot Studio, bilingüe (español e inglés).
- Base de conocimiento de 15 artículos de soporte bancario.
- API con pipeline RAG y 4 herramientas: `buscar_solucion`, `consultar_estado_ticket`, `crear_ticket` y `metricas_area`; expuesta como REST (OpenAPI) y como servidor MCP.
- Datos de 5,000 tickets sintéticos en un lakehouse de Microsoft Fabric, con tickets nuevos en un Fabric Warehouse.
- 10 consultas SQL de negocio y un reporte de Power BI.
- Modo local completo (SQLite + ChromaDB) sin llaves de pago.
- Pruebas unitarias, de integración, end-to-end y 30 casos de evaluación del agente.
- Documentación técnica, procedimiento de pruebas y caso de negocio.

**Fuera del alcance**
- Integración con un ITSM real (ServiceNow, Jira Service Management).
- Autenticación de empleados con SSO en el agente.
- Acciones reales sobre sistemas, como resetear de verdad una contraseña en Active Directory. El agente guía al usuario y crea el ticket.
- Canal de voz.
- Publicación del agente en Teams (la prueba de Copilot Studio no lo permite).

## 6. Proceso actual vs propuesto

**Actual (AS-IS)**
1. El empleado levanta un ticket o llama.
2. Espera en cola a un agente L1.
3. El agente busca la solución en documentos sueltos y la explica.
4. Si no puede, escala a L2.
5. No queda registro estructurado de qué se pudo haber automatizado.

**Propuesto (TO-BE)**
1. El empleado describe su problema al agente.
2. El agente busca en la base de conocimiento (RAG) y responde con pasos y el artículo citado.
3. Si se resolvió, termina sin ticket o con uno cerrado de inmediato.
4. Si no hay evidencia suficiente o el usuario sigue con el problema, el agente lo dice, pide los datos mínimos, crea el ticket con categoría y prioridad, y devuelve el folio.
5. El empleado puede consultar después el estado con su folio.
6. Todo queda en Fabric para análisis.

## 7. Requerimientos funcionales

### 7.1 Agente conversacional (Copilot Studio)
- **RF-01** Responder en el idioma del usuario (español o inglés).
- **RF-02** Identificar la intención: resolver incidencia, consultar estado de ticket o hablar con un humano.
- **RF-03** Para incidencias, llamar a `buscar_solucion` y presentar los pasos de forma clara.
- **RF-04** Citar siempre el artículo fuente (título e ID).
- **RF-05** Si no hay evidencia suficiente, decir explícitamente que no tiene la respuesta y ofrecer crear un ticket. Nunca inventar pasos.
- **RF-06** Preguntar si la solución funcionó. Si no, ofrecer escalar.
- **RF-07** Para escalar, pedir solo los datos mínimos (área, sucursal, descripción) y llamar a `crear_ticket`.
- **RF-08** Para consultar estado, pedir el folio y llamar a `consultar_estado_ticket`.
- **RF-09** Si el usuario pide un humano, escalar sin insistir.
- **RF-10** No pedir ni aceptar contraseñas, NIP, tokens ni datos personales sensibles. Si el usuario los escribe, advertirle y no guardarlos.

### 7.2 Búsqueda de soluciones (RAG)
- **RF-11** Indexar los artículos de la base de conocimiento por secciones (síntoma, causa, pasos, cuándo escalar) con metadatos (ID, título, categoría, idioma).
- **RF-12** Recuperar los fragmentos más relevantes (top_k configurable) y filtrar por categoría cuando se conozca.
- **RF-13** Aplicar un umbral de similitud configurable. Debajo del umbral, la respuesta es "sin evidencia".
- **RF-14** Generar la respuesta en modo extractivo (sin LLM) por defecto, y con LLM (Claude, OpenAI o Gemini) si está configurado.
- **RF-15** Reindexar la base de conocimiento con un comando, sin detener la API.

### 7.3 Tickets
- **RF-16** `crear_ticket` valida la entrada, clasifica categoría y prioridad, calcula el SLA según la prioridad y devuelve folio, categoría, prioridad y SLA.
- **RF-17** `consultar_estado_ticket` devuelve estado, fechas, prioridad y SLA del folio; si no existe, lo dice sin revelar otros datos.
- **RF-18** En modo local, los tickets viven en SQLite. En modo fabric, se consultan en el lakehouse (solo lectura) y los nuevos se escriben en el Warehouse.

### 7.4 Métricas y análisis
- **RF-19** `metricas_area` devuelve, para un área o sucursal, el total de tickets, el % de SLA cumplido, el tiempo promedio de resolución y el top de categorías.
- **RF-20** 10 consultas SQL de negocio que corren igual en SQLite y en el SQL endpoint de Fabric, como mínimo: top incidencias, % SLA por área, % SLA por sucursal, horas perdidas por categoría, tickets automatizables, tendencia mensual, efecto de quincena, comparación local vs foránea, distribución por canal y backlog por prioridad.
- **RF-21** Reporte de Power BI con los KPIs principales.

### 7.5 Datos
- **RF-22** Generar 5,000 tickets sintéticos reproducibles (semilla fija) con los patrones del problema de negocio.
- **RF-23** Notebook PySpark que limpia los datos y los carga a una tabla Delta en el lakehouse.

### 7.6 Operación
- **RF-24** CLI única (`main.py`) con los comandos generate-data, load-db, index, serve, eval y export-openapi.
- **RF-25** Exportar un OpenAPI compatible con Copilot Studio.
- **RF-26** Endpoint `/health` con el estado de la API, la base de datos y el índice vectorial.

## 8. Requerimientos no funcionales

| ID | Categoría | Requerimiento |
| --- | --- | --- |
| RNF-01 | Rendimiento | `buscar_solucion` en modo local sin LLM responde en p95 < 1.5 s con la base de 15 artículos |
| RNF-02 | Seguridad | Toda la API exige el header `X-API-Key`; sin llave, responde 401 |
| RNF-03 | Seguridad | Cero secretos en el repositorio; configuración por `.env` y `.env.example` |
| RNF-04 | Seguridad | Validación estricta y límites de longitud en todas las entradas; pruebas de abuso en `crear_ticket` |
| RNF-05 | Privacidad | Los logs no contienen secretos ni datos personales; los datos del proyecto son 100% sintéticos |
| RNF-06 | Confiabilidad | Errores con respuestas consistentes (código, mensaje, request_id); timeouts en llamadas externas |
| RNF-07 | Observabilidad | Logging estructurado en JSON con request_id, a consola y a `logs/` |
| RNF-08 | Mantenibilidad | Estructura production-style RAG; interfaces intercambiables para vectordb, LLM y repositorio de datos |
| RNF-09 | Calidad | Tipado completo; ruff y mypy sin errores; cobertura ≥ 80% en `src/` |
| RNF-10 | Portabilidad | Corre en Windows y en Docker; modo local sin servicios de pago |
| RNF-11 | Reproducibilidad | Datos con semilla fija y dependencias con versiones fijadas |
| RNF-12 | Usabilidad | Respuestas del agente en pasos numerados y cortos; en español neutro de México |
| RNF-13 | Documentación | README con instalación en ≤ 5 minutos en modo local |

## 9. Historias de usuario

**HU-01 · Resolver una incidencia común**
Como empleado de sucursal, quiero que el agente me diga cómo desbloquear mi usuario, para volver a atender clientes sin esperar.
- Dado que escribo "se bloqueó mi usuario de Windows", cuando el agente responde, entonces me da pasos numerados y cita el artículo de desbloqueo.
- Dado que los pasos funcionaron, cuando confirmo, entonces el agente cierra la conversación sin crear ticket.

**HU-02 · Escalar cuando no hay solución**
Como empleado, quiero que el agente cree un ticket cuando no pueda ayudarme, para no tener que repetir mi problema por otro canal.
- Dado que mi problema no tiene artículo con evidencia suficiente, cuando lo describo, entonces el agente dice que no tiene la respuesta y ofrece crear un ticket.
- Dado que acepto, cuando doy área, sucursal y descripción, entonces recibo un folio con prioridad y SLA.

**HU-03 · Consultar estado**
Como empleado, quiero consultar mi ticket con el folio, para saber cuándo se resolverá.
- Dado un folio válido, cuando lo consulto, entonces veo estado, prioridad y SLA.
- Dado un folio inexistente, cuando lo consulto, entonces el agente lo dice sin mostrar otros tickets.

**HU-04 · Atención en inglés**
Como empleado extranjero del corporativo, quiero que el agente me responda en inglés.
- Dado que escribo en inglés, cuando el agente responde, entonces lo hace en inglés y con el mismo artículo citado.

**HU-05 · Protección de datos**
Como banco, quiero que el agente nunca pida ni guarde contraseñas o tokens.
- Dado que un usuario escribe su contraseña, cuando el agente responde, entonces le advierte que no debe compartirla y no la incluye en ningún ticket ni log.

**HU-06 · Decidir qué automatizar**
Como coordinador del service desk, quiero ver qué tipos de ticket consumen más horas, para priorizar la automatización.
- Dado el dashboard, cuando lo abro, entonces veo top categorías, horas perdidas y % de tickets automatizables.

**HU-07 · Ver SLA por sucursal**
Como coordinador, quiero comparar el cumplimiento de SLA entre sucursales locales y foráneas.
- Dado el reporte, cuando filtro por sucursal, entonces veo el % de SLA cumplido y la diferencia contra el promedio.

**HU-08 · Mantener la base de conocimiento**
Como administrador de TI, quiero agregar un artículo y reindexar sin tocar código.
- Dado un nuevo archivo `.md` en `data/knowledge_base/`, cuando ejecuto `python main.py index`, entonces el agente puede encontrarlo y citarlo.

## 10. Reglas de negocio

- **RN-01 Prioridad.** P1: afecta a una sucursal completa o a operación con clientes. P2: un usuario sin poder operar. P3: degradación con alternativa. P4: solicitud o duda.
- **RN-02 SLA (ilustrativo).** P1: 4 h · P2: 8 h · P3: 24 h · P4: 72 h.
- **RN-03 Escalamiento obligatorio.** Fraude, sospecha de acceso no autorizado y fallas en sistemas de caja se escalan siempre, sin intentar resolver.
- **RN-04 Evidencia.** El agente solo da pasos que vienen de un artículo recuperado sobre el umbral.
- **RN-05 Datos sensibles.** Contraseñas, NIP, tokens, números de tarjeta y CURP nunca se solicitan, almacenan ni registran.
- **RN-06 Repetitivo.** Un ticket es "automatizable" si su subcategoría tiene artículo en la base de conocimiento y se resolvió sin intervención de L2.

## 11. Datos

**Ticket:** `ticket_id`, `fecha_apertura`, `fecha_cierre`, `categoria`, `subcategoria`, `prioridad`, `sucursal`, `area`, `canal`, `sla_horas`, `sla_cumplido`, `horas_resolucion`, `anio_mes`, `solucion`, `es_repetitivo`, `idioma`, `estado`.

**Artículo de la base de conocimiento:** `id`, `titulo`, `categoria`, `idioma`, `sintoma`, `causa`, `pasos`, `cuando_escalar`, `fecha_actualizacion`.

**Patrones obligatorios del generador:** ~40% de tickets en 5 subcategorías repetitivas; picos de bloqueo de usuario los días 14–16 y 29–31; SLA peor en sucursales foráneas; mezcla de canales y ~10% de tickets en inglés.

## 12. Métricas de éxito del sistema

| Métrica | Cómo se mide | Meta |
| --- | --- | --- |
| Precisión de recuperación | Artículo correcto en top 3, sobre los 30 casos | ≥ 90% |
| Rechazo correcto | Casos sin respuesta donde el agente dice "no lo sé" | 100% |
| Clasificación de tickets | Categoría y prioridad correctas en casos de escalamiento | ≥ 85% |
| Seguridad | Casos con datos sensibles bien manejados | 100% |
| Casos de evaluación aprobados | 30 casos del agente | ≥ 27 de 30 |
| Calidad de código | Cobertura en `src/`, ruff y mypy | ≥ 80%, sin errores |

## 13. Supuestos y restricciones

- Se usan las pruebas gratuitas de Microsoft Fabric (60 días) y de Copilot Studio, con cuenta de trabajo o escuela.
- La prueba de Copilot Studio no permite publicar el agente; la evidencia es el chat de prueba, las capturas y el video.
- El desarrollo se hace en un fin de semana. Claude Code hace todo el código y el usuario hace los pasos manuales en las plataformas de Microsoft.
- Windows como entorno de desarrollo; Python 3.11+.

## 14. Riesgos y mitigaciones

| Riesgo | Impacto | Mitigación |
| --- | --- | --- |
| Sin cuenta de trabajo o escuela | No se puede hacer la parte de Microsoft | Usar la cuenta de la universidad; el modo local demuestra todo lo demás |
| Filtrar secretos al repo público | Alto | `.gitignore`, `.env.example` y revisión de security-verifier antes de cada push |
| El agente inventa pasos | Alto | Umbral de evidencia, respuesta extractiva por defecto, casos de prueba de rechazo |
| SQL endpoint de Fabric de solo lectura | `crear_ticket` falla en modo fabric | Tickets nuevos en Fabric Warehouse |
| Copilot Studio no acepta el OpenAPI | No se conecta la herramienta | Exportar OpenAPI 2.0/3.0 compatible; alternativa MCP |
| Falta de tiempo | Proyecto incompleto | MVP definido; MCP y Power BI pasan a siguientes pasos |

## 15. Criterios de aceptación del proyecto

- [ ] Todos los RF tienen al menos una tarea y una prueba en el documento ODD.
- [ ] Suite de pruebas verde (unitarias, integración, e2e) y cobertura ≥ 80% en `src/`.
- [ ] Los 30 casos de evaluación corren en local y en el chat de prueba de Copilot Studio, con resultados documentados.
- [ ] Las 10 consultas SQL corren en SQLite y en Fabric, con capturas.
- [ ] README permite correr el modo local en ≤ 5 minutos.
- [ ] Caso de negocio con cifras calculadas a partir del SQL y marcado como ilustrativo.
- [ ] Video demo de 2–3 minutos enlazado.
- [ ] Repo público sin secretos, con historial de PRs documentados.

## 16. Trazabilidad con la vacante (AI Developer Trainee)

| Responsabilidad de la vacante | Requerimientos que la evidencian |
| --- | --- |
| Diseñar, desarrollar y probar agentes con Copilot Studio | RF-01 a RF-10, HU-01 a HU-05, métricas de la sección 12 |
| Consultar, procesar y preparar datos con SQL y Microsoft Fabric | RF-18 a RF-23 |
| Identificar procesos de negocio donde la IA agrega valor | Secciones 2, 3 y 6; RN-06; HU-06 y HU-07 |
| Documentar desarrollo, pruebas y resultados | RNF-13, sección 15, `docs/` |
| Programas y rutas de aprendizaje | `docs/learning-log.md` |
