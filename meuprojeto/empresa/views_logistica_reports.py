"""
Relatórios logísticos adicionais e relatório geral stock+logística.
"""
from datetime import datetime, timedelta
from decimal import Decimal
import logging

from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, F, Q, Sum
from django.shortcuts import render
from django.utils import timezone

from .decorators import get_user_sucursais, require_stock_access
from .models_cost_billing import CustoLogistico
from .models_stock import (
    Item,
    ItemOrdemCompra,
    MovimentoItem,
    OrdemCompra,
    RastreamentoEntrega,
    StockItem,
    Transportadora,
)
from .views_reports import _contexto_relatorio, _periodo_relatorio

logger = logging.getLogger(__name__)


def _gerar_dados_relatorio_custos(data_inicio, data_fim):
    data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
    data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
    qs = CustoLogistico.objects.filter(data_custo__range=[data_inicio, data_fim])

    custos_tipo = list(
        qs.values('tipo_custo__nome')
        .annotate(total=Sum('valor'), count=Count('id'))
        .order_by('-total')
    )
    custos_transportadora = list(
        qs.filter(rastreamento_entrega__transportadora__isnull=False)
        .values('rastreamento_entrega__transportadora__nome')
        .annotate(total=Sum('valor'), count=Count('id'))
        .order_by('-total')
    )

    evolucao_custos = []
    dias = min(30, (data_fim - data_inicio).days + 1)
    for i in range(dias):
        data = data_fim - timedelta(days=i)
        if data < data_inicio:
            break
        total_dia = qs.filter(data_custo=data).aggregate(total=Sum('valor'))['total'] or Decimal('0')
        evolucao_custos.append({'data': data.strftime('%d/%m'), 'total': float(total_dia)})
    evolucao_custos.reverse()

    return {
        'custos_tipo': custos_tipo,
        'custos_transportadora': custos_transportadora,
        'evolucao_custos': evolucao_custos,
    }


def _totais_custos(dados):
    total_tipo = sum((item['total'] or 0) for item in dados['custos_tipo'])
    total_transp = sum((item['total'] or 0) for item in dados['custos_transportadora'])
    return total_tipo, total_transp, total_tipo + total_transp


def _gerar_dados_relatorio_sla(data_inicio, data_fim):
    data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
    data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()

    entregas_com_prazo = RastreamentoEntrega.objects.filter(
        data_criacao__date__range=[data_inicio, data_fim],
        data_entrega_prevista__isnull=False,
        status_atual='ENTREGUE',
    )
    total_com_prazo = entregas_com_prazo.count()
    entregas_no_prazo = entregas_com_prazo.filter(
        data_entrega_realizada__lte=F('data_entrega_prevista'),
    ).count()
    sla_percentual = (entregas_no_prazo / total_com_prazo * 100) if total_com_prazo > 0 else 0

    sla_transportadoras = []
    for transportadora in Transportadora.objects.filter(ativa=True):
        entregas = RastreamentoEntrega.objects.filter(
            transportadora=transportadora,
            data_criacao__date__range=[data_inicio, data_fim],
            data_entrega_prevista__isnull=False,
            status_atual='ENTREGUE',
        )
        total = entregas.count()
        no_prazo = entregas.filter(data_entrega_realizada__lte=F('data_entrega_prevista')).count()
        em_atraso = total - no_prazo
        sla = (no_prazo / total * 100) if total > 0 else 0
        sla_transportadoras.append({
            'transportadora': transportadora.nome,
            'total': total,
            'no_prazo': no_prazo,
            'em_atraso': em_atraso,
            'sla': round(sla, 2),
        })

    return {
        'sla_percentual': round(sla_percentual, 2),
        'total_com_prazo': total_com_prazo,
        'entregas_no_prazo': entregas_no_prazo,
        'sla_transportadoras': sla_transportadoras,
    }


# =============================================================================
# DADOS — RASTREAMENTOS
# =============================================================================

_RASTREAMENTO_STATUS_EM_CURSO = (
    'PREPARANDO', 'COLETADO', 'EM_TRANSITO', 'EM_DISTRIBUICAO',
)
_RASTREAMENTO_STATUS_PROBLEMA = ('DEVOLVIDO', 'PERDIDO', 'CANCELADO')


