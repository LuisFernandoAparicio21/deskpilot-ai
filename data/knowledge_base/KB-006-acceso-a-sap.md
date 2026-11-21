---
id: KB-006
titulo: No puedo entrar a SAP o no tengo acceso a una transacción
categoria: Accesos
subcategoria: Acceso a SAP
idioma: es
fecha_actualizacion: 2026-11-01
palabras_clave:
  - SAP
  - SAP GUI
  - transacción
  - rol de SAP
  - sin autorización
  - usuario SAP bloqueado
  - SAP access
  - authorization error
---

# No puedo entrar a SAP o no tengo acceso a una transacción

## Síntoma

SAP GUI muestra "Usuario bloqueado", "Nombre o clave de acceso incorrectos" o, ya dentro del sistema, "No tiene autorización para la transacción". También aplica si SAP GUI se cierra al abrir la conexión o la lista de sistemas aparece vacía.

## Causa

El usuario de SAP es independiente del usuario de Windows: tiene su propia contraseña y se bloquea por intentos fallidos. La falta de autorización ocurre cuando tu puesto cambió o el rol de SAP no se asignó. Si SAP GUI se cierra, suele ser la caché local dañada.

## Pasos

1. Verifica que estás eligiendo el sistema correcto en SAP Logon, por ejemplo producción y no pruebas.
2. Si SAP indica usuario bloqueado, espera 10 minutos y entra con un solo intento.
3. Para restablecer la contraseña de SAP, usa la opción **SAP** del Portal de Autoservicio con tu número de empleado. No compartas tu contraseña con nadie, ni siquiera con soporte.
4. Si te falta una transacción, anota su código y el mensaje exacto con una captura de pantalla.
5. Pide a tu jefe inmediato que apruebe el rol en el portal de solicitudes de acceso.
6. Si SAP GUI se cierra al abrir, ciérralo, borra la carpeta de caché de SAP GUI en tu perfil y vuelve a abrirlo.

## Cuándo escalar

- Escala como **P2** si no puedes entrar a SAP y tu operación diaria depende de él.
- Escala como **P3** si te falta una transacción, pero puedes avanzar con otras tareas.
- Escala como **P4** si solo necesitas un rol nuevo por cambio de puesto, ya aprobado por tu jefe.
- Escala como **P1** si SAP no responde para toda la sucursal o el área.
