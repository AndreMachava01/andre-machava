"""
URLs para gerenciamento de integrações com transportadoras.
"""
from django.urls import path
from . import views_integrations

app_name = 'integrations'

urlpatterns = [
    # Dashboard
    path('dashboard/', views_integrations.integrations_dashboard, name='dashboard'),
    
    # Cotações Multi-Transportadora
    path('cotacao/', views_integrations.cotacao_multi_carrier, name='cotacao_multi_carrier'),
    
    # Solicitação de Coleta
    path('solicitar-coleta/', views_integrations.solicitar_coleta, name='solicitar_coleta'),
    
    # Sincronização
    path('sincronizar/<int:rastreamento_id>/', views_integrations.sincronizar_rastreamento, name='sincronizar_rastreamento'),
    path('sincronizar-todos/', views_integrations.sincronizar_todos_rastreamentos, name='sincronizar_todos'),
    
    # Configurações
    path('configurar/<str:carrier_code>/', views_integrations.configurar_integracao, name='configurar_integracao'),
    
    # APIs
    path('api/cotacao/', views_integrations.api_cotacao_multi_carrier, name='api_cotacao'),
    path('api/sincronizar/<int:rastreamento_id>/', views_integrations.api_sincronizar_rastreamento, name='api_sincronizar'),
    path('api/status/', views_integrations.api_status_integracao, name='api_status'),
]
