-- 03 · % de SLA cumplido por sucursal
-- Pregunta de negocio: ¿qué sucursales tienen el peor cumplimiento de SLA y cuál es su
--   diferencia contra el promedio (HU-07)?
-- Técnica SQL: JOIN entre tickets y la dimensión sucursales, GROUP BY por sucursal, CTE
--   con el promedio general (CROSS JOIN) y RANK() de peor a mejor.
-- Cómo leer el resultado: una fila por sucursal con tickets cerrados, empezando por la
--   peor. diferencia_pp negativa = por debajo del promedio del banco. es_foranea = 1
--   indica sucursal fuera de CDMX, Guadalajara y Monterrey; region permite filtrar.
WITH cerrados AS (
    SELECT
        t.sucursal,
        s.ciudad,
        s.region,
        s.es_foranea,
        t.sla_cumplido
    FROM tickets AS t
    INNER JOIN sucursales AS s ON s.sucursal = t.sucursal
    WHERE t.sla_cumplido IS NOT NULL
),
por_sucursal AS (
    SELECT
        sucursal,
        ciudad,
        region,
        es_foranea,
        COUNT(*) AS tickets_cerrados,
        100.0 * SUM(sla_cumplido) / COUNT(*) AS pct_sla
    FROM cerrados
    GROUP BY sucursal, ciudad, region, es_foranea
),
general AS (
    SELECT 100.0 * SUM(sla_cumplido) / COUNT(*) AS pct_general
    FROM cerrados
)
SELECT
    RANK() OVER (ORDER BY p.pct_sla) AS posicion_peor,
    p.sucursal,
    p.ciudad,
    p.region,
    p.es_foranea,
    p.tickets_cerrados,
    ROUND(p.pct_sla, 2) AS pct_sla_cumplido,
    ROUND(p.pct_sla - g.pct_general, 2) AS diferencia_pp
FROM por_sucursal AS p
CROSS JOIN general AS g
ORDER BY posicion_peor, p.sucursal;
