from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.utils import timezone
from datetime import datetime, timedelta
import logging

from .models_stock import NotificacaoStock, StockItem, Item, MovimentoItem
from .decorators import require_stock_access

logger = logging.getLogger(__name__)

@login_required
@require_stock_access
def notificacoes_list(request):
    """Lista de notificações do usuário"""
    try:
        # Filtrar notificações do usuário (ou todas se for admin)
        if request.user.is_superuser:
            notificacoes = NotificacaoStock.objects.all()
        else:
            notificacoes = NotificacaoStock.objects.filter(
                Q(usuario_destinatario=request.user) | Q(usuario_destinatario__isnull=True)
            )
        
        # Filtros
        tipo = request.GET.get('tipo', '')
        lida = request.GET.get('lida', '')
        
        if tipo:
            notificacoes = notificacoes.filter(tipo=tipo)
        
        if lida == 'true':
            notificacoes = notificacoes.filter(lida=True)
        elif lida == 'false':
            notificacoes = notificacoes.filter(lida=False)
        
        # Ordenar por data de criação (mais recentes primeiro)
        notificacoes = notificacoes.order_by('-data_criacao')
        
        # Paginação
        paginator = Paginator(notificacoes, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Estatísticas
        total_notificacoes = notificacoes.count()
        nao_lidas = notificacoes.filter(lida=False).count()
        criticas_count = notificacoes.filter(
            lida=False,
            tipo__in=['stock_baixo', 'error', 'warning'],
            prioridade__gte=3
        ).count()
        
        # Tipos de notificação disponíveis
        tipos_disponiveis = NotificacaoStock.TIPOS_NOTIFICACAO
        
        context = {
            'page_obj': page_obj,
            'total_notificacoes': total_notificacoes,
            'nao_lidas': nao_lidas,
            'criticas_count': criticas_count,
            'tipos_disponiveis': tipos_disponiveis,
            'filtro_tipo': tipo,
            'filtro_lida': lida,
        }
        
        return render(request, 'stock/notificacoes/list.html', context)
        
    except Exception as e:
        logger.error(f"Erro ao listar notificações: {e}")
        messages.error(request, 'Erro ao carregar notificações.')
        return redirect('stock:main')

@login_required
@require_stock_access
def notificacao_detail(request, notificacao_id):
    """Detalhes de uma notificação"""
    try:
        notificacao = get_object_or_404(NotificacaoStock, id=notificacao_id)
        
        # Verificar se o usuário tem acesso à notificação
        if not request.user.is_superuser and notificacao.usuario_destinatario and notificacao.usuario_destinatario != request.user:
            messages.error(request, 'Você não tem permissão para ver esta notificação.')
            return redirect('stock:notificacoes_list')
        
        # Marcar como lida se não estiver
        if not notificacao.lida:
            notificacao.lida = True
            notificacao.data_leitura = timezone.now()
            notificacao.save()
        
        context = {
            'notificacao': notificacao,
        }
        
        return render(request, 'stock/notificacoes/detail.html', context)
        
    except Exception as e:
        logger.error(f"Erro ao visualizar notificação {notificacao_id}: {e}")
        messages.error(request, 'Erro ao carregar notificação.')
        return redirect('stock:notificacoes_list')

@login_required
@require_stock_access
def notificacao_marcar_lida(request, notificacao_id):
    """Marcar notificação como lida"""
    # Se for GET, redirecionar para a lista
    if request.method == 'GET':
        messages.warning(request, 'Use o botão apropriado para marcar notificações como lidas.')
        return redirect('stock:notificacoes_list')
    
    try:
        notificacao = get_object_or_404(NotificacaoStock, id=notificacao_id)
        
        # Verificar se o usuário tem acesso à notificação
        if not request.user.is_superuser and notificacao.usuario_destinatario and notificacao.usuario_destinatario != request.user:
            return JsonResponse({'success': False, 'message': 'Sem permissão'})
        
        notificacao.lida = True
        notificacao.data_leitura = timezone.now()
        notificacao.save()
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        logger.error(f"Erro ao marcar notificação {notificacao_id} como lida: {e}")
        return JsonResponse({'success': False, 'message': 'Erro interno'})

@login_required
@require_stock_access
@require_http_methods(["POST"])
def notificacao_marcar_todas_lidas(request):
    """Marcar todas as notificações como lidas"""
    try:
        if request.user.is_superuser:
            notificacoes = NotificacaoStock.objects.filter(lida=False)
        else:
            notificacoes = NotificacaoStock.objects.filter(
                lida=False,
                usuario_destinatario=request.user
            )
        
        agora = timezone.now()
        notificacoes.update(lida=True, data_leitura=agora)
        
        return JsonResponse({'success': True, 'count': notificacoes.count()})
        
    except Exception as e:
        logger.error(f"Erro ao marcar todas as notificações como lidas: {e}")
        return JsonResponse({'success': False, 'message': 'Erro interno'})

@login_required
@require_stock_access
def notificacoes_dashboard(request):
    """Dashboard de notificações com estatísticas"""
    try:
        # Notificações não lidas
        if request.user.is_superuser:
            nao_lidas = NotificacaoStock.objects.filter(lida=False)
        else:
            nao_lidas = NotificacaoStock.objects.filter(
                lida=False,
                usuario_destinatario=request.user
            )
        
        # Estatísticas por tipo
        stats_por_tipo = nao_lidas.values('tipo').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Notificações críticas (últimas 24h)
        ontem = timezone.now() - timedelta(days=1)
        criticas = nao_lidas.filter(
            data_criacao__gte=ontem,
            tipo__in=['stock_baixo', 'error', 'warning']
        ).order_by('-data_criacao')[:5]
        
        # Notificações recentes
        recentes = nao_lidas.order_by('-data_criacao')[:10]
        
        context = {
            'total_nao_lidas': nao_lidas.count(),
            'stats_por_tipo': stats_por_tipo,
            'criticas': criticas,
            'recentes': recentes,
        }
        
        return render(request, 'stock/notificacoes/dashboard.html', context)
        
    except Exception as e:
        logger.error(f"Erro no dashboard de notificações: {e}")
        messages.error(request, 'Erro ao carregar dashboard de notificações.')
        return redirect('stock:main')

def criar_notificacao_stock_baixo():
    """Criar notificações para itens com estoque baixo"""
    try:
        itens_estoque_baixo = StockItem.objects.filter(
            quantidade_atual__lt=F('item__estoque_minimo')
        ).select_related('item', 'sucursal')
        
        for stock in itens_estoque_baixo:
            # Verificar se já existe notificação recente para este item
            notificacao_existente = NotificacaoStock.objects.filter(
                tipo='stock_baixo',
                titulo__icontains=stock.item.nome,
                data_criacao__gte=timezone.now() - timedelta(days=1)
            ).exists()
            
            if not notificacao_existente:
                NotificacaoStock.objects.create(
                    tipo='stock_baixo',
                    titulo=f'Estoque Baixo: {stock.item.nome}',
                    mensagem=f'O item {stock.item.nome} ({stock.item.codigo}) na sucursal {stock.sucursal.nome} está com estoque baixo. Quantidade atual: {stock.quantidade_atual}, Mínimo: {stock.item.estoque_minimo}.',
                    url=f'/stock/item/{stock.item.id}/',
                )
        
        logger.info(f"Criadas notificações para {itens_estoque_baixo.count()} itens com estoque baixo")
        
    except Exception as e:
        logger.error(f"Erro ao criar notificações de estoque baixo: {e}")

def criar_notificacao_movimento_sem_usuario():
    """Criar notificações para movimentos sem usuário"""
    try:
        movimentos_sem_usuario = MovimentoItem.objects.filter(
            usuario__isnull=True,
            data_movimento__gte=timezone.now() - timedelta(days=7)
        )
        
        if movimentos_sem_usuario.exists():
            NotificacaoStock.objects.create(
                tipo='movimentacao_sem_usuario',
                titulo=f'Movimentações sem Usuário',
                mensagem=f'Existem {movimentos_sem_usuario.count()} movimentações dos últimos 7 dias sem usuário responsável registrado.',
                url='/stock/movimentos/',
            )
        
        logger.info(f"Verificadas {movimentos_sem_usuario.count()} movimentações sem usuário")
        
    except Exception as e:
        logger.error(f"Erro ao verificar movimentações sem usuário: {e}")
