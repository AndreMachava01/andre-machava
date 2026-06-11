"""
Custom middleware for the Conception system
"""
from django.conf import settings
from django.shortcuts import redirect
from django.contrib import messages
from django.middleware.csrf import CsrfViewMiddleware, get_token
from django.utils.deprecation import MiddlewareMixin


class DisableCSRFOriginCheckMiddleware(MiddlewareMixin):
    """
    Middleware que modifica o request antes do CSRF para permitir
    requisições sem origem em desenvolvimento.
    """
    def process_request(self, request):
        """
        Adiciona header Origin baseado no Referer se não existir.
        """
        if settings.DEBUG and request.method == 'POST':
            # Se não houver Origin header, tentar obter do Referer
            if 'HTTP_ORIGIN' not in request.META:
                referer = request.META.get('HTTP_REFERER', '')
                if referer:
                    from urllib.parse import urlparse
                    try:
                        parsed = urlparse(referer)
                        origin = f"{parsed.scheme}://{parsed.netloc}"
                        # Apenas definir se for localhost ou porta 54052
                        if 'localhost' in origin or '127.0.0.1' in origin or '54052' in origin:
                            request.META['HTTP_ORIGIN'] = origin
                        else:
                            # Mesmo assim, definir como localhost em desenvolvimento
                            request.META['HTTP_ORIGIN'] = 'http://localhost:8000'
                    except:
                        request.META['HTTP_ORIGIN'] = 'http://localhost:8000'
                else:
                    # Sem referer, definir como localhost
                    request.META['HTTP_ORIGIN'] = 'http://localhost:8000'
            # Se origem for 'null', substituir por localhost
            elif request.META.get('HTTP_ORIGIN') == 'null':
                request.META['HTTP_ORIGIN'] = 'http://localhost:8000'
        
        return None


class VendasProducaoAccessMiddleware(MiddlewareMixin):
    """
    Restringe acesso a /vendas/ ao grupo "Vendas" e a /producao/ ao grupo "Produção".
    Só actua se settings.RESTRICT_VENDAS_PRODUCAO_BY_GROUP for True.
    Superuser pode aceder a ambos. Utilizadores não autenticados não são bloqueados aqui (login_required nas views).
    """
    def process_request(self, request):
        if not getattr(settings, 'RESTRICT_VENDAS_PRODUCAO_BY_GROUP', False):
            return None
        path = request.path
        if not path.startswith(('/vendas/', '/producao/')):
            return None
        if not request.user.is_authenticated:
            return None
        if request.user.is_superuser:
            return None
        if path.startswith('/vendas/'):
            if not request.user.groups.filter(name='Vendas').exists():
                messages.error(request, 'Não tem permissão para aceder ao módulo Vendas.')
                return redirect('dashboard')
        elif path.startswith('/producao/'):
            if not request.user.groups.filter(name='Produção').exists():
                messages.error(request, 'Não tem permissão para aceder ao módulo Produção.')
                return redirect('dashboard')
        return None


# Patch do CsrfViewMiddleware para desabilitar verificação de origem em DEBUG
# Este patch será aplicado quando o Django estiver configurado
_patch_applied = False

def apply_csrf_patch():
    """Aplica o patch no CsrfViewMiddleware apenas quando DEBUG=True"""
    global _patch_applied
    if _patch_applied:
        return
    
    try:
        from django.conf import settings as django_settings
        if django_settings.DEBUG:
            # Salvar o método original
            if not hasattr(CsrfViewMiddleware, '_original_check_origin'):
                CsrfViewMiddleware._original_check_origin = CsrfViewMiddleware._check_origin
            
            def patched_check_origin(self, request):
                """Patch que permite null em desenvolvimento"""
                origin = request.META.get('HTTP_ORIGIN')
                # Se origem for None ou null, permitir em desenvolvimento
                if not origin or origin == 'null':
                    return True
                # Se for localhost, sempre permitir
                if 'localhost' in origin or '127.0.0.1' in origin:
                    return True
                # Tentar verificação padrão
                try:
                    return CsrfViewMiddleware._original_check_origin(self, request)
                except:
                    # Em desenvolvimento, ser permissivo
                    return True
            
            # Aplicar o patch
            CsrfViewMiddleware._check_origin = patched_check_origin
            _patch_applied = True
    except:
        # Se Django não estiver configurado ainda, não fazer nada
        pass

# Tentar aplicar o patch quando o módulo for importado (se Django já estiver configurado)
try:
    from django.conf import settings as django_settings
    if django_settings.configured:
        apply_csrf_patch()
except:
    pass

