from django.urls import path

from . import views_rh_folha as views

urlpatterns = [
    path('folha-salarial/', views.rh_folha_salarial, name='folha_salarial'),
    path('folha-salarial/adicionar/', views.rh_folha_add, name='folha_add'),
    path('folha-salarial/detalhes/<int:folha_id>/', views.rh_folha_detail, name='folha_detail'),
    path(
        'folha-salarial/detalhes/<int:folha_id>/funcionario/<int:funcionario_id>/',
        views.rh_folha_funcionario_detail,
        name='folha_funcionario_detail',
    ),
    path('folha-salarial/editar/<int:folha_id>/', views.rh_folha_edit, name='folha_edit'),
    path('folha-salarial/deletar/<int:folha_id>/', views.rh_folha_delete, name='folha_delete'),
    path('folha-salarial/calcular/<int:folha_id>/', views.rh_folha_calcular, name='folha_calcular'),
    path('folha-salarial/pdf/<int:folha_id>/', views.rh_folha_pdf, name='folha_pdf'),
    path('folha-salarial/preview/<int:folha_id>/', views.rh_folha_preview, name='folha_preview'),
    path('folha-salarial/validar-fechamento/<int:folha_id>/', views.rh_folha_validar_fechamento, name='folha_validar_fechamento'),
    path('folha-salarial/fechar/<int:folha_id>/', views.rh_folha_fechar, name='folha_fechar'),
    path('folha-salarial/reabrir/<int:folha_id>/', views.rh_folha_reabrir, name='folha_reabrir'),
    path('folha-salarial/marcar-paga/<int:folha_id>/', views.rh_folha_marcar_paga, name='folha_marcar_paga'),
    path('folha-salarial/canhoto/<int:folha_id>/<int:funcionario_id>/', views.rh_canhoto_salario, name='canhoto_salario'),
    path('folha-salarial/canhoto-visualizar/<int:folha_id>/<int:funcionario_id>/', views.rh_canhoto_visualizar, name='canhoto_visualizar'),
    path('folha-salarial/beneficios/<int:folha_id>/', views.rh_folha_beneficios, name='folha_beneficios'),
    path('folha-salarial/beneficios/<int:folha_id>/adicionar/', views.rh_folha_beneficio_add, name='folha_beneficio_add'),
    path('folha-salarial/beneficios/<int:folha_id>/adicionar-auto/', views.rh_folha_beneficio_auto_add, name='folha_beneficio_auto_add'),
    path('folha-salarial/beneficios/<int:folha_id>/editar/<int:beneficio_folha_id>/', views.rh_folha_beneficio_edit, name='folha_beneficio_edit'),
    path('folha-salarial/beneficios/<int:folha_id>/deletar/<int:beneficio_folha_id>/', views.rh_folha_beneficio_delete, name='folha_beneficio_delete'),
    path('folha-salarial/descontos/<int:folha_id>/', views.rh_folha_descontos, name='folha_descontos'),
    path('folha-salarial/descontos/<int:folha_id>/adicionar/', views.rh_folha_desconto_add, name='folha_desconto_add'),
    path('folha-salarial/descontos/<int:folha_id>/adicionar-auto/', views.rh_folha_desconto_auto_add, name='folha_desconto_auto_add'),
    path('folha-salarial/descontos/<int:folha_id>/editar/<int:desconto_folha_id>/', views.rh_folha_desconto_edit, name='folha_desconto_edit'),
    path('folha-salarial/descontos/<int:folha_id>/deletar/<int:desconto_folha_id>/', views.rh_folha_desconto_delete, name='folha_desconto_delete'),
]
