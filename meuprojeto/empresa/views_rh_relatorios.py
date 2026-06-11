"""Views RH — relatórios RH."""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Count, Case, When, IntegerField, Sum, Avg
from django.http import JsonResponse, HttpResponse
from django.core.exceptions import ValidationError
from django.contrib import messages
from django.utils import timezone
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
import calendar
import logging
import os
import tempfile
from urllib.parse import urlencode
from django.urls import reverse

from .models_rh import (
    Funcionario, Departamento, Cargo, Presenca, TipoPresenca, Feriado, HorasExtras,
    Salario, BeneficioSalarial, DescontoSalarial, Treinamento, AvaliacaoDesempenho,
    CriterioAvaliacao, CriterioAvaliado, FolhaSalarial, FuncionarioFolha, Promocao,
    DepartamentoSucursal, TransferenciaFuncionario, InscricaoTreinamento,
)
from .models_base import Sucursal
from .views import (
    generate_pdf_report,
    generate_pdf_from_html,
    render_pdf_from_url,
    render_pdf_from_html_string,
)

logger = logging.getLogger(__name__)


@login_required
def rh_relatorios(request):
    """Página de relatórios do RH"""
    from .services.rh_service import obter_estatisticas_rh
    return render(request, 'rh/relatorios/main.html', obter_estatisticas_rh())

@login_required
def relatorio_funcionarios_documento(request):
    """Relatório de Funcionários - Documento Completo"""
    from django.db.models import Count, Q
    from django.utils import timezone
    
    # Filtros opcionais
    departamento_id = request.GET.get('departamento')
    status_filter = request.GET.get('status')
    data_admissao_inicio = request.GET.get('data_admissao_inicio')
    data_admissao_fim = request.GET.get('data_admissao_fim')
    
    # Query base
    funcionarios_query = Funcionario.objects.select_related('cargo', 'departamento', 'sucursal').order_by('nome_completo')
    
    # Aplicar filtros
    if departamento_id:
        funcionarios_query = funcionarios_query.filter(departamento_id=departamento_id)
    
    if status_filter:
        funcionarios_query = funcionarios_query.filter(status=status_filter)
    
    if data_admissao_inicio:
        try:
            from datetime import datetime
            data_inicio = datetime.strptime(data_admissao_inicio, '%Y-%m-%d').date()
            funcionarios_query = funcionarios_query.filter(data_admissao__gte=data_inicio)
        except ValueError:
            pass
    
    if data_admissao_fim:
        try:
            from datetime import datetime
            data_fim = datetime.strptime(data_admissao_fim, '%Y-%m-%d').date()
            funcionarios_query = funcionarios_query.filter(data_admissao__lte=data_fim)
        except ValueError:
            pass
    
    # Dados básicos
    funcionarios = funcionarios_query
    total_funcionarios = funcionarios.count()
    funcionarios_ativos = funcionarios.filter(status='AT').count()
    funcionarios_inativos = funcionarios.filter(status='IN').count()
    
    # Estatísticas por departamento (corrigido)
    funcionarios_por_departamento = funcionarios.values(
        'departamento__nome'
    ).annotate(
        total=Count('id')
    ).order_by('-total')
    
    # Calcular percentuais
    for dept in funcionarios_por_departamento:
        if total_funcionarios > 0:
            dept['percentual'] = (dept['total'] / total_funcionarios) * 100
        else:
            dept['percentual'] = 0
    
    # Estatísticas por cargo
    funcionarios_por_cargo = funcionarios.values(
        'cargo__nome'
    ).annotate(
        total=Count('id')
    ).order_by('-total')
    
    # Estatísticas por sucursal
    funcionarios_por_sucursal = funcionarios.values(
        'sucursal__nome'
    ).annotate(
        total=Count('id')
    ).order_by('-total')
    
    # Outras estatísticas
    total_departamentos = Departamento.objects.count()
    total_cargos = Cargo.objects.count()
    total_sucursais = Sucursal.objects.filter(ativa=True).count()
    
    # Dados para filtros
    departamentos = Departamento.objects.all().order_by('nome')
    
    context = {
        'funcionarios': funcionarios,
        'total_funcionarios': total_funcionarios,
        'funcionarios_ativos': funcionarios_ativos,
        'funcionarios_inativos': funcionarios_inativos,
        'total_departamentos': total_departamentos,
        'total_cargos': total_cargos,
        'total_sucursais': total_sucursais,
        'funcionarios_por_departamento': funcionarios_por_departamento,
        'funcionarios_por_cargo': funcionarios_por_cargo,
        'funcionarios_por_sucursal': funcionarios_por_sucursal,
        'departamentos': departamentos,
        'filtros': {
            'departamento': departamento_id,
            'status': status_filter,
            'data_admissao_inicio': data_admissao_inicio,
            'data_admissao_fim': data_admissao_fim,
        },
        'data_relatorio': timezone.now(),
    }
    
    return render(request, 'rh/relatorios/funcionarios_documento.html', context)

@login_required
def relatorio_presencas_documento(request):
    """Relatório de Presenças - Documento Completo"""
    from django.db.models import Count, Q
    from django.utils import timezone
    from datetime import datetime, timedelta
    
    # Período padrão: últimos 30 dias
    data_fim = timezone.now().date()
    data_inicio = data_fim - timedelta(days=30)
    
    # Filtros opcionais
    funcionario_id = request.GET.get('funcionario')
    departamento_id = request.GET.get('departamento')
    
    # Permitir filtros via GET
    if request.GET.get('data_inicio'):
        try:
            data_inicio = datetime.strptime(request.GET.get('data_inicio'), '%Y-%m-%d').date()
        except ValueError:
            pass
    
    if request.GET.get('data_fim'):
        try:
            data_fim = datetime.strptime(request.GET.get('data_fim'), '%Y-%m-%d').date()
        except ValueError:
            pass
    
    # Query base
    presencas_query = Presenca.objects.filter(
        data__range=[data_inicio, data_fim]
    ).select_related('funcionario', 'tipo_presenca', 'funcionario__cargo', 'funcionario__departamento')
    
    # Aplicar filtros
    if funcionario_id:
        presencas_query = presencas_query.filter(funcionario_id=funcionario_id)
    
    if departamento_id:
        presencas_query = presencas_query.filter(funcionario__departamento_id=departamento_id)
    
    # Dados básicos
    presencas = presencas_query
    total_presencas = presencas.count()
    
    # Obter tipos de presença existentes
    tipos_presenca = TipoPresenca.objects.all()
    
    # Estatísticas por tipo (corrigido)
    presencas_por_tipo = []
    for tipo in tipos_presenca:
        count = presencas.filter(tipo_presenca=tipo).count()
        if count > 0:
            presencas_por_tipo.append({
                'tipo_presenca__nome': tipo.nome,
                'total': count,
                'percentual': (count / total_presencas) * 100 if total_presencas > 0 else 0
            })
    
    # Contar presentes e ausentes (usando nomes em vez de códigos)
    presencas_presente = presencas.filter(tipo_presenca__nome__icontains='presente').count()
    presencas_ausente = presencas.filter(tipo_presenca__nome__icontains='ausente').count()
    
    # Calcular taxa de presença
    if total_presencas > 0:
        percentual_presenca = (presencas_presente / total_presencas) * 100
    else:
        percentual_presenca = 0
    
    # Presenças por funcionário (corrigido)
    presencas_por_funcionario = presencas.values(
        'funcionario__nome_completo',
        'funcionario__departamento__nome'
    ).annotate(
        presentes=Count('id', filter=Q(tipo_presenca__nome__icontains='presente')),
        ausentes=Count('id', filter=Q(tipo_presenca__nome__icontains='ausente')),
        total=Count('id')
    ).order_by('-presentes')
    
    # Calcular taxa de presença por funcionário
    for func in presencas_por_funcionario:
        if func['total'] > 0:
            func['taxa_presenca'] = (func['presentes'] / func['total']) * 100
        else:
            func['taxa_presenca'] = 0
    
    # Presenças por departamento
    presencas_por_departamento = presencas.values(
        'funcionario__departamento__nome'
    ).annotate(
        total=Count('id'),
        presentes=Count('id', filter=Q(tipo_presenca__nome__icontains='presente')),
        ausentes=Count('id', filter=Q(tipo_presenca__nome__icontains='ausente'))
    ).order_by('-total')
    
    # Calcular taxa por departamento
    for dept in presencas_por_departamento:
        if dept['total'] > 0:
            dept['taxa_presenca'] = (dept['presentes'] / dept['total']) * 100
        else:
            dept['taxa_presenca'] = 0
    
    # Dados para filtros
    funcionarios = Funcionario.objects.filter(status='AT').order_by('nome_completo')
    departamentos = Departamento.objects.all().order_by('nome')
    
    context = {
        'presencas': presencas,
        'total_presencas': total_presencas,
        'presencas_presente': presencas_presente,
        'presencas_ausente': presencas_ausente,
        'percentual_presenca': percentual_presenca,
        'presencas_por_tipo': presencas_por_tipo,
        'presencas_por_funcionario': presencas_por_funcionario,
        'presencas_por_departamento': presencas_por_departamento,
        'funcionarios': funcionarios,
        'departamentos': departamentos,
        'filtros': {
            'funcionario': funcionario_id,
            'departamento': departamento_id,
        },
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'data_relatorio': timezone.now(),
    }
    
    return render(request, 'rh/relatorios/presencas_documento.html', context)

