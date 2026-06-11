# Generated migration to update existing codes to new format

from django.db import migrations
import re


def migrar_codigos_requisicoes(apps, schema_editor):
    """Migra códigos de RequisicaoCompraExterna de COMP#### para RQCOMP####"""
    RequisicaoCompraExterna = apps.get_model('empresa', 'RequisicaoCompraExterna')
    
    # Buscar todas as requisições com código no formato antigo COMP####
    requisicoes = RequisicaoCompraExterna.objects.filter(
        codigo__regex=r'^COMP\d{4}$'
    )
    
    for requisicao in requisicoes:
        # Extrair o número do código antigo
        match = re.match(r'^COMP(\d{4})$', requisicao.codigo)
        if match:
            numero = match.group(1)
            novo_codigo = f"RQCOMP{numero}"
            
            # Verificar se o novo código já existe
            if not RequisicaoCompraExterna.objects.filter(codigo=novo_codigo).exclude(id=requisicao.id).exists():
                requisicao.codigo = novo_codigo
                requisicao.save()
                print(f"[OK] Requisicao {requisicao.id} atualizada: COMP{numero} -> {novo_codigo}")
            else:
                print(f"[AVISO] Requisicao {requisicao.id} nao atualizada: {novo_codigo} ja existe")


def migrar_codigos_ordens(apps, schema_editor):
    """Migra códigos de OrdemCompra de COMP#### para ORDCOMP####"""
    OrdemCompra = apps.get_model('empresa', 'OrdemCompra')
    
    # Buscar todas as ordens com código no formato antigo COMP####
    ordens = OrdemCompra.objects.filter(
        codigo__regex=r'^COMP\d{4}$'
    )
    
    for ordem in ordens:
        # Extrair o número do código antigo
        match = re.match(r'^COMP(\d{4})$', ordem.codigo)
        if match:
            numero = match.group(1)
            novo_codigo = f"ORDCOMP{numero}"
            
            # Verificar se o novo código já existe
            if not OrdemCompra.objects.filter(codigo=novo_codigo).exclude(id=ordem.id).exists():
                ordem.codigo = novo_codigo
                ordem.save()
                print(f"[OK] Ordem {ordem.id} atualizada: COMP{numero} -> {novo_codigo}")
            else:
                print(f"[AVISO] Ordem {ordem.id} nao atualizada: {novo_codigo} ja existe")


def reverter_codigos_requisicoes(apps, schema_editor):
    """Reverte códigos de RQCOMP#### para COMP#### (apenas se necessário)"""
    RequisicaoCompraExterna = apps.get_model('empresa', 'RequisicaoCompraExterna')
    
    requisicoes = RequisicaoCompraExterna.objects.filter(
        codigo__regex=r'^RQCOMP\d{4}$'
    )
    
    for requisicao in requisicoes:
        match = re.match(r'^RQCOMP(\d{4})$', requisicao.codigo)
        if match:
            numero = match.group(1)
            codigo_antigo = f"COMP{numero}"
            if not RequisicaoCompraExterna.objects.filter(codigo=codigo_antigo).exclude(id=requisicao.id).exists():
                requisicao.codigo = codigo_antigo
                requisicao.save()


def reverter_codigos_ordens(apps, schema_editor):
    """Reverte códigos de ORDCOMP#### para COMP#### (apenas se necessário)"""
    OrdemCompra = apps.get_model('empresa', 'OrdemCompra')
    
    ordens = OrdemCompra.objects.filter(
        codigo__regex=r'^ORDCOMP\d{4}$'
    )
    
    for ordem in ordens:
        match = re.match(r'^ORDCOMP(\d{4})$', ordem.codigo)
        if match:
            numero = match.group(1)
            codigo_antigo = f"COMP{numero}"
            if not OrdemCompra.objects.filter(codigo=codigo_antigo).exclude(id=ordem.id).exists():
                ordem.codigo = codigo_antigo
                ordem.save()


class Migration(migrations.Migration):

    dependencies = [
        ('empresa', '0149_add_forma_pagamento_ordem_compra'),
    ]

    operations = [
        migrations.RunPython(
            migrar_codigos_requisicoes,
            reverse_code=reverter_codigos_requisicoes
        ),
        migrations.RunPython(
            migrar_codigos_ordens,
            reverse_code=reverter_codigos_ordens
        ),
    ]

