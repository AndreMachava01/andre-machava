from django.urls import path

from . import views_rh_relatorios as views

urlpatterns = [
    path('relatorios/', views.rh_relatorios, name='relatorios'),
    path('relatorios/funcionarios/', views.relatorio_funcionarios_documento, name='relatorio_funcionarios_documento'),
    path('relatorios/presencas/', views.relatorio_presencas_documento, name='relatorio_presencas_documento'),
    path('relatorios/salarios/', views.relatorio_salarios_documento, name='relatorio_salarios_documento'),
    path('relatorios/treinamentos/', views.relatorio_treinamentos_documento, name='relatorio_treinamentos_documento'),
    path('relatorios/avaliacoes/', views.relatorio_avaliacoes_documento, name='relatorio_avaliacoes_documento'),
    path('relatorios/horas-extras/', views.relatorio_horas_extras_documento, name='relatorio_horas_extras_documento'),
    path('relatorios/feriados/', views.relatorio_feriados_documento, name='relatorio_feriados_documento'),
    path('relatorios/geral/', views.relatorio_geral_rh_documento, name='relatorio_geral_rh_documento'),
    path('relatorios/custos/', views.relatorio_custos_rh_documento, name='relatorio_custos_rh_documento'),
    path('relatorios/pdf/', views.relatorio_pdf, name='relatorio_pdf'),
    path('relatorios/funcionarios/pdf/', views.relatorio_funcionarios_pdf, name='relatorio_funcionarios_pdf'),
    path('relatorios/presencas/pdf/', views.relatorio_presencas_pdf, name='relatorio_presencas_pdf'),
    path('relatorios/salarios/pdf/', views.relatorio_salarios_pdf, name='relatorio_salarios_pdf'),
    path('relatorios/treinamentos/pdf/', views.relatorio_treinamentos_pdf, name='relatorio_treinamentos_pdf'),
    path('relatorios/avaliacoes/pdf/', views.relatorio_avaliacoes_pdf, name='relatorio_avaliacoes_pdf'),
    path('relatorios/horas-extras/pdf/', views.relatorio_horas_extras_pdf, name='relatorio_horas_extras_pdf'),
    path('relatorios/feriados/pdf/', views.relatorio_feriados_pdf, name='relatorio_feriados_pdf'),
    path('relatorios/geral/pdf/', views.relatorio_geral_rh_pdf, name='relatorio_geral_rh_pdf'),
    path('relatorios/custos/pdf/', views.relatorio_custos_rh_pdf, name='relatorio_custos_rh_pdf'),
]
