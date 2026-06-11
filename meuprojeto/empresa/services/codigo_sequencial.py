"""Geração de códigos sequenciais com prefixo + ano + mês + número."""
from __future__ import annotations

import re
import time
from typing import Type

from django.db import transaction
from django.db.models import Model
from django.utils import timezone


def periodo_ano_mes(dt=None) -> str:
    """Retorna YYYYMM para o período de sequência."""
    referencia = dt or timezone.now()
    return referencia.strftime('%Y%m')


def gerar_codigo_ano_mes(
    model_class: Type[Model],
    prefixo: str,
    *,
    campo: str = 'codigo',
    largura_sequencia: int = 4,
    dt=None,
) -> str:
    """
    Gera código no formato PREFIXO + YYYY + MM + NNNN.
    Exemplo: ORDCOMP2026060042, RQCOMP2026060003, TRF2026060007, REQ2026060012, RAST2026060005
    """
    periodo = periodo_ano_mes(dt)
    base = f'{prefixo}{periodo}'
    padrao = re.compile(rf'^{re.escape(prefixo)}(\d{{6}})(\d{{{largura_sequencia},}})$')

    with transaction.atomic():
        ultimo_codigo = (
            model_class.objects.select_for_update()
            .filter(**{f'{campo}__startswith': base})
            .order_by(f'-{campo}')
            .values_list(campo, flat=True)
            .first()
        )

        sequencia = 1
        if ultimo_codigo:
            match = padrao.match(str(ultimo_codigo))
            if match and match.group(1) == periodo:
                try:
                    sequencia = int(match.group(2)) + 1
                except ValueError:
                    sequencia = 1

        limite = 10 ** largura_sequencia - 1
        tentativas = 0
        while sequencia <= limite and tentativas < 200:
            codigo = f'{base}{sequencia:0{largura_sequencia}d}'
            if not model_class.objects.filter(**{campo: codigo}).exists():
                return codigo
            sequencia += 1
            tentativas += 1

        return f'{base}{int(time.time())}'


def gerar_codigo_rastreamento_entrega():
    """Código de rastreamento logístico: RAST + YYYYMM + sequencial."""
    from ..models_stock import RastreamentoEntrega
    return gerar_codigo_ano_mes(
        RastreamentoEntrega,
        'RAST',
        campo='codigo_rastreamento',
    )


def gerar_codigo_masterdata(
    model_class: Type[Model],
    prefixo: str,
    *,
    campo: str = 'codigo',
    largura_sequencia: int = 4,
) -> str:
    """
    Código operacional masterdata: PREFIXO + sequencial (ex.: REG0001, HUB0042).
    Sem ano/mês — adequado a dados mestres de configuração.
    """
    padrao = re.compile(rf'^{re.escape(prefixo)}(\d+)$')

    with transaction.atomic():
        codigos = (
            model_class.objects.select_for_update()
            .filter(**{f'{campo}__startswith': prefixo})
            .values_list(campo, flat=True)
        )
        max_seq = 0
        for codigo_existente in codigos:
            match = padrao.match(str(codigo_existente))
            if match:
                try:
                    max_seq = max(max_seq, int(match.group(1)))
                except ValueError:
                    continue

        sequencia = max_seq + 1
        limite = 10 ** largura_sequencia - 1
        while sequencia <= limite:
            codigo = f'{prefixo}{sequencia:0{largura_sequencia}d}'
            if not model_class.objects.filter(**{campo: codigo}).exists():
                return codigo
            sequencia += 1

        return f'{prefixo}{int(time.time())}'
