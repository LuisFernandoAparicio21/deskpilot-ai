---
name: metricas_area
description: Un líder o coordinador pregunta por métricas de tickets de UN área (por ejemplo Caja) o de UNA sucursal: total, % dentro de SLA, tiempo promedio de resolución y categorías principales.
languages: [es, en]
trigger_phrases_es:
  - ¿cómo va el SLA del área Caja?
  - métricas del área Crédito
  - cuántos tickets tiene la sucursal Monterrey 02
  - dame el resumen de tickets de Operaciones
  - cumplimiento de SLA de mi sucursal
trigger_phrases_en:
  - how is the SLA for the Caja area
  - metrics for the Crédito area
  - how many tickets does the Monterrey 02 branch have
  - give me a ticket summary for Operaciones
  - SLA compliance for my branch
tools: [metricas_area]
requirements: [RF-19, HU-06, HU-07]
---

# Flujo
1. Determinar si pide un área o una sucursal. Enviar exactamente uno de `area` / `sucursal`. Si dio ambos o ninguno, preguntar cuál.
2. Llamar `metricas_area`.
3. Éxito: resumir `total_tickets`, `closed_tickets`, `sla_cumplido_pct`, `avg_horas_resolucion` y `top_categorias`. Aclarar que las cifras son ilustrativas (datos sintéticos).
4. 404: decir que no hay tickets con ese nombre y pedir verificarlo.

# Mensajes
- ES: "{name}: {total_tickets} tickets, {sla_cumplido_pct}% dentro de SLA, {avg_horas_resolucion} h promedio de resolución. Principales categorías: {top_categorias}. (Datos sintéticos, cifras ilustrativas.)"
- EN: "{name}: {total_tickets} tickets, {sla_cumplido_pct}% within SLA, {avg_horas_resolucion} h average resolution. Top categories: {top_categorias}. (Synthetic data, illustrative figures.)"
- ES ambos/ninguno: "¿Quieres las métricas de un área o de una sucursal? Dime solo una."
- EN both/none: "Do you want metrics for an area or a branch? Please pick one."
- ES 404: "No encontré tickets con ese nombre. Revisa cómo se escribe el área o la sucursal."
- EN 404: "I found no tickets with that name. Please check the spelling of the area or branch."
