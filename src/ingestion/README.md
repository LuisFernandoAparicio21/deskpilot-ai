# ingestion
Carga documentos Markdown, PDF y CSV, y lee tickets del lakehouse de Fabric en modo fabric.
Incluye el generador de tickets sintéticos con semilla fija (`main.py generate-data`).

`ticket_generator.py` (con el catálogo estático `ticket_catalog.py`) escribe `data/raw/tickets.csv`,
`data/raw/sucursales.csv` y `data/sample/tickets_sample.csv`. La muestra es sistemática (una de cada
`n // 200` filas, empezando por la primera) para cubrir los 12 meses y conservar los patrones.

`sqlite_loader.py` (`main.py load-db`) carga esos CSV a SQLite (`paths.sqlite_db`) con DDL explícito, en una
transacción e idempotente: tablas `sucursales`, `tickets` y `tickets_nuevos` (vacía, para `crear_ticket`).

`documents.py` carga la base de conocimiento como `KBArticle` (front matter + secciones `##` en Markdown, texto
de PDF en una sección "Contenido", una fila por artículo en CSV); `load_knowledge_base` despacha por extensión.
