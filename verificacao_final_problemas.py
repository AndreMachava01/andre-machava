#!/usr/bin/env python3
"""
VERIFICADOR FINAL DE PROBLEMAS CRÍTICOS
Script para verificar se todos os problemas críticos foram resolvidos
"""

import os
import re
import logging
from pathlib import Path
from datetime import datetime

class VerificadorFinalProblemas:
    def __init__(self):
        self.setup_logging()
        self.problemas_encontrados = 0
        self.arquivos_processados = 0
    
    def setup_logging(self):
        """Configurar sistema de logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('verificacao_final.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def verificar_sintaxe_javascript(self):
        """Verificar se ainda há erros de sintaxe JavaScript"""
        self.logger.info("Verificando sintaxe JavaScript...")
        
        problemas_js = 0
        html_files = list(Path('.').rglob('*.html'))
        
        for html_file in html_files:
            try:
                with open(html_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Verificar padrões problemáticos
                padroes_problema = [
                    r'const\|default:0',
                    r'\.length\|default:0',
                    r'\.id\|default:"null"'
                ]
                
                for padrao in padroes_problema:
                    matches = re.findall(padrao, content)
                    if matches:
                        problemas_js += len(matches)
                        self.logger.warning(f"Erro JS encontrado em {html_file}: {len(matches)} ocorrencias do padrao '{padrao}'")
                        
            except Exception as e:
                self.logger.error(f"Erro ao processar {html_file}: {e}")
        
        if problemas_js == 0:
            self.logger.info("✅ Nenhum erro de sintaxe JavaScript encontrado!")
        else:
            self.logger.error(f"❌ {problemas_js} erros de sintaxe JavaScript ainda presentes!")
        
        return problemas_js
    
    def verificar_urls_corretas(self):
        """Verificar se as URLs estão corretas"""
        self.logger.info("Verificando configuração de URLs...")
        
        problemas_url = 0
        
        # Verificar arquivos de views por padrões problemáticos
        py_files = list(Path('meuprojeto').rglob('*.py'))
        
        for py_file in py_files:
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Verificar se há redirect com pk em vez de id
                if 'redirect' in content and 'pk=' in content:
                    matches = re.findall(r'redirect\([^)]*pk=[^)]*\)', content)
                    if matches:
                        problemas_url += len(matches)
                        self.logger.warning(f"Possivel redirect com pk em {py_file}: {matches}")
                        
            except Exception as e:
                self.logger.error(f"Erro ao processar {py_file}: {e}")
        
        if problemas_url == 0:
            self.logger.info("✅ Nenhum problema de URL encontrado!")
        else:
            self.logger.error(f"❌ {problemas_url} problemas de URL encontrados!")
        
        return problemas_url
    
    def verificar_templates_criticos(self):
        """Verificar apenas templates críticos (não backups)"""
        self.logger.info("Verificando templates críticos...")
        
        problemas_template = 0
        
        # Verificar apenas templates principais (não backups)
        template_files = list(Path('templates').rglob('*.html'))
        
        for template_file in template_files:
            try:
                with open(template_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Verificar problemas críticos específicos
                problemas_criticos = [
                    # Tags Django não fechadas críticas
                    (r'{%\s*if\s+[^%]*%}(?!.*{%\s*endif\s*%})', 'Tag if não fechada'),
                    (r'{%\s*for\s+[^%]*%}(?!.*{%\s*endfor\s*%})', 'Tag for não fechada'),
                    (r'{%\s*block\s+[^%]*%}(?!.*{%\s*endblock\s*%})', 'Tag block não fechada'),
                    # Variáveis Django malformadas
                    (r'\{\{\s*[^}]*$', 'Variável Django malformada'),
                    # Aspas não fechadas críticas
                    (r'=\s*["\'][^"\']*$', 'Aspas não fechadas')
                ]
                
                for padrao, descricao in problemas_criticos:
                    matches = re.findall(padrao, content, re.MULTILINE)
                    if matches:
                        problemas_template += len(matches)
                        self.logger.warning(f"Problema crítico em {template_file}: {len(matches)} {descricao}")
                        
            except Exception as e:
                self.logger.error(f"Erro ao processar {template_file}: {e}")
        
        if problemas_template == 0:
            self.logger.info("✅ Nenhum problema crítico de template encontrado!")
        else:
            self.logger.error(f"❌ {problemas_template} problemas críticos de template encontrados!")
        
        return problemas_template
    
    def executar_verificacao_completa(self):
        """Executar verificação completa"""
        self.logger.info("INICIANDO VERIFICACAO FINAL DE PROBLEMAS CRITICOS")
        self.logger.info("=" * 60)
        
        # Verificar cada tipo de problema
        problemas_js = self.verificar_sintaxe_javascript()
        problemas_url = self.verificar_urls_corretas()
        problemas_template = self.verificar_templates_criticos()
        
        total_problemas = problemas_js + problemas_url + problemas_template
        
        # Relatório final
        self.logger.info("=" * 60)
        self.logger.info("RELATORIO FINAL:")
        self.logger.info(f"Problemas JavaScript: {problemas_js}")
        self.logger.info(f"Problemas URL: {problemas_url}")
        self.logger.info(f"Problemas Template: {problemas_template}")
        self.logger.info(f"TOTAL DE PROBLEMAS CRITICOS: {total_problemas}")
        
        if total_problemas == 0:
            self.logger.info("🎉 TODOS OS PROBLEMAS CRITICOS FORAM RESOLVIDOS!")
        else:
            self.logger.error(f"⚠️ AINDA EXISTEM {total_problemas} PROBLEMAS CRITICOS!")
        
        self.logger.info("=" * 60)
        
        return total_problemas

def main():
    """Função principal"""
    print("VERIFICADOR FINAL DE PROBLEMAS CRITICOS")
    print("=" * 50)
    print("Este script verifica se todos os problemas críticos foram resolvidos.")
    print()
    
    verificador = VerificadorFinalProblemas()
    
    print("Iniciando verificacao final...")
    problemas = verificador.executar_verificacao_completa()
    
    print(f"\nVERIFICACAO FINAL CONCLUIDA!")
    print(f"Total de problemas criticos restantes: {problemas}")
    print(f"Log salvo em: verificacao_final.log")
    
    if problemas == 0:
        print("\n🎉 SUCESSO! Todos os problemas críticos foram resolvidos!")
    else:
        print(f"\n⚠️ ATENCAO! Ainda existem {problemas} problemas críticos.")

if __name__ == "__main__":
    main()
