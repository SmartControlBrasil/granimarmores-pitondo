# RBAC — Granimármores Pitondo

Autorização do ERP Hando via **Role-Based Access Control** (RBAC).

## Modelo

| Modelo | Descrição |
|--------|-----------|
| `AccessPermission` | Permissão atômica (`code`, `module`, `action`) |
| `AccessRole` | Cargo (papel) com escopos de dados |
| `RolePermission` | Liga cargo ↔ permissão |
| `UserAccess` | Liga usuário ↔ cargo (com vigência) |

Catálogo de permissões: `hando/access_control/permissions.py`  
Serviço de autorização: `hando/access_control/services/authorization.py`

## Cargos iniciais (seed)

Criados por `python manage.py setup_erp_foundation`:

| Cargo | `hierarchy_level` | `has_full_access` | Escopo padrão |
|-------|-------------------|-------------------|---------------|
| Administrativo | 1 | Sim | ALL |
| Gestor Comercial | 20 | Não | TEAM |
| Vendedor | 50 | Não | OWN |
| Operacional | 60 | Não | OWN |
| Consulta | 90 | Não | OWN |

O cargo **Administrativo** recebe **todas** as permissões ativas no seed.

## Escopos de dados (`DataScope`)

Definidos em `AccessRole` por recurso:

| Escopo | Significado |
|--------|-------------|
| `own` | Próprios registros |
| `team` | Equipe (via hierarquia/gestor) |
| `department` | Departamento |
| `all` | Todos |

Campos por recurso:

- `customer_scope`
- `quote_scope`
- `asset_scope`
- `maintenance_scope`

Services de query (ex.: `quotes/services/query.py`) filtram registros conforme escopo + permissão.

## Permissões

Formato: `<modulo>.<acao>` (ex.: `quotes.view`, `roles.manage_permissions`).

Grupos principais:

| Módulo | Exemplos |
|--------|----------|
| `dashboard` | `dashboard.view` |
| `users` | `users.view`, `users.create`, `users.manage_roles` |
| `roles` | `roles.view`, `roles.create`, `roles.manage_permissions` |
| `customers` | `customers.view`, `customers.create` |
| `quotes` | `quotes.view`, `quotes.approve`, `quotes.view_margin` |
| `materials` | `materials.view`, `materials.change_price` |
| `audit` | `audit.view`, `audit.export` |
| `settings` | `settings.view`, `settings.update` |

Lista completa: `hando/access_control/permissions.py`.

## Hierarquia de checagem

Função `user_has_permission(user, code)`:

1. Usuário autenticado e ativo?
2. `is_superuser` → **permitido**
3. Cargo com `has_full_access` → **permitido**
4. Permissão explícita via `RolePermission` → **permitido**
5. Caso contrário → **negado**

## Filtragem do menu lateral

Template: `hando/hando/templates/partials/sidebar.html`  
Templatetag: `{% has_permission "code" as can_x %}` (`access_control/templatetags/erp_permissions.py`)

Seções do menu:

| Seção | Permissões típicas |
|-------|-------------------|
| Cadastros | `customers.view`, `salespeople.view`, `users.view` |
| Comercial | `quotes.view`, `materials.view`, `quotes.manage_policy` |
| Patrimônio | `assets.view`, `vehicles.view` |
| Manutenção | `maintenance.view` |
| Administração | `roles.view`, `audit.view`, `settings.view` |

### Menu ausente ≠ módulo inexistente

Se um usuário **não vê** "Cargos e níveis de acesso", "Orçamentos" ou "Clientes":

- O módulo **pode existir** e estar implementado.
- O menu é **ocultado por UX** quando falta permissão.
- Acessar a URL diretamente sem permissão deve resultar em **403** ou redirecionamento (views protegidas).

**Não concluir** que a funcionalidade foi removida só porque o item sumiu do sidebar.

## URLs administrativas (RBAC)

Base: `/painel/administracao/`

| Função | URL |
|--------|-----|
| Usuários | `/painel/administracao/usuarios/` |
| Acesso de usuário | `/painel/administracao/usuarios/<id>/acessos/` |
| Cargos | `/painel/administracao/acessos/` |
| Matriz de permissões | `/painel/administracao/acessos/<id>/permissoes/` |
| Lista de permissões | `/painel/administracao/permissoes/` |
| Sessões | `/painel/administracao/sessoes/` |
| Auditoria | `/painel/administracao/auditoria/` |

## Acesso administrativo

Para gerenciar cargos e permissões, o usuário precisa de:

- `roles.view` — ver cargos e menu Administração
- `roles.manage_permissions` — editar matriz
- `users.view` / `users.manage_roles` — gerenciar usuários e acessos

Cargo **Administrativo** (`has_full_access=True`) ou **superusuário** têm acesso total.

## Signup público

`ACCOUNT_ALLOW_REGISTRATION=False` por padrão. Funcionários são criados por administradores em `/painel/administracao/usuarios/`, não por registro público.

## Configuração inicial

```bash
python manage.py createsuperuser
python manage.py setup_erp_foundation
python manage.py setup_erp_foundation --admin-username=<username>
```

## Diagnóstico: usuário não vê determinada função

Checklist:

1. **Usuário ativo?** (`is_active=True`)
2. **Tem `UserAccess` vigente?** (`/painel/administracao/usuarios/<id>/acessos/`)
3. **Cargo ativo?** (`AccessRole.is_active`)
4. **Permissão no cargo?** Matriz em `/painel/administracao/acessos/<id>/permissoes/`
5. **Escopo adequado?** Vendedor com `OWN` não vê orçamentos de colegas.
6. **Superusuário?** Bypassa RBAC.
7. **Menu vs backend:** confirmar URL direta; se 403, é permissão; se 404, rota inexistente.

### Consulta rápida (Django shell)

```python
from django.contrib.auth import get_user_model
from access_control.services.authorization import get_user_access, user_has_permission

user = get_user_model().objects.get(username="...")
access = get_user_access(user)
print(access.role if access else "Sem cargo")
print(user_has_permission(user, "quotes.view"))
print(user_has_permission(user, "roles.view"))
```

## Auditoria de alterações RBAC

Alterações em cargos, permissões e acessos de usuário devem gerar eventos em `audit` (middleware + services). Consultar `/painel/administracao/auditoria/` com permissão `audit.view`.
