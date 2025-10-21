"""
URLs para sistema de notificações push logísticas.
"""
from django.urls import path
from . import views_notifications

app_name = 'notifications'

urlpatterns = [
    # Dashboard
    path('dashboard/', views_notifications.notifications_dashboard, name='dashboard'),
    
    # Gestão de Notificações
    path('notificacoes/', views_notifications.notificacoes_list, name='notificacoes_list'),
    path('notificacoes/<int:notificacao_id>/', views_notifications.notificacao_detail, name='notificacao_detail'),
    path('enviar/', views_notifications.enviar_notificacao, name='enviar_notificacao'),
    
    # Notificações Automáticas
    path('configurar-automaticas/', views_notifications.configurar_notificacoes_automaticas, name='configurar_automaticas'),
    
    # Teste
    path('testar/', views_notifications.testar_notificacao, name='testar_notificacao'),
    
    # APIs
    path('api/enviar-push/', views_notifications.api_enviar_notificacao_push, name='api_enviar_push'),
    path('api/marcar-lida/<int:notificacao_id>/', views_notifications.api_marcar_como_lida, name='api_marcar_lida'),
    path('api/usuario/', views_notifications.api_obter_notificacoes_usuario, name='api_obter_usuario'),
    
    # Webhooks
    path('webhook/status/', views_notifications.webhook_notificacao_status, name='webhook_status'),
    path('webhook/atraso/', views_notifications.webhook_notificacao_atraso, name='webhook_atraso'),
]
