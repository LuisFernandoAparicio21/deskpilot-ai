# ingestion
Carga documentos Markdown, PDF y CSV, y lee tickets del lakehouse de Fabric en modo fabric.
Incluye el generador de tickets sintéticos con semilla fija (`main.py generate-data`).

`ticket_generator.py` (con el catálogo estático `ticket_catalog.py`) escribe `data/raw/tickets.csv`,
`data/raw/sucursales.csv` y `data/sample/tickets_sample.csv`. La muestra es sistemática (una de cada
`n // 200` filas, empezando por la primera) para cubrir los 12 meses y conservar los patrones.
