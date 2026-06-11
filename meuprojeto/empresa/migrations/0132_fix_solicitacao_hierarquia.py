from django.db import migrations

CREATE_TABLE_SQL = r'''
CREATE TABLE IF NOT EXISTS empresa_solicitacaoalteracaohierarquia (
    id BIGSERIAL PRIMARY KEY,
    funcionario_id BIGINT NOT NULL,
    novo_chefe_id BIGINT NULL,
    motivo TEXT NOT NULL,
    status VARCHAR(10) NOT NULL DEFAULT 'ABERTO',
    criado_em TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    atualizado_em TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    solicitado_por_id INTEGER NOT NULL,
    aprovado_por_id INTEGER NULL,
    observacao_aprovacao TEXT NOT NULL DEFAULT ''
);
'''

CREATE_INDEXES_SQL = r'''
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = 'empresa_solic_hierarquia_funcionario_idx'
    ) THEN
        CREATE INDEX empresa_solic_hierarquia_funcionario_idx ON empresa_solicitacaoalteracaohierarquia(funcionario_id);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = 'empresa_solic_hierarquia_novo_chefe_idx'
    ) THEN
        CREATE INDEX empresa_solic_hierarquia_novo_chefe_idx ON empresa_solicitacaoalteracaohierarquia(novo_chefe_id);
    END IF;
END $$;
'''

CREATE_FKS_SQL = r'''
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'empresa_solic_hierarquia_funcionario_fk'
    ) THEN
        ALTER TABLE empresa_solicitacaoalteracaohierarquia
            ADD CONSTRAINT empresa_solic_hierarquia_funcionario_fk
            FOREIGN KEY (funcionario_id) REFERENCES empresa_funcionario(id) DEFERRABLE INITIALLY DEFERRED;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'empresa_solic_hierarquia_novo_chefe_fk'
    ) THEN
        ALTER TABLE empresa_solicitacaoalteracaohierarquia
            ADD CONSTRAINT empresa_solic_hierarquia_novo_chefe_fk
            FOREIGN KEY (novo_chefe_id) REFERENCES empresa_funcionario(id) DEFERRABLE INITIALLY DEFERRED;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'empresa_solic_hierarquia_solicitado_por_fk'
    ) THEN
        ALTER TABLE empresa_solicitacaoalteracaohierarquia
            ADD CONSTRAINT empresa_solic_hierarquia_solicitado_por_fk
            FOREIGN KEY (solicitado_por_id) REFERENCES auth_user(id) DEFERRABLE INITIALLY DEFERRED;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'empresa_solic_hierarquia_aprovado_por_fk'
    ) THEN
        ALTER TABLE empresa_solicitacaoalteracaohierarquia
            ADD CONSTRAINT empresa_solic_hierarquia_aprovado_por_fk
            FOREIGN KEY (aprovado_por_id) REFERENCES auth_user(id) DEFERRABLE INITIALLY DEFERRED;
    END IF;
END $$;
'''

class Migration(migrations.Migration):
    dependencies = [
        ('empresa', '0131_posicaohierarquica_funcionario_posicao'),
    ]

    operations = [
        migrations.RunSQL(CREATE_TABLE_SQL),
        migrations.RunSQL(CREATE_INDEXES_SQL),
        migrations.RunSQL(CREATE_FKS_SQL),
    ]


