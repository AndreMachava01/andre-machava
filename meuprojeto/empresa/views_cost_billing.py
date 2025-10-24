"""
Views para gestão de custos e faturamento logístico.
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum, Avg
from datetime import datetime, date, timedelta
from decimal import Decimal
import json
import logging

from .decorators import require_stock_access
from .models_cost_billing import (
    CentroCusto, TipoCusto, CustoLogistico, RateioCusto,
    FaturamentoFrete, ItemFaturamento, ConfiguracaoFaturamento
)
from .models_stock import RastreamentoEntrega
from .services.cost_billing_service import CostBillingService

logger = logging.getLogger(__name__)


@login_required
@require_stock_access
def cost_billing_dashboard(request):
    """Dashboard de custos e faturamento."""
    hoje = timezone.now().date()
    
    # Estatísticas gerais
    cost_service = CostBillingService()
    stats_custos = cost_service.obter_estatisticas_custos()
    stats_faturamento = cost_service.obter_estatisticas_faturamento()
    
    # Custos pendentes de aprovação
    custos_pendentes = CustoLogistico.objects.filter(
        status='PENDENTE'
    ).order_by('-data_criacao')[:10]
    
    # Faturas pendentes de pagamento
    faturas_pendentes = FaturamentoFrete.objects.filter(
        status__in=['ENVIADO', 'VENCIDO']
    ).order_by('-data_emissao')[:10]
    
    # Custos recentes
    custos_recentes = CustoLogistico.objects.filter(
        data_criacao__gte=timezone.now() - timedelta(days=7)
    ).order_by('-data_criacao')[:10]
    
    context = {
        'stats_custos': stats_custos,
        'stats_faturamento': stats_faturamento,
        'custos_pendentes': custos_pendentes,
        'faturas_pendentes': faturas_pendentes,
        'custos_recentes': custos_recentes,
    }
    
    return render(request, 'stock/logistica/cost_billing/dashboard.html', context)


@login_required
@require_stock_access
def custos_list(request):
    """Lista de custos logísticos."""
    search = request.GET.get('search', '')
    status = request.GET.get('status', '')
    tipo_custo = request.GET.get('tipo_custo', '')
    centro_custo = request.GET.get('centro_custo', '')
    data_inicio = request.GET.get('data_inicio', '')
    data_fim = request.GET.get('data_fim', '')
    
    custos = CustoLogistico.objects.select_related(
        'tipo_custo', 'centro_custo', 'rastreamento_entrega', 'criado_por'
    )
    
    if search:
        custos = custos.filter(
            Q(codigo__icontains=search) |
            Q(descricao__icontains=search) |
            Q(numero_documento__icontains=search)
        )
    
    if status:
        custos = custos.filter(status=status)
    
    if tipo_custo:
        custos = custos.filter(tipo_custo_id=tipo_custo)
    
    if centro_custo:
        custos = custos.filter(centro_custo_id=centro_custo)
    
    if data_inicio:
        custos = custos.filter(data_custo__gte=data_inicio)
    
    if data_fim:
        custos = custos.filter(data_custo__lte=data_fim)
    
    custos = custos.order_by('-data_custo', '-data_criacao')
    
    # Paginação
    paginator = Paginator(custos, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Opções para filtros
    status_choices = CustoLogistico.STATUS_CHOICES
    tipos_custo = TipoCusto.objects.filter(ativo=True)
    centros_custo = CentroCusto.objects.filter(ativo=True)
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'status': status,
        'tipo_custo': tipo_custo,
        'centro_custo': centro_custo,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'status_choices': status_choices,
        'tipos_custo': tipos_custo,
        'centros_custo': centros_custo,
    }
    
    return render(request, 'stock/logistica/cost_billing/custos_list.html', context)


@login_required
@require_stock_access
def custo_detail(request, custo_id):
    """Detalhes de um custo logístico."""
    custo = get_object_or_404(CustoLogistico, id=custo_id)
    
    # Rateios relacionados
    rateios = custo.rateios.all().order_by('-data_criacao')
    
    context = {
        'custo': custo,
        'rateios': rateios,
    }
    
    return render(request, 'stock/logistica/cost_billing/custo_detail.html', context)


@login_required
@require_stock_access
def custo_create(request):
    """Criar novo custo logístico."""
    cost_service = CostBillingService()
    
    if request.method == 'POST':
        try:
            custo = cost_service.registrar_custo_logistico(
                rastreamento_id=request.POST.get('rastreamento_entrega') or None,
                tipo_custo_id=request.POST.get('tipo_custo'),
                centro_custo_id=request.POST.get('centro_custo'),
                descricao=request.POST.get('descricao'),
                valor=request.POST.get('valor'),
                data_custo=request.POST.get('data_custo'),
                numero_documento=request.POST.get('numero_documento', ''),
                arquivo_comprovante=request.FILES.get('arquivo_comprovante'),
                criado_por_id=request.user.id
            )
            
            messages.success(request, 'Custo logístico registrado com sucesso!')
            return redirect('stock:cost_billing:custo_detail', custo_id=custo.id)
            
        except Exception as e:
            logger.error(f"Erro ao criar custo: {e}")
            messages.error(request, f'Erro ao criar custo: {str(e)}')
    
    # GET - mostrar formulário
    tipos_custo = TipoCusto.objects.filter(ativo=True)
    centros_custo = CentroCusto.objects.filter(ativo=True)
    rastreamentos = RastreamentoEntrega.objects.filter(
        status_atual__in=['ENTREGUE', 'ENTREGUE_PARCIAL', 'EM_TRANSITO']
    ).order_by('-data_criacao')
    
    context = {
        'tipos_custo': tipos_custo,
        'centros_custo': centros_custo,
        'rastreamentos': rastreamentos,
    }
    
    return render(request, 'stock/logistica/cost_billing/custo_form.html', context)


@login_required
@require_stock_access
def custo_approve(request, custo_id):
    """Aprovar custo logístico."""
    if request.method == 'POST':
        try:
            cost_service = CostBillingService()
            custo = cost_service.aprovar_custo_logistico(
                custo_id=custo_id,
                aprovado_por_id=request.user.id,
                observacoes=request.POST.get('observacoes', '')
            )
            
            messages.success(request, 'Custo logístico aprovado com sucesso!')
            return redirect('stock:cost_billing:custo_detail', custo_id=custo.id)
            
        except Exception as e:
            logger.error(f"Erro ao aprovar custo: {e}")
            messages.error(request, f'Erro ao aprovar custo: {str(e)}')
    
    custo = get_object_or_404(CustoLogistico, id=custo_id)
    
    context = {
        'custo': custo,
    }
    
    return render(request, 'stock/logistica/cost_billing/custo_approve.html', context)


@login_required
@require_stock_access
def custo_reject(request, custo_id):
    """Rejeitar custo logístico."""
    if request.method == 'POST':
        try:
            cost_service = CostBillingService()
            custo = cost_service.rejeitar_custo_logistico(
                custo_id=custo_id,
                rejeitado_por_id=request.user.id,
                motivo_rejeicao=request.POST.get('motivo_rejeicao', '')
            )
            
            messages.success(request, 'Custo logístico rejeitado.')
            return redirect('stock:cost_billing:custo_detail', custo_id=custo.id)
            
        except Exception as e:
            logger.error(f"Erro ao rejeitar custo: {e}")
            messages.error(request, f'Erro ao rejeitar custo: {str(e)}')
    
    custo = get_object_or_404(CustoLogistico, id=custo_id)
    
    context = {
        'custo': custo,
    }
    
    return render(request, 'stock/logistica/cost_billing/custo_reject.html', context)


@login_required
@require_stock_access
def rateio_create(request, custo_id):
    """Criar rateio manual para custo."""
    custo = get_object_or_404(CustoLogistico, id=custo_id)
    
    if request.method == 'POST':
        try:
            # Processar dados do formulário
            rateios_data = []
            for key, value in request.POST.items():
                if key.startswith('centro_custo_') and value:
                    centro_id = value
                    valor_key = f'valor_{centro_id}'
                    percentual_key = f'percentual_{centro_id}'
                    
                    if valor_key in request.POST and percentual_key in request.POST:
                        rateios_data.append({
                            'centro_custo_id': centro_id,
                            'valor_rateado': request.POST[valor_key],
                            'percentual_rateio': request.POST[percentual_key]
                        })
            
            cost_service = CostBillingService()
            rateios = cost_service.criar_rateio_manual(
                custo_id=custo_id,
                rateios=rateios_data,
                criado_por_id=request.user.id
            )
            
            messages.success(request, 'Rateio criado com sucesso!')
            return redirect('stock:cost_billing:custo_detail', custo_id=custo.id)
            
        except Exception as e:
            logger.error(f"Erro ao criar rateio: {e}")
            messages.error(request, f'Erro ao criar rateio: {str(e)}')
    
    # GET - mostrar formulário
    centros_custo = CentroCusto.objects.filter(ativo=True)
    
    context = {
        'custo': custo,
        'centros_custo': centros_custo,
    }
    
    return render(request, 'stock/logistica/cost_billing/rateio_form.html', context)


@login_required
@require_stock_access
def faturas_list(request):
    """Lista de faturas de frete."""
    search = request.GET.get('search', '')
    status = request.GET.get('status', '')
    data_inicio = request.GET.get('data_inicio', '')
    data_fim = request.GET.get('data_fim', '')
    
    faturas = FaturamentoFrete.objects.select_related('emitido_por')
    
    if search:
        faturas = faturas.filter(
            Q(numero_fatura__icontains=search) |
            Q(cliente_nome__icontains=search) |
            Q(cliente_documento__icontains=search)
        )
    
    if status:
        faturas = faturas.filter(status=status)
    
    if data_inicio:
        faturas = faturas.filter(data_emissao__gte=data_inicio)
    
    if data_fim:
        faturas = faturas.filter(data_emissao__lte=data_fim)
    
    faturas = faturas.order_by('-data_emissao', '-numero_fatura')
    
    # Paginação
    paginator = Paginator(faturas, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Opções para filtros
    status_choices = FaturamentoFrete.STATUS_CHOICES
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'status': status,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'status_choices': status_choices,
    }
    
    return render(request, 'stock/logistica/cost_billing/faturas_list.html', context)


@login_required
@require_stock_access
def fatura_detail(request, fatura_id):
    """Detalhes de uma fatura de frete."""
    fatura = get_object_or_404(FaturamentoFrete, id=fatura_id)
    
    # Itens da fatura
    itens = fatura.itens.all().order_by('data_servico')
    
    context = {
        'fatura': fatura,
        'itens': itens,
    }
    
    return render(request, 'stock/logistica/cost_billing/fatura_detail.html', context)


@login_required
@require_stock_access
def fatura_create(request):
    """Criar nova fatura de frete."""
    cost_service = CostBillingService()
    
    if request.method == 'POST':
        try:
            # Processar dados do cliente
            cliente_dados = {
                'nome': request.POST.get('cliente_nome'),
                'documento': request.POST.get('cliente_documento'),
                'endereco': request.POST.get('cliente_endereco'),
                'email': request.POST.get('cliente_email', '')
            }
            
            # Processar rastreamentos selecionados
            rastreamentos_ids = request.POST.getlist('rastreamentos_ids')
            if not rastreamentos_ids:
                raise ValueError("Nenhum rastreamento selecionado")
            
            # Processar período
            periodo_inicio = datetime.strptime(request.POST.get('periodo_inicio'), '%Y-%m-%d').date()
            periodo_fim = datetime.strptime(request.POST.get('periodo_fim'), '%Y-%m-%d').date()
            
            # Processar desconto
            desconto_percentual = Decimal(request.POST.get('desconto_percentual', '0.00'))
            
            fatura = cost_service.gerar_faturamento_frete(
                cliente_dados=cliente_dados,
                rastreamentos_ids=rastreamentos_ids,
                periodo_inicio=periodo_inicio,
                periodo_fim=periodo_fim,
                emitido_por_id=request.user.id,
                observacoes=request.POST.get('observacoes', ''),
                desconto_percentual=desconto_percentual
            )
            
            messages.success(request, 'Fatura de frete gerada com sucesso!')
            return redirect('stock:cost_billing:fatura_detail', fatura_id=fatura.id)
            
        except Exception as e:
            logger.error(f"Erro ao criar fatura: {e}")
            messages.error(request, f'Erro ao criar fatura: {str(e)}')
    
    # GET - mostrar formulário
    # Rastreamentos elegíveis para faturamento
    rastreamentos = RastreamentoEntrega.objects.filter(
        status_atual__in=['ENTREGUE', 'ENTREGUE_PARCIAL'],
        custo_estimado__gt=0
    ).order_by('-data_criacao')
    
    context = {
        'rastreamentos': rastreamentos,
        'config': cost_service.config_padrao,
    }
    
    return render(request, 'stock/logistica/cost_billing/fatura_form.html', context)


@login_required
@require_stock_access
def fatura_send(request, fatura_id):
    """Enviar fatura para o cliente."""
    try:
        cost_service = CostBillingService()
        fatura = cost_service.enviar_faturamento(fatura_id)
        
        messages.success(request, 'Fatura enviada com sucesso!')
        return redirect('stock:cost_billing:fatura_detail', fatura_id=fatura.id)
        
    except Exception as e:
        logger.error(f"Erro ao enviar fatura: {e}")
        messages.error(request, f'Erro ao enviar fatura: {str(e)}')
        return redirect('stock:cost_billing:fatura_detail', fatura_id=fatura_id)


@login_required
@require_stock_access
def fatura_mark_paid(request, fatura_id):
    """Marcar fatura como paga."""
    if request.method == 'POST':
        try:
            data_pagamento = None
            if request.POST.get('data_pagamento'):
                data_pagamento = datetime.strptime(request.POST.get('data_pagamento'), '%Y-%m-%d').date()
            
            cost_service = CostBillingService()
            fatura = cost_service.marcar_faturamento_pago(fatura_id, data_pagamento)
            
            messages.success(request, 'Fatura marcada como paga!')
            return redirect('stock:cost_billing:fatura_detail', fatura_id=fatura.id)
            
        except Exception as e:
            logger.error(f"Erro ao marcar fatura como paga: {e}")
            messages.error(request, f'Erro ao marcar fatura como paga: {str(e)}')
    
    fatura = get_object_or_404(FaturamentoFrete, id=fatura_id)
    
    context = {
        'fatura': fatura,
    }
    
    return render(request, 'stock/logistica/cost_billing/fatura_mark_paid.html', context)


@login_required
@require_stock_access
def cost_billing_stats(request):
    """Estatísticas detalhadas de custos e faturamento."""
    data_inicio = request.GET.get('data_inicio', '')
    data_fim = request.GET.get('data_fim', '')
    
    # Converter datas
    data_inicio_obj = None
    data_fim_obj = None
    
    if data_inicio:
        try:
            data_inicio_obj = datetime.strptime(data_inicio, '%Y-%m-%d').date()
        except ValueError:
            pass
    
    if data_fim:
        try:
            data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d').date()
        except ValueError:
            pass
    
    # Obter estatísticas
    cost_service = CostBillingService()
    stats_custos = cost_service.obter_estatisticas_custos(
        data_inicio=data_inicio_obj,
        data_fim=data_fim_obj
    )
    stats_faturamento = cost_service.obter_estatisticas_faturamento(
        data_inicio=data_inicio_obj,
        data_fim=data_fim_obj
    )
    
    # Estatísticas por tipo de custo
    tipos_custo_stats = TipoCusto.objects.filter(
        ativo=True,
        custologistico__isnull=False
    ).annotate(
        total_custos=Count('custologistico'),
        valor_total=Sum('custologistico__valor')
    ).order_by('-valor_total')
    
    # Estatísticas por centro de custo
    centros_custo_stats = CentroCusto.objects.filter(
        ativo=True,
        custologistico__isnull=False
    ).annotate(
        total_custos=Count('custologistico'),
        valor_total=Sum('custologistico__valor')
    ).order_by('-valor_total')
    
    context = {
        'stats_custos': stats_custos,
        'stats_faturamento': stats_faturamento,
        'tipos_custo_stats': tipos_custo_stats,
        'centros_custo_stats': centros_custo_stats,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
    }
    
    return render(request, 'stock/logistica/cost_billing/stats.html', context)
