-- 06 · Tendencia mensual
-- Pregunta de negocio: ¿el volumen de tickets y el cumplimiento de SLA mejoran o empeoran
--   mes a mes?
-- Técnica SQL: GROUP BY por la columna precalculada anio_mes (evita funciones de fecha
--   que cambian entre motores), CTE, LAG() para el mes anterior y AVG() OVER con marco
--   ROWS para el promedio móvil de 3 meses.
-- Cómo leer el resultado: una fila por mes en orden cronológico. variacion_pct compara
--   con el mes anterior (vacía en el primer mes); promedio_movil_3m suaviza picos;
--   pct_sla_cumplido usa solo tickets cerrados del mes.
WITH por_mes AS (
    SELECT
        anio_mes,
        COUNT(*) AS tickets,
        SUM(CASE WHEN sla_cumplido IS NOT NULL THEN 1 ELSE 0 END) AS tickets_cerrados,
        SUM(sla_cumplido) AS tickets_en_sla
    FROM tickets
    GROUP BY anio_mes
),
con_ventanas AS (
    SELECT
        anio_mes,
        tickets,
        tickets_cerrados,
        tickets_en_sla,
        LAG(tickets) OVER (ORDER BY anio_mes) AS tickets_mes_anterior,
        AVG(1.0 * tickets) OVER (
            ORDER BY anio_mes
            ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
        ) AS promedio_movil_3m
    FROM por_mes
)
SELECT
    anio_mes,
    tickets,
    tickets_mes_anterior,
    ROUND(100.0 * (tickets - tickets_mes_anterior) / tickets_mes_anterior, 2) AS variacion_pct,
    ROUND(promedio_movil_3m, 2) AS promedio_movil_3m,
    ROUND(100.0 * tickets_en_sla / NULLIF(tickets_cerrados, 0), 2) AS pct_sla_cumplido
FROM con_ventanas
ORDER BY anio_mes;
