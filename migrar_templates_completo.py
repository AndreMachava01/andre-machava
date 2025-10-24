#!/usr/bin/env python3
"""
Script Completo para Verificação e Correção de Templates Django
Verifica e corrige todos os templates do sistema para usar o sistema unificado
"""

import os
import re
import shutil
from pathlib import Path
from datetime import datetime

class TemplateMigrator:
    def __init__(self, templates_dir="templates"):
        self.templates_dir = Path(templates_dir)
        self.backup_dir = Path("backups_templates")
        self.log_file = Path("migracao_log.txt")
        self.stats = {
            'total_templates': 0,
            'migrated': 0,
            'already_unified': 0,
            'backups_created': 0,
            'errors': 0,
            'skipped': 0
        }
        
    def log(self, message, level="INFO"):
        """Registra mensagens no log"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] [{level}] {message}"
        print(log_message)
        
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_message + "\n")
    
    def create_backup_dir(self):
        """Cria diretório de backups"""
        if not self.backup_dir.exists():
            self.backup_dir.mkdir(parents=True)
            self.log(f"Diretório de backup criado: {self.backup_dir}")
    
    def is_list_template(self, file_path):
        """Verifica se é um template de lista que deve ser migrado"""
        list_patterns = [
            'main.html',
            'list.html',
            'lista.html',
            'index.html'
        ]
        
        # Templates que NÃO devem ser migrados
        exclude_patterns = [
            'base_admin.html',
            'base_list.html',
            'dashboard.html',
            'form.html',
            'detail.html',
            'delete.html',
            'create.html',
            'edit.html',
            'print.html',
            'documento.html',
            'relatorio.html',
            'calendario.html',
            'inscrever.html',
            'inscricoes.html'
        ]
        
        filename = file_path.name.lower()
        
        # Verifica se deve ser excluído
        for exclude in exclude_patterns:
            if exclude in filename:
                return False
        
        # Verifica se é um template de lista
        for pattern in list_patterns:
            if pattern in filename:
                return True
                
        return False
    
    def should_keep_as_admin(self, file_path):
        """Verifica se deve manter como base_admin.html"""
        keep_patterns = [
            'dashboard',
            'form',
            'detail',
            'delete',
            'create',
            'edit',
            'print',
            'documento',
            'relatorio',
            'calendario',
            'inscrever',
            'inscricoes',
            'main.html'  # Menus principais
        ]
        
        filename = file_path.name.lower()
        path_str = str(file_path).lower()
        
        # Menus principais sempre mantêm base_admin
        if 'main.html' in filename and any(x in path_str for x in ['stock/main.html', 'logistica/main.html', 'rh/main.html']):
            return True
            
        # Dashboards sempre mantêm base_admin
        if 'dashboard' in filename:
            return True
            
        # Relatórios sempre mantêm base_admin
        if 'relatorio' in filename or 'documento' in filename:
            return True
            
        return False
    
    def backup_template(self, file_path):
        """Cria backup do template"""
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
    
    def fix_extends_order(self, content):
        """Corrige a ordem do {% extends %} para estar na primeira linha"""
        lines = content.split('\n')
        
        # Encontrar linha com {% extends %}
        extends_line = None
        extends_index = None
        
        for i, line in enumerate(lines):
            if '{% extends' in line:
                extends_line = line.strip()
                extends_index = i
                break
        
        if extends_line and extends_index > 0:
            # Remover da posição atual
            lines.pop(extends_index)
            # Adicionar na primeira linha
            lines.insert(0, extends_line)
            return '\n'.join(lines)
        
        return content
    
    def migrate_template(self, file_path):
        """Migra um template para base_list.html"""
        try:
            # Ler conteúdo
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Verificar se já está migrado
            if '{% extends "base_list.html" %}' in content or "{% extends 'base_list.html' %}" in content:
                self.stats['already_unified'] += 1
                self.log(f"Já migrado: {file_path}")
                return True
            
            # Criar backup
            if not self.backup_template(file_path):
                return False
            
            # Migrar para base_list.html
            content = re.sub(
                r'{% extends ["\']base_admin\.html["\'] %}',
                '{% extends "base_list.html" %}',
                content
            )
            
            # Corrigir ordem do extends
            content = self.fix_extends_order(content)
            
            # Escrever arquivo modificado
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            self.stats['migrated'] += 1
            self.log(f"Migrado com sucesso: {file_path}")
            return True
            
        except Exception as e:
            self.stats['errors'] += 1
            self.log(f"Erro ao migrar {file_path}: {e}", "ERROR")
            return False
    
    def scan_templates(self):
        """Escaneia todos os templates HTML"""
        html_files = list(self.templates_dir.rglob("*.html"))
        self.stats['total_templates'] = len(html_files)
        
        self.log(f"Encontrados {len(html_files)} templates HTML")
        
        templates_to_migrate = []
        templates_to_keep = []
        
        for file_path in html_files:
            if self.should_keep_as_admin(file_path):
                templates_to_keep.append(file_path)
                self.log(f"Mantendo como base_admin: {file_path}")
            elif self.is_list_template(file_path):
                templates_to_migrate.append(file_path)
            else:
                self.stats['skipped'] += 1
                self.log(f"Pulando (não é lista): {file_path}")
        
        return templates_to_migrate, templates_to_keep
    
    def verify_migration(self):
        """Verifica se a migração foi bem-sucedida"""
        self.log("=== VERIFICAÇÃO PÓS-MIGRAÇÃO ===")
        
        base_list_count = 0
        base_admin_count = 0
        
        for file_path in self.templates_dir.rglob("*.html"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                if '{% extends "base_list.html" %}' in content or "{% extends 'base_list.html' %}" in content:
                    base_list_count += 1
                elif '{% extends "base_admin.html" %}' in content or "{% extends 'base_admin.html' %}" in content:
                    base_admin_count += 1
                    
            except Exception as e:
                self.log(f"Erro ao verificar {file_path}: {e}", "ERROR")
        
        self.log(f"Templates usando base_list.html: {base_list_count}")
        self.log(f"Templates usando base_admin.html: {base_admin_count}")
        
        return base_list_count, base_admin_count
    
    def run_migration(self):
        """Executa a migração completa"""
        self.log("=== INICIANDO MIGRAÇÃO DE TEMPLATES ===")
        
        # Criar diretório de backup
        self.create_backup_dir()
        
        # Escanear templates
        templates_to_migrate, templates_to_keep = self.scan_templates()
        
        self.log(f"Templates para migrar: {len(templates_to_migrate)}")
        self.log(f"Templates para manter: {len(templates_to_keep)}")
        
        # Migrar templates
        for file_path in templates_to_migrate:
            self.migrate_template(file_path)
        
        # Verificar migração
        base_list_count, base_admin_count = self.verify_migration()
        
        # Relatório final
        self.log("=== RELATÓRIO FINAL ===")
        self.log(f"Total de templates encontrados: {self.stats['total_templates']}")
        self.log(f"Templates migrados: {self.stats['migrated']}")
        self.log(f"Templates já unificados: {self.stats['already_unified']}")
        self.log(f"Backups criados: {self.stats['backups_created']}")
        self.log(f"Templates pulados: {self.stats['skipped']}")
        self.log(f"Erros encontrados: {self.stats['errors']}")
        self.log(f"Templates usando base_list.html: {base_list_count}")
        self.log(f"Templates usando base_admin.html: {base_admin_count}")
        
        if self.stats['errors'] == 0:
            self.log("MIGRAÇÃO CONCLUÍDA COM SUCESSO!", "SUCCESS")
        else:
            self.log(f"MIGRAÇÃO CONCLUÍDA COM {self.stats['errors']} ERROS", "WARNING")

def main():
    """Função principal"""
    print("=== SCRIPT DE MIGRAÇÃO DE TEMPLATES DJANGO ===")
    print("Verificando e corrigindo todos os templates do sistema...")
    
    # Verificar se diretório templates existe
    if not Path("templates").exists():
        print("ERRO: Diretório 'templates' não encontrado!")
        return
    
    # Executar migração
    migrator = TemplateMigrator()
    migrator.run_migration()
    
    print("\n=== MIGRAÇÃO CONCLUÍDA ===")
    print("Verifique o arquivo 'migracao_log.txt' para detalhes completos.")

if __name__ == "__main__":
    main()
