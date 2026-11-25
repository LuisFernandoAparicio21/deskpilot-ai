---
name: final-audit
description: Úsala para ejecutar la auditoría final de DeskPilot AI (secciones 0–6 de docs/final-audit-checklist.md) después de la Fase C, antes de postular o compartir el repo.
disable-model-invocation: true
---

# final-audit: auditoría final por secciones

Entrada: "ejecuta final-audit" o `/final-audit`. Sin argumentos.
Fuente única de verdad: [docs/final-audit-checklist.md](../../../docs/final-audit-checklist.md). Esta skill NO copia su contenido (comandos, pasos, archivos de salida): solo dice cómo orquestarlo. Si algo difiere, manda el checklist.

## Reglas del orquestador (tú, el agente principal)
- Lee el checklist completo una vez y corre las secciones 0 a 6 en orden. Cada sección se delega al subagente de su campo **Agent**, UNO A LA VEZ, nunca en paralelo (RAM 7.8 GB).
  Si el rol no es un tipo de agente, usa `general-purpose` con "lee `.claude/agents/<rol>.md` y actúa con ese rol".
- Tú no haces el trabajo de las secciones: no escaneas, no instalas, no redactas resultados en el chat. Solo coordinas, pasas la ruta del checklist y la sección exacta, y verificas que existan los archivos de **Output file**.
- Pide reportes de ≤10 líneas. Tras cada sección emite UNA línea: `final-audit · sección N ✓ · <archivo de salida>`.
- Responde a Luis siempre en español.

## Stop points (obligatorio respetar el campo **Stop point** de cada sección)
- Sección 2: parar antes del red teaming y de DeepAudit hasta tener llave o autorización de Luis; si falta, omitir la herramienta, registrarlo y seguir.
- Sección 3: Luis hace los clics con sus cuentas. Un subagente nunca inicia sesión, acepta términos ni instala apps de GitHub por él. Termina tras listar los pasos y esperar sus capturas; no pasar a la sección 4 por suposición.
- Sección 5: tras 5.1 mostrar la tabla de hallazgos a Luis y esperar su "go" antes de 5.2. Nada se corrige por iniciativa propia.
- Sección 6: sin su aprobación final y del merge, la auditoría no se cierra.

## Reglas generales
- Todo es solo lectura hasta el "go" de Luis (sección 5.2).
- Todo lo que se instale o almacene va en `D:\tools-eval`; nada pesado en `C:`.
- Llaves y tokens solo por variable de entorno: nunca en chat, archivos, logs ni commits. Cero secretos.
- Cero alucinación: los resultados se copian de la salida real de las herramientas; lo no ejecutado o no confirmado se reporta como "no verificado" (respetar los `⚠ verify` del checklist).
- No tocar `docs/evaluations/` fuera de lo que indique cada sección.
- Cada corrección va por la skill `feature-loop` (`/feature-loop <nombre>`), con rama, PR y CI verde antes de merge. Nunca push directo a `main`.
- Si la sección 0 detecta árbol sucio, CI roja en `main` o `D:\` ausente, detente y avisa a Luis.
