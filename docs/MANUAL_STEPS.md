# Pasos manuales (Fase C, T28 a T36)

Guía para la persona que hace la Fase C de DeskPilot AI: lo que no puede hacer un agente porque exige tu cuenta, tu
pantalla o tu criterio. Cubre las tareas T28 a T36 de [docs/roadmap.md](roadmap.md) y del ODD
([docs/odd/deskpilot-ai.md](odd/deskpilot-ai.md)). Tiempo total: unas 6 horas (ver la tabla del final). Datos 100%
sintéticos; banco ficticio "Banco Altiplano".

## Cómo leer esta guía

- Los pasos están numerados en el orden exacto en que debes hacerlos. Marca cada casilla al terminar.
- Cada paso indica: **Dónde** (clics), **Archivo** (del repo), **Copiar** (comandos exactos), **Verificar**, **Si falla**
  y **Link** oficial.
- **"⚠ verificar en pantalla"** significa que la documentación oficial consultada no confirma ese detalle (nombre de un
  botón, una opción, un límite). Mira la pantalla real y, si difiere, anótalo en el Log (L27 o siguiente) del ODD.
- Los clics de Microsoft solo se describen cuando están en la documentación oficial consultada. Los links salen de
  [docs/sources.md](sources.md); el detalle de cada investigación está en `docs/research/`.
- Comandos desde la raíz del repo, en PowerShell, con el entorno virtual: `.venv\Scripts\python ...`.
- **Cuenta universitaria:** el tenant de tu universidad tiene un administrador que puede haber desactivado funciones
  (prueba de Fabric, autoservicio de Copilot Studio). En cada sección están las alternativas.
- **Seguridad:** nunca pegues la API key, el secreto de Entra ni tokens en capturas, issues o commits. `.env` está
  ignorado por git; no lo subas.

## 0. Prerrequisitos y orden recomendado

Tiempo: 15 a 20 min si ya tienes casi todo (estimación, no medida).

1. [ ] **Python y el entorno virtual del repo.**
   - Dónde: terminal en la raíz del repo.
   - Copiar: `.venv\Scripts\python --version` (el proyecto se probó con Python 3.13; el CI usa 3.13).
   - Verificar: `.venv\Scripts\python -m pytest tests/unit/test_scripts_check_fabric.py -q` termina en `passed`.
   - Si falla: crea el entorno e instala `requirements.txt` y `requirements-dev.txt` (README, sección de instalación).
   - Link: ⚠ verificar en pantalla (instalación de Python no investigada).
2. [ ] **Datos y artefactos locales** (sirven para Fabric, la API y los casos).
   - Archivo: `data/raw/tickets.csv`, `data/raw/sucursales.csv`.
   - Copiar, solo si faltan: `.venv\Scripts\python main.py generate-data`, luego `.venv\Scripts\python main.py load-db` y
     `.venv\Scripts\python main.py index` (la primera vez baja el modelo de embeddings, unos 250 MB).
   - Verificar: existen los dos CSV; `.venv\Scripts\python main.py eval` escribe `tests/eval/results.summary.json`.
   - Si falla: revisa que `data/knowledge_base/` tenga los 15 artículos y vuelve a correr `index`.
3. [ ] **ODBC Driver 18 for SQL Server** (solo para el modo Fabric en tu PC; la imagen Docker no lo trae).
   - Dónde: instalador de Microsoft para Windows.
   - Verificar: `.venv\Scripts\python -m scripts.check_fabric` (paso 2 del script) lo busca por nombre.
   - Si falla: instala el driver 18 (no el 17) y repite. El script imprime cómo corregirlo.
   - Link: ⚠ verificar en pantalla (página de descarga no investigada). Contexto del driver con Entra ID:
     https://learn.microsoft.com/en-us/sql/connect/odbc/using-azure-active-directory
4. [ ] **Autenticación de Entra para el modo Fabric: `azure-cli` o variables de service principal.**
   - Opción A (recomendada, la que usa `DefaultAzureCredential`): instala `azure-cli` y haz `az login` con la cuenta
     que tendrá acceso al workspace. Está en `.env.example`. Instalación y `--tenant`: ⚠ verificar con `az login --help`.
   - Opción B: service principal con `AZURE_TENANT_ID`, `AZURE_CLIENT_ID` y `AZURE_CLIENT_SECRET` (las tres juntas).
     En una cuenta universitaria crear el service principal y darle permisos suele requerir al administrador: ⚠ verificar.
   - Link: https://learn.microsoft.com/en-us/fabric/data-warehouse/entra-id-authentication y
     https://learn.microsoft.com/en-us/fabric/data-warehouse/service-principals
