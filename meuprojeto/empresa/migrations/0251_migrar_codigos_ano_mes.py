"""
Migra códigos legados para o formato PREFIXO + YYYYMM + NNNN,
usando a data de criação de cada registo para o período mensal.
"""
import re
from collections import defaultdict

from django.db import migrations
from django.utils import timezone


def _periodo(dt):
    if dt is None:
        dt = timezone.now()
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt.strftime('%Y%m')


def _codigo_migrado(codigo, prefixo):
    if not codigo or not codigo.startswith(prefixo):
        return False
    sufixo = codigo[len(prefixo):]
    if not re.fullmatch(r'\d{10}', sufixo):
        return False
    ano = int(sufixo[:4])
    mes = int(sufixo[4:6])
    return 2000 <= ano <= 2100 and 1 <= mes <= 12


def _codigo_transferencia_ligada_requisicao(codigo):
    """TRFREQ2026060001 — transferência gerada a partir de requisição interna."""
    if not codigo or not codigo.startswith('TRF'):
        return False
    return _codigo_migrado(codigo[3:], 'REQ')


def _migrar_codigos_modelo(
    Model,
    prefixo,
    campo='codigo',
    campo_data='data_criacao',
    *,
    ignorar=None,
):
    """Retorna mapa código_antigo → código_novo."""
    registos = list(Model.objects.all().order_by(campo_data, 'pk'))
    pendentes = []

    for obj in registos:
        codigo_atual = getattr(obj, campo)
        if _codigo_migrado(codigo_atual, prefixo):
            continue
        if ignorar and ignorar(codigo_atual):
            continue
        pendentes.append((obj, codigo_atual))


    if not pendentes:
        return {}

    mapa = {}

    for obj, _ in pendentes:
        setattr(obj, campo, f'__MIG_{prefixo}_{obj.pk}__')
    Model.objects.bulk_update([obj for obj, _ in pendentes], [campo])

    por_periodo = defaultdict(list)
    for obj, codigo_antigo in pendentes:
        por_periodo[_periodo(getattr(obj, campo_data))].append((obj, codigo_antigo))

    for periodo, grupo in por_periodo.items():
        for sequencia, (obj, codigo_antigo) in enumerate(grupo, start=1):
            novo_codigo = f'{prefixo}{periodo}{sequencia:04d}'
            mapa[codigo_antigo] = novo_codigo
            setattr(obj, campo, novo_codigo)

    Model.objects.bulk_update([obj for obj, _ in pendentes], [campo])
    return mapa


def _atualizar_transferencias_ligadas_requisicao(TransferenciaStock, mapa_requisicao):
    if not mapa_requisicao:
        return

    atualizados = []
    for trf in TransferenciaStock.objects.all():
        if not trf.codigo or not trf.codigo.startswith('TRF'):
            continue
        sufixo = trf.codigo[3:]
        if sufixo in mapa_requisicao:
            trf.codigo = f'TRF{mapa_requisicao[sufixo]}'
            atualizados.append(trf)

    if atualizados:
        TransferenciaStock.objects.bulk_update(atualizados, ['codigo'])


def migrar_codigos_para_ano_mes(apps, schema_editor):
    RequisicaoStock = apps.get_model('empresa', 'RequisicaoStock')
    RequisicaoCompraExterna = apps.get_model('empresa', 'RequisicaoCompraExterna')
    OrdemCompra = apps.get_model('empresa', 'OrdemCompra')
    TransferenciaStock = apps.get_model('empresa', 'TransferenciaStock')
    RastreamentoEntrega = apps.get_model('empresa', 'RastreamentoEntrega')

    mapa_req = _migrar_codigos_modelo(RequisicaoStock, 'REQ')
    _atualizar_transferencias_ligadas_requisicao(TransferenciaStock, mapa_req)

    _migrar_codigos_modelo(RequisicaoCompraExterna, 'RQCOMP')
    _migrar_codigos_modelo(OrdemCompra, 'ORDCOMP')
    _migrar_codigos_modelo(
        TransferenciaStock,
        'TRF',
        ignorar=_codigo_transferencia_ligada_requisicao,
    )
    _migrar_codigos_modelo(
        RastreamentoEntrega,
        'RAST',
        campo='codigo_rastreamento',
    )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('empresa', '0250_rastreamento_dimensoes_carga'),
    ]

    operations = [
        migrations.RunPython(migrar_codigos_para_ano_mes, reverse_code=noop),
    ]
