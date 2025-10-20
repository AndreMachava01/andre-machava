from django.urls import path
from . import views_transferencias

app_name = 'transferencias'

urlpatterns = [
    # Lista de transferências
    path('', views_transferencias.transferencias_list, name='list'),
    
    # Criar transferência
    path('create/', views_transferencias.transferencia_create, name='create'),
    
    # Detalhes da transferência
    path('<int:id>/', views_transferencias.transferencia_detail, name='detail'),
    
    # Adicionar item à transferência
    path('<int:id>/add-item/', views_transferencias.transferencia_add_item, name='add_item'),
    
    # Confirmar envio
    path('<int:id>/confirmar-envio/', views_transferencias.transferencia_confirmar_envio, name='confirmar_envio'),
    
    # Receber transferência
    path('<int:id>/receber/', views_transferencias.transferencia_receber, name='receber'),
    
    # Cancelar transferência
    path('<int:id>/cancelar/', views_transferencias.transferencia_cancelar, name='cancelar'),
    
    # Apagar transferência em rascunho
    path('<int:id>/apagar/', views_transferencias.transferencia_apagar, name='apagar'),
    
    # Verificar stock por sucursais
    path('verificar-stock/', views_transferencias.verificar_stock_sucursais, name='verificar_stock'),
    
    # Documentos impressíveis
    path('<int:id>/guia-transferencia/', views_transferencias.guia_transferencia, name='guia_transferencia'),
    path('<int:id>/nota-recebimento/', views_transferencias.nota_recebimento, name='nota_recebimento'),
]