@login_required
def relatorio_salarios_documento(request):
    """Relatório de Salários - Documento Completo"""
    from django.db.models import Count, Q, Sum, Avg
    from django.utils import timezone
    
    # Filtros opcionais
    departamento_id = request.GET.get('departamento')
    mes_referencia = request.GET.get('mes_referencia')
    
    # Query base - usar FolhaSalarial em vez de Salario
    folhas_query = FolhaSalarial.objects.all().order_by('-mes_referencia')
    
    # Aplicar filtros
    if mes_referencia:
        try:
            from datetime import datetime
            mes_ref = datetime.strptime(mes_referencia, '%Y-%m').date()
            folhas_query = folhas_query.filter(mes_referencia=mes_ref)
        except ValueError:
            pass
    
    # Dados básicos
    folhas = folhas_query
    total_folhas = folhas.count()
    folhas_calculadas = folhas.filter(status='CALCULADA').count()
    folhas_fechadas = folhas.filter(status='FECHADA').count()
    
    # Estatísticas gerais
    valor_total_bruto = folhas.aggregate(total=Sum('total_bruto'))['total'] or 0
    valor_total_liquido = folhas.aggregate(total=Sum('total_liquido'))['total'] or 0
    valor_total_descontos = folhas.aggregate(total=Sum('total_descontos'))['total'] or 0
    
    # Estatísticas por departamento (usando FuncionarioFolha)
    funcionarios_folha = FuncionarioFolha.objects.select_related(
        'funcionario', 'funcionario__departamento', 'folha'
    )
    
    if departamento_id:
        funcionarios_folha = funcionarios_folha.filter(funcionario__departamento_id=departamento_id)
    
    salarios_por_departamento = funcionarios_folha.values(
        'funcionario__departamento__nome'
    ).annotate(
        total_funcionarios=Count('id'),
        salario_total=Sum('salario_liquido'),
        salario_medio=Avg('salario_liquido')
    ).order_by('-salario_total')
    
    # Calcular percentuais
    for dept in salarios_por_departamento:
        if valor_total_liquido > 0:
            dept['percentual'] = ((dept['salario_total'] or 0) / valor_total_liquido) * 100
        else:
            dept['percentual'] = 0
    
    # Estatísticas por cargo
    salarios_por_cargo = funcionarios_folha.values(
        'funcionario__cargo__nome'
    ).annotate(
        total_funcionarios=Count('id'),
        salario_total=Sum('salario_liquido'),
        salario_medio=Avg('salario_liquido')
    ).order_by('-salario_total')
    
    # Funcionários com maiores salários
    funcionarios_maiores_salarios = funcionarios_folha.order_by('-salario_liquido')[:10]
    
    # Funcionários com menores salários
    funcionarios_menores_salarios = funcionarios_folha.order_by('salario_liquido')[:10]
    
    # Estatísticas de benefícios e descontos
    total_beneficios = funcionarios_folha.aggregate(total=Sum('total_beneficios'))['total'] or 0
    total_descontos = funcionarios_folha.aggregate(total=Sum('total_descontos'))['total'] or 0
    
    # Outras estatísticas
    total_departamentos = Departamento.objects.count()
    total_cargos = Cargo.objects.count()
    total_funcionarios_folha = funcionarios_folha.count()
    
    # Dados para filtros
    departamentos = Departamento.objects.all().order_by('nome')
    
    context = {
        'folhas': folhas,
        'total_folhas': total_folhas,
        'folhas_calculadas': folhas_calculadas,
        'folhas_fechadas': folhas_fechadas,
        'total_departamentos': total_departamentos,
        'total_cargos': total_cargos,
        'total_funcionarios_folha': total_funcionarios_folha,
        'salarios_por_departamento': salarios_por_departamento,
        'salarios_por_cargo': salarios_por_cargo,
        'funcionarios_maiores_salarios': funcionarios_maiores_salarios,
        'funcionarios_menores_salarios': funcionarios_menores_salarios,
        'valor_total_bruto': valor_total_bruto,
        'valor_total_liquido': valor_total_liquido,
        'valor_total_descontos': valor_total_descontos,
        'total_beneficios': total_beneficios,
        'total_descontos': total_descontos,
        'departamentos': departamentos,
        'filtros': {
            'departamento': departamento_id,
            'mes_referencia': mes_referencia,
        },
        'data_relatorio': timezone.now(),
    }
    
    return render(request, 'rh/relatorios/salarios_documento.html', context)

