#!/usr/bin/env python3
"""
Script Avançado para Verificação e Correção de Filtros de Pesquisa
Detecta problemas específicos e aplica correções automáticas
"""

import os
import re
import shutil
from pathlib import Path
from datetime import datetime

class FilterVerifier:
    def __init__(self, templates_dir="templates"):
        self.templates_dir = Path(templates_dir)
        self.backup_dir = Path("backups_filtros_verificacao")
        self.log_file = Path("filtros_verificacao_log.txt")
        self.stats = {
            'total_templates': 0,
            'templates_checked': 0,
            'problems_found': 0,
            'problems_fixed': 0,
            'backups_created': 0,
            'errors': 0,
            'skipped': 0
        }
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
    
    def is_list_template(self, file_path):
        list_patterns = ['main.html', 'list.html', 'lista.html', 'index.html']
        exclude_patterns = [
            'base_admin.html', 'base_list.html', 'form.html', 'detail.html',
            'delete.html', 'create.html', 'edit.html', 'print.html',
            'documento.html', 'relatorio.html', 'calendario.html',
            'dashboard.html', 'login.html', 'filters_unified.html',
            'page_header.html', 'change_form.html', 'change_list.html'
        ]
        
        filename = file_path.name.lower()
        
        for exclude in exclude_patterns:
            if exclude in filename:
                return False
        
        for pattern in list_patterns:
            if pattern in filename:
                return True
                
        return False
    
    def backup_template(self, file_path):
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
    
    def detect_filter_problems(self, content, file_path):
        problems = []
        
        # Problema 1: Filtros antigos não removidos
        old_filter_patterns = [
            r'<form[^>]*class="[^"]*filter[^"]*"[^>]*>',
            r'<div[^>]*class="[^"]*filter[^"]*"[^>]*>',
            r'<input[^>]*name="[^"]*search[^"]*"[^>]*>',
            r'<select[^>]*name="[^"]*filter[^"]*"[^>]*>',
            r'<div[^>]*class="[^"]*search[^"]*"[^>]*>',
            r'<div[^>]*class="[^"]*filtros[^"]*"[^>]*>',
            r'<!-- FILTROS[^>]*-->',
            r'FILTROS[^>]*REMOVIDO'
        ]
        
        for pattern in old_filter_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                problems.append({
                    'type': 'old_filters',
                    'description': 'Filtros antigos não removidos',
                    'pattern': pattern,
                    'severity': 'high'
                })
        
        # Problema 2: Filtros unificados malformados
        malformed_patterns = [
            r'{% include [\'"]filters_unified\.html[\'"] %}',
            r'{% include [\'"]includes/filters_unified\.html[\'"] %}',
            r'filters_unified\.html'
        ]
        
        unified_found = False
        for pattern in malformed_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                unified_found = True
                break
        
        if unified_found:
            # Verificar se está correto
            correct_pattern = r'{% include [\'"]includes/filters_unified\.html[\'"] with entity_name=[\'"][^\'"]+[\'"] %}'
            if not re.search(correct_pattern, content, re.IGNORECASE):
                problems.append({
                    'type': 'malformed_unified',
                    'description': 'Filtros unificados malformados',
                    'severity': 'medium'
                })
        
        # Problema 3: Faltam filtros unificados em templates de lista
        if self.is_list_template(file_path) and not unified_found:
            problems.append({
                'type': 'missing_unified',
                'description': 'Faltam filtros unificados',
                'severity': 'high'
            })
        
        # Problema 4: Entity name incorreto ou ausente
        if unified_found:
            entity_pattern = r'entity_name=[\'"]([^\'"]+)[\'"]'
            match = re.search(entity_pattern, content, re.IGNORECASE)
            if not match:
                problems.append({
                    'type': 'missing_entity',
                    'description': 'Entity name ausente',
                    'severity': 'medium'
                })
            else:
                entity_name = match.group(1)
                if entity_name in ['', 'default', 'template']:
                    problems.append({
                        'type': 'invalid_entity',
                        'description': f'Entity name inválido: {entity_name}',
                        'severity': 'medium'
                    })
        
        # Problema 5: CSS/JS de filtros antigos
        old_css_js_patterns = [
            r'\.filter[^>]*{[^}]*}',
            r'\.search[^>]*{[^}]*}',
            r'function[^>]*filter[^>]*\([^)]*\)',
            r'function[^>]*search[^>]*\([^)]*\)'
        ]
        
        for pattern in old_css_js_patterns:
            if re.search(pattern, content, re.IGNORECASE | re.DOTALL):
                problems.append({
                    'type': 'old_css_js',
                    'description': 'CSS/JS de filtros antigos encontrado',
                    'severity': 'low'
                })
        
        # Problema 6: Filtros duplicados
        unified_count = len(re.findall(r'filters_unified\.html', content, re.IGNORECASE))
        if unified_count > 1:
            problems.append({
                'type': 'duplicate_filters',
                'description': f'Filtros unificados duplicados ({unified_count} vezes)',
                'severity': 'high'
            })
        
        return problems
    
    def get_entity_name_from_path(self, file_path):
        path_str = str(file_path).lower()
        
        patterns = [
            r'/([^/]+)/main\.html$',
            r'/([^/]+)/list\.html$',
            r'/([^/]+)/lista\.html$'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, path_str)
            if match:
                entity = match.group(1)
                entity_map = {
            'funcionarios': 'funcionarios',
            'cargos': 'cargos',
            'departamentos': 'departamentos',
            'presencas': 'presencas',
            'treinamentos': 'treinamentos',
            'avaliacoes': 'avaliacoes',
            'feriados': 'feriados',
            'transferencias': 'transferencias',
                    'folha_salarial': 'folha_salarial',
                    'salarios': 'salarios',
                    'promocoes': 'promocoes',
            'produtos': 'produtos',
            'materiais': 'materiais',
            'fornecedores': 'fornecedores',
            'categorias': 'categorias',
            'inventario': 'inventario',
            'requisicoes': 'requisicoes',
                    'notificacoes': 'notificacoes',
                    'movimentos': 'movimentos',
                    'alertas': 'alertas',
                    'operacoes': 'operacoes_logisticas',
                    'checklist': 'checklists',
                    'coletas': 'coletas',
                    'rastreamento': 'rastreamento',
                    'transportadoras': 'transportadoras',
            'viaturas': 'viaturas',
                    'veiculos': 'veiculos',
                    'etiquetas': 'etiquetas_pod',
                    'guias': 'guias_pod',
                    'provas': 'provas_pod',
                    'ordens_compra': 'ordens_compra',
                    'por_sucursal': 'por_sucursal',
                    'sucursal_detail': 'stock_sucursal_detail',
                    'verificar_stock_baixo': 'stock_baixo',
                    'ajustes_list': 'ajustes_inventario',
                    'horas_extras_lista': 'horas_extras',
                    'detalhes_mes': 'detalhes_presenca',
                    'inscricoes': 'inscricoes_treinamento',
                    'inscrever': 'treinamentos_inscrever',
                    'relatorio': 'transferencias_relatorio',
                    'beneficios': 'beneficios_salario',
                    'descontos': 'descontos_salario',
                    'criterios': 'criterios_avaliacao'
                }
                return entity_map.get(entity, entity)
        
        return 'default'
    
    def fix_filter_problems(self, content, file_path, problems):
        fixed_content = content
        fixes_applied = 0
        
        for problem in problems:
            try:
                if problem['type'] == 'old_filters':
                    # Remover filtros antigos
                    old_filter_patterns = [
                        r'<!-- FILTROS[^>]*-->.*?(?=\n\n|\n{%|\n<div|\n<form|\Z)',
                        r'<form[^>]*class="[^"]*filter[^"]*"[^>]*>.*?</form>',
                        r'<div[^>]*class="[^"]*filter[^"]*"[^>]*>.*?</div>',
                        r'<div[^>]*class="[^"]*search[^"]*"[^>]*>.*?</div>',
                        r'<div[^>]*class="[^"]*filtros[^"]*"[^>]*>.*?</div>',
                        r'<!-- FILTROS[^>]*REMOVIDO[^>]*-->.*?(?=\n\n|\n{%|\n<div|\Z)',
                        r'FILTROS[^>]*REMOVIDO[^>]*USAR[^>]*SISTEMA[^>]*UNIFICADO.*?(?=\n\n|\n{%|\n<div|\Z)'
                    ]
                    
                    for pattern in old_filter_patterns:
                        fixed_content = re.sub(pattern, '', fixed_content, flags=re.IGNORECASE | re.DOTALL)
                    
                    fixes_applied += 1
                
                elif problem['type'] == 'malformed_unified':
                    # Corrigir filtros unificados malformados
                    entity_name = self.get_entity_name_from_path(file_path)
                    correct_unified = f'{{% include \'includes/filters_unified.html\' with entity_name=\'{entity_name}\' %}}'
                    
                    malformed_patterns = [
                        r'{% include [\'"]filters_unified\.html[\'"] %}',
                        r'{% include [\'"]includes/filters_unified\.html[\'"] %}'
                    ]
                    
                    for pattern in malformed_patterns:
                        fixed_content = re.sub(pattern, correct_unified, fixed_content, flags=re.IGNORECASE)
                    
                    fixes_applied += 1
                
                elif problem['type'] == 'missing_unified':
                    # Adicionar filtros unificados
                    entity_name = self.get_entity_name_from_path(file_path)
                    unified_filter = f'''<!-- FILTROS UNIFICADOS -->
{{% include 'includes/filters_unified.html' with entity_name='{entity_name}' %}}'''
                    
                    extends_pattern = r'({% extends [\'"][^\'"]+[\'"] %})'
                    if re.search(extends_pattern, fixed_content):
                        fixed_content = re.sub(
                            extends_pattern,
                            r'\1\n\n' + unified_filter,
                            fixed_content,
                            count=1
                        )
                    else:
                        fixed_content = unified_filter + '\n\n' + fixed_content
                    
                    fixes_applied += 1
                
                elif problem['type'] == 'missing_entity':
                    # Adicionar entity name
                    entity_name = self.get_entity_name_from_path(file_path)
                    fixed_content = re.sub(
                        r'{% include [\'"]includes/filters_unified\.html[\'"] %}',
                        f'{{% include \'includes/filters_unified.html\' with entity_name=\'{entity_name}\' %}}',
                        fixed_content,
                        flags=re.IGNORECASE
                    )
                    fixes_applied += 1
                
                elif problem['type'] == 'invalid_entity':
                    # Corrigir entity name
                    entity_name = self.get_entity_name_from_path(file_path)
                    fixed_content = re.sub(
                        r'entity_name=[\'"][^\'"]+[\'"]',
                        f'entity_name=\'{entity_name}\'',
                        fixed_content,
                        flags=re.IGNORECASE
                    )
                    fixes_applied += 1
                
                elif problem['type'] == 'old_css_js':
                    # Remover CSS/JS antigo
                    old_css_js_patterns = [
                        r'<style[^>]*>.*?\.filter[^>]*{[^}]*}.*?</style>',
                        r'<style[^>]*>.*?\.search[^>]*{[^}]*}.*?</style>',
                        r'<script[^>]*>.*?function[^>]*filter[^>]*\([^)]*\).*?</script>',
                        r'<script[^>]*>.*?function[^>]*search[^>]*\([^)]*\).*?</script>'
                    ]
                    
                    for pattern in old_css_js_patterns:
                        fixed_content = re.sub(pattern, '', fixed_content, flags=re.IGNORECASE | re.DOTALL)
                    
                    fixes_applied += 1
                
                elif problem['type'] == 'duplicate_filters':
                    # Remover filtros duplicados
                    unified_pattern = r'{% include [\'"]includes/filters_unified\.html[\'"] with entity_name=[\'"][^\'"]+[\'"] %}'
                    matches = list(re.finditer(unified_pattern, fixed_content, re.IGNORECASE))
                    
                    if len(matches) > 1:
                        # Manter apenas o primeiro
                        for match in reversed(matches[1:]):
                            fixed_content = fixed_content[:match.start()] + fixed_content[match.end():]
                    
                    fixes_applied += 1
                
            except Exception as e:
                self.log(f"Erro ao aplicar correção {problem['type']}: {e}", "ERROR")
        
        # Limpar linhas vazias extras
        fixed_content = re.sub(r'\n\s*\n\s*\n', '\n\n', fixed_content)
        
        return fixed_content, fixes_applied
    
    def verify_template_filters(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            problems = self.detect_filter_problems(content, file_path)
            
            if not problems:
                self.log(f"Sem problemas encontrados: {file_path}")
                return True
            
            self.stats['problems_found'] += len(problems)
            self.problems_found.extend([(file_path, problem) for problem in problems])
            
            self.log(f"Problemas encontrados em {file_path}: {len(problems)}")
            for problem in problems:
                self.log(f"  - {problem['type']}: {problem['description']} ({problem['severity']})")
            
            if not self.backup_template(file_path):
                return False
            
            fixed_content, fixes_applied = self.fix_filter_problems(content, file_path, problems)
            
            if fixes_applied > 0:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(fixed_content)
                
                self.stats['problems_fixed'] += fixes_applied
                self.log(f"Problemas corrigidos em {file_path}: {fixes_applied}")
                return True
            else:
                self.log(f"Nenhuma correção aplicada em {file_path}", "WARNING")
                return False
            
        except Exception as e:
            self.stats['errors'] += 1
            self.log(f"Erro ao verificar filtros de {file_path}: {e}", "ERROR")
            return False
    
    def scan_templates(self):
        html_files = list(self.templates_dir.rglob("*.html"))
        self.stats['total_templates'] = len(html_files)
        
        self.log(f"Encontrados {len(html_files)} templates HTML")
        
        templates_to_check = []
        
        for file_path in html_files:
            if self.is_list_template(file_path):
                templates_to_check.append(file_path)
            else:
                self.stats['skipped'] += 1
                self.log(f"Pulando (não é lista): {file_path}")
        
        return templates_to_check
    
    def generate_report(self):
        self.log("=== RELATÓRIO FINAL ===")
        self.log(f"Total de templates encontrados: {self.stats['total_templates']}")
        self.log(f"Templates verificados: {self.stats['templates_checked']}")
        self.log(f"Problemas encontrados: {self.stats['problems_found']}")
        self.log(f"Problemas corrigidos: {self.stats['problems_fixed']}")
        self.log(f"Backups criados: {self.stats['backups_created']}")
        self.log(f"Templates pulados: {self.stats['skipped']}")
        self.log(f"Erros encontrados: {self.stats['errors']}")
        
        if self.problems_found:
            self.log("\n=== PROBLEMAS ENCONTRADOS ===")
            for file_path, problem in self.problems_found:
                self.log(f"{file_path}: {problem['type']} - {problem['description']} ({problem['severity']})")
        
        if self.stats['errors'] == 0:
            self.log("VERIFICAÇÃO DE FILTROS CONCLUÍDA COM SUCESSO!", "SUCCESS")
        else:
            self.log(f"VERIFICAÇÃO DE FILTROS CONCLUÍDA COM {self.stats['errors']} ERROS", "WARNING")
    
    def run_verification(self):
        self.log("=== INICIANDO VERIFICAÇÃO DE FILTROS ===")
        
        self.create_backup_dir()
        
        templates_to_check = self.scan_templates()
        
        self.log(f"Templates para verificar: {len(templates_to_check)}")
        
        for file_path in templates_to_check:
            self.verify_template_filters(file_path)
            self.stats['templates_checked'] += 1
        
        self.generate_report()

def main():
    print("=== SCRIPT DE VERIFICAÇÃO E CORREÇÃO DE FILTROS DJANGO ===")
    print("Verificando e corrigindo problemas específicos nos filtros...")
    
    if not Path("templates").exists():
        print("ERRO: Diretório 'templates' não encontrado!")
        return
    
    verifier = FilterVerifier()
    verifier.run_verification()
    
    print("\n=== VERIFICAÇÃO DE FILTROS CONCLUÍDA ===")
    print("Verifique o arquivo 'filtros_verificacao_log.txt' para detalhes completos.")

if __name__ == "__main__":
    main()
