from django.urls import path
from . import views_inventario

app_name = 'inventario'

urlpatterns = [
    # Inventários Físicos
    path('', views_inventario.inventario_list, name='list'),
    path('create/', views_inventario.inventario_create, name='create'),
    path('<int:id>/', views_inventario.inventario_detail, name='detail'),
    path('<int:id>/update-item/<int:item_id>/', views_inventario.inventario_update_item, name='update_item'),
    path('<int:id>/submeter-contagem/', views_inventario.inventario_submeter_contagem, name='submeter_contagem'),
    path('<int:id>/imprimir-contagem/<int:numero_contagem>/', views_inventario.inventario_imprimir_contagem, name='imprimir_contagem'),
    path('<int:id>/finalizar/', views_inventario.inventario_finalizar, name='finalizar'),
    path('<int:id>/finalizar-com-ajuste/', views_inventario.inventario_finalizar_com_ajuste, name='finalizar_com_ajuste'),
    path('<int:id>/relatorio/', views_inventario.inventario_relatorio, name='relatorio'),
    
    # Ajustes de Inventário
    path('ajustes/', views_inventario.ajustes_list, name='ajustes_list'),
    path('ajustes/<int:id>/aprovar/', views_inventario.ajuste_aprovar, name='ajuste_aprovar'),
]
