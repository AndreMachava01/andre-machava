# Generated manually

from django.db import migrations

def criar_tipos_presenca_padrao(apps, schema_editor):
    TipoPresenca = apps.get_model('empresa', 'TipoPresenca')
    
    tipos_presenca = [
        {
            'nome': 'Presente',
            'codigo': 'PR',
            'descricao': 'Funcionário presente no dia de trabalho',
            'desconta_salario': False,
            'cor': '#28a745',
            'ativo': True
        },
        {
            'nome': 'Ausente',
            'codigo': 'AU',
            'descricao': 'Funcionário ausente sem justificativa',
            'desconta_salario': True,
            'cor': '#dc3545',
            'ativo': True
        },
        {
            'nome': 'Falta Justificada',
            'codigo': 'FJ',
            'descricao': 'Falta com justificativa aceita',
            'desconta_salario': False,
            'cor': '#ffc107',
            'ativo': True
        },
        {
            'nome': 'Falta Injustificada',
            'codigo': 'FI',
            'descricao': 'Falta sem justificativa ou não aceita',
            'desconta_salario': True,
            'cor': '#dc3545',
            'ativo': True
        },
        {
            'nome': 'Licença',
            'codigo': 'LI',
            'descricao': 'Licença médica ou outros tipos de licença',
            'desconta_salario': False,
            'cor': '#17a2b8',
            'ativo': True
        },
        {
            'nome': 'Férias',
            'codigo': 'FE',
            'descricao': 'Período de férias',
            'desconta_salario': False,
            'cor': '#6f42c1',
            'ativo': True
        },
        {
            'nome': 'Suspensão',
            'codigo': 'SU',
            'descricao': 'Suspensão disciplinar',
            'desconta_salario': True,
            'cor': '#6c757d',
            'ativo': True
        },
        {
            'nome': 'Atraso',
            'codigo': 'AT',
            'descricao': 'Chegou atrasado mas trabalhou',
            'desconta_salario': False,
            'cor': '#fd7e14',
            'ativo': True
        },
        {
            'nome': 'Outro',
            'codigo': 'OU',
            'descricao': 'Outras situações não especificadas',
            'desconta_salario': False,
            'cor': '#6c757d',
            'ativo': True
        }
    ]
    
    for tipo_data in tipos_presenca:
        TipoPresenca.objects.get_or_create(
            codigo=tipo_data['codigo'],
            defaults=tipo_data
        )

def reverter_tipos_presenca_padrao(apps, schema_editor):
    TipoPresenca = apps.get_model('empresa', 'TipoPresenca')
    TipoPresenca.objects.filter(codigo__in=['PR', 'AU', 'FJ', 'FI', 'LI', 'FE', 'SU', 'AT', 'OU']).delete()

class Migration(migrations.Migration):

    dependencies = [
        ('empresa', '0025_remove_presenca_hora_entrada_and_more'),
    ]

    operations = [
        migrations.RunPython(criar_tipos_presenca_padrao, reverter_tipos_presenca_padrao),
    ]
