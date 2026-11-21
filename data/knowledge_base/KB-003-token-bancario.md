---
id: KB-003
titulo: El token bancario no genera claves válidas
categoria: Accesos
subcategoria: Token bancario
idioma: es
fecha_actualizacion: 2026-11-01
palabras_clave:
  - token
  - token bancario
  - token físico
  - clave dinámica
  - clave rechazada
  - token desincronizado
  - token vencido
  - token not working
  - OTP
---

# El token bancario no genera claves válidas

> **Advertencia:** No compartas las claves de tu token con nadie, ni siquiera con soporte. El token es personal: nadie de Banco Altiplano te pedirá una clave dinámica ni una foto del dispositivo.

## Síntoma

El sistema rechaza la clave dinámica del token físico con mensajes como "Clave inválida" o "Token no sincronizado". En otros casos la pantalla del token aparece en blanco, muestra un aviso de batería baja o no enciende.

## Causa

El reloj interno del token se desfasa con el servidor después de varios rechazos seguidos o de mucho tiempo sin usarlo. También ocurre cuando el token llegó a su fecha de vencimiento o se agotó su batería, que no es reemplazable.

## Pasos

1. Revisa que la pantalla del token encienda y que no muestre aviso de batería baja.
2. Espera a que el token cambie de clave y usa la nueva; no repitas una clave ya rechazada.
3. Ingresa la clave directamente en el sistema del banco, sin anotarla ni enviarla por ningún medio.
4. Si el sistema ofrece **Resincronizar token**, sigue el asistente con dos claves consecutivas.
5. Si después de tres intentos sigue el rechazo, deja de intentar para no bloquear el token.
6. Solicita a la mesa de servicio la resincronización. El agente valida tu identidad con tu número de empleado, nunca con claves del token.
7. Si el token está vencido o dañado, tu gerente tramita la activación del token de reemplazo asignado a la sucursal.

## Cuándo escalar

- Escala como **P2** si el token no funciona y no puedes autorizar operaciones.
- Escala como **P1** si la falla impide atender a clientes en ventanilla o afecta a toda la sucursal.
- Escala como **P3** si tienes un token de respaldo y puedes seguir operando.
- Si perdiste el token o crees que alguien más lo usó, es sospecha de acceso no autorizado: escala **SIEMPRE y de inmediato** como **P1** a Seguridad de la Información, sin intentar resolverlo.
