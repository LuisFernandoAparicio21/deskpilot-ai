# ADR-0001: RAG con modo extractivo por defecto y LLM opcional

- **Estado:** aceptada
- **Fecha:** 2026-11-22

## Contexto

El agente de un banco no puede inventar pasos de soporte (RN-04, RF-05). El proyecto también debe correr sin
llaves de pago (RNF-10) y tener pruebas deterministas. Un LLM generativo agrega costo, latencia y riesgo de
alucinación.

## Decisión

`llm.provider` vale `none` por defecto: la respuesta se arma con una plantilla que extrae los pasos del artículo
recuperado y lo cita. Claude, OpenAI o Gemini se activan por `.env`; su salida se valida (los ids de artículo
deben estar en la evidencia y se filtra con `contains_sensitive`). Debajo del umbral de similitud (0.33,
calibrado con el modelo real) la respuesta es "sin evidencia".

## Alternativas

- **Siempre con LLM:** respuestas más fluidas, pero exige llave, no es determinista y puede inventar pasos.
- **Sin umbral, siempre responder:** más cobertura, pero viola RN-04.

## Consecuencias

- Evaluación reproducible y p95 local de 31.5 ms (`tests/eval/results.summary.json`).
- Menos fluidez en el texto; con un LLM se gana a costa de validaciones extra.
- El umbral es global: EV-16 responde con score 0.525 y es una limitación documentada (L22).

## Fuentes

Lewis et al. 2020, RAG (`docs/sources.md`, sección Metodología); *Building effective agents* (Anthropic, en la
misma sección); ODD L3 (LLM por defecto `none`), L14 (umbral y validación) y L22 (EV-16).
