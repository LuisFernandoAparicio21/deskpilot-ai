-- 10 · Backlog por prioridad
-- Pregunta de negocio: al corte del periodo, ¿cuántos tickets siguen abiertos por
--   prioridad y qué parte del volumen de cada prioridad representan?
-- Técnica SQL: GROUP BY con conteos condicionales (CASE dentro de SUM), CTE y
--   SUM() OVER (ORDER BY prioridad) para el backlog acumulado de P1 a P4.
-- Cómo leer el resultado: una fila por prioridad (P1 = más crítica). abiertos son tickets
--   sin atender; en_proceso, tickets en trabajo; backlog = abiertos + en_proceso;
--   backlog_acumulado suma desde P1 para ver cuánto backlog crítico hay antes de llegar a
--   las prioridades bajas. pct_backlog es el backlog sobre los tickets de esa prioridad.
WITH por_prioridad AS (
    SELECT
        prioridad,
        MAX(sla_horas) AS sla_horas,
        COUNT(*) AS tickets,
        SUM(CASE WHEN estado = 'abierto' THEN 1 ELSE 0 END) AS abiertos,
        SUM(CASE WHEN estado = 'en_proceso' THEN 1 ELSE 0 END) AS en_proceso
    FROM tickets
    GROUP BY prioridad
)
SELECT
    prioridad,
    sla_horas,
    tickets,
    abiertos,
    en_proceso,
    abiertos + en_proceso AS backlog,
    ROUND(100.0 * (abiertos + en_proceso) / tickets, 2) AS pct_backlog,
    SUM(abiertos + en_proceso) OVER (
        ORDER BY prioridad
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS backlog_acumulado
FROM por_prioridad
ORDER BY prioridad;
