# Migração de dados: plano de contas PGC-NIRF MZ (Decreto 70/2009)
# Classes 1-4 (Activo, Passivo, Património) e grupos 6 e 7 (Gastos, Receitas)

from django.db import migrations


def seed_plano_pgc_nirf(apps, schema_editor):
    Conta = apps.get_model('empresa', 'Conta')
    # (codigo, nome, tipo, ordem) — grupos de 2 dígitos primeiro
    grupos = [
        ('11', 'Imobilizações corpóreas', 'ATIVO', 110),
        ('21', 'Inventários', 'ATIVO', 210),
        ('22', 'Clientes e outros devedores', 'ATIVO', 220),
        ('26', 'Caixa e depósitos bancários', 'ATIVO', 260),
        ('31', 'Passivo não corrente', 'PASSIVO', 310),
        ('32', 'Fornecedores e outros credores', 'PASSIVO', 320),
        ('33', 'Estado e outros credores', 'PASSIVO', 330),
        ('41', 'Capital subscrito', 'PATRIMONIO', 410),
        ('42', 'Reservas', 'PATRIMONIO', 420),
        ('43', 'Resultados transitados', 'PATRIMONIO', 430),
        ('61', 'Gastos com compras e aprovisionamentos', 'DESPESA', 610),
        ('62', 'Gastos com pessoal', 'DESPESA', 620),
        ('63', 'Outros gastos operacionais', 'DESPESA', 630),
        ('71', 'Vendas', 'RECEITA', 710),
        ('72', 'Prestações de serviços', 'RECEITA', 720),
    ]
    pais = {}
    for codigo, nome, tipo, ordem in grupos:
        obj, _ = Conta.objects.get_or_create(
            codigo=codigo,
            defaults={'nome': nome, 'tipo': tipo, 'ordem': ordem, 'ativo': True},
        )
        if obj.nome != nome or obj.tipo != tipo:
            obj.nome = nome
            obj.tipo = tipo
            obj.ordem = ordem
            obj.save(update_fields=['nome', 'tipo', 'ordem'])
        pais[codigo] = obj

    # Subcontas já usadas no sistema (61.01, 62.01, 63.01, 71.01, 72.01) — ligar ao pai
    subcontas = [
        ('61.01', 'Compras', 'DESPESA', '61', 611),
        ('62.01', 'Pessoal (folha)', 'DESPESA', '62', 621),
        ('63.01', 'Custos Logística', 'DESPESA', '63', 631),
        ('71.01', 'Receitas de Vendas', 'RECEITA', '71', 711),
        ('72.01', 'Receitas Logística (faturamento)', 'RECEITA', '72', 721),
    ]
    for codigo, nome, tipo, codigo_pai, ordem in subcontas:
        pai = pais.get(codigo_pai)
        obj, created = Conta.objects.get_or_create(
            codigo=codigo,
            defaults={
                'nome': nome,
                'tipo': tipo,
                'ordem': ordem,
                'ativo': True,
                'conta_pai': pai,
            },
        )
        if not created:
            if obj.conta_pai_id != (pai.id if pai else None):
                obj.conta_pai = pai
                obj.save(update_fields=['conta_pai'])
            if obj.nome != nome or obj.tipo != tipo:
                obj.nome = nome
                obj.tipo = tipo
                obj.ordem = ordem
                obj.save(update_fields=['nome', 'tipo', 'ordem'])


def reverse_seed(apps, schema_editor):
    """Remove apenas contas de grupo das classes 1-4 (11, 21, 22, 26, 31, 32, 33, 41, 42, 43).
    Não remove 61, 62, 63, 71, 72 nem 61.01, 62.01, etc., para não quebrar lançamentos existentes.
    """
    Conta = apps.get_model('empresa', 'Conta')
    grupos_reversiveis = ['11', '21', '22', '26', '31', '32', '33', '41', '42', '43']
    for codigo in grupos_reversiveis:
        Conta.objects.filter(codigo=codigo).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('empresa', '0213_add_acesso_financas_permission'),
    ]

    operations = [
        migrations.RunPython(seed_plano_pgc_nirf, reverse_seed),
    ]
