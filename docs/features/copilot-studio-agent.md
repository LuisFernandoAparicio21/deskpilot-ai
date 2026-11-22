# Diseño del agente de Copilot Studio (T20)

## Qué contiene

`integrations/copilot_studio/` es el diseño del agente DeskPilot L1 (bilingüe ES/EN, Banco Altiplano ficticio, datos sintéticos). No se ejecuta en este repo: se pega en Copilot Studio a mano (T32).

- `instructions.md`: instrucciones del agente (menos de 4,000 caracteres). Idioma del último mensaje, uso de las 4 herramientas, regla de evidencia (RN-04), escalamiento obligatorio (RN-03), datos sensibles (RN-05, RF-10) y fuera de alcance.
- `topics/`: 8 temas con frases de activación ES/EN: `buscar_solucion`, `crear_ticket`, `consultar_estado_ticket`, `metricas_area`, `escalamiento_obligatorio`, `no_lo_se`, `saludo_fuera_de_alcance`, `datos_sensibles`.
- `tools.md`: las 4 herramientas con el mismo nombre que el `operationId` de `openapi.json` y del servidor MCP.
- `escalation.md`: SLA por prioridad (P1 4 h, P2 8 h, P3 24 h, P4 72 h) y mensajes ES/EN (P1 obligatorio, humano a petición, ticket normal).
- `test-conversations.md`: 18 conversaciones de prueba, CT-01 a CT-18, para T32.

## Specs y requerimientos que cubre

- Spec **S11** (agente de Copilot Studio).
- **RN-01** (SLA por prioridad), **RN-03** (escalamiento obligatorio: fraude, acceso no autorizado, falla de caja), **RN-05** (datos sensibles); además RN-04, RF-01 a RF-10, RF-16, RF-19 y RNF-12 según cada tema.
- Historias de usuario **HU-01 a HU-05** (CT-01 desbloqueo, CT-03 ticket, CT-14 estado, CT-02 VPN en inglés, CT-07 secreto pegado).
- Vacante: Copilot Studio y procesos de negocio (agente que aplica reglas de soporte y escalamiento).

## Pruebas realizadas

`tests/unit/test_copilot_studio.py` (34 pruebas):

| Grupo | Qué valida |
|---|---|
| Temas | Hay 8 temas; cada uno tiene nombre snake_case único, descripción de al menos 40 caracteres, idiomas es/en, frases ES y EN (menos de 200, hasta 80 caracteres, sin duplicados) y requerimientos. Ninguna frase se repite entre temas. |
| Herramientas | `openapi.json`, `TOOL_NAMES` del MCP y `tools.md` coinciden; cada herramienta de un tema existe en todos; las 4 se usan en algún tema. |
| Instrucciones | Máximo 4,000 caracteres; menciona fraude, acceso no autorizado, caja, RN-03, no pedir contraseñas, "no tienes la respuesta", citas KB-NNN, español e inglés y las 4 herramientas. |
| Escalamiento | Tabla de SLA 4/8/24/72 h, mensajes P1 ES/EN, humano y ticket normal con marcadores; el SLA de las instrucciones coincide. |
| Conversaciones | Al menos 12 casos con ID único, ES y EN, cubren fraude, secreto, fuera de alcance y "no lo sé"; cada caso tiene Usuario, Debe y No debe. |
| Seguridad | Sin CURP, llaves, correos reales ni tarjetas válidas (solo la de prueba 4111 1111 1111 1111 en CT-08). |
| Marcadores | Los "⚠ verificar en pantalla" exigidos por la investigación siguen presentes, incluido el de idiomas soportados. |
| Policy | Todas las frases del tema de escalamiento, ES y EN, activan `escalation_reason` (fraude, acceso no autorizado y caja) y `classify` las vuelve P1 escalado. |

`tests/unit/test_answer_service.py` (51 pruebas de `rn03` y `escalation_reason`): frases positivas por tipo (`fraud`, `unauthorized_access`, `cash_system`) en ES y EN, y negativas que no deben escalar ("la impresora de la caja de ahorro", "necesito una caja de clips", "the printer is not working", "mi cargo en el sistema de tickets no carga"). Valida también que RN-03 devuelva `mandatory_escalation` sin pasos de solución, en modo policy.

