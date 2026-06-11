from django import template
from django.utils.safestring import mark_safe
import json

register = template.Library()

@register.inclusion_tag('components/button_unified.html')
def button_unified(type='action', action=None, size='md', text='Botão', icon=None, url=None, onclick=None, disabled=False, loading=False, class_name=None, id=None, data=None):
    """
    Template tag para renderizar botões unificados
    
    Uso:
    {% button_unified type='module' text='RH' icon='fas fa-users' url='/rh/' %}
    {% button_unified type='action' action='edit' text='Editar' icon='fas fa-edit' %}
    {% button_unified type='confirmation' action='save' text='Guardar' icon='fas fa-save' %}
    """
    return {
        'type': type,
        'action': action,
        'size': size,
        'text': text,
        'icon': icon,
        'url': url,
        'onclick': onclick,
        'disabled': disabled,
        'loading': loading,
        'class_name': class_name,
        'id': id,
        'data': data or {}
    }

@register.inclusion_tag('components/module_buttons.html')
def module_buttons(modules=None, layout='cards', class_name=None):
    """
    Template tag para renderizar botões de módulos principais
    
    Uso:
    {% module_buttons %}
    {% module_buttons layout='grid' %}
    """
    if modules is None:
        from .buttons_config import MODULES
        modules = MODULES
    
    return {
        'modules': modules,
        'layout': layout,
        'class_name': class_name
    }

@register.inclusion_tag('components/submodule_buttons.html')
def submodule_buttons(submodules=None, layout='grid', class_name=None):
    """
    Template tag para renderizar botões de submódulos
    
    Uso:
    {% submodule_buttons %}
    {% submodule_buttons layout='sidebar' %}
    """
    if submodules is None:
        from .buttons_config import RH_SUBMODULES, STOCK_SUBMODULES, LOGISTICA_SUBMODULES
        # Determinar qual lista usar baseado no contexto
        submodules = RH_SUBMODULES  # Padrão
    
    return {
        'submodules': submodules,
        'layout': layout,
        'class_name': class_name
    }

@register.inclusion_tag('components/navigation_buttons.html')
def navigation_buttons(navigation=None, position='bottom', class_name=None):
    """
    Template tag para renderizar botões de navegação
    
    Uso:
    {% navigation_buttons %}
    {% navigation_buttons position='top' %}
    """
    if navigation is None:
        from .buttons_config import NAVIGATION_BUTTONS
        navigation = NAVIGATION_BUTTONS
    
    return {
        'navigation': navigation,
        'position': position,
        'class_name': class_name
    }

@register.inclusion_tag('components/action_buttons.html')
def action_buttons(actions=None, layout='inline', class_name=None):
    """
    Template tag para renderizar botões de ação
    
    Uso:
    {% action_buttons %}
    {% action_buttons layout='dropdown' %}
    """
    if actions is None:
        from .buttons_config import ACTION_BUTTONS
        actions = ACTION_BUTTONS
    
    return {
        'actions': actions,
        'layout': layout,
        'class_name': class_name
    }

@register.inclusion_tag('components/confirmation_buttons.html')
def confirmation_buttons(confirmations=None, layout='centered', class_name=None):
    """
    Template tag para renderizar botões de confirmação
    
    Uso:
    {% confirmation_buttons %}
    {% confirmation_buttons layout='justified' %}
    """
    if confirmations is None:
        from .buttons_config import CONFIRMATION_BUTTONS
        confirmations = CONFIRMATION_BUTTONS
    
    return {
        'confirmations': confirmations,
        'layout': layout,
        'class_name': class_name
    }

@register.simple_tag
def button_config():
    """
    Template tag para obter configuração de botões como JSON
    
    Uso:
    <script>
    const buttonConfig = {% button_config %};
    </script>
    """
    from .buttons_config import LAYOUT_CONFIG
    return mark_safe(json.dumps(LAYOUT_CONFIG))
