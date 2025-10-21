"""
Views para relatórios logísticos avançados e dashboard executivo.
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Q, Count, Sum, Avg, F, Max, Min
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from datetime import datetime, date, time, timedelta
import json
import logging
import csv
from decimal import Decimal

from .decorators import require_stock_access
from .models_stock import (
    RastreamentoEntrega, EventoRastreamento, Transportadora, VeiculoInterno,
    NotificacaoLogisticaUnificada
)
from .models_pod import ProvaEntrega
from .models_cost_billing import CustoLogistico, FaturamentoLogistico
from .models_routing import Rota, PlanejamentoEntrega
from .models_exceptions import ExcecaoLogistica
from .models_geolocation import CalculoDistancia
from .models_mobile import SessaoMotorista, EventoMotorista

logger = logging.getLogger(__name__)


# =============================================================================
# DASHBOARD EXECUTIVO
# =============================================================================

@login_required
@require_stock_access
def dashboard_executivo(request):
    """Dashboard executivo com métricas avançadas."""
    
    # Período padrão (últimos 30 dias)
    data_fim = timezone.now().date()
    data_inicio = data_fim - timedelta(days=30)
    
    # Permitir filtro de período
    if request.GET.get('data_inicio'):
        data_inicio = datetime.strptime(request.GET.get('data_inicio'), '%Y-%m-%d').date()
    if request.GET.get('data_fim'):
        data_fim = datetime.strptime(request.GET.get('data_fim'), '%Y-%m-%d').date()
    
    # KPIs Principais
    kpis = _calcular_kpis_principais(data_inicio, data_fim)
    
    # Métricas de Performance
    performance = _calcular_metricas_performance(data_inicio, data_fim)
    
    # Análise de Custos
    custos = _calcular_analise_custos(data_inicio, data_fim)
    
    # SLA e Pontualidade
    sla = _calcular_metricas_sla(data_inicio, data_fim)
    
    # Análise por Transportadora
    transportadoras = _calcular_analise_transportadoras(data_inicio, data_fim)
    
    # Análise por Região
    regioes = _calcular_analise_regioes(data_inicio, data_fim)
    
    # Tendências (últimos 7 dias)
    tendencias = _calcular_tendencias()
    
    context = {
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'kpis': kpis,
        'performance': performance,
        'custos': custos,
        'sla': sla,
        'transportadoras': transportadoras,
        'regioes': regioes,
        'tendencias': tendencias,
    }
    
    return render(request, 'stock/logistica/reports/dashboard_executivo.html', context)


def _calcular_kpis_principais(data_inicio, data_fim):
    """Calcula KPIs principais do período."""
    
    # Total de entregas
    total_entregas = RastreamentoEntrega.objects.filter(
        data_criacao__date__range=[data_inicio, data_fim]
    ).count()
    
    # Entregas concluídas
    entregas_concluidas = RastreamentoEntrega.objects.filter(
        data_criacao__date__range=[data_inicio, data_fim],
        status_atual='ENTREGUE'
    ).count()
    
    # Taxa de entrega
    taxa_entrega = (entregas_concluidas / total_entregas * 100) if total_entregas > 0 else 0
    
    # Tempo médio de entrega
    tempo_medio = RastreamentoEntrega.objects.filter(
        data_criacao__date__range=[data_inicio, data_fim],
        status_atual='ENTREGUE',
        data_entrega__isnull=False
    ).aggregate(
        tempo_medio=Avg(F('data_entrega') - F('data_criacao'))
    )['tempo_medio']
    
    # Custo médio por entrega
    custo_medio = CustoLogistico.objects.filter(
        data_criacao__date__range=[data_inicio, data_fim]
    ).aggregate(
        custo_medio=Avg('valor_total')
    )['custo_medio'] or Decimal('0')
    
    return {
        'total_entregas': total_entregas,
        'entregas_concluidas': entregas_concluidas,
        'taxa_entrega': round(taxa_entrega, 2),
        'tempo_medio_dias': round(tempo_medio.total_seconds() / 86400, 1) if tempo_medio else 0,
        'custo_medio': round(float(custo_medio), 2),
    }


def _calcular_metricas_performance(data_inicio, data_fim):
    """Calcula métricas de performance."""
    
    # Performance por status
    performance_status = RastreamentoEntrega.objects.filter(
        data_criacao__date__range=[data_inicio, data_fim]
    ).values('status_atual').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Performance por dia da semana
    performance_dia_semana = RastreamentoEntrega.objects.filter(
        data_criacao__date__range=[data_inicio, data_fim]
    ).extra(
        select={'dia_semana': 'EXTRACT(dow FROM data_criacao)'}
    ).values('dia_semana').annotate(
        count=Count('id')
    ).order_by('dia_semana')
    
    # Performance por hora do dia
    performance_hora = RastreamentoEntrega.objects.filter(
        data_criacao__date__range=[data_inicio, data_fim]
    ).extra(
        select={'hora': 'EXTRACT(hour FROM data_criacao)'}
    ).values('hora').annotate(
        count=Count('id')
    ).order_by('hora')
    
    return {
        'por_status': list(performance_status),
        'por_dia_semana': list(performance_dia_semana),
        'por_hora': list(performance_hora),
    }


def _calcular_analise_custos(data_inicio, data_fim):
    """Calcula análise de custos."""
    
    # Custos totais por categoria
    custos_categoria = CustoLogistico.objects.filter(
        data_criacao__date__range=[data_inicio, data_fim]
    ).values('categoria').annotate(
        total=Sum('valor_total'),
        count=Count('id')
    ).order_by('-total')
    
    # Custos por transportadora
    custos_transportadora = CustoLogistico.objects.filter(
        data_criacao__date__range=[data_inicio, data_fim],
        transportadora__isnull=False
    ).values('transportadora__nome').annotate(
        total=Sum('valor_total'),
        count=Count('id')
    ).order_by('-total')
    
    # Evolução de custos (últimos 7 dias)
    evolucao_custos = []
    for i in range(7):
        data = data_fim - timedelta(days=i)
        total_dia = CustoLogistico.objects.filter(
            data_criacao__date=data
        ).aggregate(total=Sum('valor_total'))['total'] or Decimal('0')
        
        evolucao_custos.append({
            'data': data.strftime('%d/%m'),
            'total': float(total_dia)
        })
    
    evolucao_custos.reverse()
    
    return {
        'por_categoria': list(custos_categoria),
        'por_transportadora': list(custos_transportadora),
        'evolucao': evolucao_custos,
    }


def _calcular_metricas_sla(data_inicio, data_fim):
    """Calcula métricas de SLA."""
    
    # Entregas dentro do prazo
    entregas_com_prazo = RastreamentoEntrega.objects.filter(
        data_criacao__date__range=[data_inicio, data_fim],
        data_entrega_prevista__isnull=False,
        status_atual='ENTREGUE'
    )
    
    entregas_no_prazo = entregas_com_prazo.filter(
        data_entrega__lte=F('data_entrega_prevista')
    ).count()
    
    total_com_prazo = entregas_com_prazo.count()
    sla_percentual = (entregas_no_prazo / total_com_prazo * 100) if total_com_prazo > 0 else 0
    
    # Atrasos por transportadora
    atrasos_transportadora = RastreamentoEntrega.objects.filter(
        data_criacao__date__range=[data_inicio, data_fim],
        data_entrega_prevista__isnull=False,
        status_atual='ENTREGUE',
        data_entrega__gt=F('data_entrega_prevista'),
        transportadora__isnull=False
    ).values('transportadora__nome').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Tempo médio de atraso
    tempo_atraso = RastreamentoEntrega.objects.filter(
        data_criacao__date__range=[data_inicio, data_fim],
        data_entrega_prevista__isnull=False,
        status_atual='ENTREGUE',
        data_entrega__gt=F('data_entrega_prevista')
    ).aggregate(
        tempo_atraso=Avg(F('data_entrega') - F('data_entrega_prevista'))
    )['tempo_atraso']
    
    return {
        'sla_percentual': round(sla_percentual, 2),
        'entregas_no_prazo': entregas_no_prazo,
        'total_com_prazo': total_com_prazo,
        'atrasos_por_transportadora': list(atrasos_transportadora),
        'tempo_atraso_horas': round(tempo_atraso.total_seconds() / 3600, 1) if tempo_atraso else 0,
    }


def _calcular_analise_transportadoras(data_inicio, data_fim):
    """Calcula análise por transportadora."""
    
    transportadoras_data = []
    
    for transportadora in Transportadora.objects.filter(ativo=True):
        entregas = RastreamentoEntrega.objects.filter(
            transportadora=transportadora,
            data_criacao__date__range=[data_inicio, data_fim]
        )
        
        total_entregas = entregas.count()
        entregas_concluidas = entregas.filter(status_atual='ENTREGUE').count()
        taxa_sucesso = (entregas_concluidas / total_entregas * 100) if total_entregas > 0 else 0
        
        custo_total = CustoLogistico.objects.filter(
            transportadora=transportadora,
            data_criacao__date__range=[data_inicio, data_fim]
        ).aggregate(total=Sum('valor_total'))['total'] or Decimal('0')
        
        transportadoras_data.append({
            'nome': transportadora.nome,
            'total_entregas': total_entregas,
            'entregas_concluidas': entregas_concluidas,
            'taxa_sucesso': round(taxa_sucesso, 2),
            'custo_total': float(custo_total),
            'custo_medio': float(custo_total / total_entregas) if total_entregas > 0 else 0,
        })
    
    return sorted(transportadoras_data, key=lambda x: x['total_entregas'], reverse=True)


def _calcular_analise_regioes(data_inicio, data_fim):
    """Calcula análise por região."""
    
    regioes_data = RastreamentoEntrega.objects.filter(
        data_criacao__date__range=[data_inicio, data_fim]
    ).values('cidade_entrega').annotate(
        total_entregas=Count('id'),
        entregas_concluidas=Count('id', filter=Q(status_atual='ENTREGUE')),
        custo_total=Sum('custo_entrega')
    ).order_by('-total_entregas')
    
    return list(regioes_data)


def _calcular_tendencias():
    """Calcula tendências dos últimos 7 dias."""
    
    tendencias = []
    hoje = timezone.now().date()
    
    for i in range(7):
        data = hoje - timedelta(days=i)
        
        entregas_dia = RastreamentoEntrega.objects.filter(
            data_criacao__date=data
        ).count()
        
        entregas_concluidas_dia = RastreamentoEntrega.objects.filter(
            data_criacao__date=data,
            status_atual='ENTREGUE'
        ).count()
        
        custo_dia = CustoLogistico.objects.filter(
            data_criacao__date=data
        ).aggregate(total=Sum('valor_total'))['total'] or Decimal('0')
        
        tendencias.append({
            'data': data.strftime('%d/%m'),
            'entregas': entregas_dia,
            'concluidas': entregas_concluidas_dia,
            'custo': float(custo_dia),
        })
    
    return list(reversed(tendencias))


# =============================================================================
# RELATÓRIOS ESPECÍFICOS
# =============================================================================

@login_required
@require_stock_access
def relatorio_performance(request):
    """Relatório de performance logística."""
    
    data_inicio = request.GET.get('data_inicio', (timezone.now().date() - timedelta(days=30)).strftime('%Y-%m-%d'))
    data_fim = request.GET.get('data_fim', timezone.now().date().strftime('%Y-%m-%d'))
    
    formato = request.GET.get('formato', 'html')
    
    # Dados do relatório
    dados = _gerar_dados_relatorio_performance(data_inicio, data_fim)
    
    if formato == 'csv':
        return _exportar_csv_performance(dados, data_inicio, data_fim)
    elif formato == 'json':
        return JsonResponse(dados)
    
    context = {
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'dados': dados,
    }
    
    return render(request, 'stock/logistica/reports/relatorio_performance.html', context)


@login_required
@require_stock_access
def relatorio_custos(request):
    """Relatório de custos logísticos."""
    
    data_inicio = request.GET.get('data_inicio', (timezone.now().date() - timedelta(days=30)).strftime('%Y-%m-%d'))
    data_fim = request.GET.get('data_fim', timezone.now().date().strftime('%Y-%m-%d'))
    
    formato = request.GET.get('formato', 'html')
    
    # Dados do relatório
    dados = _gerar_dados_relatorio_custos(data_inicio, data_fim)
    
    if formato == 'csv':
        return _exportar_csv_custos(dados, data_inicio, data_fim)
    elif formato == 'json':
        return JsonResponse(dados)
    
    context = {
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'dados': dados,
    }
    
    return render(request, 'stock/logistica/reports/relatorio_custos.html', context)


@login_required
@require_stock_access
def relatorio_sla(request):
    """Relatório de SLA e pontualidade."""
    
    data_inicio = request.GET.get('data_inicio', (timezone.now().date() - timedelta(days=30)).strftime('%Y-%m-%d'))
    data_fim = request.GET.get('data_fim', timezone.now().date().strftime('%Y-%m-%d'))
    
    formato = request.GET.get('formato', 'html')
    
    # Dados do relatório
    dados = _gerar_dados_relatorio_sla(data_inicio, data_fim)
    
    if formato == 'csv':
        return _exportar_csv_sla(dados, data_inicio, data_fim)
    elif formato == 'json':
        return JsonResponse(dados)
    
    context = {
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'dados': dados,
    }
    
    return render(request, 'stock/logistica/reports/relatorio_sla.html', context)


# =============================================================================
# FUNÇÕES AUXILIARES PARA RELATÓRIOS
# =============================================================================

def _gerar_dados_relatorio_performance(data_inicio, data_fim):
    """Gera dados para relatório de performance."""
    
    data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
    data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
    
    # Performance geral
    total_entregas = RastreamentoEntrega.objects.filter(
        data_criacao__date__range=[data_inicio, data_fim]
    ).count()
    
    entregas_por_status = RastreamentoEntrega.objects.filter(
        data_criacao__date__range=[data_inicio, data_fim]
    ).values('status_atual').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Performance por transportadora
    performance_transportadoras = []
    for transportadora in Transportadora.objects.filter(ativo=True):
        entregas = RastreamentoEntrega.objects.filter(
            transportadora=transportadora,
            data_criacao__date__range=[data_inicio, data_fim]
        )
        
        total = entregas.count()
        concluidas = entregas.filter(status_atual='ENTREGUE').count()
        taxa_sucesso = (concluidas / total * 100) if total > 0 else 0
        
        performance_transportadoras.append({
            'transportadora': transportadora.nome,
            'total': total,
            'concluidas': concluidas,
            'taxa_sucesso': round(taxa_sucesso, 2),
        })
    
    # Performance por região
    performance_regioes = RastreamentoEntrega.objects.filter(
        data_criacao__date__range=[data_inicio, data_fim]
    ).values('cidade_entrega').annotate(
        total=Count('id'),
        concluidas=Count('id', filter=Q(status_atual='ENTREGUE'))
    ).order_by('-total')
    
    return {
        'total_entregas': total_entregas,
        'entregas_por_status': list(entregas_por_status),
        'performance_transportadoras': performance_transportadoras,
        'performance_regioes': list(performance_regioes),
    }


def _gerar_dados_relatorio_custos(data_inicio, data_fim):
    """Gera dados para relatório de custos."""
    
    data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
    data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
    
    # Custos por categoria
    custos_categoria = CustoLogistico.objects.filter(
        data_criacao__date__range=[data_inicio, data_fim]
    ).values('categoria').annotate(
        total=Sum('valor_total'),
        count=Count('id')
    ).order_by('-total')
    
    # Custos por transportadora
    custos_transportadora = CustoLogistico.objects.filter(
        data_criacao__date__range=[data_inicio, data_fim],
        transportadora__isnull=False
    ).values('transportadora__nome').annotate(
        total=Sum('valor_total'),
        count=Count('id')
    ).order_by('-total')
    
    # Evolução de custos
    evolucao_custos = []
    for i in range(30):  # Últimos 30 dias
        data = data_fim - timedelta(days=i)
        total_dia = CustoLogistico.objects.filter(
            data_criacao__date=data
        ).aggregate(total=Sum('valor_total'))['total'] or Decimal('0')
        
        evolucao_custos.append({
            'data': data.strftime('%d/%m'),
            'total': float(total_dia)
        })
    
    evolucao_custos.reverse()
    
    return {
        'custos_categoria': list(custos_categoria),
        'custos_transportadora': list(custos_transportadora),
        'evolucao_custos': evolucao_custos,
    }


def _gerar_dados_relatorio_sla(data_inicio, data_fim):
    """Gera dados para relatório de SLA."""
    
    data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
    data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
    
    # SLA geral
    entregas_com_prazo = RastreamentoEntrega.objects.filter(
        data_criacao__date__range=[data_inicio, data_fim],
        data_entrega_prevista__isnull=False,
        status_atual='ENTREGUE'
    )
    
    total_com_prazo = entregas_com_prazo.count()
    entregas_no_prazo = entregas_com_prazo.filter(
        data_entrega__lte=F('data_entrega_prevista')
    ).count()
    
    sla_percentual = (entregas_no_prazo / total_com_prazo * 100) if total_com_prazo > 0 else 0
    
    # SLA por transportadora
    sla_transportadoras = []
    for transportadora in Transportadora.objects.filter(ativo=True):
        entregas = RastreamentoEntrega.objects.filter(
            transportadora=transportadora,
            data_criacao__date__range=[data_inicio, data_fim],
            data_entrega_prevista__isnull=False,
            status_atual='ENTREGUE'
        )
        
        total = entregas.count()
        no_prazo = entregas.filter(data_entrega__lte=F('data_entrega_prevista')).count()
        sla = (no_prazo / total * 100) if total > 0 else 0
        
        sla_transportadoras.append({
            'transportadora': transportadora.nome,
            'total': total,
            'no_prazo': no_prazo,
            'sla': round(sla, 2),
        })
    
    return {
        'sla_percentual': round(sla_percentual, 2),
        'total_com_prazo': total_com_prazo,
        'entregas_no_prazo': entregas_no_prazo,
        'sla_transportadoras': sla_transportadoras,
    }


# =============================================================================
# EXPORTAÇÃO DE DADOS
# =============================================================================

def _exportar_csv_performance(dados, data_inicio, data_fim):
    """Exporta relatório de performance para CSV."""
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="performance_{data_inicio}_{data_fim}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Relatório de Performance Logística', f'{data_inicio} a {data_fim}'])
    writer.writerow([])
    
    # Performance geral
    writer.writerow(['Performance Geral'])
    writer.writerow(['Total de Entregas', dados['total_entregas']])
    writer.writerow([])
    
    # Por status
    writer.writerow(['Entregas por Status'])
    writer.writerow(['Status', 'Quantidade'])
    for item in dados['entregas_por_status']:
        writer.writerow([item['status_atual'], item['count']])
    writer.writerow([])
    
    # Por transportadora
    writer.writerow(['Performance por Transportadora'])
    writer.writerow(['Transportadora', 'Total', 'Concluídas', 'Taxa Sucesso (%)'])
    for item in dados['performance_transportadoras']:
        writer.writerow([item['transportadora'], item['total'], item['concluidas'], item['taxa_sucesso']])
    
    return response


def _exportar_csv_custos(dados, data_inicio, data_fim):
    """Exporta relatório de custos para CSV."""
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="custos_{data_inicio}_{data_fim}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Relatório de Custos Logísticos', f'{data_inicio} a {data_fim}'])
    writer.writerow([])
    
    # Por categoria
    writer.writerow(['Custos por Categoria'])
    writer.writerow(['Categoria', 'Total', 'Quantidade'])
    for item in dados['custos_categoria']:
        writer.writerow([item['categoria'], item['total'], item['count']])
    writer.writerow([])
    
    # Por transportadora
    writer.writerow(['Custos por Transportadora'])
    writer.writerow(['Transportadora', 'Total', 'Quantidade'])
    for item in dados['custos_transportadora']:
        writer.writerow([item['transportadora__nome'], item['total'], item['count']])
    
    return response


def _exportar_csv_sla(dados, data_inicio, data_fim):
    """Exporta relatório de SLA para CSV."""
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="sla_{data_inicio}_{data_fim}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Relatório de SLA e Pontualidade', f'{data_inicio} a {data_fim}'])
    writer.writerow([])
    
    # SLA geral
    writer.writerow(['SLA Geral'])
    writer.writerow(['SLA (%)', dados['sla_percentual']])
    writer.writerow(['Total com Prazo', dados['total_com_prazo']])
    writer.writerow(['Entregas no Prazo', dados['entregas_no_prazo']])
    writer.writerow([])
    
    # Por transportadora
    writer.writerow(['SLA por Transportadora'])
    writer.writerow(['Transportadora', 'Total', 'No Prazo', 'SLA (%)'])
    for item in dados['sla_transportadoras']:
        writer.writerow([item['transportadora'], item['total'], item['no_prazo'], item['sla']])
    
    return response
