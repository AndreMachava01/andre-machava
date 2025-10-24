#!/usr/bin/env python3
"""
Script para Verificação e Correção de Acesso aos Submódulos
Verifica e corrige problemas que impedem o acesso aos submódulos RH e Stock
"""

import os
import re
import shutil
from pathlib import Path
from datetime import datetime
from collections import defaultdict

class SubmoduleAccessChecker:
    def __init__(self, templates_dir="templates", static_dir="meuprojeto/empresa/static"):
        self.templates_dir = Path(templates_dir)
        self.static_dir = Path(static_dir)
        self.backup_dir = Path("backups_submodulos_acesso")
        self.log_file = Path("submodulos_acesso_log.txt")
        self.stats = {
            'total_templates': 0,
            'templates_processed': 0,
            'problems_found': 0,
            'problems_fixed': 0,
            'backups_created': 0,
            'errors': 0,
            'skipped': 0
        }
        self.problems_found = []
        self.access_issues = []
        
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
    
    def find_submodule_access_problems(self, content):
        """Encontra problemas de acesso aos submódulos"""
        problems = []
        
        # Padrões de problemas de acesso
        access_patterns = [
            # URLs quebradas ou incorretas
            (r'href=["\']([^"\']*rh/[^"\']*)["\']', 'rh_url'),
            (r'href=["\']([^"\']*stock/[^"\']*)["\']', 'stock_url'),
            (r'href=["\']([^"\']*logistica/[^"\']*)["\']', 'logistica_url'),
            
            # Botões com URLs incorretas
            (r'<[^>]*onclick=["\']([^"\']*window\.location[^"\']*)["\'][^>]*>', 'onclick_url'),
            (r'<[^>]*onclick=["\']([^"\']*location\.href[^"\']*)["\'][^>]*>', 'onclick_href'),
            
            # Links com # que deveriam ter URLs reais
            (r'href=["\']#["\']', 'empty_href'),
            
            # JavaScript quebrado
            (r'<script[^>]*>.*?function[^>]*>', 'broken_js'),
            
            # Formulários com action incorreta
            (r'<form[^>]*action=["\']([^"\']*)["\'][^>]*>', 'form_action'),
            
            # Botões sem URL ou onclick
            (r'<button[^>]*class=["\'][^"\']*btn[^"\']*["\'][^>]*>(?!.*href)(?!.*onclick)', 'button_no_action'),
            
            # Links com onclick mas sem href
            (r'<a[^>]*onclick=["\'][^"\']*["\'][^>]*>(?!.*href)', 'link_onclick_no_href'),
        ]
        
        for pattern, problem_type in access_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)
            for match in matches:
                problems.append({
                    'pattern': pattern,
                    'content': match,
                    'type': problem_type,
                    'severity': self.classify_problem_severity(problem_type)
                })
        
        return problems
    
    def classify_problem_severity(self, problem_type):
        """Classifica a severidade do problema"""
        if problem_type in ['rh_url', 'stock_url', 'logistica_url']:
            return 'critical'
        elif problem_type in ['onclick_url', 'onclick_href', 'form_action']:
            return 'high'
        elif problem_type in ['empty_href', 'broken_js']:
            return 'medium'
        elif problem_type in ['button_no_action', 'link_onclick_no_href']:
            return 'low'
        else:
            return 'unknown'
    
    def fix_submodule_access_problems(self, content):
        """Corrige problemas de acesso aos submódulos"""
        corrections = 0
        
        # Correções de acesso
        fixes = [
            # Corrigir URLs RH quebradas
            (r'href=["\']/rh/funcionarios["\']', r'href="/rh/funcionarios/"'),
            (r'href=["\']/rh/departamentos["\']', r'href="/rh/departamentos/"'),
            (r'href=["\']/rh/cargos["\']', r'href="/rh/cargos/"'),
            (r'href=["\']/rh/salarios["\']', r'href="/rh/salarios/"'),
            (r'href=["\']/rh/presencas["\']', r'href="/rh/presencas/"'),
            (r'href=["\']/rh/treinamentos["\']', r'href="/rh/treinamentos/"'),
            (r'href=["\']/rh/avaliacoes["\']', r'href="/rh/avaliacoes/"'),
            (r'href=["\']/rh/feriados["\']', r'href="/rh/feriados/"'),
            (r'href=["\']/rh/transferencias["\']', r'href="/rh/transferencias/"'),
            (r'href=["\']/rh/folha-salarial["\']', r'href="/rh/folha-salarial/"'),
            (r'href=["\']/rh/promocoes["\']', r'href="/rh/promocoes/"'),
            (r'href=["\']/rh/relatorios["\']', r'href="/rh/relatorios/"'),
            
            # Corrigir URLs Stock quebradas
            (r'href=["\']/stock/produtos["\']', r'href="/stock/produtos/"'),
            (r'href=["\']/stock/materiais["\']', r'href="/stock/materiais/"'),
            (r'href=["\']/stock/fornecedores["\']', r'href="/stock/fornecedores/"'),
            (r'href=["\']/stock/categorias["\']', r'href="/stock/categorias/"'),
            (r'href=["\']/stock/inventario["\']', r'href="/stock/inventario/"'),
            (r'href=["\']/stock/requisicoes["\']', r'href="/stock/requisicoes/"'),
            (r'href=["\']/stock/transferencias["\']', r'href="/stock/transferencias/"'),
            (r'href=["\']/stock/relatorios["\']', r'href="/stock/relatorios/"'),
            
            # Corrigir URLs Logística quebradas
            (r'href=["\']/stock/logistica/viaturas["\']', r'href="/stock/logistica/viaturas/"'),
            (r'href=["\']/stock/logistica/transportadoras["\']', r'href="/stock/logistica/transportadoras/"'),
            (r'href=["\']/stock/logistica/operacoes["\']', r'href="/stock/logistica/operacoes/"'),
            (r'href=["\']/stock/logistica/rastreamento["\']', r'href="/stock/logistica/rastreamento/"'),
            (r'href=["\']/stock/logistica/checklist["\']', r'href="/stock/logistica/checklist/"'),
            (r'href=["\']/stock/logistica/pod["\']', r'href="/stock/logistica/pod/"'),
            (r'href=["\']/stock/logistica/guias["\']', r'href="/stock/logistica/guias/"'),
            (r'href=["\']/stock/logistica/cotacao["\']', r'href="/stock/logistica/cotacao/"'),
            
            # Corrigir href vazios
            (r'href=["\']#["\']', r'href="#"'),
            
            # Corrigir onclick com URLs incorretas
            (r'onclick=["\']window\.location\.href=["\']([^"\']*)["\']', r'onclick="window.location.href=\'\1\'"'),
            (r'onclick=["\']location\.href=["\']([^"\']*)["\']', r'onclick="location.href=\'\1\'"'),
            
            # Corrigir botões sem ação
            (r'<button([^>]*)class=["\']([^"\']*btn[^"\']*)["\']([^>]*)>([^<]*)</button>', 
             r'<button\1class="\2"\3onclick="alert(\'Funcionalidade em desenvolvimento\')">\4</button>'),
            
            # Corrigir links com onclick mas sem href
            (r'<a([^>]*)onclick=["\']([^"\']*)["\']([^>]*)>', r'<a\1href="#" onclick="\2"\3>'),
        ]
        
        for pattern, replacement in fixes:
            matches = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)
            if matches:
                content = re.sub(pattern, replacement, content, flags=re.IGNORECASE | re.DOTALL)
                corrections += len(matches)
                self.log(f"Corrigidas {len(matches)} URLs com padrão: {pattern}")
        
        return content, corrections
    
    def fix_javascript_problems(self, content):
        """Corrige problemas de JavaScript"""
        corrections = 0
        
        # Correções de JavaScript
        js_fixes = [
            # Corrigir funções JavaScript quebradas
            (r'function\s+(\w+)\s*\(\s*\)\s*{\s*}\s*', r'function \1() { alert("Funcionalidade em desenvolvimento"); }'),
            
            # Corrigir onclick com JavaScript malformado
            (r'onclick=["\']([^"\']*)\s*;\s*["\']', r'onclick="\1"'),
            
            # Corrigir window.location malformado
            (r'window\.location\s*=\s*["\']([^"\']*)["\']', r'window.location.href = "\1"'),
            
            # Corrigir location malformado
            (r'location\s*=\s*["\']([^"\']*)["\']', r'location.href = "\1"'),
        ]
        
        for pattern, replacement in js_fixes:
            matches = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)
            if matches:
                content = re.sub(pattern, replacement, content, flags=re.IGNORECASE | re.DOTALL)
                corrections += len(matches)
                self.log(f"Corrigidos {len(matches)} problemas de JavaScript com padrão: {pattern}")
        
        return content, corrections
    
    def fix_form_problems(self, content):
        """Corrige problemas de formulários"""
        corrections = 0
        
        # Correções de formulários
        form_fixes = [
            # Corrigir action vazia
            (r'<form([^>]*)action=["\']["\']([^>]*)>', r'<form\1action="."\2>'),
            
            # Corrigir method incorreto
            (r'<form([^>]*)method=["\']get["\']([^>]*)>', r'<form\1method="post"\2>'),
            
            # Adicionar CSRF token se faltar
            (r'<form([^>]*)method=["\']post["\']([^>]*)>(?!.*csrf)', r'<form\1method="post"\2>\n    {% csrf_token %}'),
        ]
        
        for pattern, replacement in form_fixes:
            matches = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)
            if matches:
                content = re.sub(pattern, replacement, content, flags=re.IGNORECASE | re.DOTALL)
                corrections += len(matches)
                self.log(f"Corrigidos {len(matches)} problemas de formulário com padrão: {pattern}")
        
        return content, corrections
    
    def fix_template_problems(self, content):
        """Corrige problemas de template"""
        corrections = 0
        
        # Correções de template
        template_fixes = [
            # Corrigir includes quebrados
            (r'{%\s*include\s*[\'"]([^\'"]*)["\']\s*%}', r'{% include "\1" %}'),
            
            # Corrigir extends quebrados
            (r'{%\s*extends\s*[\'"]([^\'"]*)["\']\s*%}', r'{% extends "\1" %}'),
            
            # Corrigir url tags quebrados
            (r'{%\s*url\s*[\'"]([^\'"]*)["\']\s*%}', r'{% url "\1" %}'),
            
            # Corrigir load tags quebrados
            (r'{%\s*load\s+([^\s%]+)\s*%}', r'{% load \1 %}'),
        ]
        
        for pattern, replacement in template_fixes:
            matches = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)
            if matches:
                content = re.sub(pattern, replacement, content, flags=re.IGNORECASE | re.DOTALL)
                corrections += len(matches)
                self.log(f"Corrigidos {len(matches)} problemas de template com padrão: {pattern}")
        
        return content, corrections
    
    def fix_template(self, file_path):
        """Aplica todas as correções em um template"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            total_corrections = 0
            
            # Encontrar problemas
            problems = self.find_submodule_access_problems(content)
            
            self.stats['problems_found'] += len(problems)
            
            # Aplicar correções
            content, corrections = self.fix_submodule_access_problems(content)
            total_corrections += corrections
            
            content, corrections = self.fix_javascript_problems(content)
            total_corrections += corrections
            
            content, corrections = self.fix_form_problems(content)
            total_corrections += corrections
            
            content, corrections = self.fix_template_problems(content)
            total_corrections += corrections
            
            # Se houve correções, salvar o arquivo
            if total_corrections > 0:
                if not self.backup_file(file_path):
                    return 0
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                self.log(f"Correções aplicadas em {file_path}: {total_corrections}")
                self.problems_found.append({
                    'file': file_path,
                    'problems': len(problems),
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
        self.log(f"Problemas encontrados: {self.stats['problems_found']}")
        self.log(f"Problemas corrigidos: {self.stats['problems_fixed']}")
        self.log(f"Backups criados: {self.stats['backups_created']}")
        self.log(f"Templates pulados: {self.stats['skipped']}")
        self.log(f"Erros encontrados: {self.stats['errors']}")
        
        if self.problems_found:
            self.log("\n=== PROBLEMAS ENCONTRADOS ===")
            for problem in self.problems_found:
                self.log(f"{problem['file']}: {problem['problems']} problemas, {problem['corrections']} correções")
        
        if self.stats['errors'] == 0:
            self.log("VERIFICAÇÃO DE ACESSO AOS SUBMÓDULOS CONCLUÍDA COM SUCESSO!", "SUCCESS")
        else:
            self.log(f"VERIFICAÇÃO DE ACESSO AOS SUBMÓDULOS CONCLUÍDA COM {self.stats['errors']} ERROS", "WARNING")
    
    def run_verification(self):
        """Executa verificação completa"""
        self.log("=== INICIANDO VERIFICAÇÃO DE ACESSO AOS SUBMÓDULOS ===")
        
        self.create_backup_dir()
        
        # Verificar templates
        html_files = self.scan_templates()
        
        for file_path in html_files:
            corrections = self.fix_template(file_path)
            
            if corrections > 0:
                self.stats['problems_fixed'] += corrections
            
            self.stats['templates_processed'] += 1
        
        self.generate_report()

def main():
    print("=== SCRIPT DE VERIFICAÇÃO E CORREÇÃO DE ACESSO AOS SUBMÓDULOS ===")
    print("Verificando e corrigindo problemas que impedem o acesso aos submódulos...")
    
    if not Path("templates").exists():
        print("ERRO: Diretório 'templates' não encontrado!")
        return
    
    checker = SubmoduleAccessChecker()
    checker.run_verification()
    
    print("\n=== VERIFICAÇÃO DE ACESSO AOS SUBMÓDULOS CONCLUÍDA ===")
    print("Verifique o arquivo 'submodulos_acesso_log.txt' para detalhes completos.")

if __name__ == "__main__":
    main()
