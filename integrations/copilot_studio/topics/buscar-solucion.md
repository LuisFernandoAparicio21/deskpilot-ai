---
name: buscar_solucion
description: El empleado describe un problema técnico (contraseña, desbloqueo de usuario, token, VPN, impresora, SAP, correo, Teams, carpeta compartida, equipo lento) y quiere resolverlo. Busca en la base de conocimiento y responde con pasos y artículo citado.
languages: [es, en]
trigger_phrases_es:
  - no puedo entrar a mi computadora
  - se bloqueó mi usuario
  - olvidé mi contraseña
  - la VPN no conecta
  - la impresora no imprime
  - no tengo acceso a SAP
  - Outlook no envía correos
  - mi equipo está muy lento
  - Teams no carga
  - no puedo abrir la carpeta compartida
trigger_phrases_en:
  - I can't log in to my computer
  - my account is locked
  - I forgot my password
  - the VPN won't connect
  - the printer is not working
  - I have no access to SAP
  - Outlook is not sending emails
  - my computer is very slow
  - Teams won't load
  - I can't open the shared folder
tools: [buscar_solucion, crear_ticket]
requirements: [RF-01, RF-03, RF-04, RF-06, RF-07, HU-01, HU-04, RN-04]
---

# Flujo
1. Llamar `buscar_solucion` con `query` = el problema tal como lo dijo el usuario (sin secretos).
2. Según `status`:
   - `answered`: mostrar `text` en pasos numerados y la cita (título + ID). Ir al paso 3.
   - `no_evidence`: ir al tema `no-lo-se`.
   - `mandatory_escalation`: ir al tema `escalamiento-obligatorio`.
3. Si `sensitive_data_warning` es true: aplicar el tema `datos-sensibles`.
4. Preguntar si funcionó.
   - Sí: despedirse, sin ticket.
   - No: ofrecer crear ticket; si acepta, tema `crear-ticket`.

# Mensajes
- ES respuesta: "Esto es lo que encontré en la base de conocimiento:\n{text}\nFuente: {titulo} ({article_id})."
- EN answer: "Here is what I found in the knowledge base:\n{text}\nSource: {titulo} ({article_id})."
- ES seguimiento: "¿Pudiste resolverlo con estos pasos?"
- EN follow-up: "Did these steps solve it?"
- ES cierre: "Perfecto, me alegra haber ayudado. No se creó ningún ticket."
- EN close: "Great, glad I could help. No ticket was created."
- ES no funcionó: "Lamento que no funcionara. ¿Quieres que cree un ticket para que lo atienda una persona?"
- EN not solved: "Sorry it didn't work. Would you like me to create a ticket so a person can take it?"
