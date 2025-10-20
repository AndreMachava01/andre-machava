from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from .models_rh import PerfilUsuario


def require_sucursal_access(view_func):
    """
    Decorator que verifica se o usuário tem acesso à sucursal especificada
    Para visualização: todos podem ver todas as sucursais
    Para modificação: apenas sua própria sucursal
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Verificar se o usuário está autenticado
        if not request.user.is_authenticated:
            return redirect('admin:login')
        
        # Obter perfil do usuário
        try:
            perfil = request.user.perfil
        except PerfilUsuario.DoesNotExist:
            messages.error(request, 'Perfil de usuário não encontrado. Contacte o administrador.')
            return redirect('dashboard')
        
        # Administradores gerais têm acesso total
        if perfil.pode_acessar_todas_sucursais:
            return view_func(request, *args, **kwargs)
        
        # Para visualização, todos podem ver todas as sucursais
        # Para modificação, verificar se é sua própria sucursal
        if request.method == 'POST':
            # Verificar se o usuário tem sucursal definida para modificações
            if not perfil.sucursal:
                messages.error(request, 'Usuário não está vinculado a nenhuma sucursal.')
                return redirect('dashboard')
            
            # Verificar se a modificação é na sua própria sucursal
            sucursal_id = kwargs.get('sucursal_id') or request.POST.get('sucursal')
            if sucursal_id:
                try:
                    sucursal_id = int(sucursal_id)
                    if sucursal_id != perfil.sucursal.id:
                        messages.error(request, 'Você só pode modificar o stock da sua própria sucursal.')
                        return redirect('stock:main')
                except (ValueError, TypeError):
                    pass
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def require_stock_access(view_func):
    """
    Decorator que verifica se o usuário tem acesso ao módulo de stock
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('admin:login')
        
        try:
            perfil = request.user.perfil
        except PerfilUsuario.DoesNotExist:
            messages.error(request, 'Perfil de usuário não encontrado. Contacte o administrador.')
            return redirect('dashboard')
        
        if not perfil.permissoes_stock:
            messages.error(request, 'Você não tem permissão para acessar o módulo de Stock.')
            return redirect('dashboard')
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def require_rh_access(view_func):
    """
    Decorator que verifica se o usuário tem acesso ao módulo de RH
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('admin:login')
        
        try:
            perfil = request.user.perfil
        except PerfilUsuario.DoesNotExist:
            messages.error(request, 'Perfil de usuário não encontrado. Contacte o administrador.')
            return redirect('dashboard')
        
        if not perfil.permissoes_rh:
            messages.error(request, 'Você não tem permissão para acessar o módulo de RH.')
            return redirect('dashboard')
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def get_user_sucursais(request, for_modification=False):
    """
    Função auxiliar para obter as sucursais que o usuário pode acessar
    for_modification: True se for para modificação, False para visualização
    """
    if not request.user.is_authenticated:
        return []
    
    try:
        perfil = request.user.perfil
        
        # Administradores gerais têm acesso total
        if perfil.pode_acessar_todas_sucursais:
            from .models_base import Sucursal
            return Sucursal.objects.filter(ativa=True)
        
        # Para modificação: apenas sua própria sucursal
        if for_modification:
            if perfil.sucursal:
                return [perfil.sucursal]
            else:
                return []
        
        # Para visualização: todas as sucursais
        from .models_base import Sucursal
        return Sucursal.objects.filter(ativa=True)
        
    except PerfilUsuario.DoesNotExist:
        return []