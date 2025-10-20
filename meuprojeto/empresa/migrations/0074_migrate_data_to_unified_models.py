# Generated manually for data migration

from django.db import migrations
from decimal import Decimal


def migrate_produtos_to_items(apps, schema_editor):
    """Migra produtos existentes para o modelo Item unificado"""
    Produto = apps.get_model('empresa', 'Produto')
    Item = apps.get_model('empresa', 'Item')
    CategoriaProduto = apps.get_model('empresa', 'CategoriaProduto')
    
    print("Iniciando migração de produtos para Item unificado...")
    
    # Buscar categoria padrão ou criar uma
    categoria_padrao, created = CategoriaProduto.objects.get_or_create(
        nome='Migração Automática',
        defaults={
            'tipo': 'PRODUTO',
            'ativa': True,
            'descricao': 'Categoria criada automaticamente durante migração'
        }
    )
    
    produtos_migrados = 0
    for produto in Produto.objects.all():
        try:
            # Criar Item baseado no Produto
            item = Item.objects.create(
                tipo='PRODUTO',
                nome=produto.nome,
                codigo=produto.codigo,
                codigo_barras=produto.codigo_barras,
                descricao=produto.descricao,
                categoria=produto.categoria or categoria_padrao,
                unidade_medida=produto.unidade_medida,
                preco_custo=produto.preco_custo,
                estoque_minimo=produto.estoque_minimo,
                estoque_maximo=produto.estoque_maximo,
                status=produto.status,
                data_cadastro=produto.data_cadastro,
                data_atualizacao=produto.data_atualizacao,
                observacoes=produto.observacoes,
                produto_tipo=produto.tipo,
                preco_venda=produto.preco_venda,
                margem_lucro=produto.margem_lucro,
                fornecedor_principal=produto.fornecedor_principal
            )
            produtos_migrados += 1
            print(f"Produto migrado: {produto.nome} -> Item ID {item.id}")
            
        except Exception as e:
            print(f"Erro ao migrar produto {produto.nome}: {e}")
    
    print(f"Migração de produtos concluída: {produtos_migrados} produtos migrados")


def migrate_materiais_to_items(apps, schema_editor):
    """Migra materiais existentes para o modelo Item unificado"""
    Material = apps.get_model('empresa', 'Material')
    Item = apps.get_model('empresa', 'Item')
    CategoriaProduto = apps.get_model('empresa', 'CategoriaProduto')
    
    print("Iniciando migração de materiais para Item unificado...")
    
    # Buscar categoria padrão ou criar uma
    categoria_padrao, created = CategoriaProduto.objects.get_or_create(
        nome='Migração Automática',
        defaults={
            'tipo': 'MATERIAL',
            'ativa': True,
            'descricao': 'Categoria criada automaticamente durante migração'
        }
    )
    
    materiais_migrados = 0
    for material in Material.objects.all():
        try:
            # Criar Item baseado no Material
            item = Item.objects.create(
                tipo='MATERIAL',
                nome=material.nome,
                codigo=material.codigo,
                codigo_barras=material.codigo_barras,
                descricao=material.descricao,
                categoria=material.categoria or categoria_padrao,
                unidade_medida=material.unidade_medida,
                preco_custo=material.preco_custo,
                estoque_minimo=material.estoque_minimo,
                estoque_maximo=material.estoque_maximo,
                status=material.status,
                data_cadastro=material.data_cadastro,
                data_atualizacao=material.data_atualizacao,
                observacoes=material.observacoes,
                material_tipo=material.tipo,
                fornecedor_principal=material.fornecedor_principal
            )
            materiais_migrados += 1
            print(f"Material migrado: {material.nome} -> Item ID {item.id}")
            
        except Exception as e:
            print(f"Erro ao migrar material {material.nome}: {e}")
    
    print(f"Migração de materiais concluída: {materiais_migrados} materiais migrados")


