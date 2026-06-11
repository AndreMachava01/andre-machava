"""
URLs para roteirização e planejamento logístico.
"""
from django.urls import path
from . import views_routing

app_name = 'routing'

urlpatterns = [
    # Dashboard
    path('dashboard/', views_routing.dashboard_roteirizacao, name='dashboard'),
    
    # Zonas de Entrega
    path('zonas/', views_routing.zonas_entrega_list, name='zonas_list'),
    path('zonas/<int:zona_id>/', views_routing.zona_entrega_detail, name='zona_detail'),
    
    # Planejamento de Entregas
    path('planejamentos/', views_routing.planejamentos_list, name='planejamentos_list'),
    path('planejamentos/create/', views_routing.planejamento_create, name='planejamento_create'),
    
    # Rotas e Otimização
    path('rotas/', views_routing.rotas_list, name='rotas_list'),
    path('rotas/<int:rota_id>/', views_routing.rota_detail, name='rota_detail'),
    path('otimizar/', views_routing.otimizar_rotas, name='otimizar_rotas'),
    
    # Configurações
    path('configuracoes/', views_routing.configuracoes_roteirizacao, name='configuracoes'),
    path('configuracoes/create/', views_routing.configuracao_create, name='configuracao_create'),
]
