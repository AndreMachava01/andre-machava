from django.http import HttpResponse
from django.shortcuts import redirect
from django.contrib.auth import authenticate, login
from django.conf import settings
from django.contrib.auth.models import User

def demo_view(request):
    # Apenas funciona se DEBUG=True (ambiente de desenvolvimento)
    if not settings.DEBUG:
        return redirect('login')
    
    # Tenta encontrar o usuário admin ou cria um novo se não existir
    admin_user = User.objects.filter(username='admin').first()
    if not admin_user:
        admin_user = User.objects.create_superuser('admin', 'admin@example.com', 'admin')
    
    # Faz login automático com o usuário admin
    login(request, admin_user)
    
    # Redireciona para o dashboard
    return redirect('dashboard')