def migrate_movimentos_to_unified(apps, schema_editor):
    """Migra movimentações existentes para o modelo MovimentoItem unificado"""
    MovimentoStock = apps.get_model('empresa', 'MovimentoStock')
    MovimentoMaterial = apps.get_model('empresa', 'MovimentoMaterial')
    MovimentoItem = apps.get_model('empresa', 'MovimentoItem')
    Item = apps.get_model('empresa', 'Item')
    
    print("Iniciando migração de movimentações para MovimentoItem unificado...")
    
    movimentos_migrados = 0
    
    # Migrar movimentações de produtos
    for movimento in MovimentoStock.objects.all():
        try:
            # Buscar o Item correspondente ao produto
            item = Item.objects.filter(
                tipo='PRODUTO',
                codigo=movimento.produto.codigo
            ).first()
            
            if item:
                movimento_item = MovimentoItem.objects.create(
                    codigo=movimento.codigo,
                    item=item,
                    sucursal=movimento.sucursal,
                    tipo_movimento=movimento.tipo_movimento,
                    quantidade=movimento.quantidade,
                    preco_unitario=movimento.preco_unitario,
                    valor_total=movimento.valor_total,
                    data_movimento=movimento.data_movimento,
                    referencia=movimento.referencia,
                    observacoes=movimento.observacoes,
                    usuario=movimento.usuario
                )
                movimentos_migrados += 1
                print(f"Movimento de produto migrado: {movimento.codigo} -> MovimentoItem ID {movimento_item.id}")
            else:
                print(f"Item não encontrado para produto: {movimento.produto.nome}")
                
        except Exception as e:
            print(f"Erro ao migrar movimento de produto {movimento.codigo}: {e}")
    
    # Migrar movimentações de materiais
    for movimento in MovimentoMaterial.objects.all():
        try:
            # Buscar o Item correspondente ao material
            item = Item.objects.filter(
                tipo='MATERIAL',
                codigo=movimento.material.codigo
            ).first()
            
            if item:
                movimento_item = MovimentoItem.objects.create(
                    codigo=movimento.codigo,
                    item=item,
                    sucursal=movimento.sucursal,
                    tipo_movimento=movimento.tipo_movimento,
                    quantidade=movimento.quantidade,
                    preco_unitario=movimento.preco_unitario,
                    valor_total=movimento.valor_total,
                    data_movimento=movimento.data_movimento,
                    referencia=movimento.referencia,
                    observacoes=movimento.observacoes,
                    usuario=movimento.usuario
                )
                movimentos_migrados += 1
                print(f"Movimento de material migrado: {movimento.codigo} -> MovimentoItem ID {movimento_item.id}")
            else:
                print(f"Item não encontrado para material: {movimento.material.nome}")
                
        except Exception as e:
            print(f"Erro ao migrar movimento de material {movimento.codigo}: {e}")
    
    print(f"Migração de movimentações concluída: {movimentos_migrados} movimentações migradas")


def migrate_stock_to_unified(apps, schema_editor):
    """Migra estoques existentes para o modelo StockItem unificado"""
    StockSucursal = apps.get_model('empresa', 'StockSucursal')
    StockMaterial = apps.get_model('empresa', 'StockMaterial')
    StockItem = apps.get_model('empresa', 'StockItem')
    Item = apps.get_model('empresa', 'Item')
    
    print("Iniciando migração de estoques para StockItem unificado...")
    
    stocks_migrados = 0
    
    # Migrar estoques de produtos
    for stock in StockSucursal.objects.all():
        try:
            # Buscar o Item correspondente ao produto
            item = Item.objects.filter(
                tipo='PRODUTO',
                codigo=stock.produto.codigo
            ).first()
            
            if item:
                stock_item = StockItem.objects.create(
                    item=item,
                    sucursal=stock.sucursal,
                    quantidade_atual=stock.quantidade_atual,
                    quantidade_reservada=stock.quantidade_reservada,
                    localizacao=stock.localizacao,
                    data_atualizacao=stock.data_atualizacao
                )
                stocks_migrados += 1
                print(f"Estoque de produto migrado: {stock.produto.nome} em {stock.sucursal.nome}")
            else:
                print(f"Item não encontrado para produto: {stock.produto.nome}")
                
        except Exception as e:
            print(f"Erro ao migrar estoque de produto {stock.produto.nome}: {e}")
    
    # Migrar estoques de materiais
    for stock in StockMaterial.objects.all():
        try:
            # Buscar o Item correspondente ao material
            item = Item.objects.filter(
                tipo='MATERIAL',
                codigo=stock.material.codigo
            ).first()
            
            if item:
                stock_item = StockItem.objects.create(
                    item=item,
                    sucursal=stock.sucursal,
                    quantidade_atual=stock.quantidade_atual,
                    quantidade_reservada=stock.quantidade_reservada,
                    localizacao=stock.localizacao,
                    data_atualizacao=stock.data_atualizacao
                )
                stocks_migrados += 1
                print(f"Estoque de material migrado: {stock.material.nome} em {stock.sucursal.nome}")
            else:
                print(f"Item não encontrado para material: {stock.material.nome}")
                
        except Exception as e:
            print(f"Erro ao migrar estoque de material {stock.material.nome}: {e}")
    
    print(f"Migração de estoques concluída: {stocks_migrados} estoques migrados")


def reverse_migration(apps, schema_editor):
    """Reverte a migração (não implementado por segurança)"""
    print("Reversão da migração não implementada por segurança dos dados")


class Migration(migrations.Migration):

    dependencies = [
        ('empresa', '0073_add_unified_models'),
    ]

    operations = [
        migrations.RunPython(
            migrate_produtos_to_items,
            reverse_migration,
        ),
        migrations.RunPython(
            migrate_materiais_to_items,
            reverse_migration,
        ),
        migrations.RunPython(
            migrate_movimentos_to_unified,
            reverse_migration,
        ),
        migrations.RunPython(
            migrate_stock_to_unified,
            reverse_migration,
        ),
    ]



