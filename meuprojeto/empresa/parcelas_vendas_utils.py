"""
Utilitários para processar parcelas de vendas (ParcelaPagamentoOrcamento) e criar
PendenteContaReceber — fluxo igual ao das empreitadas (Contas a receber, Finanças confirma).

Regra: o pagamento parcelado aplica-se apenas a ordens de SERVIÇOS, não a vendas de produtos
(orçamentos/pedidos com itens produto_tipo PRODUTO/ACABADO).

O valor de cada parcela é calculado sobre o total COM IVA, para coincidir com o que aparece
no contrato (ex.: "30% no ato da assinatura = 54.009,95 MT"). Caso contrário o adiantamento
enviado a Finanças (30% do total sem IVA) ficaria diferente do valor no contrato.
"""
import logging
from decimal import Decimal
from datetime import date

logger = logging.getLogger(__name__)


def _valor_total_com_iva_ordem(ordem_servico):
    """
    Retorna o valor total da ordem COM IVA (mesma base usada no contrato para as parcelas).
    Assim o valor do pendente em Finanças coincide com o "30% no ato da assinatura" do contrato.
    """
    ordem_servico.refresh_from_db()
    valor_sem_iva = getattr(ordem_servico, 'valor_total', None) or Decimal('0.00')
    if isinstance(valor_sem_iva, (int, float)):
        valor_sem_iva = Decimal(str(valor_sem_iva))
    if valor_sem_iva <= 0:
        return Decimal('0.00')
    try:
        from .models_base import ConfiguracaoFiscal
        config = ConfiguracaoFiscal.objects.first()
        taxa_iva = Decimal(str(config.iva)) if config and hasattr(config, 'iva') else Decimal('0.16')
    except Exception:
        taxa_iva = Decimal('0.16')
    return valor_sem_iva * (Decimal('1') + taxa_iva)


def percentagem_minima_valor_servicos_cotacao(orcamento, servico_orcamento_ids=None):
    """
    Percentagem mínima do total do contrato para que o valor
    da parcela não seja inferior ao valor dos serviços cotados (soma de
    `ServicoOrcamentoServico.valor_total`).

    IVA incide sobre o total de forma uniforme; esta proporção mantém-se no valor com IVA.

    :param servico_orcamento_ids: IDs de ServicoOrcamentoServico a considerar, ou None / lista
        vazia para todos os serviços da cotação.
    :return: inteiro 0–100 (arredondado para cima ao % inteiro mais próximo).
    """
    from decimal import ROUND_UP

    # Base do contrato (sem desconto global) para evitar mínimos > 100% quando existe desconto elevado.
    try:
        valor_servicos = sum((s.valor_total or Decimal('0')) for s in orcamento.servicos_orcamento.all())
        valor_itens = sum(
            (item.valor_total or Decimal('0'))
            for servico in orcamento.servicos_orcamento.all()
            for item in servico.itens.all()
        )
        valor_transporte = sum((t.valor_frete or Decimal('0')) for t in orcamento.transportes_orcamento.all())
        vb = valor_servicos + valor_itens + valor_transporte
    except Exception:
        vb = Decimal(str(orcamento.valor_total or 0))

    if vb <= 0:
        return 0
    todos = list(orcamento.servicos_orcamento.all())
    if not todos:
        return 0
    if servico_orcamento_ids:
        id_set = set(servico_orcamento_ids)
        linhas = [s for s in todos if s.id in id_set]
    else:
        linhas = todos
    if not linhas:
        return 0
    vs = sum((s.valor_total or Decimal('0')) for s in linhas)
    if vs <= 0:
        return 0
    pct = (vs / vb) * Decimal('100')
    q = pct.quantize(Decimal('1'), rounding=ROUND_UP)
    return int(min(q, Decimal('100')))


def ordem_e_so_servicos(ordem_servico):
    """
    Retorna True se a ordem/orçamento contém apenas serviços (Item com produto_tipo='SERVICO').
    Vendas de produtos (PRODUTO/ACABADO) não usam pagamento parcelado.
    """
    servicos_orc = list(ordem_servico.servicos_orcamento.select_related('servico').all())
    if not servicos_orc:
        return False
    return all(getattr(s.servico, 'produto_tipo', None) == 'SERVICO' for s in servicos_orc)


