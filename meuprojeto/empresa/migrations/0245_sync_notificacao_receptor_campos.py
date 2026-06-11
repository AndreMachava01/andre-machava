# Sincroniza campos de receptor no modelo (colunas já existem desde 0147)

from django.db import migrations, models


def preencher_receptor_vazio(apps, schema_editor):
    Notificacao = apps.get_model('empresa', 'NotificacaoLogisticaUnificada')
    Notificacao.objects.filter(documento_receptor__isnull=True).update(documento_receptor='')
    Notificacao.objects.filter(nome_receptor__isnull=True).update(nome_receptor='')


class Migration(migrations.Migration):

    dependencies = [
        ('empresa', '0244_sync_notificacao_motorista_operacao'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='notificacaologisticaunificada',
                    name='nome_receptor',
                    field=models.CharField(
                        blank=True,
                        default='',
                        help_text='Nome completo do receptor que assinou o documento',
                        max_length=200,
                    ),
                ),
                migrations.AddField(
                    model_name='notificacaologisticaunificada',
                    name='documento_receptor',
                    field=models.CharField(
                        blank=True,
                        default='',
                        help_text='Número de documento (BI/Passaporte) do receptor',
                        max_length=50,
                    ),
                ),
                migrations.AddField(
                    model_name='notificacaologisticaunificada',
                    name='assinatura_receptor',
                    field=models.ImageField(
                        blank=True,
                        help_text='Assinatura do receptor para confirmação de recebimento',
                        null=True,
                        upload_to='assinaturas_receptor/%Y/%m/%d/',
                    ),
                ),
            ],
            database_operations=[],
        ),
        migrations.RunPython(preencher_receptor_vazio, migrations.RunPython.noop),
    ]