@login_required
def relatorio_treinamentos_documento(request):
    """Relatório de Treinamentos - Documento Completo"""
    from django.db.models import Count, Q, Avg
    from django.utils import timezone
    from datetime import datetime, timedelta
    
    # Filtros opcionais
    tipo_filter = request.GET.get('tipo')
    status_filter = request.GET.get('status')
    data_inicio_filter = request.GET.get('data_inicio')
    data_fim_filter = request.GET.get('data_fim')
    
    # Query base
    treinamentos_query = Treinamento.objects.all().order_by('-data_inicio')
    
    # Aplicar filtros
    # Nota: Treinamento não tem campo departamento, removendo filtro
    
    if tipo_filter:
        treinamentos_query = treinamentos_query.filter(tipo=tipo_filter)
    
    if status_filter:
        treinamentos_query = treinamentos_query.filter(status=status_filter)
    
    if data_inicio_filter:
        try:
            data_inicio = datetime.strptime(data_inicio_filter, '%Y-%m-%d').date()
            treinamentos_query = treinamentos_query.filter(data_inicio__gte=data_inicio)
        except ValueError:
            pass
    
    if data_fim_filter:
        try:
            data_fim = datetime.strptime(data_fim_filter, '%Y-%m-%d').date()
            treinamentos_query = treinamentos_query.filter(data_fim__lte=data_fim)
        except ValueError:
            pass
    
    # Dados básicos
    treinamentos = treinamentos_query
    total_treinamentos = treinamentos.count()
    treinamentos_ativos = treinamentos.filter(status='EM_ANDAMENTO').count()
    treinamentos_concluidos = treinamentos.filter(status='CONCLUIDO').count()
    treinamentos_cancelados = treinamentos.filter(status='CANCELADO').count()
    
    # Estatísticas por tipo (em vez de departamento)
    treinamentos_por_tipo = treinamentos.values('tipo').annotate(
        total=Count('id')
    ).order_by('-total')
    
    # Calcular percentuais
    for tipo in treinamentos_por_tipo:
        if total_treinamentos > 0:
            tipo['percentual'] = (tipo['total'] / total_treinamentos) * 100
        else:
            tipo['percentual'] = 0
    
    # Inscrições por treinamento
    inscricoes_por_treinamento = treinamentos.annotate(
        total_inscricoes=Count('inscricoes'),
        inscricoes_concluidas=Count('inscricoes', filter=Q(inscricoes__status='CONCLUIDO')),
        inscricoes_ativas=Count('inscricoes', filter=Q(inscricoes__status='ATIVO'))
    ).order_by('-total_inscricoes')
    
    # Calcular taxa de conclusão por treinamento
    for treinamento in inscricoes_por_treinamento:
        if treinamento.total_inscricoes > 0:
            treinamento.taxa_conclusao = (treinamento.inscricoes_concluidas / treinamento.total_inscricoes) * 100
        else:
            treinamento.taxa_conclusao = 0
    
    # Funcionários mais treinados
    funcionarios_mais_treinados = InscricaoTreinamento.objects.values(
        'funcionario__nome_completo',
        'funcionario__departamento__nome'
    ).annotate(
        total_treinamentos=Count('id'),
        treinamentos_concluidos=Count('id', filter=Q(status='CONCLUIDO'))
    ).order_by('-total_treinamentos')[:10]
    
    # Calcular taxa de conclusão por funcionário
    for func in funcionarios_mais_treinados:
        if func['total_treinamentos'] > 0:
            func['taxa_conclusao'] = (func['treinamentos_concluidos'] / func['total_treinamentos']) * 100
        else:
            func['taxa_conclusao'] = 0
    
    # Estatísticas gerais
    total_inscricoes = InscricaoTreinamento.objects.count()
    inscricoes_concluidas = InscricaoTreinamento.objects.filter(status='CONCLUIDO').count()
    inscricoes_ativas = InscricaoTreinamento.objects.filter(status='ATIVO').count()
    
    # Calcular taxa geral de conclusão
    if total_inscricoes > 0:
        taxa_conclusao_geral = (inscricoes_concluidas / total_inscricoes) * 100
    else:
        taxa_conclusao_geral = 0
    
    # Dados para filtros
    departamentos = Departamento.objects.all().order_by('nome')
    
    context = {
        'treinamentos': treinamentos,
        'total_treinamentos': total_treinamentos,
        'treinamentos_ativos': treinamentos_ativos,
        'treinamentos_concluidos': treinamentos_concluidos,
        'treinamentos_cancelados': treinamentos_cancelados,
        'treinamentos_por_tipo': treinamentos_por_tipo,
        'inscricoes_por_treinamento': inscricoes_por_treinamento,
        'funcionarios_mais_treinados': funcionarios_mais_treinados,
        'total_inscricoes': total_inscricoes,
        'inscricoes_concluidas': inscricoes_concluidas,
        'inscricoes_ativas': inscricoes_ativas,
        'taxa_conclusao_geral': taxa_conclusao_geral,
        'filtros': {
            'tipo': tipo_filter,
            'status': status_filter,
            'data_inicio': data_inicio_filter,
            'data_fim': data_fim_filter,
        },
        'data_relatorio': timezone.now(),
    }
    
    return render(request, 'rh/relatorios/treinamentos_documento.html', context)

@login_required
def relatorio_avaliacoes_documento(request):
    """Relatório de Avaliações de Desempenho - Documento Completo"""
    from django.db.models import Count, Q, Avg
    from django.utils import timezone
    from datetime import datetime, timedelta
    
    # Filtros opcionais
    departamento_id = request.GET.get('departamento')
    status_filter = request.GET.get('status')
    data_inicio_filter = request.GET.get('data_inicio')
    data_fim_filter = request.GET.get('data_fim')
    
    # Query base
    avaliacoes_query = AvaliacaoDesempenho.objects.select_related('funcionario', 'funcionario__departamento').order_by('-data_inicio')
    
    # Aplicar filtros
    if departamento_id:
        avaliacoes_query = avaliacoes_query.filter(funcionario__departamento_id=departamento_id)
    
    if status_filter:
        avaliacoes_query = avaliacoes_query.filter(status=status_filter)
    
    if data_inicio_filter:
        try:
            data_inicio = datetime.strptime(data_inicio_filter, '%Y-%m-%d').date()
            avaliacoes_query = avaliacoes_query.filter(data_inicio__gte=data_inicio)
        except ValueError:
            pass
    
    if data_fim_filter:
        try:
            data_fim = datetime.strptime(data_fim_filter, '%Y-%m-%d').date()
            avaliacoes_query = avaliacoes_query.filter(data_fim__lte=data_fim)
        except ValueError:
            pass
    
    # Dados básicos
    avaliacoes = avaliacoes_query
    total_avaliacoes = avaliacoes.count()
    avaliacoes_pendentes = avaliacoes.filter(status='PENDENTE').count()
    avaliacoes_concluidas = avaliacoes.filter(status='CONCLUIDO').count()
    avaliacoes_canceladas = avaliacoes.filter(status='CANCELADO').count()
    
    # Estatísticas por departamento
    avaliacoes_por_departamento = avaliacoes.values(
        'funcionario__departamento__nome'
    ).annotate(
        total=Count('id'),
        concluidas=Count('id', filter=Q(status='CONCLUIDO')),
        pendentes=Count('id', filter=Q(status='PENDENTE'))
    ).order_by('-total')
    
    # Calcular percentuais e notas médias
    for dept in avaliacoes_por_departamento:
        if dept['total'] > 0:
            dept['percentual'] = (dept['total'] / total_avaliacoes) * 100
            dept['taxa_conclusao'] = (dept['concluidas'] / dept['total']) * 100
        else:
            dept['percentual'] = 0
            dept['taxa_conclusao'] = 0
    
    # Avaliações por funcionário
    avaliacoes_por_funcionario = avaliacoes.values(
        'funcionario__nome_completo',
        'funcionario__departamento__nome'
    ).annotate(
        total_avaliacoes=Count('id'),
        avaliacoes_concluidas=Count('id', filter=Q(status='CONCLUIDO')),
        nota_media=Avg('nota_geral')
    ).order_by('-nota_media')
    
    # Calcular taxa de conclusão por funcionário
    for func in avaliacoes_por_funcionario:
        if func['total_avaliacoes'] > 0:
            func['taxa_conclusao'] = (func['avaliacoes_concluidas'] / func['total_avaliacoes']) * 100
        else:
            func['taxa_conclusao'] = 0
    
    # Funcionários com melhores notas
    melhores_funcionarios = avaliacoes.filter(status='CONCLUIDO').order_by('-nota_geral')[:10]
    
    # Funcionários com piores notas
    piores_funcionarios = avaliacoes.filter(status='CONCLUIDO').order_by('nota_geral')[:10]
    
    # Estatísticas de critérios
    criterios_stats = CriterioAvaliado.objects.values(
        'criterio__nome'
    ).annotate(
        total_avaliacoes=Count('id'),
        nota_media=Avg('nota')
    ).order_by('-nota_media')
    
    # Estatísticas gerais
    nota_media_geral = avaliacoes.filter(status='CONCLUIDO').aggregate(media=Avg('nota_geral'))['media'] or 0
    nota_maior = avaliacoes.filter(status='CONCLUIDO').order_by('-nota_geral').first()
    nota_menor = avaliacoes.filter(status='CONCLUIDO').order_by('nota_geral').first()
    
    # Calcular taxa geral de conclusão
    if total_avaliacoes > 0:
        taxa_conclusao_geral = (avaliacoes_concluidas / total_avaliacoes) * 100
    else:
        taxa_conclusao_geral = 0
    
    # Dados para filtros
    departamentos = Departamento.objects.all().order_by('nome')
    
    context = {
        'avaliacoes': avaliacoes,
        'total_avaliacoes': total_avaliacoes,
        'avaliacoes_pendentes': avaliacoes_pendentes,
        'avaliacoes_concluidas': avaliacoes_concluidas,
        'avaliacoes_canceladas': avaliacoes_canceladas,
        'avaliacoes_por_departamento': avaliacoes_por_departamento,
        'avaliacoes_por_funcionario': avaliacoes_por_funcionario,
        'melhores_funcionarios': melhores_funcionarios,
        'piores_funcionarios': piores_funcionarios,
        'criterios_stats': criterios_stats,
        'nota_media_geral': nota_media_geral,
        'nota_maior': nota_maior,
        'nota_menor': nota_menor,
        'taxa_conclusao_geral': taxa_conclusao_geral,
        'filtros': {
            'status': status_filter,
            'data_inicio': data_inicio_filter,
            'data_fim': data_fim_filter,
        },
        'data_relatorio': timezone.now(),
    }
    
    return render(request, 'rh/relatorios/avaliacoes_documento.html', context)

