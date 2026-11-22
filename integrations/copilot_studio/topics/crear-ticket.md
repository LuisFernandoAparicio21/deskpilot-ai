---
name: crear_ticket
description: El empleado confirma que quiere abrir un ticket porque no hay solución, no funcionó, o pidió una persona. Pide solo área, sucursal y descripción breve, crea el ticket e informa folio, prioridad y SLA.
languages: [es, en]
trigger_phrases_es:
  - crea un ticket
  - abre un ticket
  - quiero levantar un reporte
  - necesito que me atienda una persona
  - quiero hablar con un agente
  - escálalo por favor
  - sí, crea el ticket
  - registra mi problema
trigger_phrases_en:
  - create a ticket
  - open a ticket
  - I want to file a request
  - I need to talk to a person
  - talk to an agent
  - please escalate it
  - yes, create the ticket
  - log my issue
tools: [crear_ticket]
requirements: [RF-05, RF-07, RF-09, RF-16, HU-02, RN-01, RN-02, RN-05]
---

# Flujo
1. Si el usuario no ha confirmado, preguntar "¿Quieres que cree un ticket?". Si pidió una persona, omitir la confirmación (RF-09).
2. Pedir solo los datos faltantes: área, sucursal y descripción breve. Nunca contraseñas, NIP, tokens ni tarjetas.
3. Llamar `crear_ticket` con `descripcion`, `area`, `sucursal` y `canal` = `Teams` (valor por defecto de la API; opciones: portal, correo, teléfono, Teams).
4. Una sola llamada por problema. Si falla: mensaje de error, sin reintentos en bucle.
5. Informar `ticket_id`, `prioridad` y `sla_horas`. Si `escalado` es true, decir que lo atenderá una persona.
6. Si `sensitive_data_warning` es true: aplicar `datos-sensibles`.

# Mensajes
- ES pedir datos: "Para crear el ticket necesito: tu área, tu sucursal y una descripción breve del problema (sin contraseñas ni datos de tarjeta)."
- EN ask: "To create the ticket I need your area, your branch and a short description of the problem (no passwords or card data)."
- ES éxito: "Listo. Tu folio es {ticket_id}, prioridad {prioridad}, tiempo objetivo de atención {sla_horas} horas."
- EN success: "Done. Your ticket is {ticket_id}, priority {prioridad}, target response time {sla_horas} hours."
- ES error: "No pude crear el ticket en este momento. Intenta de nuevo en unos minutos o llama al service desk."
- EN error: "I couldn't create the ticket right now. Please try again in a few minutes or call the service desk."
