# Generated manually to create taxas por categoria model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('empresa', '0238_add_taxa_horaria_config'),
    ]

    operations = [
        migrations.CreateModel(
            name='TaxaServicoCategoria',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('categoria', models.CharField(choices=[('OP', 'Operacional'), ('ADM', 'Administrativo'), ('TEC', 'Técnico'), ('GES', 'Gestão'), ('EXE', 'Executivo')], max_length=3, unique=True, help_text='Categoria profissional')),
                ('taxa_horaria', models.DecimalField(decimal_places=2, default=500, help_text='Taxa horária para levantamento (MT/hora)', max_digits=10)),
                ('descricao', models.CharField(blank=True, help_text='Descrição da categoria', max_length=100)),
                ('ativo', models.BooleanField(default=True, help_text='Se marcado, esta taxa pode ser usada nos cálculos')),
                ('data_criacao', models.DateTimeField(auto_now_add=True, help_text='Data de criação')),
                ('data_atualizacao', models.DateTimeField(auto_now=True, help_text='Data de última atualização')),
            ],
            options={
                'verbose_name': 'Taxa de Serviço por Categoria',
                'verbose_name_plural': 'Taxas de Serviço por Categoria',
                'ordering': ['categoria'],
            },
        ),
    ]