def _copiar_parcelas_para_ordem(orcamento, ordem_servico):
    """
    Copia parcelas_pagamento do orçamento (COT) para a ordem de serviço (OS).
    Só copia se o orçamento for apenas de serviços (pagamento parcelado não se aplica a vendas de produtos).
    Mapeia servicos pelo servico_id (Item).
    """
    from .models_stock import ParcelaPagamentoOrcamento

    if not ordem_e_so_servicos(orcamento):
        return

    parcelas_origem = list(orcamento.parcelas_pagamento.order_by('numero_ordem'))
    if not parcelas_origem:
        return

    # Mapa: servico_orc_old.id -> servico_orc_new (na ordem)
    mapa_servicos = {}
    for srv_old in orcamento.servicos_orcamento.all():
        srv_new = ordem_servico.servicos_orcamento.filter(servico_id=srv_old.servico_id).first()
        if srv_new:
            mapa_servicos[srv_old.id] = srv_new

    for parcela_old in parcelas_origem:
        parcela_new = ParcelaPagamentoOrcamento.objects.create(
            ordem_servico=ordem_servico,
            numero_ordem=parcela_old.numero_ordem,
            percentagem=parcela_old.percentagem,
            tipo=parcela_old.tipo,
        )
        servicos_ids = [mapa_servicos[s.id].id for s in parcela_old.servicos.all() if s.id in mapa_servicos]
        if servicos_ids:
            parcela_new.servicos.set(servicos_ids)


def processar_parcelas_vendas_receber(ordem_servico, user, trigger_tipo=None):
    """
    Cria PendenteContaReceber para parcelas que ficaram devidas.
    Apenas para ordens de SERVIÇOS; vendas de produtos não usam parcelas (retorna 0).
    trigger_tipo: 'ASSINATURA' (ordem criada), 'CONCLUSAO' (ordem concluída)
    """
    from .models_financas import PendenteContaReceber
    from .models_stock import ParcelaPagamentoOrcamento

    if not ordem_e_so_servicos(ordem_servico):
        return 0

    parcelas = list(ordem_servico.parcelas_pagamento.order_by('numero_ordem'))
    if not parcelas or sum(p.percentagem for p in parcelas) != 100:
        return 0

    valor_total = _valor_total_com_iva_ordem(ordem_servico)
    if valor_total <= 0:
        return 0

    credor = (ordem_servico.cliente.nome if ordem_servico.cliente else ordem_servico.nome_cliente_pagamento or 'Cliente')[:300]
    hoje = date.today()

    try:
        from django.urls import reverse
        url_origem = reverse('producao:servico_ordem_detail', args=[ordem_servico.id])
    except Exception:
        url_origem = ''

    criados = 0
    for parcela in parcelas:
        if PendenteContaReceber.objects.filter(origem_tipo='VENDAS_PARCELA', origem_id=parcela.id).exists():
            continue

        deve_criar = False
        if trigger_tipo == 'ASSINATURA':
            deve_criar = parcela.tipo == ParcelaPagamentoOrcamento.TIPO_ASSINATURA
        elif trigger_tipo == 'CONCLUSAO':
            if parcela.tipo == ParcelaPagamentoOrcamento.TIPO_CONCLUSAO_TOTAL:
                deve_criar = ordem_servico.status == 'CONCLUIDA'
            elif parcela.tipo == ParcelaPagamentoOrcamento.TIPO_CONCLUSAO_SERVICOS:
                # Quando ordem concluída, serviços seleccionados estão concluídos
                deve_criar = ordem_servico.status == 'CONCLUIDA'
        else:
            raise ValueError('trigger_tipo obrigatório')

        if not deve_criar:
            continue

        valor = valor_total * Decimal(parcela.percentagem) / Decimal('100')
        if valor <= 0:
            continue

        descricao = f"Parcela {parcela.numero_ordem} ({parcela.get_tipo_display()}) - {ordem_servico.codigo}"
        PendenteContaReceber.objects.create(
            origem_tipo='VENDAS_PARCELA',
            origem_id=parcela.id,
            credor=credor,
            valor=valor,
            descricao=descricao,
            data_vencimento=hoje,
            url_origem=url_origem,
        )
        criados += 1

    return criados


