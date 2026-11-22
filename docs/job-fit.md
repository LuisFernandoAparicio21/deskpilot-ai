# Ajuste al perfil: AI Developer Trainee

> Datos sintéticos generados para este proyecto; las cifras son ilustrativas. "Banco Altiplano" es ficticio.

Cómo este repositorio evidencia cada requisito y responsabilidad de un perfil de AI Developer Trainee (stack objetivo: Microsoft Copilot Studio y Microsoft Fabric). La tabla se puede reutilizar para vacantes similares cambiando la columna de evidencia.

Estados: **hecho** (hecho y medido en local, verificado en este repo), **parcial** (diseñado y probado con dobles, pendiente de validar en tenant real) y **pendiente manual** (depende del usuario y de un tenant de Microsoft; sin resultados todavía).

## Requisitos

| # | Requisito | Evidencia en este repo | Estado |
| --- | --- | --- | --- |
| 1 | Programación, razonamiento lógico y manejo de datos | Código Python tipado y modular en [`src/`](../src/), generador de datos con reglas de negocio ([`ticket_generator.py`](../src/ingestion/ticket_generator.py)), pipeline RAG, 1724 pruebas con 98.24% de cobertura ([procedimiento](testing-procedure.md)) | Hecho (local) |
| 2 | SQL básico | 10 consultas comentadas con JOIN, GROUP BY, CTE y funciones de ventana en [`integrations/fabric/sql/`](../integrations/fabric/sql/), ejecutadas en SQLite (`load-db --run-sql`) | Parcial: hecho en local; escrito para Fabric, pendiente de validar en tenant real (T29) |
| 3 | Interés demostrado en IA y agentes | RAG con citas ([ADR-0001](adr/0001-rag-extractivo-por-defecto.md)), [API con herramientas](features/api-rest.md), [servidor MCP](features/mcp-server.md), [diseño del agente](features/copilot-studio-agent.md) | Parcial: RAG y MCP hechos en local; agente diseñado, video pendiente manual (T35) |
| 4 | Pensamiento analítico y resolución de problemas | [Caso de negocio](business-case.md) con hipótesis y cifras por consulta; [ADR](adr/README.md) con alternativas descartadas; limitación EV-16 documentada en [eval-e2e](features/eval-e2e.md) | Hecho |
| 5 | Disposición a aprender nuevas tecnologías | [Registro de aprendizaje](learning-log.md) (plantilla; lo llena el usuario con sus rutas reales) y fuentes verificadas en [`sources.md`](sources.md) | Parcial: registro pendiente manual (T35) |
| 6 | Proactividad, trabajo en equipo y crecimiento | Flujo por PR con issues, ramas y commits convencionales: [CONTRIBUTING](../CONTRIBUTING.md), [plantilla de PR](../.github/pull_request_template.md), [CI](../.github/workflows/ci.yml), [roadmap](roadmap.md) con PR por tarea | Hecho |

## Responsabilidades

| # | Responsabilidad | Evidencia en este repo | Estado |
| --- | --- | --- | --- |
| 7 | Diseñar, desarrollar y probar agentes con Copilot Studio | [Instrucciones](../integrations/copilot_studio/instructions.md), [herramientas](../integrations/copilot_studio/tools.md), [escalamiento](../integrations/copilot_studio/escalation.md), [18 conversaciones de prueba](../integrations/copilot_studio/test-conversations.md), [openapi.json](../integrations/copilot_studio/openapi.json) | Parcial: diseñado y probado con dobles; agente en el tenant y los 30 casos en el chat pendientes de validar (T32, T33) |
| 8 | Consultar, procesar y preparar datos con SQL y Microsoft Fabric | [Notebook PySpark/Delta](../integrations/fabric/notebooks/01_load_tickets_delta.ipynb), [DDL del Warehouse](../integrations/fabric/sql/warehouse_ddl.sql), [conexión](../src/utils/fabric.py) | Parcial: diseñado y probado con dobles, pendiente de validar en tenant real; Power BI pendiente manual (T28 a T30, T34) |
| 9 | Identificar procesos de negocio donde la IA agrega valor | [Caso de negocio](business-case.md): 39.92% repetitivo, 51.24% automatizable, picos de quincena, brecha de SLA, horas ahorradas (supuesto ilustrativo) | Hecho |
| 10 | Documentar desarrollo, pruebas y resultados | [README](../README.md), [arquitectura](architecture.md), [procedimiento de pruebas](testing-procedure.md), [`tests/eval/`](../tests/eval/results.summary.json), [ODD con Log](odd/deskpilot-ai.md), [CHANGELOG](../CHANGELOG.md) | Hecho |
| 11 | Programas y rutas de aprendizaje aplicados a proyectos reales | [Registro de aprendizaje](learning-log.md): conecta cada ruta con la parte del proyecto donde se aplicó | Pendiente manual (T35): sin rutas ni insignias registradas |

## Lo que no se afirma

- Los resultados en Copilot Studio y Fabric no están medidos; el agente y el modo `fabric` están diseñados y probados con dobles.
- La evaluación local es 29 de 30 casos; EV-16 es una limitación conocida, no un caso resuelto.
- Las horas ahorradas dependen de minutos por ticket supuestos.
