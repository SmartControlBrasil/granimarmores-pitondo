import html
import re
from decimal import Decimal

from django.utils import timezone


PLACEHOLDER_WHITELIST = {
    "customer_name",
    "customer_document",
    "customer_address",
    "quote_number",
    "order_number",
    "total_value",
    "salesperson_name",
    "company_name",
    "current_date",
    "validity_date",
    "supplier_name",
    "document_title",
    "document_number",
}

_PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


def extract_placeholders(text: str) -> list[str]:
    return sorted(set(_PLACEHOLDER_RE.findall(text or "")))


def build_context_values(*, document=None, quote=None, sales_order=None, customer=None, supplier=None):
    quote = quote or getattr(document, "quote", None)
    sales_order = sales_order or getattr(document, "sales_order", None)
    customer = customer or getattr(document, "customer", None) or getattr(quote, "customer", None)
    supplier = supplier or getattr(document, "supplier", None)
    salesperson = None
    if sales_order and getattr(sales_order, "salesperson", None):
        salesperson = sales_order.salesperson
    elif quote and getattr(quote, "salesperson", None):
        salesperson = quote.salesperson

    address_parts = []
    if customer is not None:
        address = None
        addresses = getattr(customer, "addresses", None)
        if addresses is not None:
            address = addresses.filter(is_primary=True).first() or addresses.first()
        if address is not None:
            for attr in ("street", "number", "district", "city", "state"):
                value = getattr(address, attr, "") or ""
                if value:
                    address_parts.append(str(value))

    total = None
    if sales_order is not None:
        total = getattr(sales_order, "total", None)
    elif quote is not None:
        total = getattr(quote, "grand_total", None)

    validity = None
    if document and document.expiration_date:
        validity = document.expiration_date.strftime("%d/%m/%Y")
    elif quote and getattr(quote, "valid_until", None):
        validity = quote.valid_until.strftime("%d/%m/%Y")

    return {
        "customer_name": getattr(customer, "name", "") or "",
        "customer_document": getattr(customer, "document", "")
        or getattr(customer, "cpf", "")
        or getattr(customer, "cnpj", "")
        or "",
        "customer_address": ", ".join(address_parts),
        "quote_number": getattr(quote, "number", "") or "",
        "order_number": getattr(sales_order, "number", "") or "",
        "total_value": format(Decimal(str(total)), "f") if total is not None else "",
        "salesperson_name": getattr(salesperson, "display_name", "") or "",
        "company_name": "Granimármores Pitondo",
        "current_date": timezone.localdate().strftime("%d/%m/%Y"),
        "validity_date": validity or "",
        "supplier_name": getattr(supplier, "name", "") or "",
        "document_title": getattr(document, "title", "") or "",
        "document_number": getattr(document, "number", "") or "",
    }


def render_placeholders(text: str, values: dict) -> tuple[str, list[str]]:
    unknown = []
    missing = []

    def repl(match):
        key = match.group(1)
        if key not in PLACEHOLDER_WHITELIST:
            unknown.append(key)
            return match.group(0)
        value = values.get(key, "")
        if value in (None, ""):
            missing.append(key)
            return ""
        return html.escape(str(value))

    rendered = _PLACEHOLDER_RE.sub(repl, text or "")
    return rendered, sorted(set(unknown + missing))


def sanitize_html_fragment(text: str) -> str:
    """Strip dangerous tags/attributes without a heavy HTML engine."""
    if not text:
        return ""
    cleaned = re.sub(r"(?is)<script[^>]*>.*?</script>", "", text)
    cleaned = re.sub(r"(?is)<iframe[^>]*>.*?</iframe>", "", cleaned)
    cleaned = re.sub(r"(?is)\son\w+\s*=\s*([\"']).*?\1", "", cleaned)
    cleaned = re.sub(r"(?is)\son\w+\s*=\s*[^\s>]+", "", cleaned)
    cleaned = re.sub(r"(?is)javascript:", "", cleaned)
    return cleaned
