from django.urls import path
from . import views_logistica

app_name = 'logistica'

urlpatterns = [
    # Página principal do módulo de logística
    path('', views_logistica.logistica_main, name='main'),
    
    # Dashboard executivo de logística
    path('dashboard/', views_logistica.logistica_dashboard, name='dashboard'),
    
    # API endpoints
    path('dashboard-data/', views_logistica.logistica_dashboard_data, name='dashboard_data'),
    
    # Rastreamento de entregas
    path('rastreamento/', views_logistica.rastreamento_list, name='rastreamento_list'),
    path('rastreamento/<int:id>/', views_logistica.rastreamento_detail, name='rastreamento_detail'),
    # criação e adição de eventos desativadas (rastreamento vem das operações)
    
    # Transportadoras Externas
    path('transportadoras/', views_logistica.transportadoras_list, name='transportadoras_list'),
    path('transportadoras/create/', views_logistica.transportadora_create, name='transportadora_create'),
    path('transportadoras/<int:id>/', views_logistica.transportadora_detail, name='transportadora_detail'),
    path('transportadoras/<int:id>/edit/', views_logistica.transportadora_edit, name='transportadora_edit'),
    path('transportadoras/<int:id>/delete/', views_logistica.transportadora_delete, name='transportadora_delete'),
    
    # Viaturas Internas (Meios Circulantes da Empresa)
    path('viaturas/', views_logistica.viaturas_list, name='viaturas_list'),
    path('viaturas/create/', views_logistica.viatura_create, name='viatura_create'),
    path('viaturas/<int:id>/', views_logistica.viatura_detail, name='viatura_detail'),
    path('viaturas/<int:id>/edit/', views_logistica.viatura_edit, name='viatura_edit'),
    path('viaturas/<int:id>/delete/', views_logistica.viatura_delete, name='viatura_delete'),
    
    # Veículos Internos (URL alternativa para compatibilidade)
    path('veiculos/', views_logistica.viaturas_list, name='veiculos_list'),
    path('veiculos/create/', views_logistica.viatura_create, name='veiculo_create'),
    path('veiculos/<int:id>/', views_logistica.viatura_detail, name='veiculo_detail'),
    path('veiculos/<int:id>/edit/', views_logistica.viatura_edit, name='veiculo_edit'),
    path('veiculos/<int:id>/delete/', views_logistica.viatura_delete, name='veiculo_delete'),
    
    # Notificações Logísticas Unificadas
    path('operacoes/', views_logistica.operacoes_logistica_list, name='operacoes_list'),
    path('operacoes/<int:id>/', views_logistica.operacao_logistica_detail, name='operacao_detail'),
    path('operacoes/<int:id>/atribuir/', views_logistica.operacao_atribuir_transporte, name='operacao_atribuir'),
    path('operacoes/<int:id>/confirmar-coleta/', views_logistica.operacao_confirmar_coleta, name='operacao_confirmar_coleta'),
    path('operacoes/<int:id>/iniciar-transporte/', views_logistica.operacao_iniciar_transporte, name='operacao_iniciar_transporte'),
    path('operacoes/<int:id>/confirmar-entrega/', views_logistica.operacao_confirmar_entrega, name='operacao_confirmar_entrega'),
    path('operacoes/<int:id>/concluir/', views_logistica.operacao_concluir, name='operacao_concluir'),
    path('operacoes/<int:id>/editar-prioridade/', views_logistica.operacao_editar_prioridade, name='operacao_editar_prioridade'),
    
    # Checklist de Viaturas
    path('checklist/', views_logistica.checklist_viaturas_list, name='checklist_list'),
    path('checklist/create/', views_logistica.checklist_viaturas_create, name='checklist_create'),
    path('checklist/<int:id>/', views_logistica.checklist_viaturas_detail, name='checklist_detail'),
    path('checklist/<int:id>/print/', views_logistica.checklist_viaturas_print, name='checklist_print'),
    path('checklist/print/blank/', views_logistica.checklist_viaturas_print_blank, name='checklist_print_blank'),
    
    # AJAX endpoints
    path('get-funcionario-telefone/', views_logistica.get_funcionario_telefone, name='get_funcionario_telefone'),
]
