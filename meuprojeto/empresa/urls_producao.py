from django.urls import path
from . import views_producao, views_maquinas, views_linhas

app_name = 'producao'

urlpatterns = [
    # Página principal do módulo de produção
    path('', views_producao.producao_main, name='main'),
    
    # Dashboard de produção
    path('dashboard/', views_producao.producao_dashboard, name='dashboard'),
    
    # Receitas de Produção
    path('receitas/', views_producao.producao_receitas, name='receitas'),
    
    # Processos de Produção
    path('processos/', views_producao.producao_processos, name='processos'),
    path('processos/add/', views_producao.producao_processo_add, name='processo_add'),
    path('processos/<int:id>/', views_producao.producao_processo_detail, name='processo_detail'),
    path('processos/<int:id>/edit/', views_producao.producao_processo_edit, name='processo_edit'),
    path('processos/<int:id>/delete/', views_producao.producao_processo_delete, name='processo_delete'),
    
    # Ordens de Produção - Sistema de 3 Fases
    path('ordens/', views_producao.producao_ordens, name='ordens'),
    path('ordens/<int:id>/', views_producao.producao_ordem_detail, name='ordem_detail'),
    
    # FASE 1: Criação e Aprovação
    path('ordens/fase1/criar/', views_producao.producao_ordem_fase1_criar, name='ordem_fase1_criar'),
    path('ordens/<int:id>/fase1/', views_producao.producao_ordem_fase1, name='ordem_fase1'),
    path('ordens/<int:id>/fase1/aprovar/', views_producao.producao_ordem_fase1_aprovar, name='ordem_fase1_aprovar'),
    path('ordens/<int:id>/fase1/rejeitar/', views_producao.producao_ordem_fase1_rejeitar, name='ordem_fase1_rejeitar'),
    
    # FASE 2: Preparação e Execução
    path('ordens/<int:id>/fase2/', views_producao.producao_ordem_fase2, name='ordem_fase2'),
    path('ordens/<int:id>/fase2/criar-requisicao/', views_producao.producao_ordem_fase2_criar_requisicao, name='ordem_fase2_criar_requisicao'),
    path('ordens/<int:id>/fase2/confirmar-recebimento/', views_producao.producao_ordem_fase2_confirmar_recebimento, name='ordem_fase2_confirmar_recebimento'),
    path('ordens/<int:id>/fase2/marcar-preparacao/', views_producao.producao_ordem_fase2_marcar_preparacao, name='ordem_fase2_marcar_preparacao'),
    path('ordens/<int:id>/fase2/marcar-montagem/', views_producao.producao_ordem_fase2_marcar_montagem, name='ordem_fase2_marcar_montagem'),
    path('ordens/<int:id>/fase2/avancar/', views_producao.producao_ordem_fase2_avancar, name='ordem_fase2_avancar'),
    
    # Requisição de Material - Impressão
    path('requisicoes/<int:id>/imprimir/', views_producao.producao_requisicao_imprimir, name='requisicao_imprimir'),
    
    # FASE 3: Acabamentos e Finalizações
    path('ordens/<int:id>/fase3/', views_producao.producao_ordem_fase3, name='ordem_fase3'),
    path('ordens/<int:id>/fase3/marcar-acabamentos/', views_producao.producao_ordem_fase3_marcar_acabamentos, name='ordem_fase3_marcar_acabamentos'),
    path('ordens/<int:id>/fase3/marcar-retoques/', views_producao.producao_ordem_fase3_marcar_retoques, name='ordem_fase3_marcar_retoques'),
    path('ordens/<int:id>/fase3/aprovar-qualidade/', views_producao.producao_ordem_fase3_aprovar_qualidade, name='ordem_fase3_aprovar_qualidade'),
    path('ordens/<int:id>/fase3/finalizar/', views_producao.producao_ordem_fase3_finalizar, name='ordem_fase3_finalizar'),
    
    # Visualização de documentos PDF da receita
    path('receitas/<int:receita_id>/documentos/', views_producao.producao_receita_documentos, name='receita_documentos'),
    # Visualização de projeto da receita
    path('receitas/<int:receita_id>/projeto/', views_producao.producao_receita_projeto, name='receita_projeto'),
    # Visualização de PDF de receita (permitindo iframe)
    path('receitas/<int:receita_id>/pdf/', views_producao.producao_receita_pdf_view, name='receita_pdf'),
    # Visualização de PDF do plano de corte (permitindo iframe)
    path('receitas/<int:receita_id>/plano-corte-pdf/', views_producao.producao_receita_plano_corte_pdf_view, name='receita_plano_corte_pdf'),
    
    # Máquinas e Equipamentos
    path('maquinas/', views_maquinas.producao_maquinas, name='maquinas'),
    path('maquinas/add/', views_maquinas.producao_maquina_add, name='maquina_add'),
    path('maquinas/<int:id>/', views_maquinas.producao_maquina_detail, name='maquina_detail'),
    path('maquinas/<int:id>/edit/', views_maquinas.producao_maquina_edit, name='maquina_edit'),
    path('maquinas/<int:id>/delete/', views_maquinas.producao_maquina_delete, name='maquina_delete'),
    
    # Linhas de Produção
    path('linhas/', views_linhas.producao_linhas, name='linhas'),
    path('linhas/add/', views_linhas.producao_linha_add, name='linha_add'),
    path('linhas/<int:id>/', views_linhas.producao_linha_detail, name='linha_detail'),
    path('linhas/<int:id>/edit/', views_linhas.producao_linha_edit, name='linha_edit'),
    path('linhas/<int:id>/delete/', views_linhas.producao_linha_delete, name='linha_delete'),
    
    # Controle de Qualidade
    path('qualidade/inspecoes/', views_producao.producao_qualidade_inspecoes, name='qualidade_inspecoes'),
    path('qualidade/nconformidades/', views_producao.producao_qualidade_nconformidades, name='qualidade_nconformidades'),
    path('qualidade/certificados/', views_producao.producao_qualidade_certificados, name='qualidade_certificados'),
    path('qualidade/certificados/<int:id>/', views_producao.producao_qualidade_certificado_view, name='qualidade_certificado_view'),
    
    # Planejamento
    path('planejamento/capacidade/', views_producao.producao_planejamento_capacidade, name='planejamento_capacidade'),
    path('planejamento/cronograma/', views_producao.producao_planejamento_cronograma, name='planejamento_cronograma'),
    path('planejamento/mrp/', views_producao.producao_planejamento_mrp, name='planejamento_mrp'),
    
    # Serviços
    # URLs específicas devem vir ANTES das URLs genéricas
    path('servicos/agendamento/', views_producao.producao_servicos_agendamento, name='servicos_agendamento'),
    path('servicos/agendamento/<int:id>/', views_producao.producao_servico_agendamento_detail, name='servico_agendamento_detail'),
    path('servicos/agendamento/<int:id>/reagendar/', views_producao.producao_servico_agendamento_reagendar, name='servico_agendamento_reagendar'),
    path('servicos/agendamento/<int:id>/cancelar/', views_producao.producao_servico_agendamento_cancelar, name='servico_agendamento_cancelar'),
    path('servicos/equipes/', views_producao.producao_servicos_equipes, name='servicos_equipes'),
    path('servicos/equipes/<int:id>/edit/', views_producao.producao_servico_equipe_edit, name='servico_equipe_edit'),
    path('servicos/equipes/<int:id>/delete/', views_producao.producao_servico_equipe_delete, name='servico_equipe_delete'),
    path('servicos/clientes/', views_producao.producao_servicos_clientes, name='servicos_clientes'),
    path('servicos/contratos/', views_producao.producao_servicos_contratos, name='servicos_contratos'),
    path('servicos/faturamento/', views_producao.producao_servicos_faturamento, name='servicos_faturamento'),
    path('servicos/relatorios/', views_producao.producao_servicos_relatorios, name='servicos_relatorios'),
    path('servicos/relatorios/pdf/', views_producao.producao_servicos_relatorios_pdf, name='servicos_relatorios_pdf'),
    path('servicos/orcamento/', views_producao.producao_servicos_orcamento, name='servicos_orcamento'),
    path('servicos/orcamento/add/', views_producao.producao_servico_orcamento_add, name='servico_orcamento_add'),
    path('servicos/orcamento/debug-js-log/', views_producao.producao_servico_debug_js_log, name='servico_debug_js_log'),
    path('servicos/orcamento/horarios-disponiveis/', views_producao.producao_servico_orcamento_horarios_disponiveis, name='servico_orcamento_horarios_disponiveis'),
    path('servicos/orcamento/<int:id>/confirmar/', views_producao.producao_servico_orcamento_confirmar, name='servico_orcamento_confirmar'),
    path('servicos/orcamento/<int:id>/confirmar/acao/', views_producao.producao_servico_orcamento_confirmar_acao, name='servico_orcamento_confirmar_acao'),
    path('servicos/orcamento/<int:id>/', views_producao.producao_servico_orcamento_detail, name='servico_orcamento_detail'),
    path('servicos/orcamento/<int:id>/imprimir/', views_producao.producao_servico_orcamento_imprimir, name='servico_orcamento_imprimir'),
    path('servicos/orcamento/<int:id>/itens/imprimir/', views_producao.producao_servico_orcamento_itens_imprimir, name='servico_orcamento_itens_imprimir'),
    path('servicos/orcamento/<int:orcamento_id>/editar-contrato/', views_producao.editar_contrato_servico, name='editar_contrato_servico'),
    path('servicos/orcamento/<int:orcamento_id>/preview-contrato/', views_producao.preview_contrato_servico, name='preview_contrato_servico'),
    path('servicos/orcamento/<int:orcamento_id>/gerar-contrato/', views_producao.gerar_contrato_servico, name='gerar_contrato_servico'),
    path('servicos/orcamento/<int:id>/edit/', views_producao.producao_servico_orcamento_edit, name='servico_orcamento_edit'),
    path('servicos/orcamento/<int:id>/delete/', views_producao.producao_servico_orcamento_delete, name='servico_orcamento_delete'),
    path('servicos/ordens/', views_producao.producao_servicos_ordens, name='servicos_ordens'),
    path('servicos/ordens/add/', views_producao.producao_servico_ordem_add, name='servico_ordem_add'),
    path('servicos/ordens/<int:id>/', views_producao.producao_servico_ordem_detail, name='servico_ordem_detail'),
    path('servicos/ordens/<int:id>/plano-execucao/', views_producao.producao_servico_ordem_plano_execucao, name='servico_ordem_plano_execucao'),
    path('servicos/ordens/<int:id>/plano-execucao/imprimir/', views_producao.producao_servico_ordem_plano_imprimir, name='servico_ordem_plano_imprimir'),
    path('servicos/ordens/<int:id>/atividade/<int:atividade_id>/alterar-status/', views_producao.producao_servico_atividade_alterar_status, name='servico_atividade_alterar_status'),
    path('servicos/ordens/<int:id>/atividade/<int:atividade_id>/confirmar-inicio/', views_producao.producao_servico_atividade_confirmar_inicio, name='servico_atividade_confirmar_inicio'),
    path('servicos/ordens/<int:id>/atividade/<int:atividade_id>/confirmar-conclusao/', views_producao.producao_servico_atividade_confirmar_conclusao, name='servico_atividade_confirmar_conclusao'),
    path('servicos/ordens/<int:id>/atividade/<int:atividade_id>/editar-datas/', views_producao.producao_servico_atividade_editar_datas, name='servico_atividade_editar_datas'),
    path('servicos/ordens/<int:id>/edit/', views_producao.producao_servico_ordem_edit, name='servico_ordem_edit'),
    path('servicos/ordens/<int:id>/alterar-status/', views_producao.producao_servico_ordem_alterar_status, name='servico_ordem_alterar_status'),
    path('servicos/ordens/<int:id>/emitir-fatura/', views_producao.producao_servico_ordem_emitir_fatura, name='servico_ordem_emitir_fatura'),
    path('servicos/ordens/<int:id>/marcar-cobrada/', views_producao.producao_servico_ordem_marcar_cobrada, name='servico_ordem_marcar_cobrada'),
    path('servicos/ordens/<int:id>/emitir-garantia/', views_producao.producao_servico_ordem_emitir_garantia, name='servico_ordem_emitir_garantia'),
    path('servicos/clientes/<int:id>/', views_producao.producao_servico_cliente_detail, name='servico_cliente_detail'),
    path('servicos/clientes/<int:id>/edit/', views_producao.producao_servico_cliente_edit, name='servico_cliente_edit'),
    path('servicos/clientes/<int:id>/delete/', views_producao.producao_servico_cliente_delete, name='servico_cliente_delete'),
    # Gestão de Categorias de Serviços (dentro do módulo de Produção)
    path('servicos/categorias/', views_producao.producao_servicos_categorias, name='servicos_categorias'),
    path('servicos/categorias/add/', views_producao.producao_servicos_categoria_add, name='servicos_categoria_add'),
    path('servicos/categorias/<int:id>/edit/', views_producao.producao_servicos_categoria_edit, name='servicos_categoria_edit'),
    path('servicos/categorias/<int:id>/delete/', views_producao.producao_servicos_categoria_delete, name='servicos_categoria_delete'),
    # Propostas Técnicas
    path('levantamentos/obras/add/', views_producao.producao_levantamento_obra_add, name='levantamento_obra_add'),
    path('propostas-tecnicas/', views_producao.producao_propostas_tecnicas, name='propostas_tecnicas'),
    path('propostas-tecnicas/add/', views_producao.producao_proposta_tecnica_add, name='proposta_tecnica_add'),
    path('propostas-tecnicas/<int:id>/', views_producao.producao_proposta_tecnica_detail, name='proposta_tecnica_detail'),
    path('propostas-tecnicas/<int:id>/edit/', views_producao.producao_proposta_tecnica_edit, name='proposta_tecnica_edit'),
    path('propostas-tecnicas/<int:id>/delete/', views_producao.producao_proposta_tecnica_delete, name='proposta_tecnica_delete'),
    path('propostas-tecnicas/<int:id>/mudar-estagio/', views_producao.producao_proposta_tecnica_mudar_estagio, name='proposta_tecnica_mudar_estagio'),
    path('propostas-tecnicas/<int:id>/converter-orcamento/', views_producao.producao_proposta_tecnica_converter_orcamento, name='proposta_tecnica_converter_orcamento'),
    path('propostas-tecnicas/<int:id>/recibo-levantamento/', views_producao.producao_proposta_tecnica_recibo_levantamento, name='proposta_tecnica_recibo_levantamento'),
    path('propostas-tecnicas/cronograma/', views_producao.producao_propostas_tecnicas_cronograma, name='propostas_tecnicas_cronograma'),
    
    # URLs genéricas com parâmetros devem vir DEPOIS das URLs específicas
    path('servicos/<int:id>/edit/', views_producao.producao_servico_edit, name='servico_edit'),
    path('servicos/<int:id>/delete/', views_producao.producao_servico_delete, name='servico_delete'),
    path('servicos/<int:id>/', views_producao.producao_servico_detail, name='servico_detail'),
    path('servicos/add/', views_producao.producao_servico_add, name='servico_add'),
    # URL genérica deve vir POR ÚLTIMO para não capturar URLs específicas
    path('servicos/', views_producao.producao_servicos_list, name='servicos_list'),
]

