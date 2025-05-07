from django import template
from decimal import Decimal

register = template.Library()

@register.filter
def multiply(value, arg):
    """Multiplies the value by the argument"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return '' 

@register.filter
def dictsumattr(items, attr):
    """Sums up a specific attribute from a list of dictionaries"""
    try:
        total = sum(item[attr] for item in items)
        return total
    except (KeyError, TypeError):
        return 0 