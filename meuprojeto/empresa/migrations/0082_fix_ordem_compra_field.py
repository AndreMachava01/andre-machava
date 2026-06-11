# Generated manually to fix field name mismatch

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('empresa', '0081_add_purchase_order_models'),
    ]

    operations = [
        migrations.RunSQL(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = current_schema()
                      AND table_name = 'empresa_ordemcompra'
                      AND column_name = 'requisicao_compra_id'
                ) THEN
                    ALTER TABLE empresa_ordemcompra
                    RENAME COLUMN requisicao_compra_id TO requisicao_origem_id;
                END IF;
            END $$;
            """,
            reverse_sql="""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = current_schema()
                      AND table_name = 'empresa_ordemcompra'
                      AND column_name = 'requisicao_origem_id'
                ) AND NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = current_schema()
                      AND table_name = 'empresa_ordemcompra'
                      AND column_name = 'requisicao_compra_id'
                ) THEN
                    ALTER TABLE empresa_ordemcompra
                    RENAME COLUMN requisicao_origem_id TO requisicao_compra_id;
                END IF;
            END $$;
            """,
        ),
    ]
