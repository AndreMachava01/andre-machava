from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Count, Sum, Q, F, Case, When
from django.utils import timezone
from datetime import datetime, timedelta
import json
import logging

from .models_stock import (
    StockItem, Item, MovimentoItem, NotificacaoStock, 
    Fornecedor, CategoriaProduto, Receita
)
from .decorators import require_stock_access, get_user_sucursais

logger = logging.getLogger(__name__)

@login_required
@require_stock_access
def dashboard_executivo(request):
    """Dashboard executivo com gráficos interativos"""
    try:
        # Obter sucursais permitidas
        sucursais_permitidas = get_user_sucursais(request, for_modification=False)
        sucursais_ids = [s.id for s in sucursais_permitidas]
        
        # Período padrão (últimos 30 dias)
        data_limite = timezone.now() - timedelta(days=30)
        
        # Estatísticas principais
        stats = {
            'total_produtos': Item.objects.filter(status='ATIVO', tipo='PRODUTO').count(),
            'total_materiais': Item.objects.filter(status='ATIVO', tipo='MATERIAL').count(),
            'total_fornecedores': Fornecedor.objects.filter(status='ATIVO').count(),
            'total_movimentos': MovimentoItem.objects.filter(
                data_movimento__gte=data_limite,
                sucursal_id__in=sucursais_ids
            ).count(),
            'total_notificacoes': NotificacaoStock.objects.filter(
                Q(usuario_destinatario=request.user) | Q(usuario_destinatario__isnull=True),
                lida=False
            ).count(),
        }
        
        # Estoque baixo
        estoque_baixo = StockItem.objects.filter(
            sucursal_id__in=sucursais_ids,
            quantidade_atual__lt=F('item__estoque_minimo')
        ).count()
        
        stats['estoque_baixo'] = estoque_baixo
        
        # Valor total do estoque
        valor_total_estoque = StockItem.objects.filter(
            sucursal_id__in=sucursais_ids
        ).aggregate(
            total=Sum(F('quantidade_atual') * F('item__preco_custo'))
        )['total'] or 0
        
        stats['valor_total_estoque'] = valor_total_estoque
        
        context = {
            'stats': stats,
            'sucursais': sucursais_permitidas,
            'data_limite': data_limite.strftime('%Y-%m-%d'),
        }
        
        return render(request, 'stock/dashboard/executivo.html', context)
        
    except Exception as e:
        logger.error(f"Erro no dashboard executivo: {e}")
        return render(request, 'stock/dashboard/executivo.html', {'error': str(e)})

@login_required
@require_stock_access
def dashboard_chart_movimentacoes(request):
    """Dados para gráfico de movimentações por dia"""
    try:
        # Parâmetros
        dias = int(request.GET.get('dias', 30))
        tipo_item = request.GET.get('tipo_item', '')
        
        # Obter sucursais permitidas
        sucursais_permitidas = get_user_sucursais(request, for_modification=False)
        sucursais_ids = [s.id for s in sucursais_permitidas]
        
        # Data limite
        data_limite = timezone.now() - timedelta(days=dias)
        
        # Query base
        movimentos = MovimentoItem.objects.filter(
            data_movimento__gte=data_limite,
            sucursal_id__in=sucursais_ids
        )
        
        # Filtrar por tipo de item se especificado
        if tipo_item:
            movimentos = movimentos.filter(item__tipo=tipo_item)
        
        # Agrupar por dia
        movimentos_por_dia = movimentos.extra(
            select={'dia': 'DATE(data_movimento)'}
        ).values('dia').annotate(
            total=Count('id'),
            entrada=Sum(Case(When(tipo_movimento__aumenta_estoque=True, then=1), default=0)),
            saida=Sum(Case(When(tipo_movimento__aumenta_estoque=False, then=1), default=0))
        ).order_by('dia')
        
        # Preparar dados para o gráfico
        labels = []
        dados_entrada = []
        dados_saida = []
        
        # Criar lista completa de dias
        for i in range(dias):
            data = (timezone.now() - timedelta(days=dias-i-1)).date()
            labels.append(data.strftime('%d/%m'))
            
            # Buscar dados para este dia
            dia_data = next((item for item in movimentos_por_dia if item['dia'] == data), None)
            if dia_data:
                dados_entrada.append(dia_data['entrada'] or 0)
                dados_saida.append(dia_data['saida'] or 0)
            else:
                dados_entrada.append(0)
                dados_saida.append(0)
        
        return JsonResponse({
            'labels': labels,
            'datasets': [
                {
                    'label': 'Entradas',
                    'data': dados_entrada,
                    'backgroundColor': 'rgba(34, 197, 94, 0.2)',
                    'borderColor': 'rgba(34, 197, 94, 1)',
                    'borderWidth': 2
                },
                {
                    'label': 'Saídas',
                    'data': dados_saida,
                    'backgroundColor': 'rgba(239, 68, 68, 0.2)',
                    'borderColor': 'rgba(239, 68, 68, 1)',
                    'borderWidth': 2
                }
            ]
        })
        
    except Exception as e:
        logger.error(f"Erro no gráfico de movimentações: {e}")
        return JsonResponse({'error': str(e)})

