#!/usr/bin/env python3
"""
Script para Correção Automática de Redundâncias e Problemas
Corrige automaticamente CSS duplicado, JavaScript duplicado, URLs duplicadas e outros problemas
"""

import os
import re
import shutil
from pathlib import Path
from datetime import datetime
from collections import defaultdict, Counter

class RedundancyFixer:
    def __init__(self, templates_dir="templates", static_dir="meuprojeto/empresa/static"):
        self.templates_dir = Path(templates_dir)
        self.static_dir = Path(static_dir)
        self.backup_dir = Path("backups_correcoes")
        self.log_file = Path("correcoes_log.txt")
        self.stats = {
            'total_templates': 0,
            'templates_processed': 0,
            'corrections_applied': 0,
            'backups_created': 0,
            'errors': 0,
            'skipped': 0
        }
        self.corrections_applied = []
        
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
    
    def fix_duplicate_css_classes(self, content):
        """Remove classes CSS duplicadas"""
        corrections = 0
        
        # Encontrar todas as classes CSS
        css_pattern = r'\.([a-zA-Z0-9_-]+)\s*{[^}]*}'
        css_matches = re.findall(css_pattern, content)
        
        # Contar ocorrências
        class_counts = Counter(css_matches)
        duplicate_classes = [cls for cls, count in class_counts.items() if count > 1]
        
        for duplicate_class in duplicate_classes:
            # Encontrar todas as definições da classe
            pattern = rf'\.{re.escape(duplicate_class)}\s*{{[^}}]*}}'
            matches = re.findall(pattern, content)
            
            if len(matches) > 1:
                # Manter apenas a primeira definição
                first_match = matches[0]
                other_matches = matches[1:]
                
                for match in other_matches:
                    content = content.replace(match, '', 1)
                    corrections += 1
                
                self.log(f"Removidas {len(other_matches)} definições duplicadas da classe CSS: {duplicate_class}")
        
        return content, corrections
    
    def fix_duplicate_js_functions(self, content):
        """Remove funções JavaScript duplicadas"""
        corrections = 0
        
        # Encontrar todas as funções JavaScript
        js_pattern = r'function\s+([a-zA-Z0-9_]+)\s*\([^)]*\)\s*{[^}]*}'
        js_matches = re.findall(js_pattern, content, re.DOTALL)
        
        # Contar ocorrências
        function_counts = Counter(js_matches)
        duplicate_functions = [func for func, count in function_counts.items() if count > 1]
        
        for duplicate_function in duplicate_functions:
            # Encontrar todas as definições da função
            pattern = rf'function\s+{re.escape(duplicate_function)}\s*\([^)]*\)\s*{{[^}}]*}}'
            matches = re.findall(pattern, content, re.DOTALL)
            
            if len(matches) > 1:
                # Manter apenas a primeira definição
                first_match = matches[0]
                other_matches = matches[1:]
                
                for match in other_matches:
                    content = content.replace(match, '', 1)
                    corrections += 1
                
                self.log(f"Removidas {len(other_matches)} definições duplicadas da função JS: {duplicate_function}")
        
        return content, corrections
    
    def fix_duplicate_urls(self, content):
        """Remove URLs duplicadas no mesmo template"""
        corrections = 0
        
        # Encontrar todas as URLs
        url_pattern = r"{%\s*url\s+['\"]([^'\"]+)['\"]"
        url_matches = re.findall(url_pattern, content)
        
        # Contar ocorrências
        url_counts = Counter(url_matches)
        duplicate_urls = [url for url, count in url_counts.items() if count > 1]
        
        for duplicate_url in duplicate_urls:
            # Encontrar todas as ocorrências da URL
            pattern = rf"{{%\s*url\s+['\"]{re.escape(duplicate_url)}['\"]\s*%}}"
            matches = re.findall(pattern, content)
            
            if len(matches) > 1:
                # Manter apenas a primeira ocorrência
                first_match = matches[0]
                other_matches = matches[1:]
                
                for match in other_matches:
                    content = content.replace(match, '', 1)
                    corrections += 1
                
                self.log(f"Removidas {len(other_matches)} ocorrências duplicadas da URL: {duplicate_url}")
        
        return content, corrections
    
    def fix_duplicate_includes(self, content):
        """Remove includes duplicados"""
        corrections = 0
        
        # Encontrar todos os includes
        include_pattern = r"{%\s*include\s+['\"]([^'\"]+)['\"]"
        include_matches = re.findall(include_pattern, content)
        
        # Contar ocorrências
        include_counts = Counter(include_matches)
        duplicate_includes = [inc for inc, count in include_counts.items() if count > 1]
        
        for duplicate_include in duplicate_includes:
            # Encontrar todas as ocorrências do include
            pattern = rf"{{%\s*include\s+['\"]{re.escape(duplicate_include)}['\"]\s*%}}"
            matches = re.findall(pattern, content)
            
            if len(matches) > 1:
                # Manter apenas a primeira ocorrência
                first_match = matches[0]
                other_matches = matches[1:]
                
                for match in other_matches:
                    content = content.replace(match, '', 1)
                    corrections += 1
                
                self.log(f"Removidas {len(other_matches)} ocorrências duplicadas do include: {duplicate_include}")
        
        return content, corrections
    
    def fix_multiple_forms(self, content):
        """Consolida múltiplos formulários"""
        corrections = 0
        
        # Encontrar todos os formulários
        form_pattern = r'<form[^>]*>.*?</form>'
        forms = re.findall(form_pattern, content, re.DOTALL)
        
        if len(forms) > 1:
            # Manter apenas o primeiro formulário
            first_form = forms[0]
            other_forms = forms[1:]
            
            for form in other_forms:
                content = content.replace(form, '')
                corrections += 1
            
            self.log(f"Removidos {len(other_forms)} formulários duplicados")
        
        return content, corrections
    
    def fix_multiple_tables(self, content):
        """Consolida múltiplas tabelas"""
        corrections = 0
        
        # Encontrar todas as tabelas
        table_pattern = r'<table[^>]*>.*?</table>'
        tables = re.findall(table_pattern, content, re.DOTALL)
        
        if len(tables) > 1:
            # Manter apenas a primeira tabela
            first_table = tables[0]
            other_tables = tables[1:]
            
            for table in other_tables:
                content = content.replace(table, '')
                corrections += 1
            
            self.log(f"Removidas {len(other_tables)} tabelas duplicadas")
        
        return content, corrections
    
    def fix_multiple_inline_css(self, content):
        """Consolida CSS inline duplicado"""
        corrections = 0
        
        # Encontrar todos os blocos CSS inline
        css_pattern = r'<style[^>]*>(.*?)</style>'
        css_blocks = re.findall(css_pattern, content, re.DOTALL)
        
        if len(css_blocks) > 1:
            # Consolidar CSS
            consolidated_css = '\n'.join(css_blocks)
            
            # Remover todos os blocos CSS
            content = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.DOTALL)
            
            # Adicionar CSS consolidado
            content = f'<style>\n{consolidated_css}\n</style>\n\n' + content
            corrections += 1
            
            self.log(f"Consolidados {len(css_blocks)} blocos CSS inline")
        
        return content, corrections
    
    def fix_multiple_inline_js(self, content):
        """Consolida JavaScript inline duplicado"""
        corrections = 0
        
        # Encontrar todos os blocos JS inline
        js_pattern = r'<script[^>]*>(.*?)</script>'
        js_blocks = re.findall(js_pattern, content, re.DOTALL)
        
        if len(js_blocks) > 1:
            # Consolidar JavaScript
            consolidated_js = '\n'.join(js_blocks)
            
            # Remover todos os blocos JS
            content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL)
            
            # Adicionar JS consolidado
            content = f'<script>\n{consolidated_js}\n</script>\n\n' + content
            corrections += 1
            
            self.log(f"Consolidados {len(js_blocks)} blocos JavaScript inline")
        
        return content, corrections
    
    def fix_excessive_blank_lines(self, content):
        """Remove linhas em branco excessivas"""
        corrections = 0
        
        # Encontrar linhas em branco excessivas
        blank_lines_pattern = r'\n\s*\n\s*\n+'
        matches = re.findall(blank_lines_pattern, content)
        
        if len(matches) > 5:
            # Reduzir para máximo 2 linhas em branco
            content = re.sub(blank_lines_pattern, '\n\n', content)
            corrections += 1
            
            self.log(f"Reduzidas linhas em branco excessivas")
        
        return content, corrections
    
    def fix_duplicate_comments(self, content):
        """Remove comentários duplicados"""
        corrections = 0
        
        # Encontrar todos os comentários
        comment_pattern = r'<!--.*?-->'
        comments = re.findall(comment_pattern, content, re.DOTALL)
        
        # Contar ocorrências
        comment_counts = Counter(comments)
        duplicate_comments = [comment for comment, count in comment_counts.items() if count > 1]
        
        for duplicate_comment in duplicate_comments:
            # Encontrar todas as ocorrências do comentário
            pattern = re.escape(duplicate_comment)
            matches = re.findall(pattern, content)
            
            if len(matches) > 1:
                # Manter apenas a primeira ocorrência
                first_match = matches[0]
                other_matches = matches[1:]
                
                for match in other_matches:
                    content = content.replace(match, '', 1)
                    corrections += 1
                
                self.log(f"Removidos {len(other_matches)} comentários duplicados")
        
        return content, corrections
    
    def fix_duplicate_imports(self, content):
        """Remove imports duplicados"""
        corrections = 0
        
        # Encontrar todos os imports
        import_pattern = r'{%\s*load\s+([^%]+)\s*%}'
        imports = re.findall(import_pattern, content)
        
        # Contar ocorrências
        import_counts = Counter(imports)
        duplicate_imports = [imp for imp, count in import_counts.items() if count > 1]
        
        for duplicate_import in duplicate_imports:
            # Encontrar todas as ocorrências do import
            pattern = rf'{{%\s*load\s+{re.escape(duplicate_import)}\s*%}}'
            matches = re.findall(pattern, content)
            
            if len(matches) > 1:
                # Manter apenas a primeira ocorrência
                first_match = matches[0]
                other_matches = matches[1:]
                
                for match in other_matches:
                    content = content.replace(match, '', 1)
                    corrections += 1
                
                self.log(f"Removidos {len(other_matches)} imports duplicados: {duplicate_import}")
        
        return content, corrections
    
    def fix_backup_files(self):
        """Remove arquivos de backup"""
        corrections = 0
        
        # Encontrar arquivos de backup
        backup_patterns = ['*backup*', '*old*', '*original*']
        
        for pattern in backup_patterns:
            backup_files = list(self.templates_dir.rglob(pattern))
            
            for backup_file in backup_files:
                try:
                    backup_file.unlink()
                    corrections += 1
                    self.log(f"Arquivo de backup removido: {backup_file}")
                except Exception as e:
                    self.log(f"Erro ao remover backup {backup_file}: {e}", "ERROR")
        
        return corrections
    
    def fix_template(self, file_path):
        """Aplica todas as correções em um template"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            total_corrections = 0
            
            # Aplicar todas as correções
            content, corrections = self.fix_duplicate_css_classes(content)
            total_corrections += corrections
            
            content, corrections = self.fix_duplicate_js_functions(content)
            total_corrections += corrections
            
            content, corrections = self.fix_duplicate_urls(content)
            total_corrections += corrections
            
            content, corrections = self.fix_duplicate_includes(content)
            total_corrections += corrections
            
            content, corrections = self.fix_multiple_forms(content)
            total_corrections += corrections
            
            content, corrections = self.fix_multiple_tables(content)
            total_corrections += corrections
            
            content, corrections = self.fix_multiple_inline_css(content)
            total_corrections += corrections
            
            content, corrections = self.fix_multiple_inline_js(content)
            total_corrections += corrections
            
            content, corrections = self.fix_excessive_blank_lines(content)
            total_corrections += corrections
            
            content, corrections = self.fix_duplicate_comments(content)
            total_corrections += corrections
            
            content, corrections = self.fix_duplicate_imports(content)
            total_corrections += corrections
            
            # Se houve correções, salvar o arquivo
            if total_corrections > 0:
                if not self.backup_file(file_path):
                    return 0
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                self.log(f"Correções aplicadas em {file_path}: {total_corrections}")
                self.corrections_applied.append({
                    'file': file_path,
                    'corrections': total_corrections
                })
            
            return total_corrections
            
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
        self.log(f"Correções aplicadas: {self.stats['corrections_applied']}")
        self.log(f"Backups criados: {self.stats['backups_created']}")
        self.log(f"Templates pulados: {self.stats['skipped']}")
        self.log(f"Erros encontrados: {self.stats['errors']}")
        
        if self.corrections_applied:
            self.log("\n=== CORREÇÕES APLICADAS ===")
            for correction in self.corrections_applied:
                self.log(f"{correction['file']}: {correction['corrections']} correções")
        
        if self.stats['errors'] == 0:
            self.log("CORREÇÃO DE REDUNDÂNCIAS CONCLUÍDA COM SUCESSO!", "SUCCESS")
        else:
            self.log(f"CORREÇÃO DE REDUNDÂNCIAS CONCLUÍDA COM {self.stats['errors']} ERROS", "WARNING")
    
    def run_corrections(self):
        """Executa correções completas"""
        self.log("=== INICIANDO CORREÇÃO DE REDUNDÂNCIAS ===")
        
        self.create_backup_dir()
        
        # Corrigir templates
        html_files = self.scan_templates()
        
        for file_path in html_files:
            corrections = self.fix_template(file_path)
            
            if corrections > 0:
                self.stats['corrections_applied'] += corrections
            
            self.stats['templates_processed'] += 1
        
        # Corrigir arquivos de backup
        backup_corrections = self.fix_backup_files()
        self.stats['corrections_applied'] += backup_corrections
        
        self.generate_report()

def main():
    print("=== SCRIPT DE CORREÇÃO AUTOMÁTICA DE REDUNDÂNCIAS ===")
    print("Corrigindo CSS duplicado, JavaScript duplicado, URLs duplicadas e outros problemas...")
    
    if not Path("templates").exists():
        print("ERRO: Diretório 'templates' não encontrado!")
        return
    
    fixer = RedundancyFixer()
    fixer.run_corrections()
    
    print("\n=== CORREÇÃO DE REDUNDÂNCIAS CONCLUÍDA ===")
    print("Verifique o arquivo 'correcoes_log.txt' para detalhes completos.")

if __name__ == "__main__":
    main()
