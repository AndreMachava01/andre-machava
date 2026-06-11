from django.urls import path

from . import views_rh_salarios as views

urlpatterns = [
    path('salarios/', views.rh_salarios, name='salarios'),
    path('salarios/adicionar/', views.rh_salario_add, name='salario_add'),
    path('salarios/editar/<int:salario_id>/', views.rh_salario_edit, name='salario_edit'),
    path('salarios/excluir/<int:salario_id>/', views.rh_salario_delete, name='salario_delete'),
    path('salarios/beneficios/', views.rh_beneficios_salariais, name='beneficios_salariais'),
    path('salarios/beneficios/adicionar/', views.rh_beneficio_salarial_add, name='beneficio_salarial_add'),
    path('salarios/beneficios/editar/<int:beneficio_id>/', views.rh_beneficio_salarial_edit, name='beneficio_salarial_edit'),
    path('salarios/beneficios/excluir/<int:beneficio_id>/', views.rh_beneficio_salarial_delete, name='beneficio_salarial_delete'),
    path('salarios/descontos/', views.rh_descontos_salariais, name='descontos_salariais'),
    path('salarios/descontos/adicionar/', views.rh_desconto_salarial_add, name='desconto_salarial_add'),
    path('salarios/descontos/editar/<int:desconto_id>/', views.rh_desconto_salarial_edit, name='desconto_salarial_edit'),
    path('salarios/descontos/excluir/<int:desconto_id>/', views.rh_desconto_salarial_delete, name='desconto_salarial_delete'),
]
