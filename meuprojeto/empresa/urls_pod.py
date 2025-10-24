"""
URLs para gerenciamento de POD (Prova de Entrega) e documentos logísticos.
"""
from django.urls import path
from . import views_pod

app_name = 'pod'

urlpatterns = [
    # Dashboard
    path('dashboard/', views_pod.dashboard_pod, name='dashboard'),
    
    # Provas de Entrega
    path('provas/', views_pod.provas_entrega_list, name='provas_list'),
    path('provas/create/', views_pod.prova_entrega_create, name='prova_create'),
    path('provas/<int:prova_id>/', views_pod.prova_entrega_detail, name='prova_detail'),
    path('provas/<int:prova_id>/documento/', views_pod.adicionar_documento_pod, name='adicionar_documento'),
    path('provas/<int:prova_id>/assinatura/', views_pod.adicionar_assinatura_pod, name='adicionar_assinatura'),
    path('provas/<int:prova_id>/validar/', views_pod.validar_prova_entrega, name='validar_prova'),
    
    # Guias de Remessa
    path('guias/', views_pod.guias_remessa_list, name='guias_list'),
    path('guias/create/', views_pod.guia_remessa_create, name='guia_create'),
    path('guias/<int:guia_id>/', views_pod.guia_remessa_detail, name='guia_detail'),
    path('guias/<int:guia_id>/imprimir/', views_pod.imprimir_guia_remessa, name='imprimir_guia'),
    
    # Etiquetas
    path('etiquetas/', views_pod.etiquetas_list, name='etiquetas_list'),
    path('etiquetas/<int:etiqueta_id>/', views_pod.etiqueta_detail, name='etiqueta_detail'),
    path('etiquetas/rastreamento/<int:rastreamento_id>/', views_pod.gerar_etiqueta_rastreamento, name='gerar_etiqueta'),
    path('etiquetas/<int:etiqueta_id>/imprimir/', views_pod.imprimir_etiqueta, name='imprimir_etiqueta'),
]
