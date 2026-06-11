"""
URLs para relatórios logísticos avançados e dashboard executivo.
"""
from django.urls import path
from . import views_reports, views_logistica_reports

app_name = 'reports'

urlpatterns = [
    path('dashboard-executivo/', views_reports.dashboard_executivo, name='dashboard_executivo'),
    path('performance/', views_reports.relatorio_performance, name='relatorio_performance'),
    path('custos/', views_reports.relatorio_custos, name='relatorio_custos'),
    path('sla/', views_reports.relatorio_sla, name='relatorio_sla'),
    path('rastreamentos/', views_reports.relatorio_rastreamentos, name='relatorio_rastreamentos'),
    path('transportadoras/', views_logistica_reports.relatorio_transportadoras, name='relatorio_transportadoras'),
    path('excecoes/', views_logistica_reports.relatorio_excecoes, name='relatorio_excecoes'),
    path(
        'geral-stock-logistica/',
        views_logistica_reports.relatorio_geral_stock_logistica,
        name='relatorio_geral_stock_logistica',
    ),
]
