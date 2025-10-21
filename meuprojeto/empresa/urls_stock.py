from django.urls import path, include
from . import views_stock, views_notificacoes, views_dashboard, views_alertas

app_name = 'stock'

urlpatterns = [
    # Página principal do módulo de stock
    path('', views_stock.stock_main, name='main'),
    
    # Dashboard Executivo
    path('dashboard-old/', views_stock.stock_dashboard, name='dashboard_old'),
    
    # Gestão de Inventário
    path('inventario/', include('meuprojeto.empresa.urls_inventario')),
    
    # Gestão de Categorias
    path('categorias/', views_stock.stock_categorias, name='categorias'),
    path('categorias/add/', views_stock.stock_categoria_add, name='categoria_add'),
    path('categorias/<int:id>/edit/', views_stock.stock_categoria_edit, name='categoria_edit'),
    path('categorias/<int:id>/delete/', views_stock.stock_categoria_delete, name='categoria_delete'),
    
    # Gestão de Fornecedores
    path('fornecedores/', views_stock.stock_fornecedores, name='fornecedores'),
    path('fornecedores/add/', views_stock.stock_fornecedor_add, name='fornecedor_add'),
    path('fornecedores/<int:id>/detail/', views_stock.stock_fornecedor_detail, name='fornecedor_detail'),
    path('fornecedores/<int:id>/edit/', views_stock.stock_fornecedor_edit, name='fornecedor_edit'),
    path('fornecedores/<int:id>/delete/', views_stock.stock_fornecedor_delete, name='fornecedor_delete'),
    path('fornecedores/<int:id>/produtos/', views_stock.stock_fornecedor_produtos, name='fornecedor_produtos'),
    path('fornecedores/<int:id>/associar-produto/', views_stock.stock_fornecedor_associar_produto, name='fornecedor_associar_produto'),
    path('fornecedores/<int:id>/editar-associacao/<int:associacao_id>/', views_stock.stock_fornecedor_editar_associacao, name='fornecedor_editar_associacao'),
    path('fornecedores/<int:id>/remover-associacao/<int:associacao_id>/', views_stock.stock_fornecedor_remover_associacao, name='fornecedor_remover_associacao'),
    
    # Gestão de Produtos
    path('produtos/', views_stock.stock_produtos, name='produtos'),
    path('produtos/add/', views_stock.stock_produto_add, name='produto_add'),
    path('produtos/<int:id>/edit/', views_stock.stock_produto_edit, name='produto_edit'),
    path('produtos/<int:id>/delete/', views_stock.stock_produto_delete, name='produto_delete'),
    path('produtos/<int:id>/detail/', views_stock.stock_produto_detail, name='produto_detail'),
    
    # Gestão de Materiais
    path('materiais/', views_stock.stock_materiais, name='materiais'),
    path('materiais/add/', views_stock.stock_material_add, name='material_add'),
    path('materiais/<int:id>/edit/', views_stock.stock_material_edit, name='material_edit'),
    path('materiais/<int:id>/delete/', views_stock.stock_material_delete, name='material_delete'),
    path('materiais/<int:id>/detail/', views_stock.stock_material_detail, name='material_detail'),
    
    # Gestão de Receitas
    path('receitas/', views_stock.stock_receitas, name='receitas'),
    path('receitas/add/', views_stock.stock_receita_add, name='receita_add'),
    path('receitas/<int:id>/edit/', views_stock.stock_receita_edit, name='receita_edit'),
    path('receitas/<int:id>/delete/', views_stock.stock_receita_delete, name='receita_delete'),
    path('receitas/<int:id>/detail/', views_stock.stock_receita_detail, name='receita_detail'),
    
    # Gestão de Stock por Sucursal
    path('stock/', views_stock.stock_por_sucursal, name='stock_por_sucursal'),
    path('stock/<int:sucursal_id>/', views_stock.stock_sucursal_detail, name='stock_sucursal_detail'),
    path('stock/<int:sucursal_id>/produto/<int:produto_id>/', views_stock.stock_produto_sucursal, name='stock_produto_sucursal'),
    
    # Movimentações de Stock
    path('movimentos/', views_stock.stock_movimentos, name='movimentos'),
    path('movimentos/add/', views_stock.stock_movimento_add, name='movimento_add'),
    path('movimentos/add-unified/', views_stock.stock_movimento_add_unified, name='movimento_add_unified'),
    path('movimentos/<int:id>/edit/', views_stock.stock_movimento_edit, name='movimento_edit'),
    path('movimentos/<int:id>/delete/', views_stock.stock_movimento_delete, name='movimento_delete'),
    path('movimentos/<int:id>/detail/', views_stock.stock_movimento_detail, name='movimento_detail'),
    
    # Tipos de Movimento
    path('tipos-movimento/', views_stock.stock_tipos_movimento, name='tipos_movimento'),
    path('tipos-movimento/add/', views_stock.stock_tipo_movimento_add, name='tipo_movimento_add'),
    path('tipos-movimento/<int:id>/edit/', views_stock.stock_tipo_movimento_edit, name='tipo_movimento_edit'),
    path('tipos-movimento/<int:id>/delete/', views_stock.stock_tipo_movimento_delete, name='tipo_movimento_delete'),
    
    # Dashboard Executivo
    path('dashboard/', views_dashboard.dashboard_executivo, name='dashboard_executivo'),
    path('dashboard/chart-movimentacoes/', views_dashboard.dashboard_chart_movimentacoes, name='dashboard_chart_movimentacoes'),
    path('dashboard/chart-estoque-sucursal/', views_dashboard.dashboard_chart_estoque_sucursal, name='dashboard_chart_estoque_sucursal'),
    path('dashboard/chart-categorias/', views_dashboard.dashboard_chart_categorias, name='dashboard_chart_categorias'),
    path('dashboard/chart-tendencias/', views_dashboard.dashboard_chart_tendencias, name='dashboard_chart_tendencias'),
    
    # Notificações
    path('notificacoes/', views_notificacoes.notificacoes_list, name='notificacoes_list'),
    path('notificacoes/dashboard/', views_notificacoes.notificacoes_dashboard, name='notificacoes_dashboard'),
    path('notificacoes/<int:notificacao_id>/', views_notificacoes.notificacao_detail, name='notificacao_detail'),
    path('notificacoes/<int:notificacao_id>/marcar-lida/', views_notificacoes.notificacao_marcar_lida, name='notificacao_marcar_lida'),
    path('notificacoes/marcar-todas-lidas/', views_notificacoes.notificacao_marcar_todas_lidas, name='notificacao_marcar_todas_lidas'),
    
    # Sistema de Alertas
    path('alertas/', views_alertas.alertas_gerenciar, name='alertas_gerenciar'),
    path('alertas/criar-manuais/', views_alertas.alertas_criar_manuais, name='alertas_criar_manuais'),
    path('alertas/limpar-antigas/', views_alertas.alertas_limpar_antigas, name='alertas_limpar_antigas'),
    path('alertas/marcar-todos-lidos/', views_alertas.alertas_marcar_todos_lidos, name='alertas_marcar_todos_lidos'),
    path('alertas/estatisticas/', views_alertas.alertas_estatisticas, name='alertas_estatisticas'),
    
    # Relatórios
    path('relatorios/', views_stock.stock_relatorios, name='relatorios'),
    path('relatorios/estoque-atual/', views_stock.relatorio_estoque_atual, name='relatorio_estoque_atual'),
    path('relatorios/estoque-minimo/', views_stock.relatorio_estoque_minimo, name='relatorio_estoque_minimo'),
    path('relatorios/movimentacoes/', views_stock.relatorio_movimentacoes, name='relatorio_movimentacoes'),
    path('relatorios/ordens-compra/', views_stock.relatorio_ordens_compra, name='relatorio_ordens_compra'),
    path('relatorios/devolucoes/', views_stock.relatorio_devolucoes, name='relatorio_devolucoes'),
    path('relatorios/transferencias/', views_stock.relatorio_transferencias, name='relatorio_transferencias'),
    path('relatorios/valor-estoque/', views_stock.stock_relatorio_valor_estoque, name='relatorio_valor_estoque'),
    
    # API Endpoints
    path('api/produtos/search/', views_stock.api_produtos_search, name='api_produtos_search'),
    path('api/fornecedores/search/', views_stock.api_fornecedores_search, name='api_fornecedores_search'),
    path('api/stock/atualizar/', views_stock.api_stock_atualizar, name='api_stock_atualizar'),
    
    # Transferências entre sucursais
    path('transferencias/', include('meuprojeto.empresa.urls_transferencias')),
    
    # Requisições de stock
    path('requisicoes/', include('meuprojeto.empresa.urls_requisicoes')),
    
    # Logística (integrada ao módulo de stock)
    path('logistica/', include('meuprojeto.empresa.urls_logistica', namespace='logistica')),
    
    # Roteirização e Planejamento
    # path('routing/', include('meuprojeto.empresa.urls_routing', namespace='routing')),
    
    # Exceções Logísticas
    path('exceptions/', include('meuprojeto.empresa.urls_exceptions', namespace='exceptions')),
]
