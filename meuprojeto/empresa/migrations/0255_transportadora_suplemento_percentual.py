from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('empresa', '0254_transportadora_tarifa_volume_m3'),
    ]

    operations = [
        migrations.AddField(
            model_name='transportadora',
            name='peso_kg_franquia',
            field=models.DecimalField(
                decimal_places=3,
                default=Decimal('25.000'),
                help_text='Peso em kg incluído sem taxa percentual de suplemento',
                max_digits=10,
            ),
        ),
        migrations.AddField(
            model_name='transportadora',
            name='percentual_suplemento_carga',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('0.00'),
                help_text='Percentagem aplicada sobre o frete base se volume ou peso exceder a franquia',
                max_digits=5,
            ),
        ),
        migrations.RemoveField(
            model_name='transportadora',
            name='custo_por_m3_acima_franquia',
        ),
    ]