@login_required
@require_stock_access
def dashboard_chart_estoque_sucursal(request):
    """Dados para gráfico de estoque por sucursal"""
    try:
        # Obter sucursais permitidas
        sucursais_permitidas = get_user_sucursais(request, for_modification=False)
        sucursais_ids = [s.id for s in sucursais_permitidas]
        
        # Dados por sucursal
        dados_sucursal = []
        
        for sucursal in sucursais_permitidas:
            # Contar itens por tipo
            produtos = StockItem.objects.filter(
                sucursal=sucursal,
                item__tipo='PRODUTO'
            ).count()
            
            materiais = StockItem.objects.filter(
                sucursal=sucursal,
                item__tipo='MATERIAL'
            ).count()
            
            # Valor total
            valor_total = StockItem.objects.filter(
                sucursal=sucursal
            ).aggregate(
                total=Sum(F('quantidade_atual') * F('item__preco_custo'))
            )['total'] or 0
            
            dados_sucursal.append({
                'sucursal': sucursal.nome,
                'produtos': produtos,
                'materiais': materiais,
                'valor_total': float(valor_total)
            })
        
        # Preparar dados para gráfico de pizza
        labels = [item['sucursal'] for item in dados_sucursal]
        dados_produtos = [item['produtos'] for item in dados_sucursal]
        dados_materiais = [item['materiais'] for item in dados_sucursal]
        
        return JsonResponse({
            'labels': labels,
            'datasets': [
                {
                    'label': 'Produtos',
                    'data': dados_produtos,
                    'backgroundColor': [
                        'rgba(59, 130, 246, 0.8)',
                        'rgba(16, 185, 129, 0.8)',
                        'rgba(245, 158, 11, 0.8)',
                        'rgba(239, 68, 68, 0.8)',
                        'rgba(139, 92, 246, 0.8)',
                    ]
                },
                {
                    'label': 'Materiais',
                    'data': dados_materiais,
                    'backgroundColor': [
                        'rgba(59, 130, 246, 0.4)',
                        'rgba(16, 185, 129, 0.4)',
                        'rgba(245, 158, 11, 0.4)',
                        'rgba(239, 68, 68, 0.4)',
                        'rgba(139, 92, 246, 0.4)',
                    ]
                }
            ]
        })
        
    except Exception as e:
        logger.error(f"Erro no gráfico de estoque por sucursal: {e}")
        return JsonResponse({'error': str(e)})

