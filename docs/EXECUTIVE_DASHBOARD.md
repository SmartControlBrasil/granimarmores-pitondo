# Painel Executivo da Diretoria

Visão consolidada do ERP Hando em `/painel/diretoria/`.

O painel utiliza exclusivamente dados internos do ERP.
Não depende de Google Workspace, Google Sheets ou ferramentas externas de BI.

## Princípios

- Cálculo ao vivo via selectors/services (sem persistir agregações).
- Venda fechada = `QuoteStatus.ACCEPTED`.
- Valor potencial ≠ valor aprovado.
- Sem dados fictícios.
- RBAC por domínio; custos e valores comerciais são permissões separadas.

## Indicadores (definições)

| Indicador | Definição |
|-----------|-----------|
| Valor potencial | Leads abertos (`estimated_value`) + orçamentos em status potencial |
| Valor aprovado | Soma de `grand_total` de orçamentos `ACCEPTED` no período (`accepted_at`) |
| Ticket médio | valor aprovado / quantidade de vendas aceitas (0 se denominador 0) |
| Taxa de conversão | leads ganhos / (ganhos + perdidos) no período |
| Pedidos atrasados | selector operacional existente (`overdue`) |
| Riscos | regras objetivas (prazo, chapa, pausa, inspeção, agenda, assistência) |

Tempo médio por etapa do funil **não** é exibido quando não há histórico de transição.

## Períodos

`today`, `7d`, `30d`, `month`, `previous_month`, `quarter`, `year`, `custom`.

Timezone: `America/Sao_Paulo` (config do projeto).

Período máximo personalizado: 732 dias.

Tendências comparam com o intervalo imediatamente anterior de mesma duração.

## Filtros

Globais: vendedor, origem, tipo de projeto, cidade, material, responsável/etapa produtiva, status pedido, status pós-venda.

Aplicados apenas quando o módulo é compatível.

## Domínios

Comercial, vendedores, funil, produção, gargalos, estoque, riscos, agenda, entregas/instalações, pós-venda, qualidade, mídia (resumo), governança/auditoria, alertas, gráficos ApexCharts já presentes no Hando.

## Permissões

- `executive_dashboard.view`
- `executive_dashboard.view_commercial`
- `executive_dashboard.view_sales_values`
- `executive_dashboard.view_production`
- `executive_dashboard.view_stock`
- `executive_dashboard.view_stock_costs`
- `executive_dashboard.view_schedule`
- `executive_dashboard.view_after_sales`
- `executive_dashboard.view_quality`
- `executive_dashboard.view_audit`
- `executive_dashboard.export`
- `executive_dashboard.print`

Seeds em `setup_erp_foundation`:

- Administrativo: acesso total (`has_full_access`)
- Gestor Comercial: comercial + valores + produção/agenda/pós-venda resumidos + export/print
- Operacional: produção, estoque, qualidade, agenda + export
- Vendedor: **sem** painel executivo (usa Meu Desempenho)

## Exportação e relatório

- CSV UTF-8 com BOM, `;`, sanitização anti CSV injection, auditado.
- Relatório HTML imprimível em `/painel/diretoria/relatorio/`.

## Cache

`EXECUTIVE_DASHBOARD_CACHE_SECONDS` (default `60`). Cache por usuário + filtros. `0` desativa.

## Auditoria

Registrados: acesso ao painel, exportação, relatório, consulta de custos, consulta de governança.

## Comando

```bash
python manage.py audit_executive_metrics --dry-run
python manage.py audit_executive_metrics --domain commercial
```

Somente leitura; não corrige dados.

## Limitações

- Sem módulo financeiro / faturamento inventado.
- Tempo médio de etapa do funil depende de histórico (não inventado).
- Snapshot imutável não foi criado nesta fase (prioridade: cálculo ao vivo).
- Gráficos usam ApexCharts já embutido no Hando.
