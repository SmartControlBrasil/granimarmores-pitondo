# Gestão de Documentos e Contratos

Módulo interno do ERP Hando em `/painel/documentos/`.

O módulo registra documentos, aprovações, aceites e assinaturas.
Não substitui assessoria jurídica, certificação digital ou assinatura eletrônica qualificada.

O módulo não utiliza Google Drive ou Google Workspace.
Os arquivos pertencem à infraestrutura própria do ERP.

## Tipos

`DocumentType` com categorias (commercial, contract, technical, operational, financial, supplier, warranty, consent, internal, other).
Seed cria apenas cadastros de tipo — sem contratos, cláusulas ou documentos preenchidos.

## Modelos

`DocumentTemplate` com status draft → under_review → approved → inactive/archived.
Formatos: html, plain_text, uploaded_file.
Modelo aprovado não deve ser alterado diretamente; nova alteração gera nova versão/registro.

## Placeholders

Whitelist segura (`{{ customer_name }}`, `{{ quote_number }}`, etc.).
Sem `eval`, sem acesso arbitrário a atributos.
Placeholders desconhecidos geram aviso; valores são escapados; dados ausentes não são inventados.

## Documentos

`ManagedDocument` com numeração `DOC-AAAA-######`.
Status operacional controlado por services (não editar status direto na UI de cadastro).
Exige contexto (cliente, pedido, fornecedor…) ou justificativa.

## Confidencialidade

Níveis: public_internal, internal, restricted, confidential.
Download e listagem respeitam RBAC; confidencial exige `document_confidential.view`.

## Versões

`DocumentVersion` com sequência por documento, checksum SHA-256 e imutabilidade após aprovação.
Nova edição gera nova versão; arquivo via `MediaAsset` quando aplicável.

## Revisão e aprovação

`DocumentReview` e `DocumentApprovalStep` (sequência simples).
Aprovação interna ≠ aceite externo.
Rejeição exige motivo.

## Envio e visualização

Registro manual de envio/visualização (não envia e-mail/WhatsApp).
Status `sent`/`viewed` apenas com evento registrado.

## Aceite e assinatura registrada

`DocumentAcceptance` e `DocumentSignatureRecord`.
Somente registro operacional; sem ICP-Brasil, Clicksign ou DocuSign.
Aceite vincula versão aprovada exata; não apagar aceite.

## Vigência, renovação e cancelamento

Ativação após requisitos; expiração via `sync_document_statuses`.
Renovação cria novo documento vinculado (`renewed_from`), sem copiar aceite/assinatura.
Cancelamento/encerramento exigem motivo e preservam histórico.

## Anexos e aditivos

`DocumentAttachment` aponta para `MediaAsset`.
`DocumentRelationship` para amendment, renewal, replacement, etc.

## Integrações

Links no detalhe de orçamento, pedido, compra e pós-venda.
Não substitui PDF comercial nem `accept_quote()`.

## RBAC e auditoria

Permissões `documents.*`, `document_templates.*`, `document_types.*`, `document_reviews.*`, `document_confidential.view`, `document_dashboard.view`.
Eventos auditados em criação, versão, aprovação, envio, aceite, assinatura, impressão e exportação.

## Comandos

```bash
python manage.py sync_document_statuses --dry-run
python manage.py audit_document_consistency --dry-run
```

## Configuração

- `DOCUMENT_EXPIRATION_WARNING_DAYS` (default 30)
- `DOCUMENT_MAX_UPLOAD_SIZE_MB` (default 20)

## Limitações

- Sem assinatura digital qualificada
- Sem envio automático de e-mail/WhatsApp
- Sem gerador PDF jurídico novo nesta fase
- Sem cláusulas/contratos fictícios no seed
- Sem Google Drive / Google Workspace
