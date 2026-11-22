# Escalamiento (RN-01, RN-02, RN-03)

Banco Altiplano es ficticio; SLA ilustrativos. Handoff real a una persona (Omnichannel / Customer Service) no incluido en la prueba gratuita: "humano" significa ticket `escalado: true` que atiende el L1 humano ⚠ verificar en pantalla si el tema de sistema Escalate requiere configuración adicional.

## SLA por prioridad
| Prioridad | Criterio (RN-01) | SLA |
|---|---|---|
| P1 | Sucursal completa u operación con clientes | 4 h |
| P2 | Un usuario sin poder operar | 8 h |
| P3 | Degradación con alternativa | 24 h |
| P4 | Solicitud o duda | 72 h |

## Cuándo escalar
1. Obligatorio (RN-03): fraude, sospecha de acceso no autorizado, falla en sistemas de caja. P1, sin pasos de solución.
2. `buscar_solucion` devuelve `no_evidence` y el usuario acepta ticket.
3. El usuario dice que los pasos no funcionaron.
4. El usuario pide una persona (RF-09): escalar sin insistir.

## P1 obligatorio
- ES: "Esto requiere atención inmediata de una persona, así que no voy a intentar resolverlo yo. Creé el ticket {ticket_id} con prioridad P1; el tiempo objetivo de atención es 4 horas. Mientras tanto, no uses ni compartas tus credenciales."
- EN: "This needs immediate attention from a person, so I won't try to fix it myself. I created ticket {ticket_id} with priority P1; the target response time is 4 hours. Meanwhile, don't use or share your credentials."
- Variante falla de caja ES: "Reporté la falla del sistema de caja como P1 (ticket {ticket_id}, 4 horas). Avisa a tu gerente de sucursal."
- Variante falla de caja EN: "I reported the cash system failure as P1 (ticket {ticket_id}, 4 hours). Please let your branch manager know."

## Humano (a petición)
- ES: "Claro, te paso con una persona. Creé el ticket {ticket_id}, prioridad {prioridad}, tiempo objetivo {sla_horas} horas; un agente lo atenderá."
- EN: "Of course, I'm handing this over to a person. I created ticket {ticket_id}, priority {prioridad}, target time {sla_horas} hours; an agent will pick it up."

## Ticket normal por prioridad
- ES: "Ticket {ticket_id} creado. Prioridad {prioridad}: te atenderán en un máximo de {sla_horas} horas."
- EN: "Ticket {ticket_id} created. Priority {prioridad}: you will be attended within {sla_horas} hours."

## Frases del tema de sistema Escalate (⚠ verificar en pantalla)
- ES: hablar con un agente, hablar con una persona, quiero un humano, escalar.
- EN: talk to agent, talk to a human, escalate, I want a person.
