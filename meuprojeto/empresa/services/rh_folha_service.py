"""Operações de folha salarial (cálculo, fecho, reabertura, pagamento)."""
import calendar
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum

from meuprojeto.empresa.models_rh import (
    BeneficioFolha,
    DescontoFolha,
    FolhaSalarial,
    Funcionario,
    FuncionarioFolha,
    HorasExtras,
    Presenca,
)


@transaction.atomic
def calcular_folha(folha):
    """
    Adiciona funcionários activos à folha, recalcula totais.
    Mantém status ABERTA (estados válidos: ABERTA, FECHADA, PAGA).
    """
    if folha.status != 'ABERTA':
        raise ValidationError('Apenas folhas abertas podem ser calculadas.')

    funcionarios_adicionados = 0
    for funcionario in Funcionario.objects.filter(status='AT'):
        if FuncionarioFolha.objects.filter(folha=folha, funcionario=funcionario).exists():
            continue
        FuncionarioFolha.objects.create(
            folha=folha,
            funcionario=funcionario,
            salario_base=funcionario.get_salario_atual(),
            dias_trabalhados=22,
            horas_trabalhadas=176,
            observacoes='Adicionado automaticamente no cálculo da folha',
        )
        funcionarios_adicionados += 1

    folha.calcular_totais()
    return {
        'funcionarios_adicionados': funcionarios_adicionados,
        'total_funcionarios': folha.total_funcionarios,
        'total_liquido': folha.total_liquido,
    }


@transaction.atomic
def fechar_folha(folha, user=None, observacoes=''):
    resultado = folha.fechar_folha(user=user, observacoes=observacoes)
    from meuprojeto.empresa.services.rh_financas_sync import criar_ou_actualizar_pendente_pagar_folha
    pendente = criar_ou_actualizar_pendente_pagar_folha(folha)
    resultado['pendente_financas_id'] = getattr(pendente, 'id', None)
    return resultado


@transaction.atomic
def reabrir_folha(folha, user=None, motivo=''):
    from meuprojeto.empresa.services.rh_financas_sync import rejeitar_pendente_pagar_folha
    resultado = folha.reabrir_folha(user=user, motivo=motivo)
    rejeitar_pendente_pagar_folha(folha.id)
    return resultado


@transaction.atomic
def marcar_folha_paga(folha, data_pagamento=None, observacoes=''):
    return folha.marcar_como_paga(data_pagamento=data_pagamento, observacoes=observacoes)


def _periodo_mes_referencia(mes_referencia):
    if not mes_referencia:
        return None, None
    inicio = mes_referencia.replace(day=1)
    ultimo_dia = calendar.monthrange(mes_referencia.year, mes_referencia.month)[1]
    return inicio, mes_referencia.replace(day=ultimo_dia)


def montar_contexto_funcionario_folha_detail(folha, funcionario):
    """Contexto para o detalhe do funcionário dentro de uma folha salarial."""
    funcionario_folha = (
        folha.funcionarios_folha.filter(funcionario=funcionario)
        .select_related(
            'funcionario__cargo',
            'funcionario__departamento',
            'funcionario__sucursal',
        )
        .first()
    )
    if not funcionario_folha:
        return None

    funcionario_folha.calcular_salario()
    inicio, fim = _periodo_mes_referencia(folha.mes_referencia)

    presencas = []
    presencas_por_tipo = {}
    if inicio and fim:
        presencas = list(
            Presenca.objects.filter(
                funcionario=funcionario,
                data__gte=inicio,
                data__lte=fim,
            )
            .select_related('tipo_presenca')
            .order_by('data')
        )
        for presenca in presencas:
            codigo = presenca.tipo_presenca.codigo if presenca.tipo_presenca else 'N/A'
            presencas_por_tipo[codigo] = presencas_por_tipo.get(codigo, 0) + 1

    horas_extras = []
    total_horas_extras_quantidade = Decimal('0')
    total_horas_extras_valor = Decimal('0')
    if inicio and fim:
        horas_extras = list(
            HorasExtras.objects.filter(
                funcionario=funcionario,
                data__gte=inicio,
                data__lte=fim,
            ).order_by('data')
        )
        agg = HorasExtras.objects.filter(
            funcionario=funcionario,
            data__gte=inicio,
            data__lte=fim,
        ).aggregate(q=Sum('quantidade_horas'), v=Sum('valor_total'))
        total_horas_extras_quantidade = agg['q'] or Decimal('0')
        total_horas_extras_valor = agg['v'] or Decimal('0')

    descontos_qs = DescontoFolha.objects.filter(
        funcionario_folha=funcionario_folha,
    ).select_related('desconto')
    descontos_manuais = [
        d for d in descontos_qs if not d.desconto.aplicar_automaticamente
    ]
    descontos_automaticos = [
        d for d in descontos_qs if d.desconto.aplicar_automaticamente
    ]

    return {
        'folha': folha,
        'funcionario': funcionario,
        'funcionario_folha': funcionario_folha,
        'beneficios_folha': list(
            BeneficioFolha.objects.filter(funcionario_folha=funcionario_folha).select_related(
                'beneficio',
            )
        ),
        'descontos_manuais': descontos_manuais,
        'descontos_automaticos': descontos_automaticos,
        'presencas': presencas,
        'presencas_por_tipo': presencas_por_tipo,
        'horas_extras': horas_extras,
        'total_horas_extras_quantidade': total_horas_extras_quantidade,
        'total_horas_extras_valor': total_horas_extras_valor,
    }
