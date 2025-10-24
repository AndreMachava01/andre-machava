#!/usr/bin/env python3
"""
Script para Migração de Botões para Sistema Unificado
Migra botões existentes para o novo sistema unificado de botões
"""

import os
import re
import shutil
from pathlib import Path
from datetime import datetime

class ButtonMigrator:
    def __init__(self, templates_dir="templates"):
        self.templates_dir = Path(templates_dir)
        self.backup_dir = Path("backups_button_migration")
        self.log_file = Path("button_migration_log.txt")
        self.stats = {
            'total_templates': 0,
            'templates_processed': 0,
            'buttons_migrated': 0,
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
    
    def migrate_module_buttons(self, content):
        """Migra botões de módulos principais"""
        migrations = 0
        
        # Padrões para botões de módulos
        patterns = [
            # Botões RH
            (r'<a[^>]*href=["\']/rh/["\'][^>]*class=["\'][^"\']*btn[^"\']*["\'][^>]*>([^<]*)RH([^<]*)</a>', 
             r'{% button_unified type="module" text="RH" icon="fas fa-users" url="/rh/" %}'),
            
            # Botões Stock
            (r'<a[^>]*href=["\']/stock/["\'][^>]*class=["\'][^"\']*btn[^"\']*["\'][^>]*>([^<]*)Stock([^<]*)</a>', 
             r'{% button_unified type="module" text="Stock" icon="fas fa-boxes" url="/stock/" %}'),
            
            # Botões Logística
            (r'<a[^>]*href=["\']/stock/logistica/["\'][^>]*class=["\'][^"\']*btn[^"\']*["\'][^>]*>([^<]*)Logística([^<]*)</a>', 
             r'{% button_unified type="module" text="Logística" icon="fas fa-truck" url="/stock/logistica/" %}'),
        ]
        
        for pattern, replacement in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)
                migrations += len(matches)
                self.log(f"Migrados {len(matches)} botões de módulo com padrão: {pattern}")
        
        return content, migrations
    
    def migrate_submodule_buttons(self, content):
        """Migra botões de submódulos"""
        migrations = 0
        
        # Mapeamento de submódulos
        submodule_mapping = {
            'funcionarios': {'text': 'Funcionários', 'icon': 'fas fa-user', 'url': '/rh/funcionarios/'},
            'departamentos': {'text': 'Departamentos', 'icon': 'fas fa-building', 'url': '/rh/departamentos/'},
            'cargos': {'text': 'Cargos', 'icon': 'fas fa-briefcase', 'url': '/rh/cargos/'},
            'salarios': {'text': 'Salários', 'icon': 'fas fa-money-bill', 'url': '/rh/salarios/'},
            'presencas': {'text': 'Presenças', 'icon': 'fas fa-calendar-check', 'url': '/rh/presencas/'},
            'treinamentos': {'text': 'Treinamentos', 'icon': 'fas fa-graduation-cap', 'url': '/rh/treinamentos/'},
            'avaliacoes': {'text': 'Avaliações', 'icon': 'fas fa-star', 'url': '/rh/avaliacoes/'},
            'feriados': {'text': 'Feriados', 'icon': 'fas fa-calendar-times', 'url': '/rh/feriados/'},
            'transferencias': {'text': 'Transferências', 'icon': 'fas fa-exchange-alt', 'url': '/rh/transferencias/'},
            'folha_salarial': {'text': 'Folha Salarial', 'icon': 'fas fa-file-invoice', 'url': '/rh/folha_salarial/'},
            'promocoes': {'text': 'Promoções', 'icon': 'fas fa-arrow-up', 'url': '/rh/promocoes/'},
            'produtos': {'text': 'Produtos', 'icon': 'fas fa-box', 'url': '/stock/produtos/'},
            'materiais': {'text': 'Materiais', 'icon': 'fas fa-cube', 'url': '/stock/materiais/'},
            'fornecedores': {'text': 'Fornecedores', 'icon': 'fas fa-truck-loading', 'url': '/stock/fornecedores/'},
            'categorias': {'text': 'Categorias', 'icon': 'fas fa-tags', 'url': '/stock/categorias/'},
            'inventario': {'text': 'Inventário', 'icon': 'fas fa-clipboard-list', 'url': '/stock/inventario/'},
            'requisicoes': {'text': 'Requisições', 'icon': 'fas fa-file-alt', 'url': '/stock/requisicoes/'},
            'viaturas': {'text': 'Viaturas', 'icon': 'fas fa-car', 'url': '/stock/logistica/viaturas/'},
            'transportadoras': {'text': 'Transportadoras', 'icon': 'fas fa-shipping-fast', 'url': '/stock/logistica/transportadoras/'},
            'operacoes': {'text': 'Operações', 'icon': 'fas fa-cogs', 'url': '/stock/logistica/operacoes/'},
            'rastreamento': {'text': 'Rastreamento', 'icon': 'fas fa-map-marker-alt', 'url': '/stock/logistica/rastreamento/'},
            'checklist': {'text': 'Checklist', 'icon': 'fas fa-check-square', 'url': '/stock/logistica/checklist/'},
            'pod': {'text': 'POD', 'icon': 'fas fa-file-signature', 'url': '/stock/logistica/pod/'},
            'guias': {'text': 'Guias', 'icon': 'fas fa-file-export', 'url': '/stock/logistica/guias/'},
            'cotacao': {'text': 'Cotação', 'icon': 'fas fa-dollar-sign', 'url': '/stock/logistica/cotacao/'},
        }
        
        for submodule, config in submodule_mapping.items():
            pattern = rf'<a[^>]*href=["\'][^"\']*{submodule}[^"\']*["\'][^>]*class=["\'][^"\']*btn[^"\']*["\'][^>]*>([^<]*)</a>'
            replacement = f'{{% button_unified type="submodule" text="{config["text"]}" icon="{config["icon"]}" url="{config["url"]}" %}}'
            
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)
                migrations += len(matches)
                self.log(f"Migrados {len(matches)} botões de submódulo '{submodule}'")
        
        return content, migrations
    
    def migrate_action_buttons(self, content):
        """Migra botões de ação"""
        migrations = 0
        
        # Padrões para botões de ação
        action_patterns = [
            # Ver Detalhes
            (r'<a[^>]*href=["\'][^"\']*["\'][^>]*class=["\'][^"\']*btn[^"\']*["\'][^>]*>([^<]*)Ver[^<]*Detalhes([^<]*)</a>', 
             r'{% button_unified type="action" action="view" text="Ver Detalhes" icon="fas fa-eye" %}'),
            
            # Editar
            (r'<a[^>]*href=["\'][^"\']*["\'][^>]*class=["\'][^"\']*btn[^"\']*["\'][^>]*>([^<]*)Editar([^<]*)</a>', 
             r'{% button_unified type="action" action="edit" text="Editar" icon="fas fa-edit" %}'),
            
            # Apagar/Excluir
            (r'<a[^>]*href=["\'][^"\']*["\'][^>]*class=["\'][^"\']*btn[^"\']*["\'][^>]*>([^<]*)Apagar([^<]*)</a>', 
             r'{% button_unified type="action" action="delete" text="Apagar" icon="fas fa-trash" %}'),
            (r'<a[^>]*href=["\'][^"\']*["\'][^>]*class=["\'][^"\']*btn[^"\']*["\'][^>]*>([^<]*)Excluir([^<]*)</a>', 
             r'{% button_unified type="action" action="delete" text="Excluir" icon="fas fa-trash" %}'),
        ]
        
        for pattern, replacement in action_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)
                migrations += len(matches)
                self.log(f"Migrados {len(matches)} botões de ação com padrão: {pattern}")
        
        return content, migrations
    
    def migrate_confirmation_buttons(self, content):
        """Migra botões de confirmação"""
        migrations = 0
        
        # Padrões para botões de confirmação
        confirmation_patterns = [
            # Guardar/Salvar
            (r'<button[^>]*type=["\']submit["\'][^>]*class=["\'][^"\']*btn[^"\']*["\'][^>]*>([^<]*)Guardar([^<]*)</button>', 
             r'{% button_unified type="confirmation" action="save" text="Guardar" icon="fas fa-save" %}'),
            (r'<button[^>]*type=["\']submit["\'][^>]*class=["\'][^"\']*btn[^"\']*["\'][^>]*>([^<]*)Salvar([^<]*)</button>', 
             r'{% button_unified type="confirmation" action="save" text="Salvar" icon="fas fa-save" %}'),
            
            # Cancelar
            (r'<button[^>]*type=["\']button["\'][^>]*class=["\'][^"\']*btn[^"\']*["\'][^>]*>([^<]*)Cancelar([^<]*)</button>', 
             r'{% button_unified type="confirmation" action="cancel" text="Cancelar" icon="fas fa-times" %}'),
            
            # Confirmar
            (r'<button[^>]*type=["\']submit["\'][^>]*class=["\'][^"\']*btn[^"\']*["\'][^>]*>([^<]*)Confirmar([^<]*)</button>', 
             r'{% button_unified type="confirmation" action="confirm" text="Confirmar" icon="fas fa-check" %}'),
        ]
        
        for pattern, replacement in confirmation_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)
                migrations += len(matches)
                self.log(f"Migrados {len(matches)} botões de confirmação com padrão: {pattern}")
        
        return content, migrations
    
    def migrate_navigation_buttons(self, content):
        """Migra botões de navegação"""
        migrations = 0
        
        # Padrões para botões de navegação
        navigation_patterns = [
            # Voltar
            (r'<a[^>]*href=["\']javascript:history\.back\(\)["\'][^>]*class=["\'][^"\']*btn[^"\']*["\'][^>]*>([^<]*)Voltar([^<]*)</a>', 
             r'{% button_unified type="navigation" text="Voltar" icon="fas fa-arrow-left" onclick="history.back()" %}'),
            
            # Início/Home
            (r'<a[^>]*href=["\']/["\'][^>]*class=["\'][^"\']*btn[^"\']*["\'][^>]*>([^<]*)Início([^<]*)</a>', 
             r'{% button_unified type="navigation" text="Início" icon="fas fa-home" url="/" %}'),
            (r'<a[^>]*href=["\']/["\'][^>]*class=["\'][^"\']*btn[^"\']*["\'][^>]*>([^<]*)Home([^<]*)</a>', 
             r'{% button_unified type="navigation" text="Home" icon="fas fa-home" url="/" %}'),
            
            # Próximo
            (r'<a[^>]*href=["\']javascript:history\.forward\(\)["\'][^>]*class=["\'][^"\']*btn[^"\']*["\'][^>]*>([^<]*)Próximo([^<]*)</a>', 
             r'{% button_unified type="navigation" text="Próximo" icon="fas fa-arrow-right" onclick="history.forward()" %}'),
        ]
        
        for pattern, replacement in navigation_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)
                migrations += len(matches)
                self.log(f"Migrados {len(matches)} botões de navegação com padrão: {pattern}")
        
        return content, migrations
    
    def migrate_template(self, file_path):
        """Aplica todas as migrações em um template"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            total_migrations = 0
            
            # Aplicar migrações
            content, migrations = self.migrate_module_buttons(content)
            total_migrations += migrations
            
            content, migrations = self.migrate_submodule_buttons(content)
            total_migrations += migrations
            
            content, migrations = self.migrate_action_buttons(content)
            total_migrations += migrations
            
            content, migrations = self.migrate_confirmation_buttons(content)
            total_migrations += migrations
            
            content, migrations = self.migrate_navigation_buttons(content)
            total_migrations += migrations
            
            # Se houve migrações, salvar o arquivo
            if total_migrations > 0:
                if not self.backup_file(file_path):
                    return 0
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                self.log(f"Migrações aplicadas em {file_path}: {total_migrations}")
            
            return total_migrations
            
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
        self.log(f"Botões migrados: {self.stats['buttons_migrated']}")
        self.log(f"Backups criados: {self.stats['backups_created']}")
        self.log(f"Erros encontrados: {self.stats['errors']}")
        
        if self.stats['errors'] == 0:
            self.log("MIGRAÇÃO DE BOTÕES CONCLUÍDA COM SUCESSO!", "SUCCESS")
        else:
            self.log(f"MIGRAÇÃO DE BOTÕES CONCLUÍDA COM {self.stats['errors']} ERROS", "WARNING")
    
    def run_migration(self):
        """Executa migração completa"""
        self.log("=== INICIANDO MIGRAÇÃO DE BOTÕES ===")
        
        self.create_backup_dir()
        
        # Migrar templates
        html_files = self.scan_templates()
        
        for file_path in html_files:
            migrations = self.migrate_template(file_path)
            
            if migrations > 0:
                self.stats['buttons_migrated'] += migrations
            
            self.stats['templates_processed'] += 1
        
        self.generate_report()

def main():
    print("=== SCRIPT DE MIGRAÇÃO DE BOTÕES PARA SISTEMA UNIFICADO ===")
    print("Migrando botões existentes para o novo sistema unificado...")
    
    if not Path("templates").exists():
        print("ERRO: Diretório 'templates' não encontrado!")
        return
    
    migrator = ButtonMigrator()
    migrator.run_migration()
    
    print("\n=== MIGRAÇÃO DE BOTÕES CONCLUÍDA ===")
    print("Verifique o arquivo 'button_migration_log.txt' para detalhes completos.")

if __name__ == "__main__":
    main()
