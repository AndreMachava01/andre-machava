from django.urls import path
from . import views_vendas

app_name = 'vendas'

urlpatterns = [
    # Página principal do módulo de vendas
    path('', views_vendas.vendas_main, name='main'),
    
    # Pedidos
    path('pedidos/', views_vendas.vendas_pedidos, name='pedidos'),
    path('pedidos/<int:id>/', views_vendas.vendas_pedido_detail, name='pedido_detail'),
    path('pedidos/<int:id>/emitir-fatura/', views_vendas.vendas_pedido_emitir_fatura, name='pedido_emitir_fatura'),
    path('pedidos/<int:id>/emitir-garantia/', views_vendas.vendas_pedido_emitir_garantia, name='pedido_emitir_garantia'),
    path('pedidos/<int:id>/editar/', views_vendas.vendas_pedido_edit, name='pedido_edit'),
    path('pedidos/<int:id>/alterar-status/', views_vendas.vendas_pedido_alterar_status, name='pedido_alterar_status'),
    
    # Faturamento
    path('faturamento/', views_vendas.vendas_faturamento, name='faturamento'),
    
    # Dashboard
    path('dashboard/', views_vendas.vendas_dashboard, name='dashboard'),
    
    # Orçamentos
    path('orcamento/add/', views_vendas.vendas_orcamento_add, name='orcamento_add'),
    path('orcamentos/', views_vendas.vendas_orcamentos_list, name='orcamentos_list'),
    path('orcamentos/<int:id>/', views_vendas.vendas_orcamento_detail, name='orcamento_detail'),
    path('orcamentos/<int:id>/editar/', views_vendas.vendas_orcamento_edit, name='orcamento_edit'),
    path('orcamentos/<int:id>/confirmar/', views_vendas.vendas_cotacao_confirmar, name='cotacao_confirmar'),
    path('orcamentos/<int:id>/confirmar-acao/', views_vendas.vendas_confirmar_cotacao_acao, name='confirmar_cotacao_acao'),
    path('orcamentos/<int:id>/delete/', views_vendas.vendas_orcamento_delete, name='orcamento_delete'),
    path('orcamentos/pendentes/', views_vendas.vendas_orcamentos_pendentes, name='orcamentos_pendentes'),
    path('contratos/', views_vendas.vendas_contratos, name='contratos'),
    path('contratos/<int:orcamento_id>/preview/', views_vendas.vendas_preview_contrato, name='preview_contrato'),
    path('contratos/<int:orcamento_id>/gerar/', views_vendas.vendas_gerar_contrato, name='gerar_contrato'),
    path('contratos/<int:orcamento_id>/editar/', views_vendas.vendas_editar_contrato, name='editar_contrato'),
    
    # Clientes
    path('clientes/add/', views_vendas.vendas_clientes_add, name='clientes_add'),
    path('clientes/', views_vendas.vendas_clientes_list, name='clientes_list'),
    path('historico/', views_vendas.vendas_historico, name='historico'),
    
    # Relatórios
    path('relatorios/', views_vendas.vendas_relatorios, name='relatorios'),
    path('performance/', views_vendas.vendas_performance, name='performance'),
    path('periodo/', views_vendas.vendas_periodo, name='periodo'),
]

