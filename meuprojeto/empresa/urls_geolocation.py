"""
URLs para gerenciamento de geolocalização logística.
"""
from django.urls import path
from . import views_geolocation

app_name = 'geolocation'

urlpatterns = [
    # Dashboard
    path('dashboard/', views_geolocation.geolocation_dashboard, name='dashboard'),
    
    # Endereços Normalizados
    path('enderecos/', views_geolocation.enderecos_list, name='enderecos_list'),
    path('enderecos/<int:endereco_id>/', views_geolocation.endereco_detail, name='endereco_detail'),
    path('normalizar/', views_geolocation.normalizar_endereco, name='normalizar_endereco'),
    
    # Coordenadas Históricas
    path('coordenadas/', views_geolocation.coordenadas_historicas_list, name='coordenadas_list'),
    
    # Cálculos de Distância
    path('calculos/', views_geolocation.calculos_distancia_list, name='calculos_list'),
    path('calcular-distancia/', views_geolocation.calcular_distancia, name='calcular_distancia'),
    
    # Zonas Geográficas
    path('zonas/', views_geolocation.zonas_geograficas_list, name='zonas_list'),
    path('zonas/<int:zona_id>/', views_geolocation.zona_geografica_detail, name='zona_detail'),
    
    # APIs
    path('api/normalizar-endereco/', views_geolocation.api_normalizar_endereco, name='api_normalizar_endereco'),
    path('api/calcular-distancia/', views_geolocation.api_calcular_distancia, name='api_calcular_distancia'),
    path('api/obter-eta/', views_geolocation.api_obter_eta, name='api_obter_eta'),
]
