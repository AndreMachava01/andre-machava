from django.urls import path
from . import views

app_name = 'rh'

urlpatterns = [
    path('', views.rh_main, name='main'),
    
    # Gestão de Departamentos
    path('departamentos/', views.rh_departamentos, name='departamentos'),
    path('departamentos/add/', views.rh_departamento_add, name='departamento_add'),
    path('departamentos/<int:id>/edit/', views.rh_departamento_edit, name='departamento_edit'),
    path('departamentos/<int:id>/vinculacao/', views.rh_departamento_vinculacao, name='departamento_vinculacao'),
    path('departamentos/<int:id>/delete/', views.rh_departamento_delete, name='departamento_delete'),
    
    # Gestão de Cargos
    path('cargos/', views.rh_cargos, name='cargos'),
    path('cargos/add/', views.rh_cargo_add, name='cargo_add'),
    path('cargos/<int:id>/edit/', views.rh_cargo_edit, name='cargo_edit'),
    path('cargos/<int:id>/delete/', views.rh_cargo_delete, name='cargo_delete'),
    
    # Gestão de Funcionários
    path('funcionarios/', views.rh_funcionarios, name='funcionarios'),
    path('funcionarios/add/', views.rh_funcionario_add, name='funcionario_add'),
    path('funcionarios/<int:id>/', views.rh_funcionario_detail, name='funcionario_detail'),
    path('funcionarios/<int:id>/edit/', views.rh_funcionario_edit, name='funcionario_edit'),
    path('funcionarios/<int:id>/delete/', views.rh_funcionario_delete, name='funcionario_delete'),
    
    # Gestão de Presenças
    path('presencas/', views.rh_presencas, name='presencas'),
    path('presencas/add/', views.rh_presenca_add, name='presenca_add'),
    path('presencas/<int:id>/', views.rh_presenca_detail, name='presenca_detail'),
    path('presencas/<int:id>/edit/', views.rh_presenca_edit, name='presenca_edit'),
    path('presencas/<int:id>/delete/', views.rh_presenca_delete, name='presenca_delete'),
    path('presencas/detalhes/<int:ano>/<int:mes>/', views.rh_detalhes_mes, name='detalhes_mes'),
    
    # Gestão de Horas Extras
    path('horas-extras/', views.rh_horas_extras_lista, name='horas_extras'),
    path('horas-extras/nova/', views.rh_horas_extras, name='horas_extras_nova'),
    path('horas-extras/lista/', views.rh_horas_extras_lista, name='horas_extras_lista'),
    path('horas-extras/<int:id>/editar/', views.rh_horas_extras_editar, name='horas_extras_editar'),
    path('horas-extras/<int:id>/excluir/', views.rh_horas_extras_excluir, name='horas_extras_excluir'),
    path('horas-extras/detectar-tipo/', views.rh_detectar_tipo_horas_extras, name='detectar_tipo_horas_extras'),
    path('horas-extras/calcular-mistas/', views.rh_calcular_horas_extras_mistas, name='calcular_horas_extras_mistas'),
    path('horas-extras/criar-mistas/', views.rh_criar_horas_extras_mistas, name='criar_horas_extras_mistas'),
    path('funcionarios/<int:id>/dados-remuneracao/', views.rh_funcionario_dados_remuneracao, name='funcionario_dados_remuneracao'),
    
    # Tipos de Presença
    path('presencas/tipos/', views.rh_tipos_presenca, name='tipos_presenca'),
    path('presencas/tipos/add/', views.rh_tipo_presenca_add, name='tipo_presenca_add'),
    path('presencas/tipos/<int:id>/edit/', views.rh_tipo_presenca_edit, name='tipo_presenca_edit'),
    path('presencas/tipos/<int:id>/delete/', views.rh_tipo_presenca_delete, name='tipo_presenca_delete'),
    
    # Calendário de Presenças
    path('presencas/calendario/', views.rh_calendario_presencas, name='calendario_presencas'),
    path('presencas/calendario/debug/', views.rh_calendario_debug, name='calendario_debug'),
    path('presencas/calendario/teste/', views.rh_calendario_presencas, {'template_name': 'rh/presencas/calendario_teste.html'}, name='calendario_teste'),
    path('presencas/calendario/minimal/', views.rh_calendario_presencas, {'template_name': 'rh/presencas/calendario_minimal.html'}, name='calendario_minimal'),
    path('presencas/calendario/teste-navegacao/', views.rh_calendario_presencas, {'template_name': 'rh/presencas/calendario_teste_navegacao.html'}, name='calendario_teste_navegacao'),
    path('presencas/calendario/debug-navegacao/', views.rh_calendario_presencas, {'template_name': 'rh/presencas/calendario_debug_navegacao.html'}, name='calendario_debug_navegacao'),
    path('presencas/calendario/salvar/', views.rh_salvar_presenca_calendario, name='salvar_presenca_calendario'),
    path('presencas/calendario/remover/', views.rh_remover_presenca_calendario, name='remover_presenca_calendario'),
    path('presencas/calendario/marcar-dias-uteis/', views.rh_marcar_dias_uteis, name='marcar_dias_uteis'),
    path('presencas/calendario/marcar-finais-semana/', views.rh_marcar_finais_semana, name='marcar_finais_semana'),
    path('presencas/calendario/marcar-feriados/', views.rh_marcar_feriados_automaticos, name='marcar_feriados_automaticos'),
    path('presencas/calendario/marcar-finais-semana-automaticos/', views.rh_marcar_finais_semana_automaticos, name='marcar_finais_semana_automaticos'),
    
    # Feriados
    path('feriados/', views.rh_feriados, name='feriados'),
    path('feriados/adicionar/', views.rh_feriado_add, name='feriado_add'),
    path('feriados/editar/<int:feriado_id>/', views.rh_feriado_edit, name='feriado_edit'),
    path('feriados/excluir/<int:feriado_id>/', views.rh_feriado_delete, name='feriado_delete'),
    
    # Horários de Expediente
    path('horarios-expediente/', views.rh_horarios_expediente, name='horarios_expediente'),
    path('horarios-expediente/<int:sucursal_id>/', views.rh_horarios_expediente, name='horarios_expediente_sucursal'),
    
    # Salários
    path('salarios/', views.rh_salarios, name='salarios'),
    path('salarios/adicionar/', views.rh_salario_add, name='salario_add'),
    path('salarios/editar/<int:salario_id>/', views.rh_salario_edit, name='salario_edit'),
    path('salarios/excluir/<int:salario_id>/', views.rh_salario_delete, name='salario_delete'),
    
    # Benefícios Salariais
    path('salarios/beneficios/', views.rh_beneficios_salariais, name='beneficios_salariais'),
    path('salarios/beneficios/adicionar/', views.rh_beneficio_salarial_add, name='beneficio_salarial_add'),
    path('salarios/beneficios/editar/<int:beneficio_id>/', views.rh_beneficio_salarial_edit, name='beneficio_salarial_edit'),
    path('salarios/beneficios/excluir/<int:beneficio_id>/', views.rh_beneficio_salarial_delete, name='beneficio_salarial_delete'),
    
    # Descontos Salariais
    path('salarios/descontos/', views.rh_descontos_salariais, name='descontos_salariais'),
    path('salarios/descontos/adicionar/', views.rh_desconto_salarial_add, name='desconto_salarial_add'),
    path('salarios/descontos/editar/<int:desconto_id>/', views.rh_desconto_salarial_edit, name='desconto_salarial_edit'),
    path('salarios/descontos/excluir/<int:desconto_id>/', views.rh_desconto_salarial_delete, name='desconto_salarial_delete'),
    
    # Treinamentos e Formação
    path('treinamentos/', views.rh_treinamentos, name='treinamentos'),
    path('treinamentos/adicionar/', views.treinamento_add, name='treinamento_add'),
    path('treinamentos/editar/<int:treinamento_id>/', views.treinamento_edit, name='treinamento_edit'),
    path('treinamentos/detalhes/<int:treinamento_id>/', views.treinamento_detail, name='treinamento_detail'),
    path('treinamentos/deletar/<int:treinamento_id>/', views.treinamento_delete, name='treinamento_delete'),
    
    # Inscrições em Treinamentos
    path('treinamentos/<int:treinamento_id>/inscrever/', views.treinamento_inscrever, name='treinamento_inscrever'),
    path('treinamentos/<int:treinamento_id>/inscricoes/', views.treinamento_inscricoes, name='treinamento_inscricoes'),
    path('inscricoes/<int:inscricao_id>/alterar-status/', views.inscricao_alterar_status, name='inscricao_alterar_status'),
    path('inscricoes/<int:inscricao_id>/avaliar/', views.inscricao_avaliar, name='inscricao_avaliar'),
    path('inscricoes/<int:inscricao_id>/deletar/', views.inscricao_deletar, name='inscricao_deletar'),
    
    # Avaliações de Desempenho
    path('avaliacoes/', views.rh_avaliacoes, name='avaliacoes'),
    path('avaliacoes/adicionar/', views.avaliacao_add, name='avaliacao_add'),
    path('avaliacoes/adicionar-lote/', views.avaliacao_add_batch, name='avaliacao_add_batch'),
    path('avaliacoes/editar/<int:avaliacao_id>/', views.avaliacao_edit, name='avaliacao_edit'),
    path('avaliacoes/detalhes/<int:avaliacao_id>/', views.avaliacao_detail, name='avaliacao_detail'),
    path('avaliacoes/iniciar/<int:avaliacao_id>/', views.avaliacao_iniciar, name='avaliacao_iniciar'),
    path('avaliacoes/concluir/<int:avaliacao_id>/', views.avaliacao_concluir, name='avaliacao_concluir'),
    path('avaliacoes/deletar/<int:avaliacao_id>/', views.avaliacao_delete, name='avaliacao_delete'),
    path('avaliacoes/imprimir/<int:avaliacao_id>/', views.avaliacao_print, name='avaliacao_print'),
    path('avaliacoes/visualizar/<int:avaliacao_id>/', views.avaliacao_print_html, name='avaliacao_print_html'),
    path('avaliacoes/criterios/', views.criterios, name='criterios'),
    path('avaliacoes/criterios/adicionar/', views.criterio_add, name='criterio_add'),
    path('avaliacoes/criterios/editar/<int:criterio_id>/', views.criterio_edit, name='criterio_edit'),
    path('avaliacoes/criterios/deletar/<int:criterio_id>/', views.criterio_delete, name='criterio_delete'),
    
    # Outros módulos
    path('relatorios/', views.rh_relatorios, name='relatorios'),
    path('relatorios/funcionarios/', views.relatorio_funcionarios_documento, name='relatorio_funcionarios_documento'),
    path('relatorios/presencas/', views.relatorio_presencas_documento, name='relatorio_presencas_documento'),
    path('relatorios/salarios/', views.relatorio_salarios_documento, name='relatorio_salarios_documento'),
    path('relatorios/treinamentos/', views.relatorio_treinamentos_documento, name='relatorio_treinamentos_documento'),
    path('relatorios/avaliacoes/', views.relatorio_avaliacoes_documento, name='relatorio_avaliacoes_documento'),
    path('relatorios/horas-extras/', views.relatorio_horas_extras_documento, name='relatorio_horas_extras_documento'),
    path('relatorios/feriados/', views.relatorio_feriados_documento, name='relatorio_feriados_documento'),
    path('relatorios/pdf/', views.relatorio_pdf, name='relatorio_pdf'),
    
    # Exportação PDF dos Relatórios
    path('relatorios/funcionarios/pdf/', views.relatorio_funcionarios_pdf, name='relatorio_funcionarios_pdf'),
    path('relatorios/presencas/pdf/', views.relatorio_presencas_pdf, name='relatorio_presencas_pdf'),
    path('relatorios/salarios/pdf/', views.relatorio_salarios_pdf, name='relatorio_salarios_pdf'),
    path('relatorios/treinamentos/pdf/', views.relatorio_treinamentos_pdf, name='relatorio_treinamentos_pdf'),
    path('relatorios/avaliacoes/pdf/', views.relatorio_avaliacoes_pdf, name='relatorio_avaliacoes_pdf'),
    path('relatorios/horas-extras/pdf/', views.relatorio_horas_extras_pdf, name='relatorio_horas_extras_pdf'),
    path('relatorios/feriados/pdf/', views.relatorio_feriados_pdf, name='relatorio_feriados_pdf'),
    
    # Folha Salarial
    path('folha-salarial/', views.rh_folha_salarial, name='folha_salarial'),
    path('folha-salarial/adicionar/', views.rh_folha_add, name='folha_add'),
    path('folha-salarial/detalhes/<int:folha_id>/', views.rh_folha_detail, name='folha_detail'),
    path('folha-salarial/editar/<int:folha_id>/', views.rh_folha_edit, name='folha_edit'),
    path('folha-salarial/deletar/<int:folha_id>/', views.rh_folha_delete, name='folha_delete'),
    path('folha-salarial/calcular/<int:folha_id>/', views.rh_folha_calcular, name='folha_calcular'),
    path('folha-salarial/pdf/<int:folha_id>/', views.rh_folha_pdf, name='folha_pdf'),
    path('folha-salarial/preview/<int:folha_id>/', views.rh_folha_preview, name='folha_preview'),
    
    # Fechamento da Folha
    path('folha-salarial/validar-fechamento/<int:folha_id>/', views.rh_folha_validar_fechamento, name='folha_validar_fechamento'),
    path('folha-salarial/fechar/<int:folha_id>/', views.rh_folha_fechar, name='folha_fechar'),
    path('folha-salarial/reabrir/<int:folha_id>/', views.rh_folha_reabrir, name='folha_reabrir'),
    path('folha-salarial/marcar-paga/<int:folha_id>/', views.rh_folha_marcar_paga, name='folha_marcar_paga'),
    
    # Canhoto (Recibo de Salário)
    path('folha-salarial/canhoto/<int:folha_id>/<int:funcionario_id>/', views.rh_canhoto_salario, name='canhoto_salario'),
    path('folha-salarial/canhoto-visualizar/<int:folha_id>/<int:funcionario_id>/', views.rh_canhoto_visualizar, name='canhoto_visualizar'),
    
    # Benefícios e Descontos na Folha
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
    
    # Promoções e Aumentos
    path('promocoes/', views.rh_promocoes, name='promocoes'),
    path('promocoes/adicionar/', views.rh_promocao_add, name='promocao_add'),
    path('promocoes/detalhes/<int:promocao_id>/', views.rh_promocao_detail, name='promocao_detail'),
    path('promocoes/editar/<int:promocao_id>/', views.rh_promocao_edit, name='promocao_edit'),
    path('promocoes/deletar/<int:promocao_id>/', views.rh_promocao_delete, name='promocao_delete'),
    path('promocoes/aprovar/<int:promocao_id>/', views.rh_promocao_aprovar, name='promocao_aprovar'),
    path('promocoes/rejeitar/<int:promocao_id>/', views.rh_promocao_rejeitar, name='promocao_rejeitar'),
    path('promocoes/implementar/<int:promocao_id>/', views.rh_promocao_implementar, name='promocao_implementar'),
    path('promocoes/relatorio/', views.rh_promocoes_relatorio, name='promocoes_relatorio'),
    
    # Transferências de Funcionários
    path('transferencias/', views.rh_transferencias, name='transferencias'),
    path('transferencias/adicionar/', views.rh_transferencia_add, name='transferencia_add'),
    path('transferencias/detalhes/<int:transferencia_id>/', views.rh_transferencia_detail, name='transferencia_detail'),
    path('transferencias/editar/<int:transferencia_id>/', views.rh_transferencia_edit, name='transferencia_edit'),
    path('transferencias/deletar/<int:transferencia_id>/', views.rh_transferencia_delete, name='transferencia_delete'),
    path('transferencias/aprovar/<int:transferencia_id>/', views.rh_transferencia_aprovar, name='transferencia_aprovar'),
    path('transferencias/rejeitar/<int:transferencia_id>/', views.rh_transferencia_rejeitar, name='transferencia_rejeitar'),
    path('transferencias/implementar/<int:transferencia_id>/', views.rh_transferencia_implementar, name='transferencia_implementar'),
    path('transferencias/efetivar/<int:transferencia_id>/', views.rh_transferencia_efetivar, name='transferencia_efetivar'),
    path('transferencias/relatorio/', views.rh_transferencias_relatorio, name='transferencias_relatorio'),
    
    # API Endpoints
    path('api/funcionarios/search/', views.api_funcionarios_search, name='api_funcionarios_search'),
    path('api/departamentos/sucursal/<int:sucursal_id>/', views.api_departamentos_por_sucursal, name='api_departamentos_por_sucursal'),
]