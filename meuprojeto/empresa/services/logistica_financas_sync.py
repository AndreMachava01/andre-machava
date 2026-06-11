"""
Integração Logística (cost-billing) ↔ Finanças.
Cria pendentes em Contas a receber/pagar; confirmação e lançamentos ficam em views_financas.
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional

from django.utils import timezone

logger = logging.getLogger(__name__)


def _url_fatura(faturamento_id: int) -> str:
    try:
        from django.urls import reverse
        return reverse('stock:cost_billing:fatura_detail', args=[faturamento_id])
    except Exception:
        return f'/stock/cost-billing/faturas/{faturamento_id}/'


def _url_custo(custo_id: int) -> str:
    try:
        from django.urls import reverse
        return reverse('stock:cost_billing:custo_detail', args=[custo_id])
    except Exception:
        return f'/stock/cost-billing/custos/{custo_id}/'


def criar_ou_actualizar_pendente_receber_fatura(faturamento) -> Optional[object]:
    """Regista fatura de frete enviada em Contas a receber (Finanças)."""
    from ..models_financas import PendenteContaReceber, LancamentoFinanceiro

    if faturamento.status not in ('ENVIADO', 'VENCIDO'):
        return None

    valor = faturamento.valor_liquido or Decimal('0.00')
    if valor <= 0:
        return None

    if LancamentoFinanceiro.objects.filter(
        origem_tipo='LOGISTICA',
        origem_id=faturamento.id,
        conta__codigo='72.01',
    ).exists():
        return None

    descricao = f"Fatura frete {faturamento.numero_fatura} — {faturamento.cliente_nome}"
    pendente = PendenteContaReceber.objects.filter(
        origem_tipo='LOGISTICA',
        origem_id=faturamento.id,
    ).exclude(estado='REJEITADO').first()

    if pendente:
        if pendente.estado == 'CONFIRMADO':
            return pendente
        pendente.credor = (faturamento.cliente_nome or '')[:300]
        pendente.valor = valor
        pendente.descricao = descricao[:500]
        pendente.data_vencimento = faturamento.data_vencimento
        pendente.url_origem = _url_fatura(faturamento.id)
        pendente.save(update_fields=[
            'credor', 'valor', 'descricao', 'data_vencimento', 'url_origem',
        ])
        return pendente

    return PendenteContaReceber.objects.create(
        origem_tipo='LOGISTICA',
        origem_id=faturamento.id,
        credor=(faturamento.cliente_nome or '')[:300],
        valor=valor,
        descricao=descricao[:500],
        data_vencimento=faturamento.data_vencimento,
        url_origem=_url_fatura(faturamento.id),
    )


def criar_pendente_pagar_custo(custo) -> Optional[object]:
    """Regista custo logístico aprovado em Contas a pagar (Finanças)."""
    from ..models_financas import PendenteContaPagar, LancamentoFinanceiro

    if custo.status != 'APROVADO':
        return None

    valor = custo.valor or Decimal('0.00')
    if valor <= 0:
        return None

    if LancamentoFinanceiro.objects.filter(
        origem_tipo='LOGISTICA',
        origem_id=custo.id,
        conta__codigo='63.01',
        valor__lt=0,
    ).exists():
        return None

    if PendenteContaPagar.objects.filter(
        origem_tipo='LOGISTICA',
        origem_id=custo.id,
    ).exclude(estado='REJEITADO').exists():
        return None

    beneficiario = custo.centro_custo.nome if custo.centro_custo_id else 'Logística'
    if custo.rastreamento_entrega_id and custo.rastreamento_entrega.transportadora_id:
        beneficiario = custo.rastreamento_entrega.transportadora.nome

    descricao = f"{custo.codigo} — {custo.tipo_custo.nome if custo.tipo_custo_id else 'Custo logístico'}"
    if custo.descricao:
        descricao = f"{custo.codigo} — {custo.descricao}"[:500]

    return PendenteContaPagar.objects.create(
        origem_tipo='LOGISTICA',
        origem_id=custo.id,
        beneficiario=beneficiario[:300],
        valor=valor,
        descricao=descricao[:500],
        data_vencimento=custo.data_custo,
        url_origem=_url_custo(custo.id),
    )


def rejeitar_pendente_pagar_custo(custo_id: int) -> None:
    from ..models_financas import PendenteContaPagar

    PendenteContaPagar.objects.filter(
        origem_tipo='LOGISTICA',
        origem_id=custo_id,
        estado='PENDENTE',
    ).update(
        estado='REJEITADO',
        data_confirmacao=timezone.now(),
    )


def marcar_fatura_paga_apos_confirmacao(faturamento_id: int, data_pagamento) -> None:
    from ..models_cost_billing import FaturamentoFrete

    FaturamentoFrete.objects.filter(
        id=faturamento_id,
    ).exclude(status='PAGO').update(
        status='PAGO',
        data_pagamento=data_pagamento,
    )


def marcar_custo_faturado_apos_confirmacao(custo_id: int) -> None:
    from ..models_cost_billing import CustoLogistico

    CustoLogistico.objects.filter(
        id=custo_id,
        status='APROVADO',
    ).update(status='FATURADO')
