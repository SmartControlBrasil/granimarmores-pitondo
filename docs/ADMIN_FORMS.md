# Padronização de formulários do painel

Padrão visual global dos formulários do ERP Hando (FASE DE HOMOLOGAÇÃO UI 01).

Não altera o site institucional.

## Camadas

1. **Mixin/helper** — `hando/hando/forms.py`
   - `BootstrapFormMixin`
   - `apply_bootstrap_classes(form)`
2. **Template tag** — `{% erp_form_fields form %}` (`core/templatetags/erp_forms.py`)
3. **Hub** — `hando/hando/templates/erp/form.html`
4. **CSS** — `hando/hando/static/css/erp-forms.css` (carregado no `base.html` do painel)

## Uso

```python
from hando.forms import BootstrapFormMixin

class MeuForm(BootstrapFormMixin, forms.ModelForm):
    field_widths = {
        "nome": "col-md-6",
        "status": "col-md-6",
    }
```

```django
{% load erp_forms %}
<form method="post" class="erp-form" novalidate>
  {% csrf_token %}
  {% erp_form_fields form %}
  <div class="erp-form-actions mt-4">
    <button class="btn btn-primary" type="submit">Salvar</button>
  </div>
</form>
```

Ou estender `erp/form.html`.

## Classes aplicadas

| Widget | Classe |
|--------|--------|
| input/textarea/file | `form-control` |
| select | `form-select` |
| checkbox/radio | `form-check-input` |
| campo com erro (bound) | `is-invalid` |

O CSS `.erp-form` também estiliza widgets sem classe (fallback), inclusive no tema escuro.

## Crispy Forms

Módulos que já usam Crispy (after_sales, media_library, auth) podem continuar.
Não é obrigatório migrar para Crispy nesta fase.

## Piloto

`QuoteForm` (`quotes/forms.py`) com labels em português e grid (`field_widths`).