@login_required
def relatorio_feriados_documento(request):
    """Gera relatório completo de feriados"""
    # Filtros
    ano = request.GET.get('ano')
    tipo = request.GET.get('tipo')
    status = request.GET.get('status')
    
    # Query base
    feriados = Feriado.objects.all().order_by('data')
    
    # Aplicar filtros
    if ano:
        feriados = feriados.filter(data__year=ano)
    if tipo:
        feriados = feriados.filter(tipo=tipo)
    if status:
        feriados = feriados.filter(ativo=status == 'ativo')
    
    # Estatísticas gerais
    total_feriados = feriados.count()
    feriados_ativos = feriados.filter(ativo=True).count()
    feriados_inativos = feriados.filter(ativo=False).count()
    
    # Estatísticas por tipo
    feriados_por_tipo = feriados.values('tipo').annotate(
        total=Count('id')
    ).order_by('-total')
    
    # Estatísticas por ano
    feriados_por_ano = feriados.values('data__year').annotate(
        total=Count('id')
    ).order_by('data__year')
    
    # Feriados próximos (próximos 30 dias)
    from datetime import date, timedelta
    hoje = date.today()
    proximos_30_dias = hoje + timedelta(days=30)
    feriados_proximos = feriados.filter(
        data__gte=hoje,
        data__lte=proximos_30_dias,
        ativo=True
    ).order_by('data')
    
    # Feriados por mês (ano atual)
    ano_atual = date.today().year
    feriados_por_mes = feriados.filter(
        data__year=ano_atual,
        ativo=True
    ).extra(
        select={'mes': 'EXTRACT(month FROM data)'}
    ).values('mes').annotate(
        total=Count('id')
    ).order_by('mes')
    
    # Contexto
    context = {
        'feriados': feriados,
        'total_feriados': total_feriados,
        'feriados_ativos': feriados_ativos,
        'feriados_inativos': feriados_inativos,
        'feriados_por_tipo': feriados_por_tipo,
        'feriados_por_ano': feriados_por_ano,
        'feriados_proximos': feriados_proximos,
        'feriados_por_mes': feriados_por_mes,
        'filtros': {
            'ano': ano,
            'tipo': tipo,
            'status': status,
        },
        'data_relatorio': timezone.now(),
    }
    
    return render(request, 'rh/relatorios/feriados_documento.html', context)

@login_required
def relatorio_feriados_pdf(request):
    """Gera PDF do relatório de feriados"""
    from django.template.loader import render_to_string
    
    # Reutilizar a mesma lógica do documento
    from django.template.response import TemplateResponse
    
    # Criar uma resposta temporária para obter o contexto
    temp_response = relatorio_feriados_documento(request)
    if hasattr(temp_response, 'context_data'):
        context = temp_response.context_data
    else:
        # Se não tem context_data, criar o contexto manualmente
        ano = request.GET.get('ano')
        tipo = request.GET.get('tipo')
        status = request.GET.get('status')
        
        # Query base
        feriados = Feriado.objects.all().order_by('data')
        
        # Aplicar filtros
        if ano:
            feriados = feriados.filter(data__year=ano)
        if tipo:
            feriados = feriados.filter(tipo=tipo)
        if status:
            feriados = feriados.filter(ativo=status == 'ativo')
        
        # Estatísticas gerais
        total_feriados = feriados.count()
        feriados_ativos = feriados.filter(ativo=True).count()
        feriados_inativos = feriados.filter(ativo=False).count()
        
        # Estatísticas por tipo
        feriados_por_tipo = feriados.values('tipo').annotate(
            total=Count('id')
        ).order_by('-total')
        
        # Estatísticas por ano
        feriados_por_ano = feriados.values('data__year').annotate(
            total=Count('id')
        ).order_by('data__year')
        
        # Feriados próximos (próximos 30 dias)
        from datetime import date, timedelta
        hoje = date.today()
        proximos_30_dias = hoje + timedelta(days=30)
        feriados_proximos = feriados.filter(
            data__gte=hoje,
            data__lte=proximos_30_dias,
            ativo=True
        ).order_by('data')
        
        # Feriados por mês (ano atual)
        ano_atual = date.today().year
        feriados_por_mes = feriados.filter(
            data__year=ano_atual,
            ativo=True
        ).extra(
            select={'mes': 'EXTRACT(month FROM data)'}
        ).values('mes').annotate(
            total=Count('id')
        ).order_by('mes')
        
        # Contexto
        context = {
            'feriados': feriados,
            'total_feriados': total_feriados,
            'feriados_ativos': feriados_ativos,
            'feriados_inativos': feriados_inativos,
            'feriados_por_tipo': feriados_por_tipo,
            'feriados_por_ano': feriados_por_ano,
            'feriados_proximos': feriados_proximos,
            'feriados_por_mes': feriados_por_mes,
            'filtros': {
                'ano': ano,
                'tipo': tipo,
                'status': status,
            },
            'data_relatorio': timezone.now(),
        }
    
    html_string = render_to_string('rh/relatorios/feriados_documento.html', context, request=request)
    filename = f"relatorio_feriados_{timezone.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    return render_pdf_from_html_string(request, html_string, filename)

