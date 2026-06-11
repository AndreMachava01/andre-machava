"""Catálogo inicial de tipos e centros de custo logístico."""
from django.db import migrations


def seed_cost_billing_catalog(apps, schema_editor):
    TipoCusto = apps.get_model('empresa', 'TipoCusto')
    CentroCusto = apps.get_model('empresa', 'CentroCusto')

    if not TipoCusto.objects.exists():
        tipos = (
            ('FRETE', 'Frete', 'FRETE', 'Custos de transporte e entrega'),
            ('COMB', 'Combustível', 'COMBUSTIVEL', 'Abastecimento de frota'),
            ('MANUT', 'Manutenção', 'MANUTENCAO', 'Manutenção de veículos'),
            ('PED', 'Pedágio', 'PEDAGIO', 'Taxas de estrada'),
            ('SEG', 'Seguro', 'SEGURO', 'Seguros logísticos'),
            ('MULTA', 'Multa', 'MULTA', 'Multas e penalidades'),
            ('OUT', 'Outros', 'OUTROS', 'Despesas diversas'),
        )
        for codigo, nome, categoria, descricao in tipos:
            TipoCusto.objects.get_or_create(
                codigo=codigo,
                defaults={
                    'nome': nome,
                    'categoria': categoria,
                    'descricao': descricao,
                    'ativo': True,
                },
            )

    if not CentroCusto.objects.exists():
        centros = (
            ('LOG', 'Logística Geral', 'DEPARTAMENTO', 'Centro principal de logística'),
            ('TRANS', 'Transporte', 'DEPARTAMENTO', 'Operações de transporte'),
            ('ENT', 'Entregas', 'DEPARTAMENTO', 'Custos de última milha'),
            ('REG-SUL', 'Regional Sul', 'REGIONAL', 'Operações na região sul'),
        )
        for codigo, nome, tipo, descricao in centros:
            CentroCusto.objects.get_or_create(
                codigo=codigo,
                defaults={
                    'nome': nome,
                    'tipo': tipo,
                    'descricao': descricao,
                    'ativo': True,
                },
            )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('empresa', '0256_sync_faturamento_tables'),
    ]

    operations = [
        migrations.RunPython(seed_cost_billing_catalog, noop_reverse),
    ]
