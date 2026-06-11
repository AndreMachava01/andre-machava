"""
URLs do módulo de Finanças.
"""
from django.urls import path
from . import views_financas

app_name = 'financas'

urlpatterns = [
    path('', views_financas.financas_main, name='main'),
    path('contas-pagar/', views_financas.financas_contas_pagar, name='contas_pagar'),
    path('contas-receber/', views_financas.financas_contas_receber, name='contas_receber'),
    path('cronograma/', views_financas.financas_cronograma, name='cronograma'),
    path('contas-pagar/<int:pendente_id>/confirmar/', views_financas.financas_confirmar_conta_pagar, name='confirmar_conta_pagar'),
    path('contas-pagar/<int:pendente_id>/rejeitar/', views_financas.financas_rejeitar_conta_pagar, name='rejeitar_conta_pagar'),
    path('contas-pagar/<int:pendente_id>/recibo-adiantamento/', views_financas.financas_gerar_recibo_adiantamento_pagar, name='recibo_adiantamento_pagar'),
    path('contas-receber/<int:pendente_id>/confirmar/', views_financas.financas_confirmar_conta_receber, name='confirmar_conta_receber'),
    path('contas-receber/<int:pendente_id>/rejeitar/', views_financas.financas_rejeitar_conta_receber, name='rejeitar_conta_receber'),
    path('contas-receber/<int:pendente_id>/recibo-adiantamento/', views_financas.financas_gerar_recibo_adiantamento_receber, name='recibo_adiantamento_receber'),
    path('receitas/', views_financas.financas_receitas, name='receitas'),
    path('despesas/', views_financas.financas_despesas, name='despesas'),
    path('relatorio/', views_financas.financas_relatorio, name='relatorio'),
    path('plano-contas/', views_financas.financas_plano_contas, name='plano_contas'),
    path('movimentos/', views_financas.financas_movimentos, name='movimentos'),
    path('balanco-dre/', views_financas.financas_balanco_dre, name='balanco_dre'),
    path('razao/', views_financas.financas_razao, name='razao'),
    path('importar-totais/', views_financas.financas_importar_totais, name='importar_totais'),
    path('iva/', views_financas.financas_iva, name='iva'),
    path('numeracao/', views_financas.financas_numeracao, name='numeracao'),
    path('irpc/', views_financas.financas_irpc, name='irpc'),
    path('retencao/', views_financas.financas_retencao, name='retencao'),
    path('tesouraria/', views_financas.financas_tesouraria, name='tesouraria'),
]
