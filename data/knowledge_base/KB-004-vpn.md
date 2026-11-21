---
id: KB-004
titulo: La VPN no conecta o se desconecta sola
categoria: Conectividad
subcategoria: VPN
idioma: es
fecha_actualizacion: 2026-11-01
palabras_clave:
  - VPN
  - red privada
  - conexión remota
  - trabajo remoto
  - no conecta la VPN
  - certificado vencido
  - VPN disconnected
  - remote access
---

# La VPN no conecta o se desconecta sola

## Síntoma

Al trabajar fuera de la sucursal, el cliente de VPN muestra "No se pudo establecer la conexión", "Certificado no válido" o se desconecta cada pocos minutos. Sin VPN no abren el correo interno, las carpetas compartidas ni las aplicaciones del banco.

## Causa

Las causas más frecuentes son un cliente de VPN desactualizado, el certificado del equipo vencido, la contraseña de red recién cambiada o una conexión a internet inestable, como el wifi público de un hotel o una red con portal de acceso.

## Pasos

1. Confirma que tienes internet: abre un sitio público en el navegador.
2. Si estás en una red con portal de acceso, como hotel o aeropuerto, acepta primero sus condiciones.
3. Cierra el cliente de VPN por completo y vuelve a abrirlo.
4. Revisa en el cliente si hay una actualización pendiente e instálala desde el Centro de Software.
5. Si cambiaste tu contraseña de red hoy, reinicia el equipo antes de conectar.
6. Conéctate de nuevo seleccionando el perfil **Altiplano-Corporativo**.
7. Si aparece "Certificado no válido", conecta el equipo a la red de una sucursal para que renueve el certificado de forma automática.
8. Si la conexión se cae seguido, prueba con la red de tu celular para descartar tu proveedor de internet.

## Cuándo escalar

- Escala como **P2** si no puedes conectarte desde ninguna red y tu trabajo depende de la VPN.
- Escala como **P3** si la VPN se desconecta de forma intermitente, pero puedes trabajar.
- Escala como **P1** si varios usuarios reportan que la VPN no conecta al mismo tiempo, porque puede ser una falla general del servicio.
- Incluye en el ticket el mensaje de error exacto y la hora del último intento.
