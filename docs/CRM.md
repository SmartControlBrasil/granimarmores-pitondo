# CRM comercial — Granimármores Pitondo

Documentação do módulo de leads, funil e operação comercial no painel Hando.

## Lead versus cliente

| Conceito | Descrição |
|----------|-----------|
| **Lead** | Oportunidade comercial em qualificação no funil |
| **Cliente** | Cadastro definitivo em `customers` apto a receber orçamentos |

Um lead **não vira cliente automaticamente**. A conversão é ação explícita, com opção de vincular cliente existente ou criar novo.

## Estados do funil

| Status | Label |
|--------|-------|
| `new` | Novo |
| `triage` | Triagem |
| `assigned` | Atribuído |
| `contacted` | Contato realizado |
| `qualified` | Qualificado |
| `measurement_scheduled` | Medição agendada |
| `measurement_completed` | Medição concluída |
| `quote_preparation` | Preparação de orçamento |
| `quote_sent` | Orçamento enviado |
| `negotiation` | Negociação |
| `won` | Ganho |
| `lost` | Perdido |
| `disqualified` | Desqualificado |

Transições validadas em `commercial/lead_workflow.py`. Override exige permissão `leads.override_status` e justificativa.

## Atividades

Registro operacional em `LeadActivity` (ligações, WhatsApp, reuniões, mudanças de status etc.). Complementa, mas **não substitui**, a auditoria técnica (`audit`).

## Tarefas e follow-ups

`LeadTask` gerencia pendências com responsável e vencimento. Status `overdue` é **calculado**, não persistido.

Campo `next_follow_up_at` no lead indica próximo contato comercial.

## Escopo de acesso

Reutiliza `customer_scope` do cargo:

| Escopo | Leads visíveis |
|--------|----------------|
| ALL / `leads.view_all` | Todos |
| TEAM | Equipe do vendedor logado |
| OWN | Leads do vendedor ou criados pelo usuário |

## Conversão em cliente

Fluxo em `commercial/lead_conversion.py`:

1. Busca possíveis duplicatas (telefone, WhatsApp, e-mail)
2. Cria cliente novo **ou** vincula existente (sem sobrescrever dados)
3. Preserva o lead e registra atividade + auditoria

## Vínculo com orçamento

`Quote.lead` (opcional, `SET_NULL`). Ação **Criar orçamento** exige lead convertido; copia origem, parceiro e tipo de projeto. Vários orçamentos por lead são permitidos.

Criar orçamento **não** marca o lead como ganho.

## Indicadores (dashboard comercial)

Rota: `/painel/comercial/dashboard/`

- Taxa de ganho = ganhos / (ganhos + perdidos)
- Conversão em cliente = convertidos / recebidos no período
- Tempo até primeiro contato = média de `first_contact_at - created_at`

Divisões por zero retornam zero.

## Permissões

Módulos: `leads`, `lead_activities`, `lead_tasks`. Seed conservador em `setup_erp_foundation` via `get_or_create`.

## Rotas principais

| Rota | Função |
|------|--------|
| `/painel/comercial/leads/` | Listagem |
| `/painel/comercial/leads/novo/` | Criação |
| `/painel/comercial/leads/<id>/` | Detalhe |
| `/painel/comercial/leads/funil/` | Kanban |
| `/painel/comercial/dashboard/` | Dashboard comercial |

## Preparação futura

- Formulário público institucional → criar `Lead` (hoje cria `Customer` direto)
- Integração Lívia / WhatsApp / e-mail automático
- Ranking comercial e comissão
- Atualização automática para `quote_sent` ao enviar orçamento (avaliar no workflow de quotes)

## Limitações atuais

- Funil sem drag-and-drop
- Sem notificações externas de tarefas
- Sem produção ou financeiro
- Marcação `quote_sent` manual (integração com envio de orçamento documentada para fase posterior)