5. [ ] **Docker Desktop** (solo si prefieres demostrar el modo local en contenedor; el modo Fabric corre fuera de Docker).
   - Copiar: `docker --version`.
   - Disco C: lleno: puedes mover la ubicación de la imagen en Docker Desktop > Settings > Resources > Advanced >
     "Disk image location", ⚠ verificar en pantalla (con WSL2 la opción puede no aparecer). Respalda antes; no muevas el
     `.vhdx` a mano. Ver [docs/research/docker-desktop-disk-location.md](research/docker-desktop-disk-location.md).
   - Link: https://docs.docker.com/desktop/settings-and-maintenance/settings/
6. [ ] **Power BI Desktop** (gratuito, solo Windows) para la sección 6.
   - Verificar: abre la aplicación. Link de descarga: ⚠ verificar en pantalla (no investigado).

**Orden recomendado:** 0 prerrequisitos, 1 Fabric (T28, T29), 2 `.env` y modo Fabric (T30), 3 URL pública (T31),
4 Copilot Studio (T32), 5 los 30 casos (T33), 6 Power BI (T34), 7 y 8 video y learning log (T35), 9 cierre (T36).
Fabric va primero porque la prueba gratuita dura 60 días y conviene empezarla al comenzar a trabajar. Si Fabric se
bloquea más de media hora, salta a las secciones 3, 4 y 5 en modo local (`DESKPILOT_MODE=local`) y vuelve después.

## 1. Fabric (T28 y T29)

Tiempo: 90 min (45 + 45). Investigación: [docs/research/fabric-access-without-m365-devprogram.md](research/fabric-access-without-m365-devprogram.md).

### 1.1 Conseguir un tenant con Fabric (T28)

7. [ ] **Intentar la prueba gratuita con la cuenta universitaria.**
   - Dónde: portal de Fabric con la cuenta universitaria, menú de la cuenta (Account manager) > "Start trial".
     También puede ofrecerse al crear un elemento de Fabric en "My workspace". ⚠ verificar en pantalla el nombre exacto.
   - Qué obtienes: 60 días, capacidad F4 o F64, 1 TB en OneLake, sin Copilot ni Private Link.
   - Verificar: el botón existe y, al activarlo, el workspace aparece con tipo Trial. Captura:
     `docs/screenshots/01-fabric-trial-activo.png`.
   - Si falla (no aparece "Start trial" o el tenant agotó su límite): pasa a las alternativas 8, 9 o 10.
   - Link: https://learn.microsoft.com/en-us/fabric/fundamentals/fabric-trial
8. [ ] **Alternativa A: pedir al administrador de la universidad.** Que habilite los tenant settings "Users can try
   Microsoft Fabric paid features" y "Users can create Fabric items", o que un capacity admin comparta su capacidad de
   prueba (workspace de tipo Trial). Mensaje sugerido: "Necesito Fabric (Lakehouse y Warehouse) para un proyecto de
   portafolio con datos sintéticos; ¿pueden habilitar la prueba o asignarme un workspace?".
   - Link: https://learn.microsoft.com/en-us/fabric/fundamentals/fabric-trial
9. [ ] **Alternativa B: tenant Entra propio con cuenta personal y Azure free.** Crear un tenant propio, ser administrador
   de Fabric/capacidad ahí, habilitar Fabric y activar la prueba. La documentación consultada no describe cómo crear el
   tenant: **⚠ verificar en pantalla** (ruta inferida, no confirmada). Los invitados B2B no pueden ser capacity admin.
   - Link: https://learn.microsoft.com/en-us/fabric/fundamentals/fabric-trial
10. [ ] **Alternativa C (último recurso): capacidad F SKU en Azure.** Azure portal > Microsoft Fabric > Create Fabric
    Capacity. Requiere suscripción de Azure, permisos Owner/Contributor y el proveedor `Microsoft.Fabric` registrado; se puede
    pausar (suspend/resume). Precio de F2/F4 y si Azure free o los créditos la permiten: **⚠ verificar en pantalla**;
    puede tener costo.
    - Link: https://learn.microsoft.com/en-us/fabric/enterprise/buy-capacity
11. [ ] **Crear workspace, lakehouse y warehouse.**
    - Dónde: workspace de tipo Trial (o F). Lakehouse: Create > Lakehouse (⚠ verificar en pantalla; página de Lakehouse no
      consultada). Warehouse: Create > Warehouse (⚠ verificar en pantalla). Nombres sugeridos: `deskpilot`,
      `deskpilot_lakehouse`, `deskpilot_warehouse`; anótalos, irán en `.env` (sección 2).
    - Verificar: el lakehouse tiene un "SQL analytics endpoint" (se crea solo, ⚠ verificar en pantalla). Captura:
      `docs/screenshots/02-fabric-workspace-items.png`.
    - Si falla: sin capacidad asignada al workspace no se crean los elementos; revisa el paso 7.
    - Link: https://learn.microsoft.com/en-us/fabric/data-warehouse/tutorial-introduction

