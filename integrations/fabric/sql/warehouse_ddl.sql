-- DDL del Fabric Warehouse: tabla dbo.tickets_nuevos (S6, RF-18, T11).
--
-- Para qué: en modo fabric, crear_ticket (T17) escribe aquí los tickets nuevos. El SQL
-- analytics endpoint del lakehouse es de solo lectura (T-SQL define y consulta, pero no
-- modifica datos), por eso las escrituras van a un Warehouse, que sí admite DML.
-- Cómo usarlo: ejecútalo una sola vez en el editor SQL del Warehouse (T29). No borra
-- nada: si la tabla ya existe, CREATE TABLE falla y los datos quedan intactos.
--
-- Mismas columnas, mismo orden y misma nulabilidad que tickets_nuevos del modo local
-- (TICKETS_NUEVOS_COLUMNS en src/ingestion/sqlite_loader.py); un test lo comprueba.
-- Tipos según "Data types in Fabric Data Warehouse" (fuentes en docs/sources.md):
--   * varchar/char en lugar de nvarchar/nchar (no existen en Warehouse). La colación por
--     defecto es Latin1_General_100_BIN2_UTF8 y varchar(n) cuenta BYTES: una letra con
--     acento ocupa 2, por eso los tamaños tienen holgura.
--   * datetime2(0): Warehouse exige precisión explícita (0 a 6) y no tiene datetime. Las
--     fechas del proyecto llegan a segundos (YYYY-MM-DD HH:MM:SS).
--   * Banderas sla_cumplido y es_repetitivo como int 0/1 (no bit), igual que en SQLite y
--     en las tablas Delta del notebook, para que SUM(bandera) funcione igual en todos lados.
--   * horas_resolucion como float (el DOUBLE de Delta se expone como float).
-- Sin CHECK ni DEFAULT: la sintaxis de CREATE TABLE en Warehouse solo admite NULL/NOT NULL
-- y COLLATE. Los dominios (prioridad P1-P4, idioma es/en, estado, banderas 0/1) los valida
-- la aplicación con Pydantic antes del INSERT (T17).
-- Sin IDENTITY: ticket_id lo genera la aplicación (IDENTITY en Warehouse solo es bigint).
CREATE TABLE dbo.tickets_nuevos (
    ticket_id        VARCHAR(32)   NOT NULL,  -- TCK-000001; clave lógica
    fecha_apertura   DATETIME2(0)  NOT NULL,
    fecha_cierre     DATETIME2(0)  NULL,      -- NULL mientras el ticket siga abierto
    categoria        VARCHAR(100)  NOT NULL,
    subcategoria     VARCHAR(100)  NOT NULL,
    prioridad        CHAR(2)       NOT NULL,  -- P1 | P2 | P3 | P4 (RN-01)
    sucursal         VARCHAR(100)  NOT NULL,
    area             VARCHAR(100)  NOT NULL,
    canal            VARCHAR(50)   NOT NULL,
    sla_horas        INT           NOT NULL,  -- horas de SLA según prioridad (RN-02)
    sla_cumplido     INT           NULL,      -- 0/1; NULL hasta que se cierre
    horas_resolucion FLOAT         NULL,      -- NULL hasta que se cierre
    anio_mes         CHAR(7)       NOT NULL,  -- YYYY-MM, precalculado para SQL portable
    solucion         VARCHAR(2000) NULL,      -- NULL hasta que se resuelva
    es_repetitivo    INT           NOT NULL,  -- 0/1
    idioma           CHAR(2)       NOT NULL,  -- es | en
    estado           VARCHAR(20)   NOT NULL,  -- abierto | en_proceso | resuelto | cerrado
    descripcion      VARCHAR(8000) NOT NULL   -- hasta 2,000 caracteres (api.max_description_chars)
);

-- Clave primaria informativa: en Warehouse solo se admite NONCLUSTERED NOT ENFORCED y
-- solo con ALTER TABLE. NOT ENFORCED significa que el motor NO impide duplicados: la
-- unicidad de ticket_id la garantiza la aplicación al generarlo.
ALTER TABLE dbo.tickets_nuevos
    ADD CONSTRAINT pk_tickets_nuevos PRIMARY KEY NONCLUSTERED (ticket_id) NOT ENFORCED;