def _queryset_rastreamentos_periodo(data_inicio, data_fim):
    return RastreamentoEntrega.objects.filter(
        data_criacao__date__range=[data_inicio, data_fim],
    )


def _metricas_rastreamentos(qs):
    total = qs.count()
    concluidas = qs.filter(status_atual='ENTREGUE').count()
    em_curso = qs.filter(status_atual__in=_RASTREAMENTO_STATUS_EM_CURSO).count()
    com_problema = qs.filter(status_atual__in=_RASTREAMENTO_STATUS_PROBLEMA).count()

    entregas_com_prazo = qs.filter(
        data_entrega_prevista__isnull=False,
        status_atual='ENTREGUE',
    )
    total_com_prazo = entregas_com_prazo.count()
    entregas_no_prazo = entregas_com_prazo.filter(
        data_entrega_realizada__lte=F('data_entrega_prevista'),
    ).count()
    entregas_atrasadas = total_com_prazo - entregas_no_prazo
    sla_percentual = (entregas_no_prazo / total_com_prazo * 100) if total_com_prazo > 0 else 0
    taxa_conclusao = (concluidas / total * 100) if total > 0 else 0

    return {
        'total_rastreamentos': total,
        'entregas_concluidas': concluidas,
        'em_curso': em_curso,
        'com_problema': com_problema,
        'total_com_prazo': total_com_prazo,
        'entregas_no_prazo': entregas_no_prazo,
        'entregas_atrasadas': entregas_atrasadas,
        'sla_percentual': round(sla_percentual, 1),
        'taxa_conclusao': round(taxa_conclusao, 1),
    }


def _agregados_rastreamentos(qs):
    status_labels = dict(RastreamentoEntrega.STATUS_CHOICES)
    por_status = [
        {
            'status_atual': row['status_atual'],
            'label': status_labels.get(row['status_atual'], row['status_atual']),
            'count': row['count'],
        }
        for row in qs.values('status_atual').annotate(count=Count('id')).order_by('-count')
    ]
    por_transportadora = list(
        qs.filter(transportadora__isnull=False)
        .values('transportadora__nome')
        .annotate(
            total=Count('id'),
            entregues=Count('id', filter=Q(status_atual='ENTREGUE')),
        )
        .order_by('-total')[:15]
    )
    por_cidade = list(
        qs.exclude(cidade_entrega='')
        .values('cidade_entrega')
        .annotate(total=Count('id'))
        .order_by('-total')[:10]
    )
    recentes = list(
        qs.select_related('transportadora', 'veiculo_interno')
        .order_by('-data_criacao')[:15]
    )
    return {
        'por_status': por_status,
        'por_transportadora': por_transportadora,
        'por_cidade': por_cidade,
        'recentes': recentes,
        'status_labels': status_labels,
    }


def _gerar_dados_relatorio_rastreamentos(data_inicio, data_fim):
    """Gera dados para relatório de rastreamentos e entregas."""
    data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
    data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
    qs = _queryset_rastreamentos_periodo(data_inicio, data_fim)
    return {
        **_metricas_rastreamentos(qs),
        **_agregados_rastreamentos(qs),
    }


def _gerar_dados_relatorio_transportadoras(data_inicio, data_fim):
    data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
    data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()

    todas = Transportadora.objects.all()
    detalhes = []
    taxas = []
    total_entregas = 0

    for transportadora in todas.order_by('nome'):
        entregas = RastreamentoEntrega.objects.filter(
            transportadora=transportadora,
            data_criacao__date__range=[data_inicio, data_fim],
        )
        total = entregas.count()
        entregues = entregas.filter(status_atual='ENTREGUE').count()
        taxa = (entregues / total * 100) if total > 0 else 0
        total_entregas += total
        taxas.append(taxa)
        detalhes.append({
            'transportadora': transportadora,
            'total_entregas': total,
            'entregues': entregues,
            'taxa_sucesso': round(taxa, 2),
            'prazo_entrega_padrao': transportadora.prazo_entrega_padrao,
            'status': 'Ativa' if transportadora.ativa and transportadora.status == 'ATIVA' else transportadora.get_status_display(),
        })

    por_tipo = list(
        todas.values('tipo').annotate(count=Count('id')).order_by('-count')
    )
    taxa_media = sum(taxas) / len(taxas) if taxas else 0

    return {
        'total_transportadoras': todas.count(),
        'transportadoras_ativas': todas.filter(ativa=True).count(),
        'transportadoras': detalhes,
        'por_tipo': por_tipo,
        'total_entregas_periodo': total_entregas,
        'taxa_media_sucesso': round(taxa_media, 2),
    }


