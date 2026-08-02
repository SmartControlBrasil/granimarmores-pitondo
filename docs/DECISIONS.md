# Decisões arquiteturais — Granimármores Pitondo

Registro oficial de decisões imutáveis ou de alta importância. Alterações estruturais exigem **auditoria de impacto e testes** antes da implementação.

> Documentos complementares legados: `docs/DECISOES_ARQUITETURAIS.md`, `docs/ARQUITETURA_E_DIRETRIZES.md`.

---

## D-001 — Site e ERP formam uma única plataforma

**Decisão:** O site institucional e o ERP Hando pertencem ao **mesmo produto** e ao **mesmo deploy**.

**Consequências:**

- Compartilham banco, autenticação e infraestrutura.
- Lead captado no site alimenta módulos comerciais do ERP.
- Não há “dois sistemas” independentes em produção.

---

## D-002 — Existe apenas um projeto Django executável

**Decisão:** O único ponto de entrada é `manage.py` na raiz, com settings em `config/`.

**Consequências:**

- **Não** usar `hando/manage.py` (legado do template Cookiecutter).
- **Não** tratar `hando/config/` como configuração principal.
- **Não** criar segundo `manage.py` ou settings paralelos.

---

## D-003 — O painel Hando deve ser preservado visualmente

**Decisão:** A UI do ERP em `hando/hando/templates/` e `hando/hando/static/` (template Hando adquirido) é a referência visual oficial.

**Consequências:**

- Sidebar, topbar, componentes, ícones, temas claro/escuro e responsividade devem ser **preservados**.
- Evoluções estendem o template; **não** substituem por layouts improvisados ou listas HTML cruas.
- Referência histórica: commit `4611dda` (identidade do usuário no topbar).

---

## D-004 — O site institucional ocupa as rotas públicas

**Decisão:** Conteúdo marketing e captacao ficam em `/` (`src/institutional/`).

**Consequências:**

- 13 rotas públicas + 3 artigos de blog (confirmado em `presentation/urls.py`).
- Templates em `templates/institutional/`, estáticos em `static/institutional/`.
- Sitemap em `/sitemap.xml`.

---

## D-005 — O ERP ocupa `/painel/`

**Decisão:** Toda operação interna autenticada fica sob `/painel/`.

**Consequências:**

- Dashboard: `/painel/` (`pages:dashboard`).
- Módulos: `/painel/clientes/`, `/painel/comercial/orcamentos/`, etc.
- **Proibido** criar backoffices operacionais paralelos (ex.: `/app/` com auth própria).

---

## D-006 — Banco e usuário são compartilhados

**Decisão:** Um `DATABASE_URL`, um `AUTH_USER_MODEL = users.User`.

**Consequências:**

- Migrations de todos os apps no mesmo banco.
- Allauth e RBAC operam sobre o mesmo usuário.
- Não duplicar `User`, `Customer` ou `Quote`.

---

## D-007 — Formulário público alimenta o cadastro do ERP

**Decisão:** Contato/orçamento do site persiste em `customers.Customer` via `contact_requests.py`.

**Consequências:**

- Deduplicação por telefone/e-mail.
- Auditoria via `audit.services.record_audit_event`.
- E-mail para `CONTACT_RECIPIENT_EMAIL`.
- Equipe comercial trabalha leads em `/painel/clientes/`.

---

## D-008 — Autorização é feita por RBAC

**Decisão:** `AccessRole` / `AccessPermission` / `RolePermission` / `UserAccess` são a **única** autoridade de permissões operacionais.

**Consequências:**

- Seed: `python manage.py setup_erp_foundation`.
- Views e services validam permissão + escopo.
- Menu oculta itens por UX; backend **sempre** valida.
- Não criar sistema paralelo de grupos/cargos.

Detalhes: [RBAC.md](RBAC.md)

---

## D-009 — Não deve haver signup público para funcionários

**Decisão:** `ACCOUNT_ALLOW_REGISTRATION=False` por padrão.

**Consequências:**

- Funcionários criados por administradores.
- Login em `/accounts/login/`; registro público desabilitado.
- MFA disponível via allauth (configurável).

---

## D-010 — Alterações estruturais exigem auditoria e testes

**Decisão:** Mudanças que afetem arquitetura, RBAC, modelos centrais ou rotas exigem revisão prévia.

**Checklist mínimo:**

1. Impacto documentado (este repositório ou issue).
2. `python manage.py check`
3. `python manage.py test` (subset ou suite completa)
4. Verificação manual de rotas públicas e `/painel/`
5. Sem regressão no fluxo formulário → cliente → auditoria

**Exemplos de mudança estrutural:**

- Novo painel ou prefixo de URL operacional
- Novo model duplicando domínio existente
- Mover apps entre diretórios
- Alterar `AUTH_USER_MODEL` ou `ROOT_URLCONF`
- Substituir template Hando

---

## Histórico de consolidação

| Marco | Commit (referência) | Descrição |
|-------|---------------------|-----------|
| Consolidação unificada | `972a93c` | ERP Hando + formulário institucional no projeto raiz |
| Identidade topbar | `4611dda` | Topbar Hando |
| Sitemap | `7a0fb72` | `/sitemap.xml` institucional |

---

## Itens a validar (não decididos no código)

- Configuração exata de systemd / OpenLiteSpeed na VPS
- Implementação de `robots.txt`
- `config/settings/test.py` na raiz (pytest do `hando/pyproject.toml` referencia settings inexistente na raiz)
- Política de backup automatizado de `media/` e PostgreSQL
