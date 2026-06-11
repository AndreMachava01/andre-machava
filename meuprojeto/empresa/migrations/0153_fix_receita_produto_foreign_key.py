# Generated manually to fix foreign key constraint
# This fixes the issue where Receita.produto still references empresa_produto instead of empresa_item

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('empresa', '0152_fix_itemreceita_foreign_key'),
    ]

    operations = [
        migrations.RunSQL(
            # Drop all foreign key constraints on produto_id that point to empresa_produto
            sql="""
                -- Find and drop all constraints pointing to empresa_produto
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
                        WHERE tc.table_name = 'empresa_receita'
                        AND kcu.column_name = 'produto_id'
                        AND ccu.table_name = 'empresa_produto'
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
                        WHERE tc.table_name = 'empresa_receita'
                        AND kcu.column_name = 'produto_id'
                        AND ccu.table_name = 'empresa_item'
                        AND tc.constraint_type = 'FOREIGN KEY'
                    ) THEN
                        ALTER TABLE empresa_receita 
                        ADD CONSTRAINT empresa_receita_produto_id_fk_empresa_item 
                        FOREIGN KEY (produto_id) 
                        REFERENCES empresa_item(id) 
                        ON DELETE CASCADE;
                    END IF;
                END $$;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]

