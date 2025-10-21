"""
URLs para gerenciamento de exceções logísticas.
"""
from django.urls import path
from . import views_exceptions

app_name = 'exceptions'

urlpatterns = [
    # Dashboard
    path('dashboard/', views_exceptions.dashboard_excecoes, name='dashboard'),
    
    # Tipos de Exceção
    path('tipos/', views_exceptions.tipos_excecao_list, name='tipos_list'),
    
    # Exceções Logísticas
    path('excecoes/', views_exceptions.excecoes_list, name='excecoes_list'),
    path('excecoes/create/', views_exceptions.excecao_create, name='excecao_create'),
    path('excecoes/<int:excecao_id>/', views_exceptions.excecao_detail, name='excecao_detail'),
    path('excecoes/<int:excecao_id>/acao/', views_exceptions.adicionar_acao_excecao, name='adicionar_acao'),
    path('acoes/<int:acao_id>/concluir/', views_exceptions.concluir_acao_excecao, name='concluir_acao'),
    
    # Devoluções Logísticas
    path('devolucoes/', views_exceptions.devolucoes_list, name='devolucoes_list'),
    path('devolucoes/create/', views_exceptions.devolucao_create, name='devolucao_create'),
    path('devolucoes/<int:devolucao_id>/aprovar/', views_exceptions.aprovar_devolucao, name='aprovar_devolucao'),
    
    # Reentregas
    path('reentregas/', views_exceptions.reentregas_list, name='reentregas_list'),
    path('reentregas/create/', views_exceptions.reentrega_create, name='reentrega_create'),
]
