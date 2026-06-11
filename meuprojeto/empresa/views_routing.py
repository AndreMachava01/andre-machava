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
    search = request.GET.get('search', '').strip()
    provincia = request.GET.get('provincia', '').strip()
    ativo = request.GET.get('ativo', '').strip()

    zonas = ZonaEntrega.objects.all()

    if search:
        zonas = zonas.filter(
            Q(nome__icontains=search)
            | Q(codigo__icontains=search)
            | Q(cidade__icontains=search)
            | Q(bairros__icontains=search),
        )

    if provincia:
        zonas = zonas.filter(provincia__iexact=provincia)

    if ativo in ('true', 'false'):
        zonas = zonas.filter(ativo=(ativo == 'true'))

    zonas = zonas.order_by('provincia', 'cidade', 'nome')

    stats = {
        'total': zonas.count(),
        'ativas': zonas.filter(ativo=True).count(),
        'inativas': zonas.filter(ativo=False).count(),
    }

    page_obj = Paginator(zonas, 20).get_page(request.GET.get('page'))
    provincias = ZonaEntrega.objects.values_list(
        'provincia', flat=True,
    ).distinct().order_by('provincia')

    context = {
        'page_obj': page_obj,
        'stats': stats,
        'search': search,
        'provincia': provincia,
        'ativo': ativo,
        'provincias': provincias,
        'has_filters': bool(search or provincia or ativo),
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
    search = request.GET.get('search', '').strip()
    status = request.GET.get('status', '').strip()
    prioridade = request.GET.get('prioridade', '').strip()
    data_inicio = request.GET.get('data_inicio', '').strip()
    data_fim = request.GET.get('data_fim', '').strip()

    planejamentos = PlanejamentoEntrega.objects.select_related(
        'zona_entrega', 'rota_atribuida', 'rastreamento_entrega',
    )

    if search:
        planejamentos = planejamentos.filter(
            Q(codigo__icontains=search)
            | Q(endereco_completo__icontains=search)
            | Q(cidade__icontains=search)
            | Q(contato_nome__icontains=search),
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

    stats = {
        'total': planejamentos.count(),
        'pendentes': planejamentos.filter(status='PENDENTE').count(),
        'agendadas': planejamentos.filter(status='AGENDADA').count(),
        'em_rota': planejamentos.filter(status='EM_ROTA').count(),
    }

    page_obj = Paginator(planejamentos, 20).get_page(request.GET.get('page'))

    context = {
        'page_obj': page_obj,
        'stats': stats,
        'search': search,
        'status': status,
        'prioridade': prioridade,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'status_choices': PlanejamentoEntrega.STATUS_CHOICES,
        'prioridade_choices': PlanejamentoEntrega.PRIORIDADE_CHOICES,
        'has_filters': bool(
            search or status or prioridade or data_inicio or data_fim,
        ),
    }

    return render(request, 'stock/logistica/routing/planejamentos_list.html', context)


def _criar_planejamento_entrega_from_payload(data):
    """Valida payload e cria planejamento via RoutingService."""
    rastreamento_id = data.get('rastreamento_id')
    if not rastreamento_id:
        raise ValueError('Rastreamento é obrigatório.')

    rastreamento = get_object_or_404(RastreamentoEntrega, id=rastreamento_id)
    if PlanejamentoEntrega.objects.filter(rastreamento_entrega_id=rastreamento_id).exists():
        raise ValueError('Este rastreamento já possui um planejamento associado.')

    data_entrega = data.get('data_entrega')
    janela_inicio = data.get('janela_inicio')
    janela_fim = data.get('janela_fim')
    if not data_entrega or not janela_inicio or not janela_fim:
        raise ValueError('Data e janela de entrega são obrigatórias.')

    routing_service = RoutingService()
    return routing_service.criar_planejamento_entrega(
        rastreamento=rastreamento,
        endereco=data.get('endereco', ''),
        cidade=data.get('cidade', ''),
        provincia=data.get('provincia', ''),
        data_entrega=datetime.strptime(data_entrega, '%Y-%m-%d').date(),
        janela_inicio=datetime.strptime(janela_inicio, '%H:%M').time(),
        janela_fim=datetime.strptime(janela_fim, '%H:%M').time(),
        prioridade=data.get('prioridade', 'NORMAL'),
        observacoes=data.get('observacoes', ''),
        contato_nome=data.get('contato_nome', ''),
        contato_telefone=data.get('contato_telefone', ''),
        contato_email=data.get('contato_email', ''),
    )


@login_required
@require_stock_access
def planejamento_create(request):
    """Criar novo planejamento de entrega."""
    if request.method == 'POST':
        wants_json = 'application/json' in (request.content_type or '')
        try:
            if wants_json:
                data = json.loads(request.body)
            else:
                data = {
                    'rastreamento_id': request.POST.get('rastreamento_id'),
                    'endereco': request.POST.get('endereco', '').strip(),
                    'cidade': request.POST.get('cidade', '').strip(),
                    'provincia': request.POST.get('provincia', '').strip(),
                    'data_entrega': request.POST.get('data_entrega', '').strip(),
                    'janela_inicio': request.POST.get('janela_inicio', '').strip(),
                    'janela_fim': request.POST.get('janela_fim', '').strip(),
                    'prioridade': request.POST.get('prioridade', 'NORMAL'),
                    'observacoes': request.POST.get('observacoes', '').strip(),
                    'contato_nome': request.POST.get('contato_nome', '').strip(),
                    'contato_telefone': request.POST.get('contato_telefone', '').strip(),
                    'contato_email': request.POST.get('contato_email', '').strip(),
                }

            planejamento = _criar_planejamento_entrega_from_payload(data)

            if wants_json:
                return JsonResponse({
                    'success': True,
                    'planejamento_id': planejamento.id,
                    'codigo': planejamento.codigo,
                })

            messages.success(
                request,
                f'Planejamento {planejamento.codigo} criado com sucesso.',
            )
            return redirect('stock:routing:planejamentos_list')

        except (ValueError, json.JSONDecodeError) as e:
            logger.warning('Validação ao criar planejamento: %s', e)
            if wants_json:
                return JsonResponse({'success': False, 'error': str(e)})
            messages.error(request, str(e))
        except Exception as e:
            logger.error('Erro ao criar planejamento: %s', e)
            if wants_json:
                return JsonResponse({'success': False, 'error': str(e)})
            messages.error(request, f'Não foi possível criar o planejamento: {e}')

    rastreamentos = RastreamentoEntrega.objects.filter(
        status_atual__in=['PREPARANDO', 'COLETADO', 'EM_TRANSITO', 'EM_DISTRIBUICAO'],
    ).filter(
        planejamento__isnull=True,
    ).select_related('transportadora', 'veiculo_interno').order_by('-data_criacao')

    data_padrao = (timezone.now() + timedelta(days=1)).date()
    rastreamento_id = request.GET.get('rastreamento', '').strip()

    context = {
        'rastreamentos': rastreamentos,
        'prioridade_choices': PlanejamentoEntrega.PRIORIDADE_CHOICES,
        'data_padrao': data_padrao,
        'rastreamento_selecionado': rastreamento_id,
        'form_data': request.POST if request.method == 'POST' else {},
    }

    return render(request, 'stock/logistica/routing/planejamento_form.html', context)


# =============================================================================
# ROTAS E OTIMIZAÇÃO
# =============================================================================

@login_required
@require_stock_access
def rotas_list(request):
    """Lista de rotas."""
    search = request.GET.get('search', '').strip()
    status = request.GET.get('status', '').strip()
    data_inicio = request.GET.get('data_inicio', '').strip()
    data_fim = request.GET.get('data_fim', '').strip()

    rotas = Rota.objects.select_related(
        'zona_origem', 'veiculo_interno', 'motorista',
    ).prefetch_related('paradas', 'zonas_destino')

    if search:
        rotas = rotas.filter(
            Q(codigo__icontains=search)
            | Q(nome__icontains=search)
            | Q(descricao__icontains=search),
        )

    if status:
        rotas = rotas.filter(status=status)

    if data_inicio:
        rotas = rotas.filter(data_planejada__gte=data_inicio)

    if data_fim:
        rotas = rotas.filter(data_planejada__lte=data_fim)

    rotas = rotas.order_by('-data_planejada', 'hora_inicio_prevista')

    stats = {
        'total': rotas.count(),
        'planejadas': rotas.filter(status='PLANEJADA').count(),
        'em_execucao': rotas.filter(status='EM_EXECUCAO').count(),
        'concluidas': rotas.filter(status='CONCLUIDA').count(),
    }

    context = {
        'page_obj': Paginator(rotas, 20).get_page(request.GET.get('page')),
        'stats': stats,
        'search': search,
        'status': status,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'status_choices': Rota.STATUS_CHOICES,
        'has_filters': bool(search or status or data_inicio or data_fim),
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
    
    veiculos = VeiculoInterno.objects.filter(status='ATIVO', ativo=True).order_by('nome')
    zonas = ZonaEntrega.objects.filter(ativo=True).order_by('provincia', 'cidade', 'nome')
    data_padrao = (timezone.now() + timedelta(days=1)).date()

    context = {
        'veiculos': veiculos,
        'zonas': zonas,
        'data_padrao': data_padrao,
        'stats': {
            'veiculos_disponiveis': veiculos.count(),
            'zonas_ativas': zonas.count(),
            'planejamentos_pendentes': PlanejamentoEntrega.objects.filter(
                status='PENDENTE',
                data_entrega_preferida=data_padrao,
            ).count(),
        },
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
        'veiculos_disponiveis': VeiculoInterno.objects.filter(status='ATIVO', ativo=True).count(),
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