### 1.2 Cargar los tickets y correr las consultas (T29)

12. [ ] **Subir los CSV al lakehouse.**
    - Archivo: `data/raw/tickets.csv` y `data/raw/sucursales.csv`.
    - Dónde: lakehouse > carpeta **Files**; crea la subcarpeta `raw` y sube ambos CSV (subida de archivos a Files
      confirmada en la investigación; los clics exactos: ⚠ verificar en pantalla). Deben quedar en `Files/raw/`.
    - Link: https://learn.microsoft.com/en-us/fabric/data-engineering/lakehouse-notebook-load-data
13. [ ] **Importar y correr el notebook.**
    - Archivo: `integrations/fabric/notebooks/01_load_tickets_delta.ipynb`.
    - Dónde: workspace > importar notebook (el notebook indica que Fabric reconoce `.ipynb`; ⚠ verificar en pantalla el
      botón). En el notebook, agrega el lakehouse y fíjalo como predeterminado (pin) antes de ejecutar; ejecuta todas las celdas.
    - Verificar: las celdas de chequeo imprimen `OK`, y termina con `tickets` (5,000 filas) y `sucursales` como tablas
      Delta. Captura: `docs/screenshots/03-fabric-notebook-ok.png`.
    - Si falla: el notebook **no se ha ejecutado nunca en Spark** (solo se validó su sintaxis; ⚠ punto abierto T29). Si
      falla `FAILFAST`, revisa que los CSV estén en `Files/raw/` sin editar; si falla el nombre de tabla, revisa que el
      lakehouse sea el predeterminado. Pega el error en el Log del ODD.
    - Link: https://learn.microsoft.com/en-us/fabric/data-engineering/how-to-use-notebook
14. [ ] **Crear `dbo.tickets_nuevos` en el Warehouse.**
    - Archivo: `integrations/fabric/sql/warehouse_ddl.sql`.
    - Dónde: Warehouse > editor de consultas SQL (query editor); pega el contenido completo y ejecútalo una sola vez.
    - Verificar: `SELECT COUNT(*) FROM dbo.tickets_nuevos;` devuelve 0. Captura: `docs/screenshots/04-fabric-warehouse-ddl.png`.
    - Si falla: si dice que la tabla ya existe, está bien (no borra datos). Si falla un tipo, ⚠ punto abierto T29: el DDL
      no se ha ejecutado contra un Warehouse real; anota el error y la línea.
    - Link: https://learn.microsoft.com/en-us/fabric/data-warehouse/tables
15. [ ] **Ejecutar las 10 consultas en el SQL analytics endpoint del lakehouse.**
    - Archivos en `integrations/fabric/sql/`: `01_top_incidencias.sql`, `02_sla_por_area.sql`, `03_sla_por_sucursal.sql`,
      `04_horas_perdidas_por_categoria.sql`, `05_tickets_automatizables.sql`, `06_tendencia_mensual.sql`,
      `07_efecto_quincena.sql`, `08_local_vs_foranea.sql`, `09_distribucion_por_canal.sql`, `10_backlog_por_prioridad.sql`.
    - Dónde: lakehouse > cambia a la vista "SQL analytics endpoint" (⚠ verificar en pantalla) > nueva consulta SQL; pega y
      ejecuta una por una.
    - Verificar: compara contra las cifras de [docs/business-case.md](business-case.md): la 07 da factor de quincena 1.90 y
      la 08 da SLA local 79.50% contra 60.57% foráneo. Captura de cada resultado: `docs/screenshots/05-fabric-query-01.png`
      a `docs/screenshots/05-fabric-query-10.png` (o una sola `05-fabric-queries.png`).
    - Si falla: **⚠ puntos abiertos T29**: (a) la 07 convierte `datetime2` a texto con `CAST(... AS VARCHAR(19))` y toma
      las posiciones 9 y 10 como día; si Fabric devuelve el día incorrecto, anota el valor de `CAST(fecha_apertura AS
      VARCHAR(19))` para un ticket; (b) la precisión real de `datetime2` que expone Delta. Si una cifra difiere del caso de negocio, **no la cambies**:
      anótala en el Log.
    - Link: https://learn.microsoft.com/en-us/fabric/data-warehouse/connectivity

## 2. `.env` y modo Fabric (T30)

Tiempo: 30 min. Código: `src/utils/fabric.py`, `src/utils/config.py`, `scripts/check_fabric.py`.

16. [ ] **Copiar el host del SQL endpoint y del Warehouse.**
    - Dónde: Settings del lakehouse (SQL analytics endpoint) y del Warehouse > página "SQL connection string"; copia solo el
      host (`<id>.datawarehouse.fabric.microsoft.com`). Exige rol Contributor o superior en el workspace.
    - Link: https://learn.microsoft.com/en-us/fabric/data-warehouse/how-to-connect
