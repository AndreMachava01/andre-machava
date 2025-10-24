#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DEMONSTRACAO RAPIDA DOS SCRIPTS DE FILTROS
Sistema Unificado de Filtros - Demo

Este script demonstra rapidamente como usar os scripts de filtros
sem executar todas as operacoes completas.

Autor: Sistema Conception
Data: 2025
"""

import os
import sys
from pathlib import Path

def show_demo():
    """Demonstracao rapida dos scripts"""
    print("DEMONSTRACAO DOS SCRIPTS DE FILTROS")
    print("=" * 50)
    
    print("\nSCRIPTS CRIADOS:")
    
    scripts = [
        ("gerenciar_filtros.py", "Script principal com interface interativa", "[PRINCIPAL]"),
        ("verificar_corrigir_filtros.py", "Verifica problemas e aplica correcoes", "[VERIFICACAO]"),
        ("migrar_corrigir_filtros.py", "Migra filtros antigos para sistema unificado", "[MIGRACAO]"),
        ("testar_filtros.py", "Testa e valida funcionamento dos filtros", "[TESTES]"),
        ("README_FILTROS.md", "Documentacao completa do sistema", "[DOCS]")
    ]
    
    for script, description, icon in scripts:
        file_path = Path(script)
        status = "OK" if file_path.exists() else "ERRO"
        print(f"  {status} {icon} {script}")
        print(f"     {description}")
        if file_path.exists():
            size = file_path.stat().st_size
            print(f"     Tamanho: {size:,} bytes")
        print()
    
    print("COMO USAR:")
    print("1. Para iniciantes (RECOMENDADO):")
    print("   python gerenciar_filtros.py")
    print("   Escolha a opcao 1 para execucao completa")
    print()
    print("2. Para desenvolvedores:")
    print("   python verificar_corrigir_filtros.py")
    print("   python migrar_corrigir_filtros.py")
    print("   python testar_filtros.py")
    print()
    
    print("RELATORIOS GERADOS:")
    reports = [
        "relatorio_filtros.json",
        "relatorio_migracao_filtros.json", 
        "relatorio_testes_filtros.json",
        "relatorio_workflow_filtros.json"
    ]
    
    for report in reports:
        file_path = Path(report)
        status = "OK" if file_path.exists() else "PENDENTE"
        print(f"  {status} {report}")
    
    print("\nFUNCIONALIDADES PRINCIPAIS:")
    features = [
        "Verificacao automatica de problemas nos filtros",
        "Correcao automatica de problemas comuns",
        "Migracao de filtros manuais para sistema unificado",
        "Testes de validacao e consistencia",
        "Relatorios detalhados em JSON",
        "Interface interativa para facilitar uso",
        "Logs detalhados de todas as operacoes"
    ]
    
    for feature in features:
        print(f"  OK {feature}")
    
    print("\nPROBLEMAS QUE PODEM SER CORRIGIDOS:")
    fixes = [
        "CSRF Token faltante em formularios",
        "CSS inline nos templates de filtros",
        "JavaScript inline nos templates",
        "Configuracoes faltantes no filters_config.py",
        "Filtros antigos/manuais",
        "Inconsistencias entre templates e configuracoes"
    ]
    
    for fix in fixes:
        print(f"  CORRIGIVEL {fix}")
    
    print("\nDOCUMENTACAO:")
    print("  README_FILTROS.md - Guia completo de uso")
    print("  SISTEMA_UNIFICADO_FILTROS.md - Documentacao tecnica")
    print("  SISTEMA_FILTROS_MIGRACAO_COMPLETA.md - Guia de migracao")
    
    print("\nPROXIMOS PASSOS:")
    print("1. Execute: python gerenciar_filtros.py")
    print("2. Escolha a opcao 1 (Verificacao completa)")
    print("3. Revise os relatorios gerados")
    print("4. Teste os filtros no sistema")
    print("5. Execute periodicamente para manutencao")

def check_environment():
    """Verifica ambiente de execucao"""
    print("\nVERIFICACAO DO AMBIENTE:")
    
    # Verificar Python
    python_version = sys.version_info
    print(f"  Python: {python_version.major}.{python_version.minor}.{python_version.micro}")
    
    # Verificar diretorio atual
    current_dir = Path.cwd()
    print(f"  Diretorio atual: {current_dir}")
    
    # Verificar arquivos necessarios
    required_files = [
        "meuprojeto/empresa/filters_config.py",
        "templates/includes/filters_unified.html",
        "meuprojeto/empresa/mixins.py"
    ]
    
    print("\nARQUIVOS DO SISTEMA:")
    for file_path in required_files:
        path = Path(file_path)
        status = "OK" if path.exists() else "ERRO"
        print(f"  {status} {file_path}")
    
    # Verificar templates com filtros
    templates_dir = Path("templates")
    if templates_dir.exists():
        html_files = list(templates_dir.rglob("*.html"))
        print(f"\nTemplates encontrados: {len(html_files)}")
        
        # Contar templates com filtros
        templates_with_filters = 0
        for html_file in html_files:
            try:
                with open(html_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                if 'filters_unified.html' in content or 'filter' in content.lower():
                    templates_with_filters += 1
            except:
                continue
        
        print(f"Templates com filtros: {templates_with_filters}")

def main():
    """Funcao principal"""
    show_demo()
    check_environment()
    
    print("\n" + "="*60)
    print("DEMONSTRACAO CONCLUIDA!")
    print("Execute 'python gerenciar_filtros.py' para comecar!")
    print("="*60)

if __name__ == "__main__":
    main()