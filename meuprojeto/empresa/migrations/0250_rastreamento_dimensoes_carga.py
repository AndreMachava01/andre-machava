from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('empresa', '0249_logistica_frete_distancia'),
    ]

    operations = [
        migrations.AddField(
            model_name='rastreamentoentrega',
            name='altura_cm',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Altura do volume em cm',
                max_digits=8,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='rastreamentoentrega',
            name='comprimento_cm',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Comprimento do volume em cm',
                max_digits=8,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='rastreamentoentrega',
            name='largura_cm',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Largura do volume em cm',
                max_digits=8,
                null=True,
            ),
        ),
    ]
