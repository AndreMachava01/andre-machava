"""
Integração RH ↔ Finanças (Contas a pagar).
Espelha o padrão de logistica_financas_sync.
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional

from django.utils import timezone

logger = logging.getLogger(__name__)


def _url_folha(folha_id: int) -> str:
    try:
        from django.urls import reverse
        return reverse('rh:folha_detail', args=[folha_id])
    except Exception:
        return f'/rh/folha-salarial/detalhes/{folha_id}/'


def criar_ou_actualizar_pendente_pagar_folha(folha) -> Optional[object]:
    """Regista folha fechada em Contas a pagar (Finanças)."""
    from meuprojeto.empresa.models_financas import LancamentoFinanceiro, PendenteContaPagar

    if folha.status not in ('FECHADA', 'PAGA'):
        return None

    valor = folha.total_liquido or folha.total_bruto or Decimal('0')
    if isinstance(valor, (int, float)):
        valor = Decimal(str(valor))
    if valor <= 0:
        return None

    if LancamentoFinanceiro.objects.filter(
        origem_tipo__in=('RH', 'RH_FOLHA_SALARIAL'),
        origem_id=folha.id,
    ).exists():
        return None

    mes = folha.mes_referencia.strftime('%m/%Y')
    descricao = f'Folha salarial {mes} — {folha.total_funcionarios} funcionário(s)'

    pendente = PendenteContaPagar.objects.filter(
        origem_tipo='RH_FOLHA_SALARIAL',
        origem_id=folha.id,
    ).exclude(estado='REJEITADO').first()

    if pendente:
        if pendente.estado == 'CONFIRMADO':
            return pendente
        pendente.beneficiario = 'Folha de pagamento RH'[:300]
        pendente.valor = valor
        pendente.descricao = descricao[:500]
        pendente.data_vencimento = folha.data_fechamento or timezone.now().date()
        pendente.url_origem = _url_folha(folha.id)
        pendente.save(update_fields=[
            'beneficiario', 'valor', 'descricao', 'data_vencimento', 'url_origem',
        ])
        return pendente

    return PendenteContaPagar.objects.create(
        origem_tipo='RH_FOLHA_SALARIAL',
        origem_id=folha.id,
        beneficiario='Folha de pagamento RH',
        valor=valor,
        descricao=descricao[:500],
        data_vencimento=folha.data_fechamento or timezone.now().date(),
        url_origem=_url_folha(folha.id),
        estado='PENDENTE',
    )


def rejeitar_pendente_pagar_folha(folha_id: int) -> int:
    from meuprojeto.empresa.models_financas import PendenteContaPagar

    return PendenteContaPagar.objects.filter(
        origem_tipo='RH_FOLHA_SALARIAL',
        origem_id=folha_id,
        estado='PENDENTE',
    ).update(estado='REJEITADO')


def auditar_integracao_rh_financas():
    """
    Resumo de pendências RH em Finanças vs origens sem pendente.
    Útil para diagnóstico operacional.
    """
    from meuprojeto.empresa.models_financas import PendenteContaPagar
    from meuprojeto.empresa.models_producao_servicos import TrabalhoEmpreitada
    from meuprojeto.empresa.models_rh import FolhaSalarial

    folhas_fechadas = FolhaSalarial.objects.filter(status__in=('FECHADA', 'PAGA'))
    folhas_sem_pendente = []
    for folha in folhas_fechadas:
        if (folha.total_liquido or 0) <= 0:
            continue
        existe = PendenteContaPagar.objects.filter(
            origem_tipo='RH_FOLHA_SALARIAL',
            origem_id=folha.id,
        ).exclude(estado='REJEITADO').exists()
        if not existe:
            folhas_sem_pendente.append(folha.id)

    empreitadas_concluidas = TrabalhoEmpreitada.objects.filter(status='CONCLUIDO')
    empreitadas_sem_pendente = []
    for trabalho in empreitadas_concluidas:
        if trabalho.valor_fixo and trabalho.valor_fixo > 0:
            tem_emp = PendenteContaPagar.objects.filter(
                origem_tipo='RH_EMPREITADA', origem_id=trabalho.id,
            ).exclude(estado='REJEITADO').exists()
            tem_parcela = PendenteContaPagar.objects.filter(
                origem_tipo='RH_EMP_PARCELA',
                origem_id__in=trabalho.parcelas_pagamento_que_exigem.values_list('id', flat=True),
            ).exclude(estado='REJEITADO').exists()
            if not tem_emp and not tem_parcela:
                empreitadas_sem_pendente.append(trabalho.id)

    pendentes_rh = PendenteContaPagar.objects.filter(
        origem_tipo__in=('RH_FOLHA_SALARIAL', 'RH_EMPREITADA', 'RH_EMP_PARCELA'),
        estado='PENDENTE',
    ).count()

    return {
        'pendentes_rh_abertos': pendentes_rh,
        'folhas_fechadas_sem_pendente': folhas_sem_pendente,
        'empreitadas_concluidas_sem_pendente': empreitadas_sem_pendente,
    }
