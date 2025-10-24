#!/usr/bin/env python3
"""
Script para Verificação de Redundâncias e Sobreposições
Detecta código duplicado, templates redundantes e sobreposições de funcionalidades
"""

import os
import re
import shutil
from pathlib import Path
from datetime import datetime
from collections import defaultdict, Counter

class RedundancyChecker:
    def __init__(self, templates_dir="templates", static_dir="meuprojeto/empresa/static"):
        self.templates_dir = Path(templates_dir)
        self.static_dir = Path(static_dir)
        self.backup_dir = Path("backups_redundancias")
        self.log_file = Path("redundancias_verificacao_log.txt")
        self.stats = {
            'total_templates': 0,
            'templates_checked': 0,
            'redundancies_found': 0,
            'redundancies_fixed': 0,
            'backups_created': 0,
            'errors': 0,
            'skipped': 0
        }
        self.redundancies_found = []
        self.code_patterns = defaultdict(list)
        
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
    
    def extract_code_patterns(self, content, file_path):
        """Extrai padrões de código para detectar redundâncias"""
        patterns = {}
        
        # Padrões de CSS
        css_patterns = re.findall(r'\.([a-zA-Z0-9_-]+)\s*{[^}]*}', content, re.DOTALL)
        patterns['css_classes'] = css_patterns
        
        # Padrões de JavaScript
        js_functions = re.findall(r'function\s+([a-zA-Z0-9_]+)\s*\([^)]*\)', content)
        patterns['js_functions'] = js_functions
        
        # Padrões de Django templates
        template_tags = re.findall(r'{%\s*([a-zA-Z0-9_]+)', content)
        patterns['template_tags'] = template_tags
        
        # Padrões de includes
        includes = re.findall(r"{%\s*include\s+['\"]([^'\"]+)['\"]", content)
        patterns['includes'] = includes
        
        # Padrões de URLs
        urls = re.findall(r"{%\s*url\s+['\"]([^'\"]+)['\"]", content)
        patterns['urls'] = urls
        
        # Padrões de formulários
        forms = re.findall(r'<form[^>]*>', content)
        patterns['forms'] = forms
        
        # Padrões de tabelas
        tables = re.findall(r'<table[^>]*>', content)
        patterns['tables'] = tables
        
        # Padrões de filtros
        filters = re.findall(r'<input[^>]*name="[^"]*filter[^"]*"[^>]*>', content)
        patterns['filters'] = filters
        
        return patterns
    
    def detect_template_redundancies(self, file_path):
        """Detecta redundâncias em templates"""
        redundancies = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            patterns = self.extract_code_patterns(content, file_path)
            
            # Verificar CSS duplicado
            css_classes = patterns.get('css_classes', [])
            for css_class in css_classes:
                if css_class in self.code_patterns['css_classes']:
                    redundancies.append({
                        'type': 'duplicate_css',
                        'description': f'Classe CSS duplicada: {css_class}',
                        'severity': 'medium',
                        'pattern': css_class
                    })
                else:
                    self.code_patterns['css_classes'].append(css_class)
            
            # Verificar JavaScript duplicado
            js_functions = patterns.get('js_functions', [])
            for js_func in js_functions:
                if js_func in self.code_patterns['js_functions']:
                    redundancies.append({
                        'type': 'duplicate_js',
                        'description': f'Função JavaScript duplicada: {js_func}',
                        'severity': 'high',
                        'pattern': js_func
                    })
                else:
                    self.code_patterns['js_functions'].append(js_func)
            
            # Verificar includes duplicados
            includes = patterns.get('includes', [])
            for include in includes:
                if include in self.code_patterns['includes']:
                    redundancies.append({
                        'type': 'duplicate_include',
                        'description': f'Include duplicado: {include}',
                        'severity': 'low',
                        'pattern': include
                    })
                else:
                    self.code_patterns['includes'].append(include)
            
            # Verificar URLs duplicadas
            urls = patterns.get('urls', [])
            for url in urls:
                if url in self.code_patterns['urls']:
                    redundancies.append({
                        'type': 'duplicate_url',
                        'description': f'URL duplicada: {url}',
                        'severity': 'medium',
                        'pattern': url
                    })
                else:
                    self.code_patterns['urls'].append(url)
            
            # Verificar formulários duplicados
            forms = patterns.get('forms', [])
            if len(forms) > 1:
                redundancies.append({
                    'type': 'multiple_forms',
                    'description': f'Múltiplos formulários no mesmo template: {len(forms)}',
                    'severity': 'high',
                    'pattern': f'{len(forms)} forms'
                })
            
            # Verificar tabelas duplicadas
            tables = patterns.get('tables', [])
            if len(tables) > 1:
                redundancies.append({
                    'type': 'multiple_tables',
                    'description': f'Múltiplas tabelas no mesmo template: {len(tables)}',
                    'severity': 'medium',
                    'pattern': f'{len(tables)} tables'
                })
            
            # Verificar filtros duplicados
            filters = patterns.get('filters', [])
            if len(filters) > 1:
                redundancies.append({
                    'type': 'multiple_filters',
                    'description': f'Múltiplos filtros no mesmo template: {len(filters)}',
                    'severity': 'high',
                    'pattern': f'{len(filters)} filters'
                })
            
            # Verificar código CSS/JS inline duplicado
            inline_css = re.findall(r'<style[^>]*>.*?</style>', content, re.DOTALL)
            if len(inline_css) > 1:
                redundancies.append({
                    'type': 'multiple_inline_css',
                    'description': f'Múltiplos blocos CSS inline: {len(inline_css)}',
                    'severity': 'medium',
                    'pattern': f'{len(inline_css)} css blocks'
                })
            
            inline_js = re.findall(r'<script[^>]*>.*?</script>', content, re.DOTALL)
            if len(inline_js) > 1:
                redundancies.append({
                    'type': 'multiple_inline_js',
                    'description': f'Múltiplos blocos JavaScript inline: {len(inline_js)}',
                    'severity': 'medium',
                    'pattern': f'{len(inline_js)} js blocks'
                })
            
            # Verificar comentários duplicados
            comments = re.findall(r'<!--.*?-->', content, re.DOTALL)
            comment_texts = [c.strip() for c in comments]
            duplicate_comments = [text for text, count in Counter(comment_texts).items() if count > 1]
            for comment in duplicate_comments:
                redundancies.append({
                    'type': 'duplicate_comment',
                    'description': f'Comentário duplicado: {comment[:50]}...',
                    'severity': 'low',
                    'pattern': comment
                })
            
            # Verificar linhas em branco excessivas
            blank_lines = re.findall(r'\n\s*\n\s*\n', content)
            if len(blank_lines) > 5:
                redundancies.append({
                    'type': 'excessive_blank_lines',
                    'description': f'Linhas em branco excessivas: {len(blank_lines)}',
                    'severity': 'low',
                    'pattern': f'{len(blank_lines)} blank lines'
                })
            
            # Verificar imports duplicados
            imports = re.findall(r'{%\s*load\s+([^%]+)\s*%}', content)
            duplicate_imports = [imp for imp, count in Counter(imports).items() if count > 1]
            for imp in duplicate_imports:
                redundancies.append({
                    'type': 'duplicate_import',
                    'description': f'Import duplicado: {imp}',
                    'severity': 'medium',
                    'pattern': imp
                })
            
        except Exception as e:
            self.log(f"Erro ao analisar template {file_path}: {e}", "ERROR")
            return []
        
        return redundancies
    
    def detect_file_redundancies(self):
        """Detecta arquivos redundantes"""
        redundancies = []
        
        # Verificar arquivos com nomes similares
        html_files = list(self.templates_dir.rglob("*.html"))
        file_names = [f.stem for f in html_files]
        
        # Agrupar por nome base
        name_groups = defaultdict(list)
        for file_path in html_files:
            base_name = file_path.stem
            # Remover sufixos comuns
            base_name = re.sub(r'_(main|list|detail|form|delete|create|edit)$', '', base_name)
            name_groups[base_name].append(file_path)
        
        # Verificar grupos com múltiplos arquivos
        for base_name, files in name_groups.items():
            if len(files) > 1:
                redundancies.append({
                    'type': 'similar_files',
                    'description': f'Arquivos com nomes similares: {base_name}',
                    'severity': 'medium',
                    'files': files,
                    'pattern': base_name
                })
        
        # Verificar arquivos de backup
        backup_files = list(self.templates_dir.rglob("*backup*"))
        backup_files.extend(list(self.templates_dir.rglob("*old*")))
        backup_files.extend(list(self.templates_dir.rglob("*original*")))
        
        for backup_file in backup_files:
            redundancies.append({
                'type': 'backup_file',
                'description': f'Arquivo de backup encontrado: {backup_file.name}',
                'severity': 'low',
                'file': backup_file,
                'pattern': 'backup'
            })
        
        return redundancies
    
    def detect_static_redundancies(self):
        """Detecta redundâncias em arquivos estáticos"""
        redundancies = []
        
        if not self.static_dir.exists():
            return redundancies
        
        # Verificar CSS duplicado
        css_files = list(self.static_dir.rglob("*.css"))
        css_content = {}
        
        for css_file in css_files:
            try:
                with open(css_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                css_content[css_file] = content
            except Exception as e:
                self.log(f"Erro ao ler CSS {css_file}: {e}", "ERROR")
        
        # Verificar conteúdo CSS duplicado
        for file1, content1 in css_content.items():
            for file2, content2 in css_content.items():
                if file1 != file2 and content1 == content2:
                    redundancies.append({
                        'type': 'duplicate_css_file',
                        'description': f'Arquivos CSS idênticos: {file1.name} e {file2.name}',
                        'severity': 'high',
                        'files': [file1, file2],
                        'pattern': 'identical css'
                    })
        
        # Verificar JavaScript duplicado
        js_files = list(self.static_dir.rglob("*.js"))
        js_content = {}
        
        for js_file in js_files:
            try:
                with open(js_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                js_content[js_file] = content
            except Exception as e:
                self.log(f"Erro ao ler JS {js_file}: {e}", "ERROR")
        
        # Verificar conteúdo JS duplicado
        for file1, content1 in js_content.items():
            for file2, content2 in js_content.items():
                if file1 != file2 and content1 == content2:
                    redundancies.append({
                        'type': 'duplicate_js_file',
                        'description': f'Arquivos JavaScript idênticos: {file1.name} e {file2.name}',
                        'severity': 'high',
                        'files': [file1, file2],
                        'pattern': 'identical js'
                    })
        
        return redundancies
    
    def fix_redundancies(self, content, file_path, redundancies):
        """Corrige redundâncias encontradas"""
        fixed_content = content
        fixes_applied = 0
        
        for redundancy in redundancies:
            try:
                if redundancy['type'] == 'multiple_forms':
                    # Manter apenas o primeiro formulário
                    forms = re.findall(r'<form[^>]*>.*?</form>', fixed_content, re.DOTALL)
                    if len(forms) > 1:
                        for form in forms[1:]:
                            fixed_content = fixed_content.replace(form, '')
                        fixes_applied += 1
                
                elif redundancy['type'] == 'multiple_tables':
                    # Manter apenas a primeira tabela
                    tables = re.findall(r'<table[^>]*>.*?</table>', fixed_content, re.DOTALL)
                    if len(tables) > 1:
                        for table in tables[1:]:
                            fixed_content = fixed_content.replace(table, '')
                        fixes_applied += 1
                
                elif redundancy['type'] == 'multiple_filters':
                    # Manter apenas o primeiro filtro
                    filters = re.findall(r'<input[^>]*name="[^"]*filter[^"]*"[^>]*>', fixed_content)
                    if len(filters) > 1:
                        for filter_input in filters[1:]:
                            fixed_content = fixed_content.replace(filter_input, '')
                        fixes_applied += 1
                
                elif redundancy['type'] == 'multiple_inline_css':
                    # Consolidar CSS inline
                    css_blocks = re.findall(r'<style[^>]*>(.*?)</style>', fixed_content, re.DOTALL)
                    if len(css_blocks) > 1:
                        consolidated_css = '\n'.join(css_blocks)
                        # Remover todos os blocos CSS
                        fixed_content = re.sub(r'<style[^>]*>.*?</style>', '', fixed_content, flags=re.DOTALL)
                        # Adicionar CSS consolidado
                        fixed_content = f'<style>\n{consolidated_css}\n</style>\n\n' + fixed_content
                        fixes_applied += 1
                
                elif redundancy['type'] == 'multiple_inline_js':
                    # Consolidar JavaScript inline
                    js_blocks = re.findall(r'<script[^>]*>(.*?)</script>', fixed_content, re.DOTALL)
                    if len(js_blocks) > 1:
                        consolidated_js = '\n'.join(js_blocks)
                        # Remover todos os blocos JS
                        fixed_content = re.sub(r'<script[^>]*>.*?</script>', '', fixed_content, flags=re.DOTALL)
                        # Adicionar JS consolidado
                        fixed_content = f'<script>\n{consolidated_js}\n</script>\n\n' + fixed_content
                        fixes_applied += 1
                
                elif redundancy['type'] == 'duplicate_comment':
                    # Remover comentários duplicados
                    comments = re.findall(r'<!--.*?-->', fixed_content, re.DOTALL)
                    seen_comments = set()
                    for comment in comments:
                        if comment in seen_comments:
                            fixed_content = fixed_content.replace(comment, '', 1)
                        else:
                            seen_comments.add(comment)
                    fixes_applied += 1
                
                elif redundancy['type'] == 'excessive_blank_lines':
                    # Reduzir linhas em branco excessivas
                    fixed_content = re.sub(r'\n\s*\n\s*\n+', '\n\n', fixed_content)
                    fixes_applied += 1
                
                elif redundancy['type'] == 'duplicate_import':
                    # Remover imports duplicados
                    imports = re.findall(r'{%\s*load\s+([^%]+)\s*%}', fixed_content)
                    seen_imports = set()
                    for imp in imports:
                        if imp in seen_imports:
                            fixed_content = re.sub(r'{%\s*load\s+' + re.escape(imp) + r'\s*%}', '', fixed_content)
                        else:
                            seen_imports.add(imp)
                    fixes_applied += 1
                
            except Exception as e:
                self.log(f"Erro ao aplicar correção {redundancy['type']}: {e}", "ERROR")
        
        return fixed_content, fixes_applied
    
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
        self.log(f"Templates verificados: {self.stats['templates_checked']}")
        self.log(f"Redundâncias encontradas: {self.stats['redundancies_found']}")
        self.log(f"Redundâncias corrigidas: {self.stats['redundancies_fixed']}")
        self.log(f"Backups criados: {self.stats['backups_created']}")
        self.log(f"Templates pulados: {self.stats['skipped']}")
        self.log(f"Erros encontrados: {self.stats['errors']}")
        
        if self.redundancies_found:
            self.log("\n=== REDUNDÂNCIAS ENCONTRADAS ===")
            for file_path, redundancy in self.redundancies_found:
                self.log(f"{file_path}: {redundancy['type']} - {redundancy['description']} ({redundancy['severity']})")
        
        if self.stats['errors'] == 0:
            self.log("VERIFICAÇÃO DE REDUNDÂNCIAS CONCLUÍDA COM SUCESSO!", "SUCCESS")
        else:
            self.log(f"VERIFICAÇÃO DE REDUNDÂNCIAS CONCLUÍDA COM {self.stats['errors']} ERROS", "WARNING")
    
    def run_verification(self):
        """Executa verificação completa"""
        self.log("=== INICIANDO VERIFICAÇÃO DE REDUNDÂNCIAS ===")
        
        self.create_backup_dir()
        
        # Verificar templates
        html_files = self.scan_templates()
        
        for file_path in html_files:
            redundancies = self.detect_template_redundancies(file_path)
            
            if redundancies:
                self.stats['redundancies_found'] += len(redundancies)
                self.redundancies_found.extend([(file_path, redundancy) for redundancy in redundancies])
                
                self.log(f"Redundâncias encontradas em {file_path}: {len(redundancies)}")
                for redundancy in redundancies:
                    self.log(f"  - {redundancy['type']}: {redundancy['description']} ({redundancy['severity']})")
                
                if not self.backup_file(file_path):
                    continue
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    fixed_content, fixes_applied = self.fix_redundancies(content, file_path, redundancies)
                    
                    if fixes_applied > 0:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(fixed_content)
                        
                        self.stats['redundancies_fixed'] += fixes_applied
                        self.log(f"Redundâncias corrigidas em {file_path}: {fixes_applied}")
                
                except Exception as e:
                    self.stats['errors'] += 1
                    self.log(f"Erro ao corrigir redundâncias em {file_path}: {e}", "ERROR")
            
            self.stats['templates_checked'] += 1
        
        # Verificar arquivos redundantes
        file_redundancies = self.detect_file_redundancies()
        for redundancy in file_redundancies:
            self.stats['redundancies_found'] += 1
            self.redundancies_found.append((None, redundancy))
            self.log(f"Redundância de arquivo: {redundancy['description']} ({redundancy['severity']})")
        
        # Verificar arquivos estáticos
        static_redundancies = self.detect_static_redundancies()
        for redundancy in static_redundancies:
            self.stats['redundancies_found'] += 1
            self.redundancies_found.append((None, redundancy))
            self.log(f"Redundância estática: {redundancy['description']} ({redundancy['severity']})")
        
        self.generate_report()

def main():
    print("=== SCRIPT DE VERIFICAÇÃO DE REDUNDÂNCIAS E SOBREPOSIÇÕES ===")
    print("Verificando código duplicado, templates redundantes e sobreposições...")
    
    if not Path("templates").exists():
        print("ERRO: Diretório 'templates' não encontrado!")
        return
    
    checker = RedundancyChecker()
    checker.run_verification()
    
    print("\n=== VERIFICAÇÃO DE REDUNDÂNCIAS CONCLUÍDA ===")
    print("Verifique o arquivo 'redundancias_verificacao_log.txt' para detalhes completos.")

if __name__ == "__main__":
    main()
