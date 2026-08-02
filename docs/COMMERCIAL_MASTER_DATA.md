# Cadastros mestres comerciais

Documentação dos cadastros compartilhados entre clientes, orçamentos e futuras fases de CRM da Granimármores Pitondo.

## App e localização

Os cadastros mestres ficam no app Django `commercial` (`hando/commercial/`), separado de `customers` e `quotes` para evitar acoplamento indevido. Clientes e orçamentos referenciam esses cadastros por chave estrangeira opcional.

## Cadastros

| Cadastro | Modelo | Finalidade |
|----------|--------|------------|
| Origem comercial | `CommercialSource` | Como o cliente descobriu a empresa |
| Canal de contato | `ContactChannel` | Meio usado no atendimento |
| Tipo de projeto | `ProjectType` | Tipologia comercial/produtiva do interesse |
| Parceiro comercial | `CommercialPartner` | Arquitetos, construtoras, indicadores etc. |
| Motivo de perda | `LossReason` | Classificação futura de oportunidades perdidas |
| Região de atendimento | `ServiceRegion` | Área geográfica atendida e parâmetros operacionais |

### Origem x canal

- **Origem comercial:** de onde veio a oportunidade (Google, indicação, parceiro, tráfego pago…).
- **Canal de contato:** por onde ocorreu o atendimento (WhatsApp, telefone, formulário do site…).

Não misturar os dois conceitos no mesmo cadastro.

### Parceiro x cliente

Parceiro comercial representa quem indica ou influencia vendas. Cliente representa quem compra. Um parceiro pode gerar vários clientes/orçamentos no futuro; nesta fase o detalhe do parceiro exibe placeholder estruturado até o CRM.

## Integrações

### Cliente (`Customer`)

Campos opcionais:

- `commercial_source`
- `partner`
- `project_type_interest`
- `preferred_contact_channel`

Formulário interno do painel exibe e filtra esses campos. O formulário público institucional **não** foi alterado nesta fase.

### Orçamento (`Quote`)

Campos opcionais:

- `project_type`
- `commercial_source`
- `partner`

Regra adotada:

1. na criação, se o orçamento não informar esses campos, copia do cliente quando disponíveis;
2. o usuário pode ajustar no orçamento;
3. alterações no orçamento **não** sobrescrevem o cadastro do cliente.

Workflow de perda, PDF e cálculos financeiros não foram alterados.

## Rotas do painel

Prefixo: `/painel/cadastros/`

| Rota | Nome |
|------|------|
| `/resumo/` | Resumo de Cadastros |
| `/origens/` | Origens comerciais |
| `/tipos-projeto/` | Tipos de projeto |
| `/parceiros/` | Parceiros comerciais |
| `/motivos-perda/` | Motivos de perda |
| `/regioes/` | Regiões de atendimento |
| `/canais/` | Canais de contato |
| `/robots.txt` | *(não aplicável — site institucional)* |

## Permissões

Padrão: `<modulo>.view|create|update|deactivate`

Módulos: `commercial_sources`, `project_types`, `commercial_partners`, `loss_reasons`, `service_regions`, `contact_channels`.

### Cargos de sistema (seed conservador)

| Cargo | Escopo nos cadastros mestres |
|-------|------------------------------|
| Administrativo | Acesso total (via `has_full_access`) |
| Gestor Comercial | CRUD dos cadastros mestres |
| Vendedor | Somente visualização |
| Operacional | Visualiza tipos de projeto e regiões |

O seed usa `get_or_create` em `RolePermission` para **não sobrescrever** personalizações existentes.

## Seeds

Comando idempotente:

```bash
python manage.py setup_erp_foundation
```

Popula origens, canais, tipos de projeto e motivos de perda institucionais. **Não** cria parceiros, regiões, clientes ou vendas fictícias.

## Filtros disponíveis

- **Origens:** nome, grupo, ativo
- **Tipos de projeto:** nome, ativo
- **Parceiros:** nome/contato/telefone/documento, tipo, cidade, UF, responsável, ativo
- **Motivos de perda:** nome, categoria, ativo
- **Regiões:** nome, cidade, UF, atendimento habilitado, ativo
- **Canais:** nome, ativo
- **Clientes:** origem, parceiro (além de busca por nome)
- **Orçamentos:** origem, tipo de projeto, parceiro (além de status/número)

## Exclusão

Cadastros usam desativação lógica (`SoftDeleteModel`). Exclusão física é bloqueada quando há referências em clientes ou orçamentos (origem, parceiro, tipo, canal).

## Auditoria

Mutations registradas via `audit.services.record_audit_event` com `module="commercial"`.

## Limitações / próxima fase

- `LossReason` ainda não integrado ao workflow de orçamento perdido.
- Parceiro sem painel de comissão ou vínculos reais de vendas.
- Região sem cálculo automático de frete.
- Blog/lead dedicado reservado para CRM (campos como funil, etapa, responsável por lead).
- `BlogPosting`/artigos permanecem estáticos no site institucional.
