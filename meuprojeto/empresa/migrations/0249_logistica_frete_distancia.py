from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('empresa', '0248_sync_masterdata_tables'),
    ]

    operations = [
        migrations.AddField(
            model_name='transportadora',
            name='custo_por_km',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('0.00'),
                help_text='Custo por quilômetro em MT',
                max_digits=10,
            ),
        ),
        migrations.AddField(
            model_name='rastreamentoentrega',
            name='distancia_km',
            field=models.DecimalField(
                blank=True,
                decimal_places=3,
                help_text='Distância calculada origem→destino em km',
                max_digits=10,
                null=True,
            ),
        ),
    ]
