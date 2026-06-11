# Generated manually to fix sucursal field name

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('empresa', '0082_fix_ordem_compra_field'),
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
                      AND column_name = 'sucursal_id'
                ) THEN
                    ALTER TABLE empresa_ordemcompra
                    RENAME COLUMN sucursal_id TO sucursal_destino_id;
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
                      AND column_name = 'sucursal_destino_id'
                ) AND NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = current_schema()
                      AND table_name = 'empresa_ordemcompra'
                      AND column_name = 'sucursal_id'
                ) THEN
                    ALTER TABLE empresa_ordemcompra
                    RENAME COLUMN sucursal_destino_id TO sucursal_id;
                END IF;
            END $$;
            """,
        ),
    ]
