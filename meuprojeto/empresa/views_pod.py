"""
Views para gerenciamento de POD (Prova de Entrega) e documentos logísticos.
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Q, Count, Sum, Avg
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from datetime import datetime, date, time, timedelta
import json
import logging
import base64

from .decorators import require_stock_access
from .models_pod import (
    TipoDocumento, ProvaEntrega, DocumentoPOD, AssinaturaDigital,
    GuiaRemessa, Etiqueta, ConfiguracaoPOD
)
from .models_stock import RastreamentoEntrega, EventoRastreamento
from .services.pod_service import PODService

logger = logging.getLogger(__name__)


# =============================================================================
# PROVAS DE ENTREGA
# =============================================================================

@login_required
@require_stock_access
def provas_entrega_list(request):
    """Lista de provas de entrega."""
    search = request.GET.get('search', '')
    status = request.GET.get('status', '')
    tipo_entrega = request.GET.get('tipo_entrega', '')
    validada = request.GET.get('validada', '')
    data_inicio = request.GET.get('data_inicio', '')
    data_fim = request.GET.get('data_fim', '')
    
    provas = ProvaEntrega.objects.select_related(
        'rastreamento_entrega', 'entregue_por', 'validada_por'
    )
    
    if search:
        provas = provas.filter(
            Q(codigo__icontains=search) |
            Q(rastreamento_entrega__codigo_rastreamento__icontains=search) |
            Q(nome_destinatario__icontains=search) |
            Q(endereco_entrega__icontains=search)
        )
    
    if status:
        provas = provas.filter(status=status)
    
    if tipo_entrega:
        provas = provas.filter(tipo_entrega=tipo_entrega)
    
    if validada:
        provas = provas.filter(validada=validada == 'true')
    
    if data_inicio:
        provas = provas.filter(data_entrega__date__gte=data_inicio)
    
    if data_fim:
        provas = provas.filter(data_entrega__date__lte=data_fim)
    
    provas = provas.order_by('-data_entrega')
    
    # Paginação
    paginator = Paginator(provas, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Opções para filtros
    status_choices = ProvaEntrega.STATUS_CHOICES
    tipo_entrega_choices = ProvaEntrega.TIPO_ENTREGA_CHOICES
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'status': status,
        'tipo_entrega': tipo_entrega,
        'validada': validada,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'status_choices': status_choices,
        'tipo_entrega_choices': tipo_entrega_choices,
    }
    
    return render(request, 'stock/logistica/pod/provas_list.html', context)


@login_required
@require_stock_access
def prova_entrega_detail(request, prova_id):
    """Detalhes de uma prova de entrega."""
    prova = get_object_or_404(ProvaEntrega, id=prova_id)
    
    # Documentos relacionados
    documentos = prova.documentos.all().order_by('-data_criacao')
    
    # Assinatura digital
    assinatura = getattr(prova, 'assinatura', None)
    
    context = {
        'prova': prova,
        'documentos': documentos,
        'assinatura': assinatura,
    }
    
    return render(request, 'stock/logistica/pod/prova_detail.html', context)


@login_required
@require_stock_access
def prova_entrega_create(request):
    """Criar nova prova de entrega."""
    if request.method == 'POST':
        try:
            # Usar request.POST para dados de formulário HTML
            pod_service = PODService()
            
            # Converter rastreamento_id para inteiro
            rastreamento_id = int(request.POST.get('rastreamento_entrega'))
            
            prova = pod_service.criar_prova_entrega(
                rastreamento_id=rastreamento_id,
                tipo_entrega=request.POST.get('tipo_entrega', 'COMPLETA'),
                endereco_entrega=request.POST.get('endereco_entrega', ''),
                latitude=request.POST.get('latitude'),
                longitude=request.POST.get('longitude'),
                precisao_gps=request.POST.get('precisao_gps'),
                nome_destinatario=request.POST.get('nome_destinatario', ''),
                documento_destinatario=request.POST.get('documento_destinatario', ''),
                telefone_destinatario=request.POST.get('telefone_destinatario', ''),
                parentesco_destinatario=request.POST.get('parentesco_destinatario', ''),
                observacoes=request.POST.get('observacoes', ''),
                motivo_recusa=request.POST.get('motivo_recusa', ''),
                entregue_por_id=request.user.id
            )
            
            messages.success(request, 'POD criada com sucesso!')
            return redirect('stock:pod:prova_detail', prova_id=prova.id)
            
        except Exception as e:
            logger.error(f"Erro ao criar prova de entrega: {e}")
            messages.error(request, f'Erro ao criar POD: {str(e)}')
    
    # GET - mostrar formulário
    rastreamentos = RastreamentoEntrega.objects.filter(
        status_atual__in=['EM_TRANSITO', 'EM_DISTRIBUICAO', 'ENTREGUE', 'PREPARANDO']
    ).select_related('transportadora', 'veiculo_interno')
    
    context = {
        'rastreamentos': rastreamentos,
        'tipo_entrega_choices': ProvaEntrega.TIPO_ENTREGA_CHOICES,
    }
    
    return render(request, 'stock/logistica/pod/prova_form.html', context)


@login_required
@require_stock_access
def adicionar_documento_pod(request, prova_id):
    """Adicionar documento à prova de entrega."""
    if request.method == 'POST':
        try:
            # Usar request.FILES para upload de arquivos
            pod_service = PODService()
            documento = pod_service.adicionar_documento_pod(
                prova_id=prova_id,
                tipo=request.POST.get('tipo', ''),
                arquivo_data=request.FILES.get('arquivo'),
                nome_arquivo=request.POST.get('nome', ''),
                descricao=request.POST.get('descricao', ''),
                observacoes=request.POST.get('observacoes', '')
            )
            
            messages.success(request, 'Documento adicionado com sucesso!')
            return redirect('stock:pod:prova_detail', prova_id=prova_id)
            
        except Exception as e:
            logger.error(f"Erro ao adicionar documento: {e}")
            messages.error(request, f'Erro ao adicionar documento: {str(e)}')
    
    prova = get_object_or_404(ProvaEntrega, id=prova_id)
    
    context = {
        'prova': prova,
        'tipo_documento_choices': DocumentoPOD.TIPO_DOCUMENTO_CHOICES,
    }
    
    return render(request, 'stock/logistica/pod/documento_form.html', context)


@login_required
@require_stock_access
def adicionar_assinatura_pod(request, prova_id):
    """Adicionar assinatura digital à prova de entrega."""
    if request.method == 'POST':
        try:
            # Usar request.POST para dados de formulário HTML
            pod_service = PODService()
            assinatura = pod_service.adicionar_assinatura_digital(
                prova_id=prova_id,
                dados_assinatura=request.POST.get('dados_assinatura', {}),
                imagem_assinatura_data=request.FILES.get('imagem_assinatura'),
                dispositivo=request.POST.get('dispositivo', ''),
                navegador=request.POST.get('navegador', ''),
                ip_address=request.META.get('REMOTE_ADDR', '')
            )
            
            messages.success(request, 'Assinatura adicionada com sucesso!')
            return redirect('stock:pod:prova_detail', prova_id=prova_id)
            
        except Exception as e:
            logger.error(f"Erro ao adicionar assinatura: {e}")
            messages.error(request, f'Erro ao adicionar assinatura: {str(e)}')
    
    prova = get_object_or_404(ProvaEntrega, id=prova_id)
    
    context = {
        'prova': prova,
    }
    
    return render(request, 'stock/logistica/pod/assinatura_form.html', context)


@login_required
@require_stock_access
def validar_prova_entrega(request, prova_id):
    """Validar prova de entrega."""
    if request.method == 'POST':
        try:
            # Usar request.POST para dados de formulário HTML
            pod_service = PODService()
            prova = pod_service.validar_prova_entrega(
                prova_id=prova_id,
                validada_por_id=request.user.id,
                observacoes_validacao=request.POST.get('observacoes_validacao', '')
            )
            
            messages.success(request, 'Prova de entrega validada com sucesso!')
            return redirect('stock:pod:prova_detail', prova_id=prova_id)
            
        except Exception as e:
            logger.error(f"Erro ao validar prova: {e}")
            messages.error(request, f'Erro ao validar prova: {str(e)}')
    
    prova = get_object_or_404(ProvaEntrega, id=prova_id)
    
    context = {
        'prova': prova,
    }
    
    return render(request, 'stock/logistica/pod/validar_prova_form.html', context)


# =============================================================================
# GUIAS DE REMESSA
# =============================================================================

@login_required
@require_stock_access
def guias_remessa_list(request):
    """Lista de guias de remessa."""
    search = request.GET.get('search', '')
    status = request.GET.get('status', '')
    impressa = request.GET.get('impressa', '')
    data_inicio = request.GET.get('data_inicio', '')
    data_fim = request.GET.get('data_fim', '')
    
    guias = GuiaRemessa.objects.select_related(
        'rastreamento_entrega', 'impressa_por'
    )
    
    if search:
        guias = guias.filter(
            Q(codigo__icontains=search) |
            Q(rastreamento_entrega__codigo_rastreamento__icontains=search) |
            Q(nome_destinatario__icontains=search) |
            Q(nome_remetente__icontains=search)
        )
    
    if status:
        guias = guias.filter(status=status)
    
    if impressa:
        guias = guias.filter(impressa=impressa == 'true')
    
    if data_inicio:
        guias = guias.filter(data_emissao__date__gte=data_inicio)
    
    if data_fim:
        guias = guias.filter(data_emissao__date__lte=data_fim)
    
    guias = guias.order_by('-data_emissao')
    
    # Paginação
    paginator = Paginator(guias, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Opções para filtros
    status_choices = GuiaRemessa.STATUS_CHOICES
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'status': status,
        'impressa': impressa,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'status_choices': status_choices,
    }
    
    return render(request, 'stock/logistica/pod/guias_list.html', context)


@login_required
@require_stock_access
def guia_remessa_detail(request, guia_id):
    """Detalhes de uma guia de remessa."""
    guia = get_object_or_404(GuiaRemessa, id=guia_id)
    
    # Etiquetas relacionadas
    etiquetas = guia.etiquetas.all().order_by('-data_criacao')
    
    context = {
        'guia': guia,
        'etiquetas': etiquetas,
    }
    
    return render(request, 'stock/logistica/pod/guia_detail.html', context)


@login_required
@require_stock_access
def guia_remessa_create(request):
    """Criar nova guia de remessa."""
    if request.method == 'POST':
        try:
            # Usar request.POST para dados de formulário HTML
            pod_service = PODService()
            
            # Converter rastreamento_id para inteiro
            rastreamento_id = int(request.POST.get('rastreamento_entrega'))
            
            # Converter data se necessário
            data_prevista = request.POST.get('data_prevista_entrega')
            if data_prevista:
                data_prevista = datetime.strptime(data_prevista, '%Y-%m-%d').date()
            
            guia = pod_service.gerar_guia_remessa(
                rastreamento_id=rastreamento_id,
                data_prevista_entrega=data_prevista,
                nome_remetente=request.POST.get('nome_remetente', ''),
                endereco_remetente=request.POST.get('endereco_remetente', ''),
                telefone_remetente=request.POST.get('telefone_remetente', ''),
                descricao_produto=request.POST.get('descricao_produto', ''),
                peso=request.POST.get('peso'),
                valor_declarado=request.POST.get('valor_declarado'),
                instrucoes_especiais=request.POST.get('instrucoes_especiais', ''),
                observacoes=request.POST.get('observacoes', '')
            )
            
            messages.success(request, 'Guia criada com sucesso!')
            return redirect('stock:pod:guia_detail', guia_id=guia.id)
            
        except Exception as e:
            logger.error(f"Erro ao criar guia: {e}")
            messages.error(request, f'Erro ao criar guia: {str(e)}')
    
    # GET - mostrar formulário
    rastreamentos = RastreamentoEntrega.objects.filter(
        status_atual__in=['PREPARANDO', 'EM_TRANSITO', 'EM_DISTRIBUICAO']
    ).select_related('transportadora', 'veiculo_interno')
    
    context = {
        'rastreamentos': rastreamentos,
    }
    
    return render(request, 'stock/logistica/pod/guia_form.html', context)


@login_required
@require_stock_access
def imprimir_guia_remessa(request, guia_id):
    """Imprimir guia de remessa."""
    guia = get_object_or_404(GuiaRemessa, id=guia_id)
    
    # Marcar como impressa
    guia.impressa = True
    guia.data_impressao = timezone.now()
    guia.impressa_por = request.user
    guia.status = 'IMPRESSA'
    guia.save()
    
    # Aqui você renderizaria o template de impressão
    # Por enquanto, retornamos uma resposta simples
    return HttpResponse(f"Guia {guia.codigo} marcada como impressa")


# =============================================================================
# ETIQUETAS
# =============================================================================

@login_required
@require_stock_access
def etiquetas_list(request):
    """Lista de etiquetas."""
    search = request.GET.get('search', '')
    tipo = request.GET.get('tipo', '')
    impressa = request.GET.get('impressa', '')
    data_inicio = request.GET.get('data_inicio', '')
    data_fim = request.GET.get('data_fim', '')
    
    etiquetas = Etiqueta.objects.select_related(
        'rastreamento_entrega', 'guia_remessa', 'impressa_por'
    )
    
    if search:
        etiquetas = etiquetas.filter(
            Q(codigo__icontains=search) |
            Q(codigo_barras__icontains=search) |
            Q(codigo_qr__icontains=search)
        )
    
    if tipo:
        etiquetas = etiquetas.filter(tipo=tipo)
    
    if impressa:
        etiquetas = etiquetas.filter(impressa=impressa == 'true')
    
    if data_inicio:
        etiquetas = etiquetas.filter(data_criacao__date__gte=data_inicio)
    
    if data_fim:
        etiquetas = etiquetas.filter(data_criacao__date__lte=data_fim)
    
    etiquetas = etiquetas.order_by('-data_criacao')
    
    # Paginação
    paginator = Paginator(etiquetas, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Opções para filtros
    tipo_choices = Etiqueta.TIPO_CHOICES
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'tipo': tipo,
        'impressa': impressa,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'tipo_choices': tipo_choices,
    }
    
    return render(request, 'stock/logistica/pod/etiquetas_list.html', context)


@login_required
@require_stock_access
def etiqueta_detail(request, etiqueta_id):
    """Detalhes de uma etiqueta."""
    etiqueta = get_object_or_404(Etiqueta, id=etiqueta_id)
    
    context = {
        'etiqueta': etiqueta,
    }
    
    return render(request, 'stock/logistica/pod/etiqueta_detail.html', context)


@login_required
@require_stock_access
def gerar_etiqueta_rastreamento(request, rastreamento_id):
    """Gerar etiqueta de rastreamento."""
    if request.method == 'POST':
        try:
            # Usar request.POST para dados de formulário HTML
            pod_service = PODService()
            etiqueta = pod_service.gerar_etiqueta_rastreamento(
                rastreamento_id=rastreamento_id,
                tipo=request.POST.get('tipo', 'RASTREAMENTO'),
                conteudo_personalizado=request.POST.get('conteudo_personalizado')
            )
            
            messages.success(request, 'Etiqueta gerada com sucesso!')
            return redirect('stock:pod:etiqueta_detail', etiqueta_id=etiqueta.id)
            
        except Exception as e:
            logger.error(f"Erro ao gerar etiqueta: {e}")
            messages.error(request, f'Erro ao gerar etiqueta: {str(e)}')
    
    rastreamento = get_object_or_404(RastreamentoEntrega, id=rastreamento_id)
    
    context = {
        'rastreamento': rastreamento,
        'tipo_choices': Etiqueta.TIPO_CHOICES,
    }
    
    return render(request, 'stock/logistica/pod/etiqueta_form.html', context)


@login_required
@require_stock_access
def imprimir_etiqueta(request, etiqueta_id):
    """Imprimir etiqueta."""
    etiqueta = get_object_or_404(Etiqueta, id=etiqueta_id)
    
    # Marcar como impressa
    etiqueta.impressa = True
    etiqueta.data_impressao = timezone.now()
    etiqueta.impressa_por = request.user
    etiqueta.save()
    
    # Aqui você renderizaria o template de impressão
    # Por enquanto, retornamos uma resposta simples
    return HttpResponse(f"Etiqueta {etiqueta.codigo} marcada como impressa")


# =============================================================================
# DASHBOARD DE POD
# =============================================================================

@login_required
@require_stock_access
def dashboard_pod(request):
    """Dashboard de POD e documentos logísticos."""
    hoje = timezone.now().date()
    
    # Estatísticas gerais
    pod_service = PODService()
    stats = pod_service.obter_estatisticas_pod()
    
    # Provas pendentes de validação
    provas_pendentes = pod_service.obter_provas_pendentes(dias_atraso=1)
    
    # Provas recentes (últimas 24h)
    provas_recentes = ProvaEntrega.objects.filter(
        data_entrega__gte=timezone.now() - timedelta(days=1)
    ).order_by('-data_entrega')[:10]
    
    # Guias pendentes de impressão
    guias_pendentes = GuiaRemessa.objects.filter(
        status='GERADA',
        impressa=False
    ).order_by('-data_emissao')[:5]
    
    # Etiquetas pendentes de impressão
    etiquetas_pendentes = Etiqueta.objects.filter(
        impressa=False
    ).order_by('-data_criacao')[:5]
    
    context = {
        'stats': stats,
        'provas_pendentes': provas_pendentes,
        'provas_recentes': provas_recentes,
        'guias_pendentes': guias_pendentes,
        'etiquetas_pendentes': etiquetas_pendentes,
    }
    
    return render(request, 'stock/logistica/pod/dashboard.html', context)
