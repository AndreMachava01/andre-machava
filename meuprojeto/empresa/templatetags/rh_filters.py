from django import template

register = template.Library()

@register.filter
def div(value, arg):
    """Divide value by arg"""
    try:
        return float(value) / float(arg)
    except (ValueError, ZeroDivisionError):
        return 0

@register.filter
def get_item(dictionary, key):
    """Get item from dictionary by key"""
    if isinstance(dictionary, dict):
        return dictionary.get(key, '')
    return ''

@register.filter
def get_criterio_nota(notas_criterios, criterio_id):
    """Get nota for specific criterio"""
    if isinstance(notas_criterios, dict) and criterio_id in notas_criterios:
        return notas_criterios[criterio_id].get('nota', '')
    return ''

@register.filter
def get_criterio_obs(notas_criterios, criterio_id):
    """Get observacoes for specific criterio"""
    if isinstance(notas_criterios, dict) and criterio_id in notas_criterios:
        return notas_criterios[criterio_id].get('observacoes', '')
    return ''