# Estoque de Chapas — Granimármores Pitondo

Documentação operacional do módulo de estoque integrado ao ERP (Fase Admin 05).

## Material versus chapa

- **Material**: tipo comercial/técnico (granito, mármore, quartzo etc.), cadastrado em Materiais.
- **Chapa (`MaterialSlab`)**: unidade física rastreável com código `CHP-AAAA-NNNNNN`, dimensões, áreas e movimentações.

## Área

Campos principais:

- `total_area`: área física da chapa (m²)
- `available_area`: disponível para reserva
- `reserved_area`: bloqueada por reservas ativas
- `consumed_area`: já utilizada em produção
- `lost_area`: perdas registradas

Regra: `available + reserved + consumed + lost ≤ total`. Estoque negativo é bloqueado nos serviços.

## Reserva

Modelo `SlabReservation`, vinculada a peça e ordem de produção. Reduz `available_area` e aumenta `reserved_area`. Dupla reserva ativa para mesma peça/chapa é impedida por constraint.

## Consumo

Serviço `consume_slab_reservation`: registra consumo e perda opcional, atualiza reserva/chapa e gera movimentação imutável.

## Sobra

Sobras são novas chapas (`is_remnant=True`) com `parent_slab`, reutilizáveis no fluxo de reserva.

## Localização

Cadastro hierárquico `StockLocation` (galpão, cavalete, prateleira etc.). Transferências preservam histórico via `StockMovement`.

## Movimentações

Ledger imutável `StockMovement` — correções via movimento inverso/ajuste, nunca edição.

## Inventário

`StockInventory` + `StockInventoryItem` por localização. Ajustes automáticos somente após aprovação (`stock_inventory.approve_inventory`).

## Integração com produção

- Reserva no detalhe da peça (`/painel/estoque/pecas/<id>/reservar/`).
- Etapa produtiva `corte` (slug estável) exige reserva ativa para iniciar.
- Conclusão de corte exige consumo registrado (reserva não pode permanecer `active`).
- Override sem reserva exige permissão `slab_reservations.override_cut` e justificativa auditada.

## Custo

Custo congelado na entrada. Indicadores `cost_per_m2` e `estimated_consumed_cost` visíveis apenas com `stock_costs.view`.

## RBAC

Permissões `stock_*`, `slabs.*`, `slab_reservations.*`, `slab_consumption.*`, `slab_losses.*`, `slab_remnants.*`, `stock_movements.*`, `stock_inventory.*`, `stock_adjustments.execute`, `stock_costs.view`.

## Comandos

```bash
python manage.py audit_stock_consistency --dry-run
python manage.py audit_stock_consistency --fix --yes
```

Opções: `--material`, `--location`.

## Limitações desta fase

- Sem compras/financeiro completo
- Sem leitor de código de barras
- Sem integração Google Workspace/Calendar/Sheets
- Sem dados fictícios no seed

## Rotas principais

- `/painel/estoque/dashboard/`
- `/painel/estoque/chapas/`
- `/painel/estoque/chapas/entrada/`
- `/painel/cadastros/chapas/` (legado, mantido)
