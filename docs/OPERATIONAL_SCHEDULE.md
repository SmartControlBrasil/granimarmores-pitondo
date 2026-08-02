# Agenda Operacional Interna — Granimármores Pitondo

O projeto **não utiliza Google Workspace nem Google Calendar**.
A agenda operacional é interna e pertence ao ERP.

## Visão geral

A agenda consolida compromissos ligados a leads, clientes, orçamentos, pedidos, medições, entregas, instalações, produção e tarefas internas.

Fonte de verdade:

- `OperationalEvent` — visão central da agenda
- `DeliverySchedule` / `InstallationSchedule` — registros operacionais específicos, vinculados por OneToOne

## Tipos

`commercial_follow_up`, `customer_meeting`, `technical_visit`, `measurement`, `quote_presentation`, `production_task`, `material_pickup`, `delivery`, `installation`, `quality_return`, `technical_assistance`, `rework_visit`, `internal_meeting`, `other`.

## Status

`draft`, `scheduled`, `confirmed`, `in_progress`, `completed`, `cancelled`, `rescheduled`, `no_show`, `blocked`.

## Numeração

Formato `AGE-AAAA-NNNNNN` via contador transacional anual (`OperationalEventSequence`).

## Conflitos

`check_schedule_conflicts` detecta sobreposição de usuário, vendedor e veículo.
Override exige permissão `operational_events.override_conflict` e justificativa auditada.

## Confirmação

Manual (telefone, WhatsApp, e-mail, presencial). Sem envio automático.
Alerta configurável: `AGENDA_CONFIRMATION_WARNING_HOURS` (default 24).

## Medição

Modelo `MeasurementAppointment` ligado 1:1 ao evento de tipo `measurement`.

## Sincronização

Agendar entrega/instalação cria/atualiza `OperationalEvent` correspondente.
Concluir evento de entrega/instalação chama os services de produção.

## RBAC

Permissões `operational_events.*`, `schedule_dashboard.view`, `schedule_calendar.view`, `schedule_measurements.*`.

## Comandos

```bash
python manage.py audit_operational_schedule --dry-run
python manage.py sync_operational_events --dry-run
```

## Limitações

- Sem Google Calendar/Workspace/Sheets
- Sem roteirização, GPS ou mapas pagos
- Sem envio automático de confirmação
- Sem upload de planta nesta fase