@login_required
def relatorio_horas_extras_documento(request):
    """Relatório de Horas Extras - Documento Completo"""
    from django.db.models import Count, Q, Sum, Avg
    from django.utils import timezone
    from datetime import datetime, timedelta
    
    # Filtros opcionais
    funcionario_id = request.GET.get('funcionario')
    departamento_id = request.GET.get('departamento')
    tipo_filter = request.GET.get('tipo')
    data_inicio_filter = request.GET.get('data_inicio')
    data_fim_filter = request.GET.get('data_fim')
    
    # Período padrão: últimos 30 dias
    data_fim = timezone.now().date()
    data_inicio = data_fim - timedelta(days=30)
    
    # Permitir filtros via GET
    if data_inicio_filter:
        try:
            data_inicio = datetime.strptime(data_inicio_filter, '%Y-%m-%d').date()
        except ValueError:
            pass
    
    if data_fim_filter:
        try:
            data_fim = datetime.strptime(data_fim_filter, '%Y-%m-%d').date()
        except ValueError:
            pass
    
    # Query base
    horas_extras_query = HorasExtras.objects.filter(
        data__range=[data_inicio, data_fim]
    ).select_related('funcionario', 'funcionario__departamento', 'criado_por')
    
    # Aplicar filtros
    if funcionario_id:
        horas_extras_query = horas_extras_query.filter(funcionario_id=funcionario_id)
    
    if departamento_id:
        horas_extras_query = horas_extras_query.filter(funcionario__departamento_id=departamento_id)
    
    if tipo_filter:
        horas_extras_query = horas_extras_query.filter(tipo=tipo_filter)
    
    # Dados básicos
    horas_extras = horas_extras_query
    total_registros = horas_extras.count()
    
    # Estatísticas por tipo
    horas_por_tipo = horas_extras.values('tipo').annotate(
        total_registros=Count('id'),
        total_horas=Sum('quantidade_horas'),
        valor_total=Sum('valor_total')
    ).order_by('-total_horas')
    
    # Calcular percentuais
    total_horas_geral = sum([item['total_horas'] or 0 for item in horas_por_tipo])
    total_valor_geral = sum([item['valor_total'] or 0 for item in horas_por_tipo])
    
    for tipo in horas_por_tipo:
        if total_horas_geral > 0:
            tipo['percentual_horas'] = ((tipo['total_horas'] or 0) / total_horas_geral) * 100
        else:
            tipo['percentual_horas'] = 0
        
        if total_valor_geral > 0:
            tipo['percentual_valor'] = ((tipo['valor_total'] or 0) / total_valor_geral) * 100
        else:
            tipo['percentual_valor'] = 0
    
    # Estatísticas por funcionário
    horas_por_funcionario = horas_extras.values(
        'funcionario__nome_completo',
        'funcionario__departamento__nome'
    ).annotate(
        total_registros=Count('id'),
        total_horas=Sum('quantidade_horas'),
        valor_total=Sum('valor_total')
    ).order_by('-total_horas')
    
    # Estatísticas por departamento
    horas_por_departamento = horas_extras.values(
        'funcionario__departamento__nome'
    ).annotate(
        total_registros=Count('id'),
        total_horas=Sum('quantidade_horas'),
        valor_total=Sum('valor_total'),
        funcionarios_distintos=Count('funcionario', distinct=True)
    ).order_by('-total_horas')
    
    # Calcular médias por departamento
    for dept in horas_por_departamento:
        if dept['funcionarios_distintos'] > 0:
            dept['media_horas_por_funcionario'] = (dept['total_horas'] or 0) / dept['funcionarios_distintos']
            dept['media_valor_por_funcionario'] = (dept['valor_total'] or 0) / dept['funcionarios_distintos']
        else:
            dept['media_horas_por_funcionario'] = 0
            dept['media_valor_por_funcionario'] = 0
    
    # Funcionários com mais horas extras
    funcionarios_mais_horas = horas_por_funcionario[:10]
    
    # Estatísticas gerais
    total_horas_extras = horas_extras.aggregate(total=Sum('quantidade_horas'))['total'] or 0
    total_valor_horas_extras = horas_extras.aggregate(total=Sum('valor_total'))['total'] or 0
    media_horas_por_registro = horas_extras.aggregate(media=Avg('quantidade_horas'))['media'] or 0
    media_valor_por_registro = horas_extras.aggregate(media=Avg('valor_total'))['media'] or 0
    
    # Funcionários únicos que fizeram horas extras
    funcionarios_unicos = horas_extras.values('funcionario').distinct().count()
    
    # Dados para filtros
    funcionarios = Funcionario.objects.filter(status='AT').order_by('nome_completo')
    departamentos = Departamento.objects.all().order_by('nome')
    
    context = {
        'horas_extras': horas_extras,
        'total_registros': total_registros,
        'horas_por_tipo': horas_por_tipo,
        'horas_por_funcionario': horas_por_funcionario,
        'horas_por_departamento': horas_por_departamento,
        'funcionarios_mais_horas': funcionarios_mais_horas,
        'total_horas_extras': total_horas_extras,
        'total_valor_horas_extras': total_valor_horas_extras,
        'media_horas_por_registro': media_horas_por_registro,
        'media_valor_por_registro': media_valor_por_registro,
        'funcionarios_unicos': funcionarios_unicos,
        'funcionarios': funcionarios,
        'departamentos': departamentos,
        'filtros': {
            'funcionario': funcionario_id,
            'departamento': departamento_id,
            'tipo': tipo_filter,
        },
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'data_relatorio': timezone.now(),
    }
    
    return render(request, 'rh/relatorios/horas_extras_documento.html', context)

@login_required
def relatorio_funcionarios_pdf(request):
    """Exportar Relatório de Funcionários para PDF"""
    
    # Reutilizar a lógica da view de documento
    departamento_id = request.GET.get('departamento')
    status_filter = request.GET.get('status')
    data_admissao_inicio = request.GET.get('data_admissao_inicio')
    data_admissao_fim = request.GET.get('data_admissao_fim')
    
    # Query base
    funcionarios_query = Funcionario.objects.select_related('departamento', 'sucursal', 'cargo').order_by('nome_completo')
    
    # Aplicar filtros
    if departamento_id:
        funcionarios_query = funcionarios_query.filter(departamento_id=departamento_id)
    
    if status_filter:
        funcionarios_query = funcionarios_query.filter(status=status_filter)
    
    if data_admissao_inicio:
        try:
            data_inicio = datetime.strptime(data_admissao_inicio, '%Y-%m-%d').date()
            funcionarios_query = funcionarios_query.filter(data_admissao__gte=data_inicio)
        except ValueError:
            pass
    
    if data_admissao_fim:
        try:
            data_fim = datetime.strptime(data_admissao_fim, '%Y-%m-%d').date()
            funcionarios_query = funcionarios_query.filter(data_admissao__lte=data_fim)
        except ValueError:
            pass
    
    # Dados básicos
    funcionarios = funcionarios_query
    total_funcionarios = funcionarios.count()
    funcionarios_ativos = funcionarios.filter(status='AT').count()
    funcionarios_inativos = funcionarios.filter(status='IN').count()
    
    # Estatísticas por departamento
    funcionarios_por_departamento = funcionarios.values('departamento__nome').annotate(
        total=Count('id')
    ).order_by('-total')
    
    # Estatísticas por cargo
    funcionarios_por_cargo = funcionarios.values('cargo__nome').annotate(
        total=Count('id')
    ).order_by('-total')
    
    # Estatísticas por sucursal
    funcionarios_por_sucursal = funcionarios.values('sucursal__nome').annotate(
        total=Count('id')
    ).order_by('-total')
    
    total_sucursais = funcionarios.values('sucursal').distinct().count()
    
    # Renderizar HTML original com os filtros para PDF idêntico
    # Renderizar o mesmo template que a página de documento
    context = {
        'funcionarios': funcionarios,
        'total_funcionarios': total_funcionarios,
        'funcionarios_ativos': funcionarios_ativos,
        'funcionarios_inativos': funcionarios_inativos,
        'funcionarios_por_departamento': funcionarios_por_departamento,
        'funcionarios_por_cargo': funcionarios_por_cargo,
        'funcionarios_por_sucursal': funcionarios_por_sucursal,
        'total_sucursais': total_sucursais,
        'departamentos': Departamento.objects.all().order_by('nome'),
        'filtros': {
            'departamento': departamento_id,
            'status': status_filter,
            'data_admissao_inicio': data_admissao_inicio,
            'data_admissao_fim': data_admissao_fim,
        },
        'data_relatorio': timezone.now(),
    }
    from django.template.loader import render_to_string
    html_string = render_to_string('rh/relatorios/funcionarios_documento.html', context, request=request)
    filename = f'relatorio_funcionarios_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
    return render_pdf_from_html_string(request, html_string, filename)

@login_required
def relatorio_presencas_pdf(request):
    """Exportar Relatório de Presenças para PDF"""
    from django.template.loader import render_to_string
    
    # Reutilizar a lógica da view de documento
    funcionario_id = request.GET.get('funcionario')
    departamento_id = request.GET.get('departamento')
    data_inicio_filter = request.GET.get('data_inicio')
    data_fim_filter = request.GET.get('data_fim')
    
    # Query base
    presencas_query = Presenca.objects.select_related('funcionario', 'funcionario__departamento', 'tipo_presenca').order_by('-data')
    
    # Aplicar filtros
    if funcionario_id:
        presencas_query = presencas_query.filter(funcionario_id=funcionario_id)
    
    if departamento_id:
        presencas_query = presencas_query.filter(funcionario__departamento_id=departamento_id)
    
    if data_inicio_filter:
        try:
            data_inicio = datetime.strptime(data_inicio_filter, '%Y-%m-%d').date()
            presencas_query = presencas_query.filter(data__gte=data_inicio)
        except ValueError:
            pass
    
    if data_fim_filter:
        try:
            data_fim = datetime.strptime(data_fim_filter, '%Y-%m-%d').date()
            presencas_query = presencas_query.filter(data__lte=data_fim)
        except ValueError:
            pass
    
    # Dados básicos
    presencas = presencas_query
    total_presencas = presencas.count()
    presencas_presentes = presencas.filter(tipo_presenca__nome__icontains='presente').count()
    presencas_ausentes = presencas.filter(tipo_presenca__nome__icontains='ausente').count()
    
    # Estatísticas por departamento
    presencas_por_departamento = presencas.values('funcionario__departamento__nome').annotate(
        total=Count('id'),
        presentes=Count('id', filter=Q(tipo_presenca__nome__icontains='presente')),
        ausentes=Count('id', filter=Q(tipo_presenca__nome__icontains='ausente'))
    ).order_by('-total')
    
    # Dados para filtros
    funcionarios = Funcionario.objects.filter(status='AT').order_by('nome_completo')
    departamentos = Departamento.objects.all().order_by('nome')
    
    context = {
        'presencas': presencas,
        'total_presencas': total_presencas,
        'presencas_presentes': presencas_presentes,
        'presencas_ausentes': presencas_ausentes,
        'presencas_por_departamento': presencas_por_departamento,
        'funcionarios': funcionarios,
        'departamentos': departamentos,
        'filtros': {
            'funcionario': funcionario_id,
            'departamento': departamento_id,
            'data_inicio': data_inicio_filter,
            'data_fim': data_fim_filter,
        },
        'data_relatorio': timezone.now(),
    }
    
    # Renderização HTML idêntica
    from django.template.loader import render_to_string
    html_string = render_to_string('rh/relatorios/presencas_documento.html', context, request=request)
    filename = f'relatorio_presencas_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
    return render_pdf_from_html_string(request, html_string, filename)

