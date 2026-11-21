-- 09 · Distribución por canal
-- Pregunta de negocio: ¿por qué canales llegan los tickets, cuánto tardan y cuál es la
--   incidencia más común en cada canal? Ayuda a decidir dónde publicar el agente.
-- Técnica SQL: dos CTE con GROUP BY, ROW_NUMBER() OVER (PARTITION BY canal ...) para la
--   subcategoría más frecuente por canal, SUM() OVER () para el peso de cada canal, RANK()
--   para ordenar canales por volumen y un JOIN entre las CTE.
-- Cómo leer el resultado: una fila por canal, del más usado al menos usado. pct_del_total
--   es su participación; top_subcategoria es lo que más se reporta por ese canal.
WITH por_canal AS (
    SELECT
        canal,
        COUNT(*) AS tickets,
        COUNT(sla_cumplido) AS tickets_cerrados,
        SUM(sla_cumplido) AS tickets_en_sla,
        AVG(horas_resolucion) AS horas_promedio,
        SUM(CASE WHEN idioma = 'en' THEN 1 ELSE 0 END) AS tickets_en_ingles
    FROM tickets
    GROUP BY canal
),
canal_subcategoria AS (
    SELECT
        canal,
        subcategoria,
        COUNT(*) AS tickets,
        ROW_NUMBER() OVER (PARTITION BY canal ORDER BY COUNT(*) DESC, subcategoria) AS rn
    FROM tickets
    GROUP BY canal, subcategoria
)
SELECT
    RANK() OVER (ORDER BY c.tickets DESC) AS posicion,
    c.canal,
    c.tickets,
    ROUND(100.0 * c.tickets / SUM(c.tickets) OVER (), 2) AS pct_del_total,
    ROUND(c.horas_promedio, 2) AS horas_promedio,
    ROUND(100.0 * c.tickets_en_sla / NULLIF(c.tickets_cerrados, 0), 2) AS pct_sla_cumplido,
    c.tickets_en_ingles,
    cs.subcategoria AS top_subcategoria,
    cs.tickets AS tickets_top_subcategoria
FROM por_canal AS c
INNER JOIN canal_subcategoria AS cs ON cs.canal = c.canal AND cs.rn = 1
ORDER BY posicion, c.canal;
