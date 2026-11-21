---
id: KB-012
titulo: Outlook no envía, no recibe o no sincroniza el correo
categoria: Comunicaciones
subcategoria: Correo
idioma: es
fecha_actualizacion: 2026-11-01
palabras_clave:
  - correo
  - Outlook
  - correo electrónico
  - buzón lleno
  - no recibo correos
  - bandeja de salida
  - email not syncing
  - mailbox full
---

# Outlook no envía, no recibe o no sincroniza el correo

## Síntoma

Outlook muestra "Desconectado" o "Intentando conectar" en la barra inferior, los correos se quedan en la Bandeja de salida, no llegan correos nuevos o aparece el aviso "Su buzón está lleno". También puede abrir con lentitud o cerrarse solo.

## Causa

Las causas más comunes son el buzón lleno, un perfil de Outlook dañado, archivos adjuntos demasiado grandes, la sesión sin conexión a la red del banco o el modo **Trabajar sin conexión** activado por error.

## Pasos

1. Revisa en la pestaña **Enviar y recibir** que el botón **Trabajar sin conexión** no esté activado.
2. Confirma que tienes red; si estás fuera de la sucursal, conéctate a la VPN.
3. Si un correo se queda en la Bandeja de salida, revisa que sus adjuntos no superen 20 MB.
4. Si aparece "Buzón lleno", vacía la carpeta de Elementos eliminados y archiva correos antiguos.
5. Cierra Outlook por completo y vuelve a abrirlo.
6. Si sigue sin sincronizar, abre Outlook en la web del banco para confirmar que el buzón funciona.
7. Si en la web sí funciona, el problema es tu perfil local: solicita la reconstrucción del perfil de Outlook.

## Cuándo escalar

- Escala como **P2** si no puedes enviar ni recibir correos y los necesitas para operar.
- Escala como **P3** si Outlook falla, pero puedes usar el correo desde la web.
- Escala como **P1** si el correo no funciona para toda la sucursal.
- Si recibes un correo sospechoso que pide datos o te invita a abrir un enlace, no lo abras: repórtalo de inmediato a Seguridad de la Información como **P1**.