17. [ ] **Crear `.env` desde la plantilla y llenarlo.**
    - Copiar: `Copy-Item .env.example .env` (si ya existe, edítalo).
    - Variables (de `.env.example`; pega host sin `tcp:`, sin puerto y sin `;`):

      | Variable | Valor |
      | --- | --- |
      | `DESKPILOT_API_KEY` | `.venv\Scripts\python -c "import secrets;print(secrets.token_urlsafe(32))"` (16+ caracteres) |
      | `DESKPILOT_MODE` | `fabric` |
      | `LLM_PROVIDER` | `none` (sin llaves de pago) |
      | `FABRIC_SQL_ENDPOINT` | host del SQL analytics endpoint del lakehouse |
      | `FABRIC_LAKEHOUSE_DATABASE` | nombre del lakehouse |
      | `FABRIC_WAREHOUSE_ENDPOINT` | host del Warehouse |
      | `FABRIC_WAREHOUSE_DATABASE` | nombre del Warehouse |
      | `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET` | las tres, o todas vacías si usas `az login` |

    - Verificar: `git status` no muestra `.env`.
    - Si falla: `check_fabric` sale con código 2 y nombra las variables que faltan (no imprime sus valores).
18. [ ] **Correr `check_fabric`.**
    - Copiar: `.venv\Scripts\python -m scripts.check_fabric` y luego
      `.venv\Scripts\python -m scripts.check_fabric --write-test` (inserta un ticket de prueba en `dbo.tickets_nuevos` y lo borra).
    - Verificar: sale 0 y dice `all checks passed`; el conteo de `dbo.tickets` debe ser 5,000. Captura (sin datos
      secretos): `docs/screenshots/06-check-fabric.png`.
    - Si falla: código 1 indica qué chequeo falló (variables, driver, token, SQL endpoint, Warehouse, escritura). Casos
      típicos en la tabla "Si falla". **⚠ no verificado:** el scope `https://database.windows.net/.default` y todo el
      script se probaron con dobles de prueba, nunca contra un Fabric real.
    - Link: https://learn.microsoft.com/en-us/fabric/data-warehouse/entra-id-authentication
19. [ ] **Levantar la API en modo Fabric.**
    - Copiar: `.venv\Scripts\python main.py serve` (lee `.env`; escucha en el puerto 8000 de `api.port`).
    - Verificar, en otra terminal: `curl.exe http://localhost:8000/health` devuelve 200.
    - Si falla: revisa que `DESKPILOT_API_KEY` tenga 16+ caracteres y que el puerto 8000 esté libre. Alternativa modo local:
      `DESKPILOT_MODE=local` y, opcional, Docker según el README.

## 3. URL pública HTTPS (T31)

Tiempo: 20 min. Investigación: [docs/research/public-https-url-options.md](research/public-https-url-options.md).
Deja la API del paso 19 corriendo. Copilot Studio necesita una URL pública; los túneles son solo para la demo.

20. [ ] **Abrir un túnel (elige uno).**
    - **A. Microsoft Dev Tunnels (recomendado).**
      Copiar: `winget install Microsoft.devtunnel`, luego `devtunnel user login` y
      `devtunnel host -p 8000 --allow-anonymous`. La URL tiene la forma `https://<tunnel_id>-8000.<region>.devtunnels.ms/`.
      Hace falta acceso anónimo porque Copilot Studio no puede iniciar sesión con tu cuenta. Si `host` no acepta
      `--allow-anonymous`: ⚠ verificar con `devtunnel host -h` y `devtunnel access create <id> -p 8000 --anonymous`.
      Límites de tiempo y número de túneles: ⚠ verificar en pantalla.
      Link: https://learn.microsoft.com/en-us/azure/developer/dev-tunnels/get-started
    - **B. Cloudflare quick tunnel (plan B, sin cuenta).** `cloudflared tunnel --url http://localhost:8000`. La URL
      `*.trycloudflare.com` cambia en cada ejecución; sin garantía de disponibilidad; "solo pruebas y desarrollo".
      Instalación en Windows: ⚠ verificar en pantalla.
      Link: https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/
    - **C. ngrok free (tercera opción).** `ngrok http 8000`; requiere cuenta y authtoken (comando del token: ⚠ verificar en
      pantalla). Límites gratuitos: 1 GB al mes y 20,000 peticiones HTTP al mes.
      Link: https://ngrok.com/docs/pricing-limits/free-plan-limits
    - Si falla: prueba otra opción; la `API key` es la única barrera mientras el túnel sea anónimo.
    - Link de seguridad: https://learn.microsoft.com/en-us/azure/developer/dev-tunnels/security
