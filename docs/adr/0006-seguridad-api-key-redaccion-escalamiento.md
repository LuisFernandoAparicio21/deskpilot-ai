# ADR-0006: Seguridad: X-API-Key, redacción RN-05 y escalamiento RN-03

- **Estado:** aceptada
- **Fecha:** 2026-11-22

## Contexto

La API se expone con una URL pública para Copilot Studio. Un banco no debe guardar contraseñas, tarjetas ni CURP
(RN-05) y debe escalar siempre fraude, acceso no autorizado y fallas de caja (RN-03), sin depender de que un LLM
"decida bien".

## Decisión

- **Autenticación:** toda la API exige `X-API-Key` (401 sin ella); la llave tiene al menos 16 caracteres y vive
  solo en `.env` o en el entorno (RNF-02, RNF-03). El HTTP de MCP compara la llave en tiempo constante.
- **RN-05:** `src/utils/redaction.py` redacta contraseña/NIP, tarjeta (con Luhn), CURP y tokens, antes de
  guardar un ticket y en los logs; la salida del LLM también se filtra.
- **RN-03:** una policy por regex (ES/EN) escala frases de fraude, cargos no reconocidos, phishing, caja y
  acceso no autorizado. Además, el artículo obligatorio KB-011 (caja) escala solo si es el top-1 o está a menos
  de `retrieval.escalation_margin` = 0.05 del top-1.

## Alternativas

- **Dejar la detección al LLM:** no es determinista ni testeable.
- **Escalar si KB-011 aparece en cualquier posición:** sobre-escalaba EV-05, EV-07 y EV-09 (L22).
- **OAuth:** más robusto, pero Copilot Studio ofrece llave en header y alcanza para el alcance.

## Consecuencias

- Reglas deterministas y probadas con casos positivos y negativos.
- Límites conocidos: una contraseña sin separador no se redacta (L16) y en inglés "POS is not working" sin
  "terminal" no se detecta (L21). Una regex no entiende el contexto.
- El margen 0.05 se calibró con la base real (ruido a 0.29-0.33 del top-1).

## Fuentes

`docs/requirements.md` (RN-03, RN-05, RNF-02 a RNF-05). *Building effective agents*, Anthropic
(`docs/sources.md`); sección API REST (T16, `APIKeyHeader`). ODD L7, L14, L16, L21 y L22.
