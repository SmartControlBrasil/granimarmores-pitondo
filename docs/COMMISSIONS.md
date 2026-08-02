# Comissões Comerciais

Módulo interno do ERP Hando em `/painel/comissoes/` e extrato em `/painel/comercial/minhas-comissoes/`.

O módulo de comissões é operacional e gerencial.
Não substitui folha de pagamento, obrigações trabalhistas ou contabilidade.

## Conceitos

- **Venda comercial confirmada:** `QuoteStatus.ACCEPTED`
- **Receita realizada:** recebimento financeiro confirmado
- Provisionamento ≠ disponibilidade ≠ pagamento

## Política

`CommissionPolicy` versionada com vigência, prioridade, alvo (vendedor/parceiro/ambos), base e gatilho.
Faixas em `CommissionPolicyTier`. Regras específicas opcionais em `CommissionRule`.

Precedência:

```text
Regra específica do vendedor
→ parceiro/projeto/origem
→ política geral vigente
```

Alterar política não recalcula eventos históricos.

## Eventos (ledger)

`CommissionEvent` (`COM-AAAA-######`) imutável nos valores.
Tipos: provision, release, payment, reversal, adjustments, cancellation, chargeback.

## Fluxo

1. Aceite do orçamento → `provision_commission` (se política `quote_accepted`)
2. Recebimento → liberação proporcional ao principal
3. Estorno de recebimento → estorno das liberações
4. Fechamento (`FEC-`) → aprovação → gerar conta a pagar → pagamento (`PCM-`)

Default: não libera sobre juros/multa; `release_only_after_payment=True`.

## Seeds

- Permissões e associações conservadoras
- Categoria financeira `comissoes-comerciais`
- Centro de custo Comercial (se já não existir)
- **Sem** política percentual fictícia

## Comandos

```bash
python manage.py process_commissions --dry-run
python manage.py audit_commission_consistency --dry-run
```

## Limitações

- Sem folha/eSocial/IR
- Sem PIX/banco automático
- Sem portal de parceiro
- Pagamento manual (preferencialmente via contas a pagar)
