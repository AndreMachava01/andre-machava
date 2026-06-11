"""
Views para gerenciamento de escalabilidade logística.
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
from .models_scalability import (
    ControleIdempotencia, ValidacaoLogistica, ResultadoValidacao
)
from .models_stock import RastreamentoEntrega
from .services.scalability_service import ScalabilityService

logger = logging.getLogger(__name__)


# =============================================================================
# DASHBOARD DE ESCALABILIDADE
# =============================================================================

@login_required
@require_stock_access
def scalability_dashboard(request):
    """Dashboard de escalabilidade logística."""
    
    # Métricas de escalabilidade
    metricas = {
        'operacoes_idempotentes': ControleIdempotencia.objects.count(),
        'validacoes_ativas': ValidacaoLogistica.objects.filter(ativo=True).count(),
        'resultados_validacao': ResultadoValidacao.objects.count(),
        'operacoes_recentes': ControleIdempotencia.objects.filter(
            data_criacao__gte=timezone.now() - timedelta(days=7)
        ).count(),
    }
    
    # Operações recentes
    operacoes_recentes = ControleIdempotencia.objects.select_related(
        'usuario'
    ).order_by('-data_criacao')[:10]
    
    # Validações com problemas
    validacoes_problema = ResultadoValidacao.objects.filter(
        sucesso=False
    ).select_related('validacao').order_by('-data_validacao')[:5]
    
    context = {
        'metricas': metricas,
        'operacoes_recentes': operacoes_recentes,
        'validacoes_problema': validacoes_problema,
    }
    
    return render(request, 'stock/logistica/scalability/dashboard.html', context)


# =============================================================================
# CONTROLE DE IDEMPOTÊNCIA
# =============================================================================

@login_required
@require_stock_access
def idempotencia_list(request):
    """Lista de operações idempotentes."""
    search = request.GET.get('search', '')
    tipo_operacao = request.GET.get('tipo_operacao', '')
    status = request.GET.get('status', '')
    data_inicio = request.GET.get('data_inicio', '')
    data_fim = request.GET.get('data_fim', '')
    
    operacoes = ControleIdempotencia.objects.select_related('usuario')
    
    if search:
        operacoes = operacoes.filter(
            Q(chave_idempotencia__icontains=search) |
            Q(descricao__icontains=search) |
            Q(usuario__username__icontains=search)
        )
    
    if tipo_operacao:
        operacoes = operacoes.filter(tipo_operacao=tipo_operacao)
    
    if status:
        operacoes = operacoes.filter(status=status)
    
    if data_inicio:
        operacoes = operacoes.filter(data_criacao__date__gte=data_inicio)
    
    if data_fim:
        operacoes = operacoes.filter(data_criacao__date__lte=data_fim)
    
    operacoes = operacoes.order_by('-data_criacao')
    
    # Paginação
    paginator = Paginator(operacoes, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Opções para filtros
    tipo_choices = ControleIdempotencia.TIPO_OPERACAO_CHOICES
    status_choices = ControleIdempotencia.STATUS_CHOICES
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'tipo_operacao': tipo_operacao,
        'status': status,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'tipo_choices': tipo_choices,
        'status_choices': status_choices,
    }
    
    return render(request, 'stock/logistica/scalability/idempotencia_list.html', context)


@login_required
@require_stock_access
def idempotencia_detail(request, operacao_id):
    """Detalhes de uma operação idempotente."""
    operacao = get_object_or_404(ControleIdempotencia, id=operacao_id)
    
    context = {
        'operacao': operacao,
    }
    
    return render(request, 'stock/logistica/scalability/idempotencia_detail.html', context)


# =============================================================================
# VALIDAÇÕES LOGÍSTICAS
# =============================================================================

@login_required
@require_stock_access
def validacoes_list(request):
    """Lista de validações logísticas."""
    search = request.GET.get('search', '')
    tipo_validacao = request.GET.get('tipo_validacao', '')
    ativo = request.GET.get('ativo', '')
    
    validacoes = ValidacaoLogistica.objects.all()
    
    if search:
        validacoes = validacoes.filter(
            Q(nome__icontains=search) |
            Q(codigo__icontains=search) |
            Q(descricao__icontains=search)
        )
    
    if tipo_validacao:
        validacoes = validacoes.filter(tipo_validacao=tipo_validacao)
    
    if ativo:
        validacoes = validacoes.filter(ativo=ativo == 'true')
    
    validacoes = validacoes.order_by('nome')
    
    # Paginação
    paginator = Paginator(validacoes, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Opções para filtros
    tipo_choices = ValidacaoLogistica.TIPO_VALIDACAO_CHOICES
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'tipo_validacao': tipo_validacao,
        'ativo': ativo,
        'tipo_choices': tipo_choices,
    }
    
    return render(request, 'stock/logistica/scalability/validacoes_list.html', context)


@login_required
@require_stock_access
def validacao_detail(request, validacao_id):
    """Detalhes de uma validação logística."""
    validacao = get_object_or_404(ValidacaoLogistica, id=validacao_id)
    
    # Resultados recentes desta validação
    resultados_recentes = validacao.resultados.all().order_by('-data_validacao')[:10]
    
    # Estatísticas
    stats = {
        'total_validacoes': validacao.resultados.count(),
        'sucessos': validacao.resultados.filter(sucesso=True).count(),
        'falhas': validacao.resultados.filter(sucesso=False).count(),
        'taxa_sucesso': 0,
    }
    
    if stats['total_validacoes'] > 0:
        stats['taxa_sucesso'] = (stats['sucessos'] / stats['total_validacoes']) * 100
    
    context = {
        'validacao': validacao,
        'resultados_recentes': resultados_recentes,
        'stats': stats,
    }
    
    return render(request, 'stock/logistica/scalability/validacao_detail.html', context)


# =============================================================================
# RESULTADOS DE VALIDAÇÃO
# =============================================================================

@login_required
@require_stock_access
def resultados_validacao_list(request):
    """Lista de resultados de validação."""
    search = request.GET.get('search', '')
    validacao_id = request.GET.get('validacao_id', '')
    sucesso = request.GET.get('sucesso', '')
    data_inicio = request.GET.get('data_inicio', '')
    data_fim = request.GET.get('data_fim', '')
    
    resultados = ResultadoValidacao.objects.select_related(
        'validacao', 'usuario'
    )
    
    if search:
        resultados = resultados.filter(
            Q(validacao__nome__icontains=search) |
            Q(validacao__codigo__icontains=search) |
            Q(detalhes__icontains=search)
        )
    
    if validacao_id:
        resultados = resultados.filter(validacao_id=validacao_id)
    
    if sucesso:
        resultados = resultados.filter(sucesso=sucesso == 'true')
    
    if data_inicio:
        resultados = resultados.filter(data_validacao__date__gte=data_inicio)
    
    if data_fim:
        resultados = resultados.filter(data_validacao__date__lte=data_fim)
    
    resultados = resultados.order_by('-data_validacao')
    
    # Paginação
    paginator = Paginator(resultados, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Opções para filtros
    validacoes = ValidacaoLogistica.objects.filter(ativo=True).order_by('nome')
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'validacao_id': validacao_id,
        'sucesso': sucesso,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'validacoes': validacoes,
    }
    
    return render(request, 'stock/logistica/scalability/resultados_list.html', context)


# =============================================================================
# APIS PARA ESCALABILIDADE
# =============================================================================

@login_required
@require_stock_access
def api_validar_operacao(request):
    """API para validar operação antes de executar."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            scalability_service = ScalabilityService()
            resultado = scalability_service.validar_operacao(
                tipo_operacao=data.get('tipo_operacao'),
                dados_operacao=data.get('dados_operacao'),
                usuario_id=request.user.id
            )
            
            return JsonResponse({
                'success': True,
                'resultado': {
                    'sucesso': resultado.sucesso,
                    'detalhes': resultado.detalhes,
                    'validacao_id': resultado.validacao.id,
                    'resultado_id': resultado.id
                }
            })
            
        except Exception as e:
            logger.error(f"Erro na validação de operação: {e}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Método não permitido'})


@login_required
@require_stock_access
def api_executar_operacao_idempotente(request):
    """API para executar operação de forma idempotente."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            scalability_service = ScalabilityService()
            resultado = scalability_service.executar_operacao_idempotente(
                chave_idempotencia=data.get('chave_idempotencia'),
                tipo_operacao=data.get('tipo_operacao'),
                dados_operacao=data.get('dados_operacao'),
                usuario_id=request.user.id,
                descricao=data.get('descricao', '')
            )
            
            return JsonResponse({
                'success': True,
                'operacao': {
                    'id': resultado.id,
                    'chave_idempotencia': resultado.chave_idempotencia,
                    'status': resultado.status,
                    'data_criacao': resultado.data_criacao.isoformat()
                }
            })
            
        except Exception as e:
            logger.error(f"Erro na execução idempotente: {e}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Método não permitido'})
