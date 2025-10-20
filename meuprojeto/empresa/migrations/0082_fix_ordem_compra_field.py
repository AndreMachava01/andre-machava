# Generated manually to fix field name mismatch

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('empresa', '0081_add_purchase_order_models'),
    ]

    operations = [
        migrations.RunSQL(
            "ALTER TABLE empresa_ordemcompra RENAME COLUMN requisicao_compra_id TO requisicao_origem_id;",
            reverse_sql="ALTER TABLE empresa_ordemcompra RENAME COLUMN requisicao_origem_id TO requisicao_compra_id;"
        ),
    ]


