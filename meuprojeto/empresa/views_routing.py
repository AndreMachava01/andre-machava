"""
Views para roteirização e planejamento logístico.
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
from .models_routing import (
    ZonaEntrega, Rota, ParadaRota, PlanejamentoEntrega, ConfiguracaoRoteirizacao
)
from .models_stock import VeiculoInterno, RastreamentoEntrega
from .services.routing_service import RoutingService

logger = logging.getLogger(__name__)


# =============================================================================
# ZONAS DE ENTREGA
# =============================================================================

@login_required
@require_stock_access
def zonas_entrega_list(request):
    """Lista de zonas de entrega."""
    search = request.GET.get('search', '')
    provincia = request.GET.get('provincia', '')
    ativo = request.GET.get('ativo', '')
    
    zonas = ZonaEntrega.objects.all()
    
    if search:
        zonas = zonas.filter(
            Q(nome__icontains=search) |
            Q(codigo__icontains=search) |
            Q(cidade__icontains=search) |
            Q(bairros__icontains=search)
        )
    
    if provincia:
        zonas = zonas.filter(provincia__iexact=provincia)
    
    if ativo:
        zonas = zonas.filter(ativo=ativo == 'true')
    
    zonas = zonas.order_by('provincia', 'cidade', 'nome')
    
    # Paginação
    paginator = Paginator(zonas, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Opções para filtros
    provincias = ZonaEntrega.objects.values_list('provincia', flat=True).distinct().order_by('provincia')
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'provincia': provincia,
        'ativo': ativo,
        'provincias': provincias,
    }
    
    return render(request, 'stock/logistica/routing/zonas_list.html', context)


@login_required
@require_stock_access
def zona_entrega_detail(request, zona_id):
    """Detalhes de uma zona de entrega."""
    zona = get_object_or_404(ZonaEntrega, id=zona_id)
    
    # Estatísticas da zona
    planejamentos = PlanejamentoEntrega.objects.filter(zona_entrega=zona)
    rotas = Rota.objects.filter(zonas_destino=zona)
    
    stats = {
        'total_planejamentos': planejamentos.count(),
        'planejamentos_pendentes': planejamentos.filter(status='PENDENTE').count(),
        'planejamentos_agendados': planejamentos.filter(status='AGENDADA').count(),
        'total_rotas': rotas.count(),
        'rotas_planejadas': rotas.filter(status='PLANEJADA').count(),
        'rotas_executadas': rotas.filter(status='EM_EXECUCAO').count(),
    }
    
    context = {
        'zona': zona,
        'stats': stats,
    }
    
    return render(request, 'stock/logistica/routing/zona_detail.html', context)


# =============================================================================
# PLANEJAMENTO DE ENTREGAS
# =============================================================================

@login_required
@require_stock_access
def planejamentos_list(request):
    """Lista de planejamentos de entrega."""
    search = request.GET.get('search', '')
    status = request.GET.get('status', '')
    prioridade = request.GET.get('prioridade', '')
    data_inicio = request.GET.get('data_inicio', '')
    data_fim = request.GET.get('data_fim', '')
    
    planejamentos = PlanejamentoEntrega.objects.select_related(
        'zona_entrega', 'rota_atribuida', 'rastreamento_entrega'
    )
    
    if search:
        planejamentos = planejamentos.filter(
            Q(codigo__icontains=search) |
            Q(endereco_completo__icontains=search) |
            Q(cidade__icontains=search) |
            Q(contato_nome__icontains=search)
        )
    
    if status:
        planejamentos = planejamentos.filter(status=status)
    
    if prioridade:
        planejamentos = planejamentos.filter(prioridade=prioridade)
    
    if data_inicio:
        planejamentos = planejamentos.filter(data_entrega_preferida__gte=data_inicio)
    
    if data_fim:
        planejamentos = planejamentos.filter(data_entrega_preferida__lte=data_fim)
    
    planejamentos = planejamentos.order_by('-data_entrega_preferida', 'prioridade', 'janela_inicio')
    
    # Paginação
    paginator = Paginator(planejamentos, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Opções para filtros
    status_choices = PlanejamentoEntrega.STATUS_CHOICES
    prioridade_choices = PlanejamentoEntrega.PRIORIDADE_CHOICES
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'status': status,
        'prioridade': prioridade,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'status_choices': status_choices,
        'prioridade_choices': prioridade_choices,
    }
    
    return render(request, 'stock/logistica/routing/planejamentos_list.html', context)


@login_required
@require_stock_access
def planejamento_create(request):
    """Criar novo planejamento de entrega."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # Validar dados obrigatórios
            rastreamento_id = data.get('rastreamento_id')
            if not rastreamento_id:
                return JsonResponse({'success': False, 'error': 'Rastreamento é obrigatório'})
            
            rastreamento = get_object_or_404(RastreamentoEntrega, id=rastreamento_id)
            
            # Criar planejamento
            routing_service = RoutingService()
            planejamento = routing_service.criar_planejamento_entrega(
                rastreamento=rastreamento,
                endereco=data.get('endereco', ''),
                cidade=data.get('cidade', ''),
                provincia=data.get('provincia', ''),
                data_entrega=datetime.strptime(data.get('data_entrega'), '%Y-%m-%d').date(),
                janela_inicio=datetime.strptime(data.get('janela_inicio'), '%H:%M').time(),
                janela_fim=datetime.strptime(data.get('janela_fim'), '%H:%M').time(),
                prioridade=data.get('prioridade', 'NORMAL'),
                observacoes=data.get('observacoes', ''),
                contato_nome=data.get('contato_nome', ''),
                contato_telefone=data.get('contato_telefone', ''),
                contato_email=data.get('contato_email', '')
            )
            
            return JsonResponse({
                'success': True,
                'planejamento_id': planejamento.id,
                'codigo': planejamento.codigo
            })
            
        except Exception as e:
            logger.error(f"Erro ao criar planejamento: {e}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    # GET - mostrar formulário
    rastreamentos = RastreamentoEntrega.objects.filter(
        status_atual__in=['PENDENTE', 'COLETADO']
    ).select_related('transportadora', 'veiculo_interno')
    
    context = {
        'rastreamentos': rastreamentos,
        'prioridade_choices': PlanejamentoEntrega.PRIORIDADE_CHOICES,
    }
    
    return render(request, 'stock/logistica/routing/planejamento_form.html', context)


# =============================================================================
# ROTAS E OTIMIZAÇÃO
# =============================================================================

@login_required
@require_stock_access
def rotas_list(request):
    """Lista de rotas."""
    search = request.GET.get('search', '')
    status = request.GET.get('status', '')
    data_inicio = request.GET.get('data_inicio', '')
    data_fim = request.GET.get('data_fim', '')
    
    rotas = Rota.objects.select_related(
        'zona_origem', 'veiculo_interno', 'motorista'
    ).prefetch_related('paradas', 'zonas_destino')
    
    if search:
        rotas = rotas.filter(
            Q(codigo__icontains=search) |
            Q(nome__icontains=search) |
            Q(descricao__icontains=search)
        )
    
    if status:
        rotas = rotas.filter(status=status)
    
    if data_inicio:
        rotas = rotas.filter(data_planejada__gte=data_inicio)
    
    if data_fim:
        rotas = rotas.filter(data_planejada__lte=data_fim)
    
    rotas = rotas.order_by('-data_planejada', 'hora_inicio_prevista')
    
    # Paginação
    paginator = Paginator(rotas, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Opções para filtros
    status_choices = Rota.STATUS_CHOICES
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'status': status,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'status_choices': status_choices,
    }
    
    return render(request, 'stock/logistica/routing/rotas_list.html', context)


@login_required
@require_stock_access
def rota_detail(request, rota_id):
    """Detalhes de uma rota."""
    rota = get_object_or_404(Rota, id=rota_id)
    
    # Paradas ordenadas por sequência
    paradas = rota.paradas.all().order_by('sequencia')
    
    # Estatísticas da rota
    stats = {
        'total_paradas': paradas.count(),
        'paradas_concluidas': paradas.filter(status='CONCLUIDA').count(),
        'paradas_pendentes': paradas.filter(status='PENDENTE').count(),
        'paradas_problema': paradas.filter(status='PROBLEMA').count(),
        'tempo_total_previsto': paradas.aggregate(
            total=Sum('tempo_estimado_minutos')
        )['total'] or 0,
    }
    
    context = {
        'rota': rota,
        'paradas': paradas,
        'stats': stats,
    }
    
    return render(request, 'stock/logistica/routing/rota_detail.html', context)


@login_required
@require_stock_access
def otimizar_rotas(request):
    """Otimizar rotas para uma data específica."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            data_otimizacao = datetime.strptime(data.get('data'), '%Y-%m-%d').date()
            veiculos_ids = data.get('veiculos_ids', [])
            zonas_ids = data.get('zonas_ids', [])
            
            # Executar otimização
            routing_service = RoutingService()
            rotas_otimizadas = routing_service.otimizar_rotas(
                data=data_otimizacao,
                veiculos_disponiveis=veiculos_ids if veiculos_ids else None,
                zonas=zonas_ids if zonas_ids else None
            )
            
            if not rotas_otimizadas:
                return JsonResponse({
                    'success': False,
                    'message': 'Nenhuma rota foi gerada. Verifique se há planejamentos pendentes e veículos disponíveis.'
                })
            
            # Salvar rotas otimizadas
            rotas_salvas = routing_service.salvar_rotas_otimizadas(
                rotas=rotas_otimizadas,
                data=data_otimizacao,
                criado_por_id=request.user.id
            )
            
            return JsonResponse({
                'success': True,
                'rotas_criadas': len(rotas_salvas),
                'rotas_ids': [r.id for r in rotas_salvas],
                'message': f'{len(rotas_salvas)} rotas foram criadas com sucesso.'
            })
            
        except Exception as e:
            logger.error(f"Erro ao otimizar rotas: {e}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    # GET - mostrar formulário de otimização
    veiculos = VeiculoInterno.objects.filter(status='ATIVO', disponivel=True)
    zonas = ZonaEntrega.objects.filter(ativo=True)
    
    # Data padrão: amanhã
    data_padrao = (timezone.now() + timedelta(days=1)).date()
    
    context = {
        'veiculos': veiculos,
        'zonas': zonas,
        'data_padrao': data_padrao,
    }
    
    return render(request, 'stock/logistica/routing/otimizar_rotas.html', context)


@login_required
@require_stock_access
def dashboard_roteirizacao(request):
    """Dashboard de roteirização."""
    hoje = timezone.now().date()
    
    # Estatísticas gerais
    stats = {
        'planejamentos_pendentes': PlanejamentoEntrega.objects.filter(status='PENDENTE').count(),
        'planejamentos_agendados': PlanejamentoEntrega.objects.filter(status='AGENDADA').count(),
        'rotas_planejadas': Rota.objects.filter(status='PLANEJADA').count(),
        'rotas_executando': Rota.objects.filter(status='EM_EXECUCAO').count(),
        'veiculos_disponiveis': VeiculoInterno.objects.filter(status='ATIVO', disponivel=True).count(),
        'zonas_ativas': ZonaEntrega.objects.filter(ativo=True).count(),
    }
    
    # Planejamentos por prioridade
    planejamentos_prioridade = PlanejamentoEntrega.objects.filter(
        status='PENDENTE'
    ).values('prioridade').annotate(
        count=Count('id')
    ).order_by('prioridade')
    
    # Rotas por status
    rotas_status = Rota.objects.values('status').annotate(
        count=Count('id')
    ).order_by('status')
    
    # Planejamentos próximos (próximos 7 dias)
    proximos_7_dias = PlanejamentoEntrega.objects.filter(
        data_entrega_preferida__range=[hoje, hoje + timedelta(days=7)],
        status='PENDENTE'
    ).order_by('data_entrega_preferida', 'prioridade')
    
    context = {
        'stats': stats,
        'planejamentos_prioridade': planejamentos_prioridade,
        'rotas_status': rotas_status,
        'proximos_7_dias': proximos_7_dias[:10],  # Limitar a 10
    }
    
    return render(request, 'stock/logistica/routing/dashboard.html', context)


# =============================================================================
# CONFIGURAÇÕES DE ROTEIRIZAÇÃO
# =============================================================================

@login_required
@require_stock_access
def configuracoes_roteirizacao(request):
    """Configurações de roteirização."""
    configs = ConfiguracaoRoteirizacao.objects.filter(ativo=True).order_by('-padrao', 'nome')
    
    context = {
        'configuracoes': configs,
    }
    
    return render(request, 'stock/logistica/routing/configuracoes.html', context)


@login_required
@require_stock_access
def configuracao_create(request):
    """Criar nova configuração de roteirização."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            config = ConfiguracaoRoteirizacao.objects.create(
                nome=data.get('nome', ''),
                descricao=data.get('descricao', ''),
                capacidade_maxima_veiculo=data.get('capacidade_maxima_veiculo', 50),
                tempo_maximo_rota_horas=data.get('tempo_maximo_rota_horas', 8),
                distancia_maxima_rota_km=data.get('distancia_maxima_rota_km', 200),
                peso_tempo=data.get('peso_tempo', 1.0),
                peso_distancia=data.get('peso_distancia', 1.0),
                peso_prioridade=data.get('peso_prioridade', 2.0),
                considerar_trafego=data.get('considerar_trafego', True),
                considerar_janelas_tempo=data.get('considerar_janelas_tempo', True),
                agrupar_por_zona=data.get('agrupar_por_zona', True),
                padrao=data.get('padrao', False),
                ativo=True
            )
            
            return JsonResponse({
                'success': True,
                'config_id': config.id,
                'message': 'Configuração criada com sucesso.'
            })
            
        except Exception as e:
            logger.error(f"Erro ao criar configuração: {e}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    return render(request, 'stock/logistica/routing/configuracao_form.html')
