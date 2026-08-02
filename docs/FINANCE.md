# Financeiro Operacional

Módulo interno do ERP Hando em `/painel/financeiro/`.

O módulo financeiro é operacional e gerencial.
Não substitui contabilidade, emissão fiscal ou conciliação bancária.

## Escopo

Inclui:

- categorias e centros de custo;
- formas e condições de pagamento;
- contas financeiras (caixa/controle interno);
- contas a receber e parcelas;
- geração explícita a partir do pedido;
- recebimentos e estornos;
- contas a pagar, pagamentos e estornos;
- ledger imutável (`FinancialMovement`);
- transferências e ajustes auditados;
- fluxo de caixa realizado e previsto;
- inadimplência;
- dashboard e exportações CSV.

Não inclui: NF-e, bancos, Open Finance, PIX automático, boleto bancário, comissão, folha, DRE contábil.

## Definições

- Venda fechada continua sendo `QuoteStatus.ACCEPTED`.
- Aceite **não** gera pagamento.
- Contas a receber do pedido nascem apenas pela ação **Gerar contas a receber**.
- Valor do título usa o total congelado do pedido (`SalesOrder.total`).
- Parcela vencida = `due_date < hoje` e `outstanding_amount > 0` e status não final.
- Realizado = movimentos confirmados; previsto = parcelas abertas por vencimento.
- Saldo de conta = soma dos movimentos (saldo inicial gera lançamento explícito).

## Renegociação

Nesta fase: status `renegotiated` está disponível nos títulos/parcelas.
Fluxo completo de renegociação com novo título fica para fase posterior.

## Permissões

Principais: `finance_dashboard.view`, `accounts_receivable.*`, `accounts_payable.*`, `financial_movements.*`, `finance_cash_flow.view`, `finance_overdue.view`, `finance_values.view`, `finance_export`, `executive_dashboard.view_finance`.

## Comandos

```bash
python manage.py sync_financial_overdue --dry-run
python manage.py audit_financial_consistency --dry-run
```

## Seeds

`setup_erp_foundation` cria categorias, centros, formas e condições.
Não cria contas financeiras, títulos, pagamentos ou saldos fictícios.

## Limitações

- Sem integração bancária.
- Sem cobrança automática.
- Renegociação completa pendente.
- Sem inventar saldo bancário externo.
