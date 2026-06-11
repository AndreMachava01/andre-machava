"""
Views para observabilidade e métricas logísticas.
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum, Avg
from datetime import datetime, date, timedelta
from decimal import Decimal
import json
import logging

from .decorators import require_stock_access
from .models_observability import (
    AuditoriaTransicao, MetricaLogistica, ValorMetrica,
    RelatorioLogistico, ExecucaoRelatorio, APILog,
    ConfiguracaoObservabilidade
)
from .services.observability_service import ObservabilityService

logger = logging.getLogger(__name__)


@login_required
@require_stock_access
def observability_dashboard(request):
    """Dashboard de observabilidade."""
    # Estatísticas gerais
    observability_service = ObservabilityService()
    stats = observability_service.obter_estatisticas_observabilidade()
    
    auditorias_recentes = AuditoriaTransicao.objects.select_related('usuario').order_by('-data_operacao')[:8]
    metricas_recentes = ValorMetrica.objects.select_related('metrica').order_by('-data_referencia')[:8]
    execucoes_recentes = ExecucaoRelatorio.objects.select_related('relatorio', 'usuario').order_by('-data_inicio')[:8]
    logs_api_recentes = APILog.objects.select_related('usuario').order_by('-data_requisicao')[:8]

    context = {
        'stats': stats,
        'auditorias_recentes': auditorias_recentes,
        'metricas_recentes': metricas_recentes,
        'execucoes_recentes': execucoes_recentes,
        'logs_api_recentes': logs_api_recentes,
        'total_auditorias': stats['auditoria']['total_registros'],
        'total_metricas_valores': stats['metricas']['total_valores'],
        'total_execucoes': ExecucaoRelatorio.objects.count(),
        'total_api_logs': stats['api_logs']['total_logs'],
    }
    
    return render(request, 'stock/logistica/observability/dashboard.html', context)


# =============================================================================
# AUDITORIA
# =============================================================================

@login_required
@require_stock_access
def auditoria_list(request):
    """Lista de auditorias de transição."""
    search = request.GET.get('search', '')
    tipo_operacao = request.GET.get('tipo_operacao', '')
    modelo_afetado = request.GET.get('modelo_afetado', '')
    usuario_id = request.GET.get('usuario_id', '')
    data_inicio = request.GET.get('data_inicio', '')
    data_fim = request.GET.get('data_fim', '')
    sucesso = request.GET.get('sucesso', '')
    
    auditorias = AuditoriaTransicao.objects.select_related('usuario')
    
    if search:
        auditorias = auditorias.filter(
            Q(uuid__icontains=search) |
            Q(modelo_afetado__icontains=search) |
            Q(status_anterior__icontains=search) |
            Q(status_novo__icontains=search)
        )
    
    if tipo_operacao:
        auditorias = auditorias.filter(tipo_operacao=tipo_operacao)
    
    if modelo_afetado:
        auditorias = auditorias.filter(modelo_afetado=modelo_afetado)
    
    if usuario_id:
        auditorias = auditorias.filter(usuario_id=usuario_id)
    
    if data_inicio:
        auditorias = auditorias.filter(data_operacao__date__gte=data_inicio)
    
    if data_fim:
        auditorias = auditorias.filter(data_operacao__date__lte=data_fim)
    
    if sucesso:
        auditorias = auditorias.filter(sucesso=sucesso == 'true')
    
    auditorias = auditorias.order_by('-data_operacao')
    
    # Paginação
    paginator = Paginator(auditorias, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Opções para filtros
    tipo_operacao_choices = AuditoriaTransicao.TIPO_OPERACAO_CHOICES
    modelos_disponiveis = [
        'RastreamentoEntrega', 'Transportadora', 'VeiculoInterno',
        'CustoLogistico', 'FaturamentoFrete', 'ProvaEntrega',
        'Regiao', 'ZonaLogistica', 'HubLogistico'
    ]
    
    from django.contrib.auth.models import User
    usuarios = User.objects.filter(is_active=True).order_by('username')
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'tipo_operacao': tipo_operacao,
        'modelo_afetado': modelo_afetado,
        'usuario_id': usuario_id,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'sucesso': sucesso,
        'tipo_operacao_choices': tipo_operacao_choices,
        'modelos_disponiveis': modelos_disponiveis,
        'usuarios': usuarios,
    }
    
    return render(request, 'stock/logistica/observability/auditoria_list.html', context)


@login_required
@require_stock_access
def auditoria_detail(request, auditoria_id):
    """Detalhes de uma auditoria."""
    auditoria = get_object_or_404(AuditoriaTransicao, id=auditoria_id)
    
    context = {
        'auditoria': auditoria,
    }
    
    return render(request, 'stock/logistica/observability/auditoria_detail.html', context)


# =============================================================================
# MÉTRICAS
# =============================================================================

@login_required
@require_stock_access
def metricas_list(request):
    """Lista de métricas logísticas."""
    search = request.GET.get('search', '')
    tipo_metrica = request.GET.get('tipo_metrica', '')
    ativo = request.GET.get('ativo', '')
    
    metricas = MetricaLogistica.objects.all()
    
    if search:
        metricas = metricas.filter(
            Q(codigo__icontains=search) |
            Q(nome__icontains=search) |
            Q(descricao__icontains=search)
        )
    
    if tipo_metrica:
        metricas = metricas.filter(tipo_metrica=tipo_metrica)
    
    if ativo:
        metricas = metricas.filter(ativo=ativo == 'true')
    
    metricas = metricas.annotate(
        num_valores=Count('valores', distinct=True),
    ).order_by('tipo_metrica', 'nome')

    paginator = Paginator(metricas, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    hoje = timezone.now().date()
    ultimos_30_dias = hoje - timedelta(days=30)
    stats = {
        'total': MetricaLogistica.objects.count(),
        'activas': MetricaLogistica.objects.filter(ativo=True).count(),
        'inactivas': MetricaLogistica.objects.filter(ativo=False).count(),
        'valores_total': ValorMetrica.objects.count(),
        'valores_30_dias': ValorMetrica.objects.filter(
            data_referencia__gte=ultimos_30_dias
        ).count(),
    }
    valores_recentes = ValorMetrica.objects.select_related('metrica').order_by('-data_referencia')[:8]

    context = {
        'page_obj': page_obj,
        'search': search,
        'tipo_metrica': tipo_metrica,
        'ativo': ativo,
        'has_filters': bool(search or tipo_metrica or ativo),
        'tipo_metrica_choices': MetricaLogistica.TIPO_METRICA_CHOICES,
        'stats': stats,
        'valores_recentes': valores_recentes,
        'total_valores': stats['valores_total'],
    }

    return render(request, 'stock/logistica/observability/metricas_list.html', context)


@login_required
@require_stock_access
def metrica_detail(request, metrica_id):
    """Detalhes de uma métrica."""
    metrica = get_object_or_404(MetricaLogistica, id=metrica_id)
    
    # Valores recentes
    valores_recentes = metrica.valores.all().order_by('-data_referencia')[:20]
    
    context = {
        'metrica': metrica,
        'valores_recentes': valores_recentes,
    }
    
    return render(request, 'stock/logistica/observability/metrica_detail.html', context)


@login_required
@require_stock_access
def calcular_metricas(request):
    """Calcula métricas para um período específico."""
    from .models_stock import Transportadora
    from .models_masterdata import Regiao

    hoje = timezone.now().date()
    default_inicio = (hoje - timedelta(days=30)).isoformat()
    default_fim = hoje.isoformat()

    form_data = {
        'data_inicio': request.POST.get('data_inicio', default_inicio) if request.method == 'POST' else default_inicio,
        'data_fim': request.POST.get('data_fim', default_fim) if request.method == 'POST' else default_fim,
        'regiao': request.POST.get('regiao', '') if request.method == 'POST' else '',
        'transportadora': request.POST.get('transportadora', '') if request.method == 'POST' else '',
        'veiculo_interno': request.POST.get('veiculo_interno', '') if request.method == 'POST' else '',
    }

    if request.method == 'POST':
        try:
            observability_service = ObservabilityService()
            data_inicio = datetime.strptime(form_data['data_inicio'], '%Y-%m-%d').date()
            data_fim = datetime.strptime(form_data['data_fim'], '%Y-%m-%d').date()

            if data_fim < data_inicio:
                raise ValueError('A data fim não pode ser anterior à data início.')

            filtros = {}
            if form_data['regiao']:
                regiao = Regiao.objects.filter(pk=form_data['regiao']).first()
                if regiao:
                    filtros['regiao'] = regiao.nome
            if form_data['transportadora']:
                transportadora = Transportadora.objects.filter(pk=form_data['transportadora']).first()
                if transportadora:
                    filtros['transportadora'] = transportadora.nome
            if form_data['veiculo_interno']:
                from .services.freight_service import resolver_filtro_viatura_interna
                filtros.update(resolver_filtro_viatura_interna(form_data['veiculo_interno']))

            periodo_inicio = datetime.combine(data_inicio, datetime.min.time())
            periodo_fim = datetime.combine(data_fim, datetime.max.time())

            valores_salvos = observability_service.salvar_metricas_periodo(
                data_fim, periodo_inicio, periodo_fim, filtros
            )

            if valores_salvos:
                messages.success(
                    request,
                    f'{len(valores_salvos)} métrica(s) calculada(s) e guardada(s) para {data_inicio:%d/%m/%Y} a {data_fim:%d/%m/%Y}.',
                )
            else:
                messages.warning(
                    request,
                    'Cálculo concluído, mas nenhum valor foi guardado. Verifique se existem métricas activas no catálogo.',
                )
            return redirect('stock:observability:metricas_list')

        except Exception as e:
            logger.error(f"Erro ao calcular métricas: {e}")
            messages.error(request, f'Erro ao calcular métricas: {str(e)}')

    ultimos_30_dias = hoje - timedelta(days=30)
    stats = {
        'metricas_activas': MetricaLogistica.objects.filter(ativo=True).count(),
        'valores_total': ValorMetrica.objects.count(),
        'valores_30_dias': ValorMetrica.objects.filter(
            data_referencia__gte=ultimos_30_dias
        ).count(),
    }

    from .services.freight_service import opcoes_filtro_viatura_interna, queryset_transportadoras_externas

    context = {
        'transportadoras': queryset_transportadoras_externas(),
        'opcoes_viatura': opcoes_filtro_viatura_interna(),
        'regioes': Regiao.objects.filter(ativo=True).order_by('nome'),
        'metricas_activas': MetricaLogistica.objects.filter(ativo=True).order_by('tipo_metrica', 'nome'),
        'valores_recentes': ValorMetrica.objects.select_related('metrica').order_by('-data_referencia')[:8],
        'stats': stats,
        'form_data': form_data,
        'indicadores_calculo': [
            ('OTD', 'On-Time Delivery', '% entregas no prazo'),
            ('LEAD_TIME', 'Lead Time', 'Tempo médio de entrega'),
            ('COST_PER_DELIVERY', 'Custo por entrega', 'MT por entrega'),
            ('VOLUME_DELIVERED', 'Volume entregue', 'Unidades entregues'),
            ('EXCEPTION_RATE', 'Taxa de excepções', '% operações com excepção'),
            ('FLEET_UTILIZATION', 'Utilização da frota', '% capacidade usada'),
            ('ROUTE_EFFICIENCY', 'Eficiência de rota', 'Entregas por km'),
        ],
    }

    return render(request, 'stock/logistica/observability/calcular_metricas.html', context)


# =============================================================================
# RELATÓRIOS
# =============================================================================

@login_required
@require_stock_access
def relatorios_list(request):
    """Lista de relatórios logísticos."""
    search = request.GET.get('search', '')
    tipo_relatorio = request.GET.get('tipo_relatorio', '')
    ativo = request.GET.get('ativo', '')
    
    relatorios = RelatorioLogistico.objects.select_related('criado_por')
    
    if search:
        relatorios = relatorios.filter(
            Q(codigo__icontains=search) |
            Q(nome__icontains=search) |
            Q(descricao__icontains=search)
        )
    
    if tipo_relatorio:
        relatorios = relatorios.filter(tipo_relatorio=tipo_relatorio)
    
    if ativo:
        relatorios = relatorios.filter(ativo=ativo == 'true')
    
    relatorios = relatorios.annotate(
        num_execucoes=Count('execucoes', distinct=True),
        num_metricas=Count('metricas_incluidas', distinct=True),
    ).order_by('tipo_relatorio', 'nome')

    paginator = Paginator(relatorios, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    hoje = timezone.now().date()
    ultimos_30_dias = hoje - timedelta(days=30)
    stats = {
        'total': RelatorioLogistico.objects.count(),
        'activos': RelatorioLogistico.objects.filter(ativo=True).count(),
        'execucoes_total': ExecucaoRelatorio.objects.count(),
        'execucoes_30_dias': ExecucaoRelatorio.objects.filter(
            data_inicio__date__gte=ultimos_30_dias
        ).count(),
    }
    execucoes_recentes = ExecucaoRelatorio.objects.select_related(
        'relatorio', 'usuario'
    ).order_by('-data_inicio')[:8]

    context = {
        'page_obj': page_obj,
        'search': search,
        'tipo_relatorio': tipo_relatorio,
        'ativo': ativo,
        'has_filters': bool(search or tipo_relatorio or ativo),
        'tipo_relatorio_choices': RelatorioLogistico.TIPO_RELATORIO_CHOICES,
        'stats': stats,
        'execucoes_recentes': execucoes_recentes,
        'total_execucoes': stats['execucoes_total'],
    }

    return render(request, 'stock/logistica/observability/relatorios_list.html', context)


@login_required
@require_stock_access
def relatorio_detail(request, relatorio_id):
    """Detalhes de um relatório."""
    relatorio = get_object_or_404(RelatorioLogistico, id=relatorio_id)
    
    # Execuções recentes
    execucoes_recentes = relatorio.execucoes.all().order_by('-data_inicio')[:10]
    
    context = {
        'relatorio': relatorio,
        'execucoes_recentes': execucoes_recentes,
    }
    
    return render(request, 'stock/logistica/observability/relatorio_detail.html', context)


@login_required
@require_stock_access
def executar_relatorio(request, relatorio_id):
    """Executa um relatório."""
    relatorio = get_object_or_404(RelatorioLogistico, id=relatorio_id)
    
    if request.method == 'POST':
        try:
            # Processar parâmetros
            filtros_aplicados = {}
            for key, value in request.POST.items():
                if key.startswith('filtro_') and value:
                    filtros_aplicados[key[7:]] = value
            
            formato_solicitado = request.POST.get('formato', relatorio.formato_padrao)
            
            # Criar execução
            execucao = ExecucaoRelatorio.objects.create(
                relatorio=relatorio,
                usuario=request.user,
                filtros_aplicados=filtros_aplicados,
                formato_solicitado=formato_solicitado,
                status='PENDENTE'
            )
            
            # Aqui você implementaria a lógica real de geração do relatório
            # Por enquanto, apenas simular
            execucao.status = 'PROCESSANDO'
            execucao.save()
            
            # Simular processamento
            import time
            time.sleep(2)
            
            execucao.status = 'CONCLUIDO'
            execucao.data_fim = timezone.now()
            execucao.tempo_processamento_segundos = 2
            execucao.registros_processados = 100
            execucao.save()
            
            messages.success(request, 'Relatório executado com sucesso!')
            return redirect('stock:observability:relatorio_detail', relatorio_id=relatorio.id)
            
        except Exception as e:
            logger.error(f"Erro ao executar relatório: {e}")
            messages.error(request, f'Erro ao executar relatório: {str(e)}')
    
    # GET - mostrar formulário
    metricas_disponiveis = MetricaLogistica.objects.filter(ativo=True)
    
    context = {
        'relatorio': relatorio,
        'metricas_disponiveis': metricas_disponiveis,
        'formato_choices': RelatorioLogistico.FORMATO_EXPORTACAO_CHOICES,
    }
    
    return render(request, 'stock/logistica/observability/executar_relatorio.html', context)


# =============================================================================
# API LOGS
# =============================================================================

@login_required
@require_stock_access
def api_logs_list(request):
    """Lista de logs de API."""
    search = request.GET.get('search', '')
    metodo = request.GET.get('metodo', '')
    status_code = request.GET.get('status_code', '')
    usuario_id = request.GET.get('usuario_id', '')
    data_inicio = request.GET.get('data_inicio', '')
    data_fim = request.GET.get('data_fim', '')
    
    logs = APILog.objects.select_related('usuario')
    
    if search:
        logs = logs.filter(
            Q(endpoint__icontains=search) |
            Q(uuid__icontains=search)
        )
    
    if metodo:
        logs = logs.filter(metodo=metodo)
    
    if status_code:
        logs = logs.filter(status_code=status_code)
    
    if usuario_id:
        logs = logs.filter(usuario_id=usuario_id)
    
    if data_inicio:
        logs = logs.filter(data_requisicao__date__gte=data_inicio)
    
    if data_fim:
        logs = logs.filter(data_requisicao__date__lte=data_fim)
    
    logs = logs.order_by('-data_requisicao')
    
    # Paginação
    paginator = Paginator(logs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Opções para filtros
    metodo_choices = APILog.METODO_CHOICES
    
    from django.contrib.auth.models import User
    usuarios = User.objects.filter(is_active=True).order_by('username')
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'metodo': metodo,
        'status_code': status_code,
        'usuario_id': usuario_id,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'metodo_choices': metodo_choices,
        'usuarios': usuarios,
    }
    
    return render(request, 'stock/logistica/observability/api_logs_list.html', context)


@login_required
@require_stock_access
def api_log_detail(request, log_id):
    """Detalhes de um log de API."""
    log = get_object_or_404(APILog, id=log_id)
    
    context = {
        'log': log,
    }
    
    return render(request, 'stock/logistica/observability/api_log_detail.html', context)


# =============================================================================
# API ENDPOINTS
# =============================================================================

@login_required
@require_stock_access
def api_metricas(request):
    """API endpoint para métricas."""
    try:
        observability_service = ObservabilityService()
        
        # Processar parâmetros
        data_inicio = request.GET.get('data_inicio')
        data_fim = request.GET.get('data_fim')
        
        if not data_inicio or not data_fim:
            return JsonResponse({'erro': 'Parâmetros data_inicio e data_fim são obrigatórios'}, status=400)
        
        data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
        data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
        
        # Processar filtros
        filtros = {}
        if request.GET.get('regiao'):
            filtros['regiao'] = request.GET.get('regiao')
        if request.GET.get('transportadora'):
            filtros['transportadora'] = request.GET.get('transportadora')
        if request.GET.get('veiculo_interno'):
            filtros['veiculo_interno'] = request.GET.get('veiculo_interno')
        
        # Calcular métricas
        metricas = observability_service.calcular_todas_metricas(data_inicio, data_fim, filtros)
        
        return JsonResponse({
            'data_inicio': data_inicio.isoformat(),
            'data_fim': data_fim.isoformat(),
            'filtros': filtros,
            'metricas': {k: float(v) for k, v in metricas.items()}
        })
        
    except Exception as e:
        logger.error(f"Erro na API de métricas: {e}")
        return JsonResponse({'erro': str(e)}, status=500)


@login_required
@require_stock_access
def api_auditoria(request):
    """API endpoint para auditoria."""
    try:
        # Processar parâmetros
        modelo_afetado = request.GET.get('modelo_afetado')
        objeto_id = request.GET.get('objeto_id')
        
        if not modelo_afetado or not objeto_id:
            return JsonResponse({'erro': 'Parâmetros modelo_afetado e objeto_id são obrigatórios'}, status=400)
        
        # Obter auditorias
        auditorias = AuditoriaTransicao.objects.filter(
            modelo_afetado=modelo_afetado,
            objeto_id=objeto_id
        ).order_by('-data_operacao')
        
        # Converter para JSON
        auditorias_data = []
        for auditoria in auditorias:
            auditorias_data.append({
                'uuid': str(auditoria.uuid),
                'tipo_operacao': auditoria.tipo_operacao,
                'status_anterior': auditoria.status_anterior,
                'status_novo': auditoria.status_novo,
                'usuario': auditoria.usuario.username if auditoria.usuario else None,
                'data_operacao': auditoria.data_operacao.isoformat(),
                'sucesso': auditoria.sucesso,
                'duracao_ms': auditoria.duracao_ms
            })
        
        return JsonResponse({
            'modelo_afetado': modelo_afetado,
            'objeto_id': objeto_id,
            'auditorias': auditorias_data
        })
        
    except Exception as e:
        logger.error(f"Erro na API de auditoria: {e}")
        return JsonResponse({'erro': str(e)}, status=500)
