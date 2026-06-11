from django.urls import path
from . import views_marketing

app_name = 'marketing'

urlpatterns = [
    path('', views_marketing.marketing_main, name='main'),
    path('campanhas/', views_marketing.campanha_list, name='campanha_list'),
    path('campanhas/nova/', views_marketing.campanha_add, name='campanha_add'),
    path('campanhas/<int:pk>/', views_marketing.campanha_detail, name='campanha_detail'),
    path('campanhas/<int:pk>/editar/', views_marketing.campanha_edit, name='campanha_edit'),
    path('redes-sociais/', views_marketing.redes_sociais_list, name='redes_sociais_list'),
    path('redes-sociais/nova/', views_marketing.redes_sociais_add, name='redes_sociais_add'),
    path('redes-sociais/<int:pk>/', views_marketing.redes_sociais_detail, name='redes_sociais_detail'),
    path('redes-sociais/<int:pk>/editar/', views_marketing.redes_sociais_edit, name='redes_sociais_edit'),
    path('publicidade/', views_marketing.publicidade_list, name='publicidade_list'),
    path('publicidade/nova/', views_marketing.publicidade_add, name='publicidade_add'),
    path('publicidade/<int:pk>/editar/', views_marketing.publicidade_edit, name='publicidade_edit'),
    path('analise-metricas/', views_marketing.analise_metricas, name='analise_metricas'),
]