@login_required
def relatorio_salarios_pdf(request):
    """Exportar Relatório de Salários para PDF"""
    from django.template.loader import render_to_string
    
    # Reutilizar a lógica da view de documento
    departamento_id = request.GET.get('departamento')
    mes_referencia_filter = request.GET.get('mes_referencia')
    
    # Query base
    folhas_query = FolhaSalarial.objects.select_related().order_by('-mes_referencia')
    
    # Aplicar filtros
    if departamento_id:
        folhas_query = folhas_query.filter(funcionarios__funcionario__departamento_id=departamento_id).distinct()
    
    if mes_referencia_filter:
        try:
            mes_referencia = datetime.strptime(mes_referencia_filter, '%Y-%m').date()
            folhas_query = folhas_query.filter(mes_referencia=mes_referencia)
        except ValueError:
            pass
    
    # Dados básicos
    folhas = folhas_query
    total_folhas = folhas.count()
    folhas_calculadas = folhas.filter(status='CALCULADA').count()
    folhas_fechadas = folhas.filter(status='FECHADA').count()
    
    # Estatísticas gerais
    from meuprojeto.empresa.models_rh import BeneficioFolha
    total_funcionarios_folha = FuncionarioFolha.objects.count()
    valor_total_bruto = folhas.aggregate(total=Sum('total_bruto'))['total'] or 0
    valor_total_liquido = folhas.aggregate(total=Sum('total_liquido'))['total'] or 0
    valor_total_descontos = folhas.aggregate(total=Sum('total_descontos'))['total'] or 0
    total_beneficios = BeneficioFolha.objects.aggregate(total=Sum('valor'))['total'] or 0
    
    # Salários por departamento
    salarios_por_departamento = FuncionarioFolha.objects.values(
        'funcionario__departamento__nome'
    ).annotate(
        total_funcionarios=Count('id'),
        salario_total=Sum('salario_liquido'),
        salario_medio=Sum('salario_liquido') / Count('id')
    ).order_by('-salario_total')
    
    # Funcionários com maiores e menores salários
    funcionarios_maiores_salarios = FuncionarioFolha.objects.select_related('funcionario').order_by('-salario_liquido')[:5]
    funcionarios_menores_salarios = FuncionarioFolha.objects.select_related('funcionario').order_by('salario_liquido')[:5]
    
    # Dados para filtros
    departamentos = Departamento.objects.all().order_by('nome')
    
    context = {
        'folhas': folhas,
        'total_folhas': total_folhas,
        'folhas_calculadas': folhas_calculadas,
        'folhas_fechadas': folhas_fechadas,
        'total_funcionarios_folha': total_funcionarios_folha,
        'valor_total_bruto': valor_total_bruto,
        'valor_total_liquido': valor_total_liquido,
        'valor_total_descontos': valor_total_descontos,
        'total_beneficios': total_beneficios,
        'salarios_por_departamento': salarios_por_departamento,
        'funcionarios_maiores_salarios': funcionarios_maiores_salarios,
        'funcionarios_menores_salarios': funcionarios_menores_salarios,
        'departamentos': departamentos,
        'filtros': {
            'departamento': departamento_id,
            'mes_referencia': mes_referencia_filter,
        },
        'data_relatorio': timezone.now(),
    }
    
    # Preparar dados e gerar PDF
    pdf_data = {
        'Estatísticas Gerais': [
            f'Total Folhas: {total_folhas}',
            f'Calculadas: {folhas_calculadas}',
            f'Fechadas: {folhas_fechadas}',
            f'Funcionários em Folhas: {total_funcionarios_folha}',
            f'Total Bruto: {valor_total_bruto}',
            f'Total Líquido: {valor_total_liquido}',
            f'Total Descontos: {valor_total_descontos}',
            f'Total Benefícios: {total_beneficios}',
        ],
        'Salários por Departamento': [
            {
                'Departamento': d['funcionario__departamento__nome'] or '-',
                'Funcionários': d['total_funcionarios'],
                'Total': d['salario_total'],
            } for d in salarios_por_departamento
        ],
    }
    from django.template.loader import render_to_string
    html_string = render_to_string('rh/relatorios/salarios_documento.html', context, request=request)
    filename = f'relatorio_salarios_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
    return render_pdf_from_html_string(request, html_string, filename)

@login_required
def relatorio_treinamentos_pdf(request):
    """Exportar Relatório de Treinamentos para PDF"""
    from django.template.loader import render_to_string
    
    # Reutilizar a lógica da view de documento
    tipo_filter = request.GET.get('tipo')
    status_filter = request.GET.get('status')
    data_inicio_filter = request.GET.get('data_inicio')
    data_fim_filter = request.GET.get('data_fim')
    
    # Query base
    treinamentos_query = Treinamento.objects.select_related().order_by('-data_inicio')
    
    # Aplicar filtros
    if tipo_filter:
        treinamentos_query = treinamentos_query.filter(tipo=tipo_filter)
    
    if status_filter:
        treinamentos_query = treinamentos_query.filter(status=status_filter)
    
    if data_inicio_filter:
        try:
            data_inicio = datetime.strptime(data_inicio_filter, '%Y-%m-%d').date()
            treinamentos_query = treinamentos_query.filter(data_inicio__gte=data_inicio)
        except ValueError:
            pass
    
    if data_fim_filter:
        try:
            data_fim = datetime.strptime(data_fim_filter, '%Y-%m-%d').date()
            treinamentos_query = treinamentos_query.filter(data_fim__lte=data_fim)
        except ValueError:
            pass
    
    # Dados básicos
    treinamentos = treinamentos_query
    total_treinamentos = treinamentos.count()
    treinamentos_ativos = treinamentos.filter(status='EM_ANDAMENTO').count()
    treinamentos_concluidos = treinamentos.filter(status='CONCLUIDO').count()
    treinamentos_cancelados = treinamentos.filter(status='CANCELADO').count()
    
    # Estatísticas por tipo
    treinamentos_por_tipo = treinamentos.values('tipo').annotate(
        total=Count('id')
    ).order_by('-total')
    
    # Inscrições por treinamento
    inscricoes_por_treinamento = treinamentos.annotate(
        total_inscricoes=Count('inscricoes'),
        inscricoes_concluidas=Count('inscricoes', filter=Q(inscricoes__status='CONCLUIDO'))
    ).order_by('-total_inscricoes')[:10]
    
    # Funcionários mais treinados
    funcionarios_mais_treinados = InscricaoTreinamento.objects.values(
        'funcionario__nome_completo'
    ).annotate(
        total_inscricoes=Count('id'),
        treinamentos_concluidos=Count('id', filter=Q(status='CONCLUIDO'))
    ).order_by('-total_inscricoes')[:10]
    
    # Estatísticas de inscrições
    total_inscricoes = InscricaoTreinamento.objects.count()
    inscricoes_concluidas = InscricaoTreinamento.objects.filter(status='CONCLUIDO').count()
    inscricoes_ativas = InscricaoTreinamento.objects.filter(status='ATIVO').count()
    
    # Calcular taxa de conclusão geral
    if total_inscricoes > 0:
        taxa_conclusao_geral = (inscricoes_concluidas / total_inscricoes) * 100
    else:
        taxa_conclusao_geral = 0
    
    context = {
        'treinamentos': treinamentos,
        'total_treinamentos': total_treinamentos,
        'treinamentos_ativos': treinamentos_ativos,
        'treinamentos_concluidos': treinamentos_concluidos,
        'treinamentos_cancelados': treinamentos_cancelados,
        'treinamentos_por_tipo': treinamentos_por_tipo,
        'inscricoes_por_treinamento': inscricoes_por_treinamento,
        'funcionarios_mais_treinados': funcionarios_mais_treinados,
        'total_inscricoes': total_inscricoes,
        'inscricoes_concluidas': inscricoes_concluidas,
        'inscricoes_ativas': inscricoes_ativas,
        'taxa_conclusao_geral': taxa_conclusao_geral,
        'filtros': {
            'tipo': tipo_filter,
            'status': status_filter,
            'data_inicio': data_inicio_filter,
            'data_fim': data_fim_filter,
        },
        'data_relatorio': timezone.now(),
    }
    
    from django.template.loader import render_to_string
    html_string = render_to_string('rh/relatorios/treinamentos_documento.html', context, request=request)
    filename = f'relatorio_treinamentos_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
    return render_pdf_from_html_string(request, html_string, filename)

