"""
Views para gestão de dados mestres (masterdata) logísticos.
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
from .models_masterdata import (
    Regiao, HubLogistico, CatalogoDimensoes,
    RestricaoLogistica, PermissaoLogistica, ConfiguracaoMasterdata,
    LogMasterdata
)
from .models_routing import ZonaEntrega
from .services.masterdata_service import MasterdataService

logger = logging.getLogger(__name__)


@login_required
@require_stock_access
def masterdata_dashboard(request):
    """Dashboard de dados mestres."""
    # Estatísticas gerais
    masterdata_service = MasterdataService()
    stats = masterdata_service.obter_estatisticas_masterdata()
    
    # Logs recentes
    logs_recentes = masterdata_service.obter_logs_masterdata(limite=10)
    
    # Regiões ativas
    regioes_ativas = Regiao.objects.filter(ativo=True).order_by('prioridade', 'nome')
    
    # Zonas de entrega ativas
    zonas_ativas = ZonaEntrega.objects.filter(ativo=True).select_related('regiao').order_by('regiao', 'nome')
    
    # Hubs logísticos ativos
    hubs_ativos = HubLogistico.objects.filter(ativo=True).select_related('regiao').order_by('tipo', 'nome')
    
    context = {
        'stats': stats,
        'logs_recentes': logs_recentes,
        'regioes_ativas': regioes_ativas,
        'zonas_ativas': zonas_ativas,
        'hubs_ativos': hubs_ativos,
    }
    
    return render(request, 'stock/logistica/masterdata/dashboard.html', context)


# =============================================================================
# REGIÕES
# =============================================================================

@login_required
@require_stock_access
def regioes_list(request):
    """Lista de regiões."""
    search = request.GET.get('search', '')
    provincia = request.GET.get('provincia', '')
    ativo = request.GET.get('ativo', '')
    
    regioes = Regiao.objects.all()
    
    if search:
        regioes = regioes.filter(
            Q(codigo__icontains=search) |
            Q(nome__icontains=search) |
            Q(distrito__icontains=search)
        )
    
    if provincia:
        regioes = regioes.filter(provincia__icontains=provincia)
    
    if ativo:
        regioes = regioes.filter(ativo=ativo == 'true')
    
    regioes = regioes.order_by('prioridade', 'nome')
    
    # Paginação
    paginator = Paginator(regioes, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Províncias para filtro
    provincias = Regiao.objects.values_list('provincia', flat=True).distinct().order_by('provincia')
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'provincia': provincia,
        'ativo': ativo,
        'provincias': provincias,
    }
    
    return render(request, 'stock/logistica/masterdata/regioes_list.html', context)


@login_required
@require_stock_access
def regiao_detail(request, regiao_id):
    """Detalhes de uma região."""
    regiao = get_object_or_404(Regiao, id=regiao_id)
    
    # Zonas relacionadas
    zonas = regiao.zonas.all().order_by('nome')
    
    # Hubs relacionados
    hubs = regiao.hubs.all().order_by('tipo', 'nome')
    
    context = {
        'regiao': regiao,
        'zonas': zonas,
        'hubs': hubs,
    }
    
    return render(request, 'stock/logistica/masterdata/regiao_detail.html', context)


@login_required
@require_stock_access
def regiao_create(request):
    """Criar nova região."""
    masterdata_service = MasterdataService()
    
    if request.method == 'POST':
        try:
            regiao = masterdata_service.criar_regiao(
                codigo=request.POST.get('codigo'),
                nome=request.POST.get('nome'),
                provincia=request.POST.get('provincia'),
                distrito=request.POST.get('distrito', ''),
                latitude_centro=request.POST.get('latitude_centro') or None,
                longitude_centro=request.POST.get('longitude_centro') or None,
                prioridade=int(request.POST.get('prioridade', 1)),
                usuario=request.user
            )
            
            messages.success(request, 'Região criada com sucesso!')
            return redirect('stock:masterdata:regiao_detail', regiao_id=regiao.id)
            
        except Exception as e:
            logger.error(f"Erro ao criar região: {e}")
            messages.error(request, f'Erro ao criar região: {str(e)}')
    
    context = {}
    return render(request, 'stock/logistica/masterdata/regiao_form.html', context)


# =============================================================================
# ZONAS DE ENTREGA
# =============================================================================

@login_required
@require_stock_access
def zonas_list(request):
    """Lista de zonas de entrega."""
    search = request.GET.get('search', '')
    regiao = request.GET.get('regiao', '')
    ativo = request.GET.get('ativo', '')
    
    zonas = ZonaEntrega.objects.select_related('regiao')
    
    if search:
        zonas = zonas.filter(
            Q(codigo__icontains=search) |
            Q(nome__icontains=search)
        )
    
    if regiao:
        zonas = zonas.filter(regiao_id=regiao)
    
    if ativo:
        zonas = zonas.filter(ativo=ativo == 'true')
    
    zonas = zonas.order_by('regiao', 'nome')
    
    # Paginação
    paginator = Paginator(zonas, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Regiões para filtro
    regioes = Regiao.objects.filter(ativo=True).order_by('nome')
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'regiao': regiao,
        'ativo': ativo,
        'regioes': regioes,
    }
    
    return render(request, 'stock/logistica/masterdata/zonas_list.html', context)


@login_required
@require_stock_access
def zona_detail(request, zona_id):
    """Detalhes de uma zona de entrega."""
    zona = get_object_or_404(ZonaEntrega, id=zona_id)
    
    context = {
        'zona': zona,
    }
    
    return render(request, 'stock/logistica/masterdata/zona_detail.html', context)


@login_required
@require_stock_access
def zona_create(request):
    """Criar nova zona de entrega."""
    masterdata_service = MasterdataService()
    
    if request.method == 'POST':
        try:
            # Processar dias de funcionamento
            dias_funcionamento = []
            for i in range(7):
                if request.POST.get(f'dia_{i}'):
                    dias_funcionamento.append(i)
            
            zona = masterdata_service.criar_zona_entrega(
                codigo=request.POST.get('codigo'),
                nome=request.POST.get('nome'),
                regiao_id=request.POST.get('regiao'),
                prazo_entrega_dias=int(request.POST.get('prazo_entrega_dias', 1)),
                custo_adicional=Decimal(request.POST.get('custo_adicional', '0.00')),
                peso_maximo_kg=request.POST.get('peso_maximo_kg') or None,
                volume_maximo_m3=request.POST.get('volume_maximo_m3') or None,
                horario_inicio=request.POST.get('horario_inicio', '08:00'),
                horario_fim=request.POST.get('horario_fim', '18:00'),
                dias_funcionamento=dias_funcionamento,
                usuario=request.user
            )
            
            messages.success(request, 'Zona de entrega criada com sucesso!')
            return redirect('stock:masterdata:zona_detail', zona_id=zona.id)
            
        except Exception as e:
            logger.error(f"Erro ao criar zona: {e}")
            messages.error(request, f'Erro ao criar zona: {str(e)}')
    
    regioes = Regiao.objects.filter(ativo=True).order_by('nome')
    
    context = {
        'regioes': regioes,
    }
    
    return render(request, 'stock/logistica/masterdata/zona_form.html', context)


# =============================================================================
# HUBS LOGÍSTICOS
# =============================================================================

@login_required
@require_stock_access
def hubs_list(request):
    """Lista de hubs logísticos."""
    search = request.GET.get('search', '')
    tipo = request.GET.get('tipo', '')
    regiao = request.GET.get('regiao', '')
    ativo = request.GET.get('ativo', '')
    
    hubs = HubLogistico.objects.select_related('regiao')
    
    if search:
        hubs = hubs.filter(
            Q(codigo__icontains=search) |
            Q(nome__icontains=search) |
            Q(cidade__icontains=search)
        )
    
    if tipo:
        hubs = hubs.filter(tipo=tipo)
    
    if regiao:
        hubs = hubs.filter(regiao_id=regiao)
    
    if ativo:
        hubs = hubs.filter(ativo=ativo == 'true')
    
    hubs = hubs.order_by('tipo', 'nome')
    
    # Paginação
    paginator = Paginator(hubs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Opções para filtros
    tipo_choices = HubLogistico.TIPO_CHOICES
    regioes = Regiao.objects.filter(ativo=True).order_by('nome')
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'tipo': tipo,
        'regiao': regiao,
        'ativo': ativo,
        'tipo_choices': tipo_choices,
        'regioes': regioes,
    }
    
    return render(request, 'stock/logistica/masterdata/hubs_list.html', context)


@login_required
@require_stock_access
def hub_detail(request, hub_id):
    """Detalhes de um hub logístico."""
    hub = get_object_or_404(HubLogistico, id=hub_id)
    
    context = {
        'hub': hub,
    }
    
    return render(request, 'stock/logistica/masterdata/hub_detail.html', context)


@login_required
@require_stock_access
def hub_create(request):
    """Criar novo hub logístico."""
    masterdata_service = MasterdataService()
    
    if request.method == 'POST':
        try:
            hub = masterdata_service.criar_hub_logistico(
                codigo=request.POST.get('codigo'),
                nome=request.POST.get('nome'),
                endereco=request.POST.get('endereco'),
                cidade=request.POST.get('cidade'),
                regiao_id=request.POST.get('regiao'),
                latitude=Decimal(request.POST.get('latitude')),
                longitude=Decimal(request.POST.get('longitude')),
                tipo=request.POST.get('tipo', 'DISTRIBUICAO'),
                capacidade_maxima_m3=request.POST.get('capacidade_maxima_m3') or None,
                capacidade_maxima_kg=request.POST.get('capacidade_maxima_kg') or None,
                horario_inicio=request.POST.get('horario_inicio', '06:00'),
                horario_fim=request.POST.get('horario_fim', '22:00'),
                funcionamento_24h=request.POST.get('funcionamento_24h') == 'on',
                telefone=request.POST.get('telefone', ''),
                email=request.POST.get('email', ''),
                responsavel=request.POST.get('responsavel', ''),
                usuario=request.user
            )
            
            messages.success(request, 'Hub logístico criado com sucesso!')
            return redirect('stock:masterdata:hub_detail', hub_id=hub.id)
            
        except Exception as e:
            logger.error(f"Erro ao criar hub: {e}")
            messages.error(request, f'Erro ao criar hub: {str(e)}')
    
    regioes = Regiao.objects.filter(ativo=True).order_by('nome')
    tipo_choices = HubLogistico.TIPO_CHOICES
    
    context = {
        'regioes': regioes,
        'tipo_choices': tipo_choices,
    }
    
    return render(request, 'stock/logistica/masterdata/hub_form.html', context)


# =============================================================================
# CATÁLOGO DE DIMENSÕES
# =============================================================================

@login_required
@require_stock_access
def catalogo_dimensoes_list(request):
    """Lista do catálogo de dimensões."""
    search = request.GET.get('search', '')
    categoria = request.GET.get('categoria', '')
    ativo = request.GET.get('ativo', '')
    
    dimensoes = CatalogoDimensoes.objects.all()
    
    if search:
        dimensoes = dimensoes.filter(
            Q(codigo__icontains=search) |
            Q(nome__icontains=search)
        )
    
    if categoria:
        dimensoes = dimensoes.filter(categoria=categoria)
    
    if ativo:
        dimensoes = dimensoes.filter(ativo=ativo == 'true')
    
    dimensoes = dimensoes.order_by('categoria', 'volume_m3')
    
    # Paginação
    paginator = Paginator(dimensoes, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Opções para filtros
    categoria_choices = CatalogoDimensoes._meta.get_field('categoria').choices
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'categoria': categoria,
        'ativo': ativo,
        'categoria_choices': categoria_choices,
    }
    
    return render(request, 'stock/logistica/masterdata/catalogo_dimensoes_list.html', context)


@login_required
@require_stock_access
def catalogo_dimensoes_detail(request, dimensao_id):
    """Detalhes de uma entrada do catálogo de dimensões."""
    dimensao = get_object_or_404(CatalogoDimensoes, id=dimensao_id)
    
    context = {
        'dimensao': dimensao,
    }
    
    return render(request, 'stock/logistica/masterdata/catalogo_dimensoes_detail.html', context)


@login_required
@require_stock_access
def catalogo_dimensoes_create(request):
    """Criar nova entrada no catálogo de dimensões."""
    masterdata_service = MasterdataService()
    
    if request.method == 'POST':
        try:
            dimensao = masterdata_service.criar_catalogo_dimensoes(
                codigo=request.POST.get('codigo'),
                nome=request.POST.get('nome'),
                comprimento_cm=Decimal(request.POST.get('comprimento_cm')),
                largura_cm=Decimal(request.POST.get('largura_cm')),
                altura_cm=Decimal(request.POST.get('altura_cm')),
                peso_kg=Decimal(request.POST.get('peso_kg')),
                categoria=request.POST.get('categoria', 'PACOTE_MEDIO'),
                usuario=request.user
            )
            
            messages.success(request, 'Entrada do catálogo criada com sucesso!')
            return redirect('stock:masterdata:catalogo_dimensoes_detail', dimensao_id=dimensao.id)
            
        except Exception as e:
            logger.error(f"Erro ao criar catálogo de dimensões: {e}")
            messages.error(request, f'Erro ao criar entrada: {str(e)}')
    
    categoria_choices = CatalogoDimensoes._meta.get_field('categoria').choices
    
    context = {
        'categoria_choices': categoria_choices,
    }
    
    return render(request, 'stock/logistica/masterdata/catalogo_dimensoes_form.html', context)


# =============================================================================
# RESTRIÇÕES LOGÍSTICAS
# =============================================================================

@login_required
@require_stock_access
def restricoes_list(request):
    """Lista de restrições logísticas."""
    search = request.GET.get('search', '')
    tipo = request.GET.get('tipo', '')
    ativo = request.GET.get('ativo', '')
    
    restricoes = RestricaoLogistica.objects.all()
    
    if search:
        restricoes = restricoes.filter(
            Q(codigo__icontains=search) |
            Q(nome__icontains=search)
        )
    
    if tipo:
        restricoes = restricoes.filter(tipo=tipo)
    
    if ativo:
        restricoes = restricoes.filter(ativo=ativo == 'true')
    
    restricoes = restricoes.order_by('tipo', 'nome')
    
    # Paginação
    paginator = Paginator(restricoes, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Opções para filtros
    tipo_choices = RestricaoLogistica.TIPO_CHOICES
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'tipo': tipo,
        'ativo': ativo,
        'tipo_choices': tipo_choices,
    }
    
    return render(request, 'stock/logistica/masterdata/restricoes_list.html', context)


@login_required
@require_stock_access
def restricao_detail(request, restricao_id):
    """Detalhes de uma restrição logística."""
    restricao = get_object_or_404(RestricaoLogistica, id=restricao_id)
    
    context = {
        'restricao': restricao,
    }
    
    return render(request, 'stock/logistica/masterdata/restricao_detail.html', context)


@login_required
@require_stock_access
def restricao_create(request):
    """Criar nova restrição logística."""
    masterdata_service = MasterdataService()
    
    if request.method == 'POST':
        try:
            restricao = masterdata_service.criar_restricao_logistica(
                codigo=request.POST.get('codigo'),
                nome=request.POST.get('nome'),
                tipo=request.POST.get('tipo'),
                valor_minimo=request.POST.get('valor_minimo') or None,
                valor_maximo=request.POST.get('valor_maximo') or None,
                unidade_medida=request.POST.get('unidade_medida', ''),
                aplicavel_veiculo_interno=request.POST.get('aplicavel_veiculo_interno') == 'on',
                aplicavel_transportadora=request.POST.get('aplicavel_transportadora') == 'on',
                acao_violacao=request.POST.get('acao_violacao', 'AVISAR'),
                usuario=request.user
            )
            
            messages.success(request, 'Restrição logística criada com sucesso!')
            return redirect('stock:masterdata:restricao_detail', restricao_id=restricao.id)
            
        except Exception as e:
            logger.error(f"Erro ao criar restrição: {e}")
            messages.error(request, f'Erro ao criar restrição: {str(e)}')
    
    tipo_choices = RestricaoLogistica.TIPO_CHOICES
    acao_choices = RestricaoLogistica._meta.get_field('acao_violacao').choices
    
    context = {
        'tipo_choices': tipo_choices,
        'acao_choices': acao_choices,
    }
    
    return render(request, 'stock/logistica/masterdata/restricao_form.html', context)


# =============================================================================
# VALIDAÇÃO DE RESTRIÇÕES
# =============================================================================

@login_required
@require_stock_access
def validar_restricoes(request):
    """Valida restrições logísticas."""
    if request.method == 'POST':
        try:
            masterdata_service = MasterdataService()
            
            resultado = masterdata_service.validar_restricoes(
                peso_kg=request.POST.get('peso_kg') or None,
                volume_m3=request.POST.get('volume_m3') or None,
                valor_declarado=request.POST.get('valor_declarado') or None,
                zona_entrega_id=request.POST.get('zona_entrega_id') or None,
                transportadora_id=request.POST.get('transportadora_id') or None,
                veiculo_interno_id=request.POST.get('veiculo_interno_id') or None
            )
            
            return JsonResponse(resultado)
            
        except Exception as e:
            logger.error(f"Erro ao validar restrições: {e}")
            return JsonResponse({'erro': str(e)}, status=400)
    
    # GET - mostrar formulário
    from .models_stock import Transportadora, VeiculoInterno
    
    transportadoras = Transportadora.objects.filter(ativo=True)
    veiculos_internos = VeiculoInterno.objects.filter(ativo=True)
    zonas_entrega = ZonaEntrega.objects.filter(ativo=True)
    
    context = {
        'transportadoras': transportadoras,
        'veiculos_internos': veiculos_internos,
        'zonas_entrega': zonas_entrega,
    }
    
    return render(request, 'stock/logistica/masterdata/validar_restricoes.html', context)


# =============================================================================
# LOGS E AUDITORIA
# =============================================================================

@login_required
@require_stock_access
def logs_masterdata(request):
    """Logs de operações em dados mestres."""
    modelo_afetado = request.GET.get('modelo_afetado', '')
    usuario_id = request.GET.get('usuario_id', '')
    data_inicio = request.GET.get('data_inicio', '')
    data_fim = request.GET.get('data_fim', '')
    
    masterdata_service = MasterdataService()
    
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
    
    logs = masterdata_service.obter_logs_masterdata(
        modelo_afetado=modelo_afetado or None,
        usuario_id=int(usuario_id) if usuario_id else None,
        data_inicio=data_inicio_obj,
        data_fim=data_fim_obj,
        limite=100
    )
    
    # Paginação
    paginator = Paginator(logs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Opções para filtros
    modelos_disponiveis = [
        'Regiao', 'ZonaEntrega', 'HubLogistico', 
        'CatalogoDimensoes', 'RestricaoLogistica', 'PermissaoLogistica'
    ]
    
    from django.contrib.auth.models import User
    usuarios = User.objects.filter(is_active=True).order_by('username')
    
    context = {
        'page_obj': page_obj,
        'modelo_afetado': modelo_afetado,
        'usuario_id': usuario_id,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'modelos_disponiveis': modelos_disponiveis,
        'usuarios': usuarios,
    }
    
    return render(request, 'stock/logistica/masterdata/logs.html', context)
