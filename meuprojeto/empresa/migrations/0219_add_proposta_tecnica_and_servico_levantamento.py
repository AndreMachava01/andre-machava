from django.db import migrations, models
import django.db.models.deletion
from decimal import Decimal


class Migration(migrations.Migration):

    dependencies = [
        ('empresa', '0218_add_rh_treinamento_origem'),
    ]

    operations = [
        migrations.CreateModel(
            name='PropostaTecnica',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('codigo', models.CharField(help_text='Código único da proposta técnica (ex: PT2026XXXX)', max_length=20, unique=True)),
                ('titulo', models.CharField(help_text='Título curto/resumo da proposta técnica', max_length=200)),
                ('escopo', models.TextField(blank=True, help_text='Descrição do escopo da proposta técnica', null=True)),
                ('data_solicitacao', models.DateTimeField(auto_now_add=True, help_text='Data em que a proposta foi registada no sistema')),
                ('data_inicio_prevista', models.DateField(blank=True, help_text='Data prevista para início do levantamento em campo', null=True)),
                ('data_fim_prevista', models.DateField(blank=True, help_text='Data prevista para conclusão da proposta técnica', null=True)),
                ('status', models.CharField(choices=[('DISPONIVEL', 'Disponível'), ('EM_ANDAMENTO', 'Em andamento'), ('ATRASADA', 'Atrasada'), ('CONCLUIDA', 'Concluída'), ('CANCELADA', 'Cancelada')], default='DISPONIVEL', help_text='Status geral da proposta técnica', max_length=20)),
                ('estagio_atual', models.CharField(choices=[('LEVANTAMENTO', '1. Levantamento'), ('ANALISE_TECNICA', '2. Análise técnica'), ('ELABORACAO_PROPOSTA', '3. Elaboração da proposta'), ('APRESENTACAO', '4. Apresentação'), ('AJUSTES_FINAIS', '5. Ajustes finais'), ('APROVACAO', '6. Aprovação')], default='LEVANTAMENTO', help_text='Estágio atual do fluxo da proposta técnica', max_length=30)),
                ('duracao_prevista_horas', models.DecimalField(blank=True, decimal_places=2, help_text='Duração prevista do levantamento em horas (para cálculo do valor)', max_digits=7, null=True)),
                ('valor_levantamento_previsto', models.DecimalField(blank=True, decimal_places=2, help_text='Valor previsto a cobrar pelo levantamento em campo (adiantamento)', max_digits=12, null=True)),
                ('data_conclusao', models.DateTimeField(blank=True, help_text='Data e hora de conclusão da proposta técnica', null=True)),
                ('observacoes', models.TextField(blank=True, help_text='Observações gerais sobre a proposta técnica', null=True)),
                ('cliente', models.ForeignKey(help_text='Cliente alvo da proposta técnica', on_delete=django.db.models.deletion.PROTECT, related_name='propostas_tecnicas', to='empresa.clienteservico')),
            ],
            options={
                'verbose_name': 'Proposta técnica',
                'verbose_name_plural': 'Propostas técnicas',
                'ordering': ['-data_solicitacao', 'codigo'],
            },
        ),
        migrations.AddField(
            model_name='configuracaofiscal',
            name='servico_levantamento',
            field=models.ForeignKey(blank=True, help_text='Serviço do catálogo utilizado para cobrar o levantamento técnico (preço/hora + IVA)', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='empresa.item'),
        ),
        migrations.AddField(
            model_name='propostatecnica',
            name='criado_por',
            field=models.ForeignKey(blank=True, help_text='Utilizador que registou a proposta', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='propostas_tecnicas_criadas', to='auth.user'),
        ),
        migrations.AddField(
            model_name='propostatecnica',
            name='orcamento_servico',
            field=models.ForeignKey(blank=True, help_text='Orçamento de serviço gerado a partir desta proposta (quando aprovado)', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='propostas_origem', to='empresa.ordemservico'),
        ),
        migrations.AddField(
            model_name='propostatecnica',
            name='responsavel',
            field=models.ForeignKey(blank=True, help_text='Responsável técnico pela proposta', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='propostas_tecnicas_responsavel', to='auth.user'),
        ),
        migrations.AddField(
            model_name='propostatecnica',
            name='sucursal',
            field=models.ForeignKey(blank=True, help_text='Sucursal responsável pela proposta técnica', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='propostas_tecnicas', to='empresa.sucursal'),
        ),
    ]

