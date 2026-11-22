---
name: escalamiento_obligatorio
description: El usuario reporta fraude, sospecha de acceso no autorizado, o una falla en sistemas de caja (terminal caída, no se puede cobrar). Nunca se intenta resolver: se crea un ticket P1 y se avisa que lo atiende una persona.
languages: [es, en]
trigger_phrases_es:
  - creo que es un fraude
  - hay un cargo que no reconozco en el sistema
  - alguien entró a mi cuenta sin permiso
  - sospecho acceso no autorizado
  - vi movimientos extraños con mi usuario
  - se cayó el sistema de caja
  - no podemos cobrar en caja
  - la terminal de caja no funciona
trigger_phrases_en:
  - I think this is fraud
  - there is a transaction I don't recognize
  - someone accessed my account without permission
  - I suspect unauthorized access
  - strange activity with my user
  - the teller system is down
  - we can't process payments at the counter
  - the cash terminal is not working
tools: [buscar_solucion, crear_ticket]
requirements: [RN-03, RN-01, RN-02, RF-07, RF-16]
---

# Flujo
1. NO dar pasos de solución ni diagnósticos (RN-03).
2. Llamar `buscar_solucion` con la descripción: debe responder `mandatory_escalation`. Mostrar su `text` tal cual. Aunque no responda así, tratar el caso como escalamiento obligatorio.
3. Pedir solo área, sucursal y descripción breve (sin datos sensibles); no repetir lo que ya dio. No se pregunta "¿quieres ticket?": se informa que se creará.
4. Llamar `crear_ticket`. Esperado: `prioridad` P1, `escalado` true, `sla_horas` 4.
5. Informar folio, P1, SLA 4 h y que lo atenderá una persona. Mensajes completos en `../escalation.md`.
6. Si es fraude o acceso no autorizado, recomendar no usar ni compartir credenciales y cambiar la contraseña por el canal oficial.

# Mensajes
Ver `../escalation.md` (secciones "P1 obligatorio" y "Humano").
