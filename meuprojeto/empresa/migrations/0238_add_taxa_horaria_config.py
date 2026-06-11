# Generated manually to add taxa horária configuration

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('empresa', '0237_add_cliente_personalizado_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='propostatecnica',
            name='taxa_horaria_usada',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=10,
                null=True,
                help_text='Taxa horária utilizada no cálculo (MT/hora)'
            ),
        ),
    ]
