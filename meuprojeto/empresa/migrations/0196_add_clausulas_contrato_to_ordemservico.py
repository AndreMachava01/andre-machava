# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('empresa', '0195_formapagamento_alter_ordemservico_forma_pagamento_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='ordemservico',
            name='clausula4_obrigacoes',
            field=models.TextField(blank=True, null=True, help_text='Cláusula 4 - Obrigações das Partes (editável pelo utilizador)'),
        ),
        migrations.AddField(
            model_name='ordemservico',
            name='clausula5_garantia',
            field=models.TextField(blank=True, null=True, help_text='Cláusula 5 - Garantia (editável pelo utilizador, pode usar {{ validade_garantia_dias }})'),
        ),
        migrations.AddField(
            model_name='ordemservico',
            name='clausula6_alteracoes',
            field=models.TextField(blank=True, null=True, help_text='Cláusula 6 - Alterações do Contrato (editável pelo utilizador)'),
        ),
        migrations.AddField(
            model_name='ordemservico',
            name='clausula7_rescisao',
            field=models.TextField(blank=True, null=True, help_text='Cláusula 7 - Rescisão (editável pelo utilizador)'),
        ),
        migrations.AddField(
            model_name='ordemservico',
            name='clausula8_confidencialidade',
            field=models.TextField(blank=True, null=True, help_text='Cláusula 8 - Confidencialidade (editável pelo utilizador)'),
        ),
        migrations.AddField(
            model_name='ordemservico',
            name='clausula9_foro',
            field=models.TextField(blank=True, null=True, help_text='Cláusula 9 - Legislação e Foro (editável pelo utilizador)'),
        ),
    ]
