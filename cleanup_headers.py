import os
import re
from pathlib import Path

# Diretório de templates
templates_dir = Path('d:/PROGRAMA/CONCEPTION/ANDRE/templates')

# Padrões para remoção
header_patterns = [
    # Remove classes de header antigas
    r'\s*\.page-header\s*\{[^}]*\}.*?\n',
    r'\s*\.page-header::before\s*\{[^}]*\}.*?\n',
    r'\s*\.page-header-content\s*\{[^}]*\}.*?\n',
    # Remove blocos de estilo inline
    r'<style>[\s\S]*?<\/style>',
    # Remove divs de header antigas
    r'<div class=["\']page-header["\'][\s\S]*?<\/div>\s*<!-- \/Page Header -->',
]

# Percorre todos os arquivos HTML
def clean_headers():
    for root, _, files in os.walk(templates_dir):
        for file in files:
            if file.endswith('.html'):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Remove os padrões antigos
                    for pattern in header_patterns:
                        content = re.sub(pattern, '', content, flags=re.IGNORECASE)
                    
                    # Atualiza o arquivo
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(content)
                    
                    print(f'Atualizado: {filepath}')
                except Exception as e:
                    print(f'Erro ao processar {filepath}: {str(e)}')

if __name__ == '__main__':
    clean_headers()
