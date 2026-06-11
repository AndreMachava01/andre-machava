"""
Cria tabelas de custos/faturamento logístico quando a migração 0126 foi
marcada como aplicada mas as tabelas não existem na base de dados.
"""
from django.db import migrations


COST_BILLING_MODELS = (
    'TipoCusto',
    'CentroCusto',
    'CustoLogistico',
    'RateioCusto',
)


def create_missing_cost_billing_tables(apps, schema_editor):
    connection = schema_editor.connection
    existing = set(connection.introspection.table_names())

    for model_name in COST_BILLING_MODELS:
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
        ('empresa', '0245_sync_notificacao_receptor_campos'),
    ]

    operations = [
        migrations.RunPython(
            create_missing_cost_billing_tables,
            noop_reverse,
        ),
    ]
