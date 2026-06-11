"""
Views para gerenciamento de integrações com transportadoras.
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

from .decorators import require_stock_access
from .models_stock import Transportadora, RastreamentoEntrega, EventoRastreamento
from .services.carrier_integration_service import carrier_integration_service
from .services.carriers.contracts import QuoteRequest, PickupRequest, TrackingRequest

logger = logging.getLogger(__name__)


# =============================================================================
# DASHBOARD DE INTEGRAÇÕES
# =============================================================================

@login_required
@require_stock_access
def integrations_dashboard(request):
    """Dashboard de integrações com transportadoras."""
    
    # Status das integrações
    integrations_status = {
        'correios': _check_integration_status('CORREIOS'),
        'dhl': _check_integration_status('DHL'),
        'local': _check_integration_status('LOCAL'),
    }
    
    # Estatísticas de sincronização
    stats = {
        'total_rastreamentos': RastreamentoEntrega.objects.count(),
        'rastreamentos_sincronizados': RastreamentoEntrega.objects.filter(
            data_atualizacao__gte=timezone.now() - timedelta(hours=24)
        ).count(),
        'eventos_sincronizados': EventoRastreamento.objects.filter(
            data_evento__gte=timezone.now() - timedelta(hours=24)
        ).count(),
        'transportadoras_ativas': Transportadora.objects.filter(ativo=True).count(),
    }
    
    # Rastreamentos recentes
    rastreamentos_recentes = RastreamentoEntrega.objects.select_related(
        'transportadora'
    ).order_by('-data_atualizacao')[:10]
    
    # Eventos recentes
    eventos_recentes = EventoRastreamento.objects.select_related(
        'rastreamento', 'rastreamento__transportadora'
    ).order_by('-data_evento')[:10]
    
    context = {
        'integrations_status': integrations_status,
        'stats': stats,
        'rastreamentos_recentes': rastreamentos_recentes,
        'eventos_recentes': eventos_recentes,
    }
    
    return render(request, 'stock/logistica/integrations/dashboard.html', context)


def _check_integration_status(carrier_code: str) -> dict:
    """Verifica status da integração com transportadora."""
    client = carrier_integration_service.get_client(carrier_code)
    
    if client:
        return {
            'available': True,
            'status': 'Ativa',
            'environment': getattr(client, 'environment', 'unknown')
        }
    else:
        return {
            'available': False,
            'status': 'Não configurada',
            'environment': 'N/A'
        }


# =============================================================================
# COTAÇÕES MULTI-TRANSPORTADORA
# =============================================================================

@login_required
@require_stock_access
def cotacao_multi_carrier(request):
    """Calcula cotações de múltiplas transportadoras."""
    if request.method == 'POST':
        try:
            # Dados da cotação
            origem_cep = request.POST.get('origem_cep', '').replace('-', '').replace(' ', '')
            destino_cep = request.POST.get('destino_cep', '').replace('-', '').replace(' ', '')
            peso = float(request.POST.get('peso', 0))
            comprimento = float(request.POST.get('comprimento', 0))
            largura = float(request.POST.get('largura', 0))
            altura = float(request.POST.get('altura', 0))
            valor_declarado = float(request.POST.get('valor_declarado', 0))
            
            if not origem_cep or not destino_cep:
                raise ValueError("CEP de origem e destino são obrigatórios")
            
            # Criar request de cotação
            quote_request = QuoteRequest(
                origin_zipcode=origem_cep,
                destination_zipcode=destino_cep,
                weight_kg=peso,
                length_cm=comprimento,
                width_cm=largura,
                height_cm=altura,
                declared_value=valor_declarado
            )
            
            # Calcular cotações de todas as transportadoras
            results = carrier_integration_service.quote_all_carriers(quote_request)
            
            # Processar resultados
            cotacoes = []
            for carrier_code, response in results.items():
                if response.success:
                    for quote in response.quotes:
                        cotacoes.append({
                            'carrier': carrier_code,
                            'service_code': quote['service_code'],
                            'service_name': quote['service_name'],
                            'cost': quote['cost'],
                            'delivery_days': quote['delivery_days'],
                            'delivery_date': quote['delivery_date'],
                            'currency': response.currency
                        })
                else:
                    messages.warning(request, f"Erro ao cotar com {carrier_code}: {response.error}")
            
            # Ordenar por custo
            cotacoes.sort(key=lambda x: x['cost'])
            
            context = {
                'cotacoes': cotacoes,
                'quote_request': {
                    'origem_cep': origem_cep,
                    'destino_cep': destino_cep,
                    'peso': peso,
                    'comprimento': comprimento,
                    'largura': largura,
                    'altura': altura,
                    'valor_declarado': valor_declarado
                }
            }
            
            return render(request, 'stock/logistica/integrations/cotacao_resultado.html', context)
            
        except Exception as e:
            logger.error(f"Erro ao calcular cotações: {e}")
            messages.error(request, f'Erro ao calcular cotações: {str(e)}')
    
    return render(request, 'stock/logistica/integrations/cotacao_form.html')


# =============================================================================
# SOLICITAÇÃO DE COLETA
# =============================================================================

@login_required
@require_stock_access
def solicitar_coleta(request):
    """Solicita coleta com transportadora."""
    if request.method == 'POST':
        try:
            # Dados da coleta
            transportadora_id = request.POST.get('transportadora_id')
            origem_cep = request.POST.get('origem_cep', '').replace('-', '').replace(' ', '')
            destino_cep = request.POST.get('destino_cep', '').replace('-', '').replace(' ', '')
            peso = float(request.POST.get('peso', 0))
            valor_declarado = float(request.POST.get('valor_declarado', 0))
            servico_codigo = request.POST.get('servico_codigo', '')
            data_coleta = request.POST.get('data_coleta', '')
            hora_coleta = request.POST.get('hora_coleta', '')
            observacoes = request.POST.get('observacoes', '')
            
            if not transportadora_id or not origem_cep or not destino_cep:
                raise ValueError("Transportadora, CEP de origem e destino são obrigatórios")
            
            transportadora = get_object_or_404(Transportadora, id=transportadora_id)
            
            # Determinar código da transportadora
            carrier_code = _determine_carrier_code(transportadora)
            client = carrier_integration_service.get_client(carrier_code)
            
            if not client:
                raise ValueError(f"Integração não disponível para {transportadora.nome}")
            
            # Criar request de coleta
            pickup_request = PickupRequest(
                order_number=f"COL-{timezone.now().strftime('%Y%m%d%H%M%S')}",
                origin_zipcode=origem_cep,
                destination_zipcode=destino_cep,
                weight_kg=peso,
                declared_value=valor_declarado,
                service_code=servico_codigo,
                pickup_date=datetime.strptime(data_coleta, '%Y-%m-%d').date(),
                pickup_time=datetime.strptime(hora_coleta, '%H:%M').time(),
                notes=observacoes
            )
            
            # Solicitar coleta
            response = client.request_pickup(pickup_request)
            
            if response.success:
                messages.success(request, f'Coleta solicitada com sucesso! ID: {response.pickup_id}')
                
                # Criar rastreamento se necessário
                if response.tracking_code:
                    rastreamento = RastreamentoEntrega.objects.create(
                        codigo_rastreamento=response.tracking_code,
                        transportadora=transportadora,
                        status_atual='COLETADO',
                        usuario=request.user,
                        custo_entrega=response.estimated_cost
                    )
                    
                    messages.info(request, f'Rastreamento criado: {response.tracking_code}')
                
                return redirect('stock:integrations:dashboard')
            else:
                messages.error(request, f'Erro ao solicitar coleta: {response.error}')
                
        except Exception as e:
            logger.error(f"Erro ao solicitar coleta: {e}")
            messages.error(request, f'Erro ao solicitar coleta: {str(e)}')
    
    # GET - mostrar formulário
    transportadoras = Transportadora.objects.filter(ativo=True).order_by('nome')
    
    context = {
        'transportadoras': transportadoras,
    }
    
    return render(request, 'stock/logistica/integrations/solicitar_coleta_form.html', context)


# =============================================================================
# SINCRONIZAÇÃO DE RASTREAMENTO
# =============================================================================

@login_required
@require_stock_access
def sincronizar_rastreamento(request, rastreamento_id):
    """Sincroniza dados de rastreamento com transportadora."""
    try:
        rastreamento = get_object_or_404(RastreamentoEntrega, id=rastreamento_id)
        
        # Sincronizar dados
        carrier_integration_service.sync_tracking_data(rastreamento_id)
        
        messages.success(request, 'Dados de rastreamento sincronizados com sucesso!')
        return redirect('stock:logistica:rastreamento_detail', rastreamento_id=rastreamento_id)
        
    except Exception as e:
        logger.error(f"Erro ao sincronizar rastreamento: {e}")
        messages.error(request, f'Erro ao sincronizar rastreamento: {str(e)}')
        return redirect('stock:logistica:rastreamento_detail', rastreamento_id=rastreamento_id)


@login_required
@require_stock_access
def sincronizar_todos_rastreamentos(request):
    """Sincroniza todos os rastreamentos pendentes."""
    try:
        # Rastreamentos que precisam de sincronização
        rastreamentos = RastreamentoEntrega.objects.filter(
            codigo_rastreamento__isnull=False,
            transportadora__isnull=False,
            data_atualizacao__lt=timezone.now() - timedelta(hours=6)
        )[:50]  # Limitar para não sobrecarregar
        
        sincronizados = 0
        erros = 0
        
        for rastreamento in rastreamentos:
            try:
                carrier_integration_service.sync_tracking_data(rastreamento.id)
                sincronizados += 1
            except Exception as e:
                logger.error(f"Erro ao sincronizar rastreamento {rastreamento.id}: {e}")
                erros += 1
        
        messages.success(request, f'Sincronização concluída! {sincronizados} sucessos, {erros} erros.')
        return redirect('stock:integrations:dashboard')
        
    except Exception as e:
        logger.error(f"Erro na sincronização em massa: {e}")
        messages.error(request, f'Erro na sincronização em massa: {str(e)}')
        return redirect('stock:integrations:dashboard')


# =============================================================================
# CONFIGURAÇÕES DE INTEGRAÇÃO
# =============================================================================

@login_required
@require_stock_access
def configurar_integracao(request, carrier_code):
    """Configura integração com transportadora."""
    if request.method == 'POST':
        try:
            # Salvar configurações (implementar conforme necessário)
            configuracao = {
                'api_key': request.POST.get('api_key', ''),
                'api_secret': request.POST.get('api_secret', ''),
                'environment': request.POST.get('environment', 'sandbox'),
                'api_url': request.POST.get('api_url', ''),
                'ativo': request.POST.get('ativo') == 'on'
            }
            
            # Salvar no cache ou banco de dados
            from django.core.cache import cache
            cache.set(f'integracao_{carrier_code.lower()}', configuracao, timeout=None)
            
            messages.success(request, f'Configuração da {carrier_code} salva com sucesso!')
            return redirect('stock:integrations:dashboard')
            
        except Exception as e:
            logger.error(f"Erro ao salvar configuração: {e}")
            messages.error(request, f'Erro ao salvar configuração: {str(e)}')
    
    # GET - mostrar configurações atuais
    from django.core.cache import cache
    configuracao = cache.get(f'integracao_{carrier_code.lower()}', {
        'api_key': '',
        'api_secret': '',
        'environment': 'sandbox',
        'api_url': '',
        'ativo': False
    })
    
    context = {
        'carrier_code': carrier_code,
        'configuracao': configuracao,
    }
    
    return render(request, 'stock/logistica/integrations/configurar_integracao.html', context)


# =============================================================================
# APIS PARA INTEGRAÇÕES
# =============================================================================

@login_required
@require_stock_access
def api_cotacao_multi_carrier(request):
    """API para cotação multi-transportadora."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            quote_request = QuoteRequest(
                origin_zipcode=data.get('origem_cep', '').replace('-', '').replace(' ', ''),
                destination_zipcode=data.get('destino_cep', '').replace('-', '').replace(' ', ''),
                weight_kg=float(data.get('peso', 0)),
                length_cm=float(data.get('comprimento', 0)),
                width_cm=float(data.get('largura', 0)),
                height_cm=float(data.get('altura', 0)),
                declared_value=float(data.get('valor_declarado', 0))
            )
            
            results = carrier_integration_service.quote_all_carriers(quote_request)
            
            cotacoes = []
            for carrier_code, response in results.items():
                if response.success:
                    for quote in response.quotes:
                        cotacoes.append({
                            'carrier': carrier_code,
                            'service_code': quote['service_code'],
                            'service_name': quote['service_name'],
                            'cost': float(quote['cost']),
                            'delivery_days': quote['delivery_days'],
                            'delivery_date': quote['delivery_date'].isoformat() if quote['delivery_date'] else None,
                            'currency': response.currency
                        })
            
            return JsonResponse({
                'success': True,
                'quotes': cotacoes
            })
            
        except Exception as e:
            logger.error(f"Erro na API de cotação: {e}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Método não permitido'})


@login_required
@require_stock_access
def api_sincronizar_rastreamento(request, rastreamento_id):
    """API para sincronizar rastreamento."""
    if request.method == 'POST':
        try:
            carrier_integration_service.sync_tracking_data(rastreamento_id)
            
            return JsonResponse({'success': True})
            
        except Exception as e:
            logger.error(f"Erro na API de sincronização: {e}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Método não permitido'})


@login_required
@require_stock_access
def api_status_integracao(request):
    """API para verificar status das integrações."""
    if request.method == 'GET':
        try:
            status = {}
            
            for carrier_code in ['CORREIOS', 'DHL', 'LOCAL']:
                client = carrier_integration_service.get_client(carrier_code)
                status[carrier_code] = {
                    'available': client is not None,
                    'status': 'Ativa' if client else 'Não configurada',
                    'environment': getattr(client, 'environment', 'N/A') if client else 'N/A'
                }
            
            return JsonResponse({
                'success': True,
                'integrations': status
            })
            
        except Exception as e:
            logger.error(f"Erro na API de status: {e}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Método não permitido'})


# =============================================================================
# FUNÇÕES AUXILIARES
# =============================================================================

def _determine_carrier_code(transportadora: Transportadora) -> str:
    """Determina código da transportadora."""
    nome = transportadora.nome.upper()
    if 'CORREIOS' in nome:
        return 'CORREIOS'
    elif 'DHL' in nome:
        return 'DHL'
    else:
        return 'LOCAL'
