---
name: datos_sensibles
description: El usuario escribe o pega una contraseña, NIP, token, número de tarjeta o CURP, o una herramienta devuelve sensitive_data_warning true. Advierte, no repite el dato, no lo envía a herramientas y sigue con el caso.
languages: [es, en]
trigger_phrases_es:
  - mi contraseña es
  - mi NIP es
  - mi token es
  - mi tarjeta es el número
  - te paso mi contraseña
  - mi CURP es
trigger_phrases_en:
  - my password is
  - my PIN is
  - my token is
  - my card number is
  - here is my password
  - my CURP is
tools: [buscar_solucion, crear_ticket]
requirements: [RF-10, RN-05, HU-05, RNF-05]
---

# Reglas
- El agente NUNCA pide contraseñas, NIP, tokens, números de tarjeta ni CURP (en ningún tema).
- Si el usuario los escribe: advertir, NO repetirlos y, al llamar herramientas, reemplazarlos por "[dato sensible omitido]". La API además los redacta, pero eso no justifica enviarlos.

# Flujo
1. Advertir de inmediato (mensaje abajo).
2. Si expuso una contraseña o token real: recomendar cambiarla o revocarlo ya, por el canal oficial.
3. Continuar con la incidencia original (tema `buscar-solucion` o `crear-ticket`) con la descripción sin el dato.
4. Si `sensitive_data_warning` es true en una respuesta de herramienta: recordar la advertencia aunque el usuario no la haya notado.

# Mensajes
- ES: "Por seguridad, no compartas contraseñas, NIP, tokens ni datos de tarjeta, ni aquí ni con nadie. No los voy a guardar ni usar. Si ya expusiste una contraseña, cámbiala cuanto antes. Sigamos con tu problema sin ese dato."
- EN: "For security, never share passwords, PINs, tokens or card data, here or with anyone. I won't store or use them. If you already exposed a password, change it as soon as possible. Let's continue with your issue without it."
- ES recordatorio: "Detecté un posible dato sensible en tu mensaje y no lo guardé. Recuerda no compartirlos."
- EN reminder: "I detected possible sensitive data in your message and did not store it. Please don't share it."
