# Decisoes Arquiteturais da Plataforma Granimarmores Pitondo

Este documento registra decisoes imutaveis ou de alta importancia. Qualquer mudanca nestas decisoes exige revisao humana explicita antes de implementacao.

## ADR-001 - Painel administrativo unico

Decisao: Hando e o painel administrativo oficial.

Consequencias:

- Nao criar outro backoffice operacional.
- Toda area nova deve entrar como modulo do Hando.
- Django Admin pode existir apenas como ferramenta tecnica.
- A separacao entre areas ocorre por RBAC, nao por paineis separados.

## ADR-002 - RBAC unico

Decisao: `AccessRole` / `AccessPermission` / `RolePermission` / `UserAccess` sao autoridade de autorizacao.

Consequencias:

- Nao criar sistema paralelo de cargos/permissoes.
- Menu lateral pode esconder itens por UX, mas backend deve validar permissao.
- Views, services e endpoints devem respeitar permissao e escopo.
- `has_full_access` e hierarquia devem continuar centralizados no RBAC do Hando.

## ADR-003 - Marco visual Hando

Decisao: Commit `4611dda` e referencia historica visual/funcional aprovada.

Mensagem do commit: `fix: finaliza identidade do usuario no topbar do ERP`.

Consequencias:

- Evolucoes visuais devem preservar a identidade do Hando.
- Sidebar, topbar, componentes, icones, dark/light, collapses, cards, tabelas, modais e responsividade devem ser mantidos.
- Nao substituir o template Hando por lista HTML simples ou layout improvisado.

## ADR-004 - Sem fontes paralelas de verdade

Decisao: Entidades centrais nao podem ser duplicadas em modulos concorrentes.

Consequencias:

- Nao criar outro `User` operacional.
- Nao criar outro `Quote` para o mesmo dominio comercial.
- Nao duplicar `Customer` ou `Salesperson`.
- Lead, Opportunity, Sale, Order, Production e Finance devem ser modelados ou incorporados no Hando.
- Integracoes externas nao sao fonte primaria de verdade.

## ADR-005 - Auditoria desde a origem

Decisao: Toda acao operacional relevante deve ser rastreavel.

Consequencias:

- Alteracoes relevantes devem gerar `AuditEvent` ou trilha equivalente.
- Eventos devem registrar usuario, data/hora, modulo, acao, registro afetado e metadados seguros.
- Acoes sensiveis de usuario, permissao, preco, margem, aprovacao, envio, cancelamento, exportacao e integracao devem ser auditadas.
- Agentes de IA tambem devem produzir rastreabilidade quando consultarem ou alterarem dados operacionais.

## ADR-006 - Isolamento por permissao

Decisao: Financeiro, Comercial, Producao e demais areas sao isoladas por RBAC, nao por paineis separados.

Consequencias:

- Vendedores devem ver somente dados permitidos por permissao e escopo.
- Financeiro deve ter permissoes especificas para caixa, pagamentos e relatorios financeiros.
- Producao deve acessar pedidos, ordens e dados tecnicos sem receber dados financeiros sensiveis por padrao.
- Diretoria pode ter visao ampla por permissoes e escopos adequados.

## ADR-007 - Arquitetura publica raiz e painel

Decisao: a arquitetura publica preferencial e `/` para o site institucional e `/painel/` para o Hando.

Consequencias:

- O dashboard operacional do Hando deve responder em `/painel/`.
- Modulos operacionais devem ficar sob `/painel/`.
- A raiz `/` deve permanecer disponivel para o site institucional.
- Rotas tecnicas de autenticacao podem preservar caminhos necessarios ao allauth, desde que o painel operacional unico continue sendo o Hando.

## ADR-008 - Projeto raiz legado temporario

Decisao: o projeto raiz atual e legado temporario durante a migracao; o Hando sera o Django project principal.

Consequencias:

- O legado pode ser usado como referencia temporaria de regras e funcionalidades.
- Nao migrar entidade central sem definir fonte de verdade no Hando.
- Nao alterar `AUTH_USER_MODEL` nesta fase.
- Remocoes definitivas devem ocorrer apenas em fase propria, com checkpoint e testes.
