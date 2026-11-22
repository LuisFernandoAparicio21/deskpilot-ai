# Decisiones de arquitectura (ADR)

Cada ADR registra una decisión técnica de DeskPilot AI en formato corto: contexto, decisión, alternativas y consecuencias.
Se numeran ADR-0001 en adelante y citan sus fuentes de `docs/sources.md` o del Log del ODD.
Las cifras de negocio están en [`docs/business-case.md`](../business-case.md).

| ADR | Decisión |
| --- | --- |
| [0001](0001-rag-extractivo-por-defecto.md) | RAG con modo extractivo por defecto y LLM opcional |
| [0002](0002-chromadb-indice-versionado.md) | ChromaDB coseno con índice versionado y puntero CURRENT |
| [0003](0003-fastembed-minilm-multilingue.md) | fastembed con MiniLM multilingüe |
| [0004](0004-sql-portable-y-fabric.md) | SQL portable SQLite/T-SQL y Fabric (endpoint solo lectura, Warehouse con INSERT) |
| [0005](0005-api-rest-y-mcp-una-capa.md) | API REST y MCP sobre una sola capa de servicio |
| [0006](0006-seguridad-api-key-redaccion-escalamiento.md) | Seguridad: X-API-Key, redacción RN-05 y escalamiento RN-03 |
| [0007](0007-swagger-2-json-copilot-studio.md) | Swagger 2.0 en JSON para Copilot Studio |
| [0008](0008-docker-una-etapa-modelo-en-build.md) | Docker de una etapa con el modelo en el build |
| [0009](0009-veto-con-reranker-cross-encoder.md) | Veto con reranker cross-encoder |
