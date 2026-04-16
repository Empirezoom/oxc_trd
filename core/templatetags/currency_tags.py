from django import template
from decimal import Decimal

register = template.Library()

@register.filter
def currency(value, request):
    # This filter requires the request to access pref_symbol and currency_rate
    # But filters don't have access to context easily.
    # We can assume context_processor has already run and placed them in context.
    # However, filters take (value, arg).
    # A better way is to just use a simple multiplication filter.
    try:
        if value is None: return "0.00"
        return Decimal(value)
    except:
        return value

@register.simple_tag(takes_context=True)
def convert_price(context, value):
    """Converts a value using the user's preferred currency. Use for balances/totals."""
    try:
        rate = context.get('currency_rate', Decimal('1.00'))
        symbol = context.get('pref_symbol', '$')
        if value is None: value = 0
        converted = Decimal(value) * rate
        return f"{symbol}{converted:,.2f}"
    except:
        return f"${value}"

@register.simple_tag
def usd_price(value):
    """Always displays a price in USD format — used for crypto market prices."""
    try:
        if value is None: value = 0
        amount = Decimal(value)
        return f"${amount:,.2f} USD"
    except:
        return f"${value} USD"