def _gerar_dados_relatorio_excecoes(data_inicio, data_fim):
    data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
    data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
    try:
        from .models_exceptions import ExcecaoLogistica

        qs = ExcecaoLogistica.objects.filter(
            data_ocorrencia__date__range=[data_inicio, data_fim],
        )
        total = qs.count()
        resolvidas = qs.filter(status='RESOLVIDA').count()
        pendentes = qs.exclude(status__in=['RESOLVIDA', 'CANCELADA']).count()
        por_tipo = list(
            qs.values('tipo_excecao__nome').annotate(count=Count('id')).order_by('-count')
        )
        por_prioridade = list(
            qs.values('prioridade').annotate(count=Count('id')).order_by('-count')
        )
        por_transportadora = list(
            qs.filter(rastreamento_entrega__transportadora__isnull=False)
            .values('rastreamento_entrega__transportadora__nome')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )
        return {
            'total_excecoes': total,
            'resolvidas': resolvidas,
            'pendentes': pendentes,
            'por_tipo': por_tipo,
            'por_prioridade': por_prioridade,
            'por_transportadora': por_transportadora,
        }
    except Exception as exc:
        logger.warning('Relatório de exceções indisponível: %s', exc)
        return {'mensagem': 'Módulo de exceções logísticas indisponível neste ambiente.'}


