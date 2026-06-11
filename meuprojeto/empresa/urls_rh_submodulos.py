from django.urls import path

from . import views_rh_empreitada
from . import views_rh_ferias
from . import views_rh_hierarquia
from . import views_rh_prestador

urlpatterns = [
    path('hierarquia/', views_rh_hierarquia.rh_hierarquia_main, name='hierarquia_main'),
    path('hierarquia/solicitar/', views_rh_hierarquia.rh_hierarquia_solicitar, name='hierarquia_solicitar'),
    path('hierarquia/aprovar/', views_rh_hierarquia.rh_hierarquia_aprovar, name='hierarquia_aprovar'),
    path('hierarquia/historico/', views_rh_hierarquia.rh_hierarquia_historico, name='hierarquia_historico'),
    path('posicoes/', views_rh_hierarquia.rh_posicoes, name='posicoes'),
    path('posicoes/adicionar/', views_rh_hierarquia.rh_posicao_add, name='posicao_add'),
    path('posicoes/<int:posicao_id>/editar/', views_rh_hierarquia.rh_posicao_edit, name='posicao_edit'),
    path('posicoes/<int:posicao_id>/eliminar/', views_rh_hierarquia.rh_posicao_delete, name='posicao_delete'),
    path('ferias/', views_rh_ferias.rh_ferias, name='ferias'),
    path('ferias/solicitar/', views_rh_ferias.rh_ferias_solicitar, name='ferias_solicitar'),
    path('ferias/<int:solicitacao_id>/aprovar/', views_rh_ferias.rh_ferias_aprovar, name='ferias_aprovar'),
    path('ferias/<int:solicitacao_id>/cancelar/', views_rh_ferias.rh_ferias_cancelar, name='ferias_cancelar'),
    path('prestadores/', views_rh_prestador.rh_prestadores, name='prestadores'),
    path('prestadores/adicionar/', views_rh_prestador.rh_prestador_add, name='prestador_add'),
    path('prestadores/<int:prestador_id>/', views_rh_prestador.rh_prestador_detail, name='prestador_detail'),
    path('prestadores/<int:prestador_id>/editar/', views_rh_prestador.rh_prestador_edit, name='prestador_edit'),
    path('prestadores/<int:prestador_id>/eliminar/', views_rh_prestador.rh_prestador_delete, name='prestador_delete'),
    path('empreitadas/', views_rh_empreitada.rh_empreitadas, name='empreitadas'),
    path('empreitadas/adicionar/', views_rh_empreitada.rh_empreitada_add, name='empreitada_add'),
    path('empreitadas/<int:trabalho_id>/', views_rh_empreitada.rh_empreitada_detail, name='empreitada_detail'),
    path('empreitadas/<int:trabalho_id>/editar/', views_rh_empreitada.rh_empreitada_edit, name='empreitada_edit'),
    path('empreitadas/<int:trabalho_id>/eliminar/', views_rh_empreitada.rh_empreitada_delete, name='empreitada_delete'),
    path('empreitadas/contrato/<int:contrato_id>/editar/', views_rh_empreitada.rh_editar_contrato_empreitada, name='editar_contrato_empreitada'),
    path('empreitadas/contrato/<int:contrato_id>/preview/', views_rh_empreitada.rh_preview_contrato_empreitada, name='preview_contrato_empreitada'),
    path('empreitadas/contrato/<int:contrato_id>/confirmar-assinatura/', views_rh_empreitada.rh_confirmar_assinatura_contrato_empreitada, name='confirmar_assinatura_contrato_empreitada'),
]
