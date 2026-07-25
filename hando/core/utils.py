from decimal import Decimal


def format_brl(value):
    if value is None:
        value = Decimal("0.00")
    value = Decimal(value).quantize(Decimal("0.01"))
    formatted = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {formatted}"