@login_required
def relatorio_avaliacoes_pdf(request):
    """Exportar Relatório de Avaliações para PDF"""
    from django.template.loader import render_to_string
    
    # Reutilizar a lógica da view de documento
    departamento_id = request.GET.get('departamento')
    status_filter = request.GET.get('status')
    data_inicio_filter = request.GET.get('data_inicio')
    data_fim_filter = request.GET.get('data_fim')
    
    # Query base
    avaliacoes_query = AvaliacaoDesempenho.objects.select_related('funcionario', 'funcionario__departamento').order_by('-data_inicio')
    
    # Aplicar filtros
    if departamento_id:
        avaliacoes_query = avaliacoes_query.filter(funcionario__departamento_id=departamento_id)
    
    if status_filter:
        avaliacoes_query = avaliacoes_query.filter(status=status_filter)
    
    if data_inicio_filter:
        try:
            data_inicio = datetime.strptime(data_inicio_filter, '%Y-%m-%d').date()
            avaliacoes_query = avaliacoes_query.filter(data_inicio__gte=data_inicio)
        except ValueError:
            pass
    
    if data_fim_filter:
        try:
            data_fim = datetime.strptime(data_fim_filter, '%Y-%m-%d').date()
            avaliacoes_query = avaliacoes_query.filter(data_fim__lte=data_fim)
        except ValueError:
            pass
    
    # Dados básicos
    avaliacoes = avaliacoes_query
    total_avaliacoes = avaliacoes.count()
    avaliacoes_pendentes = avaliacoes.filter(status='PENDENTE').count()
    avaliacoes_concluidas = avaliacoes.filter(status='CONCLUIDO').count()
    avaliacoes_canceladas = avaliacoes.filter(status='CANCELADO').count()
    
    # Estatísticas por departamento
    avaliacoes_por_departamento = avaliacoes.values('funcionario__departamento__nome').annotate(
        total=Count('id'),
        concluidas=Count('id', filter=Q(status='CONCLUIDO')),
        pendentes=Count('id', filter=Q(status='PENDENTE'))
    ).order_by('-total')
    
    # Avaliações por funcionário
    avaliacoes_por_funcionario = avaliacoes.values(
        'funcionario__nome_completo',
        'funcionario__departamento__nome'
    ).annotate(
        total_avaliacoes=Count('id'),
        avaliacoes_concluidas=Count('id', filter=Q(status='CONCLUIDO')),
        nota_media=Avg('nota_geral')
    ).order_by('-nota_media')
    
    # Calcular taxa de conclusão por funcionário
    for func in avaliacoes_por_funcionario:
        if func['total_avaliacoes'] > 0:
            func['taxa_conclusao'] = (func['avaliacoes_concluidas'] / func['total_avaliacoes']) * 100
        else:
            func['taxa_conclusao'] = 0
    
    # Funcionários com melhores notas
    melhores_funcionarios = avaliacoes.filter(status='CONCLUIDO').order_by('-nota_geral')[:10]
    
    # Funcionários com piores notas
    piores_funcionarios = avaliacoes.filter(status='CONCLUIDO').order_by('nota_geral')[:10]
    
    # Estatísticas de critérios
    criterios_stats = CriterioAvaliado.objects.values('criterio__nome').annotate(
        total_avaliacoes=Count('id'),
        nota_media=Avg('nota')
    ).order_by('-nota_media')
    
    # Estatísticas gerais
    nota_media_geral = avaliacoes.filter(status='CONCLUIDO').aggregate(media=Avg('nota_geral'))['media'] or 0
    nota_maior = avaliacoes.filter(status='CONCLUIDO').order_by('-nota_geral').first()
    nota_menor = avaliacoes.filter(status='CONCLUIDO').order_by('nota_geral').first()
    
    # Calcular taxa geral de conclusão
    if total_avaliacoes > 0:
        taxa_conclusao_geral = (avaliacoes_concluidas / total_avaliacoes) * 100
    else:
        taxa_conclusao_geral = 0
    
    # Dados para filtros
    departamentos = Departamento.objects.all().order_by('nome')
    
    context = {
        'avaliacoes': avaliacoes,
        'total_avaliacoes': total_avaliacoes,
        'avaliacoes_pendentes': avaliacoes_pendentes,
        'avaliacoes_concluidas': avaliacoes_concluidas,
        'avaliacoes_canceladas': avaliacoes_canceladas,
        'avaliacoes_por_departamento': avaliacoes_por_departamento,
        'avaliacoes_por_funcionario': avaliacoes_por_funcionario,
        'melhores_funcionarios': melhores_funcionarios,
        'piores_funcionarios': piores_funcionarios,
        'criterios_stats': criterios_stats,
        'nota_media_geral': nota_media_geral,
        'nota_maior': nota_maior,
        'nota_menor': nota_menor,
        'taxa_conclusao_geral': taxa_conclusao_geral,
        'departamentos': departamentos,
        'filtros': {
            'status': status_filter,
            'data_inicio': data_inicio_filter,
            'data_fim': data_fim_filter,
        },
        'data_relatorio': timezone.now(),
    }
    
    from django.template.loader import render_to_string
    html_string = render_to_string('rh/relatorios/avaliacoes_documento.html', context, request=request)
    filename = f'relatorio_avaliacoes_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
    return render_pdf_from_html_string(request, html_string, filename)

