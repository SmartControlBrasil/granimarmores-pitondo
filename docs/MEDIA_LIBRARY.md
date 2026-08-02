# Biblioteca Interna de Mídias

Módulo ERP `media_library` para organização, rastreabilidade e aprovação de imagens/documentos da Granimármores Pitondo.

**A biblioteca não utiliza Google Drive ou Google Workspace. Os arquivos pertencem ao ERP e são armazenados conforme a infraestrutura própria.**

## Conceitos

- **MediaAsset**: arquivo + metadados + status + visibilidade + vínculos principais.
- **MediaCategory**: classificação configurável (seed idempotente).
- **MediaTag**: etiquetas opcionais (sem seed obrigatório).
- **MediaAssetLink**: vínculos adicionais explícitos.
- **MediaCollection / MediaCollectionItem**: álbuns e capa.
- **BeforeAfterPair**: comparação antes/depois.
- **MediaReview**: aprovação técnica (não é autorização pública).
- **PublicationCandidate**: planejamento futuro — **não publica**.
- **MediaUsageConsent** (pós-venda): único mecanismo de autorização de uso.

## Numeração

`MID-AAAA-NNNNNN` e coleções `COL-AAAA-NNNNNN` via contadores transacionais.

## Validação

Extensão, MIME real (assinatura), tamanho, imagem/PDF válido, nome seguro, bloqueio de executáveis.

Settings:

- `MEDIA_LIBRARY_MAX_IMAGE_SIZE_MB` (default 10)
- `MEDIA_LIBRARY_MAX_DOCUMENT_SIZE_MB` (default 20)
- `MEDIA_LIBRARY_ALLOWED_IMAGE_TYPES`
- `MEDIA_LIBRARY_ALLOWED_DOCUMENT_TYPES`
- `MEDIA_LIBRARY_MAX_FILES_PER_BATCH`

## Armazenamento

```text
media/library/AAAA/MM/MID-.../arquivo_seguro.ext
media/library/AAAA/MM/MID-.../thumbs/...
```

Checksum SHA-256; duplicidade detectada e reutilização opcional.

## Consentimento e portfólio

`evaluate_media_consent(asset)` reutiliza `MediaUsageConsent`.

Portfólio exige: aprovação técnica, consentimento compatível, alt text, título e vínculo com obra/material.

## Acesso privado

Download/visualização em `/painel/midias/<id>/arquivo/` com autenticação, RBAC e escopo.

Em produção, o servidor web (ex.: OpenLiteSpeed) não deve servir `MEDIA_URL` publicamente para `media/library/`; o Django deve mediar o acesso.

## Comandos

```bash
python manage.py audit_media_library --dry-run
python manage.py rebuild_media_metadata --dry-run
python manage.py rebuild_media_metadata --fix --confirm
```

## Limitações

- Sem CDN, sem Google Drive/Photos/Workspace.
- Sem publicação automática (site/redes/Google Meu Negócio).
- Vídeos sem transcodificação nesta fase.
- Miniaturas síncronas via Pillow; falha não invalida o original.
- Exclusão física controlada fica para processo futuro; padrão é arquivamento/exclusão lógica.
