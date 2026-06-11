"""
URLs para gestão de custos e faturamento logístico.
"""
from django.urls import path
from . import views_cost_billing

app_name = 'cost_billing'

urlpatterns = [
    # Dashboard
    path('dashboard/', views_cost_billing.cost_billing_dashboard, name='dashboard'),
    
    # Custos Logísticos
    path('custos/', views_cost_billing.custos_list, name='custos_list'),
    path('custos/create/', views_cost_billing.custo_create, name='custo_create'),
    path('custos/<int:custo_id>/', views_cost_billing.custo_detail, name='custo_detail'),
    path('custos/<int:custo_id>/approve/', views_cost_billing.custo_approve, name='custo_approve'),
    path('custos/<int:custo_id>/reject/', views_cost_billing.custo_reject, name='custo_reject'),
    path('custos/<int:custo_id>/rateio/', views_cost_billing.rateio_create, name='rateio_create'),
    
    # Faturamento
    path('faturas/', views_cost_billing.faturas_list, name='faturas_list'),
    path('faturas/create/', views_cost_billing.fatura_create, name='fatura_create'),
    path('faturas/<int:fatura_id>/', views_cost_billing.fatura_detail, name='fatura_detail'),
    path('faturas/<int:fatura_id>/send/', views_cost_billing.fatura_send, name='fatura_send'),
    path('faturas/<int:fatura_id>/mark-paid/', views_cost_billing.fatura_mark_paid, name='fatura_mark_paid'),
    
    # Estatísticas
    path('stats/', views_cost_billing.cost_billing_stats, name='stats'),
]
