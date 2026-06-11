# Generated manually to fix foreign key constraint
# This fixes the issue where ItemReceita.material still references empresa_material instead of empresa_item

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('empresa', '0151_add_finalizada_status'),
    ]

    operations = [
        migrations.RunSQL(
            # Drop all foreign key constraints on material_id that point to empresa_material
            sql="""
                -- Find and drop all constraints pointing to empresa_material
                DO $$ 
                DECLARE
                    constraint_rec RECORD;
                BEGIN
                    FOR constraint_rec IN 
                        SELECT 
                            tc.constraint_name,
                            tc.table_name
                        FROM information_schema.table_constraints tc
                        JOIN information_schema.key_column_usage kcu 
                            ON tc.constraint_name = kcu.constraint_name
                        JOIN information_schema.constraint_column_usage ccu 
                            ON ccu.constraint_name = tc.constraint_name
                        WHERE tc.table_name = 'empresa_itemreceita'
                        AND kcu.column_name = 'material_id'
                        AND ccu.table_name = 'empresa_material'
                        AND tc.constraint_type = 'FOREIGN KEY'
                    LOOP
                        EXECUTE format('ALTER TABLE %I DROP CONSTRAINT IF EXISTS %I', 
                                     constraint_rec.table_name, 
                                     constraint_rec.constraint_name);
                    END LOOP;
                END $$;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
        
        migrations.RunSQL(
            # Add the correct foreign key constraint pointing to empresa_item
            sql="""
                -- Add foreign key constraint pointing to empresa_item if it doesn't exist
                DO $$ 
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 
                        FROM information_schema.table_constraints tc
                        JOIN information_schema.key_column_usage kcu 
                            ON tc.constraint_name = kcu.constraint_name
                        JOIN information_schema.constraint_column_usage ccu 
                            ON ccu.constraint_name = tc.constraint_name
                        WHERE tc.table_name = 'empresa_itemreceita'
                        AND kcu.column_name = 'material_id'
                        AND ccu.table_name = 'empresa_item'
                        AND tc.constraint_type = 'FOREIGN KEY'
                    ) THEN
                        ALTER TABLE empresa_itemreceita 
                        ADD CONSTRAINT empresa_itemreceita_material_id_fk_empresa_item 
                        FOREIGN KEY (material_id) 
                        REFERENCES empresa_item(id) 
                        ON DELETE CASCADE;
                    END IF;
                END $$;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]