def _contexto_relatorio_geral(request, data_inicio, data_fim, sucursal_id=None):
    sucursais_permitidas = list(get_user_sucursais(request))
    sucursal_selecionada = int(sucursal_id) if sucursal_id else None

    stock_qs = StockItem.objects.select_related('item', 'sucursal')
    mov_qs = MovimentoItem.objects.filter(
        data_movimento__date__range=[data_inicio, data_fim],
    )
    rast_qs = RastreamentoEntrega.objects.filter(
        data_criacao__date__range=[data_inicio, data_fim],
    )
    ordens_qs = OrdemCompra.objects.filter(
        data_criacao__date__range=[data_inicio, data_fim],
    )
    custos_qs = CustoLogistico.objects.filter(
        data_custo__range=[data_inicio, data_fim],
    )

    if sucursal_selecionada:
        stock_qs = stock_qs.filter(sucursal_id=sucursal_selecionada)
        mov_qs = mov_qs.filter(sucursal_id=sucursal_selecionada)
        ordens_qs = ordens_qs.filter(sucursal_destino_id=sucursal_selecionada)

    total_produtos = Item.objects.filter(status='ATIVO', tipo='PRODUTO').count()
    total_materiais = Item.objects.filter(status='ATIVO', tipo='MATERIAL').count()
    total_itens = total_produtos + total_materiais

    valor_total_estoque = stock_qs.aggregate(
        total=Sum(F('quantidade_atual') * F('item__preco_custo')),
    )['total'] or Decimal('0')

    itens_estoque_baixo = stock_qs.filter(
        quantidade_atual__lte=F('item__estoque_minimo'),
    ).count()

    total_movimentos = mov_qs.count()
    entradas_qs = mov_qs.filter(tipo_movimento__aumenta_estoque=True)
    saidas_qs = mov_qs.filter(tipo_movimento__aumenta_estoque=False)
    total_entradas = entradas_qs.count()
    total_saidas = saidas_qs.count()
    valor_entradas = entradas_qs.aggregate(t=Sum('valor_total'))['t'] or Decimal('0')
    valor_saidas = saidas_qs.aggregate(t=Sum('valor_total'))['t'] or Decimal('0')

    estoque_por_sucursal = list(
        stock_qs.values('sucursal__nome')
        .annotate(
            total_itens=Count('id'),
            valor_total=Sum(F('quantidade_atual') * F('item__preco_custo')),
        )
        .order_by('sucursal__nome')
    )

    itens_estoque_baixo_detalhado = []
    for stock_item in stock_qs.filter(
        quantidade_atual__lte=F('item__estoque_minimo'),
    ).select_related('item', 'sucursal')[:20]:
        minimo = stock_item.item.estoque_minimo or 0
        atual = stock_item.quantidade_atual or 0
        itens_estoque_baixo_detalhado.append({
            'nome': stock_item.item.nome,
            'codigo': stock_item.item.codigo,
            'sucursal': stock_item.sucursal.nome if stock_item.sucursal else '—',
            'quantidade_atual': atual,
            'estoque_minimo': minimo,
            'deficit': max(minimo - atual, 0),
        })

    itens_mais_movimentados = list(
        mov_qs.values('item__nome', 'item__codigo')
        .annotate(
            total_movimentos=Count('id'),
            quantidade_total=Sum('quantidade'),
            valor_total=Sum('valor_total'),
        )
        .order_by('-total_movimentos')[:15]
    )

    movimentacoes_por_tipo = list(
        mov_qs.values('tipo_movimento__nome')
        .annotate(count=Count('id'), valor_total=Sum('valor_total'))
        .order_by('-count')
    )

    estoque_produtos = list(
        stock_qs.filter(item__tipo='PRODUTO')
        .values('sucursal__nome')
        .annotate(
            total=Count('id'),
            valor=Sum(F('quantidade_atual') * F('item__preco_custo')),
        )
        .order_by('-valor')[:10]
    )
    estoque_materiais = list(
        stock_qs.filter(item__tipo='MATERIAL')
        .values('sucursal__nome')
        .annotate(
            total=Count('id'),
            valor=Sum(F('quantidade_atual') * F('item__preco_custo')),
        )
        .order_by('-valor')[:10]
    )

    total_rastreamentos = rast_qs.count()
    rastreamentos_por_status = list(
        rast_qs.values('status_atual').annotate(count=Count('id')).order_by('-count')
    )
    rastreamentos_por_transportadora = list(
        rast_qs.filter(transportadora__isnull=False)
        .values('transportadora__nome')
        .annotate(
            total=Count('id'),
            entregues=Count('id', filter=Q(status_atual='ENTREGUE')),
        )
        .order_by('-total')[:15]
    )

    entregas_com_prazo = rast_qs.filter(
        data_entrega_prevista__isnull=False,
        status_atual='ENTREGUE',
    )
    total_com_prazo = entregas_com_prazo.count()
    entregas_no_prazo = entregas_com_prazo.filter(
        data_entrega_realizada__lte=F('data_entrega_prevista'),
    ).count()
    entregas_atrasadas = total_com_prazo - entregas_no_prazo
    sla_percentual = (entregas_no_prazo / total_com_prazo * 100) if total_com_prazo > 0 else 0

    tempo_medio = entregas_com_prazo.filter(
        data_entrega_realizada__isnull=False,
    ).aggregate(
        media=Avg(F('data_entrega_realizada') - F('data_criacao')),
    )['media']
    tempo_medio_entrega = (
        tempo_medio.total_seconds() / 86400 if tempo_medio else None
    )

    transportadoras_performance = []
    for transportadora in Transportadora.objects.filter(ativa=True):
        entregas = rast_qs.filter(transportadora=transportadora)
        total = entregas.count()
        entregues = entregas.filter(status_atual='ENTREGUE').count()
        atrasados = entregas.filter(
            status_atual='ENTREGUE',
            data_entrega_realizada__gt=F('data_entrega_prevista'),
        ).count()
        taxa_sucesso = (entregues / total * 100) if total > 0 else 0
        taxa_atraso = (atrasados / entregues * 100) if entregues > 0 else 0
        transportadoras_performance.append({
            'transportadora__nome': transportadora.nome,
            'total': total,
            'entregues': entregues,
            'atrasados': atrasados,
            'taxa_sucesso': round(taxa_sucesso, 1),
            'taxa_atraso': round(taxa_atraso, 1),
        })

    rastreamentos_recentes = list(
        rast_qs.select_related('transportadora').order_by('-data_criacao')[:20]
    )
    rastreamentos_por_cidade = list(
        rast_qs.exclude(cidade_entrega='')
        .values('cidade_entrega')
        .annotate(total=Count('id'))
        .order_by('-total')[:15]
    )

    total_ordens = ordens_qs.count()
    valor_total_ordens = ItemOrdemCompra.objects.filter(
        ordem_compra__in=ordens_qs,
    ).aggregate(
        t=Sum(F('quantidade_solicitada') * F('preco_unitario')),
    )['t'] or Decimal('0')

    ordens_por_status = list(
        ordens_qs.values('status').annotate(count=Count('id')).order_by('-count')
    )
    ordens_por_fornecedor = list(
        ordens_qs.filter(fornecedor__isnull=False)
        .values('fornecedor__nome')
        .annotate(total=Count('id'), valor_total=Sum(F('itens__quantidade_solicitada') * F('itens__preco_unitario')))
        .order_by('-total')[:15]
    )
    itens_mais_comprados = list(
        ItemOrdemCompra.objects.filter(ordem_compra__in=ordens_qs)
        .values('produto__nome', 'produto__codigo')
        .annotate(
            total_quantidade=Sum('quantidade_solicitada'),
            total_ordens=Count('ordem_compra', distinct=True),
            valor_total=Sum(F('quantidade_solicitada') * F('preco_unitario')),
        )
        .order_by('-total_quantidade')[:15]
    )
    ordens_pendentes = list(
        ordens_qs.exclude(status__in=['RECEBIDA', 'CANCELADA'])
        .select_related('fornecedor', 'sucursal_destino')[:20]
    )
    ordens_por_sucursal_destino = list(
        ordens_qs.values('sucursal_destino__nome')
        .annotate(total=Count('id'))
        .order_by('-total')
    )

    total_custos = custos_qs.aggregate(t=Sum('valor'))['t'] or Decimal('0')
    custos_por_tipo = list(
        custos_qs.values('tipo_custo__nome')
        .annotate(quantidade=Count('id'), total=Sum('valor'))
        .order_by('-total')
    )
    custos_por_transportadora = list(
        custos_qs.filter(rastreamento_entrega__transportadora__isnull=False)
        .values('rastreamento_entrega__transportadora__nome')
        .annotate(quantidade=Count('id'), total=Sum('valor'))
        .order_by('-total')[:15]
    )

    sucursal_nome = None
    if sucursal_selecionada:
        for sucursal in sucursais_permitidas:
            if sucursal.id == sucursal_selecionada:
                sucursal_nome = sucursal.nome
                break

    estoque_por_sucursal_total_itens = sum(
        row.get('total_itens') or 0 for row in estoque_por_sucursal
    )

    return {
        'sucursais_permitidas': sucursais_permitidas,
        'sucursal_selecionada': sucursal_selecionada,
        'sucursal_nome': sucursal_nome,
        'estoque_por_sucursal_total_itens': estoque_por_sucursal_total_itens,
        'total_itens': total_itens,
        'total_produtos': total_produtos,
        'total_materiais': total_materiais,
        'valor_total_estoque': valor_total_estoque,
        'itens_estoque_baixo': itens_estoque_baixo,
        'total_movimentos': total_movimentos,
        'total_entradas': total_entradas,
        'total_saidas': total_saidas,
        'valor_entradas': valor_entradas,
        'valor_saidas': valor_saidas,
        'estoque_por_sucursal': estoque_por_sucursal,
        'itens_estoque_baixo_detalhado': itens_estoque_baixo_detalhado,
        'itens_mais_movimentados': itens_mais_movimentados,
        'movimentacoes_por_tipo': movimentacoes_por_tipo,
        'estoque_produtos': estoque_produtos,
        'estoque_materiais': estoque_materiais,
        'total_rastreamentos': total_rastreamentos,
        'sla_percentual': round(sla_percentual, 2),
        'entregas_no_prazo': entregas_no_prazo,
        'entregas_atrasadas': entregas_atrasadas,
        'transportadoras_ativas': Transportadora.objects.filter(ativa=True).count(),
        'tempo_medio_entrega': tempo_medio_entrega,
        'rastreamentos_por_status': rastreamentos_por_status,
        'rastreamentos_por_transportadora': rastreamentos_por_transportadora,
        'transportadoras_performance': transportadoras_performance,
        'rastreamentos_recentes': rastreamentos_recentes,
        'rastreamentos_por_cidade': rastreamentos_por_cidade,
        'total_ordens': total_ordens,
        'valor_total_ordens': valor_total_ordens,
        'ordens_por_status': ordens_por_status,
        'ordens_por_fornecedor': ordens_por_fornecedor,
        'itens_mais_comprados': itens_mais_comprados,
        'ordens_pendentes': ordens_pendentes,
        'ordens_por_sucursal_destino': ordens_por_sucursal_destino,
        'total_custos': total_custos,
        'custos_por_tipo': custos_por_tipo,
        'custos_por_transportadora': custos_por_transportadora,
    }


