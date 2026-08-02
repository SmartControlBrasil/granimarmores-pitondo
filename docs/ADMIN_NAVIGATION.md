# Navegação do painel Hando

A sidebar do ERP fica em `hando/hando/templates/partials/sidebar.html`.

## Grupos (dropdowns)

Ordem fixa no código:

1. Início (`sidebarHome`)
2. Comercial (`sidebarCommercial`)
3. Operação (`sidebarOperations`)
4. Produção (`sidebarProduction`)
5. Estoque (`sidebarStock`)
6. Agenda (`sidebarSchedule`)
7. Pós-venda (`sidebarAfterSales`)
8. Mídia (`sidebarMedia`)
9. Financeiro (`sidebarFinance`)
10. Compras (`sidebarPurchasing`)
11. Comissões (`sidebarCommissions`)
12. Administração (`sidebarAdministration`)

## Padrão Hando

Cada grupo usa collapse Bootstrap nativo do template:

- link pai com `data-bs-toggle="collapse"`, `aria-expanded`, `aria-controls`
- `span.menu-arrow`
- `div.collapse` + `ul.nav-second-level`
- item ativo: `tp-link active` + `li.menuitem-active`
- grupo ativo: `collapse show` + `li.menuitem-active`

O JS em `hando/hando/static/js/app.js` mantém um dropdown aberto por vez e reforça o item ativo pela URL.

## RBAC

- Cada item filho continua com `{% has_permission %}`
- O dropdown pai só renderiza se houver ao menos um filho visível
- Separadores (`li.menu-title`) só aparecem quando há itens na seção

## Estado ativo

Tag `{% nav_active %}` em `access_control/templatetags/erp_permissions.py`:

- `app` → namespace
- `app:name` → namespace + url_name
- `app:prefix*` → prefixo do url_name
- `app:*part*` → substring do url_name
- `:name` → url_name em qualquer namespace

Sem consulta ao banco. Querystring não interfere.

## Incluir novo item

1. Confirmar que a rota e a permissão já existem
2. Inserir o `<li>` no grupo correto, com `{% has_permission %}` e `{% nav_active %}`
3. Atualizar a condição do dropdown pai se for uma permissão nova
4. Não duplicar o link em outro grupo

## Limitações

- Menu definido em template (não há editor no banco)
- Não há submenu de terceiro nível
- Rotas legadas fora do menu permanecem válidas
