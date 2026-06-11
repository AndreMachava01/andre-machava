"""
Views para o módulo de Vendas
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django.utils import timezone
from datetime import datetime, date
from decimal import Decimal
import logging

from .models_stock import Item, ClienteServico, OrdemServico
from .models_base import Sucursal
from django.contrib.auth.models import User

logger = logging.getLogger(__name__)


@login_required
def vendas_main(request):
    """Página principal do módulo de Vendas"""
    try:
        from .models_stock import OrdemServico, ClienteServico
        
        # Estatísticas: Orçamentos = não confirmados; Pedidos = confirmados não faturados
        ids_cot_com_pedido = OrdemServico.objects.filter(
            codigo__startswith='OS',
            orcamento_origem_id__isnull=False
        ).values_list('orcamento_origem_id', flat=True).distinct()
        orcamentos_qs = OrdemServico.objects.filter(codigo__startswith='COT').exclude(id__in=ids_cot_com_pedido)
        total_orcamentos = orcamentos_qs.count()
        orcamentos_pendentes = orcamentos_qs.filter(status='AGENDADA').count()
        total_clientes = ClienteServico.objects.filter(ativo=True).count()
        pedidos_qs = OrdemServico.objects.filter(codigo__startswith='OS').exclude(numero_impressao_fatura__gt=0)
        total_pedidos = pedidos_qs.count()
        pedidos_pendentes = pedidos_qs.filter(status='AGENDADA').count()
        pedidos_aprovados = pedidos_qs.exclude(status='CANCELADA').count()
        total_faturas = OrdemServico.objects.filter(codigo__startswith='OS', numero_impressao_fatura__gt=0).count()
        
        # Filtro período (igual às outras telas principais)
        today = date.today()
        data_inicio = request.GET.get('data_inicio') or today.replace(day=1).isoformat()
        data_fim = request.GET.get('data_fim') or today.isoformat()
        
        context = {
            'total_pedidos': total_pedidos,
            'pedidos_pendentes': pedidos_pendentes,
            'pedidos_aprovados': pedidos_aprovados,
            'total_orcamentos': total_orcamentos,
            'orcamentos_pendentes': orcamentos_pendentes,
            'total_faturas': total_faturas,
            'total_clientes': total_clientes,
            'data_inicio': data_inicio,
            'data_fim': data_fim,
        }
        
        return render(request, 'vendas/main.html', context)
    except Exception as e:
        logger.error(f"Erro ao carregar página principal de vendas: {e}", exc_info=True)
        messages.error(request, 'Erro ao carregar página principal de vendas.')
        return redirect('vendas:main')


@login_required
def vendas_pedidos(request):
    """Lista de pedidos de venda (ordens de serviço OS)"""
    try:
        from .models_stock import OrdemServico
        from .models_stock import Item
        from django.core.paginator import Paginator
        from django.db.models import Q
        
        search_query = request.GET.get('q', '').strip()
        status_filter = request.GET.get('status', '')
        servico_id = request.GET.get('servico', '')
        
        ordens = OrdemServico.objects.select_related(
            'servico', 'cliente', 'responsavel', 'criado_por', 'orcamento_origem'
        ).prefetch_related(
            'servicos_orcamento__servico'
        ).filter(
            codigo__startswith='OS'
        ).exclude(
            numero_impressao_fatura__gt=0
        ).distinct()
        
        if search_query:
            ordens = ordens.filter(
                Q(codigo__icontains=search_query) |
                Q(cliente__nome__icontains=search_query) |
                Q(servico__nome__icontains=search_query) |
                Q(endereco_servico__icontains=search_query)
            )
        if status_filter:
            ordens = ordens.filter(status=status_filter)
        if servico_id:
            ordens = ordens.filter(servico_id=servico_id)
        
        ordens = ordens.order_by('-data_agendada', '-data_criacao')
        
        paginator = Paginator(ordens, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        base_qs = OrdemServico.objects.filter(codigo__startswith='OS').exclude(numero_impressao_fatura__gt=0)
        total_pedidos = base_qs.count()
        pedidos_agendados = base_qs.filter(status='AGENDADA').count()
        pedidos_em_andamento = base_qs.filter(status='EM_ANDAMENTO').count()
        pedidos_concluidos = base_qs.filter(status='CONCLUIDA').count()
        pedidos_cancelados = base_qs.filter(status='CANCELADA').count()
        
        servicos = Item.objects.filter(tipo='PRODUTO', produto_tipo='SERVICO', status='ATIVO').order_by('nome')
        
        context = {
            'title': 'Pedidos de Venda',
            'page_obj': page_obj,
            'pedidos': page_obj,
            'search_query': search_query or '',
            'status_filter': status_filter or '',
            'servico_id': servico_id or '',
            'servicos': servicos,
            'total_pedidos': total_pedidos,
            'pedidos_agendados': pedidos_agendados,
            'pedidos_em_andamento': pedidos_em_andamento,
            'pedidos_concluidos': pedidos_concluidos,
            'pedidos_cancelados': pedidos_cancelados,
        }
        return render(request, 'vendas/pedidos/list.html', context)
    except Exception as e:
        logger.error(f'Erro ao listar pedidos de venda: {e}', exc_info=True)
        messages.error(request, 'Erro ao carregar lista de pedidos.')
        return render(request, 'vendas/pedidos/list.html', {
            'title': 'Pedidos de Venda',
            'page_obj': None,
            'pedidos': [],
            'search_query': '',
            'status_filter': '',
            'servico_id': '',
            'servicos': [],
            'total_pedidos': 0,
            'pedidos_agendados': 0,
            'pedidos_em_andamento': 0,
            'pedidos_concluidos': 0,
            'pedidos_cancelados': 0,
        })


@login_required
def vendas_pedido_detail(request, id):
    """Detalhe do pedido (ordem de serviço) — vista só de leitura no sector Vendas."""
    from .models_stock import OrdemServico
    ordem = get_object_or_404(
        OrdemServico.objects.select_related('cliente', 'responsavel', 'criado_por', 'orcamento_origem').prefetch_related(
            'servicos_orcamento__servico',
            'servicos_orcamento__itens__item',
            'transportes_orcamento__transportadora',
        ),
        id=id
    )
    if not ordem.codigo.startswith('OS'):
        return redirect('vendas:pedidos')
    context = {
        'title': f'Pedido {ordem.codigo}',
        'ordem': ordem,
    }
    return render(request, 'vendas/pedidos/detail.html', context)


@login_required
def vendas_pedido_emitir_fatura(request, id):
    """Emitir ou reimprimir fatura do pedido — vista no sector Vendas (sem abrir Produção)."""
    from .models_stock import OrdemServico
    from .fatura_ordem_utils import build_fatura_context
    ordem = get_object_or_404(
        OrdemServico.objects.select_related('cliente', 'responsavel', 'criado_por', 'orcamento_origem').prefetch_related(
            'servicos_orcamento__servico',
            'servicos_orcamento__itens__item',
            'transportes_orcamento__transportadora'
        ),
        id=id
    )
    if not ordem.codigo.startswith('OS'):
        messages.error(request, 'Pedido inválido.')
        return redirect('vendas:pedidos')
    if ordem.status != 'CONCLUIDA':
        messages.warning(request, 'Apenas pedidos concluídos podem ter faturas emitidas.')
        return redirect('vendas:pedido_detail', id=id)
    try:
        context = build_fatura_context(request, ordem)
        context['return_to_vendas'] = True
        return render(request, 'servicos/ordens/fatura.html', context)
    except ValueError as e:
        messages.warning(request, str(e))
        return redirect('vendas:pedido_detail', id=id)
    except Exception as e:
        logger.error(f'Erro ao emitir fatura do pedido {id}: {e}', exc_info=True)
        messages.error(request, f'Erro ao emitir fatura: {str(e)}')
        return redirect('vendas:pedido_detail', id=id)


@login_required
def vendas_pedido_emitir_garantia(request, id):
    """Emitir garantia para pedido concluído (vendedores fornecem garantias após emitir a fatura)."""
    from datetime import datetime, timedelta
    from django.db.models import Q
    from django.db import transaction
    ordem = get_object_or_404(
        OrdemServico.objects.select_related('cliente', 'responsavel', 'criado_por', 'orcamento_origem').prefetch_related(
            'servicos_orcamento__servico',
            'servicos_orcamento__itens__item',
            'transportes_orcamento__transportadora'
        ),
        id=id
    )
    if not ordem.codigo or not ordem.codigo.startswith('OS'):
        messages.error(request, 'Pedido inválido.')
        return redirect('vendas:pedidos')
    if ordem.status != 'CONCLUIDA':
        messages.warning(request, 'Apenas pedidos concluídos podem ter garantias emitidas.')
        return redirect('vendas:pedido_detail', id=id)
    if not ordem.numero_impressao_fatura or ordem.numero_impressao_fatura <= 0:
        messages.warning(request, 'A garantia depende da fatura. Emita primeiro a fatura do pedido.')
        return redirect('vendas:pedido_detail', id=id)
    try:
        from .models_base import DadosEmpresa
        from django.conf import settings
        dados_empresa = DadosEmpresa.objects.first()
        hoje = datetime.now()
        data_emissao = hoje.date()
        hora_emissao = hoje.time()
        ano_atual = hoje.year
        garantias_antes = OrdemServico.objects.filter(
            codigo__startswith='OS',
            status='CONCLUIDA',
            numero_impressao_garantia__gt=0
        ).exclude(id=ordem.id)
        if ordem.data_conclusao:
            data_ref_ordem = ordem.data_conclusao.date()
            garantias_antes = garantias_antes.filter(
                Q(data_conclusao__date__year=ano_atual) & (
                    Q(data_conclusao__date__lt=data_ref_ordem) |
                    Q(data_conclusao__date=data_ref_ordem, id__lt=ordem.id)
                ) |
                Q(data_conclusao__isnull=True, data_criacao__date__year=ano_atual) & (
                    Q(data_criacao__date__lt=data_ref_ordem) |
                    Q(data_criacao__date=data_ref_ordem, id__lt=ordem.id)
                )
            )
        else:
            data_ref_ordem = ordem.data_criacao.date()
            garantias_antes = garantias_antes.filter(
                Q(data_criacao__date__year=ano_atual) & (
                    Q(data_criacao__date__lt=data_ref_ordem) |
                    Q(data_criacao__date=data_ref_ordem, id__lt=ordem.id)
                )
            )
        numero_sequencial = garantias_antes.count() + 1
        numero_garantia = f"GAR-{ano_atual}-{numero_sequencial:06d}"
        with transaction.atomic():
            ordem.numero_impressao_garantia = (ordem.numero_impressao_garantia or 0) + 1
            ordem.save(update_fields=['numero_impressao_garantia'])
        tipo_documento = 'ORIGINAL' if ordem.numero_impressao_garantia == 1 else f'CÓPIA {ordem.numero_impressao_garantia - 1}'
        data_inicio_garantia = ordem.data_conclusao.date() if ordem.data_conclusao else ordem.data_criacao.date()
        validade_dias = ordem.validade_garantia_dias if ordem.validade_garantia_dias else 90
        data_validade_garantia = data_inicio_garantia + timedelta(days=validade_dias)
        if ordem.cliente:
            cliente_nome = ordem.cliente.nome
            cliente_documento = getattr(ordem.cliente, 'nuit', '') or ''
            cliente_endereco = getattr(ordem.cliente, 'endereco', '') or ''
            cliente_email = getattr(ordem.cliente, 'email', '') or ''
        else:
            cliente_nome = ordem.nome_cliente_pagamento or 'Cliente não identificado'
            cliente_documento = ordem.nuit_cliente_pagamento or ''
            cliente_endereco = ordem.endereco_servico or ''
            cliente_email = ''
        lista_servicos = []
        for servico_orc in ordem.servicos_orcamento.all():
            try:
                nome_servico = getattr(servico_orc, 'nome_para_documento', None) or (servico_orc.servico.nome if servico_orc.servico else 'Serviço não especificado')
            except Exception:
                nome_servico = servico_orc.servico.nome if servico_orc.servico else 'Serviço não especificado'
            quantidade = servico_orc.quantidade or 1
            lista_servicos.append(f"{quantidade} x {nome_servico}")
        context = {
            'request': request,
            'ordem': ordem,
            'dados_empresa': dados_empresa,
            'servicos_orcamento': ordem.servicos_orcamento.all(),
            'numero_garantia': numero_garantia,
            'data_emissao': data_emissao,
            'hora_emissao': hora_emissao,
            'data_inicio_garantia': data_inicio_garantia,
            'data_validade_garantia': data_validade_garantia,
            'tipo_documento': tipo_documento,
            'cliente_nome': cliente_nome,
            'cliente_documento': cliente_documento,
            'cliente_endereco': cliente_endereco,
            'cliente_email': cliente_email,
            'lista_servicos': lista_servicos,
            'MEDIA_URL': settings.MEDIA_URL,
            'return_to_vendas': True,
        }
        return render(request, 'producao/servicos/ordens/garantia.html', context)
    except Exception as e:
        logger.error(f'Erro ao emitir garantia do pedido {id}: {e}', exc_info=True)
        messages.error(request, f'Erro ao emitir garantia: {str(e)}')
        return redirect('vendas:pedido_detail', id=id)


@login_required
@require_http_methods(["GET", "POST"])
def vendas_orcamento_edit(request, id):
    """Editar orçamento (cotação) — chama a lógica de Produção sem redirecionar para Produção."""
    # #region agent log
    try:
        import json as _json, time as _time
        _data = {
            'method': request.method,
            'orcamento_id': id,
            'path': request.path,
        }
        _log = open('debug-630fd6.log', 'a', encoding='utf-8')
        _log.write(_json.dumps({
            'sessionId': '630fd6',
            'runId': 'pre-fix',
            'hypothesisId': 'H2',
            'location': 'vendas_orcamento_edit',
            'message': 'entry vendas_orcamento_edit',
            'data': _data,
            'timestamp': int(_time.time() * 1000),
        }) + '\n')
        _log.close()
    except Exception:
        pass
    # #endregion
    from . import views_producao
    return views_producao.producao_servico_orcamento_edit(request, id, from_vendas_param=True)


@login_required
def vendas_preview_contrato(request, orcamento_id):
    """Pré-visualização do contrato (chama lógica de Produção sem redirecionar para Produção)."""
    from . import views_producao
    return views_producao.preview_contrato_servico(request, orcamento_id, from_vendas=True)


@login_required
def vendas_gerar_contrato(request, orcamento_id):
    """Gera o PDF do contrato (chama lógica de Produção sem redirecionar para Produção)."""
    from . import views_producao
    return views_producao.gerar_contrato_servico(request, orcamento_id, from_vendas=True)


@login_required
@require_http_methods(["GET", "POST"])
def vendas_editar_contrato(request, orcamento_id):
    """Editar cláusulas do contrato (chama lógica de Produção sem redirecionar para Produção)."""
    from . import views_producao
    return views_producao.editar_contrato_servico(request, orcamento_id, from_vendas=True)


@login_required
def vendas_contratos(request):
    """Lista de orçamentos para os vendedores fornecerem contratos (preview/gerar em Vendas).
    Oculta orçamentos cujo pedido já foi faturado (ficam só em Faturamento)."""
    from django.db.models import Exists, OuterRef
    # Orçamentos faturados: COT com pedido (OS) que já tem fatura emitida
    pedidos_faturados = OrdemServico.objects.filter(
        codigo__startswith='OS',
        orcamento_origem_id=OuterRef('pk'),
        numero_impressao_fatura__gt=0
    )
    orcamentos = OrdemServico.objects.filter(
        codigo__startswith='COT'
    ).exclude(
        Exists(pedidos_faturados)
    ).select_related(
        'cliente'
    ).prefetch_related(
        'servicos_orcamento__servico',
    ).order_by('-data_criacao')[:200]
    context = {
        'title': 'Contratos',
        'orcamentos': orcamentos,
    }
    return render(request, 'vendas/contratos/list.html', context)


@login_required
def vendas_orcamento_detail(request, id):
    """Detalhes do orçamento (cotação) em Vendas."""
    orcamento = get_object_or_404(
        OrdemServico.objects.select_related('cliente', 'responsavel', 'criado_por').prefetch_related(
            'servicos_orcamento__servico',
            'servicos_orcamento__itens__item',
            'transportes_orcamento__transportadora',
        ),
        id=id
    )
    if not orcamento.codigo or not orcamento.codigo.startswith('COT'):
        messages.error(request, 'Não é uma cotação.')
        return redirect('vendas:orcamentos_list')
    pedido = OrdemServico.objects.filter(codigo__startswith='OS', orcamento_origem=orcamento).first()
    context = {
        'title': f'Orçamento {orcamento.codigo}',
        'orcamento': orcamento,
        'pedido': pedido,
    }
    return render(request, 'vendas/orcamento/detail.html', context)


@login_required
def vendas_cotacao_confirmar(request, id):
    """Página em Vendas para confirmar e converter cotação em pedido."""
    from .models_stock import OrdemServico as OS
    orcamento = get_object_or_404(
        OS.objects.select_related('cliente').prefetch_related(
            'servicos_orcamento__servico',
            'transportes_orcamento__transportadora',
        ),
        id=id
    )
    if not orcamento.codigo or not orcamento.codigo.startswith('COT'):
        messages.error(request, 'Não é uma cotação.')
        return redirect('vendas:orcamentos_list')
    ja_tem_pedido = OS.objects.filter(codigo__startswith='OS', orcamento_origem=orcamento).first()
    context = {
        'title': f'Converter cotação {orcamento.codigo} em pedido',
        'orcamento': orcamento,
        'ja_tem_pedido': ja_tem_pedido,
    }
    return render(request, 'vendas/cotacao/confirmar.html', context)


@login_required
@require_http_methods(['POST'])
def vendas_confirmar_cotacao_acao(request, id):
    """Converte cotação em ordem de serviço (pedido) e redireciona para o pedido em Vendas."""
    from .models_stock import (
        OrdemServico,
        ServicoOrcamentoServico,
        ItemOrcamentoServico,
        TransporteOrcamentoServico,
    )
    orcamento = get_object_or_404(
        OrdemServico.objects.select_related('cliente', 'responsavel', 'criado_por').prefetch_related(
            'servicos_orcamento__servico',
            'servicos_orcamento__itens__item',
            'transportes_orcamento__transportadora',
            'parcelas_pagamento__servicos',
        ),
        id=id
    )
    if not orcamento.codigo or not orcamento.codigo.startswith('COT'):
        messages.error(request, 'Não é uma cotação.')
        return redirect('vendas:orcamentos_list')
    ordem_existente = OrdemServico.objects.filter(codigo__startswith='OS', orcamento_origem=orcamento).first()
    if ordem_existente:
        messages.info(request, f'Já existe o pedido {ordem_existente.codigo} criado a partir desta cotação.')
        return redirect('vendas:pedido_detail', id=ordem_existente.id)
    try:
        with transaction.atomic():
            ordem_servico = OrdemServico(
                orcamento_origem=orcamento,
                departamento_origem='VENDAS',
                servico=None,
                cliente=orcamento.cliente,
                data_agendada=orcamento.data_agendada,
                endereco_servico=orcamento.endereco_servico,
                cidade_servico=orcamento.cidade_servico,
                equipe=orcamento.equipe,
                responsavel=orcamento.responsavel,
                prioridade=orcamento.prioridade,
                quantidade=Decimal('1.00'),
                valor_unitario=None,
                desconto=orcamento.desconto,
                observacoes=orcamento.observacoes,
                problema_relatado=orcamento.problema_relatado,
                criado_por=request.user,
                status='AGENDADA',
                forma_pagamento=getattr(orcamento, 'forma_pagamento', None),
                nome_cliente_pagamento=getattr(orcamento, 'nome_cliente_pagamento', None),
                nuit_cliente_pagamento=getattr(orcamento, 'nuit_cliente_pagamento', None),
                telefone_cliente_pagamento=getattr(orcamento, 'telefone_cliente_pagamento', None),
            )
            ordem_servico.save(is_orcamento=False)
            for servico_orc in orcamento.servicos_orcamento.all():
                ServicoOrcamentoServico.objects.create(
                    ordem_servico=ordem_servico,
                    servico=servico_orc.servico,
                    quantidade=servico_orc.quantidade,
                    valor_unitario=servico_orc.valor_unitario,
                    desconto_percentual=servico_orc.desconto_percentual,
                    desconto=servico_orc.desconto,
                    observacoes=servico_orc.observacoes,
                    nome_documento=getattr(servico_orc, 'nome_documento', None),
                )
            for servico_orc in orcamento.servicos_orcamento.all():
                servico_ordem = ordem_servico.servicos_orcamento.filter(servico=servico_orc.servico).first()
                if servico_ordem:
                    for item_orc in servico_orc.itens.all():
                        ItemOrcamentoServico.objects.create(
                            servico_orcamento=servico_ordem,
                            ordem_servico=ordem_servico,
                            item=item_orc.item,
                            quantidade=item_orc.quantidade,
                            valor_unitario=item_orc.valor_unitario,
                            desconto_percentual=getattr(item_orc, 'desconto_percentual', Decimal('0.00')),
                            desconto=item_orc.desconto,
                        )
            for transporte_orc in orcamento.transportes_orcamento.all():
                TransporteOrcamentoServico.objects.create(
                    ordem_servico=ordem_servico,
                    transportadora=transporte_orc.transportadora,
                    tipo_transporte=transporte_orc.tipo_transporte,
                    valor_frete=transporte_orc.valor_frete,
                )
            orcamento.status = 'CONCLUIDA'
            orcamento.save(update_fields=['status'])
            from .parcelas_vendas_utils import _copiar_parcelas_para_ordem, processar_parcelas_vendas_receber
            _copiar_parcelas_para_ordem(orcamento, ordem_servico)
            processar_parcelas_vendas_receber(ordem_servico, request.user, 'ASSINATURA')
        messages.success(request, f'Pedido {ordem_servico.codigo} criado. Defina o plano de execução (etapas) para continuar.')
        from django.urls import reverse
        url = reverse('producao:servico_ordem_plano_execucao', args=[ordem_servico.id])
        return redirect(url + '?from=vendas')
    except Exception as e:
        logger.error(f'Erro ao converter cotação {id} em pedido: {e}', exc_info=True)
        messages.error(request, f'Erro ao criar pedido: {str(e)}')
        return redirect('vendas:cotacao_confirmar', id=id)


@login_required
@require_http_methods(['POST'])
def vendas_pedido_alterar_status(request, id):
    """Alterar status do pedido (iniciar, pausar, retomar, concluir) — em Vendas."""
    ordem = get_object_or_404(OrdemServico, id=id)
    if not ordem.codigo or not ordem.codigo.startswith('OS'):
        messages.error(request, 'Pedido inválido.')
        return redirect('vendas:pedidos')
    if (ordem.numero_impressao_fatura or 0) > 0:
        messages.error(request, 'Este pedido já teve fatura emitida e não pode ser alterado.')
        return redirect('vendas:pedido_detail', id=id)
    acao = (request.POST.get('acao') or '').strip()
    try:
        with transaction.atomic():
            if acao == 'iniciar':
                if ordem.status in ('CONCLUIDA', 'CANCELADA'):
                    messages.error(request, 'Não é possível iniciar uma ordem concluída ou cancelada.')
                else:
                    ordem.status = 'EM_ANDAMENTO'
                    if not ordem.data_inicio:
                        ordem.data_inicio = timezone.now()
                    ordem.save()
                    messages.success(request, f'Pedido {ordem.codigo} iniciado.')
            elif acao == 'pausar':
                if ordem.status != 'EM_ANDAMENTO':
                    messages.error(request, 'Apenas ordens em andamento podem ser pausadas.')
                else:
                    ordem.status = 'PAUSADA'
                    ordem.save()
                    messages.success(request, f'Pedido {ordem.codigo} pausado.')
            elif acao == 'retomar':
                if ordem.status != 'PAUSADA':
                    messages.error(request, 'Apenas ordens pausadas podem ser retomadas.')
                else:
                    ordem.status = 'EM_ANDAMENTO'
                    ordem.save()
                    messages.success(request, f'Pedido {ordem.codigo} retomado.')
            elif acao == 'concluir':
                if ordem.status == 'CANCELADA':
                    messages.error(request, 'Não é possível concluir uma ordem cancelada.')
                else:
                    ordem.status = 'CONCLUIDA'
                    if not ordem.data_conclusao:
                        ordem.data_conclusao = timezone.now()
                    ordem.save()
                    from .parcelas_vendas_utils import processar_parcelas_vendas_receber
                    processar_parcelas_vendas_receber(ordem, request.user, 'CONCLUSAO')
                    messages.success(request, f'Pedido {ordem.codigo} concluído.')
            else:
                messages.error(request, 'Ação inválida.')
    except Exception as e:
        logger.error(f'Erro ao alterar status do pedido {id}: {e}', exc_info=True)
        messages.error(request, f'Erro ao alterar status: {str(e)}')
    return redirect('vendas:pedido_detail', id=id)


@login_required
@require_http_methods(['GET', 'POST'])
def vendas_pedido_edit(request, id):
    """Editar pedido (datas, status, endereço, equipe) — em Vendas."""
    ordem = get_object_or_404(
        OrdemServico.objects.select_related('cliente', 'responsavel').prefetch_related('servicos_orcamento__servico'),
        id=id
    )
    if not ordem.codigo or not ordem.codigo.startswith('OS'):
        messages.error(request, 'Pedido inválido.')
        return redirect('vendas:pedidos')
    if (ordem.numero_impressao_fatura or 0) > 0:
        messages.error(request, 'Este pedido já teve fatura emitida e não pode ser editado.')
        return redirect('vendas:pedido_detail', id=id)
    if request.method == 'POST':
        try:
            data_agendada_str = request.POST.get('data_agendada')
            hora = request.POST.get('hora_agendada', '09:00')
            ordem.endereco_servico = request.POST.get('endereco_servico', '') or ordem.endereco_servico
            ordem.cidade_servico = request.POST.get('cidade_servico', '') or ordem.cidade_servico
            ordem.equipe = request.POST.get('equipe', '') or ordem.equipe
            ordem.status = request.POST.get('status', ordem.status)
            responsavel_id = request.POST.get('responsavel')
            ordem.responsavel_id = int(responsavel_id) if responsavel_id else None
            if data_agendada_str:
                try:
                    dt = datetime.strptime(f'{data_agendada_str} {hora}', '%Y-%m-%d %H:%M')
                    ordem.data_agendada = timezone.make_aware(dt)
                except ValueError:
                    pass
            if ordem.status == 'EM_ANDAMENTO' and not ordem.data_inicio:
                ordem.data_inicio = timezone.now()
            if ordem.status == 'CONCLUIDA' and not ordem.data_conclusao:
                ordem.data_conclusao = timezone.now()
            ordem.save()
            if ordem.status == 'CONCLUIDA':
                from .parcelas_vendas_utils import processar_parcelas_vendas_receber
                processar_parcelas_vendas_receber(ordem, request.user, 'CONCLUSAO')
            messages.success(request, f'Pedido {ordem.codigo} atualizado.')
            return redirect('vendas:pedido_detail', id=id)
        except Exception as e:
            logger.error(f'Erro ao editar pedido {id}: {e}', exc_info=True)
            messages.error(request, f'Erro ao guardar: {str(e)}')
    usuarios = User.objects.filter(is_active=True).order_by('username')
    context = {
        'title': f'Editar pedido {ordem.codigo}',
        'ordem': ordem,
        'status_choices': OrdemServico.STATUS_CHOICES,
        'usuarios': usuarios,
    }
    return render(request, 'vendas/pedidos/edit.html', context)


@login_required
def vendas_faturamento(request):
    """Faturamento de vendas — ordens de serviço concluídas (com/sem fatura emitida)."""
    try:
        from .models_stock import OrdemServico
        from django.core.paginator import Paginator
        from django.db.models import Q
        from datetime import datetime

        search_query = request.GET.get('q', '').strip()
        cliente_id = request.GET.get('cliente', '')
        data_inicio = request.GET.get('data_inicio', '')
        data_fim = request.GET.get('data_fim', '')
        tem_fatura = request.GET.get('tem_fatura', '')

        ordens = OrdemServico.objects.select_related(
            'cliente', 'responsavel', 'criado_por', 'orcamento_origem'
        ).prefetch_related(
            'servicos_orcamento__servico'
        ).filter(
            codigo__startswith='OS',
            status='CONCLUIDA'
        ).distinct()

        if search_query:
            ordens = ordens.filter(
                Q(codigo__icontains=search_query) |
                Q(cliente__nome__icontains=search_query) |
                Q(nome_cliente_pagamento__icontains=search_query) |
                Q(endereco_servico__icontains=search_query)
            )
        if cliente_id:
            ordens = ordens.filter(cliente_id=cliente_id)
        if data_inicio:
            try:
                data_inicio_obj = datetime.strptime(data_inicio, '%Y-%m-%d').date()
                ordens = ordens.filter(data_conclusao__date__gte=data_inicio_obj)
            except ValueError:
                pass
        if data_fim:
            try:
                data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d').date()
                ordens = ordens.filter(data_conclusao__date__lte=data_fim_obj)
            except ValueError:
                pass
        if tem_fatura == 'sim':
            ordens = ordens.filter(numero_impressao_fatura__gt=0)
        elif tem_fatura == 'nao':
            ordens = ordens.filter(Q(numero_impressao_fatura__isnull=True) | Q(numero_impressao_fatura=0))

        ordens = ordens.order_by('-data_conclusao', '-data_criacao')

        paginator = Paginator(ordens, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        total_ordens = ordens.count()
        ordens_com_fatura = ordens.filter(numero_impressao_fatura__gt=0).count()
        ordens_sem_fatura = total_ordens - ordens_com_fatura
        total_faturado = Decimal('0.00')
        for ordem in ordens:
            if ordem.valor_total:
                total_faturado += ordem.valor_total

        clientes = ClienteServico.objects.filter(ativo=True).order_by('nome')

        context = {
            'title': 'Faturamento',
            'page_obj': page_obj,
            'ordens': page_obj,
            'search_query': search_query or '',
            'cliente_id': cliente_id,
            'data_inicio': data_inicio,
            'data_fim': data_fim,
            'tem_fatura': tem_fatura,
            'total_ordens': total_ordens,
            'ordens_com_fatura': ordens_com_fatura,
            'ordens_sem_fatura': ordens_sem_fatura,
            'total_faturado': total_faturado,
            'clientes': clientes,
        }
        return render(request, 'vendas/faturamento/list.html', context)
    except Exception as e:
        logger.error(f'Erro ao carregar faturamento: {e}', exc_info=True)
        messages.error(request, 'Erro ao carregar faturamento.')
        return render(request, 'vendas/faturamento/list.html', {
            'title': 'Faturamento',
            'page_obj': None,
            'ordens': [],
            'search_query': '',
            'cliente_id': '',
            'data_inicio': '',
            'data_fim': '',
            'tem_fatura': '',
            'total_ordens': 0,
            'ordens_com_fatura': 0,
            'ordens_sem_fatura': 0,
            'total_faturado': Decimal('0.00'),
            'clientes': ClienteServico.objects.none(),
        })


@login_required
def vendas_dashboard(request):
    """Dashboard de vendas"""
    return render(request, 'vendas/dashboard.html', {'title': 'Dashboard de Vendas'})


@login_required
def vendas_orcamentos_list(request):
    """Lista de orçamentos"""
    try:
        from .models_stock import OrdemServico
        from django.core.paginator import Paginator
        
        # Apenas orçamentos não confirmados (sem pedido criado). Confirmados = Pedidos de Venda; Faturados = Faturamento.
        ids_com_pedido = OrdemServico.objects.filter(
            codigo__startswith='OS',
            orcamento_origem_id__isnull=False
        ).values_list('orcamento_origem_id', flat=True).distinct()
        orcamentos = OrdemServico.objects.filter(codigo__startswith='COT').exclude(
            id__in=ids_com_pedido
        ).order_by('-data_criacao')
        paginator = Paginator(orcamentos, 20)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)
        ids_na_pagina = [o.id for o in page_obj]
        pedidos_dos_orcamentos = dict(
            OrdemServico.objects.filter(
                codigo__startswith='OS',
                orcamento_origem_id__in=ids_na_pagina
            ).values_list('orcamento_origem_id', 'id')
        )
        for o in page_obj:
            o.pedido_id = pedidos_dos_orcamentos.get(o.id)
        context = {
            'title': 'Lista de Orçamentos',
            'page_obj': page_obj,
            'orcamentos': page_obj,
        }
        return render(request, 'vendas/orcamento/list.html', context)
    except Exception as e:
        logger.error(f"Erro ao carregar lista de orçamentos: {e}", exc_info=True)
        messages.error(request, 'Erro ao carregar lista de orçamentos.')
        return redirect('vendas:main')


@login_required
def vendas_orcamentos_pendentes(request):
    """Orçamentos pendentes"""
    try:
        from .models_stock import OrdemServico
        from django.core.paginator import Paginator
        
        # Orçamentos pendentes = não confirmados (sem pedido criado)
        ids_com_pedido = OrdemServico.objects.filter(
            codigo__startswith='OS',
            orcamento_origem_id__isnull=False
        ).values_list('orcamento_origem_id', flat=True).distinct()
        orcamentos = OrdemServico.objects.filter(
            codigo__startswith='COT',
            status='AGENDADA'
        ).exclude(id__in=ids_com_pedido).order_by('-data_criacao')
        
        paginator = Paginator(orcamentos, 20)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)
        ids_na_pagina = [o.id for o in page_obj]
        pedidos_dos_orcamentos = dict(
            OrdemServico.objects.filter(
                codigo__startswith='OS',
                orcamento_origem_id__in=ids_na_pagina
            ).values_list('orcamento_origem_id', 'id')
        )
        for o in page_obj:
            o.pedido_id = pedidos_dos_orcamentos.get(o.id)
        
        context = {
            'title': 'Orçamentos Pendentes',
            'page_obj': page_obj,
            'orcamentos': page_obj,
        }
        return render(request, 'vendas/orcamento/pendentes.html', context)
    except Exception as e:
        logger.error(f"Erro ao carregar orçamentos pendentes: {e}", exc_info=True)
        messages.error(request, 'Erro ao carregar orçamentos pendentes.')
        return redirect('vendas:main')


@login_required
@require_http_methods(["GET", "POST"])
def vendas_orcamento_delete(request, id):
    """Eliminar orçamento (cotação). Só permite se ainda não tiver sido convertido em pedido."""
    orcamento = get_object_or_404(OrdemServico, id=id)
    if not orcamento.codigo or not orcamento.codigo.startswith('COT'):
        messages.error(request, 'Só é possível eliminar cotações (orçamentos), não ordens de serviço.')
        return redirect('vendas:orcamentos_list')
    if OrdemServico.objects.filter(codigo__startswith='OS', orcamento_origem=orcamento).exists():
        messages.error(request, f'Não pode eliminar a cotação {orcamento.codigo}: já foi convertida em pedido.')
        return redirect('vendas:orcamentos_list')
    if request.method == 'POST':
        try:
            codigo = orcamento.codigo
            orcamento.delete()
            messages.success(request, f'Orçamento {codigo} eliminado com sucesso.')
            return redirect('vendas:orcamentos_list')
        except Exception as e:
            logger.error(f"Erro ao eliminar orçamento {id}: {e}", exc_info=True)
            messages.error(request, f'Erro ao eliminar orçamento: {str(e)}')
            return redirect('vendas:orcamentos_list')
    context = {'orcamento': orcamento}
    return render(request, 'vendas/orcamento/delete.html', context)


@login_required
def vendas_clientes_add(request):
    """Cadastrar novo cliente"""
    if request.method == 'POST':
        try:
            with transaction.atomic():
                nome = request.POST.get('nome', '').strip()
                email = request.POST.get('email', '').strip()
                telefone = request.POST.get('telefone', '').strip()
                nuit = request.POST.get('nuit', '').strip()
                endereco = request.POST.get('endereco', '').strip()
                cidade = request.POST.get('cidade', '').strip()
                observacoes = request.POST.get('observacoes', '').strip()
                
                if not nome:
                    messages.error(request, 'Nome do cliente é obrigatório.')
                    return redirect('vendas:clientes_add')
                
                ClienteServico.objects.create(
                    nome=nome,
                    email=email if email else None,
                    telefone=telefone if telefone else None,
                    nuit=nuit if nuit else None,
                    endereco=endereco if endereco else None,
                    cidade=cidade if cidade else None,
                    observacoes=observacoes if observacoes else None,
                    ativo=True
                )
                
                messages.success(request, f'Cliente "{nome}" criado com sucesso!')
                return redirect('vendas:clientes_list')
        except Exception as e:
            logger.error(f"Erro ao criar cliente: {e}", exc_info=True)
            messages.error(request, f'Erro ao criar cliente: {str(e)}')
    
    return render(request, 'vendas/clientes/add.html', {'title': 'Cadastrar Cliente'})


@login_required
def vendas_clientes_list(request):
    """Lista de clientes"""
    try:
        from django.core.paginator import Paginator
        
        clientes = ClienteServico.objects.filter(ativo=True).order_by('nome')
        
        paginator = Paginator(clientes, 20)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)
        
        context = {
            'title': 'Lista de Clientes',
            'page_obj': page_obj,
            'clientes': page_obj,
        }
        return render(request, 'vendas/clientes/list.html', context)
    except Exception as e:
        logger.error(f"Erro ao carregar lista de clientes: {e}", exc_info=True)
        messages.error(request, 'Erro ao carregar lista de clientes.')
        return redirect('vendas:main')


@login_required
def vendas_historico(request):
    """Histórico de vendas — pedidos com filtro por cliente e período."""
    try:
        from .models_stock import OrdemServico
        from django.core.paginator import Paginator
        from django.db.models import Q
        from datetime import datetime, timedelta

        cliente_id = request.GET.get('cliente', '')
        data_inicio = request.GET.get('data_inicio', '')
        data_fim = request.GET.get('data_fim', '')
        # Por defeito: último ano
        if not data_fim:
            data_fim = timezone.now().date().isoformat()
        if not data_inicio:
            try:
                data_inicio = (timezone.now().date() - timedelta(days=365)).isoformat()
            except Exception:
                data_inicio = ''

        ordens = OrdemServico.objects.select_related(
            'cliente', 'responsavel', 'criado_por'
        ).prefetch_related(
            'servicos_orcamento__servico'
        ).filter(
            codigo__startswith='OS'
        ).distinct()

        if cliente_id:
            ordens = ordens.filter(cliente_id=cliente_id)
        if data_inicio:
            try:
                di = datetime.strptime(data_inicio, '%Y-%m-%d').date()
                ordens = ordens.filter(data_agendada__date__gte=di)
            except ValueError:
                pass
        if data_fim:
            try:
                df = datetime.strptime(data_fim, '%Y-%m-%d').date()
                ordens = ordens.filter(data_agendada__date__lte=df)
            except ValueError:
                pass

        # Ordenar por data de conclusão (ou agendada) mais recente primeiro
        ordens = ordens.order_by('-data_conclusao', '-data_agendada', '-data_criacao')

        paginator = Paginator(ordens, 25)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        total_periodo = sum((o.valor_total or Decimal('0.00')) for o in ordens)
        clientes = ClienteServico.objects.filter(ativo=True).order_by('nome')

        context = {
            'title': 'Histórico de Vendas',
            'page_obj': page_obj,
            'pedidos': page_obj,
            'cliente_id': cliente_id or '',
            'data_inicio': data_inicio or '',
            'data_fim': data_fim or '',
            'total_periodo': total_periodo,
            'clientes': clientes,
        }
        return render(request, 'vendas/historico.html', context)
    except Exception as e:
        logger.error(f'Erro ao carregar histórico de vendas: {e}', exc_info=True)
        messages.error(request, 'Erro ao carregar histórico.')
        return redirect('vendas:main')


@login_required
def vendas_relatorios(request):
    """Relatórios de vendas — totais e resumo por período."""
    try:
        from .models_stock import OrdemServico
        from django.db.models import Sum, Count, Q
        from datetime import datetime, timedelta

        periodo = request.GET.get('periodo', 'mes')  # mes, trimestre, ano, personalizado
        data_inicio = request.GET.get('data_inicio', '')
        data_fim = request.GET.get('data_fim', '')

        hoje = timezone.now().date()
        if periodo == 'mes':
            data_inicio = (hoje.replace(day=1)).isoformat()
            data_fim = hoje.isoformat()
        elif periodo == 'trimestre':
            # Últimos 3 meses
            data_inicio = (hoje - timedelta(days=90)).isoformat()
            data_fim = hoje.isoformat()
        elif periodo == 'ano':
            data_inicio = (hoje.replace(month=1, day=1)).isoformat()
            data_fim = hoje.isoformat()
        elif periodo == 'personalizado' and data_inicio and data_fim:
            try:
                datetime.strptime(data_inicio, '%Y-%m-%d')
                datetime.strptime(data_fim, '%Y-%m-%d')
            except ValueError:
                data_inicio = (hoje.replace(day=1)).isoformat()
                data_fim = hoje.isoformat()
        else:
            data_inicio = (hoje.replace(day=1)).isoformat()
            data_fim = hoje.isoformat()

        try:
            di = datetime.strptime(data_inicio, '%Y-%m-%d').date()
            df = datetime.strptime(data_fim, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            di = hoje.replace(day=1)
            df = hoje

        base = OrdemServico.objects.filter(codigo__startswith='OS')
        no_periodo = base.filter(
            data_agendada__date__gte=di,
            data_agendada__date__lte=df
        )

        total_pedidos = no_periodo.count()
        concluidos = no_periodo.filter(status='CONCLUIDA')
        total_concluidos = concluidos.count()
        com_fatura = concluidos.filter(numero_impressao_fatura__gt=0).count()

        soma_valor = no_periodo.aggregate(s=Sum('valor_total'))['s']
        total_valor = soma_valor if soma_valor is not None else Decimal('0.00')

        # Top 5 clientes por valor no período (agregação por cliente)
        top_clientes = (
            no_periodo.values('cliente__nome', 'cliente_id')
            .annotate(total=Sum('valor_total'), num_pedidos=Count('id'))
            .order_by('-total')[:5]
        )
        outros = no_periodo.filter(cliente__isnull=True)
        outros_valor = sum((o.valor_total or Decimal('0.00')) for o in outros) if outros.exists() else Decimal('0.00')
        outros_count = outros.count()

        context = {
            'title': 'Relatórios de Vendas',
            'periodo': request.GET.get('periodo', 'mes'),
            'data_inicio': data_inicio,
            'data_fim': data_fim,
            'total_pedidos': total_pedidos,
            'total_concluidos': total_concluidos,
            'com_fatura': com_fatura,
            'total_valor': total_valor,
            'top_clientes': list(top_clientes),
            'outros_valor': outros_valor,
            'outros_count': outros_count,
        }
        return render(request, 'vendas/relatorios/list.html', context)
    except Exception as e:
        logger.error(f'Erro ao carregar relatórios de vendas: {e}', exc_info=True)
        messages.error(request, 'Erro ao carregar relatórios.')
        return redirect('vendas:main')


@login_required
def vendas_performance(request):
    """Análise de performance de vendas: conversão orçamento→pedido, status, ticket médio."""
    try:
        from .models_stock import OrdemServico
        from django.db.models import Sum, Count, Q
        from datetime import datetime, timedelta

        hoje = timezone.now().date()
        data_inicio_str = request.GET.get('data_inicio', '')
        data_fim_str = request.GET.get('data_fim', '')
        if data_inicio_str and data_fim_str:
            try:
                di = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
                df = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
                if di > df:
                    di, df = df, di
            except (ValueError, TypeError):
                di = hoje - timedelta(days=365)
                df = hoje
        else:
            di = hoje - timedelta(days=365)
            df = hoje
            data_inicio_str = di.isoformat()
            data_fim_str = df.isoformat()

        # Orçamentos (COT) no período
        orcamentos = OrdemServico.objects.filter(
            codigo__startswith='COT',
            data_agendada__date__gte=di,
            data_agendada__date__lte=df
        )
        total_orcamentos = orcamentos.count()
        # Orçamentos do período que geraram pelo menos um pedido
        orcamentos_convertidos = orcamentos.filter(ordens_servico_geradas__isnull=False).distinct().count()
        # Pedidos no período (incluindo os que vêm de orçamento e os que não)
        pedidos = OrdemServico.objects.filter(
            codigo__startswith='OS',
            data_agendada__date__gte=di,
            data_agendada__date__lte=df
        )
        total_pedidos = pedidos.count()
        taxa_conversao = (orcamentos_convertidos / total_orcamentos * 100) if total_orcamentos else Decimal('0.00')

        # Distribuição por status (pedidos)
        status_choices = [
            ('AGENDADA', 'Agendada'),
            ('EM_ANDAMENTO', 'Em Andamento'),
            ('PAUSADA', 'Pausada'),
            ('CONCLUIDA', 'Concluída'),
            ('CANCELADA', 'Cancelada'),
        ]
        por_status = []
        for cod, label in status_choices:
            c = pedidos.filter(status=cod).count()
            por_status.append({'cod': cod, 'label': label, 'count': c})

        # Valor total e ticket médio
        agg = pedidos.aggregate(soma=Sum('valor_total'))
        total_valor = agg['soma'] if agg['soma'] is not None else Decimal('0.00')
        ticket_medio = (total_valor / total_pedidos) if total_pedidos else Decimal('0.00')

        # Concluídos: com fatura vs sem fatura
        concluidos = pedidos.filter(status='CONCLUIDA')
        concluidos_com_fatura = concluidos.filter(numero_impressao_fatura__gt=0).count()
        concluidos_sem_fatura = concluidos.count() - concluidos_com_fatura

        context = {
            'title': 'Análise de Performance',
            'data_inicio': data_inicio_str,
            'data_fim': data_fim_str,
            'total_orcamentos': total_orcamentos,
            'total_pedidos': total_pedidos,
            'orcamentos_convertidos': orcamentos_convertidos,
            'taxa_conversao': taxa_conversao,
            'por_status': por_status,
            'total_valor': total_valor,
            'ticket_medio': ticket_medio,
            'concluidos_com_fatura': concluidos_com_fatura,
            'concluidos_sem_fatura': concluidos_sem_fatura,
        }
        return render(request, 'vendas/performance.html', context)
    except Exception as e:
        logger.error(f'Erro ao carregar análise de performance: {e}', exc_info=True)
        messages.error(request, 'Erro ao carregar análise de performance.')
        return redirect('vendas:main')


@login_required
def vendas_periodo(request):
    """Vendas por período — análise por mês (ano seleccionado)."""
    try:
        from .models_stock import OrdemServico
        from django.db.models import Sum, Count, Q
        from django.db.models.functions import TruncMonth

        MESES_PT = ('', 'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
                    'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro')

        ano = request.GET.get('ano', '')
        if not ano:
            ano = str(timezone.now().year)

        try:
            ano_int = int(ano)
            if ano_int < 2000 or ano_int > 2100:
                ano_int = timezone.now().year
                ano = str(ano_int)
        except (ValueError, TypeError):
            ano_int = timezone.now().year
            ano = str(ano_int)

        base = OrdemServico.objects.filter(
            codigo__startswith='OS',
            data_agendada__year=ano_int
        )
        por_mes = (
            base.annotate(mes=TruncMonth('data_agendada'))
            .values('mes')
            .annotate(
                total_pedidos=Count('id'),
                total_valor=Sum('valor_total'),
            )
            .order_by('-mes')
        )
        concluidos_por_mes = (
            base.annotate(mes=TruncMonth('data_agendada'))
            .values('mes')
            .annotate(concluidos=Count('id', filter=Q(status='CONCLUIDA')))
            .order_by('-mes')
        )
        concluidos_map = {r['mes']: r['concluidos'] for r in concluidos_por_mes}

        meses_lista = []
        for r in por_mes:
            mes_dt = r['mes']
            if mes_dt:
                nome_mes = MESES_PT[mes_dt.month] if 1 <= mes_dt.month <= 12 else mes_dt.strftime('%Y-%m')
                meses_lista.append({
                    'mes': mes_dt,
                    'nome_mes': nome_mes,
                    'total_pedidos': r['total_pedidos'],
                    'total_valor': r['total_valor'] or Decimal('0.00'),
                    'concluidos': concluidos_map.get(mes_dt, 0),
                })

        total_ano_pedidos = sum(m['total_pedidos'] for m in meses_lista)
        total_ano_valor = sum(m['total_valor'] for m in meses_lista)
        anos_disponiveis = list(range(timezone.now().year, 2019, -1))

        context = {
            'title': 'Vendas por Período',
            'ano': ano,
            'anos_disponiveis': anos_disponiveis,
            'meses_lista': meses_lista,
            'total_ano_pedidos': total_ano_pedidos,
            'total_ano_valor': total_ano_valor,
        }
        return render(request, 'vendas/periodo.html', context)
    except Exception as e:
        logger.error(f'Erro ao carregar vendas por período: {e}', exc_info=True)
        messages.error(request, 'Erro ao carregar análise por período.')
        return redirect('vendas:main')


@login_required
@require_http_methods(["GET", "POST"])
def vendas_orcamento_add(request):
    """Criar novo orçamento de venda"""
    if request.method == 'POST':
        try:
            with transaction.atomic():
                cliente_id = request.POST.get('cliente')
                data_entrega_str = request.POST.get('data_entrega', '')
                endereco_entrega = request.POST.get('endereco_entrega', '')
                cidade_entrega = request.POST.get('cidade_entrega', '')
                observacoes = request.POST.get('observacoes', '')
                forma_pagamento = request.POST.get('forma_pagamento', 'PRONTO_PAGAMENTO')
                nome_cliente_pagamento = request.POST.get('nome_cliente_pagamento', '').strip()
                nuit_cliente_pagamento = request.POST.get('nuit_cliente_pagamento', '').strip()
                telefone_cliente_pagamento = request.POST.get('telefone_cliente_pagamento', '').strip()
                desconto_global = Decimal(request.POST.get('desconto', '0.00') or '0.00')
                
                # Validar método de pagamento
                if forma_pagamento == 'PRONTO_PAGAMENTO':
                    if not nome_cliente_pagamento:
                        messages.error(request, 'Nome do cliente é obrigatório para pronto pagamento.')
                        return redirect('vendas:orcamento_add')
                    cliente = None
                else:
                    if not cliente_id:
                        messages.error(request, 'Cliente é obrigatório para venda a crédito.')
                        return redirect('vendas:orcamento_add')
                    cliente = get_object_or_404(ClienteServico, id=cliente_id)
                
                # Processar data de entrega
                if data_entrega_str:
                    try:
                        data_entrega = datetime.strptime(data_entrega_str, "%Y-%m-%d").date()
                    except:
                        data_entrega = None
                else:
                    data_entrega = None
                
                # Processar endereço de entrega
                if forma_pagamento == 'PRONTO_PAGAMENTO':
                    sucursal_padrao = Sucursal.objects.filter(tipo='SEDE').first()
                    if not sucursal_padrao:
                        sucursal_padrao = Sucursal.objects.first()
                    endereco_final = endereco_entrega or (sucursal_padrao.endereco if sucursal_padrao and sucursal_padrao.endereco else 'Localização da sucursal')
                    cidade_final = cidade_entrega or ''
                else:
                    if cliente:
                        endereco_final = endereco_entrega or cliente.endereco or 'A definir'
                        cidade_final = cidade_entrega or cliente.cidade or ''
                    else:
                        endereco_final = endereco_entrega or 'A definir'
                        cidade_final = cidade_entrega or ''
                
                # Por enquanto, vamos usar OrdemServico como base (pode ser adaptado depois)
                # TODO: Criar modelo OrcamentoVenda específico
                from .models_stock import OrdemServico
                
                ordem = OrdemServico(
                    servico=None,
                    cliente=cliente if cliente else None,
                    data_agendada=timezone.now(),
                    endereco_servico=endereco_final,
                    cidade_servico=cidade_final,
                    equipe='',
                    prioridade='NORMAL',
                    quantidade=Decimal('1.00'),
                    valor_unitario=None,
                    desconto=desconto_global,
                    observacoes=observacoes,
                    problema_relatado='',
                    criado_por=request.user,
                    status='AGENDADA',
                    forma_pagamento=forma_pagamento,
                    nome_cliente_pagamento=nome_cliente_pagamento if forma_pagamento == 'PRONTO_PAGAMENTO' else None,
                    nuit_cliente_pagamento=nuit_cliente_pagamento if forma_pagamento == 'PRONTO_PAGAMENTO' else None,
                    telefone_cliente_pagamento=telefone_cliente_pagamento if forma_pagamento == 'PRONTO_PAGAMENTO' else None,
                    validade_garantia_dias=90,
                )
                ordem.save(is_orcamento=True)
                
                # Processar produtos
                from .models_stock import ServicoOrcamentoServico
                produto_ids = request.POST.getlist('produto_id[]')
                produto_quantidades = request.POST.getlist('produto_quantidade[]')
                produto_valores_unitarios = request.POST.getlist('produto_valor_unitario[]')
                produto_descontos_percentuais = request.POST.getlist('produto_desconto_percentual[]')
                produto_descontos = request.POST.getlist('produto_desconto[]')
                
                if not produto_ids or not any(produto_ids):
                    messages.error(request, 'Pelo menos um produto é obrigatório.')
                    ordem.delete()
                    return redirect('vendas:orcamento_add')
                
                for i, produto_id in enumerate(produto_ids):
                    if produto_id and produto_id.strip():
                        try:
                            produto_item = Item.objects.get(id=produto_id, tipo='PRODUTO', produto_tipo__in=['PRODUTO', 'ACABADO'])
                            quantidade_produto = Decimal(produto_quantidades[i] if i < len(produto_quantidades) else '1.00')
                            valor_unitario_produto_str = produto_valores_unitarios[i] if i < len(produto_valores_unitarios) else '0.00'
                            valor_unitario_produto = Decimal(valor_unitario_produto_str) if valor_unitario_produto_str else Decimal('0.00')
                            
                            if not valor_unitario_produto or valor_unitario_produto == 0:
                                valor_unitario_produto = produto_item.preco_venda if produto_item.preco_venda else Decimal('0.00')
                            
                            desconto_percentual_produto_str = produto_descontos_percentuais[i] if i < len(produto_descontos_percentuais) else '0.00'
                            desconto_percentual_produto = Decimal(desconto_percentual_produto_str) if desconto_percentual_produto_str else Decimal('0.00')
                            
                            desconto_produto_str = produto_descontos[i] if i < len(produto_descontos) else '0.00'
                            desconto_produto = Decimal(desconto_produto_str) if desconto_produto_str else Decimal('0.00')
                            
                            # Usar ServicoOrcamentoServico temporariamente (pode ser adaptado depois)
                            ServicoOrcamentoServico.objects.create(
                                ordem_servico=ordem,
                                servico=produto_item,  # Usando campo servico para produtos temporariamente
                                quantidade=quantidade_produto,
                                valor_unitario=valor_unitario_produto,
                                desconto_percentual=desconto_percentual_produto,
                                desconto=desconto_produto,
                            )
                        except (Item.DoesNotExist, ValueError, IndexError) as e:
                            logger.warning(f"Erro ao adicionar produto ao orçamento: {e}")
                            continue
                
                messages.success(request, f'Orçamento {ordem.codigo} criado com sucesso!')
                return redirect('vendas:orcamento_detail', id=ordem.id)
        except Exception as e:
            logger.error(f"Erro ao criar orçamento: {e}", exc_info=True)
            messages.error(request, f'Erro ao criar orçamento: {str(e)}')
    
    # GET - Exibir formulário
    try:
        clientes = ClienteServico.objects.filter(ativo=True).order_by('nome')
        produtos = Item.objects.filter(
            tipo='PRODUTO',
            produto_tipo__in=['PRODUTO', 'ACABADO'],
            status='ATIVO'
        ).order_by('nome')
        
        context = {
            'clientes': clientes,
            'produtos': produtos,
        }
        return render(request, 'vendas/orcamento/form.html', context)
    except Exception as e:
        logger.error(f"Erro ao carregar formulário de orçamento: {e}", exc_info=True)
        messages.error(request, 'Erro ao carregar formulário de orçamento.')
        return redirect('vendas:main')
