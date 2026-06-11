"""
Views para gerenciamento de UX Mobile e painel motorista.
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Q, Count, Sum, Avg, F
from django.http import JsonResponse
from django.core.paginator import Paginator
from datetime import datetime, date, time, timedelta
import json
import logging
import uuid

from .decorators import require_stock_access
from .models_mobile import (
    SessaoMotorista, EventoMotorista, ConfiguracaoMobile, 
    SincronizacaoOffline, NotificacaoMobile
)
from .models_stock import RastreamentoEntrega, VeiculoInterno
from .services.mobile_service import MobileService

logger = logging.getLogger(__name__)


# =============================================================================
# DASHBOARD DE UX MOBILE
# =============================================================================

@login_required
@require_stock_access
def mobile_dashboard(request):
    """Dashboard de UX Mobile."""
    
    # Métricas de mobile
    metricas = {
        'sessoes_ativas': SessaoMotorista.objects.filter(status='ATIVA').count(),
        'sessoes_total': SessaoMotorista.objects.count(),
        'eventos_motorista': EventoMotorista.objects.count(),
        'sincronizacoes_pendentes': SincronizacaoOffline.objects.filter(
            status='PENDENTE'
        ).count(),
        'notificacoes_nao_lidas': NotificacaoMobile.objects.filter(
            lida=False
        ).count(),
    }
    
    # Sessões ativas
    sessoes_ativas = SessaoMotorista.objects.filter(
        status='ATIVA'
    ).select_related('motorista', 'veiculo_interno').order_by('-data_inicio')
    
    # Eventos recentes
    eventos_recentes = EventoMotorista.objects.select_related(
        'sessao', 'sessao__motorista'
    ).order_by('-data_evento')[:10]
    
    # Estatísticas de uso
    stats_uso = {
        'sessoes_por_dia': SessaoMotorista.objects.filter(
            data_inicio__gte=timezone.now() - timedelta(days=7)
        ).count(),
        'tempo_medio_sessao': SessaoMotorista.objects.filter(
            status='FINALIZADA'
        ).aggregate(
            tempo_medio=Avg(F('data_fim') - F('data_inicio'))
        )['tempo_medio'],
        'eventos_por_tipo': dict(EventoMotorista.objects.values('tipo_evento').annotate(
            count=Count('id')
        ).values_list('tipo_evento', 'count')),
    }
    
    context = {
        'metricas': metricas,
        'sessoes_ativas': sessoes_ativas,
        'eventos_recentes': eventos_recentes,
        'stats_uso': stats_uso,
    }
    
    return render(request, 'stock/logistica/mobile/dashboard.html', context)


# =============================================================================
# SESSÕES DE MOTORISTA
# =============================================================================

@login_required
@require_stock_access
def sessoes_motorista_list(request):
    """Lista de sessões de motorista."""
    search = request.GET.get('search', '')
    status = request.GET.get('status', '')
    motorista_id = request.GET.get('motorista_id', '')
    data_inicio = request.GET.get('data_inicio', '')
    data_fim = request.GET.get('data_fim', '')
    
    sessoes = SessaoMotorista.objects.select_related('motorista', 'veiculo_interno')
    
    if search:
        sessoes = sessoes.filter(
            Q(motorista__username__icontains=search) |
            Q(motorista__first_name__icontains=search) |
            Q(motorista__last_name__icontains=search) |
            Q(veiculo_interno__nome__icontains=search) |
            Q(token_sessao__icontains=search)
        )
    
    if status:
        sessoes = sessoes.filter(status=status)
    
    if motorista_id:
        sessoes = sessoes.filter(motorista_id=motorista_id)
    
    if data_inicio:
        sessoes = sessoes.filter(data_inicio__date__gte=data_inicio)
    
    if data_fim:
        sessoes = sessoes.filter(data_inicio__date__lte=data_fim)
    
    sessoes = sessoes.order_by('-data_inicio')
    
    # Paginação
    paginator = Paginator(sessoes, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Opções para filtros
    status_choices = SessaoMotorista.STATUS_CHOICES
    motoristas = SessaoMotorista.objects.values_list(
        'motorista_id', 'motorista__username'
    ).distinct().order_by('motorista__username')
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'status': status,
        'motorista_id': motorista_id,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'status_choices': status_choices,
        'motoristas': motoristas,
    }
    
    return render(request, 'stock/logistica/mobile/sessoes_list.html', context)


@login_required
@require_stock_access
def sessao_motorista_detail(request, sessao_id):
    """Detalhes de uma sessão de motorista."""
    sessao = get_object_or_404(SessaoMotorista, id=sessao_id)
    
    # Eventos da sessão
    eventos_sessao = sessao.eventos.all().order_by('-data_evento')
    
    # Rastreamentos atribuídos
    rastreamentos = RastreamentoEntrega.objects.filter(
        veiculo_interno=sessao.veiculo_interno,
        status_atual__in=['EM_TRANSITO', 'EM_DISTRIBUICAO']
    ).order_by('-data_criacao')
    
    context = {
        'sessao': sessao,
        'eventos_sessao': eventos_sessao,
        'rastreamentos': rastreamentos,
    }
    
    return render(request, 'stock/logistica/mobile/sessao_detail.html', context)


@login_required
@require_stock_access
def iniciar_sessao_motorista(request):
    """Iniciar nova sessão de motorista."""
    if request.method == 'POST':
        try:
            veiculo_id = request.POST.get('veiculo_interno')
            latitude_inicial = request.POST.get('latitude_inicial')
            longitude_inicial = request.POST.get('longitude_inicial')
            dispositivo_info = request.POST.get('dispositivo_info', '{}')
            versao_app = request.POST.get('versao_app', '')
            
            if not veiculo_id:
                raise ValueError("Veículo é obrigatório")
            
            if not latitude_inicial or not longitude_inicial:
                raise ValueError("Coordenadas iniciais são obrigatórias")
            
            mobile_service = MobileService()
            sessao = mobile_service.iniciar_sessao_motorista(
                motorista_id=request.user.id,
                veiculo_id=veiculo_id,
                latitude_inicial=float(latitude_inicial),
                longitude_inicial=float(longitude_inicial),
                dispositivo_info=json.loads(dispositivo_info),
                versao_app=versao_app
            )
            
            messages.success(request, f'Sessão iniciada com sucesso! Token: {sessao.token_sessao}')
            return redirect('stock:mobile:sessao_detail', sessao_id=sessao.id)
            
        except Exception as e:
            logger.error(f"Erro ao iniciar sessão: {e}")
            messages.error(request, f'Erro ao iniciar sessão: {str(e)}')
    
    # GET - mostrar formulário
    veiculos = VeiculoInterno.objects.filter(status='ATIVO').order_by('nome')
    
    context = {
        'veiculos': veiculos,
    }
    
    return render(request, 'stock/logistica/mobile/iniciar_sessao_form.html', context)


# =============================================================================
# EVENTOS DE MOTORISTA
# =============================================================================

@login_required
@require_stock_access
def eventos_motorista_list(request):
    """Lista de eventos de motorista."""
    search = request.GET.get('search', '')
    tipo_evento = request.GET.get('tipo_evento', '')
    sessao_id = request.GET.get('sessao_id', '')
    data_inicio = request.GET.get('data_inicio', '')
    data_fim = request.GET.get('data_fim', '')
    
    eventos = EventoMotorista.objects.select_related('sessao', 'sessao__motorista')
    
    if search:
        eventos = eventos.filter(
            Q(sessao__motorista__username__icontains=search) |
            Q(observacoes__icontains=search) |
            Q(dados_evento__icontains=search)
        )
    
    if tipo_evento:
        eventos = eventos.filter(tipo_evento=tipo_evento)
    
    if sessao_id:
        eventos = eventos.filter(sessao_id=sessao_id)
    
    if data_inicio:
        eventos = eventos.filter(data_evento__date__gte=data_inicio)
    
    if data_fim:
        eventos = eventos.filter(data_evento__date__lte=data_fim)
    
    eventos = eventos.order_by('-data_evento')
    
    # Paginação
    paginator = Paginator(eventos, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Opções para filtros
    tipo_choices = EventoMotorista.TIPO_EVENTO_CHOICES
    sessoes = SessaoMotorista.objects.values_list('id', 'token_sessao').order_by('-data_inicio')
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'tipo_evento': tipo_evento,
        'sessao_id': sessao_id,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'tipo_choices': tipo_choices,
        'sessoes': sessoes,
    }
    
    return render(request, 'stock/logistica/mobile/eventos_list.html', context)


# =============================================================================
# SINCRONIZAÇÃO OFFLINE
# =============================================================================

@login_required
@require_stock_access
def sincronizacoes_offline_list(request):
    """Lista de sincronizações offline."""
    search = request.GET.get('search', '')
    status = request.GET.get('status', '')
    tipo_operacao = request.GET.get('tipo_operacao', '')
    data_inicio = request.GET.get('data_inicio', '')
    data_fim = request.GET.get('data_fim', '')
    
    sincronizacoes = SincronizacaoOffline.objects.select_related('sessao')
    
    if search:
        sincronizacoes = sincronizacoes.filter(
            Q(sessao__token_sessao__icontains=search) |
            Q(operacao__icontains=search) |
            Q(dados_operacao__icontains=search)
        )
    
    if status:
        sincronizacoes = sincronizacoes.filter(status=status)
    
    if tipo_operacao:
        sincronizacoes = sincronizacoes.filter(tipo_operacao=tipo_operacao)
    
    if data_inicio:
        sincronizacoes = sincronizacoes.filter(data_criacao__date__gte=data_inicio)
    
    if data_fim:
        sincronizacoes = sincronizacoes.filter(data_criacao__date__lte=data_fim)
    
    sincronizacoes = sincronizacoes.order_by('-data_criacao')
    
    # Paginação
    paginator = Paginator(sincronizacoes, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Opções para filtros
    status_choices = SincronizacaoOffline.STATUS_CHOICES
    tipo_choices = SincronizacaoOffline.TIPO_OPERACAO_CHOICES
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'status': status,
        'tipo_operacao': tipo_operacao,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'status_choices': status_choices,
        'tipo_choices': tipo_choices,
    }
    
    return render(request, 'stock/logistica/mobile/sincronizacoes_list.html', context)


@login_required
@require_stock_access
def sincronizar_offline(request, sincronizacao_id):
    """Sincronizar operação offline."""
    if request.method == 'POST':
        try:
            mobile_service = MobileService()
            resultado = mobile_service.processar_sincronizacao_offline(sincronizacao_id)
            
            messages.success(request, 'Sincronização processada com sucesso!')
            return redirect('stock:mobile:sincronizacoes_list')
            
        except Exception as e:
            logger.error(f"Erro na sincronização: {e}")
            messages.error(request, f'Erro na sincronização: {str(e)}')
    
    sincronizacao = get_object_or_404(SincronizacaoOffline, id=sincronizacao_id)
    
    context = {
        'sincronizacao': sincronizacao,
    }
    
    return render(request, 'stock/logistica/mobile/sincronizar_form.html', context)


# =============================================================================
# NOTIFICAÇÕES MOBILE
# =============================================================================

@login_required
@require_stock_access
def notificacoes_mobile_list(request):
    """Lista de notificações mobile."""
    search = request.GET.get('search', '')
    tipo_notificacao = request.GET.get('tipo_notificacao', '')
    lida = request.GET.get('lida', '')
    data_inicio = request.GET.get('data_inicio', '')
    data_fim = request.GET.get('data_fim', '')
    
    notificacoes = NotificacaoMobile.objects.select_related('destinatario')
    
    if search:
        notificacoes = notificacoes.filter(
            Q(titulo__icontains=search) |
            Q(mensagem__icontains=search) |
            Q(destinatario__username__icontains=search)
        )
    
    if tipo_notificacao:
        notificacoes = notificacoes.filter(tipo_notificacao=tipo_notificacao)
    
    if lida:
        notificacoes = notificacoes.filter(lida=lida == 'true')
    
    if data_inicio:
        notificacoes = notificacoes.filter(data_criacao__date__gte=data_inicio)
    
    if data_fim:
        notificacoes = notificacoes.filter(data_criacao__date__lte=data_fim)
    
    notificacoes = notificacoes.order_by('-data_criacao')
    
    # Paginação
    paginator = Paginator(notificacoes, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Opções para filtros
    tipo_choices = NotificacaoMobile.TIPO_NOTIFICACAO_CHOICES
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'tipo_notificacao': tipo_notificacao,
        'lida': lida,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'tipo_choices': tipo_choices,
    }
    
    return render(request, 'stock/logistica/mobile/notificacoes_list.html', context)


# =============================================================================
# APIS PARA MOBILE
# =============================================================================

@login_required
@require_stock_access
def api_iniciar_sessao(request):
    """API para iniciar sessão de motorista."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            mobile_service = MobileService()
            sessao = mobile_service.iniciar_sessao_motorista(
                motorista_id=request.user.id,
                veiculo_id=data.get('veiculo_id'),
                latitude_inicial=float(data.get('latitude_inicial')),
                longitude_inicial=float(data.get('longitude_inicial')),
                dispositivo_info=data.get('dispositivo_info', {}),
                versao_app=data.get('versao_app', '')
            )
            
            return JsonResponse({
                'success': True,
                'sessao': {
                    'id': sessao.id,
                    'token_sessao': sessao.token_sessao,
                    'status': sessao.status,
                    'data_inicio': sessao.data_inicio.isoformat()
                }
            })
            
        except Exception as e:
            logger.error(f"Erro ao iniciar sessão: {e}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Método não permitido'})


@login_required
@require_stock_access
def api_registrar_evento(request):
    """API para registrar evento de motorista."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            mobile_service = MobileService()
            evento = mobile_service.registrar_evento_motorista(
                token_sessao=data.get('token_sessao'),
                tipo_evento=data.get('tipo_evento'),
                latitude=float(data.get('latitude')),
                longitude=float(data.get('longitude')),
                dados_evento=data.get('dados_evento', {}),
                observacoes=data.get('observacoes', '')
            )
            
            return JsonResponse({
                'success': True,
                'evento': {
                    'id': evento.id,
                    'tipo_evento': evento.tipo_evento,
                    'data_evento': evento.data_evento.isoformat()
                }
            })
            
        except Exception as e:
            logger.error(f"Erro ao registrar evento: {e}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Método não permitido'})


@login_required
@require_stock_access
def api_sincronizar_offline(request):
    """API para sincronizar operações offline."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            mobile_service = MobileService()
            resultado = mobile_service.criar_sincronizacao_offline(
                token_sessao=data.get('token_sessao'),
                tipo_operacao=data.get('tipo_operacao'),
                operacao=data.get('operacao'),
                dados_operacao=data.get('dados_operacao', {})
            )
            
            return JsonResponse({
                'success': True,
                'sincronizacao': {
                    'id': resultado.id,
                    'status': resultado.status,
                    'data_criacao': resultado.data_criacao.isoformat()
                }
            })
            
        except Exception as e:
            logger.error(f"Erro na sincronização offline: {e}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Método não permitido'})


@login_required
@require_stock_access
def api_obter_rastreamentos(request):
    """API para obter rastreamentos do motorista."""
    if request.method == 'GET':
        try:
            token_sessao = request.GET.get('token_sessao')
            
            if not token_sessao:
                return JsonResponse({'success': False, 'error': 'Token de sessão é obrigatório'})
            
            mobile_service = MobileService()
            rastreamentos = mobile_service.obter_rastreamentos_motorista(token_sessao)
            
            return JsonResponse({
                'success': True,
                'rastreamentos': [
                    {
                        'id': r.id,
                        'codigo_rastreamento': r.codigo_rastreamento,
                        'status_atual': r.status_atual,
                        'destinatario_nome': r.destinatario_nome,
                        'endereco_entrega': r.endereco_entrega,
                        'data_entrega_prevista': r.data_entrega_prevista.isoformat() if r.data_entrega_prevista else None
                    }
                    for r in rastreamentos
                ]
            })
            
        except Exception as e:
            logger.error(f"Erro ao obter rastreamentos: {e}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Método não permitido'})
