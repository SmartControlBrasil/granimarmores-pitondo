# Pós-venda, Garantia e Assistência Técnica

Módulo ERP `after_sales` para acompanhamento pós-entrega/instalação, assistência, garantias, satisfação, avaliações, autorização de imagens e indicações.

**O módulo não utiliza Google Workspace, Google Calendar ou Google Drive. Toda agenda e rastreabilidade operacional pertencem ao ERP.**

## Caso (`AfterSalesCase`)

Código transacional anual: `POS-AAAA-NNNNNN` (via `AfterSalesCaseSequence` + `select_for_update`).

Abertura exige cliente e pedido, salvo exceção autorizada (`allow_without_order` + permissão de visão geral).

## Tipos

`post_delivery_follow_up`, `post_installation_follow_up`, `installation_pending`, `customer_complaint`, `technical_assistance`, `warranty_request`, `damage_report`, `measurement_issue`, `material_issue`, `finish_issue`, `installation_issue`, `delivery_issue`, `rework_request`, `return_visit`, `other`.

## Status

`new` → triagem/atribuição → estados operacionais → `resolved` → `closed`.

Também: `rejected`, `cancelled` (exigem motivo).

- Resolução não fecha automaticamente.
- Fechamento exige caso resolvido, sem pendência aberta vinculada e sem evento técnico ativo.
- Status finais (`resolved`/`closed`/`rejected`/`cancelled`) não são editáveis pelo formulário genérico de status.

## Prioridade e severidade

- Prioridade: prazo de ação (`low`…`urgent`).
- Severidade: impacto técnico (`cosmetic`…`critical`).
- Críticos entram em alertas.

## Garantia

- `WarrantyPolicy`: cadastrada pela empresa (sem seed fictício).
- `WarrantyRecord`: vinculada a pedido; número `GAR-AAAA-NNNNNN`.
- Elegibilidade (`evaluate_warranty_eligibility`): `eligible` | `not_eligible` | `manual_review`.
- Decisão final autorizada exige justificativa (`decide_warranty_eligibility`).

## Histórico e interações

- `AfterSalesCaseHistory`: ledger imutável (não substitui auditoria).
- `AfterSalesInteraction`: registro de contatos realizados (sem envio real).

## Anexos

`AfterSalesAttachment` em `media/after_sales/`. Validação de extensão/tamanho. Acesso via painel autenticado; não há CDN pública dedicada nesta fase.

## Diagnóstico, causa raiz e responsabilidade

Campos controlados no caso. Causa raiz obrigatória para tipos técnicos antes da resolução. `other` exige descrição. Responsabilidade é decisão registrada (sem lançamento financeiro).

## Pendências de instalação

`InstallationPendingItem`: criação explícita na conclusão/instalação (ação “Registrar pendência”). Pode gerar caso e visita. Resolução obrigatória.

## Agenda

Visitas via `OperationalEvent` (`technical_assistance` etc.) com FK opcional `after_sales_case`. Atalhos no caso; calendário permanece no módulo Agenda.

## Retrabalho pós-entrega

Origem `after_sales` (distinta de `production_internal` / `quality_rejection`). Vínculo opcional com ordem de produção; não altera orçamento nem cria venda.

## Estoque

Solicitação de material registrada no caso (`awaiting_material`). Consumo/reserva seguem services de estoque existentes — sem módulo de compras.

## Satisfação, avaliação, consentimento e indicação

- `CustomerSatisfactionSurvey` (notas 1–5, resposta manual).
- `ReviewRequest` (controle manual; sem Google Meu Negócio).
- `MediaUsageConsent` (explícito; revogação preserva histórico).
- `CustomerReferral` → conversão explícita em Lead com origem Indicação (sem criar cliente automático).

## RBAC e escopo

Permissões `after_sales_cases.*`, `warranties.*`, `installation_pending_items.*`, `customer_satisfaction.*`, `review_requests.*`, `media_usage_consents.*`, `customer_referrals.*`, `after_sales_dashboard.view`.

Selectors centralizam escopo: visão geral vs. casos do vendedor/responsável.

## Comandos

```bash
python manage.py audit_after_sales --dry-run
```

Opções: `--start`, `--end`, `--status`, `--responsible`.

Não corrige automaticamente.

## Rotas

Prefixo: `/painel/pos-venda/`

- Dashboard, casos, pendências, garantias, pesquisas, avaliações, autorizações, indicações.

## Limitações

- Sem WhatsApp/e-mail automático.
- Sem financeiro/fiscal.
- Sem Google Workspace/Calendar/Drive/Sheets.
- Anexos locais; privacidade depende do controle de acesso do painel.
- Políticas de garantia não são inventadas pelo seed.
- Follow-ups automáticos pós-entrega não são criados sem prazo configurado pela empresa.
