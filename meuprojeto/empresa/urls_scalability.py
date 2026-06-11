"""
URLs para gerenciamento de escalabilidade logística.
"""
from django.urls import path
from . import views_scalability

app_name = 'scalability'

urlpatterns = [
    # Dashboard
    path('dashboard/', views_scalability.scalability_dashboard, name='dashboard'),
    
    # Controle de Idempotência
    path('idempotencia/', views_scalability.idempotencia_list, name='idempotencia_list'),
    path('idempotencia/<int:operacao_id>/', views_scalability.idempotencia_detail, name='idempotencia_detail'),
    
    # Validações Logísticas
    path('validacoes/', views_scalability.validacoes_list, name='validacoes_list'),
    path('validacoes/<int:validacao_id>/', views_scalability.validacao_detail, name='validacao_detail'),
    
    # Resultados de Validação
    path('resultados/', views_scalability.resultados_validacao_list, name='resultados_list'),
    
    # APIs
    path('api/validar-operacao/', views_scalability.api_validar_operacao, name='api_validar_operacao'),
    path('api/executar-idempotente/', views_scalability.api_executar_operacao_idempotente, name='api_executar_idempotente'),
]
