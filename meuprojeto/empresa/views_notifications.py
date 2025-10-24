"""
Views para sistema de notificações push logísticas.
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
import requests
from django.conf import settings

from .decorators import require_stock_access
from .models_stock import RastreamentoEntrega, EventoRastreamento
# from .models_mobile import NotificacaoMobile
from .services.notification_service import NotificationService

logger = logging.getLogger(__name__)


# =============================================================================
# DASHBOARD DE NOTIFICAÇÕES
# =============================================================================

@login_required
@require_stock_access
def notifications_dashboard(request):
    """Dashboard de notificações push."""
    
    # Métricas de notificações
    metricas = {
        'notificacoes_enviadas': 0,  # NotificacaoMobile.objects.count(),
        'notificacoes_nao_lidas': 0,  # NotificacaoMobile.objects.filter(lida=False).count(),
        'notificacoes_hoje': 0,  # NotificacaoMobile.objects.filter(
        #     data_criacao__date=timezone.now().date()
        # ).count(),
        'taxa_leitura': 0,
    }
    
    # Calcular taxa de leitura
    total_notificacoes = 0  # NotificacaoMobile.objects.count()
    if total_notificacoes > 0:
        lidas = 0  # NotificacaoMobile.objects.filter(lida=True).count()
        metricas['taxa_leitura'] = round((lidas / total_notificacoes) * 100, 2)
    
    # Notificações recentes
    notificacoes_recentes = []  # NotificacaoMobile.objects.select_related(
    #     'destinatario'
    # ).order_by('-data_criacao')[:10]
    
    # Estatísticas por tipo
    stats_por_tipo = []  # NotificacaoMobile.objects.values('tipo_notificacao').annotate(
    #     count=Count('id')
    # ).order_by('-count')
    
    # Estatísticas por canal
    stats_por_canal = []  # NotificacaoMobile.objects.values('canal').annotate(
    #     count=Count('id')
    # ).order_by('-count')
    
    context = {
        'metricas': metricas,
        'notificacoes_recentes': notificacoes_recentes,
        'stats_por_tipo': stats_por_tipo,
        'stats_por_canal': stats_por_canal,
    }
    
    return render(request, 'stock/logistica/notifications/dashboard.html', context)


# =============================================================================
# GESTÃO DE NOTIFICAÇÕES
# =============================================================================

@login_required
@require_stock_access
def notificacoes_list(request):
    """Lista de notificações."""
    search = request.GET.get('search', '')
    tipo_notificacao = request.GET.get('tipo_notificacao', '')
    canal = request.GET.get('canal', '')
    lida = request.GET.get('lida', '')
    data_inicio = request.GET.get('data_inicio', '')
    data_fim = request.GET.get('data_fim', '')
    
    notificacoes = []  # NotificacaoMobile.objects.select_related('destinatario')
    
    if search:
        notificacoes = notificacoes.filter(
            Q(titulo__icontains=search) |
            Q(mensagem__icontains=search) |
            Q(destinatario__username__icontains=search)
        )
    
    if tipo_notificacao:
        notificacoes = notificacoes.filter(tipo_notificacao=tipo_notificacao)
    
    if canal:
        notificacoes = notificacoes.filter(canal=canal)
    
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
    tipo_choices = []  # NotificacaoMobile.TIPO_NOTIFICACAO_CHOICES
    canal_choices = []  # NotificacaoMobile.CANAL_CHOICES
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'tipo_notificacao': tipo_notificacao,
        'canal': canal,
        'lida': lida,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'tipo_choices': tipo_choices,
        'canal_choices': canal_choices,
    }
    
    return render(request, 'stock/logistica/notifications/notificacoes_list.html', context)


@login_required
@require_stock_access
def notificacao_detail(request, notificacao_id):
    """Detalhes de uma notificação."""
    # notificacao = get_object_or_404(NotificacaoMobile, id=notificacao_id)
    
    # Marcar como lida se for o destinatário
    if request.user == notificacao.destinatario and not notificacao.lida:
        notificacao.lida = True
        notificacao.data_leitura = timezone.now()
        notificacao.save()
    
    context = {
        'notificacao': notificacao,
    }
    
    return render(request, 'stock/logistica/notifications/notificacao_detail.html', context)


@login_required
@require_stock_access
def enviar_notificacao(request):
    """Enviar nova notificação."""
    if request.method == 'POST':
        try:
            notification_service = NotificationService()
            
            # Dados da notificação
            destinatario_id = request.POST.get('destinatario_id')
            tipo_notificacao = request.POST.get('tipo_notificacao')
            canal = request.POST.get('canal', 'PUSH')
            titulo = request.POST.get('titulo', '')
            mensagem = request.POST.get('mensagem', '')
            dados_extras = request.POST.get('dados_extras', '{}')
            prioridade = request.POST.get('prioridade', 'NORMAL')
            
            if not destinatario_id or not tipo_notificacao or not mensagem:
                raise ValueError("Destinatário, tipo e mensagem são obrigatórios")
            
            # Enviar notificação
            notificacao = notification_service.enviar_notificacao(
                destinatario_id=int(destinatario_id),
                tipo_notificacao=tipo_notificacao,
                canal=canal,
                titulo=titulo,
                mensagem=mensagem,
                dados_extras=json.loads(dados_extras),
                prioridade=prioridade
            )
            
            messages.success(request, 'Notificação enviada com sucesso!')
            return redirect('stock:notifications:notificacao_detail', notificacao_id=notificacao.id)
            
        except Exception as e:
            logger.error(f"Erro ao enviar notificação: {e}")
            messages.error(request, f'Erro ao enviar notificação: {str(e)}')
    
    # GET - mostrar formulário
    from django.contrib.auth.models import User
    usuarios = User.objects.filter(is_active=True).order_by('username')
    tipo_choices = []  # NotificacaoMobile.TIPO_NOTIFICACAO_CHOICES
    canal_choices = []  # NotificacaoMobile.CANAL_CHOICES
    prioridade_choices = []  # NotificacaoMobile.PRIORIDADE_CHOICES
    
    context = {
        'usuarios': usuarios,
        'tipo_choices': tipo_choices,
        'canal_choices': canal_choices,
        'prioridade_choices': prioridade_choices,
    }
    
    return render(request, 'stock/logistica/notifications/enviar_notificacao_form.html', context)


# =============================================================================
# NOTIFICAÇÕES AUTOMÁTICAS
# =============================================================================

@login_required
@require_stock_access
def configurar_notificacoes_automaticas(request):
    """Configurar notificações automáticas."""
    if request.method == 'POST':
        try:
            # Salvar configurações de notificações automáticas
            configuracao = {
                'notificar_status_mudanca': request.POST.get('notificar_status_mudanca') == 'on',
                'notificar_atraso': request.POST.get('notificar_atraso') == 'on',
                'notificar_excecao': request.POST.get('notificar_excecao') == 'on',
                'notificar_pod_criada': request.POST.get('notificar_pod_criada') == 'on',
                'notificar_pod_validada': request.POST.get('notificar_pod_validada') == 'on',
                'horario_inicio': request.POST.get('horario_inicio', '08:00'),
                'horario_fim': request.POST.get('horario_fim', '18:00'),
                'dias_semana': request.POST.getlist('dias_semana'),
            }
            
            # Salvar no cache ou banco de dados
            from django.core.cache import cache
            cache.set('configuracao_notificacoes_automaticas', configuracao, timeout=None)
            
            messages.success(request, 'Configurações salvas com sucesso!')
            return redirect('stock:notifications:dashboard')
            
        except Exception as e:
            logger.error(f"Erro ao salvar configurações: {e}")
            messages.error(request, f'Erro ao salvar configurações: {str(e)}')
    
    # GET - mostrar configurações atuais
    from django.core.cache import cache
    configuracao = cache.get('configuracao_notificacoes_automaticas', {
        'notificar_status_mudanca': True,
        'notificar_atraso': True,
        'notificar_excecao': True,
        'notificar_pod_criada': True,
        'notificar_pod_validada': True,
        'horario_inicio': '08:00',
        'horario_fim': '18:00',
        'dias_semana': ['1', '2', '3', '4', '5'],  # Segunda a sexta
    })
    
    dias_semana_choices = [
        ('0', 'Domingo'),
        ('1', 'Segunda-feira'),
        ('2', 'Terça-feira'),
        ('3', 'Quarta-feira'),
        ('4', 'Quinta-feira'),
        ('5', 'Sexta-feira'),
        ('6', 'Sábado'),
    ]
    
    context = {
        'configuracao': configuracao,
        'dias_semana_choices': dias_semana_choices,
    }
    
    return render(request, 'stock/logistica/notifications/configurar_automaticas.html', context)


# =============================================================================
# APIS PARA NOTIFICAÇÕES
# =============================================================================

@login_required
@require_stock_access
def api_enviar_notificacao_push(request):
    """API para enviar notificação push."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            notification_service = NotificationService()
            notificacao = notification_service.enviar_notificacao(
                destinatario_id=data.get('destinatario_id'),
                tipo_notificacao=data.get('tipo_notificacao'),
                canal=data.get('canal', 'PUSH'),
                titulo=data.get('titulo', ''),
                mensagem=data.get('mensagem', ''),
                dados_extras=data.get('dados_extras', {}),
                prioridade=data.get('prioridade', 'NORMAL')
            )
            
            return JsonResponse({
                'success': True,
                'notificacao': {
                    'id': notificacao.id,
                    'titulo': notificacao.titulo,
                    'mensagem': notificacao.mensagem,
                    'data_criacao': notificacao.data_criacao.isoformat()
                }
            })
            
        except Exception as e:
            logger.error(f"Erro ao enviar notificação push: {e}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Método não permitido'})


@login_required
@require_stock_access
def api_marcar_como_lida(request, notificacao_id):
    """API para marcar notificação como lida."""
    if request.method == 'POST':
        try:
            # notificacao = get_object_or_404(NotificacaoMobile, id=notificacao_id)
            
            if request.user == notificacao.destinatario:
                notificacao.lida = True
                notificacao.data_leitura = timezone.now()
                notificacao.save()
                
                return JsonResponse({'success': True})
            else:
                return JsonResponse({'success': False, 'error': 'Não autorizado'})
                
        except Exception as e:
            logger.error(f"Erro ao marcar notificação como lida: {e}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Método não permitido'})


@login_required
@require_stock_access
def api_obter_notificacoes_usuario(request):
    """API para obter notificações do usuário."""
    if request.method == 'GET':
        try:
            nao_lidas = request.GET.get('nao_lidas', 'false') == 'true'
            limite = int(request.GET.get('limite', 20))
            
            notificacoes = []  # NotificacaoMobile.objects.filter(
            #     destinatario=request.user
            # )
            
            if nao_lidas:
                notificacoes = notificacoes.filter(lida=False)
            
            notificacoes = notificacoes.order_by('-data_criacao')[:limite]
            
            return JsonResponse({
                'success': True,
                'notificacoes': [
                    {
                        'id': n.id,
                        'titulo': n.titulo,
                        'mensagem': n.mensagem,
                        'tipo_notificacao': n.tipo_notificacao,
                        'canal': n.canal,
                        'prioridade': n.prioridade,
                        'lida': n.lida,
                        'data_criacao': n.data_criacao.isoformat(),
                        'data_leitura': n.data_leitura.isoformat() if n.data_leitura else None,
                        'dados_extras': n.dados_extras
                    }
                    for n in notificacoes
                ]
            })
            
        except Exception as e:
            logger.error(f"Erro ao obter notificações: {e}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Método não permitido'})


# =============================================================================
# WEBHOOKS PARA NOTIFICAÇÕES
# =============================================================================

@require_http_methods(["POST"])
def webhook_notificacao_status(request):
    """Webhook para notificações de mudança de status."""
    try:
        data = json.loads(request.body)
        
        notification_service = NotificationService()
        
        # Notificar mudança de status
        notification_service.notificar_mudanca_status(
            rastreamento_id=data.get('rastreamento_id'),
            status_anterior=data.get('status_anterior'),
            status_novo=data.get('status_novo'),
            observacoes=data.get('observacoes', '')
        )
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        logger.error(f"Erro no webhook de notificação: {e}")
        return JsonResponse({'success': False, 'error': str(e)})


@require_http_methods(["POST"])
def webhook_notificacao_atraso(request):
    """Webhook para notificações de atraso."""
    try:
        data = json.loads(request.body)
        
        notification_service = NotificationService()
        
        # Notificar atraso
        notification_service.notificar_atraso(
            rastreamento_id=data.get('rastreamento_id'),
            data_prevista=data.get('data_prevista'),
            dias_atraso=data.get('dias_atraso', 0)
        )
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        logger.error(f"Erro no webhook de atraso: {e}")
        return JsonResponse({'success': False, 'error': str(e)})


# =============================================================================
# TESTE DE NOTIFICAÇÕES
# =============================================================================

@login_required
@require_stock_access
def testar_notificacao(request):
    """Testar envio de notificação."""
    if request.method == 'POST':
        try:
            notification_service = NotificationService()
            
            # Enviar notificação de teste
            notificacao = notification_service.enviar_notificacao(
                destinatario_id=request.user.id,
                tipo_notificacao='TESTE',
                canal='PUSH',
                titulo='Teste de Notificação',
                mensagem='Esta é uma notificação de teste do sistema logístico.',
                dados_extras={'teste': True},
                prioridade='NORMAL'
            )
            
            messages.success(request, 'Notificação de teste enviada com sucesso!')
            return redirect('stock:notifications:notificacao_detail', notificacao_id=notificacao.id)
            
        except Exception as e:
            logger.error(f"Erro ao testar notificação: {e}")
            messages.error(request, f'Erro ao testar notificação: {str(e)}')
    
    return render(request, 'stock/logistica/notifications/testar_notificacao.html')
