#!/usr/bin/env python3
"""
Script para Verificação da Estrutura Unificada
Verifica se todos os componentes da estrutura unificada estão no lugar correto e funcionando
"""

import os
import re
from pathlib import Path
from datetime import datetime

class UnifiedStructureChecker:
    def __init__(self):
        self.log_file = Path("estrutura_unificada_verificacao_log.txt")
        self.stats = {
            'total_checks': 0,
            'passed_checks': 0,
            'failed_checks': 0,
            'warnings': 0,
            'errors': 0
        }
        self.issues = []
        
    def log(self, message, level="INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] [{level}] {message}"
        print(log_message)
        
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_message + "\n")
    
    def check_file_exists(self, file_path, description):
        """Verifica se um arquivo existe"""
        self.stats['total_checks'] += 1
        
        if Path(file_path).exists():
            self.log(f"OK {description}: {file_path}")
            self.stats['passed_checks'] += 1
            return True
        else:
            self.log(f"ERRO {description}: {file_path} - ARQUIVO NAO ENCONTRADO", "ERROR")
            self.stats['failed_checks'] += 1
            self.issues.append(f"Arquivo nao encontrado: {file_path}")
            return False
    
    def check_file_content(self, file_path, required_content, description):
        """Verifica se um arquivo contém conteúdo específico"""
        self.stats['total_checks'] += 1
        
        if not Path(file_path).exists():
            self.log(f"ERRO {description}: Arquivo nao existe", "ERROR")
            self.stats['failed_checks'] += 1
            return False
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if required_content in content:
                self.log(f"OK {description}: Conteudo encontrado")
                self.stats['passed_checks'] += 1
                return True
            else:
                self.log(f"AVISO {description}: Conteudo nao encontrado", "WARNING")
                self.stats['warnings'] += 1
                self.issues.append(f"Conteudo nao encontrado em {file_path}: {required_content}")
                return False
        except Exception as e:
            self.log(f"ERRO {description}: Erro ao ler arquivo - {e}", "ERROR")
            self.stats['errors'] += 1
            return False
    
    def check_css_inclusion(self, template_path, css_file):
        """Verifica se um template inclui um arquivo CSS"""
        self.stats['total_checks'] += 1
        
        if not Path(template_path).exists():
            self.log(f"ERRO Template nao existe: {template_path}", "ERROR")
            self.stats['failed_checks'] += 1
            return False
        
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if css_file in content:
                self.log(f"OK CSS incluido em {template_path}: {css_file}")
                self.stats['passed_checks'] += 1
                return True
            else:
                self.log(f"AVISO CSS nao incluido em {template_path}: {css_file}", "WARNING")
                self.stats['warnings'] += 1
                self.issues.append(f"CSS nao incluido em {template_path}: {css_file}")
                return False
        except Exception as e:
            self.log(f"ERRO Erro ao verificar CSS em {template_path}: {e}", "ERROR")
            self.stats['errors'] += 1
            return False
    
    def check_template_inclusion(self, template_path, included_template):
        """Verifica se um template inclui outro template"""
        self.stats['total_checks'] += 1
        
        if not Path(template_path).exists():
            self.log(f"ERRO Template nao existe: {template_path}", "ERROR")
            self.stats['failed_checks'] += 1
            return False
        
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if included_template in content:
                self.log(f"OK Template incluido em {template_path}: {included_template}")
                self.stats['passed_checks'] += 1
                return True
            else:
                self.log(f"AVISO Template nao incluido em {template_path}: {included_template}", "WARNING")
                self.stats['warnings'] += 1
                self.issues.append(f"Template nao incluido em {template_path}: {included_template}")
                return False
        except Exception as e:
            self.log(f"ERRO Erro ao verificar template em {template_path}: {e}", "ERROR")
            self.stats['errors'] += 1
            return False
    
    def check_python_import(self, file_path, import_statement):
        """Verifica se um arquivo Python contém um import específico"""
        self.stats['total_checks'] += 1
        
        if not Path(file_path).exists():
            self.log(f"ERRO Arquivo nao existe: {file_path}", "ERROR")
            self.stats['failed_checks'] += 1
            return False
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if import_statement in content:
                self.log(f"OK Import encontrado em {file_path}: {import_statement}")
                self.stats['passed_checks'] += 1
                return True
            else:
                self.log(f"AVISO Import nao encontrado em {file_path}: {import_statement}", "WARNING")
                self.stats['warnings'] += 1
                self.issues.append(f"Import nao encontrado em {file_path}: {import_statement}")
                return False
        except Exception as e:
            self.log(f"ERRO Erro ao verificar import em {file_path}: {e}", "ERROR")
            self.stats['errors'] += 1
            return False
    
    def check_unified_structure(self):
        """Verifica toda a estrutura unificada"""
        self.log("=== VERIFICAÇÃO DA ESTRUTURA UNIFICADA ===")
        
        # 1. Verificar arquivos CSS
        self.log("\n--- VERIFICANDO ARQUIVOS CSS ---")
        self.check_file_exists("meuprojeto/empresa/static/css/buttons-unified.css", "CSS dos Botões Unificados")
        self.check_file_exists("meuprojeto/empresa/static/css/grids-unified.css", "CSS dos Grids Unificados")
        self.check_file_exists("meuprojeto/empresa/static/css/design-system.css", "CSS do Design System")
        
        # 2. Verificar templates de componentes
        self.log("\n--- VERIFICANDO TEMPLATES DE COMPONENTES ---")
        self.check_file_exists("templates/components/button_unified.html", "Template Base de Botão")
        self.check_file_exists("templates/components/button_group_unified.html", "Template de Grupo de Botões")
        self.check_file_exists("templates/components/module_buttons.html", "Template de Botões de Módulo")
        self.check_file_exists("templates/components/submodule_buttons.html", "Template de Botões de Submódulo")
        self.check_file_exists("templates/components/navigation_buttons.html", "Template de Botões de Navegação")
        self.check_file_exists("templates/components/action_buttons.html", "Template de Botões de Ação")
        self.check_file_exists("templates/components/confirmation_buttons.html", "Template de Botões de Confirmação")
        self.check_file_exists("templates/components/page_header.html", "Template de Cabeçalho Unificado")
        
        # 3. Verificar templates de filtros
        self.log("\n--- VERIFICANDO TEMPLATES DE FILTROS ---")
        self.check_file_exists("templates/includes/filters_unified.html", "Template de Filtros Unificados")
        
        # 4. Verificar arquivos Python
        self.log("\n--- VERIFICANDO ARQUIVOS PYTHON ---")
        self.check_file_exists("meuprojeto/empresa/buttons_config.py", "Configuração de Botões")
        self.check_file_exists("meuprojeto/empresa/mixins.py", "Mixins Unificados")
        self.check_file_exists("meuprojeto/empresa/views_unified.py", "Views Unificadas")
        self.check_file_exists("meuprojeto/empresa/templatetags/button_tags.py", "Template Tags de Botões")
        
        # 5. Verificar conteúdo dos arquivos CSS
        self.log("\n--- VERIFICANDO CONTEÚDO DOS ARQUIVOS CSS ---")
        self.check_file_content("meuprojeto/empresa/static/css/buttons-unified.css", ".btn-unified", "Classe CSS btn-unified")
        self.check_file_content("meuprojeto/empresa/static/css/buttons-unified.css", ".btn-module", "Classe CSS btn-module")
        self.check_file_content("meuprojeto/empresa/static/css/buttons-unified.css", ".btn-submodule", "Classe CSS btn-submodule")
        
        # 6. Verificar conteúdo dos templates
        self.log("\n--- VERIFICANDO CONTEÚDO DOS TEMPLATES ---")
        self.check_file_content("templates/components/button_unified.html", "btn-unified", "Template de botão unificado")
        self.check_file_content("templates/includes/filters_unified.html", "filters-section", "Template de filtros unificados")
        
        # 7. Verificar inclusões CSS
        self.log("\n--- VERIFICANDO INCLUSÕES CSS ---")
        self.check_css_inclusion("templates/base_admin.html", "buttons-unified.css")
        self.check_css_inclusion("templates/base_admin.html", "design-system.css")
        
        # 8. Verificar inclusões de templates
        self.log("\n--- VERIFICANDO INCLUSÕES DE TEMPLATES ---")
        self.check_template_inclusion("templates/components/module_buttons.html", "button_unified.html")
        self.check_template_inclusion("templates/components/submodule_buttons.html", "button_unified.html")
        
        # 9. Verificar imports Python
        self.log("\n--- VERIFICANDO IMPORTS PYTHON ---")
        self.check_python_import("meuprojeto/empresa/templatetags/button_tags.py", "from meuprojeto.empresa.buttons_config import")
        self.check_python_import("meuprojeto/empresa/mixins.py", "from .filters_config import")
        
        # 10. Verificar arquivos de exemplo
        self.log("\n--- VERIFICANDO ARQUIVOS DE EXEMPLO ---")
        self.check_file_exists("templates/examples/buttons_unified_example.html", "Exemplo de Botões Unificados")
        
        # 11. Verificar documentação
        self.log("\n--- VERIFICANDO DOCUMENTAÇÃO ---")
        self.check_file_exists("SISTEMA_BOTOES_UNIFICADO.md", "Documentação dos Botões Unificados")
        self.check_file_exists("SISTEMA_UNIFICADO_FILTROS.md", "Documentação dos Filtros Unificados")
    
    def generate_report(self):
        """Gera relatório final"""
        self.log("\n=== RELATÓRIO FINAL ===")
        self.log(f"Total de verificações: {self.stats['total_checks']}")
        self.log(f"Verificações aprovadas: {self.stats['passed_checks']}")
        self.log(f"Verificações falhadas: {self.stats['failed_checks']}")
        self.log(f"Avisos: {self.stats['warnings']}")
        self.log(f"Erros: {self.stats['errors']}")
        
        success_rate = (self.stats['passed_checks'] / self.stats['total_checks']) * 100 if self.stats['total_checks'] > 0 else 0
        self.log(f"Taxa de sucesso: {success_rate:.1f}%")
        
        if self.issues:
            self.log("\n=== PROBLEMAS ENCONTRADOS ===")
            for issue in self.issues:
                self.log(f"AVISO {issue}")
        
        if self.stats['errors'] == 0 and self.stats['failed_checks'] == 0:
            self.log("OK ESTRUTURA UNIFICADA VERIFICADA COM SUCESSO!", "SUCCESS")
        else:
            self.log(f"AVISO ESTRUTURA UNIFICADA COM PROBLEMAS - {self.stats['errors']} erros, {self.stats['failed_checks']} falhas", "WARNING")
    
    def run_verification(self):
        """Executa verificação completa"""
        self.log("=== INICIANDO VERIFICAÇÃO DA ESTRUTURA UNIFICADA ===")
        
        self.check_unified_structure()
        self.generate_report()

def main():
    print("=== SCRIPT DE VERIFICAÇÃO DA ESTRUTURA UNIFICADA ===")
    print("Verificando se todos os componentes estão no lugar correto...")
    
    checker = UnifiedStructureChecker()
    checker.run_verification()
    
    print("\n=== VERIFICAÇÃO DA ESTRUTURA UNIFICADA CONCLUÍDA ===")
    print("Verifique o arquivo 'estrutura_unificada_verificacao_log.txt' para detalhes completos.")

if __name__ == "__main__":
    main()
