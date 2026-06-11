"""
Lógica partilhada para emissão de fatura de ordem de serviço (usado por Vendas e Produção).
"""
import logging
from decimal import Decimal, InvalidOperation
from datetime import datetime
from django.db import transaction
from django.db.models import Q
from django.conf import settings

logger = logging.getLogger(__name__)


def _custo_total_ordem_servico(ordem):
    """
    Calcula o custo total da ordem com base nos itens (produtos/materiais) com preço de custo.
    Percorre servicos_orcamento.itens e itens_orcamento_legado; cada item: quantidade * item.preco_custo.
    Retorna Decimal >= 0.
    """
    total = Decimal('0.00')
    try:
        for servico in ordem.servicos_orcamento.all():
            for item_orc in servico.itens.all():
                prod = getattr(item_orc, 'item', None)
                if not prod:
                    continue
                qtd = Decimal(str(item_orc.quantidade)) if item_orc.quantidade is not None else Decimal('0.00')
                custo_unit = getattr(prod, 'preco_custo', None)
                custo_unit = Decimal(str(custo_unit)) if custo_unit is not None else Decimal('0.00')
                total += qtd * custo_unit
        for item_orc in ordem.itens_orcamento_legado.all():
            prod = getattr(item_orc, 'item', None)
            if not prod:
                continue
            qtd = Decimal(str(item_orc.quantidade)) if item_orc.quantidade is not None else Decimal('0.00')
            custo_unit = getattr(prod, 'preco_custo', None)
            custo_unit = Decimal(str(custo_unit)) if custo_unit is not None else Decimal('0.00')
            total += qtd * custo_unit
    except (ValueError, TypeError, AttributeError, InvalidOperation):
        pass
    return max(total, Decimal('0.00'))


