# Generated manually to add cliente personalizado fields to PropostaTecnica

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('empresa', '0236_add_cliente_personalizado_fields_proposta_tecnica'),
    ]

    operations = [
        migrations.AddField(
            model_name='propostatecnica',
            name='nome_cliente_personalizado',
            field=models.CharField(
                blank=True, 
                max_length=200, 
                null=True, 
                help_text='Nome do cliente personalizado (usado quando não há cliente cadastrado)'
            ),
        ),
        migrations.AddField(
            model_name='propostatecnica',
            name='nuit_cliente_personalizado',
            field=models.CharField(
                blank=True, 
                max_length=20, 
                null=True, 
                help_text='NUIT do cliente personalizado'
            ),
        ),
        migrations.AddField(
            model_name='propostatecnica',
            name='telefone_cliente_personalizado',
            field=models.CharField(
                blank=True, 
                max_length=20, 
                null=True, 
                help_text='Telefone/Contato do cliente personalizado'
            ),
        ),
        # Tornar o campo cliente opcional
        migrations.AlterField(
            model_name='propostatecnica',
            name='cliente',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.PROTECT,
                related_name='propostas_tecnicas',
                to='empresa.clienteservico',
                help_text='Cliente alvo da proposta técnica (opcional - pode usar nome personalizado)'
            ),
        ),
    ]
