-- 04 · Horas perdidas por categoría
-- Pregunta de negocio: ¿qué categorías consumen más horas de resolución y cuántas de esas
--   horas exceden el SLA? Indica dónde un agente L1 libera más tiempo (HU-06).
-- Técnica SQL: GROUP BY con SUM y CASE (horas fuera de SLA), CTE, SUM() OVER () para el
--   total y SUM() OVER (ORDER BY ...) para el acumulado (análisis de Pareto).
-- Cómo leer el resultado: una fila por categoría, de la que más horas consume a la que
--   menos. horas_totales = suma de horas_resolucion de tickets cerrados; horas_fuera_sla =
--   horas por encima del SLA comprometido; pct_acumulado muestra cuántas categorías
--   explican la mayor parte del tiempo.
WITH por_categoria AS (
    SELECT
        categoria,
        COUNT(*) AS tickets_cerrados,
        SUM(horas_resolucion) AS horas_totales,
        SUM(
            CASE
                WHEN horas_resolucion > sla_horas THEN horas_resolucion - sla_horas
                ELSE 0
            END
        ) AS horas_fuera_sla
    FROM tickets
    WHERE horas_resolucion IS NOT NULL
    GROUP BY categoria
),
con_totales AS (
    SELECT
        categoria,
        tickets_cerrados,
        horas_totales,
        horas_fuera_sla,
        SUM(horas_totales) OVER () AS horas_banco,
        SUM(horas_totales) OVER (
            ORDER BY horas_totales DESC, categoria
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS horas_acumuladas
    FROM por_categoria
)
SELECT
    categoria,
    tickets_cerrados,
    ROUND(horas_totales, 2) AS horas_totales,
    ROUND(horas_totales / tickets_cerrados, 2) AS horas_promedio,
    ROUND(horas_fuera_sla, 2) AS horas_fuera_sla,
    ROUND(100.0 * horas_totales / horas_banco, 2) AS pct_horas,
    ROUND(100.0 * horas_acumuladas / horas_banco, 2) AS pct_acumulado
FROM con_totales
ORDER BY horas_totales DESC, categoria;
