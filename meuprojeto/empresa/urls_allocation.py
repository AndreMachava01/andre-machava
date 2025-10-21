"""
URLs para gerenciamento de alocação automática de recursos logísticos.
"""
from django.urls import path
from . import views_allocation

app_name = 'allocation'

urlpatterns = [
    # Dashboard
    path('dashboard/', views_allocation.allocation_dashboard, name='dashboard'),
    
    # Configuração
    path('criteria/', views_allocation.allocation_criteria_config, name='criteria_config'),
    
    # Alocação
    path('single/<int:rastreamento_id>/', views_allocation.allocation_single, name='single'),
    path('batch/', views_allocation.allocation_batch, name='batch'),
    
    # Histórico e Estatísticas
    path('history/', views_allocation.allocation_history, name='history'),
    path('stats/', views_allocation.allocation_stats, name='stats'),
    
    # APIs
    path('api/preview/<int:rastreamento_id>/', views_allocation.api_allocation_preview, name='api_preview'),
    path('api/apply/<int:rastreamento_id>/', views_allocation.api_apply_allocation, name='api_apply'),
]
