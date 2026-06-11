"""
Views para gerenciamento de exceções logísticas.
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Q, Count, Sum, Avg
from django.http import JsonResponse
from django.core.paginator import Paginator
from datetime import datetime, date, time, timedelta
import json
import logging

from .decorators import require_stock_access
from .models_exceptions import (
    TipoExcecao, ExcecaoLogistica, AcaoExcecao, DevolucaoLogistica, 
    Reentrega, ConfiguracaoExcecoes
)
from .models_stock import RastreamentoEntrega, EventoRastreamento
from .models_routing import PlanejamentoEntrega, Rota
from .services.exception_service import ExceptionService

logger = logging.getLogger(__name__)


# =============================================================================
# TIPOS DE EXCEÇÃO
# =============================================================================

@login_required
@require_stock_access
def tipos_excecao_list(request):
    """Lista de tipos de exceção."""
    search = request.GET.get('search', '')
    ativo = request.GET.get('ativo', '')
    
    tipos = TipoExcecao.objects.all()
    
    if search:
        tipos = tipos.filter(
            Q(codigo__icontains=search) |
            Q(nome__icontains=search) |
            Q(descricao__icontains=search)
        )
    
    if ativo:
        tipos = tipos.filter(ativo=ativo == 'true')
    
    tipos = tipos.order_by('nome')
    
    # Paginação
    paginator = Paginator(tipos, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'ativo': ativo,
    }
    
    return render(request, 'stock/logistica/exceptions/tipos_list.html', context)


# =============================================================================
# EXCEÇÕES LOGÍSTICAS
# =============================================================================

@login_required
@require_stock_access
def excecoes_list(request):
    """Lista de exceções logísticas."""
    search = request.GET.get('search', '').strip()
    status = request.GET.get('status', '').strip()
    prioridade = request.GET.get('prioridade', '').strip()
    tipo_codigo = request.GET.get('tipo_codigo', '').strip()
    data_inicio = request.GET.get('data_inicio', '').strip()
    data_fim = request.GET.get('data_fim', '').strip()

    excecoes = ExcecaoLogistica.objects.select_related(
        'tipo_excecao', 'rastreamento_entrega', 'reportado_por',
    )

    if search:
        excecoes = excecoes.filter(
            Q(codigo__icontains=search)
            | Q(descricao__icontains=search)
            | Q(local_ocorrencia__icontains=search)
            | Q(observacoes__icontains=search),
        )

    if status:
        excecoes = excecoes.filter(status=status)

    if prioridade:
        excecoes = excecoes.filter(prioridade=prioridade)

    if tipo_codigo:
        excecoes = excecoes.filter(tipo_excecao__codigo=tipo_codigo)

    if data_inicio:
        excecoes = excecoes.filter(data_ocorrencia__date__gte=data_inicio)

    if data_fim:
        excecoes = excecoes.filter(data_ocorrencia__date__lte=data_fim)

    excecoes = excecoes.order_by('-data_ocorrencia', 'prioridade')

    stats = {
        'total': excecoes.count(),
        'abertas': excecoes.filter(status='ABERTA').count(),
        'em_analise': excecoes.filter(status='EM_ANALISE').count(),
        'resolvidas': excecoes.filter(status='RESOLVIDA').count(),
    }

    context = {
        'page_obj': Paginator(excecoes, 20).get_page(request.GET.get('page')),
        'stats': stats,
        'search': search,
        'status': status,
        'prioridade': prioridade,
        'tipo_codigo': tipo_codigo,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'status_choices': ExcecaoLogistica.STATUS_CHOICES,
        'prioridade_choices': ExcecaoLogistica.PRIORIDADE_CHOICES,
        'tipos_excecao': TipoExcecao.objects.filter(ativo=True).order_by('nome'),
        'has_filters': bool(
            search or status or prioridade or tipo_codigo or data_inicio or data_fim,
        ),
    }

    return render(request, 'stock/logistica/exceptions/excecoes_list.html', context)


@login_required
@require_stock_access
def excecao_detail(request, excecao_id):
    """Detalhes de uma exceção logística."""
    excecao = get_object_or_404(ExcecaoLogistica, id=excecao_id)
    
    # Ações relacionadas
    acoes = excecao.acoes.all().order_by('-data_execucao')
    
    # Devoluções relacionadas
    devolucoes = excecao.devolucoes.all().order_by('-data_solicitacao')
    
    # Reentregas relacionadas
    reentregas = excecao.reentregas.all().order_by('-data_agendamento')
    
    context = {
        'excecao': excecao,
        'acoes': acoes,
        'devolucoes': devolucoes,
        'reentregas': reentregas,
    }
    
    return render(request, 'stock/logistica/exceptions/excecao_detail.html', context)


@login_required
@require_stock_access
def excecao_create(request):
    """Criar nova exceção logística."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            exception_service = ExceptionService()
            excecao = exception_service.criar_excecao(
                tipo_codigo=data.get('tipo_codigo', ''),
                rastreamento_id=data.get('rastreamento_id'),
                planejamento_id=data.get('planejamento_id'),
                rota_id=data.get('rota_id'),
                descricao=data.get('descricao', ''),
                observacoes=data.get('observacoes', ''),
                local_ocorrencia=data.get('local_ocorrencia', ''),
                latitude=data.get('latitude'),
                longitude=data.get('longitude'),
                prioridade=data.get('prioridade', 'NORMAL'),
                reportado_por_id=request.user.id,
                evidencia_fotos=data.get('evidencia_fotos', [])
            )
            
            return JsonResponse({
                'success': True,
                'excecao_id': excecao.id,
                'codigo': excecao.codigo
            })
            
        except Exception as e:
            logger.error(f"Erro ao criar exceção: {e}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    tipos_excecao = TipoExcecao.objects.filter(ativo=True).order_by('nome')
    rastreamentos = RastreamentoEntrega.objects.filter(
        status_atual__in=['PREPARANDO', 'COLETADO', 'EM_TRANSITO', 'EM_DISTRIBUICAO'],
    ).select_related('transportadora', 'veiculo_interno').order_by('-data_coleta')

    rastreamento_selecionado = request.GET.get('rastreamento_id', '').strip()

    context = {
        'tipos_excecao': tipos_excecao,
        'rastreamentos': rastreamentos,
        'prioridade_choices': ExcecaoLogistica.PRIORIDADE_CHOICES,
        'rastreamento_selecionado': rastreamento_selecionado,
    }

    return render(request, 'stock/logistica/exceptions/excecao_form.html', context)


@login_required
@require_stock_access
def adicionar_acao_excecao(request, excecao_id):
    """Adicionar ação para resolver exceção."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            exception_service = ExceptionService()
            acao = exception_service.adicionar_acao_excecao(
                excecao_id=excecao_id,
                tipo_acao=data.get('tipo_acao', ''),
                descricao=data.get('descricao', ''),
                executado_por_id=data.get('executado_por_id'),
                data_prevista_conclusao=datetime.strptime(
                    data.get('data_prevista_conclusao'), '%Y-%m-%d %H:%M'
                ) if data.get('data_prevista_conclusao') else None
            )
            
            return JsonResponse({
                'success': True,
                'acao_id': acao.id,
                'message': 'Ação adicionada com sucesso.'
            })
            
        except Exception as e:
            logger.error(f"Erro ao adicionar ação: {e}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    excecao = get_object_or_404(ExcecaoLogistica, id=excecao_id)
    
    context = {
        'excecao': excecao,
        'tipo_acao_choices': AcaoExcecao.TIPO_CHOICES,
    }
    
    return render(request, 'stock/logistica/exceptions/acao_form.html', context)


@login_required
@require_stock_access
def concluir_acao_excecao(request, acao_id):
    """Concluir ação de exceção."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            exception_service = ExceptionService()
            acao = exception_service.concluir_acao_excecao(
                acao_id=acao_id,
                resultado=data.get('resultado', ''),
                observacoes=data.get('observacoes', '')
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Ação concluída com sucesso.'
            })
            
        except Exception as e:
            logger.error(f"Erro ao concluir ação: {e}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    acao = get_object_or_404(AcaoExcecao, id=acao_id)
    
    context = {
        'acao': acao,
    }
    
    return render(request, 'stock/logistica/exceptions/concluir_acao_form.html', context)


# =============================================================================
# DEVOLUÇÕES LOGÍSTICAS
# =============================================================================

@login_required
@require_stock_access
def devolucoes_list(request):
    """Lista de devoluções logísticas."""
    search = request.GET.get('search', '').strip()
    status = request.GET.get('status', '').strip()
    motivo = request.GET.get('motivo', '').strip()
    data_inicio = request.GET.get('data_inicio', '').strip()
    data_fim = request.GET.get('data_fim', '').strip()

    devolucoes = DevolucaoLogistica.objects.select_related(
        'rastreamento_original', 'excecao_relacionada', 'aprovado_por',
    )

    if search:
        devolucoes = devolucoes.filter(
            Q(codigo__icontains=search)
            | Q(solicitado_por__icontains=search)
            | Q(descricao_motivo__icontains=search),
        )

    if status:
        devolucoes = devolucoes.filter(status=status)

    if motivo:
        devolucoes = devolucoes.filter(motivo=motivo)

    if data_inicio:
        devolucoes = devolucoes.filter(data_solicitacao__date__gte=data_inicio)

    if data_fim:
        devolucoes = devolucoes.filter(data_solicitacao__date__lte=data_fim)

    devolucoes = devolucoes.order_by('-data_solicitacao')

    stats = {
        'total': devolucoes.count(),
        'solicitadas': devolucoes.filter(status='SOLICITADA').count(),
        'em_processo': devolucoes.filter(
            status__in=['APROVADA', 'EM_COLETA', 'COLETADA', 'EM_TRANSITO'],
        ).count(),
        'recebidas': devolucoes.filter(status='RECEBIDA').count(),
    }

    context = {
        'page_obj': Paginator(devolucoes, 20).get_page(request.GET.get('page')),
        'stats': stats,
        'search': search,
        'status': status,
        'motivo': motivo,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'status_choices': DevolucaoLogistica.STATUS_CHOICES,
        'motivo_choices': DevolucaoLogistica.MOTIVO_CHOICES,
        'has_filters': bool(search or status or motivo or data_inicio or data_fim),
    }

    return render(request, 'stock/logistica/exceptions/devolucoes_list.html', context)


@login_required
@require_stock_access
def devolucao_create(request):
    """Criar nova devolução logística."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            exception_service = ExceptionService()
            devolucao = exception_service.criar_devolucao(
                rastreamento_id=data.get('rastreamento_id'),
                motivo=data.get('motivo', ''),
                descricao_motivo=data.get('descricao_motivo', ''),
                solicitado_por=data.get('solicitado_por', ''),
                contato_solicitante=data.get('contato_solicitante', ''),
                excecao_id=data.get('excecao_id'),
                observacoes=data.get('observacoes', ''),
                instrucoes_coleta=data.get('instrucoes_coleta', '')
            )
            
            return JsonResponse({
                'success': True,
                'devolucao_id': devolucao.id,
                'codigo': devolucao.codigo
            })
            
        except Exception as e:
            logger.error(f"Erro ao criar devolução: {e}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    rastreamentos = RastreamentoEntrega.objects.filter(
        status_atual__in=['ENTREGUE', 'DEVOLVIDO'],
    ).select_related('transportadora', 'veiculo_interno').order_by('-data_entrega_realizada')

    excecoes = ExcecaoLogistica.objects.filter(
        status__in=['ABERTA', 'EM_ANALISE'],
    ).select_related('tipo_excecao').order_by('-data_ocorrencia')

    context = {
        'rastreamentos': rastreamentos,
        'excecoes': excecoes,
        'motivo_choices': DevolucaoLogistica.MOTIVO_CHOICES,
        'rastreamento_selecionado': request.GET.get('rastreamento_id', '').strip(),
        'excecao_selecionada': request.GET.get('excecao_id', '').strip(),
    }

    return render(request, 'stock/logistica/exceptions/devolucao_form.html', context)


@login_required
@require_stock_access
def aprovar_devolucao(request, devolucao_id):
    """Aprovar devolução logística."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            exception_service = ExceptionService()
            devolucao = exception_service.aprovar_devolucao(
                devolucao_id=devolucao_id,
                aprovado_por_id=request.user.id,
                custo_devolucao=data.get('custo_devolucao')
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Devolução aprovada com sucesso.'
            })
            
        except Exception as e:
            logger.error(f"Erro ao aprovar devolução: {e}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    devolucao = get_object_or_404(DevolucaoLogistica, id=devolucao_id)
    
    context = {
        'devolucao': devolucao,
    }
    
    return render(request, 'stock/logistica/exceptions/aprovar_devolucao_form.html', context)


# =============================================================================
# REENTREGAS
# =============================================================================

@login_required
@require_stock_access
def reentregas_list(request):
    """Lista de reentregas."""
    search = request.GET.get('search', '').strip()
    status = request.GET.get('status', '').strip()
    data_inicio = request.GET.get('data_inicio', '').strip()
    data_fim = request.GET.get('data_fim', '').strip()

    reentregas = Reentrega.objects.select_related(
        'rastreamento_original', 'excecao_relacionada', 'agendado_por',
    )

    if search:
        reentregas = reentregas.filter(
            Q(codigo__icontains=search)
            | Q(motivo_tentativa_anterior__icontains=search)
            | Q(observacoes__icontains=search),
        )

    if status:
        reentregas = reentregas.filter(status=status)

    if data_inicio:
        reentregas = reentregas.filter(nova_data_entrega__gte=data_inicio)

    if data_fim:
        reentregas = reentregas.filter(nova_data_entrega__lte=data_fim)

    reentregas = reentregas.order_by('-data_agendamento')

    stats = {
        'total': reentregas.count(),
        'agendadas': reentregas.filter(status='AGENDADA').count(),
        'em_andamento': reentregas.filter(status='EM_ANDAMENTO').count(),
        'concluidas': reentregas.filter(status='CONCLUIDA').count(),
    }

    context = {
        'page_obj': Paginator(reentregas, 20).get_page(request.GET.get('page')),
        'stats': stats,
        'search': search,
        'status': status,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'status_choices': Reentrega.STATUS_CHOICES,
        'has_filters': bool(search or status or data_inicio or data_fim),
    }

    return render(request, 'stock/logistica/exceptions/reentregas_list.html', context)


@login_required
@require_stock_access
def reentrega_create(request):
    """Criar nova reentrega."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            exception_service = ExceptionService()
            reentrega = exception_service.criar_reentrega(
                rastreamento_id=data.get('rastreamento_id'),
                motivo_tentativa_anterior=data.get('motivo_tentativa_anterior', ''),
                nova_data_entrega=datetime.strptime(data.get('nova_data_entrega'), '%Y-%m-%d').date(),
                nova_janela_inicio=datetime.strptime(data.get('nova_janela_inicio'), '%H:%M').time(),
                nova_janela_fim=datetime.strptime(data.get('nova_janela_fim'), '%H:%M').time(),
                excecao_id=data.get('excecao_id'),
                agendado_por_id=request.user.id,
                observacoes=data.get('observacoes', ''),
                instrucoes_especiais=data.get('instrucoes_especiais', ''),
                custo_reentrega=data.get('custo_reentrega')
            )
            
            return JsonResponse({
                'success': True,
                'reentrega_id': reentrega.id,
                'codigo': reentrega.codigo
            })
            
        except Exception as e:
            logger.error(f"Erro ao criar reentrega: {e}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    rastreamentos = RastreamentoEntrega.objects.filter(
        status_atual__in=['EM_TRANSITO', 'EM_DISTRIBUICAO', 'DEVOLVIDO'],
    ).select_related('transportadora', 'veiculo_interno').order_by('-data_coleta')

    excecoes = ExcecaoLogistica.objects.filter(
        status__in=['ABERTA', 'EM_ANALISE'],
    ).select_related('tipo_excecao').order_by('-data_ocorrencia')

    context = {
        'rastreamentos': rastreamentos,
        'excecoes': excecoes,
        'data_padrao': timezone.now().date() + timedelta(days=1),
        'rastreamento_selecionado': request.GET.get('rastreamento_id', '').strip(),
        'excecao_selecionada': request.GET.get('excecao_id', '').strip(),
    }

    return render(request, 'stock/logistica/exceptions/reentrega_form.html', context)


# =============================================================================
# DASHBOARD DE EXCEÇÕES
# =============================================================================

@login_required
@require_stock_access
def dashboard_excecoes(request):
    """Dashboard de exceções logísticas."""
    hoje = timezone.now().date()
    limite_24h = timezone.now() - timedelta(days=1)

    exception_service = ExceptionService()
    stats = exception_service.obter_estatisticas_excecoes()

    excecoes_criticas_qs = exception_service.obter_excecoes_pendentes(
        prioridade='CRITICA',
        dias_atraso=1,
    )
    excecoes_criticas = excecoes_criticas_qs[:5]

    excecoes_recentes = ExcecaoLogistica.objects.filter(
        data_ocorrencia__gte=limite_24h,
    ).select_related('tipo_excecao').order_by('-data_ocorrencia')[:10]

    devolucoes_pendentes_qs = DevolucaoLogistica.objects.filter(
        status='SOLICITADA',
    ).order_by('-data_solicitacao')
    devolucoes_pendentes = devolucoes_pendentes_qs[:5]

    reentregas_agendadas_qs = Reentrega.objects.filter(
        status='AGENDADA',
        nova_data_entrega__gte=hoje,
    ).order_by('nova_data_entrega')
    reentregas_agendadas = reentregas_agendadas_qs[:5]

    context = {
        'stats': stats,
        'excecoes_criticas': excecoes_criticas,
        'total_excecoes_criticas': len(excecoes_criticas_qs),
        'excecoes_recentes': excecoes_recentes,
        'devolucoes_pendentes': devolucoes_pendentes,
        'total_devolucoes_pendentes': devolucoes_pendentes_qs.count(),
        'reentregas_agendadas': reentregas_agendadas,
        'total_reentregas_agendadas': reentregas_agendadas_qs.count(),
    }

    return render(request, 'stock/logistica/exceptions/dashboard.html', context)
