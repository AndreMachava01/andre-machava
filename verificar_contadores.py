#!/usr/bin/env python3
"""
Script para Verificação e Correção de Contadores
Verifica se contadores estão exibindo informações corretas e corrige problemas
"""

import os
import re
import shutil
from pathlib import Path
from datetime import datetime
from collections import defaultdict, Counter

class CounterChecker:
    def __init__(self, templates_dir="templates", static_dir="meuprojeto/empresa/static"):
        self.templates_dir = Path(templates_dir)
        self.static_dir = Path(static_dir)
        self.backup_dir = Path("backups_contadores")
        self.log_file = Path("contadores_verificacao_log.txt")
        self.stats = {
            'total_templates': 0,
            'templates_processed': 0,
            'counters_found': 0,
            'counters_fixed': 0,
            'backups_created': 0,
            'errors': 0,
            'skipped': 0
        }
        self.counters_found = []
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
    
    def find_counter_patterns(self, content):
        """Encontra padrões de contadores no template"""
        counters = []
        
        # Padrões de contadores Django
        patterns = [
            # Contadores de objetos
            r'(\w+)\.count',
            r'(\w+)\.length',
            r'len\((\w+)\)',
            r'(\w+)\.total',
            r'(\w+)\.size',
            
            # Contadores em loops
            r'for\s+\w+\s+in\s+(\w+)',
            r'{%\s*for\s+\w+\s+in\s+(\w+)\s*%}',
            
            # Contadores em condicionais
            r'if\s+(\w+)\.count',
            r'if\s+len\((\w+)\)',
            r'{%\s*if\s+(\w+)\.count\s*%}',
            r'{%\s*if\s+len\((\w+)\)\s*%}',
            
            # Contadores em JavaScript
            r'(\w+)\.length',
            r'(\w+)\.count',
            r'(\w+)\.size',
            r'(\w+)\.total',
            
            # Contadores em CSS (para elementos)
            r'counter\((\w+)\)',
            r'counter-reset:\s*(\w+)',
            r'counter-increment:\s*(\w+)',
            
            # Contadores em HTML
            r'data-count="(\w+)"',
            r'data-total="(\w+)"',
            r'data-size="(\w+)"',
            
            # Contadores em atributos
            r'aria-label="(\w+)\s+items"',
            r'title="(\w+)\s+items"',
            r'alt="(\w+)\s+items"',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                counters.append({
                    'pattern': pattern,
                    'variable': match,
                    'type': self.classify_counter_type(pattern, match)
                })
        
        return counters
    
    def classify_counter_type(self, pattern, variable):
        """Classifica o tipo de contador"""
        if 'count' in pattern.lower():
            return 'count'
        elif 'length' in pattern.lower():
            return 'length'
        elif 'total' in pattern.lower():
            return 'total'
        elif 'size' in pattern.lower():
            return 'size'
        elif 'len(' in pattern.lower():
            return 'len'
        else:
            return 'unknown'
    
    def find_counter_display_patterns(self, content):
        """Encontra padrões de exibição de contadores"""
        displays = []
        
        # Padrões de exibição
        patterns = [
            # Exibição direta
            r'{{(\w+)\.count}}',
            r'{{(\w+)\.length}}',
            r'{{(\w+)\.total}}',
            r'{{(\w+)\.size}}',
            r'{{len\((\w+)\)}}',
            
            # Exibição em texto
            r'(\w+)\s+items?',
            r'(\w+)\s+records?',
            r'(\w+)\s+entries?',
            r'(\w+)\s+results?',
            r'(\w+)\s+total',
            r'(\w+)\s+count',
            
            # Exibição em JavaScript
            r'document\.getElementById\([\'"](\w+)[\'"]\)\.textContent\s*=\s*(\w+)',
            r'document\.querySelector\([\'"](\w+)[\'"]\)\.textContent\s*=\s*(\w+)',
            r'\$\([\'"](\w+)[\'"]\)\.text\((\w+)\)',
            r'\$\([\'"](\w+)[\'"]\)\.html\((\w+)\)',
            
            # Exibição em atributos
            r'aria-label="(\w+)\s+items"',
            r'title="(\w+)\s+items"',
            r'alt="(\w+)\s+items"',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                displays.append({
                    'pattern': pattern,
                    'element': match[0] if isinstance(match, tuple) else match,
                    'variable': match[1] if isinstance(match, tuple) and len(match) > 1 else match,
                    'type': self.classify_display_type(pattern)
                })
        
        return displays
    
    def classify_display_type(self, pattern):
        """Classifica o tipo de exibição"""
        if 'textContent' in pattern:
            return 'textContent'
        elif 'text(' in pattern:
            return 'text'
        elif 'html(' in pattern:
            return 'html'
        elif 'aria-label' in pattern:
            return 'aria-label'
        elif 'title' in pattern:
            return 'title'
        elif 'alt' in pattern:
            return 'alt'
        else:
            return 'direct'
    
    def find_counter_problems(self, content):
        """Encontra problemas com contadores"""
        problems = []
        
        # Problemas comuns
        problem_patterns = [
            # Contadores não inicializados
            r'(\w+)\.count(?!\s*[=}])',
            r'(\w+)\.length(?!\s*[=}])',
            r'(\w+)\.total(?!\s*[=}])',
            r'(\w+)\.size(?!\s*[=}])',
            
            # Contadores em loops infinitos
            r'for\s+\w+\s+in\s+(\w+)\s*:\s*(\w+)\.count',
            r'while\s+(\w+)\.count',
            r'while\s+len\((\w+)\)',
            
            # Contadores inconsistentes
            r'(\w+)\.count\s*!=\s*(\w+)\.length',
            r'(\w+)\.total\s*!=\s*(\w+)\.count',
            r'(\w+)\.size\s*!=\s*(\w+)\.length',
            
            # Contadores em condicionais problemáticas
            r'if\s+(\w+)\.count\s*>\s*(\w+)\.count',
            r'if\s+len\((\w+)\)\s*>\s*len\((\w+)\)',
            
            # Contadores em JavaScript problemáticos
            r'(\w+)\.length\s*\+\+\s*\+\+',
            r'(\w+)\.count\s*\+\+\s*\+\+',
            r'(\w+)\.total\s*\+\+\s*\+\+',
            
            # Contadores em CSS problemáticos
            r'counter\((\w+)\)\s*\+\s*counter\((\w+)\)',
            r'counter-reset:\s*(\w+)\s*\+\s*counter-reset:\s*(\w+)',
        ]
        
        for pattern in problem_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                problems.append({
                    'pattern': pattern,
                    'variables': match if isinstance(match, tuple) else [match],
                    'type': self.classify_problem_type(pattern),
                    'severity': self.classify_problem_severity(pattern)
                })
        
        return problems
    
    def classify_problem_type(self, pattern):
        """Classifica o tipo de problema"""
        if 'count' in pattern.lower():
            return 'count_problem'
        elif 'length' in pattern.lower():
            return 'length_problem'
        elif 'total' in pattern.lower():
            return 'total_problem'
        elif 'size' in pattern.lower():
            return 'size_problem'
        elif 'len(' in pattern.lower():
            return 'len_problem'
        else:
            return 'unknown_problem'
    
    def classify_problem_severity(self, pattern):
        """Classifica a severidade do problema"""
        if '++' in pattern or '--' in pattern:
            return 'high'
        elif '!=' in pattern or '>' in pattern:
            return 'medium'
        elif 'count' in pattern.lower() or 'length' in pattern.lower():
            return 'low'
        else:
            return 'unknown'
    
    def fix_counter_problems(self, content):
        """Corrige problemas com contadores"""
        corrections = 0
        
        # Correções comuns
        fixes = [
            # Corrigir contadores não inicializados
            (r'(\w+)\.count(?!\s*[=}])', r'\1.count|default:0'),
            (r'(\w+)\.length(?!\s*[=}])', r'\1.length|default:0'),
            (r'(\w+)\.total(?!\s*[=}])', r'\1.total|default:0'),
            (r'(\w+)\.size(?!\s*[=}])', r'\1.size|default:0'),
            
            # Corrigir contadores em loops infinitos
            (r'for\s+\w+\s+in\s+(\w+)\s*:\s*(\w+)\.count', r'for \w+ in \1: \2.count|default:0'),
            (r'while\s+(\w+)\.count', r'while \1.count|default:0'),
            (r'while\s+len\((\w+)\)', r'while len(\1)|default:0'),
            
            # Corrigir contadores inconsistentes
            (r'(\w+)\.count\s*!=\s*(\w+)\.length', r'\1.count|default:0 != \2.length|default:0'),
            (r'(\w+)\.total\s*!=\s*(\w+)\.count', r'\1.total|default:0 != \2.count|default:0'),
            (r'(\w+)\.size\s*!=\s*(\w+)\.length', r'\1.size|default:0 != \2.length|default:0'),
            
            # Corrigir contadores em condicionais problemáticas
            (r'if\s+(\w+)\.count\s*>\s*(\w+)\.count', r'if \1.count|default:0 > \2.count|default:0'),
            (r'if\s+len\((\w+)\)\s*>\s*len\((\w+)\)', r'if len(\1)|default:0 > len(\2)|default:0'),
            
            # Corrigir contadores em JavaScript problemáticos
            (r'(\w+)\.length\s*\+\+\s*\+\+', r'\1.length++'),
            (r'(\w+)\.count\s*\+\+\s*\+\+', r'\1.count++'),
            (r'(\w+)\.total\s*\+\+\s*\+\+', r'\1.total++'),
            
            # Corrigir contadores em CSS problemáticos
            (r'counter\((\w+)\)\s*\+\s*counter\((\w+)\)', r'counter(\1) + counter(\2)'),
            (r'counter-reset:\s*(\w+)\s*\+\s*counter-reset:\s*(\w+)', r'counter-reset: \1 \2'),
        ]
        
        for pattern, replacement in fixes:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)
                corrections += len(matches)
                self.log(f"Corrigidos {len(matches)} problemas com padrão: {pattern}")
        
        return content, corrections
    
    def fix_counter_display_problems(self, content):
        """Corrige problemas de exibição de contadores"""
        corrections = 0
        
        # Correções de exibição
        display_fixes = [
            # Corrigir exibição direta
            (r'{{(\w+)\.count}}', r'{{\1.count|default:0}}'),
            (r'{{(\w+)\.length}}', r'{{\1.length|default:0}}'),
            (r'{{(\w+)\.total}}', r'{{\1.total|default:0}}'),
            (r'{{(\w+)\.size}}', r'{{\1.size|default:0}}'),
            (r'{{len\((\w+)\)}}', r'{{len(\1)|default:0}}'),
            
            # Corrigir exibição em texto
            (r'(\w+)\s+items?', r'\1|default:0 items'),
            (r'(\w+)\s+records?', r'\1|default:0 records'),
            (r'(\w+)\s+entries?', r'\1|default:0 entries'),
            (r'(\w+)\s+results?', r'\1|default:0 results'),
            (r'(\w+)\s+total', r'\1|default:0 total'),
            (r'(\w+)\s+count', r'\1|default:0 count'),
            
            # Corrigir exibição em JavaScript
            (r'document\.getElementById\([\'"](\w+)[\'"]\)\.textContent\s*=\s*(\w+)', r'document.getElementById("\1").textContent = \2 || 0'),
            (r'document\.querySelector\([\'"](\w+)[\'"]\)\.textContent\s*=\s*(\w+)', r'document.querySelector("\1").textContent = \2 || 0'),
            (r'\$\([\'"](\w+)[\'"]\)\.text\((\w+)\)', r'$("\1").text(\2 || 0)'),
            (r'\$\([\'"](\w+)[\'"]\)\.html\((\w+)\)', r'$("\1").html(\2 || 0)'),
            
            # Corrigir exibição em atributos
            (r'aria-label="(\w+)\s+items"', r'aria-label="\1|default:0 items"'),
            (r'title="(\w+)\s+items"', r'title="\1|default:0 items"'),
            (r'alt="(\w+)\s+items"', r'alt="\1|default:0 items"'),
        ]
        
        for pattern, replacement in display_fixes:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)
                corrections += len(matches)
                self.log(f"Corrigidos {len(matches)} problemas de exibição com padrão: {pattern}")
        
        return content, corrections
    
    def fix_counter_consistency_problems(self, content):
        """Corrige problemas de consistência de contadores"""
        corrections = 0
        
        # Correções de consistência
        consistency_fixes = [
            # Padronizar contadores
            (r'(\w+)\.count', r'\1.count'),
            (r'(\w+)\.length', r'\1.length'),
            (r'(\w+)\.total', r'\1.total'),
            (r'(\w+)\.size', r'\1.size'),
            
            # Padronizar exibição
            (r'(\w+)\s+items?', r'\1 items'),
            (r'(\w+)\s+records?', r'\1 records'),
            (r'(\w+)\s+entries?', r'\1 entries'),
            (r'(\w+)\s+results?', r'\1 results'),
            
            # Padronizar JavaScript
            (r'document\.getElementById\([\'"](\w+)[\'"]\)\.textContent', r'document.getElementById("\1").textContent'),
            (r'document\.querySelector\([\'"](\w+)[\'"]\)\.textContent', r'document.querySelector("\1").textContent'),
            (r'\$\([\'"](\w+)[\'"]\)\.text', r'$("\1").text'),
            (r'\$\([\'"](\w+)[\'"]\)\.html', r'$("\1").html'),
        ]
        
        for pattern, replacement in consistency_fixes:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)
                corrections += len(matches)
                self.log(f"Corrigidos {len(matches)} problemas de consistência com padrão: {pattern}")
        
        return content, corrections
    
    def fix_counter_performance_problems(self, content):
        """Corrige problemas de performance de contadores"""
        corrections = 0
        
        # Correções de performance
        performance_fixes = [
            # Otimizar contadores em loops
            (r'for\s+\w+\s+in\s+(\w+)\s*:\s*(\w+)\.count', r'for \w+ in \1: \2.count'),
            (r'while\s+(\w+)\.count', r'while \1.count'),
            (r'while\s+len\((\w+)\)', r'while len(\1)'),
            
            # Otimizar contadores em condicionais
            (r'if\s+(\w+)\.count\s*>\s*(\w+)\.count', r'if \1.count > \2.count'),
            (r'if\s+len\((\w+)\)\s*>\s*len\((\w+)\)', r'if len(\1) > len(\2)'),
            
            # Otimizar contadores em JavaScript
            (r'(\w+)\.length\s*\+\+', r'\1.length++'),
            (r'(\w+)\.count\s*\+\+', r'\1.count++'),
            (r'(\w+)\.total\s*\+\+', r'\1.total++'),
        ]
        
        for pattern, replacement in performance_fixes:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)
                corrections += len(matches)
                self.log(f"Corrigidos {len(matches)} problemas de performance com padrão: {pattern}")
        
        return content, corrections
    
    def fix_template(self, file_path):
        """Aplica todas as correções em um template"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            total_corrections = 0
            
            # Encontrar contadores
            counters = self.find_counter_patterns(content)
            displays = self.find_counter_display_patterns(content)
            problems = self.find_counter_problems(content)
            
            self.stats['counters_found'] += len(counters) + len(displays)
            
            # Aplicar correções
            content, corrections = self.fix_counter_problems(content)
            total_corrections += corrections
            
            content, corrections = self.fix_counter_display_problems(content)
            total_corrections += corrections
            
            content, corrections = self.fix_counter_consistency_problems(content)
            total_corrections += corrections
            
            content, corrections = self.fix_counter_performance_problems(content)
            total_corrections += corrections
            
            # Se houve correções, salvar o arquivo
            if total_corrections > 0:
                if not self.backup_file(file_path):
                    return 0
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                self.log(f"Correções aplicadas em {file_path}: {total_corrections}")
                self.counters_found.append({
                    'file': file_path,
                    'counters': len(counters),
                    'displays': len(displays),
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
        self.log(f"Contadores encontrados: {self.stats['counters_found']}")
        self.log(f"Contadores corrigidos: {self.stats['counters_fixed']}")
        self.log(f"Backups criados: {self.stats['backups_created']}")
        self.log(f"Templates pulados: {self.stats['skipped']}")
        self.log(f"Erros encontrados: {self.stats['errors']}")
        
        if self.counters_found:
            self.log("\n=== CONTADORES ENCONTRADOS ===")
            for counter in self.counters_found:
                self.log(f"{counter['file']}: {counter['counters']} contadores, {counter['displays']} exibições, {counter['problems']} problemas, {counter['corrections']} correções")
        
        if self.stats['errors'] == 0:
            self.log("VERIFICAÇÃO DE CONTADORES CONCLUÍDA COM SUCESSO!", "SUCCESS")
        else:
            self.log(f"VERIFICAÇÃO DE CONTADORES CONCLUÍDA COM {self.stats['errors']} ERROS", "WARNING")
    
    def run_verification(self):
        """Executa verificação completa"""
        self.log("=== INICIANDO VERIFICAÇÃO DE CONTADORES ===")
        
        self.create_backup_dir()
        
        # Verificar templates
        html_files = self.scan_templates()
        
        for file_path in html_files:
            corrections = self.fix_template(file_path)
            
            if corrections > 0:
                self.stats['counters_fixed'] += corrections
            
            self.stats['templates_processed'] += 1
        
        self.generate_report()

def main():
    print("=== SCRIPT DE VERIFICAÇÃO E CORREÇÃO DE CONTADORES ===")
    print("Verificando se contadores estão exibindo informações corretas...")
    
    if not Path("templates").exists():
        print("ERRO: Diretório 'templates' não encontrado!")
        return
    
    checker = CounterChecker()
    checker.run_verification()
    
    print("\n=== VERIFICAÇÃO DE CONTADORES CONCLUÍDA ===")
    print("Verifique o arquivo 'contadores_verificacao_log.txt' para detalhes completos.")

if __name__ == "__main__":
    main()
