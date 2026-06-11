# Adiciona campo codigo ao Fornecedor e preenche registos existentes

from django.db import migrations, models


def atribuir_codigos_fornecedores(apps, schema_editor):
    Fornecedor = apps.get_model('empresa', 'Fornecedor')
    for i, fornecedor in enumerate(Fornecedor.objects.order_by('id'), 1):
        fornecedor.codigo = f"FORN{i:04d}"
        fornecedor.save(update_fields=['codigo'])


def reverter_codigos_fornecedores(apps, schema_editor):
    Fornecedor = apps.get_model('empresa', 'Fornecedor')
    Fornecedor.objects.all().update(codigo='TEMP')


class Migration(migrations.Migration):

    dependencies = [
        ('empresa', '0242_fix_fornecedorproduto_item_fks'),
    ]

    operations = [
        migrations.AddField(
            model_name='fornecedor',
            name='codigo',
            field=models.CharField(
                default='TEMP',
                help_text='Código único do fornecedor',
                max_length=20,
            ),
        ),
        migrations.RunPython(atribuir_codigos_fornecedores, reverter_codigos_fornecedores),
        migrations.AlterField(
            model_name='fornecedor',
            name='codigo',
            field=models.CharField(
                help_text='Código único do fornecedor',
                max_length=20,
                unique=True,
            ),
        ),
    ]