@login_required
@require_stock_access
def relatorio_transportadoras(request):
    data_inicio_str, data_fim_str, data_inicio, data_fim = _periodo_relatorio(request)
    dados = _gerar_dados_relatorio_transportadoras(data_inicio_str, data_fim_str)
    ctx = _contexto_relatorio(request, data_inicio_str, data_fim_str, {
        'dados': dados,
        'total_entregas': dados.get('total_entregas_periodo', 0),
        'taxa_media_sucesso': dados.get('taxa_media_sucesso', 0),
    })
    return render(request, 'stock/logistica/reports/relatorio_transportadoras.html', ctx)


@login_required
@require_stock_access
def relatorio_excecoes(request):
    data_inicio_str, data_fim_str, _, _ = _periodo_relatorio(request)
    dados = _gerar_dados_relatorio_excecoes(data_inicio_str, data_fim_str)
    total = dados.get('total_excecoes', 0) or 0
    resolvidas = dados.get('resolvidas', 0) or 0
    taxa_resolucao = (resolvidas / total * 100) if total > 0 else 0
    ctx = _contexto_relatorio(request, data_inicio_str, data_fim_str, {
        'dados': dados,
        'taxa_resolucao': round(taxa_resolucao, 2),
    })
    return render(request, 'stock/logistica/reports/relatorio_excecoes.html', ctx)