def build_fatura_context(request, ordem):
    """
    Constrói o contexto para o template da fatura e incrementa numero_impressao_fatura.
    Ordem deve estar concluída (status='CONCLUIDA'). Levanta ValueError se não estiver.
    Retorna dict para render('servicos/ordens/fatura.html', context).
    """
    from .models_stock import OrdemServico
    from .models_base import ConfiguracaoFiscal, DadosEmpresa

    if ordem.status != 'CONCLUIDA':
        raise ValueError('Apenas ordens concluídas podem ter faturas emitidas.')

    # Calcular valores brutos e descontos para cada serviço
    servicos_com_totais = []
    for servico_orc in ordem.servicos_orcamento.all():
        try:
            qtd = Decimal(str(servico_orc.quantidade)) if servico_orc.quantidade is not None else Decimal('0.00')
            valor_unit = Decimal(str(servico_orc.valor_unitario)) if servico_orc.valor_unitario is not None else Decimal('0.00')
            desconto = Decimal(str(servico_orc.desconto)) if servico_orc.desconto is not None else Decimal('0.00')
            desconto_percentual = Decimal(str(servico_orc.desconto_percentual)) if servico_orc.desconto_percentual is not None else Decimal('0.00')
            servico_orc.valor_total_bruto = qtd * valor_unit
            if desconto_percentual > 0:
                servico_orc.desconto_aplicado = servico_orc.valor_total_bruto * (desconto_percentual / Decimal('100'))
                servico_orc.desconto_tipo = f"{desconto_percentual}%"
            elif desconto > 0:
                servico_orc.desconto_aplicado = desconto
                servico_orc.desconto_tipo = f"{desconto:.2f} MT"
            else:
                servico_orc.desconto_aplicado = Decimal('0.00')
                servico_orc.desconto_tipo = ""
            for item in servico_orc.itens.all():
                try:
                    qtd_item = Decimal(str(item.quantidade)) if item.quantidade is not None else Decimal('0.00')
                    valor_unit_item = Decimal(str(item.valor_unitario)) if item.valor_unitario is not None else Decimal('0.00')
                    item.valor_total_bruto = qtd_item * valor_unit_item
                    item_desconto = Decimal(str(item.desconto)) if item.desconto is not None else Decimal('0.00')
                    item_desconto_percentual = Decimal(str(item.desconto_percentual)) if item.desconto_percentual is not None else Decimal('0.00')
                    if item_desconto_percentual > 0:
                        item.desconto_aplicado = item.valor_total_bruto * (item_desconto_percentual / Decimal('100'))
                        item.desconto_tipo = f"{item_desconto_percentual}%"
                    elif item_desconto > 0:
                        item.desconto_aplicado = item_desconto
                        item.desconto_tipo = f"{item_desconto:.2f} MT"
                    else:
                        item.desconto_aplicado = Decimal('0.00')
                        item.desconto_tipo = ""
                except (ValueError, TypeError, AttributeError, InvalidOperation):
                    item.valor_total_bruto = Decimal('0.00')
                    item.desconto_aplicado = Decimal('0.00')
                    item.desconto_tipo = ""
            servicos_com_totais.append(servico_orc)
        except (ValueError, TypeError, AttributeError, InvalidOperation):
            servico_orc.valor_total_bruto = Decimal('0.00')
            servico_orc.desconto_aplicado = Decimal('0.00')
            servico_orc.desconto_tipo = ""
            servicos_com_totais.append(servico_orc)

    try:
        total_servicos = sum(Decimal(str(s.valor_total)) for s in ordem.servicos_orcamento.all())
    except (ValueError, InvalidOperation, TypeError):
        total_servicos = Decimal('0.00')
    try:
        total_itens = sum(Decimal(str(item.valor_total)) for servico_orc in ordem.servicos_orcamento.all() for item in servico_orc.itens.all())
    except (ValueError, InvalidOperation, TypeError):
        total_itens = Decimal('0.00')
    try:
        total_transporte = sum(Decimal(str(t.valor_frete)) for t in ordem.transportes_orcamento.all())
    except (ValueError, InvalidOperation, TypeError):
        total_transporte = Decimal('0.00')
    try:
        subtotal = Decimal(str(total_servicos)) + Decimal(str(total_itens)) + Decimal(str(total_transporte))
    except (ValueError, InvalidOperation):
        subtotal = Decimal('0.00')

    total_bruto_servicos = sum(getattr(s, 'valor_total_bruto', Decimal('0.00')) for s in servicos_com_totais)
    total_bruto_itens = Decimal('0.00')
    total_descontos_aplicados = sum(getattr(s, 'desconto_aplicado', Decimal('0.00')) for s in servicos_com_totais)
    for servico_orc in servicos_com_totais:
        for item in servico_orc.itens.all():
            total_bruto_itens += getattr(item, 'valor_total_bruto', Decimal('0.00'))
            total_descontos_aplicados += getattr(item, 'desconto_aplicado', Decimal('0.00'))
    total_bruto = total_bruto_servicos + total_bruto_itens + total_transporte

    try:
        desconto_global = Decimal(str(ordem.desconto)) if ordem.desconto else Decimal('0.00')
    except (ValueError, InvalidOperation, TypeError):
        desconto_global = Decimal('0.00')
    try:
        valor_apos_desconto = max(Decimal('0.00'), subtotal - desconto_global)
    except (ValueError, InvalidOperation):
        valor_apos_desconto = subtotal

    try:
        taxa_iva_decimal = ConfiguracaoFiscal.get_taxa_iva_atual()
        if not isinstance(taxa_iva_decimal, Decimal):
            taxa_iva_decimal = Decimal(str(taxa_iva_decimal))
    except Exception:
        taxa_iva_decimal = Decimal('0.16')
    try:
        taxa_iva_percentual = taxa_iva_decimal * Decimal('100.00')
        valor_iva = valor_apos_desconto * taxa_iva_decimal
        valor_final = valor_apos_desconto + valor_iva
    except (ValueError, InvalidOperation):
        taxa_iva_percentual = Decimal('16.00')
        valor_iva = Decimal('0.00')
        valor_final = valor_apos_desconto

    dados_empresa = DadosEmpresa.objects.first()
    hoje = datetime.now()
    ano_atual = hoje.year

    with transaction.atomic():
        is_primeira_emissao = (ordem.numero_impressao_fatura or 0) == 0
        if is_primeira_emissao:
            try:
                from .models_financas import ContadorSerieDocumento
                num = ContadorSerieDocumento.get_proximo_numero('FT', ano_atual)
                numero_fatura = f"FT-{ano_atual}-{num:06d}"
                ordem.numero_fatura_fiscal = numero_fatura
            except Exception:
                ordens_concluidas_antes = OrdemServico.objects.filter(
                    codigo__startswith='OS', status='CONCLUIDA'
                ).exclude(id=ordem.id)
                if ordem.data_conclusao:
                    data_ref_ordem = ordem.data_conclusao.date()
                    ordens_concluidas_antes = ordens_concluidas_antes.filter(
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
                    ordens_concluidas_antes = ordens_concluidas_antes.filter(
                        Q(data_criacao__date__year=ano_atual) & (
                            Q(data_criacao__date__lt=data_ref_ordem) |
                            Q(data_criacao__date=data_ref_ordem, id__lt=ordem.id)
                        )
                    )
                numero_sequencial = ordens_concluidas_antes.count() + 1
                numero_fatura = f"FAT-{ano_atual}-{numero_sequencial:06d}"
        else:
            numero_fatura = ordem.numero_fatura_fiscal or f"FAT-{ano_atual}-(reimpressão)"

        ordem.numero_impressao_fatura = (ordem.numero_impressao_fatura or 0) + 1
        update_fields = ['numero_impressao_fatura']
        if ordem.numero_fatura_fiscal:
            update_fields.append('numero_fatura_fiscal')
        ordem.save(update_fields=update_fields)

        # Na primeira emissão, criar PendenteContaReceber — Finanças confirma depois e cria os lançamentos
        # Se a ordem tiver parcelas que somam 100%, não criar VENDAS_FATURA (o fluxo por parcela já criou VENDAS_PARCELA)
        if is_primeira_emissao and request and request.user:
            try:
                from .models_financas import PendenteContaReceber, LancamentoFinanceiro
                from .parcelas_vendas_utils import ordem_tem_parcelas_validas
                usa_parcelas = ordem_tem_parcelas_validas(ordem)
                if not usa_parcelas and not PendenteContaReceber.objects.filter(origem_tipo='VENDAS_FATURA', origem_id=ordem.id).exists() and not LancamentoFinanceiro.objects.filter(origem_tipo='VENDAS', origem_id=ordem.id).exists():
                    valor = getattr(ordem, 'valor_total', None) or Decimal('0.00')
                    if isinstance(valor, (int, float)):
                        valor = Decimal(str(valor))
                    credor = (ordem.cliente.nome if ordem.cliente else ordem.nome_cliente_pagamento or 'Cliente')[:300]
                    descricao = f"Fatura {numero_fatura} - {ordem.codigo}"
                    try:
                        from django.urls import reverse
                        url_origem = reverse('producao:servico_ordem_detail', args=[ordem.id])
                    except Exception:
                        url_origem = ''
                    PendenteContaReceber.objects.create(
                        origem_tipo='VENDAS_FATURA',
                        origem_id=ordem.id,
                        credor=credor,
                        valor=valor,
                        descricao=descricao,
                        data_vencimento=hoje.date(),
                        url_origem=url_origem,
                    )
            except Exception as e:
                logger.warning(f'Não foi possível criar lançamento financeiro para fatura {ordem.id}: {e}')

    tipo_documento = 'ORIGINAL' if ordem.numero_impressao_fatura == 1 else f'CÓPIA {ordem.numero_impressao_fatura - 1}'
    if ordem.cliente:
        cliente_nome = ordem.cliente.nome
        cliente_documento = getattr(ordem.cliente, 'nuit', '') or ''
        cliente_endereco = getattr(ordem.cliente, 'endereco', '') or ''
        cliente_email = getattr(ordem.cliente, 'email', '') or ''
    else:
        cliente_nome = ordem.nome_cliente_pagamento or 'Cliente não identificado'
        cliente_documento = getattr(ordem, 'nuit_cliente_pagamento', '') or ''
        cliente_endereco = ordem.endereco_servico or ''
        cliente_email = ''

    return {
        'request': request,
        'ordem': ordem,
        'dados_empresa': dados_empresa,
        'servicos_orcamento': servicos_com_totais,
        'transportes': ordem.transportes_orcamento.all(),
        'total_servicos': total_servicos,
        'total_itens': total_itens,
        'total_transporte': total_transporte,
        'total_bruto': total_bruto,
        'total_descontos_aplicados': total_descontos_aplicados,
        'subtotal': subtotal,
        'desconto_global': desconto_global,
        'valor_apos_desconto': valor_apos_desconto,
        'taxa_iva': taxa_iva_percentual,
        'valor_iva': valor_iva,
        'valor_final': valor_final,
        'numero_fatura': numero_fatura,
        'data_emissao': hoje,
        'hora_emissao': hoje.time(),
        'tipo_documento': tipo_documento,
        'cliente_nome': cliente_nome,
        'cliente_documento': cliente_documento,
        'cliente_endereco': cliente_endereco,
        'cliente_email': cliente_email,
        'MEDIA_URL': getattr(settings, 'MEDIA_URL', '/media/'),
    }
