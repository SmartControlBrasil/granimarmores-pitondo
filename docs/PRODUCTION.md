# Módulo Produção — FASE ADMIN 04

Documentação do fluxo operacional: aceite de orçamento → pedido → ordem de produção → etapas → qualidade → entrega → instalação.

## Fluxo

```text
Orçamento enviado/visualizado
  → Aceite (QuoteAcceptance + QuoteStatus.ACCEPTED)
  → Pedido (SalesOrder + snapshot de itens)
  → Ordem de produção (ProductionOrder + peças + etapas)
  → Apontamentos (ProductionLog)
  → Qualidade (QualityInspection)
  → Entrega / Instalação
  → Conclusão
```

## Aceite

- Serviços: `quotes.services.acceptance.accept_quote`, `refuse_quote`
- Modelo histórico: `QuoteAcceptance` (um aceite vigente por orçamento)
- Permissões: `quotes.accept`, `quotes.refuse`, `quotes.accept_expired`
- Integração CRM: lead marcado como ganho quando aplicável
- Score: `score_quote_accepted` registra bônus por valor e pontos LEAD_WON

## Pedido (`SalesOrder`)

- Criado automaticamente no aceite via `create_sales_order_from_quote`
- Numeração: `PED-AAAA-NNNNNN` (sequência anual transacional)
- Constraint: um pedido ativo por orçamento
- Status e transições: `production.services.order_workflow.ORDER_TRANSITIONS`

## Ordem de produção

- Numeração: `OP-AAAA-NNNNNN`
- Serviços: `production.services.work_orders`
- Progresso calculado em `production.selectors` (não persistido)

## RBAC

Permissões em `access_control.permissions.PERMISSIONS`. Seeds em `setup_erp_foundation`:

- **Gestor Comercial**: pedidos, entregas, instalações, visualização produção
- **Vendedor**: visualização de pedidos próprios (escopo de orçamento)
- **Operacional**: operação completa de produção

## Rotas

| URL | Descrição |
|-----|-----------|
| `/painel/operacao/pedidos/` | Lista de pedidos |
| `/painel/producao/` | Dashboard de produção |
| `/painel/producao/ordens/` | Ordens de produção |
| `/painel/producao/quadro/` | Quadro kanban por etapa |

## Comandos

```bash
python manage.py setup_erp_foundation   # permissões, etapas, checklist
python manage.py sync_production_delays   # identifica atrasos (--dry-run)
```

## Limitações desta fase

- Sem drag-and-drop no quadro
- Sem roteirização de entrega
- Sem integração WhatsApp / Google Calendar
- Atraso calculado em tempo real (sem flags persistidas)
