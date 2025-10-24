#!/usr/bin/env python3
"""
SISTEMA UNIFICADO DE GERENCIAMENTO DE PROBLEMAS
Script para gerenciar e resolver problemas do sistema de forma sistemática
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path
import subprocess

class SistemaGerenciamentoProblemas:
    def __init__(self):
        self.setup_logging()
        self.problemas_resolvidos = 0
        self.problemas_detectados = 0
        self.relatorio = {
            'timestamp': datetime.now().isoformat(),
            'problemas_criticos': [],
            'problemas_importantes': [],
            'problemas_menores': [],
            'correcoes_aplicadas': [],
            'estatisticas': {}
        }
    
    def setup_logging(self):
        """Configurar sistema de logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('gerenciamento_problemas.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def detectar_problemas_criticos(self):
        """Detectar problemas críticos que quebram o sistema"""
        self.logger.info("🔴 DETECTANDO PROBLEMAS CRÍTICOS...")
        
        problemas = []
        
        # 1. Verificar erros de sintaxe JavaScript
        problemas.extend(self.verificar_sintaxe_javascript())
        
        # 2. Verificar erros de URL
        problemas.extend(self.verificar_erros_url())
        
        # 3. Verificar templates malformados
        problemas.extend(self.verificar_templates_malformados())
        
        self.relatorio['problemas_criticos'] = problemas
        self.problemas_detectados += len(problemas)
        
        return problemas
    
    def detectar_problemas_importantes(self):
        """Detectar problemas importantes que afetam performance/UX"""
        self.logger.info("🟡 DETECTANDO PROBLEMAS IMPORTANTES...")
        
        problemas = []
        
        # 1. Verificar duplicação de CSS
        problemas.extend(self.verificar_duplicacao_css())
        
        # 2. Verificar sistema de filtros
        problemas.extend(self.verificar_problemas_filtros())
        
        # 3. Verificar redundâncias
        problemas.extend(self.verificar_redundancias())
        
        self.relatorio['problemas_importantes'] = problemas
        self.problemas_detectados += len(problemas)
        
        return problemas
    
    def verificar_sintaxe_javascript(self):
        """Verificar erros de sintaxe JavaScript"""
        problemas = []
        
        try:
            # Procurar por padrões problemáticos
            import subprocess
            result = subprocess.run([
                'powershell', '-Command', 
                "Get-ChildItem -Recurse -Filter '*.html' | Select-String -Pattern 'const\\|default:0' | Measure-Object | Select-Object Count"
            ], capture_output=True, text=True)
            
            if 'Count' in result.stdout:
                count = int(result.stdout.split()[-1])
                if count > 0:
                    problemas.append({
                        'tipo': 'Sintaxe JavaScript',
                        'descricao': f'{count} erros de sintaxe JavaScript encontrados',
                        'severidade': 'CRÍTICO',
                        'solucao': 'Executar correção automática de sintaxe'
                    })
        except Exception as e:
            self.logger.error(f"Erro ao verificar sintaxe JavaScript: {e}")
        
        return problemas
    
    def verificar_erros_url(self):
        """Verificar erros de URL"""
        problemas = []
        
        try:
            # Verificar logs por erros de URL
            if os.path.exists('django.log'):
                with open('django.log', 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    if 'NoReverseMatch' in content:
                        problemas.append({
                            'tipo': 'Erro de URL',
                            'descricao': 'Erros de NoReverseMatch encontrados no log',
                            'severidade': 'CRÍTICO',
                            'solucao': 'Verificar configuração de URLs'
                        })
        except Exception as e:
            self.logger.error(f"Erro ao verificar URLs: {e}")
        
        return problemas
    
    def verificar_templates_malformados(self):
        """Verificar templates HTML malformados"""
        problemas = []
        
        try:
            # Verificar por HTML malformado
            import subprocess
            result = subprocess.run([
                'powershell', '-Command',
                "Get-ChildItem -Recurse -Filter '*.html' | Select-String -Pattern '<div.*<div.*</div>.*</div>' | Measure-Object | Select-Object Count"
            ], capture_output=True, text=True)
            
            # Esta é uma verificação básica - pode ser expandida
            problemas.append({
                'tipo': 'Template Malformado',
                'descricao': 'Verificação básica de templates',
                'severidade': 'CRÍTICO',
                'solucao': 'Executar verificação completa de templates'
            })
        except Exception as e:
            self.logger.error(f"Erro ao verificar templates: {e}")
        
        return problemas
    
    def verificar_duplicacao_css(self):
        """Verificar duplicação de CSS"""
        problemas = []
        
        try:
            # Verificar tamanho dos arquivos CSS
            css_files = list(Path('.').rglob('*.css'))
            for css_file in css_files:
                if css_file.stat().st_size > 100000:  # > 100KB
                    problemas.append({
                        'tipo': 'CSS Duplicado',
                        'descricao': f'Arquivo CSS muito grande: {css_file.name}',
                        'severidade': 'IMPORTANTE',
                        'solucao': 'Otimizar e remover duplicações'
                    })
        except Exception as e:
            self.logger.error(f"Erro ao verificar CSS: {e}")
        
        return problemas
    
    def verificar_problemas_filtros(self):
        """Verificar problemas no sistema de filtros"""
        problemas = []
        
        try:
            # Verificar se existem logs de problemas de filtros
            if os.path.exists('filtros_verificacao_log.txt'):
                with open('filtros_verificacao_log.txt', 'r', encoding='utf-8') as f:
                    content = f.read()
                    if 'problema' in content.lower():
                        problemas.append({
                            'tipo': 'Sistema de Filtros',
                            'descricao': 'Problemas detectados no sistema de filtros',
                            'severidade': 'IMPORTANTE',
                            'solucao': 'Executar correção de filtros'
                        })
        except Exception as e:
            self.logger.error(f"Erro ao verificar filtros: {e}")
        
        return problemas
    
    def verificar_redundancias(self):
        """Verificar redundâncias no código"""
        problemas = []
        
        try:
            # Verificar logs de redundâncias
            if os.path.exists('redundancias_verificacao_log.txt'):
                size = os.path.getsize('redundancias_verificacao_log.txt')
                if size > 1000000:  # > 1MB
                    problemas.append({
                        'tipo': 'Redundâncias',
                        'descricao': 'Muitas redundâncias detectadas',
                        'severidade': 'IMPORTANTE',
                        'solucao': 'Executar limpeza de redundâncias'
                    })
        except Exception as e:
            self.logger.error(f"Erro ao verificar redundâncias: {e}")
        
        return problemas
    
    def executar_correcoes_automaticas(self):
        """Executar correções automáticas"""
        self.logger.info("🔧 EXECUTANDO CORREÇÕES AUTOMÁTICAS...")
        
        correcoes = []
        
        # 1. Corrigir sintaxe JavaScript
        if self.executar_script('fix_js_syntax.py'):
            correcoes.append('Sintaxe JavaScript corrigida')
        
        # 2. Corrigir filtros
        if self.executar_script('verificar_corrigir_filtros.py'):
            correcoes.append('Sistema de filtros corrigido')
        
        # 3. Corrigir redundâncias
        if self.executar_script('verificar_redundancias.py'):
            correcoes.append('Redundâncias removidas')
        
        # 4. Corrigir botões
        if self.executar_script('verificar_corrigir_botoes.py'):
            correcoes.append('Sistema de botões corrigido')
        
        self.relatorio['correcoes_aplicadas'] = correcoes
        self.problemas_resolvidos += len(correcoes)
        
        return correcoes
    
    def executar_script(self, script_name):
        """Executar um script de correção"""
        try:
            if os.path.exists(script_name):
                result = subprocess.run([sys.executable, script_name], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    self.logger.info(f"✅ Script {script_name} executado com sucesso")
                    return True
                else:
                    self.logger.error(f"❌ Erro ao executar {script_name}: {result.stderr}")
                    return False
            else:
                self.logger.warning(f"⚠️ Script {script_name} não encontrado")
                return False
        except Exception as e:
            self.logger.error(f"❌ Erro ao executar {script_name}: {e}")
            return False
    
    def gerar_relatorio(self):
        """Gerar relatório completo"""
        self.relatorio['estatisticas'] = {
            'problemas_detectados': self.problemas_detectados,
            'problemas_resolvidos': self.problemas_resolvidos,
            'taxa_sucesso': (self.problemas_resolvidos / max(self.problemas_detectados, 1)) * 100
        }
        
        # Salvar relatório
        with open('relatorio_gerenciamento_problemas.json', 'w', encoding='utf-8') as f:
            json.dump(self.relatorio, f, indent=2, ensure_ascii=False)
        
        self.logger.info("📊 Relatório salvo em: relatorio_gerenciamento_problemas.json")
    
    def executar_workflow_completo(self):
        """Executar workflow completo de gerenciamento"""
        self.logger.info("🚀 INICIANDO WORKFLOW COMPLETO DE GERENCIAMENTO DE PROBLEMAS")
        
        # Fase 1: Detectar problemas
        problemas_criticos = self.detectar_problemas_criticos()
        problemas_importantes = self.detectar_problemas_importantes()
        
        # Fase 2: Executar correções
        correcoes = self.executar_correcoes_automaticas()
        
        # Fase 3: Gerar relatório
        self.gerar_relatorio()
        
        # Resumo final
        self.logger.info("=" * 60)
        self.logger.info("📊 RESUMO FINAL:")
        self.logger.info(f"🔴 Problemas Críticos: {len(problemas_criticos)}")
        self.logger.info(f"🟡 Problemas Importantes: {len(problemas_importantes)}")
        self.logger.info(f"✅ Correções Aplicadas: {len(correcoes)}")
        self.logger.info(f"📈 Taxa de Sucesso: {self.relatorio['estatisticas']['taxa_sucesso']:.1f}%")
        self.logger.info("=" * 60)

def main():
    """Função principal"""
    print("SISTEMA DE GERENCIAMENTO DE PROBLEMAS")
    print("=" * 50)
    
    gerenciador = SistemaGerenciamentoProblemas()
    
    print("\nEscolha uma opcao:")
    print("1. Executar apenas deteccao de problemas criticos")
    print("2. Executar deteccao de problemas importantes")
    print("3. Executar correcoes automaticas")
    print("4. Executar workflow completo")
    print("5. Gerar relatorio de status")
    
    opcao = input("\nDigite sua opção (1-5): ").strip()
    
    if opcao == '1':
        problemas = gerenciador.detectar_problemas_criticos()
        print(f"\nProblemas criticos encontrados: {len(problemas)}")
        for problema in problemas:
            print(f"  - {problema['tipo']}: {problema['descricao']}")
    
    elif opcao == '2':
        problemas = gerenciador.detectar_problemas_importantes()
        print(f"\nProblemas importantes encontrados: {len(problemas)}")
        for problema in problemas:
            print(f"  - {problema['tipo']}: {problema['descricao']}")
    
    elif opcao == '3':
        correcoes = gerenciador.executar_correcoes_automaticas()
        print(f"\nCorrecoes aplicadas: {len(correcoes)}")
        for correcao in correcoes:
            print(f"  - {correcao}")
    
    elif opcao == '4':
        gerenciador.executar_workflow_completo()
    
    elif opcao == '5':
        gerenciador.gerar_relatorio()
        print("\nRelatorio gerado com sucesso!")
    
    else:
        print("Opcao invalida!")

if __name__ == "__main__":
    main()