## Resultados reales

Comando: `.venv\Scripts\python -m pytest --cov=src --cov-report=term` (rama `feat/t20-copilot-studio-design`, 2026-11-22).

```text
1287 passed, 1 skipped, 1 deselected, 5 warnings in 89.35s
TOTAL 3011 statements, 31 missing, 580 branches, 27 partial: 98%
Required test coverage of 80.0% reached. Total coverage: 98.33%
SKIPPED tests\unit\test_openapi_export.py:347: openapi-spec-validator is not installed (optional)
```

Por archivo: `test_copilot_studio.py` 34 pasan; los casos de policy de `test_answer_service.py` 51 pasan; `src/retrieval/policy.py` 100% de cobertura.

## Cómo verificar paso a paso

1. Pruebas del diseño:
   ```powershell
   .venv\Scripts\python -m pytest tests/unit/test_copilot_studio.py -q
   ```
2. Casos de policy RN-03:
   ```powershell
   .venv\Scripts\python -m pytest tests/unit/test_answer_service.py -k "escalation_reason or rn03" -q
   ```
3. Suite completa con cobertura:
   ```powershell
   .venv\Scripts\python -m pytest --cov=src --cov-report=term
   ```
4. Revisar a mano `integrations/copilot_studio/test-conversations.md`: cada caso lista usuario, herramientas esperadas en orden y criterios Debe / No debe.
5. Uso real en Copilot Studio: manual (T32). Los pasos de interfaz irán en `docs/MANUAL_STEPS.md` (T25, pendiente). Hasta entonces el agente no se ha probado en pantalla: no verificado.

## Hallazgos del QA y su corrección

- Seis frases de escalamiento obligatorio no estaban cubiertas por RN-03 (ES: «vi movimientos extraños con mi usuario», «no podemos cobrar en caja»; EN: «there is a transaction I don't recognize», «strange activity with my user», «we can't process payments at the counter», «the cash terminal is not working»). Se amplió `src/retrieval/policy.py` (ES/EN) y se agregaron pruebas positivas y negativas. Ahora cada frase del tema de escalamiento activa la policy y crea un ticket P1.
- Faltaba el marcador "⚠ verificar en pantalla" sobre idiomas soportados (español e inglés). Se añadió una nota en `integrations/copilot_studio/README.md` y una prueba que lo exige.

## Límites verificados y pendientes

Fuente: `docs/research/copilot-studio-agent-limits.md` (consulta 2026-11-22; 3 fuentes de Microsoft Learn).

Verificado en la documentación oficial:

- Máximo 200 frases de activación por tema; 1,000 temas y 100 skills por agente.
- El tema de sistema **Escalate** se dispara con "talk to agent" o el evento de sistema; se puede apagar pero no borrar. Para pasar a una persona real hay que configurar handoff (Omnichannel / Customer Service); sin eso solo informa.
- El idioma principal se define al crear el agente y no se cambia después; los secundarios se agregan en Settings > Languages; `User.Language` permite cambiar dinámicamente.

⚠ verificar en pantalla (las fuentes no lo confirman):

- Máximo de caracteres de las instrucciones (el diseño usa menos de 4,000 como precaución).
- Longitud máxima del nombre y la descripción de herramientas y temas.
- Cantidad recomendada de frases de activación, y si son opcionales con orquestación generativa.
- Que español e inglés figuren como idiomas soportados.
- Si el tema Escalate requiere configuración adicional sin handoff real.

## Limitaciones

- En inglés, "POS is not working" sin la palabra "terminal" no se detecta como falla de caja.
- El texto exacto de las respuestas del LLM de Copilot Studio varía; por eso las conversaciones se evalúan por criterios, no por texto literal.
- Sin handoff real a una persona (cuenta de prueba): "humano" significa un ticket `escalado: true`.
- Los resultados de las 18 conversaciones en el agente real aún no existen (T32 y T33).