@login_required
@require_stock_access
def relatorio_geral_stock_logistica(request):
    data_inicio_str, data_fim_str, data_inicio, data_fim = _periodo_relatorio(request)
    sucursal_id = request.GET.get('sucursal') or None
    geral = _contexto_relatorio_geral(request, data_inicio, data_fim, sucursal_id)
    ctx = _contexto_relatorio(request, data_inicio_str, data_fim_str, geral)
    return render(request, 'stock/relatorios/geral_stock_logistica_documento.html', ctx)


# Funções reutilizadas pelas views em views_reports (custos/SLA corrigidos)
def enrich_custos_context(dados):
    total_tipo, total_transp, total_geral = _totais_custos(dados)
    return {
        'total_custos_tipo': total_tipo,
        'total_custos_transportadora': total_transp,
        'total_geral': total_geral,
    }


def enrich_sla_context(dados):
    total_com_prazo = dados.get('total_com_prazo', 0) or 0
    no_prazo = dados.get('entregas_no_prazo', 0) or 0
    return {'entregas_em_atraso': max(total_com_prazo - no_prazo, 0)}


def enrich_rastreamentos_context(dados):
    return {
        'entregas_em_atraso': dados.get('entregas_atrasadas', 0) or 0,
    }


def serializar_dados_rastreamentos_json(dados):
    """Converte instâncias de modelo em estruturas JSON-serializáveis."""
    out = {k: v for k, v in dados.items() if k != 'recentes'}
    out['recentes'] = [
        {
            'codigo_rastreamento': r.codigo_rastreamento,
            'destinatario_nome': r.destinatario_nome,
            'transporte': (
                r.transportadora.nome if r.transportadora
                else (r.veiculo_interno.nome if r.veiculo_interno else None)
            ),
            'cidade_entrega': r.cidade_entrega,
            'status_atual': r.status_atual,
            'status_label': r.get_status_atual_display(),
            'data_criacao': r.data_criacao.isoformat() if r.data_criacao else None,
        }
        for r in dados.get('recentes', [])
    ]
    return out
