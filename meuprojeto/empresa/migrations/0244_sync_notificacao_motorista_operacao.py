# Sincroniza motorista_operacao no modelo (coluna já existe desde 0129)

from django.db import migrations, models


def preencher_motorista_vazio(apps, schema_editor):
    Notificacao = apps.get_model('empresa', 'NotificacaoLogisticaUnificada')
    Notificacao.objects.filter(motorista_operacao__isnull=True).update(motorista_operacao='')
    Notificacao.objects.filter(telefone_motorista_operacao__isnull=True).update(
        telefone_motorista_operacao=''
    )


class Migration(migrations.Migration):

    dependencies = [
        ('empresa', '0243_fornecedor_codigo'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='notificacaologisticaunificada',
                    name='motorista_operacao',
                    field=models.CharField(
                        blank=True,
                        default='',
                        help_text='Nome do motorista designado para esta operação específica',
                        max_length=200,
                    ),
                ),
                migrations.AddField(
                    model_name='notificacaologisticaunificada',
                    name='telefone_motorista_operacao',
                    field=models.CharField(
                        blank=True,
                        default='',
                        help_text='Telefone do motorista designado para esta operação',
                        max_length=13,
                    ),
                ),
            ],
            database_operations=[],
        ),
        migrations.RunPython(preencher_motorista_vazio, migrations.RunPython.noop),
    ]
