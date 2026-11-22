# Arquitectura

> Datos sintéticos generados para este proyecto; las cifras son ilustrativas. "Banco Altiplano" es ficticio.

DeskPilot AI tiene una capa de servicio única (RAG y tickets) expuesta por dos puertas: la API REST (FastAPI) y el servidor MCP. Las decisiones están en [`docs/adr/`](adr/README.md). Los nombres de módulos son los de `src/`.

## 1. Componentes

```mermaid
flowchart LR
    subgraph Clientes
        CS[Agente Copilot Studio]
        MC[Cliente MCP]
        CLI[main.py CLI]
    end
    subgraph API["src/api"]
        APP[app.py: FastAPI, X-API-Key]
        MCPS[mcp_server.py]
        TS[ticket_service.py + classification.py]
        REPO[repository.py: SqlTicketRepository]
    end
    subgraph RAG["src/retrieval, llm, prompts"]
        ANS[answer_service.py]
        POL[policy.py: escalamiento RN-03]
        RET[retriever.py: umbral]
        LLM[llm: none, Claude, OpenAI, Gemini]
    end
    subgraph Datos
        EMB[embeddings: fastembed]
        VDB[(vectordb: Chroma versionado)]
        KB[data/knowledge_base: 15 articulos]
        SQLITE[(SQLite local)]
        FAB[(Fabric: Lakehouse y Warehouse)]
    end
    RED[utils/redaction.py]

    CS -->|HTTPS, Swagger 2.0| APP
    MC --> MCPS
    APP --> ANS
    APP --> TS
    MCPS --> ANS
    MCPS --> TS
    ANS --> RED
    ANS --> POL
    ANS --> RET
    ANS -.opcional.-> LLM
    RET --> EMB
    RET --> VDB
    TS --> RED
    TS --> REPO
    APP --> REPO
    REPO --> SQLITE
    REPO -->|utils/fabric.py, ODBC| FAB
    CLI -->|index: ingestion, chunking| KB
    CLI --> VDB
    CLI -->|generate-data, load-db| SQLITE
```

## 2. Flujo de una consulta RAG

El umbral (`retrieval.similarity_threshold`, 0.33), el margen de escalamiento (`retrieval.escalation_margin`, 0.05) y la redacción son los de `config.yaml` y `src/retrieval/answer_service.py`.

```mermaid
sequenceDiagram
    participant U as Usuario o agente
    participant A as API / MCP
    participant S as AnswerService
    participant R as Retriever
    participant P as policy
    participant L as LLM (opcional)
    U->>A: buscar_solucion(query, categoria)
    A->>S: answer(query)
    S->>S: contains_sensitive? redact(query)
    S->>R: search(consulta redactada)
    R-->>S: articulos con score (evidencia: sobre el umbral)
    S->>P: escalation_reason(query)
    alt frase de fraude, acceso no autorizado o caja (RN-03)
        S-->>A: mandatory_escalation, articulo citado
    else articulo KB-011 dentro del margen del top-1
        S-->>A: mandatory_escalation
    else sin evidencia sobre el umbral
        S-->>A: no_evidence ("no lo se, escalo a un agente")
    else hay evidencia
        opt LLM_PROVIDER distinto de none
            S->>L: prompt con contexto citado
            L-->>S: texto (ids KB validados)
        end
        S-->>A: answered, pasos y cita (RN-04)
    end
    A-->>U: respuesta, citations, sensitive_data_warning
```

Si el LLM falla o devuelve citas no válidas, se usa la respuesta extractiva (ADR-0001). EV-16 es el caso conocido en que una consulta fuera de dominio supera el umbral (ver README).

## 3. Flujo de `crear_ticket`

```mermaid
flowchart TD
    IN[POST /tickets o herramienta crear_ticket] --> KEY{X-API-Key valida?}
    KEY -- no --> E401[401 error uniforme con request_id]
    KEY -- si --> VAL[Validar: descripcion, area, sucursal, canal]
    VAL -- invalido --> E422[Error de validacion]
    VAL --> RED[contains_sensitive y redact RN-05]
    RED --> CLS[classify: reglas, LLM opcional validado]
    CLS --> ESC{Escalamiento obligatorio RN-03?}
    ESC -- si --> P1[Prioridad no degradable por el LLM]
    ESC -- no --> PRI[Categoria y prioridad]
    P1 --> SLA[SLA en horas RN-01]
    PRI --> SLA
    SLA --> SAVE[(repository.create_ticket: tickets_nuevos)]
    SAVE --> OUT[201: ticket_id, SLA, fecha limite, escalado]
```

## 4. Despliegue

```mermaid
flowchart LR
    subgraph Local["Local o Docker (modo local, verificado)"]
        IMG[Imagen Docker: usuario no root, modelo e indice en el build]
        API1[FastAPI en :8000]
        DB1[(SQLite y Chroma)]
        IMG --> API1 --> DB1
    end
    subgraph MS["Microsoft (diseno; no verificado contra un tenant real)"]
        CS2[Copilot Studio: agente con 4 herramientas]
        FL[Fabric Lakehouse: tickets, SQL endpoint]
        FW[Fabric Warehouse: tickets_nuevos]
        PBI[Power BI: pendiente]
    end
    PUB[URL publica HTTPS: pendiente]
    CS2 -->|openapi.json| PUB --> API1
    API1 -.DESKPILOT_MODE=fabric.-> FL
    API1 -.-> FW
    FL --> PBI
```

- **Verificado:** `docker build` y `docker run` en modo local, incluido `--network none` ([`docs/features/docker.md`](features/docker.md)).
- **No verificado:** modo `fabric` (la imagen Docker no incluye el driver ODBC 18), URL pública, agente en Copilot Studio y Power BI. Son tareas manuales (T28 a T34) en [`docs/roadmap.md`](roadmap.md).
