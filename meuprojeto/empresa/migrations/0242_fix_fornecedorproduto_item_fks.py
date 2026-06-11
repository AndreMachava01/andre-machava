# Corrige FKs de FornecedorProduto que ainda apontam para empresa_produto/empresa_material
# em vez de empresa_item (schema desalinhado após migração 0085).

from django.db import migrations


def _legacy_table_exists(cursor, table_name):
    cursor.execute(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = current_schema()
              AND table_name = %s
        )
        """,
        [table_name],
    )
    return cursor.fetchone()[0]


def remap_fornecedorproduto_ids(apps, schema_editor):
    """Re-mapeia IDs legados para empresa_item antes de trocar as FKs."""
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        if not _legacy_table_exists(cursor, 'empresa_produto'):
            return
        cursor.execute(
            """
            UPDATE empresa_fornecedorproduto fp
            SET produto_id = sub.new_id
            FROM (
                SELECT fp2.id, i.id AS new_id
                FROM empresa_fornecedorproduto fp2
                INNER JOIN empresa_produto ep ON ep.id = fp2.produto_id
                INNER JOIN empresa_item i ON i.tipo = 'PRODUTO'
                    AND TRIM(LOWER(i.nome)) = TRIM(LOWER(ep.nome))
            ) sub
            WHERE fp.id = sub.id AND fp.produto_id IS NOT NULL
            """
        )
        cursor.execute(
            """
            UPDATE empresa_fornecedorproduto fp
            SET material_id = sub.new_id
            FROM (
                SELECT fp2.id, i.id AS new_id
                FROM empresa_fornecedorproduto fp2
                INNER JOIN empresa_material em ON em.id = fp2.material_id
                INNER JOIN empresa_item i ON i.tipo = 'MATERIAL'
                    AND TRIM(LOWER(i.nome)) = TRIM(LOWER(em.nome))
            ) sub
            WHERE fp.id = sub.id AND fp.material_id IS NOT NULL
            """
        )


class Migration(migrations.Migration):

    dependencies = [
        ('empresa', '0241_add_publicacao_investimento_marketing'),
    ]

    operations = [
        migrations.RunPython(remap_fornecedorproduto_ids, migrations.RunPython.noop),
        migrations.RunSQL(
            sql=[
                """
                ALTER TABLE empresa_fornecedorproduto
                DROP CONSTRAINT IF EXISTS empresa_fornecedorpr_produto_id_a0784b65_fk_empresa_p;
                """,
                """
                ALTER TABLE empresa_fornecedorproduto
                DROP CONSTRAINT IF EXISTS empresa_fornecedorpr_material_id_79cf2c8a_fk_empresa_m;
                """,
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conname = 'empresa_fornecedorproduto_produto_id_fk_item'
                    ) THEN
                        ALTER TABLE empresa_fornecedorproduto
                        ADD CONSTRAINT empresa_fornecedorproduto_produto_id_fk_item
                        FOREIGN KEY (produto_id) REFERENCES empresa_item(id)
                        DEFERRABLE INITIALLY DEFERRED;
                    END IF;
                END $$;
                """,
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conname = 'empresa_fornecedorproduto_material_id_fk_item'
                    ) THEN
                        ALTER TABLE empresa_fornecedorproduto
                        ADD CONSTRAINT empresa_fornecedorproduto_material_id_fk_item
                        FOREIGN KEY (material_id) REFERENCES empresa_item(id)
                        DEFERRABLE INITIALLY DEFERRED;
                    END IF;
                END $$;
                """,
            ],
            reverse_sql=[
                """
                ALTER TABLE empresa_fornecedorproduto
                DROP CONSTRAINT IF EXISTS empresa_fornecedorproduto_material_id_fk_item;
                """,
                """
                ALTER TABLE empresa_fornecedorproduto
                DROP CONSTRAINT IF EXISTS empresa_fornecedorproduto_produto_id_fk_item;
                """,
            ],
        ),
    ]
