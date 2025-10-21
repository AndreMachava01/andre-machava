"""
URLs para observabilidade e métricas logísticas.
"""
from django.urls import path
from . import views_observability

app_name = 'observability'

urlpatterns = [
    # Dashboard
    path('dashboard/', views_observability.observability_dashboard, name='dashboard'),
    
    # Auditoria
    path('auditoria/', views_observability.auditoria_list, name='auditoria_list'),
    path('auditoria/<int:auditoria_id>/', views_observability.auditoria_detail, name='auditoria_detail'),
    
    # Métricas
    path('metricas/', views_observability.metricas_list, name='metricas_list'),
    path('metricas/<int:metrica_id>/', views_observability.metrica_detail, name='metrica_detail'),
    path('metricas/calcular/', views_observability.calcular_metricas, name='calcular_metricas'),
    
    # Relatórios
    path('relatorios/', views_observability.relatorios_list, name='relatorios_list'),
    path('relatorios/<int:relatorio_id>/', views_observability.relatorio_detail, name='relatorio_detail'),
    path('relatorios/<int:relatorio_id>/executar/', views_observability.executar_relatorio, name='executar_relatorio'),
    
    # API Logs
    path('api-logs/', views_observability.api_logs_list, name='api_logs_list'),
    path('api-logs/<int:log_id>/', views_observability.api_log_detail, name='api_log_detail'),
    
    # API Endpoints
    path('api/metricas/', views_observability.api_metricas, name='api_metricas'),
    path('api/auditoria/', views_observability.api_auditoria, name='api_auditoria'),
]
