from django import template

register = template.Library()

@register.filter
def mul(value, arg):
    """Multiplica value por arg"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def add(value, arg):
    """Adiciona arg a value"""
    try:
        return float(value) + float(arg)
    except (ValueError, TypeError):
        return 0