21. [ ] **Comprobar la URL con `check_public_url`.**
    - Copiar (reemplaza la URL; la key se lee de `DESKPILOT_API_KEY` en `.env` o del entorno, y no se imprime):
      `.venv\Scripts\python -m scripts.check_public_url https://<host-del-tunel>`
    - Verificar: sale 0. El script confirma https, `/health` 200, `/buscar_solucion` sin key 401 y con key 200 con citas
      en español e inglés, y que `/docs`, `/redoc` y `/openapi.json` dan 404. Captura: `docs/screenshots/07-check-public-url.png`.
    - Si falla: 401 con key = la key del `.env` no coincide con la del proceso `serve`; 404 en todo = el túnel apunta a
      otro puerto; timeout = sube `--timeout`. Las advertencias (host del openapi, latencia) no bloquean.
22. [ ] **Exportar el OpenAPI con el host del túnel.**
    - Archivo: `integrations/copilot_studio/openapi.json`.
    - Copiar (solo el host, sin `https://`): `.venv\Scripts\python main.py export-openapi --host <host-del-tunel>`
    - Verificar: repite el paso 21; ya no avisa del host. El archivo pesa menos de 1 MB.
    - Si falla: sin `--host` queda el marcador `your-deskpilot-host.example.com`.
23. [ ] **Rotar la key al terminar la demo** (sección 9). Genera una nueva con el comando del paso 17, ponla en `.env`,
    reinicia `serve` y actualiza la conexión en Copilot Studio. Cierra el túnel con Ctrl+C. Borrar un Dev Tunnel con
    `devtunnel delete`: ⚠ verificar el comando.

## 4. Copilot Studio (T32)

Tiempo: 75 min. Investigaciones: [acceso y pasos](research/copilot-studio-access-and-steps.md),
[requisitos OpenAPI](research/copilot-studio-openapi-requirements.md), [límites](research/copilot-studio-agent-limits.md).

24. [ ] **Entrar con la cuenta universitaria.**
    - Dónde: https://copilotstudio.microsoft.com con la cuenta de trabajo o escuela (un correo personal se rechaza). Empieza
      una prueba gratuita individual: permite crear y probar en el panel de prueba, pero **no publicar**.
    - Link: https://learn.microsoft.com/en-us/microsoft-copilot-studio/requirements-licensing-subscriptions
    - Si falla: el administrador pudo desactivar el autoservicio; pídele que lo habilite. Publicar a canales exige
      suscripción standalone. Si el tenant no permite nada: graba el panel de prueba como evidencia (sección 7).
25. [ ] **Crear el agente.**
    - Dónde: Home > describe el agente en lenguaje natural (hasta 1,024 caracteres) > se abre Overview; ajusta nombre,
      descripción e instrucciones. Idioma principal: español (no se puede cambiar después). El inglés se agrega en
      Settings > Languages > Add language; que ES y EN estén soportados: ⚠ verificar en pantalla.
    - Texto sugerido: "Agente de soporte de TI nivel 1 de Banco Altiplano (ficticio). Resuelve incidencias con la base de
      conocimiento y crea tickets."
    - Link: https://learn.microsoft.com/en-us/microsoft-copilot-studio/fundamentals-get-started y
      https://learn.microsoft.com/en-us/microsoft-copilot-studio/multilingual
26. [ ] **Pegar las instrucciones.**
    - Archivo: `integrations/copilot_studio/instructions.md` (2,478 bytes). Dónde: Overview > Instructions. Límite de
      caracteres del campo: ⚠ verificar en el contador de pantalla.
    - Verificar: el texto pega completo sin recortes. Captura: `docs/screenshots/08-copilot-agente-overview.png`.
27. [ ] **Agregar knowledge (opcional).**
    - Archivos: `data/knowledge_base/KB-001-*.md` a `KB-015-*.md`. Dónde: Overview > Knowledge > Add > Add to agent. La guía
      oficial solo demuestra una URL pública. **Subir archivos propios: ⚠ verificar en pantalla** (no confirmado). La
      respuesta con citas ya viene de la herramienta `buscar_solucion`; si no puedes subirlos, omite este paso.
28. [ ] **Agregar la herramienta REST API.**
    - Archivo: `integrations/copilot_studio/openapi.json` (generado en el paso 22). Descripciones de cada herramienta:
      `integrations/copilot_studio/tools.md`.
    - Dónde: Agent > Tools > Add tool > New tool > REST API > sube el `openapi.json` (debe ser Swagger 2.0 en JSON; la
      función está en preview) > descripción > Authentication: **API key** > Parameter label `X-API-Key`, Parameter name
      `X-API-Key`, Parameter location **Header** > elige las 4 operaciones (`buscar_solucion`, `crear_ticket`,
      `consultar_estado_ticket`, `metricas_area`) > revisa nombres y descripciones (no dejes descripciones en blanco) > Next >
      Create connection (pega aquí la API key de tu `.env`) > Add and configure.
    - Verificar: aparecen las 4 herramientas en Tools. Captura: `docs/screenshots/09-copilot-herramienta-rest.png`.
    - Si falla: ver "Si falla" (YAML, https, tamaño, key). Que `https` sea obligatorio y si acepta `.yaml`: ⚠ verificar en
      pantalla.
    - Link: https://learn.microsoft.com/en-us/microsoft-copilot-studio/agent-extend-action-rest-api
