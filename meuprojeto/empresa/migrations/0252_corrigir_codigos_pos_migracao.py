"""
Correcção pós-migração 0251:
- Restaura TRFREQ… (transferência ligada à requisição)
- Migra TRF/RAST remanescentes (timestamps) sem colidir com códigos existentes
"""
import re

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


def _proxima_sequencia(Model, prefixo, periodo, campo='codigo'):
    base = f'{prefixo}{periodo}'
    max_seq = 0
    for codigo in Model.objects.filter(**{f'{campo}__startswith': base}).values_list(campo, flat=True):
        if not _codigo_migrado(codigo, prefixo):
            continue
        try:
            max_seq = max(max_seq, int(codigo[len(base):]))
        except ValueError:
            continue
    return max_seq + 1


def _atribuir_codigo_seguro(obj, Model, prefixo, periodo, campo='codigo'):
    sequencia = _proxima_sequencia(Model, prefixo, periodo, campo)
    while True:
        novo_codigo = f'{prefixo}{periodo}{sequencia:04d}'
        if not Model.objects.filter(**{campo: novo_codigo}).exists():
            break
        sequencia += 1
    setattr(obj, campo, f'__TMP2_{obj.pk}__')
    obj.save(update_fields=[campo])
    setattr(obj, campo, novo_codigo)
    obj.save(update_fields=[campo])
    return novo_codigo


def _restaurar_transferencias_requisicao(TransferenciaStock, RequisicaoStock):
    for req in RequisicaoStock.objects.all():
        codigo_ligado = f'TRF{req.codigo}'
        codigo_errado = f'TRF{req.codigo[3:]}'
        if TransferenciaStock.objects.filter(codigo=codigo_ligado).exists():
            continue
        trf = TransferenciaStock.objects.filter(codigo=codigo_errado).first()
        if not trf:
            continue
        trf.codigo = f'__TMP_LINK_{trf.pk}__'
        trf.save(update_fields=['codigo'])
        trf.codigo = codigo_ligado
        trf.save(update_fields=['codigo'])


def _migrar_restantes(Model, prefixo, campo='codigo', campo_data='data_criacao'):
    for obj in Model.objects.all().order_by(campo_data, 'pk'):
        codigo_atual = getattr(obj, campo)
        if _codigo_migrado(codigo_atual, prefixo):
            continue
        if str(codigo_atual).startswith('__TMP'):
            continue
        periodo = _periodo(getattr(obj, campo_data))
        _atribuir_codigo_seguro(obj, Model, prefixo, periodo, campo)


def corrigir_codigos_pos_migracao(apps, schema_editor):
    TransferenciaStock = apps.get_model('empresa', 'TransferenciaStock')
    RequisicaoStock = apps.get_model('empresa', 'RequisicaoStock')
    RastreamentoEntrega = apps.get_model('empresa', 'RastreamentoEntrega')

    _restaurar_transferencias_requisicao(TransferenciaStock, RequisicaoStock)
    _migrar_restantes(TransferenciaStock, 'TRF')
    _migrar_restantes(
        RastreamentoEntrega,
        'RAST',
        campo='codigo_rastreamento',
    )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('empresa', '0251_migrar_codigos_ano_mes'),
    ]

    operations = [
        migrations.RunPython(corrigir_codigos_pos_migracao, reverse_code=noop),
    ]
