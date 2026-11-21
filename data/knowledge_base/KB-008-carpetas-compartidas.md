---
id: KB-008
titulo: No puedo abrir una carpeta compartida o una unidad de red
categoria: Conectividad
subcategoria: Carpetas compartidas
idioma: es
fecha_actualizacion: 2026-11-01
palabras_clave:
  - carpeta compartida
  - unidad de red
  - unidad mapeada
  - acceso denegado
  - permisos de carpeta
  - disco de red
  - shared folder
  - network drive
---

# No puedo abrir una carpeta compartida o una unidad de red

## Síntoma

La unidad de red aparece con una X roja en el Explorador de archivos, Windows muestra "No se puede acceder a la ruta" o "No tiene permiso para acceder a esta carpeta". En otros casos la carpeta abre, pero no permite guardar ni modificar archivos.

## Causa

La unidad se desconecta cuando el equipo arranca sin red, cuando se trabaja fuera de la sucursal sin VPN o después de un cambio de contraseña. El acceso denegado ocurre cuando el usuario no pertenece al grupo de seguridad de la carpeta, por ejemplo tras un cambio de área.

## Pasos

1. Verifica que tienes red: abre la intranet del banco en el navegador.
2. Si estás fuera de la sucursal, conéctate primero a la VPN.
3. En el Explorador de archivos, da doble clic en la unidad con X roja para reconectarla.
4. Si no reconecta, cierra sesión en Windows y vuelve a entrar.
5. Si la unidad desapareció, da clic derecho en **Este equipo > Conectar unidad de red** y escribe la ruta que te indique tu jefe.
6. Si aparece "No tiene permiso", pide a tu jefe que apruebe tu alta en el grupo de la carpeta en el portal de solicitudes de acceso.
7. Después de la aprobación, cierra sesión y vuelve a entrar para que se apliquen los permisos.

## Cuándo escalar

- Escala como **P2** si no puedes abrir información indispensable para operar hoy.
- Escala como **P3** si la unidad falla, pero puedes trabajar con copias locales o con otra ruta.
- Escala como **P4** si solo necesitas acceso a una carpeta nueva.
- Escala como **P1** si toda la sucursal perdió acceso a las carpetas compartidas.
