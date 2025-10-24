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
    path('regioes/<int:regiao_id>/', views_masterdata.regiao_detail, name='regiao_detail'),
    
    # Zonas de Entrega
    path('zonas/', views_masterdata.zonas_list, name='zonas_list'),
    path('zonas/create/', views_masterdata.zona_create, name='zona_create'),
    path('zonas/<int:zona_id>/', views_masterdata.zona_detail, name='zona_detail'),
    
    # Hubs Logísticos
    path('hubs/', views_masterdata.hubs_list, name='hubs_list'),
    path('hubs/create/', views_masterdata.hub_create, name='hub_create'),
    path('hubs/<int:hub_id>/', views_masterdata.hub_detail, name='hub_detail'),
    
    # Catálogo de Dimensões
    path('catalogo-dimensoes/', views_masterdata.catalogo_dimensoes_list, name='catalogo_dimensoes_list'),
    path('catalogo-dimensoes/create/', views_masterdata.catalogo_dimensoes_create, name='catalogo_dimensoes_create'),
    path('catalogo-dimensoes/<int:dimensao_id>/', views_masterdata.catalogo_dimensoes_detail, name='catalogo_dimensoes_detail'),
    
    # Restrições Logísticas
    path('restricoes/', views_masterdata.restricoes_list, name='restricoes_list'),
    path('restricoes/create/', views_masterdata.restricao_create, name='restricao_create'),
    path('restricoes/<int:restricao_id>/', views_masterdata.restricao_detail, name='restricao_detail'),
    
    # Validação de Restrições
    path('validar-restricoes/', views_masterdata.validar_restricoes, name='validar_restricoes'),
    
    # Logs e Auditoria
    path('logs/', views_masterdata.logs_masterdata, name='logs'),
]
