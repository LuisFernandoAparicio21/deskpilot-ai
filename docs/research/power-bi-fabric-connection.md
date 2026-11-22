# Power BI Desktop a Fabric (Lakehouse/Warehouse) y licencias

Consulta: 2026-11-22. Rama chore/t25-manual-steps.

## Pregunta
¿Pasos oficiales para que Power BI Desktop (gratuito) se conecte a un Lakehouse/Warehouse de Fabric y haga un reporte simple; qué licencia hace falta para publicar vs solo capturas desde Desktop?

## Respuesta
**Opción A, SQL analytics endpoint (más simple):**
1. En Fabric, Settings del Warehouse o del SQL analytics endpoint > "SQL connection string"; copiarla (`<id>.datawarehouse.fabric.microsoft.com`). Exige rol Contributor o superior en el workspace.
2. Power BI Desktop: el Warehouse o SQL analytics endpoint es fuente nativa (panel Data / OneLake catalog), sin necesidad de la cadena; elegir el elemento, las tablas y modo **Import** o **DirectQuery**. Con el conector SQL Server: servidor = cadena, base de datos = nombre del item (si no, se conecta a `master`); autenticación Microsoft Entra ID.
3. Crear visuales (tarjeta, barras por categoría) y capturar pantalla.

**Opción B, Direct Lake / modelo semántico (OneLake catalog):** Desktop > OneLake catalog > elegir Lakehouse o Warehouse > Connect > nombrar el modelo, elegir workspace y tablas > OK. Se crea un modelo semántico Direct Lake on OneLake en el workspace y se edita en vivo (sin botón publicar; sin vista Reporte mientras se edita). Para el reporte: File > Blank report > OneLake catalog > elegir el modelo semántico > Connect; guardar y publicar al workspace. Requisitos: XMLA endpoint con lectura/escritura habilitado en tenant y capacidad, permiso Write en el modelo, Viewer en el lakehouse; **no disponible con licencia free**.

**Licencias:**
- Solo capturas desde Desktop (Import/DirectQuery contra el SQL endpoint): Desktop es gratuito; basta una cuenta Entra con acceso al workspace de Fabric. Que no se necesite Pro para esto: ⚠ verificar en pantalla (las fuentes no lo afirman de forma explícita).
- Publicar/compartir elementos Power BI en un workspace distinto de "My workspace": requiere licencia **Pro** o PPU (o prueba individual de Power BI). Con capacidad F64 o Trial (equivale a F64), usuarios con solo Free y rol Viewer pueden ver; en F menores a F64 quien ve también necesita Pro/PPU.
- La opción B (live edit) no funciona con licencia free.

## Decisión recomendada
Para la demo: opción A en Import desde Desktop y capturas para `docs/screenshots/`; no publicar al servicio salvo que haya Pro/PPU o prueba individual. Opción B solo si hay Pro/PPU y XMLA habilitado.

## Fuentes
- How to connect (Fabric Data Warehouse). https://learn.microsoft.com/en-us/fabric/data-warehouse/how-to-connect (consulta 2026-11-22)
- Direct Lake semantic models in Power BI Desktop. https://learn.microsoft.com/en-us/fabric/fundamentals/direct-lake-power-bi-desktop (2026-11-22)
- Understand Microsoft Fabric licenses and capacity. https://learn.microsoft.com/en-us/fabric/enterprise/licenses (2026-11-22)
