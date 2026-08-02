# Compras e Abastecimento

Módulo interno do ERP Hando em `/painel/compras/`.

O módulo de compras é operacional.
Não realiza emissão fiscal, integração bancária ou comunicação automática com fornecedores.

## Fluxo

```text
Necessidade → Solicitação (SC) → Cotação (COT) → Comparação →
Aprovação/seleção → Pedido (PC) → Recebimento (RCM) →
Entrada de chapas → Conta a pagar → Encerramento
```

## Solicitação

- Numeração `SC-AAAA-000001`
- Justificativa obrigatória
- Origens: manual, peça, OP, estoque, assistência, manutenção
- Aprovação/rejeição explícitas
- Botões em peça (`Solicitar compra de chapa`) e OP (`Solicitar material`)

## Cotação e comparação

- Numeração `COT-AAAA-000001`
- Registro manual de cotações recebidas (sem e-mail automático)
- Comparação por item com destaques (menor preço/prazo/custo)
- Seleção humana; justificativa obrigatória se não for o menor custo
- Compra dividida por fornecedor permitida

## Pedido e recebimento

- Numeração `PC-AAAA-000001` / `RCM-AAAA-000001`
- Valores congelados no pedido
- Recebimento parcial permitido; excesso exige override
- Entrada de estoque somente após aceite
- Chapas: uma `MaterialSlab` por unidade física via `receive_slab()`
- Materiais não-chapa: registro documental (sem estoque quantitativo genérico)

## Divergências e devoluções

- Divergências abertas no dashboard
- Devolução `DEV-AAAA-000001` com bloqueio/saída de chapa quando aplicável
- Ajustes financeiros por divergência são ações explícitas (não automáticas)

## Financeiro

Configuração:

```text
PURCHASING_PAYABLE_TRIGGER = receipt  # receipt | purchase_order | manual
```

Ação **Gerar conta a pagar** no pedido; evita duplicidade; não marca como paga.

## Fornecedores

Reutiliza `materials.MaterialSupplier`. Menu principal em Compras; rota de estoque permanece por compatibilidade.

## RBAC / comandos / exportações

Permissões `purchase_*`, `purchasing_*`, `executive_dashboard.view_purchasing`.
CSV com sanitização e auditoria.

```bash
python manage.py audit_purchasing_consistency --dry-run
python manage.py sync_purchase_delays --dry-run
```

## Limitações

- Sem NF-e / XML fiscal / SPED
- Sem integração com ERP de fornecedor
- Sem estoque quantitativo genérico para insumos não-chapa
- Sem alçada financeira automática
- Seeds não criam compras fictícias
