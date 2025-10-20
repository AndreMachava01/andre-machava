#!/usr/bin/env python
"""
Script para encontrar e corrigir nomes codificados das viaturas
"""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meuprojeto.settings')
django.setup()

from meuprojeto.empresa.models_stock import Transportadora

def corrigir_nomes_codificados():
    print("🔍 PROCURANDO E CORRIGINDO NOMES CODIFICADOS")
    print("=" * 60)
    
    # Buscar todas as viaturas internas
    viaturas = Transportadora.objects.filter(
        tipo__in=['VIATURA_INTERNA_ENTREGA', 'VIATURA_INTERNA_EXECUTIVO']
    ).order_by('id')
    
    print(f"\n📋 VIATURAS ENCONTRADAS: {viaturas.count()}")
    
    # Identificar nomes codificados
    nomes_codificados = []
    for viatura in viaturas:
        # Verificar se o nome segue padrão técnico (XXX-XXX-XX)
        if '-' in viatura.nome and len(viatura.nome.split('-')) == 3:
            partes = viatura.nome.split('-')
            if len(partes[0]) <= 3 and len(partes[1]) <= 4 and partes[2].isdigit():
                nomes_codificados.append(viatura)
    
    print(f"\n🔍 NOMES CODIFICADOS ENCONTRADOS: {len(nomes_codificados)}")
    
    if nomes_codificados:
        print(f"\n📝 LISTA DE NOMES CODIFICADOS:")
        for viatura in nomes_codificados:
            print(f"   • ID: {viatura.id} | Nome: '{viatura.nome}' | Código: {viatura.codigo}")
            print(f"     Tipo: {viatura.get_tipo_display()} | Categoria: {viatura.categoria_veiculo}")
            print(f"     Sucursal: {viatura.sucursal.nome if viatura.sucursal else 'N/A'}")
        
        print(f"\n🔄 CORRIGINDO NOMES CODIFICADOS:")
        
        # Agrupar por categoria e sucursal para enumerar
        grupos = {}
        
        for viatura in nomes_codificados:
            categoria = viatura.categoria_veiculo
            sucursal_nome = viatura.sucursal.nome if viatura.sucursal else 'Sem Sucursal'
            
            # Simplificar nome da sucursal
            if 'LOJA DA MATOLA' in sucursal_nome:
                sucursal_simples = 'Matola'
            elif 'LOJA DE MARRACUENE' in sucursal_nome:
                sucursal_simples = 'Marracuene'
            elif 'Sede - Conception' in sucursal_nome:
                sucursal_simples = 'Sede'
            else:
                sucursal_simples = sucursal_nome
            
            chave = f"{categoria}_{sucursal_simples}"
            if chave not in grupos:
                grupos[chave] = []
            grupos[chave].append(viatura)
        
        # Renomear cada grupo
        for chave, grupo in grupos.items():
            categoria, sucursal = chave.split('_', 1)
            
            for i, viatura in enumerate(grupo, 1):
                nome_antigo = viatura.nome
                
                if len(grupo) == 1:
                    # Apenas uma viatura desta categoria nesta sucursal
                    nome_novo = f"{categoria} - {sucursal}"
                else:
                    # Múltiplas viaturas, enumerar
                    nome_novo = f"{categoria} - {sucursal} {i}"
                
                # Atualizar nome
                viatura.nome = nome_novo
                viatura.save()
                
                print(f"   ✅ '{nome_antigo}' → '{nome_novo}'")
        
        print(f"\n📊 RESULTADO FINAL:")
        viaturas_atualizadas = Transportadora.objects.filter(
            tipo__in=['VIATURA_INTERNA_ENTREGA', 'VIATURA_INTERNA_EXECUTIVO']
        ).order_by('tipo', 'nome')
        
        print(f"\n📦 VIATURAS DE ENTREGAS:")
        for viatura in viaturas_atualizadas.filter(tipo='VIATURA_INTERNA_ENTREGA'):
            print(f"   • {viatura.nome} ({viatura.codigo})")
        
        print(f"\n👔 VIATURAS EXECUTIVAS:")
        for viatura in viaturas_atualizadas.filter(tipo='VIATURA_INTERNA_EXECUTIVO'):
            print(f"   • {viatura.nome} ({viatura.codigo})")
    
    else:
        print(f"\n✅ NENHUM NOME CODIFICADO ENCONTRADO!")
        print(f"   Todas as viaturas já têm nomes claros.")
    
    print("\n" + "=" * 60)
    print("✅ CORREÇÃO CONCLUÍDA!")
    print("\n🌐 VERIFIQUE EM:")
    print("   • http://localhost:8000/stock/logistica/veiculos/")

if __name__ == "__main__":
    corrigir_nomes_codificados()


