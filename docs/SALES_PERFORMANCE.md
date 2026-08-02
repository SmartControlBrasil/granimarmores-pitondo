# Desempenho Comercial — Granimármores Pitondo

Documentação de metas, score, ranking e indicadores operacionais.

## Definições de indicadores

| Indicador | Definição |
|-----------|-----------|
| Lead recebido | Lead criado no período (`created_at`) |
| Lead atendido | `first_contact_at` preenchido ou atividade de contato válida |
| Lead convertido | `converted_customer` preenchido |
| Lead ganho | Status `won` |
| Lead perdido | Status `lost` |
| Orçamento enviado | Status `sent` via workflow `send_quote()` |
| Venda fechada | Status `accepted` no orçamento (aceite do cliente) |

### Valor potencial

Soma de `estimated_value` em leads abertos + `grand_total` de orçamentos em pipeline (`sent`, `viewed`, `approved`).

**Não** representa faturamento.

### Valor aprovado

Soma de `grand_total` de orçamentos com status `accepted` no período (`accepted_at`).

**Limitação:** o workflow de aceite de orçamento (`QuoteStatus.ACCEPTED`) existe no modelo, mas ainda não possui tela/serviço dedicado. Indicadores monetários de venda usam somente registros já aceitos.

## Score

Pontuação calculada por eventos imutáveis em `SalesScoreEvent`, conforme `SalesScorePolicy` vigente.

### Eventos positivos (configuráveis)

- Primeiro contato
- Lead qualificado
- Medição concluída
- Orçamento enviado
- Follow-up concluído no prazo
- Lead ganho
- Bônus por valor vendido (fator × `grand_total` aceito)

### Penalidades (configuráveis)

- Lead sem primeiro contato após 48h
- Follow-up vencido
- Perda sem motivo adequado
- Orçamento expirado sem retorno

Penalidades são idempotentes por referência (`lead`, `lead_task`, `quote`).

## Metas (`SalesGoal`)

Metas por vendedor e intervalo. Situações:

- **Atingida** — progresso médio ≥ 100%
- **No ritmo** — progresso adequado
- **Em risco** — progresso < 60% com período em andamento
- **Sem dados** — sem movimento no período
- **Encerrada** — período finalizado

Projeção linear documentada: `(realizado / dias decorridos) × dias totais`.

## Ranking

Rota: `/painel/comercial/ranking/`

Critérios: score, valor aprovado, conversão, tempo de resposta, follow-up, ganhos, orçamentos enviados.

Empates: critério secundário determinístico (ex.: mais ganhos, depois nome).

## Escopo

Reutiliza escopo comercial existente (`customer_scope` / equipe via `Salesperson.manager`).

| Perfil | Acesso |
|--------|--------|
| Gestor | Equipe completa, metas, ranking |
| Vendedor | Próprio desempenho e ranking limitado |
| Operacional | Sem acesso a desempenho |

## Permissões

Módulos: `sales_goals`, `sales_score_policy`, `sales_score_events`, `sales_performance`, `sales_ranking`.

Seed conservador em `setup_erp_foundation`.

## Comandos

```bash
python manage.py process_commercial_score [--start YYYY-MM-DD] [--end YYYY-MM-DD] [--dry-run]
python manage.py rebuild_commercial_score --start YYYY-MM-DD --end YYYY-MM-DD --dry-run
python manage.py rebuild_commercial_score --start ... --end ... --confirm
```

- `process_commercial_score` — penalidades idempotentes
- `rebuild_commercial_score` — reconstrói eventos a partir de dados reais (exige período; `--confirm` para execução)

## Limitações atuais

- Aceite formal de orçamento (`accepted`) sem UI dedicada
- Sem comissão financeira
- Sem notificações externas
- Sem pontuação retroativa automática no seed
- Sem ranking gamificado / badges

## Preparação futura

- Formulário público de leads (pontuação via `external_source`)
- Integração Lívia
- Workflow de aceite de orçamento integrado ao score de venda
