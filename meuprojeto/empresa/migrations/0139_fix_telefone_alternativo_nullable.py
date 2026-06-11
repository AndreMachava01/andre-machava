# Generated manually to fix telefone_alternativo NOT NULL constraint

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('empresa', '0138_add_numero_contribuinte_inss'),
    ]

    operations = [
        migrations.AlterField(
            model_name='funcionario',
            name='telefone_alternativo',
            field=models.CharField(blank=True, help_text='Telefone alternativo', max_length=13, null=True),
        ),
    ]

