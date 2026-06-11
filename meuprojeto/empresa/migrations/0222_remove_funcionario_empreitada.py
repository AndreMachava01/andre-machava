# Generated manually - Remove funcionario and incluir_na_folha from TrabalhoEmpreitada

from django.db import migrations, models
import django.db.models.deletion


def migrar_funcionarios_para_prestadores(apps, schema_editor):
    """Para cada empreitada com funcionario, cria PrestadorServico e associa."""
    TrabalhoEmpreitada = apps.get_model('empresa', 'TrabalhoEmpreitada')
    PrestadorServico = apps.get_model('empresa', 'PrestadorServico')
    Funcionario = apps.get_model('empresa', 'Funcionario')

    for trabalho in TrabalhoEmpreitada.objects.filter(funcionario_id__isnull=False, prestador_id__isnull=True).select_related('funcionario'):
        try:
            funcionario = trabalho.funcionario
            prestador, _ = PrestadorServico.objects.get_or_create(
                nome=funcionario.nome_completo[:200],
                tipo='SINGULAR',
                defaults={'ativo': True}
            )
            trabalho.prestador = prestador
            trabalho.save()
        except Exception:
            pass  # Se falhar, o trabalho ficará sem prestador - será tratado manualmente


def reverse_migrar(apps, schema_editor):
    pass  # Não reversível


class Migration(migrations.Migration):

    dependencies = [
        ('empresa', '0221_add_prestador_servico'),
    ]

    operations = [
        migrations.RunPython(migrar_funcionarios_para_prestadores, reverse_migrar),
        migrations.RemoveField(
            model_name='trabalhoempreitada',
            name='funcionario',
        ),
        migrations.RemoveField(
            model_name='trabalhoempreitada',
            name='incluir_na_folha',
        ),
        migrations.AlterField(
            model_name='trabalhoempreitada',
            name='prestador',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='trabalhos_empreitada',
                to='empresa.prestadorservico',
                verbose_name='Prestador de Serviços'
            ),
        ),
    ]
