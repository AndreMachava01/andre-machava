from django.urls import path
from . import views_requisicoes

app_name = 'requisicoes'

urlpatterns = [
    # Lista de requisições
    path('', views_requisicoes.requisicoes_list, name='list'),
    
    # Criar requisição
    path('create/', views_requisicoes.requisicao_create, name='create'),
    
    # Detalhes da requisição
    path('<int:id>/', views_requisicoes.requisicao_detail, name='detail'),
    
    # Adicionar item à requisição
    path('<int:id>/add-item/', views_requisicoes.requisicao_add_item_form, name='add_item_form'),
    path('<int:id>/edit-quantidade-atendida/<int:item_id>/', views_requisicoes.requisicao_edit_quantidade_atendida, name='edit_quantidade_atendida'),
    path('<int:id>/add-item/submit/', views_requisicoes.requisicao_add_item, name='add_item'),
    path('<int:id>/quick-add-item/', views_requisicoes.requisicao_quick_add_item, name='quick_add_item'),
    
    # Remover item da requisição
    path('<int:id>/remove-item/<int:item_id>/', views_requisicoes.requisicao_remove_item, name='remove_item'),
    
    # Ações da requisição
    path('<int:id>/submit/', views_requisicoes.requisicao_submit, name='submit'),
    path('<int:id>/approve/', views_requisicoes.requisicao_approve, name='approve'),
    path('<int:id>/reject/', views_requisicoes.requisicao_reject, name='reject'),
    path('<int:id>/cancel/', views_requisicoes.requisicao_cancel, name='cancel'),
    path('<int:id>/delete/', views_requisicoes.requisicao_delete, name='delete'),
    path('<int:id>/transfer-preview/', views_requisicoes.requisicao_transfer_preview, name='transfer_preview'),
    path('<int:id>/guia-transferencia/', views_requisicoes.requisicao_guia_transferencia, name='guia_transferencia'),
    path('<int:id>/guia-transferencia-preview/', views_requisicoes.requisicao_guia_transferencia_preview, name='guia_transferencia_preview'),
    path('<int:id>/guia-recebimento-preview/', views_requisicoes.requisicao_guia_recebimento_preview, name='guia_recebimento_preview'),
    path('<int:id>/guia-recebimento/', views_requisicoes.requisicao_guia_recebimento, name='guia_recebimento'),
    path('<int:id>/transfer-stock/', views_requisicoes.requisicao_transfer_stock, name='transfer_stock'),
    
    # API
    path('api/itens-disponiveis/', views_requisicoes.api_itens_disponiveis, name='api_itens_disponiveis'),
    path('api/stock-por-sucursal/', views_requisicoes.api_stock_por_sucursal, name='api_stock_por_sucursal'),
    path('api/stock-item-sucursal/', views_requisicoes.api_stock_item_sucursal, name='api_stock_item_sucursal'),
    path('api/sugestao-quantidade/', views_requisicoes.api_sugestao_quantidade, name='api_sugestao_quantidade'),
    
    # Verificar stock baixo
    path('verificar-stock-baixo/', views_requisicoes.verificar_stock_baixo, name='verificar_stock_baixo'),
    
    # Compra externa
    path('compra-externa/', views_requisicoes.compra_externa_list, name='compra_externa_list'),
    path('compra-externa/create/', views_requisicoes.compra_externa_create, name='compra_externa_create'),
    
    # Ordens de Compra
    path('ordens-compra/', views_requisicoes.ordens_compra_list, name='ordens_compra_list'),
    path('compra-externa/<int:id>/', views_requisicoes.compra_externa_detail, name='compra_externa_detail'),
    path('compra-externa/<int:id>/create-order/', views_requisicoes.compra_externa_create_order, name='compra_externa_create_order'),
    path('compra-externa/<int:id>/add-item/', views_requisicoes.compra_externa_add_item, name='compra_externa_add_item'),
    path('compra-externa/<int:id>/update-preco/<int:item_id>/', views_requisicoes.compra_externa_update_preco, name='compra_externa_update_preco'),
    
    # Ordem de compra
    path('ordem-compra/<int:id>/preview/', views_requisicoes.ordem_compra_preview, name='ordem_compra_preview'),
    path('ordem-compra/<int:id>/action/', views_requisicoes.ordem_compra_action, name='ordem_compra_action'),
    path('ordem-compra/<int:id>/confirm-tipo/', views_requisicoes.ordem_compra_confirm_tipo, name='ordem_compra_confirm_tipo'),
    path('ordem-compra/<int:id>/print/', views_requisicoes.ordem_compra_print, name='ordem_compra_print'),
    path('ordem-compra/<int:id>/receive/', views_requisicoes.ordem_compra_receive, name='ordem_compra_receive'),
    path('ordem-compra/<int:id>/confirm-items/', views_requisicoes.ordem_compra_confirm_items, name='ordem_compra_confirm_items'),
    path('ordem-compra/<int:id>/receipt-note/', views_requisicoes.ordem_compra_receipt_note, name='ordem_compra_receipt_note'),
    
    # URLs de envio de email
    path('ordem-compra/<int:id>/enviar-email/', views_requisicoes.ordem_compra_enviar_email, name='ordem_compra_enviar_email'),
    path('ordem-compra/<int:id>/historico-envios/', views_requisicoes.ordem_compra_historico_envios, name='ordem_compra_historico_envios'),
    path('ordem-compra/<int:id>/download-pdf/', views_requisicoes.ordem_compra_download_pdf, name='ordem_compra_download_pdf'),
    path('compra-externa/<int:id>/remove-item/<int:item_id>/', views_requisicoes.compra_externa_remove_item, name='compra_externa_remove_item'),
    path('compra-externa/<int:id>/submit/', views_requisicoes.compra_externa_submit, name='compra_externa_submit'),
    path('compra-externa/<int:id>/approve/', views_requisicoes.compra_externa_approve, name='compra_externa_approve'),
    path('compra-externa/<int:id>/reject/', views_requisicoes.compra_externa_reject, name='compra_externa_reject'),
    path('compra-externa/<int:id>/cancel/', views_requisicoes.compra_externa_cancel, name='compra_externa_cancel'),
    path('compra-externa/<int:id>/documento/', views_requisicoes.compra_externa_documento, name='compra_externa_documento'),
    path('compra-externa/<int:id>/duplicate/', views_requisicoes.compra_externa_duplicate, name='compra_externa_duplicate'),
    path('compra-externa/<int:id>/finalize/', views_requisicoes.compra_externa_finalize, name='compra_externa_finalize'),
    path('compra-externa/<int:id>/delete/', views_requisicoes.compra_externa_delete, name='compra_externa_delete'),
]
