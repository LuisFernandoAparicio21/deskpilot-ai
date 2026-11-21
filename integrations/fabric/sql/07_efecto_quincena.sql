-- 07 · Efecto de quincena
-- Pregunta de negocio: ¿los desbloqueos de usuario se disparan en días de quincena
--   (14–16 y 29–31), cuando hay más operación en sucursal?
-- Técnica SQL: CTE que deriva el día del mes de forma portable:
--   SUBSTRING(CAST(fecha_apertura AS VARCHAR(19)), 9, 2). En SQLite la fecha es texto
--   'YYYY-MM-DD HH:MM:SS'; en T-SQL un datetime2 se convierte a texto con el estilo 121
--   ('yyyy-MM-dd HH:mm:ss...'), así que las posiciones 9–10 son el día en ambos motores.
--   Después GROUP BY con CASE, COUNT(DISTINCT ...) para normalizar por número de días y
--   MAX(...) OVER () para comparar contra el resto de los días.
-- Cómo leer el resultado: dos filas (quincena y resto). desbloqueos_por_dia es el promedio
--   diario de tickets 'Desbloqueo de usuario'; veces_vs_resto > 1 indica cuántas veces más
--   desbloqueos hay en quincena; pct_desbloqueo es su peso dentro de los tickets del día.
WITH por_ticket AS (
    SELECT
        subcategoria,
        SUBSTRING(CAST(fecha_apertura AS VARCHAR(19)), 1, 10) AS fecha,
        CAST(SUBSTRING(CAST(fecha_apertura AS VARCHAR(19)), 9, 2) AS INT) AS dia
    FROM tickets
),
clasificados AS (
    SELECT
        fecha,
        CASE WHEN dia IN (14, 15, 16, 29, 30, 31) THEN 'quincena' ELSE 'resto' END AS tipo_dia,
        CASE WHEN subcategoria = 'Desbloqueo de usuario' THEN 1 ELSE 0 END AS es_desbloqueo
    FROM por_ticket
),
por_tipo AS (
    SELECT
        tipo_dia,
        COUNT(DISTINCT fecha) AS dias,
        COUNT(*) AS tickets,
        SUM(es_desbloqueo) AS desbloqueos,
        1.0 * SUM(es_desbloqueo) / COUNT(DISTINCT fecha) AS desbloqueos_por_dia
    FROM clasificados
    GROUP BY tipo_dia
)
SELECT
    tipo_dia,
    dias,
    tickets,
    desbloqueos,
    ROUND(desbloqueos_por_dia, 2) AS desbloqueos_por_dia,
    ROUND(100.0 * desbloqueos / tickets, 2) AS pct_desbloqueo,
    ROUND(
        desbloqueos_por_dia
        / MAX(CASE WHEN tipo_dia = 'resto' THEN desbloqueos_por_dia END) OVER (),
        2
    ) AS veces_vs_resto
FROM por_tipo
ORDER BY tipo_dia;
