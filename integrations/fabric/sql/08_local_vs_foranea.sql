-- 08 · Sucursales locales vs foráneas
-- Pregunta de negocio: ¿las sucursales foráneas (fuera de CDMX, Guadalajara y Monterrey)
--   cumplen peor el SLA que las locales, y por cuántos puntos (HU-07)?
-- Técnica SQL: INNER JOIN con la dimensión sucursales, GROUP BY por es_foranea con CASE
--   para la etiqueta, y MAX(...) OVER () para restar el % de las locales a cada fila.
-- Cómo leer el resultado: dos filas. pct_sla_cumplido usa tickets cerrados;
--   diferencia_vs_local_pp es 0 para 'local' y negativa para 'foranea' si cumple peor;
--   horas_promedio compara el tiempo de resolución.
WITH por_tipo AS (
    SELECT
        CASE WHEN s.es_foranea = 1 THEN 'foranea' ELSE 'local' END AS tipo_sucursal,
        COUNT(DISTINCT s.sucursal) AS sucursales,
        COUNT(*) AS tickets_cerrados,
        100.0 * SUM(t.sla_cumplido) / COUNT(*) AS pct_sla,
        AVG(t.horas_resolucion) AS horas_promedio
    FROM tickets AS t
    INNER JOIN sucursales AS s ON s.sucursal = t.sucursal
    WHERE t.sla_cumplido IS NOT NULL
    GROUP BY CASE WHEN s.es_foranea = 1 THEN 'foranea' ELSE 'local' END
)
SELECT
    tipo_sucursal,
    sucursales,
    tickets_cerrados,
    ROUND(pct_sla, 2) AS pct_sla_cumplido,
    ROUND(pct_sla - MAX(CASE WHEN tipo_sucursal = 'local' THEN pct_sla END) OVER (), 2)
        AS diferencia_vs_local_pp,
    ROUND(horas_promedio, 2) AS horas_promedio
FROM por_tipo
ORDER BY tipo_sucursal DESC;
