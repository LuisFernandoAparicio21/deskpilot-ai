-- 02 · % de SLA cumplido por área
-- Pregunta de negocio: ¿qué áreas de sucursal cumplen menos el SLA y cuánto se alejan del
--   promedio del banco?
-- Técnica SQL: GROUP BY con agregados condicionales, CTE para el promedio general unida
--   con CROSS JOIN, RANK() para ordenar áreas por cumplimiento.
-- Cómo leer el resultado: una fila por área. pct_sla_cumplido se calcula solo sobre
--   tickets cerrados (sla_cumplido no nulo). diferencia_pp es la distancia en puntos
--   porcentuales contra el promedio general: negativa = el área está por debajo.
--   posicion 1 = mejor cumplimiento.
WITH cerrados AS (
    SELECT area, sla_cumplido, horas_resolucion
    FROM tickets
    WHERE sla_cumplido IS NOT NULL
),
por_area AS (
    SELECT
        area,
        COUNT(*) AS tickets_cerrados,
        SUM(sla_cumplido) AS tickets_en_sla,
        AVG(horas_resolucion) AS horas_promedio
    FROM cerrados
    GROUP BY area
),
general AS (
    SELECT 100.0 * SUM(sla_cumplido) / COUNT(*) AS pct_general
    FROM cerrados
)
SELECT
    RANK() OVER (ORDER BY 1.0 * a.tickets_en_sla / a.tickets_cerrados DESC) AS posicion,
    a.area,
    a.tickets_cerrados,
    ROUND(100.0 * a.tickets_en_sla / a.tickets_cerrados, 2) AS pct_sla_cumplido,
    ROUND(100.0 * a.tickets_en_sla / a.tickets_cerrados - g.pct_general, 2) AS diferencia_pp,
    ROUND(a.horas_promedio, 2) AS horas_promedio
FROM por_area AS a
CROSS JOIN general AS g
ORDER BY posicion, a.area;
