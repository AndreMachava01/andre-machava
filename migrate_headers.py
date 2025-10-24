import os
import re
from pathlib import Path

def migrate_headers():
    # Diretório de templates
    templates_dir = Path('d:/PROGRAMA/CONCEPTION/ANDRE/templates')
    
    # Contador de arquivos atualizados
    updated_count = 0
    
    # Padrão para encontrar o header antigo
    header_pattern = re.compile(
        r'<div class="page-header">\s*<div class="page-header-content">(.*?)</div>\s*</div>',
        re.DOTALL
    )
    
    # Padrão para encontrar título e ícone
    title_pattern = re.compile(
        r'<h1[^>]*>(?:\s*<i[^>]*class="([^"]*)"[^>]*>\s*</i>\s*)?(.*?)</h1>',
        re.DOTALL
    )
    
    # Padrão para encontrar subtítulo
    subtitle_pattern = re.compile(
        r'<p class="page-subtitle">(.*?)</p>',
        re.DOTALL
    )
    
    # Padrão para encontrar botões
    buttons_pattern = re.compile(
        r'<div class="header-actions">(.*?)</div>',
        re.DOTALL
    )
    
    # Padrão para encontrar botões individuais
    button_pattern = re.compile(
        r'<a\s+[^>]*class="([^"]*)"[^>]*href="([^"]*)"(?:[^>]*)>(.*?)</a>',
        re.DOTALL
    )
    
    # Padrão para encontrar ícones dentro dos botões
    icon_pattern = re.compile(
        r'<i[^>]*class="([^"]*)"[^>]*>',
        re.DOTALL
    )
    
    # Percorrer todos os arquivos HTML
    for root, _, files in os.walk(templates_dir):
        for file in files:
            if file.endswith('.html'):
                filepath = os.path.join(root, file)
                
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Pular arquivos que já usam o novo header
                    if '{% include "includes/header.html"' in content:
                        continue
                    
                    # Encontrar o header antigo
                    header_match = header_pattern.search(content)
                    if not header_match:
                        continue
                    
                    print(f'\nProcessando: {filepath}')
                    
                    # Extrair o conteúdo do header
                    header_content = header_match.group(1)
                    
                    # Extrair título e ícone
                    title_match = title_pattern.search(header_content)
                    if not title_match:
                        print(f'  - Aviso: Não foi possível extrair o título do header em {filepath}')
                        continue
                    
                    icon_class = title_match.group(1) or ''
                    title = title_match.group(2).strip()
                    
                    # Extrair subtítulo se existir
                    subtitle_match = subtitle_pattern.search(header_content)
                    subtitle = subtitle_match.group(1).strip() if subtitle_match else ''
                    
                    # Extrair botões se existirem
                    buttons_match = buttons_pattern.search(header_content)
                    buttons_html = buttons_match.group(1) if buttons_match else ''
                    
                    # Construir o novo header
                    new_header = '{% load static %}\n'
                    new_header += '{% include "includes/header.html" with\n'
                    # Adicionar título
                    new_header += f'    title="{title}"\n'
                    # Adicionar subtítulo se existir
                    if subtitle:
                        new_header += f'    subtitle="{subtitle}"\n'
                    # Adicionar ícone se existir
                    if icon_class:
                        new_header += f'    icon="{icon_class}"\n'
                    # Adicionar botões se existirem
                    if buttons_html:
                        new_header += '    actions=[\n'
                        # Encontrar todos os botões
                        buttons = button_pattern.finditer(buttons_html)
                        
                        for btn in buttons:
                            btn_class = btn.group(1).strip()
                            btn_url = btn.group(2).strip()
                            btn_content = btn.group(3).strip()
                            
                            # Extrair texto do botão (removendo tags HTML)
                            btn_text = re.sub(r'<[^>]*>', '', btn_content).strip()
                            
                            # Extrair ícone se existir
                            icon_match = icon_pattern.search(btn_content)
                            btn_icon = icon_match.group(1).strip() if icon_match else ''
                            
                            new_header += '        {\n'
                            # Adicionar URL
                            new_header += f'            "url": "{btn_url}",\n'
                            # Adicionar texto
                            if btn_text:
                                new_header += f'            "text": "{btn_text}",\n'
                            # Adicionar classe
                            if btn_class:
                                new_header += f'            "class": "{btn_class}",\n'
                            # Adicionar ícone
                            if btn_icon:
                                new_header += f'            "icon": "{btn_icon}",\n'
                            # Remover a vírgula extra do último item
                            new_header = new_header.rstrip(',\n') + '\n'
                            new_header += '        },\n'
                        new_header += '    ]\n'
                    new_header += '%}'
                    
                    # Substituir o header antigo pelo novo
                    new_content = content[:header_match.start()] + new_header + content[header_match.end()+1:]
                    
                    # Salvar o arquivo
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    
                    print(f'  - Atualizado com sucesso')
                    updated_count += 1
                    
                except Exception as e:
                    print(f'  - Erro ao processar {filepath}: {str(e)}')
    
    print(f'\nMigração concluída! {updated_count} arquivos foram atualizados.')

if __name__ == '__main__':
    print('Iniciando migração dos cabeçalhos...')
    migrate_headers()