def criar_pendente_parcela_ligada_etapa(ordem_servico, parcela, user):
    """
    Cria PendenteContaReceber para uma parcela que está ligada a uma etapa do plano.
    Chamado quando essa etapa é concluída. Retorna 1 se criou, 0 se já existia ou não criou.
    """
    from .models_financas import PendenteContaReceber

    if not parcela or parcela.ordem_servico_id != ordem_servico.id:
        return 0
    if PendenteContaReceber.objects.filter(origem_tipo='VENDAS_PARCELA', origem_id=parcela.id).exists():
        return 0

    valor_total = _valor_total_com_iva_ordem(ordem_servico)
    if valor_total <= 0:
        return 0

    valor = valor_total * Decimal(parcela.percentagem) / Decimal('100')
    if valor <= 0:
        return 0

    credor = (ordem_servico.cliente.nome if ordem_servico.cliente else ordem_servico.nome_cliente_pagamento or 'Cliente')[:300]
    hoje = date.today()
    try:
        from django.urls import reverse
        url_origem = reverse('producao:servico_ordem_detail', args=[ordem_servico.id])
    except Exception:
        url_origem = ''

    descricao = f"Parcela {parcela.numero_ordem} ({parcela.get_tipo_display()}) - {ordem_servico.codigo}"
    PendenteContaReceber.objects.create(
        origem_tipo='VENDAS_PARCELA',
        origem_id=parcela.id,
        credor=credor,
        valor=valor,
        descricao=descricao,
        data_vencimento=hoje,
        url_origem=url_origem,
    )
    return 1


def processar_parcelas_por_etapa_concluida(ordem_servico, user):
    """
    Após concluir uma actividade, verifica se alguma parcela CONCLUSAO_SERVICOS fica satisfeita
    (todos os serviços da parcela foram "entregues" por actividades já CONCLUIDA com servicos_entregues).
    Cria PendenteContaReceber para cada parcela que ainda não tem e cujos serviços estão todos cobertos.
    Retorna o número de pendentes criados.
    """
    from .models_financas import PendenteContaReceber
    from .models_stock import ParcelaPagamentoOrcamento

    if not ordem_e_so_servicos(ordem_servico):
        return 0

    parcelas = list(ordem_servico.parcelas_pagamento.filter(tipo=ParcelaPagamentoOrcamento.TIPO_CONCLUSAO_SERVICOS).prefetch_related('servicos'))
    if not parcelas:
        return 0

    valor_total = _valor_total_com_iva_ordem(ordem_servico)
    if valor_total <= 0:
        return 0

    # Serviços já "entregues" pela união das actividades CONCLUIDA
    from .models_stock import AtividadeExecucao
    atividades_concluidas = ordem_servico.atividades_execucao.filter(status='CONCLUIDA').prefetch_related('servicos_entregues')
    servicos_entregues_ids = set()
    for atv in atividades_concluidas:
        servicos_entregues_ids.update(atv.servicos_entregues.values_list('id', flat=True))

    credor = (ordem_servico.cliente.nome if ordem_servico.cliente else ordem_servico.nome_cliente_pagamento or 'Cliente')[:300]
    hoje = date.today()
    try:
        from django.urls import reverse
        url_origem = reverse('producao:servico_ordem_detail', args=[ordem_servico.id])
    except Exception:
        url_origem = ''

    criados = 0
    for parcela in parcelas:
        if PendenteContaReceber.objects.filter(origem_tipo='VENDAS_PARCELA', origem_id=parcela.id).exists():
            continue
        parcela_servicos_ids = set(parcela.servicos.values_list('id', flat=True))
        if not parcela_servicos_ids:
            continue
        if not parcela_servicos_ids.issubset(servicos_entregues_ids):
            continue

        valor = valor_total * Decimal(parcela.percentagem) / Decimal('100')
        if valor <= 0:
            continue

        descricao = f"Parcela {parcela.numero_ordem} ({parcela.get_tipo_display()}) - {ordem_servico.codigo}"
        PendenteContaReceber.objects.create(
            origem_tipo='VENDAS_PARCELA',
            origem_id=parcela.id,
            credor=credor,
            valor=valor,
            descricao=descricao,
            data_vencimento=hoje,
            url_origem=url_origem,
        )
        criados += 1

    return criados


def ordem_tem_parcelas_validas(ordem_servico):
    """Retorna True se a ordem é só de serviços e tem parcelas que somam 100% (pagamento parcelado só para serviços)."""
    if not ordem_e_so_servicos(ordem_servico):
        return False
    parcelas = list(ordem_servico.parcelas_pagamento.all())
    return bool(parcelas) and sum(p.percentagem for p in parcelas) == 100
