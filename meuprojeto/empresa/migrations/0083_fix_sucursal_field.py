# Generated manually to fix sucursal field name

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('empresa', '0082_fix_ordem_compra_field'),
    ]

    operations = [
        migrations.RunSQL(
            "ALTER TABLE empresa_ordemcompra RENAME COLUMN sucursal_id TO sucursal_destino_id;",
            reverse_sql="ALTER TABLE empresa_ordemcompra RENAME COLUMN sucursal_destino_id TO sucursal_id;"
        ),
    ]


