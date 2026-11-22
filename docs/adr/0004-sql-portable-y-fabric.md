# ADR-0004: SQL portable SQLite/T-SQL y Fabric (endpoint solo lectura, Warehouse con INSERT)

- **Estado:** aceptada
- **Fecha:** 2026-11-22

## Contexto

RF-20 exige 10 consultas que corran igual en SQLite (modo local) y en el SQL analytics endpoint de Fabric. Ese
endpoint es de solo lectura, pero `crear_ticket` necesita escribir (RF-18). Microsoft Learn indica que el
Warehouse admite INSERT y solo acepta autenticación Microsoft Entra ID.

## Decisión

- Las consultas usan SQL común: CTE, JOIN, GROUP BY y `ROW_NUMBER()`; sin `TOP` ni `LIMIT`. El generador
  precalcula `horas_resolucion` y `anio_mes`, y el día del mes se obtiene con `SUBSTRING(CAST(... AS
  VARCHAR(19)), 9, 2)`. Un test las parsea con sqlglot como `tsql` y `sqlite`.
- Lectura de tickets en el lakehouse (endpoint) y escritura de los nuevos en `dbo.tickets_nuevos` de un
  Warehouse (`warehouse_ddl.sql`; PK `NONCLUSTERED NOT ENFORCED`).
- Conexión con pyodbc y ODBC 18: token de Entra ID por `attrs_before` (1256), sin secretos en la cadena.

## Alternativas

- **Una consulta por motor:** más natural, pero duplica el mantenimiento.
- **Escribir en el endpoint:** imposible, es de solo lectura.
- **Escribir en el lakehouse con Spark:** pide un notebook por ticket; no es una API.

## Consecuencias

- Un solo conjunto de `.sql` sirve a los dos motores.
- La unicidad de `ticket_id` no la garantiza la PK no forzada; riesgo residual aceptado (L16).
- No verificado: el scope `https://database.windows.net/.default`, el DDL y la consulta `07` en un tenant real
  (T29-T30); la columna debe llegar como `datetime2` (L9, L10).

## Fuentes

`docs/sources.md`, sección Microsoft Fabric (T11): *What is Fabric Data Warehouse?*, *Warehouse Connectivity*,
*Table constraints*, *CAST and CONVERT*; sección SQL portable (T10). ODD L3, L9 y L10.
