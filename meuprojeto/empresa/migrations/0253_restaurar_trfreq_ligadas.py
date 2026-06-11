"""
Restaura códigos TRFREQ… (transferência ligada à requisição interna).

A migração 0251 re-numerava TRFREQ como TRF isolado; esta correcção é idempotente.
"""
from django.db import migrations


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


def restaurar_trfreq(apps, schema_editor):
    TransferenciaStock = apps.get_model('empresa', 'TransferenciaStock')
    RequisicaoStock = apps.get_model('empresa', 'RequisicaoStock')
    _restaurar_transferencias_requisicao(TransferenciaStock, RequisicaoStock)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('empresa', '0252_corrigir_codigos_pos_migracao'),
    ]

    operations = [
        migrations.RunPython(restaurar_trfreq, reverse_code=noop),
    ]
