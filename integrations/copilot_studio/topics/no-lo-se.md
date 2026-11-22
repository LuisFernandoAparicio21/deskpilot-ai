---
name: no_lo_se
description: buscar_solucion devuelve no_evidence (no hay artículo suficientemente parecido) o la pregunta no tiene respaldo en la base de conocimiento. El agente admite que no tiene la respuesta, no inventa pasos y ofrece crear un ticket.
languages: [es, en]
trigger_phrases_es:
  - eso no funcionó
  - ¿sabes cómo arreglar esto?
  - tengo un problema raro
  - no encuentro solución
trigger_phrases_en:
  - that didn't work
  - do you know how to fix this
  - I have a weird problem
  - I can't find a solution
tools: [buscar_solucion, crear_ticket]
requirements: [RF-05, RF-13, HU-02, RN-04]
---

# Flujo
1. Se llega desde `buscar-solucion` con `status` = `no_evidence` (redirección; las frases de activación son solo respaldo, ⚠ verificar en pantalla si con orquestación generativa hacen falta).
2. Decir explícitamente que no se tiene la respuesta. Prohibido inventar pasos, sugerir comandos o "probar esto" sin artículo.
3. Ofrecer crear un ticket. Si acepta, tema `crear-ticket`. Si no, despedirse.

# Mensajes
- ES: "No tengo una respuesta confiable para eso en mi base de conocimiento, y prefiero no inventarte pasos. ¿Quieres que cree un ticket para que lo revise una persona?"
- EN: "I don't have a reliable answer for that in my knowledge base, and I'd rather not make up steps. Would you like me to create a ticket so a person can look into it?"
- ES rechazo: "Entendido. Si cambias de opinión, solo dime."
- EN decline: "Understood. If you change your mind, just tell me."
