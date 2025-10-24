"""
URLs para gerenciamento de UX Mobile e painel motorista.
"""
from django.urls import path
# from . import views_mobile

app_name = 'mobile'

urlpatterns = [
    # Dashboard
    # path('dashboard/', views_mobile.mobile_dashboard, name='dashboard'),
    
    # Sessões de Motorista
    # path('sessoes/', views_mobile.sessoes_motorista_list, name='sessoes_list'),
    # path('sessoes/<int:sessao_id>/', views_mobile.sessao_motorista_detail, name='sessao_detail'),
    # path('iniciar-sessao/', views_mobile.iniciar_sessao_motorista, name='iniciar_sessao'),
    
    # Eventos de Motorista
    # path('eventos/', views_mobile.eventos_motorista_list, name='eventos_list'),
    
    # Sincronização Offline
    # path('sincronizacoes/', views_mobile.sincronizacoes_offline_list, name='sincronizacoes_list'),
    # path('sincronizacoes/<int:sincronizacao_id>/sincronizar/', views_mobile.sincronizar_offline, name='sincronizar_offline'),
    
    # Notificações Mobile
    # path('notificacoes/', views_mobile.notificacoes_mobile_list, name='notificacoes_list'),
    
    # APIs para Mobile
    # path('api/iniciar-sessao/', views_mobile.api_iniciar_sessao, name='api_iniciar_sessao'),
    # path('api/registrar-evento/', views_mobile.api_registrar_evento, name='api_registrar_evento'),
    # path('api/sincronizar-offline/', views_mobile.api_sincronizar_offline, name='api_sincronizar_offline'),
    # path('api/rastreamentos/', views_mobile.api_obter_rastreamentos, name='api_obter_rastreamentos'),
]
