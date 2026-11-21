---
id: KB-007
titulo: Perfil sin acceso al core bancario
categoria: Accesos
subcategoria: Acceso a core bancario
idioma: es
fecha_actualizacion: 2026-11-01
palabras_clave:
  - core bancario
  - sistema central
  - perfil inactivo
  - fuera de horario
  - sin acceso al core
  - perfil suspendido
  - core banking
  - access denied
---

# Perfil sin acceso al core bancario

## Síntoma

Al entrar al core bancario aparece "Perfil inactivo", "Acceso fuera de horario permitido" o "Usuario sin facultades para esta operación". Puede pasar después de vacaciones, una incapacidad, un cambio de sucursal o un cambio de puesto.

## Causa

El core bancario suspende los perfiles que no se usan durante un periodo prolongado y limita cada perfil a un horario y a ciertas operaciones según el puesto. Para reactivar o ampliar un perfil se necesita la autorización del gerente de la sucursal; la mesa de servicio no puede otorgarla por su cuenta.

## Pasos

1. Anota el mensaje exacto que muestra el core bancario y la hora del intento.
2. Verifica que estás dentro de tu horario laboral registrado.
3. Confirma con tu gerente si hubo un cambio reciente en tu puesto o sucursal.
4. Pide a tu gerente que registre la autorización de reactivación en el portal de solicitudes de acceso.
5. Levanta el ticket con tu número de empleado, sucursal, mensaje de error y folio de la autorización.
6. Mientras se atiende, no uses el perfil de otra persona: está prohibido por la política de seguridad.

## Cuándo escalar

- Escala como **P1** si ningún usuario de la sucursal puede entrar al core bancario o la falla detiene la atención a clientes.
- Escala como **P2** si solo tu perfil está inactivo y no puedes operar.
- Escala como **P3** si te falta una operación específica, pero puedes seguir trabajando.
- Si el core muestra accesos con tu usuario que no reconoces, es sospecha de acceso no autorizado: escala **SIEMPRE y de inmediato** como **P1** a Seguridad de la Información, sin intentar resolverlo.
