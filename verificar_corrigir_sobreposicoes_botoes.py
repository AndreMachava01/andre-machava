#!/usr/bin/env python3
"""
Script para Verificação e Correção de Sobreposições de Botões
Verifica e corrige problemas que impedem o funcionamento dos botões
"""

import os
import re
import shutil
from pathlib import Path
from datetime import datetime
from collections import defaultdict

class ButtonOverlapChecker:
    def __init__(self, templates_dir="templates", static_dir="meuprojeto/empresa/static"):
        self.templates_dir = Path(templates_dir)
        self.static_dir = Path(static_dir)
        self.backup_dir = Path("backups_botoes_sobreposicao")
        self.log_file = Path("botoes_sobreposicao_log.txt")
        self.stats = {
            'total_templates': 0,
            'templates_processed': 0,
            'overlaps_found': 0,
            'overlaps_fixed': 0,
            'backups_created': 0,
            'errors': 0,
            'skipped': 0
        }
        self.overlaps_found = []
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
    
    def find_button_overlaps(self, content):
        """Encontra sobreposições de botões"""
        overlaps = []
        
        # Padrões de sobreposição
        overlap_patterns = [
            # Botões duplicados com mesmo ID
            r'<[^>]*id=["\']([^"\']*)["\'][^>]*>.*?<[^>]*id=["\']\1["\'][^>]*>',
            
            # Botões com classes conflitantes
            r'<[^>]*class=["\'][^"\']*btn[^"\']*btn[^"\']*["\'][^>]*>',
            
            # Botões com onclick duplicado
            r'<[^>]*onclick=["\'][^"\']*["\'][^>]*onclick=["\'][^"\']*["\'][^>]*>',
            
            # Botões com href e onclick
            r'<a[^>]*href=["\'][^"\']*["\'][^>]*onclick=["\'][^"\']*["\'][^>]*>',
            
            # Botões com type conflitante
            r'<button[^>]*type=["\']submit["\'][^>]*onclick=["\'][^"\']*["\'][^>]*>',
            
            # Botões com z-index sobreposto
            r'<[^>]*style=["\'][^"\']*z-index[^"\']*["\'][^>]*class=["\'][^"\']*btn[^"\']*["\'][^>]*>',
            
            # Botões com position absoluta sobreposta
            r'<[^>]*style=["\'][^"\']*position:\s*absolute[^"\']*["\'][^>]*class=["\'][^"\']*btn[^"\']*["\'][^>]*>',
            
            # Botões com float sobreposto
            r'<[^>]*style=["\'][^"\']*float[^"\']*["\'][^>]*class=["\'][^"\']*btn[^"\']*["\'][^>]*>',
            
            # Botões com margin negativo
            r'<[^>]*style=["\'][^"\']*margin[^"\']*-[^"\']*["\'][^>]*class=["\'][^"\']*btn[^"\']*["\'][^>]*>',
            
            # Botões com padding excessivo
            r'<[^>]*style=["\'][^"\']*padding[^"\']*[0-9]{3,}[^"\']*["\'][^>]*class=["\'][^"\']*btn[^"\']*["\'][^>]*>',
        ]
        
        for pattern in overlap_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)
            for match in matches:
                overlaps.append({
                    'pattern': pattern,
                    'content': match,
                    'type': self.classify_overlap_type(pattern),
                    'severity': self.classify_overlap_severity(pattern)
                })
        
        return overlaps
    
    def classify_overlap_type(self, pattern):
        """Classifica o tipo de sobreposição"""
        if 'id=' in pattern.lower():
            return 'duplicate_id'
        elif 'class=' in pattern.lower() and 'btn' in pattern.lower():
            return 'conflicting_classes'
        elif 'onclick=' in pattern.lower():
            return 'duplicate_onclick'
        elif 'href=' in pattern.lower() and 'onclick=' in pattern.lower():
            return 'href_onclick_conflict'
        elif 'type=' in pattern.lower():
            return 'type_conflict'
        elif 'z-index' in pattern.lower():
            return 'z_index_overlap'
        elif 'position:' in pattern.lower():
            return 'position_overlap'
        elif 'float' in pattern.lower():
            return 'float_overlap'
        elif 'margin' in pattern.lower():
            return 'margin_overlap'
        elif 'padding' in pattern.lower():
            return 'padding_overlap'
        else:
            return 'unknown'
    
    def classify_overlap_severity(self, pattern):
        """Classifica a severidade da sobreposição"""
        if 'id=' in pattern.lower():
            return 'critical'
        elif 'onclick=' in pattern.lower():
            return 'high'
        elif 'href=' in pattern.lower() and 'onclick=' in pattern.lower():
            return 'high'
        elif 'type=' in pattern.lower():
            return 'medium'
        elif 'z-index' in pattern.lower():
            return 'medium'
        elif 'position:' in pattern.lower():
            return 'medium'
        elif 'float' in pattern.lower():
            return 'low'
        elif 'margin' in pattern.lower():
            return 'low'
        elif 'padding' in pattern.lower():
            return 'low'
        else:
            return 'unknown'
    
    def fix_button_overlaps(self, content):
        """Corrige sobreposições de botões"""
        corrections = 0
        
        # Correções de sobreposição
        fixes = [
            # Remover IDs duplicados
            (r'<([^>]*)id=["\']([^"\']*)["\']([^>]*)>.*?<([^>]*)id=["\']\2["\']([^>]*)>', 
             r'<\1id="\2"\3>\4id="\2-2"\5>'),
            
            # Corrigir classes conflitantes
            (r'<([^>]*)class=["\']([^"\']*)btn([^"\']*)btn([^"\']*)["\']([^>]*)>', 
             r'<\1class="\2btn\3\4"\5>'),
            
            # Remover onclick duplicado
            (r'<([^>]*)onclick=["\']([^"\']*)["\']([^>]*)onclick=["\']([^"\']*)["\']([^>]*)>', 
             r'<\1onclick="\2; \4"\3\5>'),
            
            # Corrigir href + onclick
            (r'<a([^>]*)href=["\']([^"\']*)["\']([^>]*)onclick=["\']([^"\']*)["\']([^>]*)>', 
             r'<a\1href="#"\3onclick="event.preventDefault(); \4"\5>'),
            
            # Corrigir type conflitante
            (r'<button([^>]*)type=["\']submit["\']([^>]*)onclick=["\']([^"\']*)["\']([^>]*)>', 
             r'<button\1type="button"\2onclick="\3"\4>'),
            
            # Remover z-index problemático
            (r'<([^>]*)style=["\']([^"\']*)z-index[^"\']*["\']([^>]*)class=["\']([^"\']*)btn([^"\']*)["\']([^>]*)>', 
             r'<\1\3class="\4btn\5"\6>'),
            
            # Corrigir position absoluta
            (r'<([^>]*)style=["\']([^"\']*)position:\s*absolute[^"\']*["\']([^>]*)class=["\']([^"\']*)btn([^"\']*)["\']([^>]*)>', 
             r'<\1\3class="\4btn\5"\6>'),
            
            # Corrigir float
            (r'<([^>]*)style=["\']([^"\']*)float[^"\']*["\']([^>]*)class=["\']([^"\']*)btn([^"\']*)["\']([^>]*)>', 
             r'<\1\3class="\4btn\5"\6>'),
            
            # Corrigir margin negativo
            (r'<([^>]*)style=["\']([^"\']*)margin[^"\']*-[^"\']*["\']([^>]*)class=["\']([^"\']*)btn([^"\']*)["\']([^>]*)>', 
             r'<\1\3class="\4btn\5"\6>'),
            
            # Corrigir padding excessivo
            (r'<([^>]*)style=["\']([^"\']*)padding[^"\']*[0-9]{3,}[^"\']*["\']([^>]*)class=["\']([^"\']*)btn([^"\']*)["\']([^>]*)>', 
             r'<\1\3class="\4btn\5"\6>'),
        ]
        
        for pattern, replacement in fixes:
            matches = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)
            if matches:
                content = re.sub(pattern, replacement, content, flags=re.IGNORECASE | re.DOTALL)
                corrections += len(matches)
                self.log(f"Corrigidas {len(matches)} sobreposições com padrão: {pattern}")
        
        return content, corrections
    
    def fix_css_conflicts(self, content):
        """Corrige conflitos de CSS"""
        corrections = 0
        
        # Correções de CSS
        css_fixes = [
            # Remover !important desnecessário
            (r'<([^>]*)style=["\']([^"\']*)!important[^"\']*["\']([^>]*)class=["\']([^"\']*)btn([^"\']*)["\']([^>]*)>', 
             r'<\1\3class="\4btn\5"\6>'),
            
            # Corrigir display conflitante
            (r'<([^>]*)style=["\']([^"\']*)display[^"\']*["\']([^>]*)class=["\']([^"\']*)btn([^"\']*)["\']([^>]*)>', 
             r'<\1\3class="\4btn\5"\6>'),
            
            # Corrigir width conflitante
            (r'<([^>]*)style=["\']([^"\']*)width[^"\']*["\']([^>]*)class=["\']([^"\']*)btn([^"\']*)["\']([^>]*)>', 
             r'<\1\3class="\4btn\5"\6>'),
            
            # Corrigir height conflitante
            (r'<([^>]*)style=["\']([^"\']*)height[^"\']*["\']([^>]*)class=["\']([^"\']*)btn([^"\']*)["\']([^>]*)>', 
             r'<\1\3class="\4btn\5"\6>'),
            
            # Corrigir overflow conflitante
            (r'<([^>]*)style=["\']([^"\']*)overflow[^"\']*["\']([^>]*)class=["\']([^"\']*)btn([^"\']*)["\']([^>]*)>', 
             r'<\1\3class="\4btn\5"\6>'),
        ]
        
        for pattern, replacement in css_fixes:
            matches = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)
            if matches:
                content = re.sub(pattern, replacement, content, flags=re.IGNORECASE | re.DOTALL)
                corrections += len(matches)
                self.log(f"Corrigidos {len(matches)} conflitos de CSS com padrão: {pattern}")
        
        return content, corrections
    
    def fix_javascript_conflicts(self, content):
        """Corrige conflitos de JavaScript"""
        corrections = 0
        
        # Correções de JavaScript
        js_fixes = [
            # Corrigir onclick com return false
            (r'<([^>]*)onclick=["\']([^"\']*)return\s+false[^"\']*["\']([^>]*)>', 
             r'<\1onclick="event.preventDefault(); \2"\3>'),
            
            # Corrigir onclick com alert
            (r'<([^>]*)onclick=["\']([^"\']*)alert[^"\']*["\']([^>]*)>', 
             r'<\1onclick="\2"\3>'),
            
            # Corrigir onclick com confirm
            (r'<([^>]*)onclick=["\']([^"\']*)confirm[^"\']*["\']([^>]*)>', 
             r'<\1onclick="\2"\3>'),
            
            # Corrigir onclick com window.open
            (r'<([^>]*)onclick=["\']([^"\']*)window\.open[^"\']*["\']([^>]*)>', 
             r'<\1onclick="\2"\3>'),
            
            # Corrigir onclick com location.href
            (r'<([^>]*)onclick=["\']([^"\']*)location\.href[^"\']*["\']([^>]*)>', 
             r'<\1onclick="\2"\3>'),
        ]
        
        for pattern, replacement in js_fixes:
            matches = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)
            if matches:
                content = re.sub(pattern, replacement, content, flags=re.IGNORECASE | re.DOTALL)
                corrections += len(matches)
                self.log(f"Corrigidos {len(matches)} conflitos de JavaScript com padrão: {pattern}")
        
        return content, corrections
    
    def fix_template_conflicts(self, content):
        """Corrige conflitos de template"""
        corrections = 0
        
        # Correções de template
        template_fixes = [
            # Corrigir includes duplicados
            (r'{%\s*include\s*[\'"]components/button_unified\.html[\'"]\s*%}.*?{%\s*include\s*[\'"]components/button_unified\.html[\'"]\s*%}', 
             r'{% include \'components/button_unified.html\' %}'),
            
            # Corrigir load duplicado
            (r'{%\s*load\s+button_tags\s*%}.*?{%\s*load\s+button_tags\s*%}', 
             r'{% load button_tags %}'),
            
            # Corrigir extends duplicado
            (r'{%\s*extends\s*[\'"]base_admin\.html[\'"]\s*%}.*?{%\s*extends\s*[\'"]base_admin\.html[\'"]\s*%}', 
             r'{% extends \'base_admin.html\' %}'),
            
            # Corrigir block duplicado
            (r'{%\s*block\s+(\w+)\s*%}.*?{%\s*block\s+\1\s*%}', 
             r'{% block \1 %}'),
        ]
        
        for pattern, replacement in template_fixes:
            matches = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)
            if matches:
                content = re.sub(pattern, replacement, content, flags=re.IGNORECASE | re.DOTALL)
                corrections += len(matches)
                self.log(f"Corrigidos {len(matches)} conflitos de template com padrão: {pattern}")
        
        return content, corrections
    
    def fix_template(self, file_path):
        """Aplica todas as correções em um template"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            total_corrections = 0
            
            # Encontrar sobreposições
            overlaps = self.find_button_overlaps(content)
            
            self.stats['overlaps_found'] += len(overlaps)
            
            # Aplicar correções
            content, corrections = self.fix_button_overlaps(content)
            total_corrections += corrections
            
            content, corrections = self.fix_css_conflicts(content)
            total_corrections += corrections
            
            content, corrections = self.fix_javascript_conflicts(content)
            total_corrections += corrections
            
            content, corrections = self.fix_template_conflicts(content)
            total_corrections += corrections
            
            # Se houve correções, salvar o arquivo
            if total_corrections > 0:
                if not self.backup_file(file_path):
                    return 0
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                self.log(f"Correções aplicadas em {file_path}: {total_corrections}")
                self.overlaps_found.append({
                    'file': file_path,
                    'overlaps': len(overlaps),
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
        self.log(f"Sobreposições encontradas: {self.stats['overlaps_found']}")
        self.log(f"Sobreposições corrigidas: {self.stats['overlaps_fixed']}")
        self.log(f"Backups criados: {self.stats['backups_created']}")
        self.log(f"Templates pulados: {self.stats['skipped']}")
        self.log(f"Erros encontrados: {self.stats['errors']}")
        
        if self.overlaps_found:
            self.log("\n=== SOBREPOSIÇÕES ENCONTRADAS ===")
            for overlap in self.overlaps_found:
                self.log(f"{overlap['file']}: {overlap['overlaps']} sobreposições, {overlap['corrections']} correções")
        
        if self.stats['errors'] == 0:
            self.log("VERIFICAÇÃO DE SOBREPOSIÇÕES CONCLUÍDA COM SUCESSO!", "SUCCESS")
        else:
            self.log(f"VERIFICAÇÃO DE SOBREPOSIÇÕES CONCLUÍDA COM {self.stats['errors']} ERROS", "WARNING")
    
    def run_verification(self):
        """Executa verificação completa"""
        self.log("=== INICIANDO VERIFICAÇÃO DE SOBREPOSIÇÕES DE BOTÕES ===")
        
        self.create_backup_dir()
        
        # Verificar templates
        html_files = self.scan_templates()
        
        for file_path in html_files:
            corrections = self.fix_template(file_path)
            
            if corrections > 0:
                self.stats['overlaps_fixed'] += corrections
            
            self.stats['templates_processed'] += 1
        
        self.generate_report()

def main():
    print("=== SCRIPT DE VERIFICAÇÃO E CORREÇÃO DE SOBREPOSIÇÕES DE BOTÕES ===")
    print("Verificando e corrigindo sobreposições que impedem o funcionamento dos botões...")
    
    if not Path("templates").exists():
        print("ERRO: Diretório 'templates' não encontrado!")
        return
    
    checker = ButtonOverlapChecker()
    checker.run_verification()
    
    print("\n=== VERIFICAÇÃO DE SOBREPOSIÇÕES CONCLUÍDA ===")
    print("Verifique o arquivo 'botoes_sobreposicao_log.txt' para detalhes completos.")

if __name__ == "__main__":
    main()
