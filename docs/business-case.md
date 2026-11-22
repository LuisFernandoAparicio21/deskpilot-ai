# Caso de negocio · DeskPilot AI

> **Datos sintéticos generados para este proyecto; las cifras son ilustrativas.**
> "Banco Altiplano" es un banco ficticio. Ninguna cifra describe a una empresa real.

Cada cifra de este documento sale de una de las 10 consultas de `integrations/fabric/sql/`, ejecutadas sobre
SQLite con los 5,000 tickets sintéticos (semilla 42) en una copia temporal de `data/deskpilot.db`. Lo que no
sale de una consulta se marca como **SUPUESTO ILUSTRATIVO**. La tabla de trazabilidad (sección 10) lista cada
cifra con su consulta y su valor. Las mismas consultas se validarán en Microsoft Fabric en la Fase C (T29);
hasta entonces no hay cifras medidas en Fabric.

## 1. Contexto

Banco Altiplano (ficticio) tiene unos 6,000 empleados en 120 sucursales y oficinas corporativas. Su mesa de
servicio de TI atiende tickets por portal, correo, teléfono y Teams. El nivel 1 (L1) lo opera un equipo humano
en un modelo de outsourcing típico de consultoras de servicio (`docs/requirements.md`, sección 1).
Los datos del análisis cubren 12 meses, de 2025-11 a 2026-10 (`06_tendencia_mensual.sql`), unos 417 tickets al
mes en promedio (5,000 / 12, cálculo propio sobre el total de `01`).

## 2. Problema

1. **Volumen repetitivo.** Cinco subcategorías (reseteo de contraseña, desbloqueo de usuario, token bancario,
   impresoras y VPN) suman 1,996 tickets, el **39.92%** del total (`01_top_incidencias.sql`: 11.06 + 10.08 +
   7.34 + 5.78 + 5.66).
2. **Picos de quincena.** Los días 14-16 y 29-31 hay **2.30** desbloqueos de usuario por día contra **1.21**
   el resto: **1.90 veces** más (`07_efecto_quincena.sql`, columnas `desbloqueos_por_dia` y `veces_vs_resto`).
3. **SLA desigual.** Las sucursales locales (CDMX, Guadalajara y Monterrey) cumplen el SLA en **79.50%** de los
   tickets cerrados; las foráneas, en **60.57%**: una brecha de **18.93 pp** (`08_local_vs_foranea.sql`).
   La peor sucursal es Puebla 05 con 35.56% (`03_sla_por_sucursal.sql`, `posicion_peor` = 1).
4. **Conocimiento disperso y sin visibilidad.** Sin una base de conocimiento única, cada agente resuelve distinto
   y la coordinación no sabe qué automatizar primero (`docs/requirements.md`, sección 2).

## 3. Solución: DeskPilot AI

Un agente L1 en Microsoft Copilot Studio (español e inglés) que usa una API propia con pipeline RAG sobre 15
artículos de soporte. Las herramientas son `buscar_solucion`, `consultar_estado_ticket`, `crear_ticket` y
`metricas_area`, expuestas como REST (Swagger 2.0 para Copilot Studio) y como servidor MCP, sobre una sola capa
de servicio. Los tickets viven en un lakehouse de Microsoft Fabric (lectura) y los nuevos se escriben en un
Warehouse; el modo local (SQLite + ChromaDB) corre sin llaves de pago. Las decisiones de diseño están en
[`docs/adr/`](adr/README.md).

Qué hace el agente: responde con pasos y artículo citado (RN-04), dice "no lo sé" y ofrece ticket si no hay
evidencia, y escala sin intentar resolver fraude, acceso no autorizado y fallas de caja (RN-03).

## 4. Qué conviene automatizar (RN-06)

RN-06 define un ticket automatizable así: su subcategoría tiene artículo en la base de conocimiento y se
resolvió sin L2. La consulta `05_tickets_automatizables.sql` lo aplica (estado resuelto o cerrado y solución
que no empieza con "Escalado a L2").

| Hallazgo | Valor | Fuente |
| --- | --- | --- |
| Tickets automatizables | 2,562 de 5,000 = **51.24%** | `05` (suma de `tickets_automatizables`; suma de `pct_del_banco`) |
| Automatizables dentro de las 5 repetitivas | 1,767 de 1,996 = **88.53%** | `05` (504 + 460 + 321 + 246 + 236) sobre `01` (1,996) |
| Mejores subcategorías | Desbloqueo 91.27%, contraseña 91.14%, token 87.47%, impresoras 85.12%, VPN 83.39% | `05` (`pct_automatizable`) |
| Subcategorías sin artículo | 5 (alta de usuario, consulta general, equipo dañado, red de sucursal, sospecha de fraude), 689 tickets | `05` (`tiene_articulo` = 0) |
| Sistema de caja | 224 tickets con artículo, **0** automatizables | `05`: RN-03 obliga a escalar |

