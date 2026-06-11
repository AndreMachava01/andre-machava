import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('empresa', '0257_seed_cost_billing_catalog'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SolicitacaoFerias',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('data_inicio', models.DateField()),
                ('data_fim', models.DateField()),
                ('dias_solicitados', models.PositiveIntegerField(default=0)),
                ('motivo', models.TextField(blank=True, default='')),
                ('status', models.CharField(
                    choices=[
                        ('PENDENTE', 'Pendente'),
                        ('APROVADO', 'Aprovado'),
                        ('REJEITADO', 'Rejeitado'),
                        ('CANCELADO', 'Cancelado'),
                    ],
                    default='PENDENTE',
                    max_length=12,
                )),
                ('observacao_aprovacao', models.TextField(blank=True, default='')),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                ('aprovado_por', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='solicitacoes_ferias_aprovadas',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('funcionario', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='solicitacoes_ferias',
                    to='empresa.funcionario',
                )),
                ('solicitado_por', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='solicitacoes_ferias_criadas',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Solicitação de Férias',
                'verbose_name_plural': 'Solicitações de Férias',
                'ordering': ['-criado_em'],
            },
        ),
    ]