29. [ ] **MCP (opcional).** Procedimiento no confirmado en las páginas consultadas: **⚠ verificar en pantalla** (busca en
    Tools > Add tool una opción de Model Context Protocol). El servidor MCP del repo se arranca con
    `.venv\Scripts\python main.py mcp --transport http`; la REST API ya cubre la demo, por lo que este paso puede omitirse.
30. [ ] **Crear los temas.**
    - Archivos: `integrations/copilot_studio/topics/` (8 `.md`: `buscar-solucion`, `crear-ticket`, `consultar-estado`,
      `metricas-area`, `escalamiento-obligatorio`, `no-lo-se`, `saludo-fuera-de-alcance`, `datos-sensibles`). Cada uno trae
      descripción y frases de activación ES/EN (máximo 200 por tema).
    - Dónde: crea cada tema y copia descripción y frases (clics: ⚠ verificar en pantalla). Para escalamiento usa el tema del
      sistema **Escalate** (se puede apagar, no borrar) con el texto de `integrations/copilot_studio/escalation.md`; no hay
      transferencia a una persona real en una cuenta de prueba.
    - Link: https://learn.microsoft.com/en-us/microsoft-copilot-studio/authoring-system-topics
31. [ ] **Probar con las conversaciones de diseño.**
    - Archivo: `integrations/copilot_studio/test-conversations.md` (CT-01 a CT-18).
    - Dónde: panel "Test your agent"; el icono "Start new test session" reinicia la conversación.
    - Verificar: cumple los criterios "Debe" y ningún "No debe" de al menos CT-01 (resuelto), CT-03 (ticket) y CT-04
      (fraude, P1). Capturas: `docs/screenshots/10-copilot-prueba-es.png`, `11-copilot-prueba-en.png` y `12-copilot-escalamiento.png`
      (todas en `docs/screenshots/`).
    - Si falla: el agente no llama a la herramienta: revisa que Authentication y la conexión estén bien y que las instrucciones
      se pegaron completas.

## 5. Los 30 casos en Copilot Studio (T33)

Tiempo: 60 min. Con la API en modo Fabric, `crear_ticket` escribe tickets reales en `dbo.tickets_nuevos`.

32. [ ] **Correr los 30 casos en el panel de prueba.**
    - Archivo: `tests/eval/cases.csv` (columnas `id`, `pregunta`, `esperado`). Pega cada `pregunta` en una sesión nueva
      ("Start new test session"). `esperado` indica: `articulo:KB-xxx` (cita ese artículo), `rechazo` (no inventa; dice que no
      sabe o ofrece ticket), `escalamiento` (P1 y aviso de que lo atiende una persona), `ticket:categoria=...;prioridad=...`
      (crea el ticket con esa clasificación) y `seguridad` (no repite el dato sensible y avisa).
    - Verificar: anota por caso lo que respondió y si pasó. En EV-16 el modo local falla de forma documentada; en Copilot
      Studio puede variar. Captura de 2 o 3 casos: `docs/screenshots/13-casos-ev-xx.png`.
    - Si falla: no ajustes el caso para que pase; registra `no` y una nota.
33. [ ] **Registrar en la tabla T32.**
    - Archivo: `docs/testing-procedure.md`, sección "Resultados en Copilot Studio (T32)". Reemplaza `PENDIENTE` por la respuesta
      resumida en "Obtenido en Copilot Studio" y por `sí` o `no` en la columna "Pasó (sí/no)" (solo esos valores; el script
      cuenta `sí`, `si` y `no`). No borres filas ni cambies ID, pregunta o esperado. Quita la línea "PENDIENTE (manual)" solo
      cuando estén los 30.
    - Verificar: `.venv\Scripts\python -m scripts.update_readme_results --dry-run` muestra la línea "Copilot Studio (T32, medido
      a mano)" con N de M casos.
34. [ ] **Actualizar el README.**
    - Copiar: `.venv\Scripts\python -m scripts.update_readme_results` (solo cambia el bloque entre `<!-- RESULTS:START -->` y
      `<!-- RESULTS:END -->`; es idempotente).
    - Verificar: `git diff README.md` solo toca ese bloque. Si sale código 2: faltan los marcadores o el
      `tests/eval/results.summary.json`; corre `.venv\Scripts\python main.py eval`.
