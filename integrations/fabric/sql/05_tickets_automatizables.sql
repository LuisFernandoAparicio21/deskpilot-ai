-- 05 · Tickets automatizables (RN-06)
-- Pregunta de negocio: ¿cuántos tickets podría resolver el agente L1 sin intervención
--   humana y cuántas horas representan (HU-06)?
-- Regla RN-06 con las columnas existentes: un ticket es automatizable si
--   (a) su subcategoría tiene artículo en la base de conocimiento: el modelo de datos no
--       trae esa columna, así que la CTE kb lista las 15 subcategorías con artículo
--       (las mismas del catálogo del generador; un test verifica que coincidan), y
--   (b) se resolvió sin L2: estado 'resuelto' o 'cerrado' y la solución NO empieza con el
--       prefijo de escalamiento que escribe el generador ('Escalado a L2.' en español,
--       'Escalated to L2.' en inglés).
-- Técnica SQL: CTE con UNION ALL como catálogo, LEFT JOIN, CASE dentro de SUM (conteo
--   condicional), GROUP BY y SUM() OVER () para el peso sobre el total del banco.
-- Cómo leer el resultado: una fila por subcategoría (tiene_articulo = 1 si hay artículo).
--   pct_automatizable es la parte de sus tickets que cumple RN-06; pct_del_banco es su
--   aporte al total de tickets; la suma de pct_del_banco es el % automatizable global.
WITH kb AS (
    SELECT 'Reseteo de contraseña' AS subcategoria
    UNION ALL SELECT 'Desbloqueo de usuario'
    UNION ALL SELECT 'Token bancario'
    UNION ALL SELECT 'VPN'
    UNION ALL SELECT 'Impresoras'
    UNION ALL SELECT 'Acceso a SAP'
    UNION ALL SELECT 'Acceso a core bancario'
    UNION ALL SELECT 'Carpetas compartidas'
    UNION ALL SELECT 'Equipo lento'
    UNION ALL SELECT 'Escáner de cheques'
    UNION ALL SELECT 'Sistema de caja'
    UNION ALL SELECT 'Correo'
    UNION ALL SELECT 'Microsoft Teams'
    UNION ALL SELECT 'Telefonía'
    UNION ALL SELECT 'Instalación de software'
),
clasificados AS (
    SELECT
        t.subcategoria,
        t.horas_resolucion,
        CASE WHEN kb.subcategoria IS NULL THEN 0 ELSE 1 END AS tiene_articulo,
        CASE
            WHEN kb.subcategoria IS NOT NULL
                AND t.estado IN ('resuelto', 'cerrado')
                AND t.solucion NOT LIKE 'Escalado a L2%'
                AND t.solucion NOT LIKE 'Escalated to L2%'
                THEN 1
            ELSE 0
        END AS automatizable
    FROM tickets AS t
    LEFT JOIN kb ON kb.subcategoria = t.subcategoria
),
por_subcategoria AS (
    SELECT
        subcategoria,
        tiene_articulo,
        COUNT(*) AS tickets,
        SUM(automatizable) AS tickets_automatizables,
        SUM(CASE WHEN automatizable = 1 THEN horas_resolucion ELSE 0 END)
            AS horas_automatizables
    FROM clasificados
    GROUP BY subcategoria, tiene_articulo
)
SELECT
    subcategoria,
    tiene_articulo,
    tickets,
    tickets_automatizables,
    ROUND(100.0 * tickets_automatizables / tickets, 2) AS pct_automatizable,
    ROUND(100.0 * tickets_automatizables / SUM(tickets) OVER (), 2) AS pct_del_banco,
    ROUND(horas_automatizables, 2) AS horas_automatizables
FROM por_subcategoria
ORDER BY tickets_automatizables DESC, subcategoria;
