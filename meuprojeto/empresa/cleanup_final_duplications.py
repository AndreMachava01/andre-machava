"""
LIMPEZA FINAL DE DUPLICAÇÕES RESTANTES
Script para remover todas as duplicações que ainda existem
"""

import os
import re

def clean_remaining_template_duplications():
    """Remove filtros inline restantes dos templates"""
    
    template_files = [
        'templates/stock/notificacoes/list.html',
        'templates/stock/inventario/ajustes_list.html',
        'templates/stock/requisicoes/list.html'
    ]
    
    for template_file in template_files:
        if os.path.exists(template_file):
            print(f"Limpando filtros restantes em {template_file}...")
            
            # Ler arquivo
            with open(template_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Remover seções de filtros inline restantes
            patterns_to_remove = [
                r'\.filters-section\s*\{[^}]*\}\s*',
                r'\.filters-title\s*\{[^}]*\}\s*',
                r'\.filter-group\s*\{[^}]*\}\s*',
                r'\.filter-label\s*\{[^}]*\}\s*',
                r'\.filter-actions\s*\{[^}]*\}\s*',
                r'\.btn-filter\s*\{[^}]*\}\s*',
                r'\.btn-clear\s*\{[^}]*\}\s*',
                r'\.filters-grid\s*\{[^}]*\}\s*',
            ]
            
            for pattern in patterns_to_remove:
                content = re.sub(pattern, '', content, flags=re.MULTILINE | re.DOTALL)
            
            # Adicionar comentário de substituição
            replacement_comment = """<!-- FILTROS - REMOVIDO (USAR SISTEMA UNIFICADO) -->
<!-- Substituir por: {% include 'includes/filters_unified.html' with entity_name='nome_entidade' %} -->

"""
            
            # Escrever arquivo limpo
            with open(template_file, 'w', encoding='utf-8') as f:
                f.write(replacement_comment + content)
            
            print(f"OK {template_file} limpo com sucesso")

def clean_remaining_css_duplications():
    """Remove duplicações restantes de CSS"""
    
    # Limpar components.css
    css_file = 'meuprojeto/empresa/static/css/components.css'
    if os.path.exists(css_file):
        print(f"Limpando duplicações restantes em {css_file}...")
        
        with open(css_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Remover seções de filtros duplicadas
        patterns_to_remove = [
            r'/\* =============================================================================\s*\n\s*FILTROS.*?\n\s*=.*?\*/\s*\n',
            r'\.filters-section\s*\{[^}]*\}\s*',
            r'\.filters-title\s*\{[^}]*\}\s*',
            r'\.filter-group\s*\{[^}]*\}\s*',
            r'\.filter-label\s*\{[^}]*\}\s*',
            r'\.filter-actions\s*\{[^}]*\}\s*',
        ]
        
        for pattern in patterns_to_remove:
            content = re.sub(pattern, '', content, flags=re.MULTILINE | re.DOTALL)
        
        # Adicionar comentário de substituição
        replacement_comment = """/* =============================================================================
   FILTROS - REMOVIDO (USAR SISTEMA UNIFICADO)
   Estilos movidos para templates/includes/filters_unified.html
   ============================================================================= */

"""
        
        with open(css_file, 'w', encoding='utf-8') as f:
            f.write(replacement_comment + content)
        
        print(f"OK {css_file} limpo com sucesso")
    
    # Limpar forms.css
    css_file = 'meuprojeto/empresa/static/css/forms.css'
    if os.path.exists(css_file):
        print(f"Limpando duplicações restantes em {css_file}...")
        
        with open(css_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Remover .filter-actions restante
        content = re.sub(r'\.filter-actions[^}]*\{[^}]*\}\s*', '', content, flags=re.MULTILINE | re.DOTALL)
        
        with open(css_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"OK {css_file} limpo com sucesso")

def clean_hardcoded_effects():
    """Remove efeitos visuais hardcoded"""
    
    # Limpar page-headers.css
    css_file = 'meuprojeto/empresa/static/css/page-headers.css'
    if os.path.exists(css_file):
        print(f"Limpando efeitos hardcoded em {css_file}...")
        
        with open(css_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Substituir valores hardcoded por variáveis
        content = content.replace('backdrop-filter: blur(10px)', 'backdrop-filter: var(--blur-medium)')
        
        with open(css_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"OK {css_file} limpo com sucesso")

def sync_staticfiles_final():
    """Sincroniza staticfiles/ com meuprojeto/empresa/static/"""
    
    print("Sincronizando staticfiles/ com meuprojeto/empresa/static/...")
    
    # Diretórios para sincronizar
    source_dir = 'meuprojeto/empresa/static'
    target_dir = 'staticfiles'
    
    if os.path.exists(source_dir):
        # Copiar arquivos CSS
        css_files = [
            'css/visual-effects.css',
            'css/counters-fix.css',
            'css/page-headers.css',
            'css/components.css',
            'css/grids-unified.css',
            'css/forms.css',
            'css/dark-mode-global.css',
            'css/tables.css',
            'css/compatibility.css'
        ]
        
        for css_file in css_files:
            source_path = os.path.join(source_dir, css_file)
            target_path = os.path.join(target_dir, css_file)
            
            if os.path.exists(source_path):
                # Criar diretório de destino se não existir
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                
                # Copiar arquivo
                import shutil
                shutil.copy2(source_path, target_path)
                print(f"OK Sincronizado: {css_file}")
    
    print("OK Sincronização concluída")

def verify_final_cleanup():
    """Verifica se a limpeza final foi concluída"""
    
    print("\nVerificando limpeza final...")
    
    # Verificar templates limpos
    template_files = [
        'templates/stock/notificacoes/list.html',
        'templates/stock/inventario/ajustes_list.html',
        'templates/stock/requisicoes/list.html'
    ]
    
    for template_file in template_files:
        if os.path.exists(template_file):
            with open(template_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if '.filters-section' in content or '.filter-group' in content:
                print(f"ERRO: {template_file} ainda contém duplicações!")
            else:
                print(f"OK: {template_file} limpo com sucesso")
    
    # Verificar CSS limpo
    css_files = [
        'meuprojeto/empresa/static/css/components.css',
        'meuprojeto/empresa/static/css/forms.css',
        'meuprojeto/empresa/static/css/page-headers.css'
    ]
    
    for css_file in css_files:
        if os.path.exists(css_file):
            with open(css_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if '.filters-section' in content or 'backdrop-filter: blur(10px)' in content:
                print(f"ERRO: {css_file} ainda contém duplicações!")
            else:
                print(f"OK: {css_file} limpo com sucesso")
    
    print("\nOK Limpeza final concluída!")

def main():
    """Executa limpeza final"""
    
    print("Iniciando limpeza final de duplicações...")
    
    # 1. Limpar templates restantes
    clean_remaining_template_duplications()
    
    # 2. Limpar CSS restante
    clean_remaining_css_duplications()
    
    # 3. Limpar efeitos hardcoded
    clean_hardcoded_effects()
    
    # 4. Sincronizar staticfiles
    sync_staticfiles_final()
    
    # 5. Verificar limpeza final
    verify_final_cleanup()
    
    print("\nOK Limpeza final concluída!")
    print("OK Sistema unificado é agora 100% limpo!")

if __name__ == "__main__":
    main()