35. [ ] **Limpiar los tickets de prueba (si usaste modo Fabric).** Los casos EV-19 a EV-27 crean tickets reales. Bórralos en el
    editor SQL del Warehouse con `DELETE FROM dbo.tickets_nuevos WHERE ...` (filtra por fecha o por los folios que viste);
    no existe un script para esto. No lo hagas si quieres mostrarlos en Power BI.

## 6. Power BI (T34)

Tiempo: 45 min. Investigación: [docs/research/power-bi-fabric-connection.md](research/power-bi-fabric-connection.md).
Para la demo basta Power BI Desktop con capturas; no publiques al servicio salvo que tengas licencia Pro, PPU o la prueba
individual.

36. [ ] **Conectar Power BI Desktop al lakehouse.**
    - Dónde: Power BI Desktop > el SQL analytics endpoint es una fuente nativa (panel de datos / OneLake catalog) > elige el
      lakehouse, tablas `tickets` y `sucursales`, modo **Import** o DirectQuery. Con el conector SQL Server: servidor = cadena
      "SQL connection string" (paso 16), base de datos = nombre del lakehouse (si no, se conecta a `master`), autenticación
      Microsoft Entra ID. Que baste una licencia Free para esto: ⚠ verificar en pantalla.
    - Si falla: el modelo Direct Lake (OneLake catalog > Connect) no funciona con licencia Free y exige XMLA habilitado.
    - Link: https://learn.microsoft.com/en-us/fabric/data-warehouse/how-to-connect
37. [ ] **Armar el reporte con KPIs.** Visuales sugeridos, con las cifras de [docs/business-case.md](business-case.md): tarjetas de
    total de tickets y SLA; barras de tickets por categoría; SLA local contra foráneo; tendencia mensual (consulta 06).
    - Verificar: las cifras coinciden con las consultas del paso 15. Capturas: `docs/screenshots/14-powerbi-reporte.png` y
      `docs/screenshots/15-powerbi-conexion.png` (sin cadena de conexión visible).
    - Link: https://learn.microsoft.com/en-us/fabric/enterprise/licenses (licencias para publicar)

## 7. Video demo (T35)

Tiempo: 40 min junto con la sección 8. Herramienta de grabación y hosting (YouTube no listado o Loom): ⚠ verificar en
pantalla. S22 pide 2 a 3 minutos; este guion es de 3 a 5 con escenas marcadas `[opcional]` para recortar.

38. [ ] **Grabar siguiendo este guion.** Antes de grabar: oculta la API key y el host del túnel (o usa uno que vayas a borrar).
    - [ ] Escena 1 (0:00 a 0:20): qué es DeskPilot AI y el problema (39.92% de tickets repetitivos, ver business-case).
    - [ ] Escena 2 (0:20 a 1:00): chat en Copilot Studio, caso resuelto con cita (por ejemplo CT-01 o EV-04).
    - [ ] Escena 3 (1:00 a 1:30): caso en inglés (EV-03 o CT-02).
    - [ ] Escena 4 (1:30 a 2:10): ticket creado con folio, prioridad y SLA (CT-03).
    - [ ] Escena 5 (2:10 a 2:40): escalamiento por fraude, P1 (CT-04 o EV-19).
    - [ ] Escena 6 (2:40 a 3:20): datos sensibles no repetidos (EV-28) `[opcional]`.
    - [ ] Escena 7 (3:20 a 4:00): Fabric y consultas SQL, o la salida de `check_fabric` `[opcional]`.
    - [ ] Escena 8 (4:00 a 4:30): reporte de Power BI `[opcional]`.
    - [ ] Escena 9 (4:30 a 5:00): resultados (29/30 local, tabla T32) y cierre con el repo.
    - Verificar: el video se ve sin secretos y el enlace abre sin iniciar sesión.
39. [ ] **Capturas necesarias** (todas en `docs/screenshots/`, PNG, sin secretos): `01-fabric-trial-activo.png`,
    `02-fabric-workspace-items.png`, `03-fabric-notebook-ok.png`, `04-fabric-warehouse-ddl.png`, `05-fabric-queries.png`
    (o `05-fabric-query-01.png` a `10`), `06-check-fabric.png`, `07-check-public-url.png`, `08-copilot-agente-overview.png`,
    `09-copilot-herramienta-rest.png`, `10-copilot-prueba-es.png`, `11-copilot-prueba-en.png`, `12-copilot-escalamiento.png`,
    `13-casos-ev-xx.png`, `14-powerbi-reporte.png`, `15-powerbi-conexion.png`.

## 8. Learning log y link del video (T35)

