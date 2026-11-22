# Límites y formato de agentes en Copilot Studio (T20)

Consulta: 2026-11-22. Rama `feat/t20-copilot-studio-design`. Solo 3 fuentes (regla del researcher). "⚠ verificar en pantalla" = las fuentes consultadas no lo confirman.

## Pregunta
En Copilot Studio (agentes generativos), ¿qué límites y formato oficiales aplican a (a) instrucciones del agente, (b) nombre/descripción de herramientas (REST API tool) y temas, (c) frases de activación, (d) escalamiento a humano, (e) idiomas para un agente bilingüe es/en?

## Respuesta
- (a) Instrucciones: la página de cuotas y límites NO lista un máximo de caracteres. ⚠ verificar en pantalla (el contador del campo Instructions en Overview). No asumir cifra; mantener las instrucciones cortas.
- (b) Nombre/descripción de herramientas y temas: sin longitud máxima publicada en la página de límites. ⚠ verificar en pantalla. Sí hay límites de cantidad: 100 skills por agente y 1,000 temas por agente (Dataverse; 250 en Dataverse for Teams). Descripciones claras importan porque la orquestación generativa elige herramientas y temas por su descripción (no está en las fuentes consultadas: ⚠ verificar).
- (c) Trigger phrases: máximo 200 por tema. Cantidad recomendada: no publicada en las fuentes consultadas ⚠ verificar. Con orquestación generativa, el tema se elige por su descripción; las frases son opcionales (⚠ verificar en pantalla).
- (d) Escalamiento: el tema de sistema **Escalate** "Informs customers if they need to speak with a human"; se dispara cuando coincide "talk to agent" o se llama al evento de sistema **Escalate** (por ejemplo, un nodo Question que no recibe respuesta válida). Se puede apagar pero no borrar, y se redirige a él desde otros temas. Ejemplos de frases del bot clásico: "talk to agent, escalate, can I talk to a human". Para entregar a una persona real hay que configurar el handoff (Omnichannel / Dynamics 365 Customer Service); sin eso el tema solo informa. Para DeskPilot (sin agente humano real) basta el mensaje de escalamiento en Escalate más sugerencia en las instrucciones.
- (e) Idiomas: se define un idioma principal al crear el agente (no se puede cambiar después; sí la región). Se agregan secundarios en Settings > Languages > Add language. Toda la edición se hace en el idioma principal; para los secundarios se descarga/sube un archivo de localización JSON o ResX. Con orquestación generativa los mensajes generados se traducen solos y se puede cambiar de idioma dinámicamente con un tema "A message is received" que fija `User.Language`. Si el idioma del navegador no está soportado, usa el principal. Que español y inglés estén en la lista de soportados: ⚠ verificar en la página Language support (no consultada).

## Decisión recomendada
- Idioma principal: español; agregar inglés como secundario y activar el cambio dinámico con `User.Language`.
- Instrucciones y descripciones breves; confirmar el contador de caracteres en pantalla antes de pegar `integrations/copilot_studio/` (⚠).
- Escalate: dejar el tema del sistema, ajustar el mensaje y las frases ("hablar con un agente", "talk to agent"), sin handoff real (cuenta trial).
- Menos de 200 frases por tema (límite duro); apuntar a pocas y claras.

## Fuentes (consulta 2026-11-22)
1. Quotas and limits - Microsoft Copilot Studio. https://learn.microsoft.com/en-us/microsoft-copilot-studio/requirements-quotas
2. Use system topics - Microsoft Copilot Studio. https://learn.microsoft.com/en-us/microsoft-copilot-studio/authoring-system-topics
3. Configure and create multilingual agents - Microsoft Copilot Studio. https://learn.microsoft.com/en-us/microsoft-copilot-studio/multilingual
