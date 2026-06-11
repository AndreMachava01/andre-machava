"""
Views para gerenciamento de alocação automática de recursos logísticos.
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q, Count, Avg
from datetime import datetime, date, timedelta
import json
import logging

from .decorators import require_stock_access
from .models_stock import RastreamentoEntrega, Transportadora, VeiculoInterno
from .services.auto_allocation_service import (
    AutoAllocationService, AllocationCriteria, AllocationResult
)

logger = logging.getLogger(__name__)


@login_required
@require_stock_access
def allocation_dashboard(request):
    """Dashboard de alocação automática."""
    hoje = timezone.now().date()
    
    # Estatísticas gerais
    allocation_service = AutoAllocationService()
    stats = allocation_service.obter_estatisticas_alocacao()
    
    # Rastreamentos não alocados
    rastreamentos_nao_alocados = RastreamentoEntrega.objects.filter(
        veiculo_interno__isnull=True,
        transportadora__isnull=True,
        status_atual__in=['PENDENTE', 'PREPARANDO']
    ).order_by('-data_criacao')[:10]
    
    # Rastreamentos recentes alocados
    rastreamentos_alocados_recentes = RastreamentoEntrega.objects.filter(
        Q(veiculo_interno__isnull=False) | Q(transportadora__isnull=False),
        data_atualizacao__gte=timezone.now() - timedelta(days=1)
    ).order_by('-data_atualizacao')[:10]
    
    context = {
        'stats': stats,
        'rastreamentos_nao_alocados': rastreamentos_nao_alocados,
        'rastreamentos_alocados_recentes': rastreamentos_alocados_recentes,
    }
    
    return render(request, 'stock/logistica/allocation/dashboard.html', context)


@login_required
@require_stock_access
def allocation_criteria_config(request):
    """Configuração de critérios de alocação."""
    allocation_service = AutoAllocationService()
    
    if request.method == 'POST':
        try:
            # Criar novos critérios baseados no formulário
            criteria = AllocationCriteria(
                priorizar_custo=request.POST.get('priorizar_custo') == 'on',
                priorizar_sla=request.POST.get('priorizar_sla') == 'on',
                peso_custo=float(request.POST.get('peso_custo', 0.7)),
                peso_sla=float(request.POST.get('peso_sla', 0.3)),
                peso_capacidade=float(request.POST.get('peso_capacidade', 0.2)),
                peso_disponibilidade=float(request.POST.get('peso_disponibilidade', 0.1)),
                custo_maximo_diferenca=float(request.POST.get('custo_maximo_diferenca', 50.0)),
                sla_maximo_diferenca_dias=int(request.POST.get('sla_maximo_diferenca_dias', 2)),
                considerar_zonas=request.POST.get('considerar_zonas') == 'on',
                considerar_janelas_tempo=request.POST.get('considerar_janelas_tempo') == 'on'
            )
            
            allocation_service.configurar_criterios(criteria)
            messages.success(request, 'Critérios de alocação atualizados com sucesso!')
            return redirect('stock:allocation:dashboard')
            
        except Exception as e:
            logger.error(f"Erro ao configurar critérios: {e}")
            messages.error(request, f'Erro ao configurar critérios: {str(e)}')
    
    # GET - mostrar formulário com critérios atuais
    criteria_atual = allocation_service.criteria
    
    context = {
        'criteria': criteria_atual,
    }
    
    return render(request, 'stock/logistica/allocation/criteria_config.html', context)


@login_required
@require_stock_access
def allocation_single(request, rastreamento_id):
    """Alocação individual de um rastreamento."""
    rastreamento = get_object_or_404(RastreamentoEntrega, id=rastreamento_id)
    allocation_service = AutoAllocationService()
    
    if request.method == 'POST':
        try:
            # Obter critérios personalizados se fornecidos
            criteria_personalizados = None
            if request.POST.get('usar_criterios_personalizados') == 'on':
                criteria_personalizados = AllocationCriteria(
                    priorizar_custo=request.POST.get('priorizar_custo') == 'on',
                    priorizar_sla=request.POST.get('priorizar_sla') == 'on',
                    peso_custo=float(request.POST.get('peso_custo', 0.7)),
                    peso_sla=float(request.POST.get('peso_sla', 0.3)),
                    peso_capacidade=float(request.POST.get('peso_capacidade', 0.2)),
                    peso_disponibilidade=float(request.POST.get('peso_disponibilidade', 0.1)),
                    custo_maximo_diferenca=float(request.POST.get('custo_maximo_diferenca', 50.0)),
                    sla_maximo_diferenca_dias=int(request.POST.get('sla_maximo_diferenca_dias', 2)),
                    considerar_zonas=request.POST.get('considerar_zonas') == 'on',
                    considerar_janelas_tempo=request.POST.get('considerar_janelas_tempo') == 'on'
                )
            
            # Executar alocação
            resultado = allocation_service.alocar_rastreamento(
                rastreamento_id=rastreamento_id,
                criterios_personalizados=criteria_personalizados
            )
            
            # Aplicar alocação se solicitado
            if request.POST.get('aplicar_alocacao') == 'on':
                sucesso = allocation_service.aplicar_alocacao(resultado)
                if sucesso:
                    messages.success(request, 'Alocação aplicada com sucesso!')
                    return redirect('stock:logistica:rastreamento_detail', rastreamento_id=rastreamento_id)
                else:
                    messages.error(request, 'Erro ao aplicar alocação.')
            
            # Mostrar resultado
            context = {
                'rastreamento': rastreamento,
                'resultado': resultado,
                'criteria_usados': criteria_personalizados or allocation_service.criteria,
            }
            
            return render(request, 'stock/logistica/allocation/resultado.html', context)
            
        except Exception as e:
            logger.error(f"Erro na alocação individual: {e}")
            messages.error(request, f'Erro na alocação: {str(e)}')
    
    # GET - mostrar formulário
    context = {
        'rastreamento': rastreamento,
        'criteria_atual': allocation_service.criteria,
    }
    
    return render(request, 'stock/logistica/allocation/alocar_single.html', context)


@login_required
@require_stock_access
def allocation_batch(request):
    """Alocação em lote de múltiplos rastreamentos."""
    if request.method == 'POST':
        try:
            # Obter IDs dos rastreamentos
            rastreamentos_ids = request.POST.getlist('rastreamentos_ids')
            if not rastreamentos_ids:
                messages.error(request, 'Nenhum rastreamento selecionado.')
                return redirect('stock:allocation:batch')
            
            # Converter para inteiros
            rastreamentos_ids = [int(rid) for rid in rastreamentos_ids]
            
            # Obter critérios personalizados se fornecidos
            criteria_personalizados = None
            if request.POST.get('usar_criterios_personalizados') == 'on':
                criteria_personalizados = AllocationCriteria(
                    priorizar_custo=request.POST.get('priorizar_custo') == 'on',
                    priorizar_sla=request.POST.get('priorizar_sla') == 'on',
                    peso_custo=float(request.POST.get('peso_custo', 0.7)),
                    peso_sla=float(request.POST.get('peso_sla', 0.3)),
                    peso_capacidade=float(request.POST.get('peso_capacidade', 0.2)),
                    peso_disponibilidade=float(request.POST.get('peso_disponibilidade', 0.1)),
                    custo_maximo_diferenca=float(request.POST.get('custo_maximo_diferenca', 50.0)),
                    sla_maximo_diferenca_dias=int(request.POST.get('sla_maximo_diferenca_dias', 2)),
                    considerar_zonas=request.POST.get('considerar_zonas') == 'on',
                    considerar_janelas_tempo=request.POST.get('considerar_janelas_tempo') == 'on'
                )
            
            # Executar alocação em lote
            allocation_service = AutoAllocationService()
            resultados = allocation_service.alocar_lote(
                rastreamentos_ids=rastreamentos_ids,
                criterios_personalizados=criteria_personalizados
            )
            
            # Aplicar alocações se solicitado
            aplicados = 0
            erros = 0
            
            if request.POST.get('aplicar_alocacoes') == 'on':
                for resultado in resultados:
                    if resultado.opcao_recomendada != 'ERRO':
                        sucesso = allocation_service.aplicar_alocacao(resultado)
                        if sucesso:
                            aplicados += 1
                        else:
                            erros += 1
                    else:
                        erros += 1
            
            # Mostrar resultados
            context = {
                'resultados': resultados,
                'total_processados': len(resultados),
                'aplicados': aplicados,
                'erros': erros,
                'criteria_usados': criteria_personalizados or allocation_service.criteria,
            }
            
            return render(request, 'stock/logistica/allocation/resultado_batch.html', context)
            
        except Exception as e:
            logger.error(f"Erro na alocação em lote: {e}")
            messages.error(request, f'Erro na alocação em lote: {str(e)}')
    
    # GET - mostrar formulário
    # Rastreamentos não alocados para seleção
    rastreamentos_nao_alocados = RastreamentoEntrega.objects.filter(
        veiculo_interno__isnull=True,
        transportadora__isnull=True,
        status_atual__in=['PENDENTE', 'PREPARANDO']
    ).order_by('-data_criacao')
    
    # Paginação
    paginator = Paginator(rastreamentos_nao_alocados, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    allocation_service = AutoAllocationService()
    
    context = {
        'page_obj': page_obj,
        'criteria_atual': allocation_service.criteria,
    }
    
    return render(request, 'stock/logistica/allocation/alocar_batch.html', context)


@login_required
@require_stock_access
def allocation_history(request):
    """Histórico de alocações."""
    search = request.GET.get('search', '')
    tipo_alocacao = request.GET.get('tipo_alocacao', '')
    data_inicio = request.GET.get('data_inicio', '')
    data_fim = request.GET.get('data_fim', '')
    
    # Filtrar rastreamentos que foram alocados
    rastreamentos = RastreamentoEntrega.objects.filter(
        Q(veiculo_interno__isnull=False) | Q(transportadora__isnull=False)
    ).select_related('veiculo_interno', 'transportadora')
    
    if search:
        rastreamentos = rastreamentos.filter(
            Q(codigo_rastreamento__icontains=search) |
            Q(nome_destinatario__icontains=search) |
            Q(endereco_entrega__icontains=search)
        )
    
    if tipo_alocacao:
        if tipo_alocacao == 'VEICULO_INTERNO':
            rastreamentos = rastreamentos.filter(veiculo_interno__isnull=False)
        elif tipo_alocacao == 'TRANSPORTADORA':
            rastreamentos = rastreamentos.filter(transportadora__isnull=False)
    
    if data_inicio:
        rastreamentos = rastreamentos.filter(data_atualizacao__date__gte=data_inicio)
    
    if data_fim:
        rastreamentos = rastreamentos.filter(data_atualizacao__date__lte=data_fim)
    
    rastreamentos = rastreamentos.order_by('-data_atualizacao')
    
    # Paginação
    paginator = Paginator(rastreamentos, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'tipo_alocacao': tipo_alocacao,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
    }
    
    return render(request, 'stock/logistica/allocation/history.html', context)


@login_required
@require_stock_access
def allocation_stats(request):
    """Estatísticas detalhadas de alocação."""
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
    allocation_service = AutoAllocationService()
    stats = allocation_service.obter_estatisticas_alocacao(
        data_inicio=data_inicio_obj,
        data_fim=data_fim_obj
    )
    
    # Estatísticas por transportadora
    transportadoras_stats = Transportadora.objects.filter(
        ativo=True,
        rastreamentoentrega__isnull=False
    ).annotate(
        total_rastreamentos=Count('rastreamentoentrega'),
        custo_medio=Avg('rastreamentoentrega__custo_estimado'),
        sla_medio=Avg('rastreamentoentrega__sla_estimado_dias')
    ).order_by('-total_rastreamentos')
    
    # Estatísticas por veículo interno
    veiculos_stats = VeiculoInterno.objects.filter(
        ativo=True,
        rastreamentoentrega__isnull=False
    ).annotate(
        total_rastreamentos=Count('rastreamentoentrega'),
        custo_medio=Avg('rastreamentoentrega__custo_estimado'),
        sla_medio=Avg('rastreamentoentrega__sla_estimado_dias')
    ).order_by('-total_rastreamentos')
    
    context = {
        'stats': stats,
        'transportadoras_stats': transportadoras_stats,
        'veiculos_stats': veiculos_stats,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
    }
    
    return render(request, 'stock/logistica/allocation/stats.html', context)


@login_required
@require_stock_access
def api_allocation_preview(request, rastreamento_id):
    """API para preview de alocação sem aplicar."""
    try:
        allocation_service = AutoAllocationService()
        resultado = allocation_service.alocar_rastreamento(rastreamento_id)
        
        return JsonResponse({
            'success': True,
            'resultado': {
                'opcao_recomendada': resultado.opcao_recomendada,
                'opcao_id': resultado.opcao_id,
                'custo_estimado': float(resultado.custo_estimado),
                'sla_estimado_dias': resultado.sla_estimado_dias,
                'pontuacao': resultado.pontuacao,
                'motivo': resultado.motivo,
                'alternativas': [
                    {
                        'tipo': alt['tipo'],
                        'nome': alt['nome'],
                        'custo': float(alt['custo']),
                        'sla_dias': alt['sla_dias'],
                        'pontuacao': alt['pontuacao']
                    }
                    for alt in resultado.alternativas[:3]
                ]
            }
        })
        
    except Exception as e:
        logger.error(f"Erro no preview de alocação: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@require_stock_access
def api_apply_allocation(request, rastreamento_id):
    """API para aplicar alocação."""
    try:
        data = json.loads(request.body)
        
        # Criar resultado baseado nos dados fornecidos
        resultado = AllocationResult(
            rastreamento_id=rastreamento_id,
            opcao_recomendada=data.get('opcao_recomendada'),
            opcao_id=data.get('opcao_id'),
            custo_estimado=float(data.get('custo_estimado', 0)),
            sla_estimado_dias=data.get('sla_estimado_dias', 0),
            pontuacao=data.get('pontuacao', 0.0),
            motivo=data.get('motivo', '')
        )
        
        allocation_service = AutoAllocationService()
        sucesso = allocation_service.aplicar_alocacao(resultado)
        
        if sucesso:
            return JsonResponse({
                'success': True,
                'message': 'Alocação aplicada com sucesso.'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Erro ao aplicar alocação.'
            })
            
    except Exception as e:
        logger.error(f"Erro ao aplicar alocação: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })
