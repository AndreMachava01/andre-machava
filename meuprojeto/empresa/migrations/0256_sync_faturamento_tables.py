"""
Cria tabelas de faturamento de frete quando a migração 0126 foi marcada como
aplicada mas FaturamentoFrete, ItemFaturamento e ConfiguracaoFaturamento não existem.
"""
from django.db import migrations


FATURAMENTO_MODELS = (
    'ConfiguracaoFaturamento',
    'FaturamentoFrete',
    'ItemFaturamento',
)


def create_missing_faturamento_tables(apps, schema_editor):
    connection = schema_editor.connection
    existing = set(connection.introspection.table_names())

    for model_name in FATURAMENTO_MODELS:
        model = apps.get_model('empresa', model_name)
        table = model._meta.db_table
        if table in existing:
            continue
        schema_editor.create_model(model)
        existing.add(table)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('empresa', '0255_transportadora_suplemento_percentual'),
    ]

    operations = [
        migrations.RunPython(
            create_missing_faturamento_tables,
            noop_reverse,
        ),
    ]
