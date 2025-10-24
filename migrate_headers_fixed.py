import os
import re
from pathlib import Path

def escape_quotes(text):
    """Escapa aspas simples e duplas no texto"""
    if not text:
        return ''
    return str(text).replace('"', '\\"').replace("'", "\\'")

def process_file(filepath, is_priority=False):
    """Processa um único arquivo para atualizar o cabeçalho"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Pular arquivos que já usam o novo header
        if '{% include "includes/header.html"' in content:
            if is_priority:
                print(f'  - Já atualizado (usa o novo formato): {filepath}')
            return 0
        
        # Padrão para encontrar o header antigo (mais flexível)
        header_pattern = re.compile(
            r'<div[^>]*class=[\'\"]page-header[\'\"][^>]*>.*?<div[^>]*class=[\'\"]page-header-content[\'\"][^>]*>(.*?)</div>\s*</div>',
            re.DOTALL | re.IGNORECASE
        )
        
        # Encontrar o header antigo
        header_match = header_pattern.search(content)
        if not header_match:
            if is_priority:
                print(f'  - Nenhum header antigo encontrado em: {filepath}')
            return 0
        
        print(f'\nProcessando: {filepath}')
        
        # Extrair o conteúdo do header
        header_content = header_match.group(0)
        
        # Padrão para encontrar título e ícone
        title_pattern = re.compile(
            r'<h1[^>]*>\s*(?:<i[^>]*class=[\'\"]([^\'\"]*)[\'\"][^>]*>\s*</i>\s*)?(.*?)</h1>',
            re.DOTALL | re.IGNORECASE
        )
        
        # Extrair título e ícone
        title_match = title_pattern.search(header_content)
        if not title_match:
            print(f'  - Aviso: Não foi possível extrair o título do header')
            return 0
        
        icon_class = title_match.group(1).strip() if title_match.group(1) else ''
        title = title_match.group(2).strip()
        
        # Extrair subtítulo se existir
        subtitle_pattern = re.compile(
            r'<p[^>]*class=[\'\"]page-subtitle[\'\"][^>]*>(.*?)</p>',
            re.DOTALL | re.IGNORECASE
        )
        
        subtitle_match = subtitle_pattern.search(header_content)
        subtitle = subtitle_match.group(1).strip() if subtitle_match else ''
        
        # Extrair botões se existirem
        buttons_pattern = re.compile(
            r'<div[^>]*class=[\'\"]header-actions[\'\"][^>]*>(.*?)</div>',
            re.DOTALL | re.IGNORECASE
        )
        
        buttons_match = buttons_pattern.search(header_content)
        buttons_html = buttons_match.group(0) if buttons_match else ''
        
        # Construir o novo header
        new_header = '{# Cabeçalho padronizado - Gerado automaticamente #}\n'

        # Se não tiver a tag de load, adicionar
        if '{% load static %}' not in content:
            new_header = '{% load static %}\n' + new_header
        
        new_header += '{% include "includes/header.html" with\n'
        # Adicionar título
        new_header += f'    title="{escape_quotes(title)}"\n'
        # Adicionar subtítulo se existir
        if subtitle:
            new_header += f'    subtitle="{escape_quotes(subtitle)}"\n'
        # Adicionar ícone se existir
        if icon_class:
            # Pegar apenas a primeira classe de ícone (Font Awesome)
            icon = next((cls for cls in icon_class.split() if cls.startswith('fa-')), '')
            if icon:
                new_header += f'    icon="{icon}"\n'
        # Adicionar botões se existirem
        if buttons_match:
            new_header += '    actions=[\n'
            # Padrão para encontrar botões individuais
            button_pattern = re.compile(
                r'<a\s+[^>]*class=[\'\"]([^\'\"]*)[\'\"][^>]*href=[\'\"]([^\'\"]*)[\'\"]([^>]*)>(.*?)</a>',
                re.DOTALL | re.IGNORECASE
            )
            
            # Padrão para encontrar ícones dentro dos botões
            icon_pattern = re.compile(
                r'<i[^>]*class=[\'\"]([^\'\"]*)[\'\"][^>]*>',
                re.IGNORECASE
            )
            
            # Encontrar todos os botões
            button_matches = button_pattern.finditer(buttons_html)
            
            for btn in button_matches:
                btn_class = btn.group(1).strip() if btn.group(1) else ''
                btn_url = btn.group(2).strip()
                btn_attrs = btn.group(3)
                btn_content = btn.group(4).strip()
                
                # Extrair texto do botão (removendo tags HTML)
                btn_text = re.sub(r'<[^>]*>', '', btn_content).strip()
                
                # Extrair ícone se existir
                icon_match = icon_pattern.search(btn_content)
                btn_icon = icon_match.group(1).strip() if icon_match else ''
                
                # Extrair ID se existir
                id_match = re.search(r'id=[\'\"]([^\'\"]*)[\'\"]', btn_attrs, re.IGNORECASE)
                btn_id = id_match.group(1) if id_match else ''
                
                # Construir o dicionário do botão
                btn_dict = '        {\n'
                # URL é obrigatória
                btn_dict += f'            "url": "{escape_quotes(btn_url)}",\n'
                # Texto é obrigatório
                btn_dict += f'            "text": "{escape_quotes(btn_text)}",\n'
                # Adicionar classe se existir
                if btn_class:
                    btn_dict += f'            "class": "{escape_quotes(btn_class)}",\n'
                # Adicionar ícone se existir
                if btn_icon:
                    # Pegar apenas a primeira classe de ícone (Font Awesome)
                    icon = next((cls for cls in btn_icon.split() if cls.startswith('fa-')), '')
                    if icon:
                        btn_dict += f'            "icon": "{icon}",\n'
                # Adicionar ID se existir
                if btn_id:
                    btn_dict += f'            "id": "{btn_id}",\n'
                # Remover a vírgula extra do último item
                btn_dict = btn_dict.rstrip(',\n') + '\n'
                btn_dict += '        },\n'
                new_header += btn_dict

            new_header += '    ]\n'
        new_header += '%}'
        
        # Substituir o header antigo pelo novo
        new_content = content.replace(header_content, new_header)
        
        # Salvar o arquivo
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        print(f'  - Atualizado com sucesso')
        return 1
        
    except Exception as e:
        print(f'  - Erro ao processar {filepath}: {str(e)}')
        return 0

def migrate_headers():
    """Função principal para migrar os cabeçalhos"""
    # Diretório de templates
    templates_dir = Path('d:/PROGRAMA/CONCEPTION/ANDRE/templates')
    
    # Contador de arquivos atualizados
    updated_count = 0
    
    # Lista de arquivos para pular
    skip_files = [
        'base_admin.html',
        'base.html',
        'includes/header.html',
        'components/page_header.html'
    ]
    
    # Lista de arquivos para processar primeiro (opcional)
    priority_files = [
        'rh/avaliacoes/main.html',
        'rh/presencas/calendario.html',
        'rh/feriados/delete.html',
        'rh/avaliacoes/main.html',
        'rh/avaliacoes/form.html',
        'rh/avaliacoes/detail.html',
        'rh/avaliacoes/delete.html'
    ]
    
    print('Iniciando migração dos cabeçalhos...')
    
    # Primeiro, processar os arquivos prioritários
    print('\n=== Processando arquivos prioritários ===')
    for rel_path in priority_files:
        filepath = templates_dir / rel_path
        if filepath.exists():
            print(f'\nProcessando arquivo prioritário: {rel_path}')
            updated_count += process_file(filepath, True)
        else:
            print(f'\nArquivo prioritário não encontrado: {rel_path}')
    
    # Agora, processar todos os outros arquivos
    print('\n=== Processando demais arquivos ===')
    for root, _, files in os.walk(templates_dir):
        for file in files:
            if file.endswith('.html'):
                filepath = Path(root) / file
                rel_path = str(filepath.relative_to(templates_dir)).replace('\\', '/')
                
                # Pular arquivos na lista de exclusão
                if any(skip in rel_path for skip in skip_files):
                    continue
                
                # Pular arquivos já processados
                if rel_path in priority_files:
                    continue
                
                updated_count += process_file(filepath)
    
    return updated_count

if __name__ == '__main__':
    updated_count = migrate_headers()
    print(f'\nMigração concluída! {updated_count} arquivos foram atualizados.')
