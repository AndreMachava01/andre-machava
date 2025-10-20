from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Count
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import timedelta
import logging

from .models_stock import NotificacaoStock
from .decorators import require_stock_access
from .signals_alertas import criar_alertas_sistema, limpar_notificacoes_antigas

logger = logging.getLogger(__name__)

@login_required
@require_stock_access
def alertas_gerenciar(request):
    """Página de gerenciamento de alertas"""
    try:
        # Estatísticas de alertas
        total_alertas = NotificacaoStock.objects.count()
        alertas_nao_lidos = NotificacaoStock.objects.filter(lida=False).count()
        
        # Alertas por tipo
        alertas_por_tipo = NotificacaoStock.objects.values('tipo').annotate(
            total=Count('id'),
            nao_lidos=Count('id', filter=Q(lida=False))
        ).order_by('tipo')
        
        # Alertas recentes (últimos 7 dias)
        data_limite = timezone.now() - timedelta(days=7)
        alertas_recentes = NotificacaoStock.objects.filter(
            data_criacao__gte=data_limite
        ).order_by('-data_criacao')[:10]
        
        # Alertas críticos (não lidos)
        alertas_criticos = NotificacaoStock.objects.filter(
            lida=False,
            tipo__in=['stock_baixo', 'requisicao_antiga', 'movimentacao_sem_usuario']
        ).order_by('-data_criacao')[:5]
        
        context = {
            'total_alertas': total_alertas,
            'alertas_nao_lidos': alertas_nao_lidos,
            'alertas_por_tipo': alertas_por_tipo,
            'alertas_recentes': alertas_recentes,
            'alertas_criticos': alertas_criticos,
        }
        
        return render(request, 'stock/alertas/gerenciar.html', context)
        
    except Exception as e:
        logger.error(f"Erro na página de gerenciamento de alertas: {e}")
        messages.error(request, f"Erro ao carregar alertas: {e}")
        return redirect('stock:main')

@login_required
@require_stock_access
def alertas_criar_manuais(request):
    """Cria alertas do sistema manualmente"""
    try:
        if request.method == 'POST':
            criar_alertas_sistema()
            messages.success(request, "Alertas do sistema criados com sucesso!")
            return redirect('stock:alertas_gerenciar')
        
        return render(request, 'stock/alertas/criar_manuais.html')
        
    except Exception as e:
        logger.error(f"Erro ao criar alertas manuais: {e}")
        messages.error(request, f"Erro ao criar alertas: {e}")
        return redirect('stock:alertas_gerenciar')

@login_required
@require_stock_access
def alertas_limpar_antigas(request):
    """Remove notificações antigas"""
    try:
        if request.method == 'POST':
            data_limite = timezone.now() - timedelta(days=30)
            notificacoes_removidas = NotificacaoStock.objects.filter(
                data_criacao__lt=data_limite,
                lida=True
            ).delete()
            
            messages.success(request, f"Removidas {notificacoes_removidas[0]} notificações antigas!")
            return redirect('stock:alertas_gerenciar')
        
        return render(request, 'stock/alertas/limpar_antigas.html')
        
    except Exception as e:
        logger.error(f"Erro ao limpar notificações antigas: {e}")
        messages.error(request, f"Erro ao limpar notificações: {e}")
        return redirect('stock:alertas_gerenciar')

@login_required
@require_stock_access
def alertas_marcar_todos_lidos(request):
    """Marca todos os alertas como lidos"""
    try:
        if request.method == 'POST':
            alertas_atualizados = NotificacaoStock.objects.filter(
                lida=False
            ).update(
                lida=True,
                data_leitura=timezone.now()
            )
            
            messages.success(request, f"{alertas_atualizados} alertas marcados como lidos!")
            return redirect('stock:alertas_gerenciar')
        
        return render(request, 'stock/alertas/marcar_todos_lidos.html')
        
    except Exception as e:
        logger.error(f"Erro ao marcar alertas como lidos: {e}")
        messages.error(request, f"Erro ao marcar alertas: {e}")
        return redirect('stock:alertas_gerenciar')

@login_required
@require_stock_access
def alertas_estatisticas(request):
    """API para estatísticas de alertas"""
    try:
        # Estatísticas gerais
        total_alertas = NotificacaoStock.objects.count()
        alertas_nao_lidos = NotificacaoStock.objects.filter(lida=False).count()
        
        # Alertas por tipo
        alertas_por_tipo = list(NotificacaoStock.objects.values('tipo').annotate(
            total=Count('id'),
            nao_lidos=Count('id', filter=Q(lida=False))
        ).order_by('tipo'))
        
        # Alertas por dia (últimos 30 dias)
        data_limite = timezone.now() - timedelta(days=30)
        alertas_por_dia = list(NotificacaoStock.objects.filter(
            data_criacao__gte=data_limite
        ).extra(
            select={'dia': 'DATE(data_criacao)'}
        ).values('dia').annotate(
            total=Count('id')
        ).order_by('dia'))
        
        return JsonResponse({
            'total_alertas': total_alertas,
            'alertas_nao_lidos': alertas_nao_lidos,
            'alertas_por_tipo': alertas_por_tipo,
            'alertas_por_dia': alertas_por_dia,
        })
        
    except Exception as e:
        logger.error(f"Erro ao obter estatísticas de alertas: {e}")
        return JsonResponse({'error': str(e)}, status=500)
