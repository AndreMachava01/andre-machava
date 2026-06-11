from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('empresa', '0253_restaurar_trfreq_ligadas'),
    ]

    operations = [
        migrations.AddField(
            model_name='transportadora',
            name='volume_m3_franquia',
            field=models.DecimalField(
                decimal_places=3,
                default=Decimal('1.000'),
                help_text='Volume em m³ incluído no preço base (sem custo extra por m³)',
                max_digits=8,
            ),
        ),
        migrations.AddField(
            model_name='transportadora',
            name='custo_por_m3_acima_franquia',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('0.00'),
                help_text='Custo adicional em MT por cada m³ acima do volume incluído',
                max_digits=10,
            ),
        ),
    ]
