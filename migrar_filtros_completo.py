#!/usr/bin/env python3
"""
Script para Verificação e Correção de Filtros de Pesquisa
Verifica e corrige todos os filtros para usar o sistema unificado
"""

import os
import re
import shutil
from pathlib import Path
from datetime import datetime

class FilterMigrator:
    def __init__(self, templates_dir="templates"):
        self.templates_dir = Path(templates_dir)
        self.backup_dir = Path("backups_filtros")
        self.log_file = Path("filtros_migracao_log.txt")
        self.stats = {
            'total_templates': 0,
            'filters_corrected': 0,
            'filters_already_unified': 0,
            'backups_created': 0,
            'errors': 0,
            'skipped': 0
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
    
    def is_list_template(self, file_path):
        list_patterns = ['main.html', 'list.html', 'lista.html', 'index.html']
        exclude_patterns = [
            'base_admin.html', 'base_list.html', 'form.html', 'detail.html',
            'delete.html', 'create.html', 'edit.html', 'print.html',
            'documento.html', 'relatorio.html', 'calendario.html',
            'dashboard.html', 'login.html', 'filters_unified.html'
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
    
    def has_unified_filters(self, content):
        unified_patterns = [
            r'{% include [\'"]includes/filters_unified\.html[\'"] %}',
            r'{% include [\'"]filters_unified\.html[\'"] %}',
            r'filters_unified\.html'
        ]
        
        for pattern in unified_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        return False
    
    def has_old_filters(self, content):
        old_patterns = [
            r'<form[^>]*class="[^"]*filter[^"]*"[^>]*>',
            r'<div[^>]*class="[^"]*filter[^"]*"[^>]*>',
            r'<input[^>]*name="[^"]*search[^"]*"[^>]*>',
            r'<select[^>]*name="[^"]*filter[^"]*"[^>]*>',
            r'<div[^>]*class="[^"]*search[^"]*"[^>]*>',
            r'<div[^>]*class="[^"]*filtros[^"]*"[^>]*>',
            r'<!-- FILTROS[^>]*-->',
            r'FILTROS[^>]*REMOVIDO'
        ]
        
        for pattern in old_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        return False
    
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
    
    def replace_old_filters(self, content, entity_name):
        unified_filter = f'''<!-- FILTROS UNIFICADOS -->
{{% include 'includes/filters_unified.html' with entity_name='{entity_name}' %}}'''
        
        # Padrões para remover filtros antigos
        old_filter_patterns = [
            r'<!-- FILTROS[^>]*-->.*?(?=\n\n|\n{%|\n<div|\n<form|\Z)',
            r'<form[^>]*class="[^"]*filter[^"]*"[^>]*>.*?</form>',
            r'<div[^>]*class="[^"]*filter[^"]*"[^>]*>.*?</div>',
            r'<div[^>]*class="[^"]*search[^"]*"[^>]*>.*?</div>',
            r'<div[^>]*class="[^"]*filtros[^"]*"[^>]*>.*?</div>',
            r'<!-- FILTROS[^>]*REMOVIDO[^>]*-->.*?(?=\n\n|\n{%|\n<div|\Z)',
            r'FILTROS[^>]*REMOVIDO[^>]*USAR[^>]*SISTEMA[^>]*UNIFICADO.*?(?=\n\n|\n{%|\n<div|\Z)'
        ]
        
        # Remover filtros antigos
        for pattern in old_filter_patterns:
            content = re.sub(pattern, '', content, flags=re.IGNORECASE | re.DOTALL)
        
        # Limpar linhas vazias extras
        content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
        
        # Adicionar filtros unificados após extends
        extends_pattern = r'({% extends [\'"][^\'"]+[\'"] %})'
        if re.search(extends_pattern, content):
            content = re.sub(
                extends_pattern,
                r'\1\n\n' + unified_filter,
                content,
                count=1
            )
        else:
            content = unified_filter + '\n\n' + content
        
        return content
    
    def migrate_template_filters(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if self.has_unified_filters(content):
                self.stats['filters_already_unified'] += 1
                self.log(f"Filtros já unificados: {file_path}")
                return True
            
            if not self.has_old_filters(content):
                self.stats['skipped'] += 1
                self.log(f"Sem filtros para migrar: {file_path}")
                return True
            
            if not self.backup_template(file_path):
                return False
            
            entity_name = self.get_entity_name_from_path(file_path)
            content = self.replace_old_filters(content, entity_name)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            self.stats['filters_corrected'] += 1
            self.log(f"Filtros migrados com sucesso: {file_path} (entidade: {entity_name})")
            return True
            
        except Exception as e:
            self.stats['errors'] += 1
            self.log(f"Erro ao migrar filtros de {file_path}: {e}", "ERROR")
            return False
    
    def scan_templates(self):
        html_files = list(self.templates_dir.rglob("*.html"))
        self.stats['total_templates'] = len(html_files)
        
        self.log(f"Encontrados {len(html_files)} templates HTML")
        
        templates_to_migrate = []
        
        for file_path in html_files:
            if self.is_list_template(file_path):
                templates_to_migrate.append(file_path)
            else:
                self.stats['skipped'] += 1
                self.log(f"Pulando (não é lista): {file_path}")
        
        return templates_to_migrate
    
    def verify_migration(self):
        self.log("=== VERIFICAÇÃO PÓS-MIGRAÇÃO ===")
        
        unified_filters = 0
        old_filters = 0
        
        for file_path in self.templates_dir.rglob("*.html"):
            if self.is_list_template(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    if self.has_unified_filters(content):
                        unified_filters += 1
                    elif self.has_old_filters(content):
                        old_filters += 1
                        self.log(f"Ainda tem filtros antigos: {file_path}", "WARNING")
                        
                except Exception as e:
                    self.log(f"Erro ao verificar {file_path}: {e}", "ERROR")
        
        self.log(f"Templates com filtros unificados: {unified_filters}")
        self.log(f"Templates com filtros antigos: {old_filters}")
        
        return unified_filters, old_filters
    
    def run_migration(self):
        self.log("=== INICIANDO MIGRAÇÃO DE FILTROS ===")
        
        self.create_backup_dir()
        
        templates_to_migrate = self.scan_templates()
        
        self.log(f"Templates para migrar filtros: {len(templates_to_migrate)}")
        
        for file_path in templates_to_migrate:
            self.migrate_template_filters(file_path)
        
        unified_filters, old_filters = self.verify_migration()
        
        self.log("=== RELATÓRIO FINAL ===")
        self.log(f"Total de templates encontrados: {self.stats['total_templates']}")
        self.log(f"Filtros migrados: {self.stats['filters_corrected']}")
        self.log(f"Filtros já unificados: {self.stats['filters_already_unified']}")
        self.log(f"Backups criados: {self.stats['backups_created']}")
        self.log(f"Templates pulados: {self.stats['skipped']}")
        self.log(f"Erros encontrados: {self.stats['errors']}")
        self.log(f"Templates com filtros unificados: {unified_filters}")
        self.log(f"Templates com filtros antigos: {old_filters}")
        
        if self.stats['errors'] == 0:
            self.log("MIGRAÇÃO DE FILTROS CONCLUÍDA COM SUCESSO!", "SUCCESS")
        else:
            self.log(f"MIGRAÇÃO DE FILTROS CONCLUÍDA COM {self.stats['errors']} ERROS", "WARNING")

def main():
    print("=== SCRIPT DE MIGRAÇÃO DE FILTROS DJANGO ===")
    print("Verificando e corrigindo todos os filtros dos templates...")
    
    if not Path("templates").exists():
        print("ERRO: Diretório 'templates' não encontrado!")
        return
    
    migrator = FilterMigrator()
    migrator.run_migration()
    
    print("\n=== MIGRAÇÃO DE FILTROS CONCLUÍDA ===")
    print("Verifique o arquivo 'filtros_migracao_log.txt' para detalhes completos.")

if __name__ == "__main__":
    main()
