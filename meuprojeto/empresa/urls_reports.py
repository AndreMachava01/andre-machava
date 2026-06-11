"""
URLs para relatórios logísticos avançados e dashboard executivo.
"""
from django.urls import path
from . import views_reports

app_name = 'reports'

urlpatterns = [
    # Dashboard Executivo
    path('dashboard-executivo/', views_reports.dashboard_executivo, name='dashboard_executivo'),
    
    # Relatórios Específicos
    path('performance/', views_reports.relatorio_performance, name='relatorio_performance'),
    path('custos/', views_reports.relatorio_custos, name='relatorio_custos'),
    path('sla/', views_reports.relatorio_sla, name='relatorio_sla'),
]
