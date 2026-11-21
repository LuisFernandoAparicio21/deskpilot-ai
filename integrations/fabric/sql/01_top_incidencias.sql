-- 01 · Top incidencias
-- Pregunta de negocio: ¿cuáles son las 10 subcategorías con más tickets y qué parte del
--   volumen total concentran? Son las primeras candidatas a automatizar (HU-06).
-- Técnica SQL: GROUP BY en una CTE, ROW_NUMBER() para el ranking (en lugar de TOP/LIMIT,
--   para que corra igual en SQLite y en T-SQL), SUM() OVER () para el total general y
--   SUM() OVER (ORDER BY ...) para el porcentaje acumulado.
-- Cómo leer el resultado: una fila por subcategoría, de la más frecuente a la menos.
--   pct_del_total es su peso sobre todos los tickets y pct_acumulado suma las filas
--   anteriores (Pareto): si el top 5 llega a ~40%, ese bloque es el foco del agente L1.
WITH conteo AS (
    SELECT
        categoria,
        subcategoria,
        COUNT(*) AS tickets,
        SUM(es_repetitivo) AS tickets_repetitivos
    FROM tickets
    GROUP BY categoria, subcategoria
),
ranking AS (
    SELECT
        categoria,
        subcategoria,
        tickets,
        tickets_repetitivos,
        ROW_NUMBER() OVER (ORDER BY tickets DESC, subcategoria) AS posicion,
        SUM(tickets) OVER () AS total_tickets,
        SUM(tickets) OVER (
            ORDER BY tickets DESC, subcategoria
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS tickets_acumulados
    FROM conteo
)
SELECT
    posicion,
    categoria,
    subcategoria,
    tickets,
    tickets_repetitivos,
    ROUND(100.0 * tickets / total_tickets, 2) AS pct_del_total,
    ROUND(100.0 * tickets_acumulados / total_tickets, 2) AS pct_acumulado
FROM ranking
WHERE posicion <= 10
ORDER BY posicion;
