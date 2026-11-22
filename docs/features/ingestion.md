# Ingestion: synthetic data and document loading

- `ticket_generator.py` (with the static catalog `ticket_catalog.py`) writes `data/raw/tickets.csv`, `data/raw/sucursales.csv` and `data/sample/tickets_sample.csv`. The sample is systematic (one of every `n // 200` rows, starting with the first) to cover the 12 months and keep the patterns.
- `sqlite_loader.py` (`main.py load-db`) loads those CSVs into SQLite (`paths.sqlite_db`) with explicit DDL, in one transaction and idempotently: tables `sucursales`, `tickets` and `tickets_nuevos` (empty, for `crear_ticket`).
- `documents.py` loads the knowledge base as `KBArticle` (front matter + `##` sections in Markdown, PDF text in a "Contenido" section, one row per article in CSV); `load_knowledge_base` dispatches by extension.