40. [ ] **Completar el learning log.**
    - Archivo: `docs/learning-log.md`. Llena rutas o cursos con enlace, insignias con su enlace de verificación y notas por
      fecha, **solo lo que realmente hiciste**, con fecha. No inventes logros.
    - Verificar: no queda ninguna fila `(pendiente)` que no sea cierta.
41. [ ] **Poner el link del video en el README.**
    - Archivo: `README.md`, sección "Video": reemplaza la línea `PLACEHOLDER: enlace al video de demo...` por el enlace. Verifica abriéndolo en una ventana privada.

## 9. Cierre (T36)

Tiempo: 20 min (estimación; T36 la hace docs-writer con tus resultados, aquí solo tu parte).

42. [ ] **Revisión final de resultados.**
    - Copiar: `.venv\Scripts\python -m scripts.update_readme_results --check`.
    - Verificar: sale 0 (README al día). Si sale 1, corre sin `--check` y revisa `git diff README.md`.
43. [ ] **Entregar la evidencia.** Pasa a la sesión: tabla T32 llena, capturas de `docs/screenshots/`, link del video y las notas
    de lo que no funcionó. De ahí se actualizan README, business-case y testing-procedure (T36).
44. [ ] **Push por PR.** Rama `feat/t36-evidencia-real`; nunca push directo a `main`: `git push -u origin feat/t36-evidencia-real` y
    abre el PR en GitHub (CI verde: ruff, mypy, pytest, eval-smoke, docker-build). Verifica que `.env` y claves no estén en el diff.
45. [ ] **Tag `v0.1.0`.** Según el roadmap lo crea la tarea T27 (`fix/t27-correcciones-t26`) tras la revisión final T26 y con la suite
    completa verde; confirma que T26 y T27 están en `mergeada` antes. Copiar: `git tag v0.1.0` y `git push origin v0.1.0`.
46. [ ] **Rotar la key** (paso 23), cerrar el túnel y revisar que `git status` esté limpio.

## Si falla

| # | Problema probable | Causa y qué hacer |
| --- | --- | --- |
| 1 | No aparece "Start trial" en Fabric | El administrador desactivó el tenant setting o el tenant agotó su límite. Pedir habilitarlo, usar un trial compartido o un tenant propio (pasos 8 y 9). |
| 2 | `check_fabric` sale 2 | Faltan variables `FABRIC_*` o `AZURE_*` (deben ir las tres de Azure juntas o ninguna). Revisa `.env`. |
| 3 | `check_fabric` falla en el driver | ODBC Driver 18 no instalado (el 17 no sirve). Instálalo y repite (paso 3). |
| 4 | `check_fabric` falla en el token | Sin `az login` o el tenant/service principal no tiene acceso. Inicia sesión con la cuenta del workspace; con service principal puede requerir al administrador (⚠ scope `database.windows.net/.default` sin probar). |
| 5 | Falla SQL endpoint o Warehouse | Falta el rol Contributor, no corrió el notebook (no existe `dbo.tickets`) o no se creó `dbo.tickets_nuevos` (paso 14). |
| 6 | El notebook falla en Spark | No se ejecutó nunca en Spark. Revisa `Files/raw/` y el lakehouse predeterminado; guarda el error en el Log. |
| 7 | La consulta 07 da un día o factor raro | ⚠ punto abierto: conversión `datetime2` a texto. Compara con 1.90 de business-case y anota el valor de `CAST(fecha_apertura AS VARCHAR(19))`. |
| 8 | `check_public_url` da 401, 404 o timeout | Key distinta entre `.env` y el proceso `serve`, puerto equivocado del túnel o túnel caído. Reinicia `serve` y el túnel. |
| 9 | Copilot Studio rechaza el OpenAPI | Debe ser Swagger 2.0 en JSON, menos de 1 MB y `host` correcto. Vuelve a exportar con `export-openapi --host`; descripciones en blanco o `.yaml`: ⚠ verificar en pantalla. |
| 10 | Copilot Studio no deja publicar o crear el agente | La prueba gratuita solo permite probar; publicar exige suscripción. Usa el panel de prueba y grábalo como evidencia (secciones 4 y 7). |

## Tiempo estimado por sección

| Sección | Tareas | Minutos |
| --- | --- | --- |
| 0 Prerrequisitos | - | 15 a 20 (estimación) |
| 1 Fabric | T28 y T29 | 90 |
| 2 `.env` y modo Fabric | T30 | 30 |
| 3 URL pública | T31 | 20 |
| 4 Copilot Studio | T32 | 75 |
| 5 Los 30 casos | T33 | 60 |
| 6 Power BI | T34 | 45 |
| 7 y 8 Video y learning log | T35 | 40 |
| 9 Cierre | T36 | 20 (estimación) |
| **Total** | | **375 a 380 min, unas 6 h** (los de T28 a T35 salen del roadmap: 360 min) |
