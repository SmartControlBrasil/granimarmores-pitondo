# Roadmap da Plataforma Granimarmores Pitondo

Este roadmap descreve o estado macro da plataforma com base no codigo atual e nas decisoes arquiteturais aprovadas. Ele nao declara como implementadas funcionalidades que ainda nao existem no Hando.

Legenda:

- Existente: ha models, rotas ou telas operacionais no Hando.
- Parcial: ha base de codigo ou parte do dominio, mas o fluxo ainda nao esta completo.
- Planejado: diretriz aprovada, ainda sem dominio implementado no Hando.

## Fase 1 - Presenca digital e captacao

| Item | Estado | Observacao |
| --- | --- | --- |
| Site institucional | Parcial | Ha templates e estrutura institucional na raiz, mas o Hando esta sendo consolidado como projeto principal. |
| SEO e paginas comerciais | Parcial | Ha paginas institucionais e conteudo de servicos/projetos, mas a consolidacao publica ainda esta em andamento. |
| Formulario de contato/captacao | Parcial | Historico de `ContactRequest`/backoffice legado aparece no trabalho local anterior, mas models institucionais atuais estao vazios no arquivo inspecionado. |
| Livia | Planejado | Deve captar/qualificar e registrar no Hando, sem ser fonte primaria de verdade. |
| Origem do lead | Planejado | Deve alimentar Lead no Hando. |
| Integracoes de entrada | Planejado | WhatsApp, e-mail, formularios e analytics devem respeitar fonte de verdade no ERP. |

## Fase 2 - CRM comercial

| Item | Estado | Observacao |
| --- | --- | --- |
| Clientes | Existente | `customers.Customer` e `CustomerAddress`. |
| Vendedores | Existente | `salespeople.Salesperson`, com usuario opcional e gestor. |
| Orcamentos | Existente | `quotes.Quote`, itens, medidas, acabamentos, servicos, versoes, envio e politica comercial. |
| Permissoes comerciais | Existente | Codigos como `customers.*`, `salespeople.*`, `quotes.*`. |
| Margem/custo restritos | Parcial | Existem campos e permissoes como `quotes.view_cost` e `quotes.view_margin`; uso deve continuar protegido no backend. |
| Leads | Planejado | Devem ser incorporados ao Hando antes de uso operacional. |
| Oportunidades | Planejado | Devem ser incorporadas ao Hando e vinculadas a lead/cliente/vendedor. |
| Follow-ups | Planejado | Devem pertencer ao CRM do Hando. |
| Ranking de vendedores | Planejado | Deve derivar de dados do Hando. |
| Score comercial | Planejado | Deve derivar de leads, oportunidades e orcamentos do Hando. |
| Metas | Planejado | Deve usar usuarios/vendedores e auditoria do Hando. |

## Fase 3 - Producao

| Item | Estado | Observacao |
| --- | --- | --- |
| Materiais | Existente | `materials.Material`, categorias, historico de preco e chapas. |
| Categorias | Existente | `materials.MaterialCategory`. |
| Acabamentos | Existente | `materials.FinishType`. |
| Servicos adicionais | Existente | `materials.AdditionalService`. |
| Chapas | Existente | `materials.MaterialSlab`. |
| Pedido | Planejado | Deve nascer de orcamento aceito/aprovado. |
| Ordem de producao | Planejado | Deve ser modelada no Hando. |
| Etapas de producao | Planejado | Medicao, corte, acabamento, polimento, inspecao e expedicao. |
| Instalacao | Planejado | Deve se conectar a pedido/producao e pos-venda. |
| Pos-venda | Planejado | Deve ficar no Hando e usar clientes/pedidos. |

## Fase 4 - Marketing intelligence

| Item | Estado | Observacao |
| --- | --- | --- |
| Biblioteca de imagens | Planejado | Arquivos podem ficar em storage, mas metadados devem ficar no Hando. |
| Analytics de captacao | Planejado | Deve consolidar origem, campanha, canal e conversao. |
| Dashboards executivos | Parcial | Dashboard Hando existe; indicadores finais por area ainda devem evoluir. |
| Funil comercial | Planejado | Depende de Lead e Opportunity no Hando. |
| Campanhas | Planejado | Devem alimentar Leads e Analytics. |
| Agentes de IA | Planejado | Devem respeitar RBAC, escopo e auditoria. |

## Fase 5 - Escala

| Item | Estado | Observacao |
| --- | --- | --- |
| RBAC operacional | Existente | `AccessRole`, `AccessPermission`, `RolePermission`, `UserAccess`. |
| Escopos de dados | Existente | `OWN`, `TEAM`, `DEPARTMENT`, `ALL` em `DataScope`. |
| Auditoria | Existente | `AuditEvent`, `UserSessionLog`, middleware e services. |
| Patrimonio | Existente | `assets.Asset`, categorias e documentos. |
| Frota | Existente | `fleet.Vehicle`. |
| Manutencao | Existente | Planos, ordens, pecas e anexos. |
| Financeiro | Planejado | Contas, caixa, pagamentos e conciliacao ainda nao existem como dominio completo. |
| Relatorios avancados | Planejado | Devem derivar das fontes centrais do Hando. |
| Integracoes maduras | Planejado | Nao podem virar fonte primaria de verdade. |
| Governanca multi-area | Parcial | Base de RBAC e auditoria existe; processos por area ainda devem ser expandidos. |

## Checkpoints recomendados

1. Consolidar roteamento publico com `/` para site e `/painel/` para Hando.
2. Estabilizar identidade visual do Hando apos cada alteracao de menu/layout.
3. Incorporar Leads ao Hando com fonte unica.
4. Incorporar Oportunidades ao Hando com vinculo a Lead, Customer e Salesperson.
5. Integrar orcamento aceito ao futuro pedido.
6. Modelar pedido e producao sem duplicar Quote.
7. Modelar financeiro como modulo do Hando.
8. Conectar integracoes e agentes de IA sempre com RBAC, auditoria e metadados no ERP.
