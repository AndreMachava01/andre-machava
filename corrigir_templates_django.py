#!/usr/bin/env python3
"""
Script para Corrigir Erros de Template Django
Corrige problemas causados pelo script de contadores que aplicou filtros incorretamente
"""

import os
import re
import shutil
from pathlib import Path
from datetime import datetime

class TemplateFixer:
    def __init__(self, templates_dir="templates"):
        self.templates_dir = Path(templates_dir)
        self.backup_dir = Path("backups_template_fixes")
        self.log_file = Path("template_fixes_log.txt")
        self.stats = {
            'total_templates': 0,
            'templates_processed': 0,
            'fixes_applied': 0,
            'backups_created': 0,
            'errors': 0
        }
        
    def log(self, message, level="INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] [{level}] {message}"
        print(log_message)
        
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_message + "\n")
    
    def create_backup_dir(self):
        if not self.backup_dir.exists():
            self.backup_dir.mkdir(parents=True)
            self.log(f"Diretório de backup criado: {self.backup_dir}")
    
    def backup_file(self, file_path):
        try:
            backup_path = self.backup_dir / file_path.relative_to(self.templates_dir)
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file_path, backup_path)
            self.stats['backups_created'] += 1
            self.log(f"Backup criado: {backup_path}")
            return True
        except Exception as e:
            self.log(f"Erro ao criar backup de {file_path}: {e}", "ERROR")
            return False
    
    def fix_template_syntax_errors(self, content):
        """Corrige erros de sintaxe de template Django"""
        fixes = 0
        
        # Corrigir blocos for com filtros incorretos
        patterns = [
            # {% for|default:0 items in ... %}
            (r'{%\s*for\|default:0\s+(\w+)\s+in\s+([^%]+)\s*%}', r'{% for \1 in \2 %}'),
            
            # {% for|default:0 ... %}
            (r'{%\s*for\|default:0\s+([^%]+)\s*%}', r'{% for \1 %}'),
            
            # {% if|default:0 ... %}
            (r'{%\s*if\|default:0\s+([^%]+)\s*%}', r'{% if \1 %}'),
            
            # {% elif|default:0 ... %}
            (r'{%\s*elif\|default:0\s+([^%]+)\s*%}', r'{% elif \1 %}'),
            
            # {% while|default:0 ... %}
            (r'{%\s*while\|default:0\s+([^%]+)\s*%}', r'{% while \1 %}'),
            
            # {% with|default:0 ... %}
            (r'{%\s*with\|default:0\s+([^%]+)\s*%}', r'{% with \1 %}'),
        ]
        
        for pattern, replacement in patterns:
            matches = re.findall(pattern, content)
            if matches:
                content = re.sub(pattern, replacement, content)
                fixes += len(matches)
                self.log(f"Corrigidos {len(matches)} blocos com filtros incorretos: {pattern}")
        
        return content, fixes
    
    def fix_variable_syntax_errors(self, content):
        """Corrige erros de sintaxe de variáveis"""
        fixes = 0
        
        # Corrigir variáveis com filtros incorretos em contextos inadequados
        patterns = [
            # {{ for|default:0 ... }}
            (r'{{\s*for\|default:0\s+([^}]+)\s*}}', r'{{ \1 }}'),
            
            # {{ if|default:0 ... }}
            (r'{{\s*if\|default:0\s+([^}]+)\s*}}', r'{{ \1 }}'),
            
            # {{ while|default:0 ... }}
            (r'{{\s*while\|default:0\s+([^}]+)\s*}}', r'{{ \1 }}'),
            
            # {{ with|default:0 ... }}
            (r'{{\s*with\|default:0\s+([^}]+)\s*}}', r'{{ \1 }}'),
        ]
        
        for pattern, replacement in patterns:
            matches = re.findall(pattern, content)
            if matches:
                content = re.sub(pattern, replacement, content)
                fixes += len(matches)
                self.log(f"Corrigidas {len(matches)} variáveis com filtros incorretos: {pattern}")
        
        return content, fixes
    
    def fix_template(self, file_path):
        """Aplica todas as correções em um template"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            total_fixes = 0
            
            # Aplicar correções
            content, fixes = self.fix_template_syntax_errors(content)
            total_fixes += fixes
            
            content, fixes = self.fix_variable_syntax_errors(content)
            total_fixes += fixes
            
            # Se houve correções, salvar o arquivo
            if total_fixes > 0:
                if not self.backup_file(file_path):
                    return 0
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                self.log(f"Correções aplicadas em {file_path}: {total_fixes}")
            
            return total_fixes
            
        except Exception as e:
            self.log(f"Erro ao processar template {file_path}: {e}", "ERROR")
            self.stats['errors'] += 1
            return 0
    
    def scan_templates(self):
        """Escaneia todos os templates"""
        html_files = list(self.templates_dir.rglob("*.html"))
        self.stats['total_templates'] = len(html_files)
        
        self.log(f"Encontrados {len(html_files)} templates HTML")
        
        return html_files
    
    def generate_report(self):
        """Gera relatório final"""
        self.log("=== RELATÓRIO FINAL ===")
        self.log(f"Total de templates encontrados: {self.stats['total_templates']}")
        self.log(f"Templates processados: {self.stats['templates_processed']}")
        self.log(f"Correções aplicadas: {self.stats['fixes_applied']}")
        self.log(f"Backups criados: {self.stats['backups_created']}")
        self.log(f"Erros encontrados: {self.stats['errors']}")
        
        if self.stats['errors'] == 0:
            self.log("CORREÇÃO DE TEMPLATES CONCLUÍDA COM SUCESSO!", "SUCCESS")
        else:
            self.log(f"CORREÇÃO DE TEMPLATES CONCLUÍDA COM {self.stats['errors']} ERROS", "WARNING")
    
    def run_fixes(self):
        """Executa correções completas"""
        self.log("=== INICIANDO CORREÇÃO DE TEMPLATES ===")
        
        self.create_backup_dir()
        
        # Corrigir templates
        html_files = self.scan_templates()
        
        for file_path in html_files:
            fixes = self.fix_template(file_path)
            
            if fixes > 0:
                self.stats['fixes_applied'] += fixes
            
            self.stats['templates_processed'] += 1
        
        self.generate_report()

def main():
    print("=== SCRIPT DE CORREÇÃO DE TEMPLATES DJANGO ===")
    print("Corrigindo erros de sintaxe causados pelo script de contadores...")
    
    if not Path("templates").exists():
        print("ERRO: Diretório 'templates' não encontrado!")
        return
    
    fixer = TemplateFixer()
    fixer.run_fixes()
    
    print("\n=== CORREÇÃO DE TEMPLATES CONCLUÍDA ===")
    print("Verifique o arquivo 'template_fixes_log.txt' para detalhes completos.")

if __name__ == "__main__":
    main()
