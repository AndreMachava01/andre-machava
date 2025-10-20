# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('empresa', '0039_promocao'),
    ]

    operations = [
        migrations.AddField(
            model_name='funcionariofolha',
            name='desconto_faltas',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name='Desconto por Faltas'),
        ),
    ]