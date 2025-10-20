from django import template

register = template.Library()

@register.filter
def get_item_value(obj, field_name):
    """
    Retorna o valor de um item booleano do checklist.
    Útil para acessar dinamicamente os campos do modelo no template.
    """
    try:
        return getattr(obj, field_name, False)
    except (AttributeError, TypeError):
        return False