@login_required
@require_stock_access
def dashboard_chart_categorias(request):
    """Dados para gráfico de distribuição por categorias"""
    try:
        # Obter sucursais permitidas
        sucursais_permitidas = get_user_sucursais(request, for_modification=False)
        sucursais_ids = [s.id for s in sucursais_permitidas]
        
        # Agrupar por categoria
        categorias_data = StockItem.objects.filter(
            sucursal_id__in=sucursais_ids
        ).values(
            'item__categoria__nome'
        ).annotate(
            total_itens=Count('id'),
            total_quantidade=Sum('quantidade_atual'),
            valor_total=Sum(F('quantidade_atual') * F('item__preco_custo'))
        ).order_by('-total_quantidade')[:10]  # Top 10 categorias
        
        labels = []
        dados_quantidade = []
        dados_valor = []
        
        for item in categorias_data:
            categoria_nome = item['item__categoria__nome'] or 'Sem Categoria'
            labels.append(categoria_nome)
            dados_quantidade.append(item['total_quantidade'] or 0)
            dados_valor.append(float(item['valor_total'] or 0))
        
        return JsonResponse({
            'labels': labels,
            'datasets': [
                {
                    'label': 'Quantidade',
                    'data': dados_quantidade,
                    'backgroundColor': 'rgba(59, 130, 246, 0.6)',
                    'borderColor': 'rgba(59, 130, 246, 1)',
                    'borderWidth': 1
                },
                {
                    'label': 'Valor (MT)',
                    'data': dados_valor,
                    'backgroundColor': 'rgba(16, 185, 129, 0.6)',
                    'borderColor': 'rgba(16, 185, 129, 1)',
                    'borderWidth': 1,
                    'yAxisID': 'y1'
                }
            ]
        })
        
    except Exception as e:
        logger.error(f"Erro no gráfico de categorias: {e}")
        return JsonResponse({'error': str(e)})

@login_required
@require_stock_access
def dashboard_chart_tendencias(request):
    """Dados para gráfico de tendências de estoque"""
    try:
        # Parâmetros
        dias = int(request.GET.get('dias', 30))
        
        # Obter sucursais permitidas
        sucursais_permitidas = get_user_sucursais(request, for_modification=False)
        sucursais_ids = [s.id for s in sucursais_permitidas]
        
        # Data limite
        data_limite = timezone.now() - timedelta(days=dias)
        
        # Movimentações por dia
        movimentos_por_dia = MovimentoItem.objects.filter(
            data_movimento__gte=data_limite,
            sucursal_id__in=sucursais_ids
        ).extra(
            select={'dia': 'DATE(data_movimento)'}
        ).values('dia').annotate(
            entrada_valor=Sum(Case(
                When(tipo_movimento__aumenta_estoque=True, 
                     then=F('quantidade') * F('preco_unitario')), 
                default=0
            )),
            saida_valor=Sum(Case(
                When(tipo_movimento__aumenta_estoque=False, 
                     then=F('quantidade') * F('preco_unitario')), 
                default=0
            ))
        ).order_by('dia')
        
        # Preparar dados
        labels = []
        dados_entrada = []
        dados_saida = []
        
        for i in range(dias):
            data = (timezone.now() - timedelta(days=dias-i-1)).date()
            labels.append(data.strftime('%d/%m'))
            
            dia_data = next((item for item in movimentos_por_dia if item['dia'] == data), None)
            if dia_data:
                dados_entrada.append(float(dia_data['entrada_valor'] or 0))
                dados_saida.append(float(dia_data['saida_valor'] or 0))
            else:
                dados_entrada.append(0)
                dados_saida.append(0)
        
        return JsonResponse({
            'labels': labels,
            'datasets': [
                {
                    'label': 'Valor Entradas (MT)',
                    'data': dados_entrada,
                    'backgroundColor': 'rgba(34, 197, 94, 0.2)',
                    'borderColor': 'rgba(34, 197, 94, 1)',
                    'borderWidth': 2,
                    'fill': True
                },
                {
                    'label': 'Valor Saídas (MT)',
                    'data': dados_saida,
                    'backgroundColor': 'rgba(239, 68, 68, 0.2)',
                    'borderColor': 'rgba(239, 68, 68, 1)',
                    'borderWidth': 2,
                    'fill': True
                }
            ]
        })
        
    except Exception as e:
        logger.error(f"Erro no gráfico de tendências: {e}")
        return JsonResponse({'error': str(e)})
