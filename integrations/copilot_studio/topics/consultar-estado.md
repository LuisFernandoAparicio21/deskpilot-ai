---
name: consultar_estado_ticket
description: El empleado pregunta cómo va un ticket y da su folio (TCK-NNNNNN). Consulta el estado, prioridad, fechas y SLA.
languages: [es, en]
trigger_phrases_es:
  - ¿cómo va mi ticket?
  - quiero saber el estado de mi folio
  - consultar ticket
  - estado de TCK-000123
  - ya resolvieron mi solicitud
  - cuándo me atienden
trigger_phrases_en:
  - how is my ticket going
  - what is the status of my ticket
  - check ticket status
  - status of TCK-000123
  - has my request been resolved
  - when will someone help me
tools: [consultar_estado_ticket]
requirements: [RF-02, RF-08, RF-17, HU-03]
---

# Flujo
1. Si no hay folio, pedirlo (formato TCK-NNNNNN).
2. Llamar `consultar_estado_ticket` con `ticket_id`.
3. Éxito: informar `estado` (abierto, en_proceso, resuelto, cerrado), `prioridad`, `fecha_limite_sla` y si cumplió o cumple el SLA (`sla_cumplido`).
4. 404: decir que no existe ese folio y pedir que lo verifique. No adivinar otro folio ni mostrar otros tickets.
5. Otro error: mensaje de indisponibilidad.

# Mensajes
- ES: "Tu ticket {ticket_id} está {estado}, prioridad {prioridad}. Fecha límite de SLA: {fecha_limite_sla}."
- EN: "Your ticket {ticket_id} is {estado}, priority {prioridad}. SLA deadline: {fecha_limite_sla}."
- ES no encontrado: "No encontré ese folio. Verifica que tenga el formato TCK-000123 e inténtalo de nuevo."
- EN not found: "I couldn't find that ticket. Please check it has the format TCK-000123 and try again."
- ES pedir folio: "¿Cuál es tu folio? Tiene el formato TCK-000123."
- EN ask id: "What is your ticket number? It looks like TCK-000123."
