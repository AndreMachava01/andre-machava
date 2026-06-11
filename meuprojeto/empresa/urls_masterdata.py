"""
URLs para gestão de dados mestres (masterdata) logísticos.
"""
from django.urls import path
from . import views_masterdata

app_name = 'masterdata'

urlpatterns = [
    # Dashboard
    path('dashboard/', views_masterdata.masterdata_dashboard, name='dashboard'),
    
    # Regiões
    path('regioes/', views_masterdata.regioes_list, name='regioes_list'),
    path('regioes/create/', views_masterdata.regiao_create, name='regiao_create'),
    path('regioes/<int:regiao_id>/edit/', views_masterdata.regiao_edit, name='regiao_edit'),
    path('regioes/<int:regiao_id>/delete/', views_masterdata.regiao_delete, name='regiao_delete'),
    path('regioes/<int:regiao_id>/', views_masterdata.regiao_detail, name='regiao_detail'),
    
    # Zonas de Entrega
    path('zonas/', views_masterdata.zonas_list, name='zonas_list'),
    path('zonas/create/', views_masterdata.zona_create, name='zona_create'),
    path('zonas/<int:zona_id>/edit/', views_masterdata.zona_edit, name='zona_edit'),
    path('zonas/<int:zona_id>/delete/', views_masterdata.zona_delete, name='zona_delete'),
    path('zonas/<int:zona_id>/', views_masterdata.zona_detail, name='zona_detail'),
    
    # Hubs Logísticos
    path('hubs/', views_masterdata.hubs_list, name='hubs_list'),
    path('hubs/create/', views_masterdata.hub_create, name='hub_create'),
    path('hubs/<int:hub_id>/edit/', views_masterdata.hub_edit, name='hub_edit'),
    path('hubs/<int:hub_id>/delete/', views_masterdata.hub_delete, name='hub_delete'),
    path('hubs/<int:hub_id>/', views_masterdata.hub_detail, name='hub_detail'),
    
    # Catálogo de Dimensões
    path('catalogo-dimensoes/', views_masterdata.catalogo_dimensoes_list, name='catalogo_dimensoes_list'),
    path('catalogo-dimensoes/create/', views_masterdata.catalogo_dimensoes_create, name='catalogo_dimensoes_create'),
    path('catalogo-dimensoes/<int:dimensao_id>/edit/', views_masterdata.catalogo_dimensoes_edit, name='catalogo_dimensoes_edit'),
    path('catalogo-dimensoes/<int:dimensao_id>/delete/', views_masterdata.catalogo_dimensoes_delete, name='catalogo_dimensoes_delete'),
    path('catalogo-dimensoes/<int:dimensao_id>/', views_masterdata.catalogo_dimensoes_detail, name='catalogo_dimensoes_detail'),
    
    # Restrições Logísticas
    path('restricoes/', views_masterdata.restricoes_list, name='restricoes_list'),
    path('restricoes/create/', views_masterdata.restricao_create, name='restricao_create'),
    path('restricoes/<int:restricao_id>/edit/', views_masterdata.restricao_edit, name='restricao_edit'),
    path('restricoes/<int:restricao_id>/delete/', views_masterdata.restricao_delete, name='restricao_delete'),
    path('restricoes/<int:restricao_id>/', views_masterdata.restricao_detail, name='restricao_detail'),
    
    # Validação de Restrições
    path('validar-restricoes/', views_masterdata.validar_restricoes, name='validar_restricoes'),
    
    # Logs e Auditoria
    path('logs/', views_masterdata.logs_masterdata, name='logs'),
]
