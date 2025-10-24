#!/usr/bin/env python3
"""
CORREÇÃO AUTOMÁTICA DE SINTAXE JAVASCRIPT
Script para corrigir automaticamente os 211 erros de sintaxe JavaScript detectados
"""

import os
import re
import logging
from pathlib import Path
from datetime import datetime

class JavaScriptSyntaxFixer:
    def __init__(self):
        self.setup_logging()
        self.correcoes_aplicadas = 0
        self.arquivos_processados = 0
        self.padroes_correcao = [
            # Padrão 1: const|default:0
            (r'const\|default:0', 'const'),
            # Padrão 2: .length|default:0
            (r'\.length\|default:0', '.length'),
            # Padrão 3: .id|default:"null"
            (r'\.id\|default:"null"', '.id'),
            # Padrão 4: const|default:0 variável
            (r'const\|default:0\s+(\w+)', r'const \1'),
            # Padrão 5: .length|default:0 em expressões
            (r'(\w+)\.length\|default:0', r'\1.length'),
        ]
    
    def setup_logging(self):
        """Configurar sistema de logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('correcao_js_syntax.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def corrigir_arquivo(self, file_path):
        """Corrigir um arquivo HTML específico"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            correcoes_no_arquivo = 0
            
            # Aplicar cada padrão de correção
            for padrao, substituicao in self.padroes_correcao:
                matches = re.findall(padrao, content)
                if matches:
                    content = re.sub(padrao, substituicao, content)
                    correcoes_no_arquivo += len(matches)
                    self.logger.info(f"  - Corrigido padrao '{padrao}' -> '{substituicao}': {len(matches)} ocorrencias")
            
            # Salvar arquivo se houve mudanças
            if content != original_content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                self.correcoes_aplicadas += correcoes_no_arquivo
                self.logger.info(f"Arquivo corrigido: {file_path} ({correcoes_no_arquivo} correcoes)")
                return correcoes_no_arquivo
            else:
                self.logger.info(f"Nenhuma correcao necessaria: {file_path}")
                return 0
                
        except Exception as e:
            self.logger.error(f"Erro ao processar {file_path}: {e}")
            return 0
    
    def processar_todos_arquivos(self):
        """Processar todos os arquivos HTML do projeto"""
        self.logger.info("INICIANDO CORRECAO DE SINTAXE JAVASCRIPT")
        self.logger.info("=" * 60)
        
        # Encontrar todos os arquivos HTML
        html_files = list(Path('.').rglob('*.html'))
        self.logger.info(f"Encontrados {len(html_files)} arquivos HTML para processar")
        
        # Processar cada arquivo
        for html_file in html_files:
            self.logger.info(f"Processando: {html_file}")
            correcoes = self.corrigir_arquivo(html_file)
            self.arquivos_processados += 1
        
        # Relatório final
        self.logger.info("=" * 60)
        self.logger.info("RELATORIO FINAL:")
        self.logger.info(f"Arquivos processados: {self.arquivos_processados}")
        self.logger.info(f"Correcoes aplicadas: {self.correcoes_aplicadas}")
        self.logger.info(f"Taxa de correcao: {(self.correcoes_aplicadas/max(self.arquivos_processados, 1))*100:.1f}%")
        self.logger.info("=" * 60)
        
        return self.correcoes_aplicadas

def main():
    """Função principal"""
    print("CORRECAO AUTOMATICA DE SINTAXE JAVASCRIPT")
    print("=" * 50)
    print("Este script corrige automaticamente os 211 erros de sintaxe JavaScript detectados.")
    print()
    
    fixer = JavaScriptSyntaxFixer()
    
    print("Iniciando correcao...")
    correcoes = fixer.processar_todos_arquivos()
    
    print(f"\nCORRECAO CONCLUIDA!")
    print(f"Total de correcoes aplicadas: {correcoes}")
    print(f"Arquivos processados: {fixer.arquivos_processados}")
    print(f"Log salvo em: correcao_js_syntax.log")

if __name__ == "__main__":
    main()