**Contención estimada.** Se define como la proporción de tickets que el agente podría resolver sin L2. El techo
teórico es el **51.24%** de `05`; no considera adopción ni errores del agente, por eso es un techo y no una
promesa. Para las 5 repetitivas llega a 88.53%, por encima de la meta OB-1 (50%, `docs/requirements.md`,
sección 3).

**Dónde está el tiempo.** Por categoría, Accesos concentra **31.54%** de las horas de resolución, Hardware
20.77% y Comunicaciones 18.78% (`04_horas_perdidas_por_categoria.sql`, `pct_horas`). Las horas de `04` son
tiempo transcurrido de resolución (suma de `horas_totales`: 114,540.35 h), no esfuerzo del agente.

**Top por volumen** (`01`): contraseña 553, desbloqueo 504, token 367, correo 328 y equipo lento 294; el top 5
acumula 40.92%. Correo y equipo lento no son repetitivas pero sí tienen artículo; por eso su automatización es
menor (41.16% y 39.80% en `05`).

## 5. Horas ahorradas al mes

La consulta `05` entrega los tickets automatizables; los minutos por ticket **no** están en los datos.

> **SUPUESTO ILUSTRATIVO.** Minutos de trabajo de un agente L1 por ticket de estos tipos: 10, 15 o 20 minutos.
> **SUPUESTO ILUSTRATIVO.** Escenario conservador: el agente resuelve la mitad del techo de contención.

Cálculo: 2,562 tickets automatizables (`05`) / 12 meses (`06`) = 213.5 tickets al mes.

| Minutos por ticket (SUPUESTO) | Horas al mes, techo (51.24%) | Horas al mes, conservador (mitad, SUPUESTO) |
| --- | --- | --- |
| 10 | 35.6 | 17.8 |
| 15 | 53.4 | 26.7 |
| 20 | 71.2 | 35.6 |

Si el volumen fuera el del requerimiento (unos 5,000 tickets al mes, `docs/requirements.md`, sección 1) y se
mantuviera la proporción de `05`, serían 2,562 tickets al mes: **427 / 641 / 854 horas** al mes con 10 / 15 / 20
minutos (techo; la mitad en el conservador). Este escenario es un **SUPUESTO ILUSTRATIVO**, porque los datos
sintéticos solo contienen 12 meses de 5,000 tickets. No se traduce a dinero: no hay tarifa en los datos.

## 6. Picos y SLA: dónde actuar

- **Quincena:** 64 días de quincena contra 296 del resto; los desbloqueos son 15.96% de los tickets de esos
  días contra 8.75% (`07`). Un agente disponible 24/7 absorbe el pico sin sumar personal.
- **Áreas:** Caja tiene el menor cumplimiento (63.47%, -4.50 pp contra el promedio) y Cobranza el mayor (71.65%,
  +3.67 pp) (`02_sla_por_area.sql`).
- **Canales:** el portal concentra 34.78% de los tickets y teléfono 26.40% (`09_distribucion_por_canal.sql`).
- **Inglés:** 481 tickets (172 + 123 + 115 + 71 por canal en `09`) = **9.62%**; justifica el soporte bilingüe.
- **Backlog:** 16 tickets abiertos o en proceso: P1 0, P2 1, P3 7 y P4 8 (`10_backlog_por_prioridad.sql`).
- **Tendencia:** entre 380 y 453 tickets por mes, sin tendencia clara; el SLA mensual va de 64.50% a 73.11%
  (`06_tendencia_mensual.sql`).

## 7. Costos y beneficios (cualitativos)

| Beneficios | Costos |
| --- | --- |
| Menos carga repetitiva en L1; el equipo se enfoca en casos complejos | Licencias de Copilot Studio y de Fabric (no cotizadas aquí) |
| Respuesta inmediata en cualquier horario, incluido el pico de quincena | Curaduría continua de los artículos de la base de conocimiento |
| Respuestas estandarizadas y con artículo citado | Operar y monitorear la API (modo local gratis; Fabric requiere capacidad) |
| Datos estructurados de cada ticket para decidir qué automatizar | Gestión de cambio: capacitar a L1 y a los usuarios |

No se calcula un ROI en dinero porque no hay costos reales ni tarifas; hacerlo sería inventar cifras.

## 8. Riesgos y límites

