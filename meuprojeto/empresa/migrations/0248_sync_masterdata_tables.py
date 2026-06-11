"""
Cria tabelas de masterdata quando a migração 0126 foi marcada como aplicada
mas as tabelas não existem na base de dados.
"""
from django.db import migrations


MASTERDATA_MODELS = (
    'Regiao',
    'ZonaEntregaMasterdata',
    'HubLogistico',
    'CatalogoDimensoes',
    'RestricaoLogistica',
    'PermissaoLogistica',
    'ConfiguracaoMasterdata',
    'LogMasterdata',
)


def create_missing_masterdata_tables(apps, schema_editor):
    connection = schema_editor.connection
    existing = set(connection.introspection.table_names())

    for model_name in MASTERDATA_MODELS:
        model = apps.get_model('empresa', model_name)
        table = model._meta.db_table
        if table in existing:
            continue
        schema_editor.create_model(model)
        existing.add(table)
        for m2m in model._meta.many_to_many:
            through_table = m2m.remote_field.through._meta.db_table
            existing.add(through_table)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('empresa', '0247_sync_observability_tables'),
    ]

    operations = [
        migrations.RunPython(
            create_missing_masterdata_tables,
            noop_reverse,
        ),
    ]
