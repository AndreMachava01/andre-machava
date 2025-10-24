#!/usr/bin/env python3
"""
VERIFICADOR DE TEMPLATES MALFORMADOS
Script para detectar e corrigir problemas de HTML nos templates
"""

import os
import re
import logging
from pathlib import Path
from datetime import datetime

class TemplateMalformedChecker:
    def __init__(self):
        self.setup_logging()
        self.problemas_encontrados = 0
        self.arquivos_processados = 0
        self.padroes_problema = [
            # Padrão 1: Tags não fechadas
            (r'<(\w+)(?![^>]*/>)(?![^>]*</\1>)', 'Tag não fechada'),
            # Padrão 2: Tags duplicadas
            (r'<(\w+)[^>]*>.*?<\1[^>]*>', 'Tag duplicada'),
            # Padrão 3: Atributos malformados
            (r'(\w+)=\s*=\s*["\']', 'Atributo malformado'),
            # Padrão 4: Aspas não fechadas
            (r'=\s*["\'][^"\']*$', 'Aspas não fechadas'),
            # Padrão 5: Tags Django malformadas
            (r'{%\s*(\w+)\s*%}(?!\s*{%\s*end\1\s*%})', 'Tag Django não fechada'),
        ]
    
    def setup_logging(self):
        """Configurar sistema de logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('verificacao_templates.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def verificar_arquivo(self, file_path):
        """Verificar um arquivo HTML específico"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            problemas_no_arquivo = []
            
            # Verificar problemas básicos de HTML
            for padrao, descricao in self.padroes_problema:
                matches = re.findall(padrao, content, re.MULTILINE | re.DOTALL)
                if matches:
                    problemas_no_arquivo.append({
                        'tipo': descricao,
                        'ocorrencias': len(matches),
                        'padrao': padrao
                    })
            
            # Verificar tags não balanceadas (verificação básica)
            tags_abertas = re.findall(r'<(\w+)(?![^>]*/>)', content)
            tags_fechadas = re.findall(r'</(\w+)>', content)
            
            if len(tags_abertas) != len(tags_fechadas):
                problemas_no_arquivo.append({
                    'tipo': 'Tags não balanceadas',
                    'ocorrencias': abs(len(tags_abertas) - len(tags_fechadas)),
                    'padrao': 'Verificação de balanceamento'
                })
            
            # Verificar problemas específicos do Django
            django_problemas = self.verificar_django_syntax(content)
            problemas_no_arquivo.extend(django_problemas)
            
            if problemas_no_arquivo:
                self.problemas_encontrados += len(problemas_no_arquivo)
                self.logger.info(f"Problemas encontrados em {file_path}: {len(problemas_no_arquivo)}")
                for problema in problemas_no_arquivo:
                    self.logger.info(f"  - {problema['tipo']}: {problema['ocorrencias']} ocorrencias")
                return problemas_no_arquivo
            else:
                self.logger.info(f"Nenhum problema encontrado: {file_path}")
                return []
                
        except Exception as e:
            self.logger.error(f"Erro ao processar {file_path}: {e}")
            return []
    
    def verificar_django_syntax(self, content):
        """Verificar sintaxe específica do Django"""
        problemas = []
        
        # Verificar tags Django não fechadas
        django_tags = re.findall(r'{%\s*(\w+)\s*%}', content)
        django_end_tags = re.findall(r'{%\s*end(\w+)\s*%}', content)
        
        # Verificar se há tags de abertura sem fechamento
        for tag in django_tags:
            if tag in ['if', 'for', 'block', 'with']:
                end_tag = f'end{tag}'
                if end_tag not in django_end_tags:
                    problemas.append({
                        'tipo': f'Tag Django nao fechada: {tag}',
                        'ocorrencias': 1,
                        'padrao': f'{{% {tag} %}} sem {{% end{tag} %}}'
                    })
        
        # Verificar variáveis Django malformadas
        variaveis_malformadas = re.findall(r'\{\{\s*[^}]*\s*$', content, re.MULTILINE)
        if variaveis_malformadas:
            problemas.append({
                'tipo': 'Variavel Django malformada',
                'ocorrencias': len(variaveis_malformadas),
                'padrao': '{{ sem }}'
            })
        
        return problemas
    
    def processar_todos_arquivos(self):
        """Processar todos os arquivos HTML do projeto"""
        self.logger.info("INICIANDO VERIFICACAO DE TEMPLATES MALFORMADOS")
        self.logger.info("=" * 60)
        
        # Encontrar todos os arquivos HTML
        html_files = list(Path('.').rglob('*.html'))
        self.logger.info(f"Encontrados {len(html_files)} arquivos HTML para processar")
        
        # Processar cada arquivo
        for html_file in html_files:
            self.logger.info(f"Processando: {html_file}")
            problemas = self.verificar_arquivo(html_file)
            self.arquivos_processados += 1
        
        # Relatório final
        self.logger.info("=" * 60)
        self.logger.info("RELATORIO FINAL:")
        self.logger.info(f"Arquivos processados: {self.arquivos_processados}")
        self.logger.info(f"Problemas encontrados: {self.problemas_encontrados}")
        self.logger.info(f"Taxa de problemas: {(self.problemas_encontrados/max(self.arquivos_processados, 1))*100:.1f}%")
        self.logger.info("=" * 60)
        
        return self.problemas_encontrados

def main():
    """Função principal"""
    print("VERIFICADOR DE TEMPLATES MALFORMADOS")
    print("=" * 50)
    print("Este script verifica problemas de HTML nos templates.")
    print()
    
    checker = TemplateMalformedChecker()
    
    print("Iniciando verificacao...")
    problemas = checker.processar_todos_arquivos()
    
    print(f"\nVERIFICACAO CONCLUIDA!")
    print(f"Total de problemas encontrados: {problemas}")
    print(f"Arquivos processados: {checker.arquivos_processados}")
    print(f"Log salvo em: verificacao_templates.log")

if __name__ == "__main__":
    main()