| Riesgo | Mitigación | Límite conocido |
| --- | --- | --- |
| Datos sensibles (RN-05): el usuario escribe una contraseña o tarjeta | El agente advierte; `crear_ticket` y los logs redactan por regex ([ADR-0006](adr/0006-seguridad-api-key-redaccion-escalamiento.md)) | Una contraseña sin separador no se redacta (L16 del ODD) |
| Escalamiento obligatorio (RN-03): fraude, acceso no autorizado, caja | Regex de frases más escalamiento por artículo con margen de 0.05 (ADR-0006) | En inglés "POS is not working" sin "terminal" no se detecta (L21) |
| El agente inventa pasos | Umbral de similitud 0.33, modo extractivo por defecto, citas validadas ([ADR-0001](adr/0001-rag-extractivo-por-defecto.md)) | El umbral es global y sin rerank: EV-16 falla |
| Fabric solo lectura en el endpoint | Tickets nuevos en un Warehouse ([ADR-0004](adr/0004-sql-portable-y-fabric.md)) | Fabric no se probó contra un tenant real (T28-T30) |
| Unicidad de `ticket_id` en el Warehouse | PK no forzada en Fabric; ID aleatorio | Riesgo residual de colisión aceptado (L16) |
| Resultados en Copilot Studio no medidos | Evaluación local de 30 casos | Los 30 casos en el chat son manuales (T33) |

El agente no ejecuta acciones sobre sistemas (no resetea contraseñas): guía y crea el ticket (fuera de alcance
en `docs/requirements.md`, sección 5).

## 9. Métricas de éxito: resultado real

Salida de `python main.py eval` (modo local, índice real), leída de `tests/eval/results.summary.json`:

| Métrica | Meta (requisitos, sección 12) | Resultado | ¿Cumple? |
| --- | --- | --- | --- |
| Casos aprobados | >= 27 de 30 | **29 de 30** (96.7%) | Sí |
| Recuperación en top 3 | >= 90% | 14 de 14 (100%) | Sí |
| Rechazo correcto | 100% | **3 de 4 (75%)** | **No** |
| Clasificación de tickets | >= 85% | 5 de 5 (100%) | Sí |
| Seguridad (datos sensibles) | 100% | 3 de 3 (100%) | Sí |
| Latencia local sin LLM (RNF-01) | p95 < 1.5 s | p50 13.8 ms, p95 31.5 ms | Sí |

El caso que falla es **EV-16**: una consulta fuera de dominio recupera KB-003 con score 0.525, sobre el umbral
de 0.33, y el agente responde en vez de rechazar. Se documentó como limitación y no se subió el umbral, para no
rechazar consultas legítimas (L22 del ODD). Por eso `eval` sale con código 1.
Las métricas de Copilot Studio se medirán en la Fase C (T33).

## 10. Trazabilidad cifra, consulta y valor

| Cifra | Consulta (`integrations/fabric/sql/`) | Valor obtenido |
| --- | --- | --- |
| % repetitivo (5 subcategorías) | `01_top_incidencias.sql` | 1,996 tickets, 39.92% |
| Top 5 por volumen acumulado | `01_top_incidencias.sql` | 40.92% |
| % automatizable (RN-06) | `05_tickets_automatizables.sql` | 2,562 tickets, 51.24% |
| Automatizable dentro de las repetitivas | `05` y `01` | 1,767 / 1,996 = 88.53% |
| Contención estimada (techo) | `05_tickets_automatizables.sql` | 51.24% |
| Tickets sin artículo | `05_tickets_automatizables.sql` | 689 en 5 subcategorías |
| Sistema de caja | `05_tickets_automatizables.sql` | 224 tickets, 0 automatizables |
| Horas de resolución por categoría | `04_horas_perdidas_por_categoria.sql` | Accesos 31.54%; total 114,540.35 h |
| Horas ahorradas al mes | `05` y `06` más SUPUESTO de minutos | 35.6 / 53.4 / 71.2 h (10 / 15 / 20 min) |
| Factor quincena | `07_efecto_quincena.sql` | 1.90 (2.30 contra 1.21 por día) |
| SLA local | `08_local_vs_foranea.sql` | 79.50% |
| SLA foráneo | `08_local_vs_foranea.sql` | 60.57% (brecha 18.93 pp) |
| Peor sucursal | `03_sla_por_sucursal.sql` | Puebla 05, 35.56% |
| SLA por área | `02_sla_por_area.sql` | Caja 63.47% a Cobranza 71.65% |
| Distribución por canal | `09_distribucion_por_canal.sql` | Portal 34.78%, teléfono 26.40% |
| % inglés | `09_distribucion_por_canal.sql` | 481 tickets, 9.62% |
| Tendencia mensual | `06_tendencia_mensual.sql` | 380 a 453 tickets al mes; 12 meses |
| Backlog | `10_backlog_por_prioridad.sql` | 16 tickets (P1 0, P2 1, P3 7, P4 8) |
| Resultado de evaluación | `tests/eval/results.summary.json` | 29/30, rechazo 3/4, p95 31.5 ms |

## 11. Cómo reproducir

```powershell
.venv\Scripts\python main.py generate-data
.venv\Scripts\python main.py load-db --run-sql
.venv\Scripts\python main.py eval
```

La semilla fija (42) da siempre los mismos datos. Los resultados en Fabric y en Copilot Studio se agregarán con
evidencia real en T36.
