"""
Views para gerenciamento de geolocalização logística.
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
import math

from .decorators import require_stock_access
from .models_geolocation import (
    EnderecoNormalizado, CoordenadaHistorica, CalculoDistancia, 
    ConfiguracaoGeolocalizacao, ZonaGeografica
)
from .models_stock import RastreamentoEntrega, VeiculoInterno
from .services.geolocation_service import GeolocationService

logger = logging.getLogger(__name__)


# =============================================================================
# DASHBOARD DE GEOLOCALIZAÇÃO
# =============================================================================

@login_required
@require_stock_access
def geolocation_dashboard(request):
    """Dashboard de geolocalização logística."""
    
    # Métricas de geolocalização
    metricas = {
        'enderecos_normalizados': EnderecoNormalizado.objects.count(),
        'coordenadas_historicas': CoordenadaHistorica.objects.count(),
        'calculos_distancia': CalculoDistancia.objects.count(),
        'zonas_geograficas': ZonaGeografica.objects.count(),
        'enderecos_recentes': EnderecoNormalizado.objects.filter(
            data_criacao__gte=timezone.now() - timedelta(days=7)
        ).count(),
    }
    
    # Endereços recentes
    enderecos_recentes = EnderecoNormalizado.objects.order_by('-data_criacao')[:10]
    
    # Coordenadas com problemas de precisão
    coordenadas_baixa_precisao = EnderecoNormalizado.objects.filter(
        precisao='APPROXIMATE'
    ).order_by('-data_criacao')[:5]
    
    # Estatísticas de precisão
    stats_precisao = EnderecoNormalizado.objects.values('precisao').annotate(
        count=Count('id')
    ).order_by('-count')
    
    context = {
        'metricas': metricas,
        'enderecos_recentes': enderecos_recentes,
        'coordenadas_baixa_precisao': coordenadas_baixa_precisao,
        'stats_precisao': stats_precisao,
    }
    
    return render(request, 'stock/logistica/geolocation/dashboard.html', context)


# =============================================================================
# ENDEREÇOS NORMALIZADOS
# =============================================================================

@login_required
@require_stock_access
def enderecos_list(request):
    """Lista de endereços normalizados."""
    search = request.GET.get('search', '')
    cidade = request.GET.get('cidade', '')
    precisao = request.GET.get('precisao', '')
    data_inicio = request.GET.get('data_inicio', '')
    data_fim = request.GET.get('data_fim', '')
    
    enderecos = EnderecoNormalizado.objects.all()
    
    if search:
        enderecos = enderecos.filter(
            Q(endereco_original__icontains=search) |
            Q(endereco_normalizado__icontains=search) |
            Q(logradouro__icontains=search) |
            Q(bairro__icontains=search) |
            Q(cidade__icontains=search)
        )
    
    if cidade:
        enderecos = enderecos.filter(cidade__iexact=cidade)
    
    if precisao:
        enderecos = enderecos.filter(precisao=precisao)
    
    if data_inicio:
        enderecos = enderecos.filter(data_criacao__date__gte=data_inicio)
    
    if data_fim:
        enderecos = enderecos.filter(data_criacao__date__lte=data_fim)
    
    enderecos = enderecos.order_by('-data_criacao')
    
    # Paginação
    paginator = Paginator(enderecos, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Opções para filtros
    precisao_choices = EnderecoNormalizado.PRECISAO_CHOICES
    cidades = EnderecoNormalizado.objects.values_list('cidade', flat=True).distinct().order_by('cidade')
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'cidade': cidade,
        'precisao': precisao,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'precisao_choices': precisao_choices,
        'cidades': cidades,
    }
    
    return render(request, 'stock/logistica/geolocation/enderecos_list.html', context)


@login_required
@require_stock_access
def endereco_detail(request, endereco_id):
    """Detalhes de um endereço normalizado."""
    endereco = get_object_or_404(EnderecoNormalizado, id=endereco_id)
    
    # Coordenadas históricas relacionadas
    coordenadas_historicas = endereco.coordenadas_historicas.all().order_by('-data_registro')[:10]
    
    # Cálculos de distância relacionados
    calculos_distancia = CalculoDistancia.objects.filter(
        Q(origem=endereco) | Q(destino=endereco)
    ).order_by('-data_calculo')[:10]
    
    context = {
        'endereco': endereco,
        'coordenadas_historicas': coordenadas_historicas,
        'calculos_distancia': calculos_distancia,
    }
    
    return render(request, 'stock/logistica/geolocation/endereco_detail.html', context)


@login_required
@require_stock_access
def normalizar_endereco(request):
    """Normalizar um endereço usando geocoding."""
    if request.method == 'POST':
        try:
            endereco_original = request.POST.get('endereco_original', '').strip()
            
            if not endereco_original:
                raise ValueError("Endereço é obrigatório")
            
            geolocation_service = GeolocationService()
            resultado = geolocation_service.normalizar_endereco(endereco_original)
            
            messages.success(request, f'Endereço normalizado com sucesso! Precisão: {resultado.get_precisao_display()}')
            return redirect('stock:geolocation:endereco_detail', endereco_id=resultado.id)
            
        except Exception as e:
            logger.error(f"Erro ao normalizar endereço: {e}")
            messages.error(request, f'Erro ao normalizar endereço: {str(e)}')
    
    return render(request, 'stock/logistica/geolocation/normalizar_form.html')


# =============================================================================
# COORDENADAS HISTÓRICAS
# =============================================================================

@login_required
@require_stock_access
def coordenadas_historicas_list(request):
    """Lista de coordenadas históricas."""
    search = request.GET.get('search', '')
    tipo_entidade = request.GET.get('tipo_entidade', '')
    data_inicio = request.GET.get('data_inicio', '')
    data_fim = request.GET.get('data_fim', '')
    
    coordenadas = CoordenadaHistorica.objects.select_related('endereco')
    
    if search:
        coordenadas = coordenadas.filter(
            Q(endereco__endereco_normalizado__icontains=search) |
            Q(entidade_id__icontains=search) |
            Q(observacoes__icontains=search)
        )
    
    if tipo_entidade:
        coordenadas = coordenadas.filter(tipo_entidade=tipo_entidade)
    
    if data_inicio:
        coordenadas = coordenadas.filter(data_registro__date__gte=data_inicio)
    
    if data_fim:
        coordenadas = coordenadas.filter(data_registro__date__lte=data_fim)
    
    coordenadas = coordenadas.order_by('-data_registro')
    
    # Paginação
    paginator = Paginator(coordenadas, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Opções para filtros
    tipo_choices = CoordenadaHistorica.TIPO_ENTIDADE_CHOICES
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'tipo_entidade': tipo_entidade,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'tipo_choices': tipo_choices,
    }
    
    return render(request, 'stock/logistica/geolocation/coordenadas_list.html', context)


# =============================================================================
# CÁLCULOS DE DISTÂNCIA
# =============================================================================

@login_required
@require_stock_access
def calculos_distancia_list(request):
    """Lista de cálculos de distância."""
    search = request.GET.get('search', '')
    metodo_calculo = request.GET.get('metodo_calculo', '')
    data_inicio = request.GET.get('data_inicio', '')
    data_fim = request.GET.get('data_fim', '')
    
    calculos = CalculoDistancia.objects.select_related('origem', 'destino')
    
    if search:
        calculos = calculos.filter(
            Q(origem__endereco_normalizado__icontains=search) |
            Q(destino__endereco_normalizado__icontains=search) |
            Q(observacoes__icontains=search)
        )
    
    if metodo_calculo:
        calculos = calculos.filter(metodo_calculo=metodo_calculo)
    
    if data_inicio:
        calculos = calculos.filter(data_calculo__date__gte=data_inicio)
    
    if data_fim:
        calculos = calculos.filter(data_calculo__date__lte=data_fim)
    
    calculos = calculos.order_by('-data_calculo')
    
    # Paginação
    paginator = Paginator(calculos, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Opções para filtros
    metodo_choices = CalculoDistancia.METODO_CALCULO_CHOICES
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'metodo_calculo': metodo_calculo,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'metodo_choices': metodo_choices,
    }
    
    return render(request, 'stock/logistica/geolocation/calculos_list.html', context)


@login_required
@require_stock_access
def calcular_distancia(request):
    """Calcular distância entre dois endereços."""
    if request.method == 'POST':
        try:
            origem_id = request.POST.get('origem_id')
            destino_id = request.POST.get('destino_id')
            metodo_calculo = request.POST.get('metodo_calculo', 'HAVERSINE')
            observacoes = request.POST.get('observacoes', '')
            
            if not origem_id or not destino_id:
                raise ValueError("Origem e destino são obrigatórios")
            
            origem = get_object_or_404(EnderecoNormalizado, id=origem_id)
            destino = get_object_or_404(EnderecoNormalizado, id=destino_id)
            
            geolocation_service = GeolocationService()
            resultado = geolocation_service.calcular_distancia(
                origem, destino, metodo_calculo, observacoes
            )
            
            messages.success(request, f'Distância calculada: {resultado.distancia_km:.2f} km')
            return redirect('stock:geolocation:calculos_list')
            
        except Exception as e:
            logger.error(f"Erro ao calcular distância: {e}")
            messages.error(request, f'Erro ao calcular distância: {str(e)}')
    
    # GET - mostrar formulário
    enderecos = EnderecoNormalizado.objects.order_by('endereco_normalizado')
    metodo_choices = CalculoDistancia.METODO_CALCULO_CHOICES
    
    context = {
        'enderecos': enderecos,
        'metodo_choices': metodo_choices,
    }
    
    return render(request, 'stock/logistica/geolocation/calcular_distancia_form.html', context)


# =============================================================================
# ZONAS GEOGRÁFICAS
# =============================================================================

@login_required
@require_stock_access
def zonas_geograficas_list(request):
    """Lista de zonas geográficas."""
    search = request.GET.get('search', '')
    tipo_zona = request.GET.get('tipo_zona', '')
    ativo = request.GET.get('ativo', '')
    
    zonas = ZonaGeografica.objects.all()
    
    if search:
        zonas = zonas.filter(
            Q(nome__icontains=search) |
            Q(codigo__icontains=search) |
            Q(descricao__icontains=search)
        )
    
    if tipo_zona:
        zonas = zonas.filter(tipo_zona=tipo_zona)
    
    if ativo:
        zonas = zonas.filter(ativo=ativo == 'true')
    
    zonas = zonas.order_by('nome')
    
    # Paginação
    paginator = Paginator(zonas, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Opções para filtros
    tipo_choices = ZonaGeografica.TIPO_ZONA_CHOICES
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'tipo_zona': tipo_zona,
        'ativo': ativo,
        'tipo_choices': tipo_choices,
    }
    
    return render(request, 'stock/logistica/geolocation/zonas_list.html', context)


@login_required
@require_stock_access
def zona_geografica_detail(request, zona_id):
    """Detalhes de uma zona geográfica."""
    zona = get_object_or_404(ZonaGeografica, id=zona_id)
    
    # Endereços dentro desta zona
    enderecos_zona = EnderecoNormalizado.objects.filter(
        latitude__gte=zona.latitude_min,
        latitude__lte=zona.latitude_max,
        longitude__gte=zona.longitude_min,
        longitude__lte=zona.longitude_max
    ).order_by('endereco_normalizado')
    
    context = {
        'zona': zona,
        'enderecos_zona': enderecos_zona,
    }
    
    return render(request, 'stock/logistica/geolocation/zona_detail.html', context)


# =============================================================================
# APIS PARA GEOLOCALIZAÇÃO
# =============================================================================

@login_required
@require_stock_access
def api_normalizar_endereco(request):
    """API para normalizar endereço."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            endereco_original = data.get('endereco_original', '').strip()
            
            if not endereco_original:
                return JsonResponse({'success': False, 'error': 'Endereço é obrigatório'})
            
            geolocation_service = GeolocationService()
            resultado = geolocation_service.normalizar_endereco(endereco_original)
            
            return JsonResponse({
                'success': True,
                'endereco': {
                    'id': resultado.id,
                    'endereco_normalizado': resultado.endereco_normalizado,
                    'latitude': float(resultado.latitude),
                    'longitude': float(resultado.longitude),
                    'precisao': resultado.precisao,
                    'cidade': resultado.cidade,
                    'bairro': resultado.bairro
                }
            })
            
        except Exception as e:
            logger.error(f"Erro na normalização de endereço: {e}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Método não permitido'})


@login_required
@require_stock_access
def api_calcular_distancia(request):
    """API para calcular distância entre coordenadas."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            lat1 = float(data.get('lat1'))
            lon1 = float(data.get('lon1'))
            lat2 = float(data.get('lat2'))
            lon2 = float(data.get('lon2'))
            metodo = data.get('metodo', 'HAVERSINE')
            
            geolocation_service = GeolocationService()
            distancia = geolocation_service.calcular_distancia_coordenadas(
                lat1, lon1, lat2, lon2, metodo
            )
            
            return JsonResponse({
                'success': True,
                'distancia_km': distancia,
                'metodo': metodo
            })
            
        except Exception as e:
            logger.error(f"Erro no cálculo de distância: {e}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Método não permitido'})


@login_required
@require_stock_access
def api_obter_eta(request):
    """API para obter ETA baseado em distância."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            distancia_km = float(data.get('distancia_km'))
            velocidade_media = float(data.get('velocidade_media', 30))  # km/h padrão
            tempo_paradas = float(data.get('tempo_paradas', 0))  # minutos
            
            geolocation_service = GeolocationService()
            eta = geolocation_service.calcular_eta(distancia_km, velocidade_media, tempo_paradas)
            
            return JsonResponse({
                'success': True,
                'eta_minutos': eta,
                'eta_horas': eta / 60,
                'distancia_km': distancia_km,
                'velocidade_media': velocidade_media
            })
            
        except Exception as e:
            logger.error(f"Erro no cálculo de ETA: {e}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Método não permitido'})