@login_required
def relatorio_horas_extras_pdf(request):
    """Exportar Relatório de Horas Extras para PDF"""
    from django.template.loader import render_to_string
    
    # Reutilizar a lógica da view de documento
    funcionario_id = request.GET.get('funcionario')
    departamento_id = request.GET.get('departamento')
    tipo_filter = request.GET.get('tipo')
    data_inicio_filter = request.GET.get('data_inicio')
    data_fim_filter = request.GET.get('data_fim')
    
    # Query base
    horas_extras_query = HorasExtras.objects.select_related('funcionario', 'funcionario__departamento').order_by('-data')
    
    # Aplicar filtros
    if funcionario_id:
        horas_extras_query = horas_extras_query.filter(funcionario_id=funcionario_id)
    
    if departamento_id:
        horas_extras_query = horas_extras_query.filter(funcionario__departamento_id=departamento_id)
    
    if tipo_filter:
        horas_extras_query = horas_extras_query.filter(tipo=tipo_filter)
    
    if data_inicio_filter:
        try:
            data_inicio = datetime.strptime(data_inicio_filter, '%Y-%m-%d').date()
            horas_extras_query = horas_extras_query.filter(data__gte=data_inicio)
        except ValueError:
            pass
    
    if data_fim_filter:
        try:
            data_fim = datetime.strptime(data_fim_filter, '%Y-%m-%d').date()
            horas_extras_query = horas_extras_query.filter(data__lte=data_fim)
        except ValueError:
            pass
    
    # Dados básicos
    horas_extras = horas_extras_query
    total_registros = horas_extras.count()
    total_horas_extras = horas_extras.aggregate(total=Sum('quantidade_horas'))['total'] or 0
    total_valor_horas_extras = horas_extras.aggregate(total=Sum('valor_total'))['total'] or 0
    
    # Estatísticas por tipo
    horas_por_tipo = horas_extras.values('tipo').annotate(
        total_registros=Count('id'),
        total_horas=Sum('quantidade_horas'),
        total_valor=Sum('valor_total')
    ).order_by('-total_horas')
    
    # Estatísticas por funcionário
    horas_por_funcionario = horas_extras.values(
        'funcionario__nome_completo',
        'funcionario__departamento__nome'
    ).annotate(
        total_registros=Count('id'),
        total_horas=Sum('quantidade_horas'),
        total_valor=Sum('valor_total')
    ).order_by('-total_horas')[:10]
    
    # Estatísticas por departamento
    horas_por_departamento = horas_extras.values('funcionario__departamento__nome').annotate(
        total_registros=Count('id'),
        total_horas=Sum('quantidade_horas'),
        total_valor=Sum('valor_total')
    ).order_by('-total_horas')
    
    # Funcionários com mais horas extras
    funcionarios_mais_horas = horas_extras.values('funcionario__nome_completo').annotate(
        total_horas=Sum('quantidade_horas')
    ).order_by('-total_horas')[:10]
    
    # Estatísticas gerais
    media_horas_por_registro = total_horas_extras / total_registros if total_registros > 0 else 0
    media_valor_por_registro = total_valor_horas_extras / total_registros if total_registros > 0 else 0
    funcionarios_unicos = horas_extras.values('funcionario').distinct().count()
    
    # Dados para filtros
    funcionarios = Funcionario.objects.filter(status='AT').order_by('nome_completo')
    departamentos = Departamento.objects.all().order_by('nome')
    
    context = {
        'horas_extras': horas_extras,
        'total_registros': total_registros,
        'total_horas_extras': total_horas_extras,
        'total_valor_horas_extras': total_valor_horas_extras,
        'horas_por_tipo': horas_por_tipo,
        'horas_por_funcionario': horas_por_funcionario,
        'horas_por_departamento': horas_por_departamento,
        'funcionarios_mais_horas': funcionarios_mais_horas,
        'media_horas_por_registro': media_horas_por_registro,
        'media_valor_por_registro': media_valor_por_registro,
        'funcionarios_unicos': funcionarios_unicos,
        'funcionarios': funcionarios,
        'departamentos': departamentos,
        'filtros': {
            'funcionario': funcionario_id,
            'departamento': departamento_id,
            'tipo': tipo_filter,
            'data_inicio': data_inicio_filter,
            'data_fim': data_fim_filter,
        },
        'data_inicio': data_inicio_filter,
        'data_fim': data_fim_filter,
        'data_relatorio': timezone.now(),
    }
    
    from django.template.loader import render_to_string
    html_string = render_to_string('rh/relatorios/horas_extras_documento.html', context, request=request)
    filename = f'relatorio_horas_extras_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
    return render_pdf_from_html_string(request, html_string, filename)

@login_required
def relatorio_pdf(request):
    """Redireciona para o relatório/PDF seleccionado com filtros."""
    mapa_pdf = {
        'funcionarios': 'rh:relatorio_funcionarios_pdf',
        'presencas': 'rh:relatorio_presencas_pdf',
        'salarios': 'rh:relatorio_salarios_pdf',
        'treinamentos': 'rh:relatorio_treinamentos_pdf',
        'avaliacoes': 'rh:relatorio_avaliacoes_pdf',
        'horas_extras': 'rh:relatorio_horas_extras_pdf',
        'feriados': 'rh:relatorio_feriados_pdf',
        'geral': 'rh:relatorio_geral_rh_pdf',
        'custos': 'rh:relatorio_custos_rh_pdf',
    }
    mapa_doc = {
        'funcionarios': 'rh:relatorio_funcionarios_documento',
        'presencas': 'rh:relatorio_presencas_documento',
        'salarios': 'rh:relatorio_salarios_documento',
        'treinamentos': 'rh:relatorio_treinamentos_documento',
        'avaliacoes': 'rh:relatorio_avaliacoes_documento',
        'horas_extras': 'rh:relatorio_horas_extras_documento',
        'feriados': 'rh:relatorio_feriados_documento',
        'geral': 'rh:relatorio_geral_rh_documento',
        'custos': 'rh:relatorio_custos_rh_documento',
    }

    if request.method == 'POST':
        tipo_relatorio = request.POST.get('tipo_relatorio')
        formato = request.POST.get('formato', 'pdf')
        if not tipo_relatorio:
            messages.error(request, 'Seleccione o tipo de relatório.')
            return redirect('rh:relatorio_pdf')

        params = {}
        for key in ('data_inicio', 'data_fim', 'mes_referencia', 'departamento', 'sucursal'):
            val = request.POST.get(key)
            if val:
                params[key] = val

        destino = (mapa_pdf if formato == 'pdf' else mapa_doc).get(tipo_relatorio)
        if not destino:
            messages.error(request, 'Tipo de relatório inválido.')
            return redirect('rh:relatorio_pdf')

        url = reverse(destino)
        if params:
            url += '?' + urlencode(params)
        return redirect(url)

    sucursais = Sucursal.objects.filter(ativa=True).order_by('nome')
    context = {
        'sucursais': sucursais,
        'tipos_relatorio': [
            ('funcionarios', 'Relatório de Funcionários'),
            ('presencas', 'Relatório de Presenças'),
            ('salarios', 'Relatório de Salários'),
            ('treinamentos', 'Relatório de Treinamentos'),
            ('avaliacoes', 'Relatório de Avaliações'),
            ('horas_extras', 'Relatório de Horas Extras'),
            ('feriados', 'Relatório de Feriados'),
            ('geral', 'Relatório Geral de RH'),
            ('custos', 'Relatório de Custos de RH'),
        ],
    }
    return render(request, 'rh/relatorios/gerar.html', context)

@login_required
def relatorio_geral_rh_documento(request):
    from .services.rh_relatorios_service import montar_contexto_relatorio_geral_rh
    context = montar_contexto_relatorio_geral_rh(request.GET)
    return render(request, 'rh/relatorios/geral_rh_documento.html', context)

@login_required
def relatorio_geral_rh_pdf(request):
    from django.template.loader import render_to_string
    from .services.rh_relatorios_service import montar_contexto_relatorio_geral_rh
    context = montar_contexto_relatorio_geral_rh(request.GET)
    html_string = render_to_string('rh/relatorios/geral_rh_documento.html', context, request=request)
    filename = f'relatorio_geral_rh_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
    return render_pdf_from_html_string(request, html_string, filename)

@login_required
def relatorio_custos_rh_documento(request):
    from .services.rh_relatorios_service import montar_contexto_relatorio_custos_rh
    context = montar_contexto_relatorio_custos_rh(request.GET)
    return render(request, 'rh/relatorios/custos_rh_documento.html', context)

@login_required
def relatorio_custos_rh_pdf(request):
    from django.template.loader import render_to_string
    from .services.rh_relatorios_service import montar_contexto_relatorio_custos_rh
    context = montar_contexto_relatorio_custos_rh(request.GET)
    html_string = render_to_string('rh/relatorios/custos_rh_documento.html', context, request=request)
    filename = f'relatorio_custos_rh_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
    return render_pdf_from_html_string(request, html_string, filename)
