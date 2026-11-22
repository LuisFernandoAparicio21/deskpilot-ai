# Acceso a Microsoft Fabric sin el Microsoft 365 Developer Program

Consulta: 2026-11-22. Rama: chore/t25-manual-steps.

## Pregunta
¿Cómo puede una persona con cuenta universitaria (Entra de la universidad, posibles restricciones de tenant) obtener Fabric (Lakehouse + Warehouse + SQL endpoint) sin depender del M365 Developer Program?

## Respuesta
- (a) Prueba gratuita: 60 días, capacidad F4 (4 CU) o F64 (64 CU), con Power BI Individual Trial; 1 TB en OneLake; sin Copilot, AI experiences ni Private Link. Cualquier usuario del tenant puede iniciarla (Cuenta > Start trial, o al crear un item Fabric en My Workspace) si el admin lo permite y el tenant no agotó su límite de trials. Requiere licencia Fabric (Free) o Power BI. Si el admin la deshabilita (tenant setting "Users can try Microsoft Fabric paid features" / "Users can create Fabric items"), no aparece "Start trial". Alternativas: que otro capacity admin comparta su trial (workspace tipo Trial) o que el admin del tenant habilite el setting.
- Al vencer: se revoca la capacidad, items no-Power BI quedan inactivos y el contenido se conserva 7 días en OneLake; reactivable asignando a capacidad F/P de pago. Otra prueba posterior no está garantizada.
- (b) Tenant propio: la documentación consultada no describe cómo crear el tenant, solo que la prueba depende de los tenant settings y que la capacidad se provisiona en el tenant de Entra asociado a la suscripción. Ruta inferida (⚠ verificar en pantalla): crear un tenant Entra propio con cuenta personal Microsoft + Azure free account, ser Fabric/Capacity admin allí, habilitar Fabric y activar el trial. Los usuarios B2B (invitados) no pueden ser capacity admin.
- (c) Capacidad F SKU: se compra en Azure portal > Microsoft Fabric > Create Fabric Capacity. Requiere suscripción Azure en el tenant, permisos (Owner/Contributor o rol con `Microsoft.Fabric/capacities/read|write|suspend/action|resume/action`), proveedor `Microsoft.Fabric` registrado, región soportada y cuota de CU. Hay `suspend`/`resume` (pausa posible). Precio por hora de F2/F4, facturación en pausa y si una Azure free account/créditos permiten F SKU: ⚠ verificar en pantalla (no confirmado en las páginas consultadas).
- (d) Pasos de alto nivel (tutorial de Warehouse): 1) habilitar Fabric en el tenant, 2) crear workspace (tipo Trial o F), 3) crear Warehouse, 4) ingerir datos con pipeline, 5) consultar con SQL query editor. Lakehouse: se crea en el mismo workspace (Create > Lakehouse), expone SQL analytics endpoint automático (⚠ verificar en pantalla; página de Lakehouse no consultada). Carga: pipeline/dataflow, shortcuts o subida de archivos CSV a Files del Lakehouse.

## Decisión recomendada
1) Intentar primero el trial con la cuenta universitaria (Account manager > Start trial); si no aparece el botón, pedir al admin habilitar el setting o compartir un trial. 2) Si no es posible, tenant Entra propio (cuenta personal + Azure free) y trial ahí. 3) F2 pausable en Azure solo como último recurso, tras ⚠ verificar precios.

## Fuentes (3)
- Fabric trial capacity: https://learn.microsoft.com/en-us/fabric/fundamentals/fabric-trial (2026-11-22)
- Buy Fabric capacity Azure SKUs: https://learn.microsoft.com/en-us/fabric/enterprise/buy-capacity (2026-11-22)
- Data Warehouse Tutorial: Introduction: https://learn.microsoft.com/en-us/fabric/data-warehouse/tutorial-introduction (2026-11-22)
