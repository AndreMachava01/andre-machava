#!/usr/bin/env python3
"""
Script para Verificação e Correção de Botões
Verifica e corrige problemas com botões em templates HTML
"""

import os
import re
import shutil
from pathlib import Path
from datetime import datetime
from collections import defaultdict, Counter

class ButtonChecker:
    def __init__(self, templates_dir="templates", static_dir="meuprojeto/empresa/static"):
        self.templates_dir = Path(templates_dir)
        self.static_dir = Path(static_dir)
        self.backup_dir = Path("backups_botoes")
        self.log_file = Path("botoes_verificacao_log.txt")
        self.stats = {
            'total_templates': 0,
            'templates_processed': 0,
            'buttons_found': 0,
            'buttons_fixed': 0,
            'backups_created': 0,
            'errors': 0,
            'skipped': 0
        }
        self.buttons_found = []
        self.problems_found = []
        
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
    
    def find_button_patterns(self, content):
        """Encontra padrões de botões no template"""
        buttons = []
        
        # Padrões de botões HTML
        patterns = [
            # Botões <button>
            r'<button[^>]*>.*?</button>',
            r'<button[^>]*/>',
            
            # Botões <input type="button">
            r'<input[^>]*type=["\']button["\'][^>]*>',
            r'<input[^>]*type=["\']submit["\'][^>]*>',
            r'<input[^>]*type=["\']reset["\'][^>]*>',
            
            # Links estilizados como botões
            r'<a[^>]*class=["\'][^"\']*btn[^"\']*["\'][^>]*>.*?</a>',
            r'<a[^>]*class=["\'][^"\']*button[^"\']*["\'][^>]*>.*?</a>',
            
            # Botões com onclick
            r'<[^>]*onclick=["\'][^"\']*["\'][^>]*>',
            
            # Botões Django forms
            r'<input[^>]*type=["\']submit["\'][^>]*value=["\'][^"\']*["\'][^>]*>',
            
            # Botões Bootstrap
            r'<[^>]*class=["\'][^"\']*btn-[^"\']*["\'][^>]*>',
            
            # Botões com data-attributes
            r'<[^>]*data-[^=]*=["\'][^"\']*["\'][^>]*>',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)
            for match in matches:
                buttons.append({
                    'pattern': pattern,
                    'content': match,
                    'type': self.classify_button_type(match)
                })
        
        return buttons
    
    def classify_button_type(self, button_content):
        """Classifica o tipo de botão"""
        if '<button' in button_content.lower():
            return 'button_tag'
        elif 'type="submit"' in button_content.lower():
            return 'submit_input'
        elif 'type="button"' in button_content.lower():
            return 'button_input'
        elif 'type="reset"' in button_content.lower():
            return 'reset_input'
        elif 'class=' in button_content.lower() and 'btn' in button_content.lower():
            return 'styled_button'
        elif 'onclick=' in button_content.lower():
            return 'clickable_element'
        else:
            return 'unknown'
    
    def find_button_problems(self, content):
        """Encontra problemas com botões"""
        problems = []
        
        # Problemas comuns
        problem_patterns = [
            # Botões sem texto ou conteúdo
            r'<button[^>]*></button>',
            r'<button[^>]*/>',
            r'<input[^>]*type=["\']button["\'][^>]*value=["\']["\'][^>]*>',
            r'<input[^>]*type=["\']submit["\'][^>]*value=["\']["\'][^>]*>',
            
            # Botões sem classes de estilo
            r'<button[^>]*(?!class=)[^>]*>',
            r'<input[^>]*type=["\']button["\'][^>]*(?!class=)[^>]*>',
            
            # Botões sem IDs únicos
            r'<button[^>]*(?!id=)[^>]*>',
            r'<input[^>]*type=["\']button["\'][^>]*(?!id=)[^>]*>',
            
            # Botões com onclick inline (má prática)
            r'<[^>]*onclick=["\'][^"\']*["\'][^>]*>',
            
            # Botões duplicados
            r'<button[^>]*id=["\']([^"\']*)["\'][^>]*>.*?<button[^>]*id=["\']\1["\'][^>]*>',
            
            # Botões com URLs quebradas
            r'<a[^>]*href=["\'][^"\']*["\'][^>]*class=["\'][^"\']*btn[^"\']*["\'][^>]*>',
            
            # Botões sem acessibilidade
            r'<button[^>]*(?!aria-label=)[^>]*(?!title=)[^>]*>',
            r'<input[^>]*type=["\']button["\'][^>]*(?!aria-label=)[^>]*(?!title=)[^>]*>',
            
            # Botões com estilos inline (má prática)
            r'<[^>]*style=["\'][^"\']*["\'][^>]*class=["\'][^"\']*btn[^"\']*["\'][^>]*>',
            
            # Botões sem responsividade
            r'<[^>]*class=["\'][^"\']*btn[^"\']*["\'][^>]*(?!btn-sm|btn-lg|btn-xs)[^>]*>',
        ]
        
        for pattern in problem_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)
            for match in matches:
                problems.append({
                    'pattern': pattern,
                    'content': match,
                    'type': self.classify_problem_type(pattern),
                    'severity': self.classify_problem_severity(pattern)
                })
        
        return problems
    
    def classify_problem_type(self, pattern):
        """Classifica o tipo de problema"""
        if 'onclick=' in pattern.lower():
            return 'inline_js'
        elif 'style=' in pattern.lower():
            return 'inline_styles'
        elif 'href=' in pattern.lower():
            return 'broken_links'
        elif 'aria-label=' in pattern.lower():
            return 'accessibility'
        elif 'class=' in pattern.lower():
            return 'styling'
        elif 'id=' in pattern.lower():
            return 'duplicate_ids'
        elif 'value=' in pattern.lower():
            return 'empty_content'
        else:
            return 'unknown'
    
    def classify_problem_severity(self, pattern):
        """Classifica a severidade do problema"""
        if 'onclick=' in pattern.lower():
            return 'high'
        elif 'style=' in pattern.lower():
            return 'high'
        elif 'aria-label=' in pattern.lower():
            return 'medium'
        elif 'class=' in pattern.lower():
            return 'medium'
        elif 'id=' in pattern.lower():
            return 'low'
        elif 'value=' in pattern.lower():
            return 'low'
        else:
            return 'unknown'
    
    def fix_button_problems(self, content):
        """Corrige problemas com botões"""
        corrections = 0
        
        # Correções comuns
        fixes = [
            # Adicionar classes de estilo padrão
            (r'<button([^>]*)(?!class=)([^>]*)>', r'<button\1 class="btn btn-primary"\2>'),
            (r'<input([^>]*)type=["\']button["\']([^>]*)(?!class=)([^>]*)>', r'<input\1type="button"\2 class="btn btn-secondary"\3>'),
            (r'<input([^>]*)type=["\']submit["\']([^>]*)(?!class=)([^>]*)>', r'<input\1type="submit"\2 class="btn btn-primary"\3>'),
            
            # Adicionar IDs únicos
            (r'<button([^>]*)(?!id=)([^>]*)>', r'<button\1 id="btn-{{ forloop.counter|default:"1" }}"\2>'),
            (r'<input([^>]*)type=["\']button["\']([^>]*)(?!id=)([^>]*)>', r'<input\1type="button"\2 id="btn-{{ forloop.counter|default:"1" }}"\3>'),
            
            # Adicionar acessibilidade
            (r'<button([^>]*)(?!aria-label=)([^>]*)(?!title=)([^>]*)>', r'<button\1 aria-label="Botão de ação"\2 title="Clique para executar ação"\3>'),
            (r'<input([^>]*)type=["\']button["\']([^>]*)(?!aria-label=)([^>]*)(?!title=)([^>]*)>', r'<input\1type="button"\2 aria-label="Botão de ação"\3 title="Clique para executar ação"\4>'),
            
            # Corrigir botões vazios
            (r'<button([^>]*)></button>', r'<button\1>Executar</button>'),
            (r'<button([^>]*)/>', r'<button\1>Executar</button>'),
            (r'<input([^>]*)type=["\']button["\']([^>]*)value=["\']["\']([^>]*)>', r'<input\1type="button"\2value="Executar"\3>'),
            (r'<input([^>]*)type=["\']submit["\']([^>]*)value=["\']["\']([^>]*)>', r'<input\1type="submit"\2value="Enviar"\3>'),
            
            # Adicionar responsividade
            (r'<([^>]*)class=["\']([^"\']*)btn([^"\']*)["\']([^>]*)>', r'<\1class="\2btn\3 btn-responsive"\4>'),
            
            # Remover estilos inline
            (r'<([^>]*)style=["\'][^"\']*["\']([^>]*)class=["\']([^"\']*)btn([^"\']*)["\']([^>]*)>', r'<\1\2class="\3btn\4"\5>'),
            
            # Corrigir URLs quebradas
            (r'<a([^>]*)href=["\'][^"\']*["\']([^>]*)class=["\']([^"\']*)btn([^"\']*)["\']([^>]*)>', r'<a\1href="#"\2class="\3btn\4"\5>'),
            
            # Adicionar tipos de botão específicos
            (r'<button([^>]*)class=["\']([^"\']*)btn([^"\']*)["\']([^>]*)>([^<]*)Salvar([^<]*)</button>', r'<button\1class="\2btn\3 btn-success"\4>\5Salvar\6</button>'),
            (r'<button([^>]*)class=["\']([^"\']*)btn([^"\']*)["\']([^>]*)>([^<]*)Excluir([^<]*)</button>', r'<button\1class="\2btn\3 btn-danger"\4>\5Excluir\6</button>'),
            (r'<button([^>]*)class=["\']([^"\']*)btn([^"\']*)["\']([^>]*)>([^<]*)Cancelar([^<]*)</button>', r'<button\1class="\2btn\3 btn-secondary"\4>\5Cancelar\6</button>'),
            (r'<button([^>]*)class=["\']([^"\']*)btn([^"\']*)["\']([^>]*)>([^<]*)Editar([^<]*)</button>', r'<button\1class="\2btn\3 btn-warning"\4>\5Editar\6</button>'),
        ]
        
        for pattern, replacement in fixes:
            matches = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)
            if matches:
                content = re.sub(pattern, replacement, content, flags=re.IGNORECASE | re.DOTALL)
                corrections += len(matches)
                self.log(f"Corrigidos {len(matches)} problemas com padrão: {pattern}")
        
        return content, corrections
    
    def fix_button_accessibility(self, content):
        """Corrige problemas de acessibilidade de botões"""
        corrections = 0
        
        # Correções de acessibilidade
        accessibility_fixes = [
            # Adicionar aria-label para botões sem texto
            (r'<button([^>]*)(?!aria-label=)([^>]*)>([^<]*)</button>', r'<button\1 aria-label="Botão de ação"\2>\3</button>'),
            (r'<input([^>]*)type=["\']button["\']([^>]*)(?!aria-label=)([^>]*)>', r'<input\1type="button"\2 aria-label="Botão de ação"\3>'),
            
            # Adicionar title para botões
            (r'<button([^>]*)(?!title=)([^>]*)>', r'<button\1 title="Clique para executar ação"\2>'),
            (r'<input([^>]*)type=["\']button["\']([^>]*)(?!title=)([^>]*)>', r'<input\1type="button"\2 title="Clique para executar ação"\3>'),
            
            # Adicionar role para elementos não-semânticos
            (r'<div([^>]*)class=["\']([^"\']*)btn([^"\']*)["\']([^>]*)>', r'<div\1class="\2btn\3"\4 role="button">'),
            (r'<span([^>]*)class=["\']([^"\']*)btn([^"\']*)["\']([^>]*)>', r'<span\1class="\2btn\3"\4 role="button">'),
            
            # Adicionar tabindex para elementos clicáveis
            (r'<([^>]*)onclick=["\'][^"\']*["\']([^>]*)(?!tabindex=)([^>]*)>', r'<\1onclick="\2" tabindex="0"\3>'),
        ]
        
        for pattern, replacement in accessibility_fixes:
            matches = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)
            if matches:
                content = re.sub(pattern, replacement, content, flags=re.IGNORECASE | re.DOTALL)
                corrections += len(matches)
                self.log(f"Corrigidos {len(matches)} problemas de acessibilidade com padrão: {pattern}")
        
        return content, corrections
    
    def fix_button_styling(self, content):
        """Corrige problemas de estilo de botões"""
        corrections = 0
        
        # Correções de estilo
        styling_fixes = [
            # Padronizar classes de botão
            (r'<([^>]*)class=["\']([^"\']*)button([^"\']*)["\']([^>]*)>', r'<\1class="\2btn\3"\4>'),
            (r'<([^>]*)class=["\']([^"\']*)btn-primary([^"\']*)["\']([^>]*)>', r'<\1class="\2btn btn-primary\3"\4>'),
            (r'<([^>]*)class=["\']([^"\']*)btn-secondary([^"\']*)["\']([^>]*)>', r'<\1class="\2btn btn-secondary\3"\4>'),
            (r'<([^>]*)class=["\']([^"\']*)btn-success([^"\']*)["\']([^>]*)>', r'<\1class="\2btn btn-success\3"\4>'),
            (r'<([^>]*)class=["\']([^"\']*)btn-danger([^"\']*)["\']([^>]*)>', r'<\1class="\2btn btn-danger\3"\4>'),
            (r'<([^>]*)class=["\']([^"\']*)btn-warning([^"\']*)["\']([^>]*)>', r'<\1class="\2btn btn-warning\3"\4>'),
            (r'<([^>]*)class=["\']([^"\']*)btn-info([^"\']*)["\']([^>]*)>', r'<\1class="\2btn btn-info\3"\4>'),
            
            # Adicionar tamanhos responsivos
            (r'<([^>]*)class=["\']([^"\']*)btn([^"\']*)["\']([^>]*)>', r'<\1class="\2btn\3 btn-responsive"\4>'),
            
            # Remover estilos inline
            (r'<([^>]*)style=["\'][^"\']*["\']([^>]*)class=["\']([^"\']*)btn([^"\']*)["\']([^>]*)>', r'<\1\2class="\3btn\4"\5>'),
        ]
        
        for pattern, replacement in styling_fixes:
            matches = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)
            if matches:
                content = re.sub(pattern, replacement, content, flags=re.IGNORECASE | re.DOTALL)
                corrections += len(matches)
                self.log(f"Corrigidos {len(matches)} problemas de estilo com padrão: {pattern}")
        
        return content, corrections
    
    def fix_button_functionality(self, content):
        """Corrige problemas de funcionalidade de botões"""
        corrections = 0
        
        # Correções de funcionalidade
        functionality_fixes = [
            # Corrigir URLs quebradas
            (r'<a([^>]*)href=["\'][^"\']*["\']([^>]*)class=["\']([^"\']*)btn([^"\']*)["\']([^>]*)>', r'<a\1href="#"\2class="\3btn\4"\5>'),
            
            # Adicionar preventDefault para links
            (r'<a([^>]*)href=["\'][^"\']*["\']([^>]*)onclick=["\'][^"\']*["\']([^>]*)>', r'<a\1href="#"\2onclick="event.preventDefault(); \3"\4>'),
            
            # Corrigir formulários sem action
            (r'<form([^>]*)(?!action=)([^>]*)>', r'<form\1action="."\2>'),
            
            # Adicionar method para formulários
            (r'<form([^>]*)(?!method=)([^>]*)>', r'<form\1method="post"\2>'),
            
            # Adicionar CSRF token
            (r'<form([^>]*)>', r'<form\1>{% csrf_token %}'),
        ]
        
        for pattern, replacement in functionality_fixes:
            matches = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)
            if matches:
                content = re.sub(pattern, replacement, content, flags=re.IGNORECASE | re.DOTALL)
                corrections += len(matches)
                self.log(f"Corrigidos {len(matches)} problemas de funcionalidade com padrão: {pattern}")
        
        return content, corrections
    
    def fix_template(self, file_path):
        """Aplica todas as correções em um template"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            total_corrections = 0
            
            # Encontrar botões
            buttons = self.find_button_patterns(content)
            problems = self.find_button_problems(content)
            
            self.stats['buttons_found'] += len(buttons)
            
            # Aplicar correções
            content, corrections = self.fix_button_problems(content)
            total_corrections += corrections
            
            content, corrections = self.fix_button_accessibility(content)
            total_corrections += corrections
            
            content, corrections = self.fix_button_styling(content)
            total_corrections += corrections
            
            content, corrections = self.fix_button_functionality(content)
            total_corrections += corrections
            
            # Se houve correções, salvar o arquivo
            if total_corrections > 0:
                if not self.backup_file(file_path):
                    return 0
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                self.log(f"Correções aplicadas em {file_path}: {total_corrections}")
                self.buttons_found.append({
                    'file': file_path,
                    'buttons': len(buttons),
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
        self.log(f"Botões encontrados: {self.stats['buttons_found']}")
        self.log(f"Botões corrigidos: {self.stats['buttons_fixed']}")
        self.log(f"Backups criados: {self.stats['backups_created']}")
        self.log(f"Templates pulados: {self.stats['skipped']}")
        self.log(f"Erros encontrados: {self.stats['errors']}")
        
        if self.buttons_found:
            self.log("\n=== BOTÕES ENCONTRADOS ===")
            for button in self.buttons_found:
                self.log(f"{button['file']}: {button['buttons']} botões, {button['problems']} problemas, {button['corrections']} correções")
        
        if self.stats['errors'] == 0:
            self.log("VERIFICAÇÃO DE BOTÕES CONCLUÍDA COM SUCESSO!", "SUCCESS")
        else:
            self.log(f"VERIFICAÇÃO DE BOTÕES CONCLUÍDA COM {self.stats['errors']} ERROS", "WARNING")
    
    def run_verification(self):
        """Executa verificação completa"""
        self.log("=== INICIANDO VERIFICAÇÃO DE BOTÕES ===")
        
        self.create_backup_dir()
        
        # Verificar templates
        html_files = self.scan_templates()
        
        for file_path in html_files:
            corrections = self.fix_template(file_path)
            
            if corrections > 0:
                self.stats['buttons_fixed'] += corrections
            
            self.stats['templates_processed'] += 1
        
        self.generate_report()

def main():
    print("=== SCRIPT DE VERIFICAÇÃO E CORREÇÃO DE BOTÕES ===")
    print("Verificando e corrigindo problemas com botões...")
    
    if not Path("templates").exists():
        print("ERRO: Diretório 'templates' não encontrado!")
        return
    
    checker = ButtonChecker()
    checker.run_verification()
    
    print("\n=== VERIFICAÇÃO DE BOTÕES CONCLUÍDA ===")
    print("Verifique o arquivo 'botoes_verificacao_log.txt' para detalhes completos.")

if __name__ == "__main__":
    main()
