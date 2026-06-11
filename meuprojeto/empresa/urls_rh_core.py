from django.urls import path

from . import views_rh_core as views

urlpatterns = [
    path('', views.rh_main, name='main'),
    path('departamentos/', views.rh_departamentos, name='departamentos'),
    path('departamentos/add/', views.rh_departamento_add, name='departamento_add'),
    path('departamentos/<int:id>/edit/', views.rh_departamento_edit, name='departamento_edit'),
    path('departamentos/<int:id>/vinculacao/', views.rh_departamento_vinculacao, name='departamento_vinculacao'),
    path('departamentos/<int:id>/delete/', views.rh_departamento_delete, name='departamento_delete'),
    path('cargos/', views.rh_cargos, name='cargos'),
    path('cargos/add/', views.rh_cargo_add, name='cargo_add'),
    path('cargos/<int:id>/edit/', views.rh_cargo_edit, name='cargo_edit'),
    path('cargos/<int:id>/delete/', views.rh_cargo_delete, name='cargo_delete'),
    path('funcionarios/', views.rh_funcionarios, name='funcionarios'),
    path('funcionarios/add/', views.rh_funcionario_add, name='funcionario_add'),
    path('funcionarios/<int:id>/', views.rh_funcionario_detail, name='funcionario_detail'),
    path('funcionarios/<int:id>/edit/', views.rh_funcionario_edit, name='funcionario_edit'),
    path('funcionarios/<int:id>/delete/', views.rh_funcionario_delete, name='funcionario_delete'),
    path('funcionarios/<int:id>/dados-remuneracao/', views.rh_funcionario_dados_remuneracao, name='funcionario_dados_remuneracao'),
    path('api/funcionarios/search/', views.api_funcionarios_search, name='api_funcionarios_search'),
    path('api/departamentos/sucursal/<int:sucursal_id>/', views.api_departamentos_por_sucursal, name='api_departamentos_por_sucursal'),
]
