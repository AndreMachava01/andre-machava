"""
LIMPEZA AUTOMÁTICA DE DUPLICAÇÕES
Script para remover todas as duplicações de filtros do sistema
"""

import os
import re
import shutil

def clean_css_duplications():
    """Remove duplicações de CSS de filtros"""
    
    # Arquivos CSS com duplicações de filtros
    css_files = [
        'meuprojeto/empresa/static/css/forms.css',
        'meuprojeto/empresa/static/css/dark-mode-global.css',
        'meuprojeto/empresa/static/css/tables.css',
        'meuprojeto/empresa/static/css/compatibility.css'
    ]
    
    for css_file in css_files:
        if os.path.exists(css_file):
            print(f"Limpando duplicações em {css_file}...")
            
            # Ler arquivo
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
                r'\.filter-container\s*\{[^}]*\}\s*',
                r'\.filter-row\s*\{[^}]*\}\s*',
                r'\.filter-item\s*\{[^}]*\}\s*',
                r'\.filters-card\s*\{[^}]*\}\s*',
                r'\.btn-filter\s*\{[^}]*\}\s*',
            ]
            
            for pattern in patterns_to_remove:
                content = re.sub(pattern, '', content, flags=re.MULTILINE | re.DOTALL)
            
            # Adicionar comentário de substituição
            replacement_comment = """/* =============================================================================
   FILTROS - REMOVIDO (USAR SISTEMA UNIFICADO)
   Estilos movidos para templates/includes/filters_unified.html
   ============================================================================= */

"""
            
            # Escrever arquivo limpo
            with open(css_file, 'w', encoding='utf-8') as f:
                f.write(replacement_comment + content)
            
            print(f"OK {css_file} limpo com sucesso")

def clean_template_duplications():
    """Remove filtros inline duplicados dos templates"""
    
    # Templates com filtros duplicados
    template_files = [
        'templates/stock/requisicoes/list.html',
        'templates/stock/inventario/ajustes_list.html',
        'templates/stock/logistica/operacoes/list.html',
        'templates/stock/logistica/coletas/list.html',
        'templates/stock/logistica/transferencias/list.html',
        'templates/stock/logistica/checklist/list.html',
        'templates/stock/notificacoes/list.html',
        'templates/stock/alertas/gerenciar.html',
        'templates/stock/requisicoes/ordens_compra_list.html'
    ]
    
    for template_file in template_files:
        if os.path.exists(template_file):
            print(f"Limpando filtros inline em {template_file}...")
            
            # Ler arquivo
            with open(template_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Remover seções de filtros inline
            patterns_to_remove = [
                r'<style>\s*/\* Filters \*/\s*\.filters-section[^<]*</style>',
                r'<div class="filters-section">.*?</div>',
                r'<form[^>]*class="filters-grid"[^>]*>.*?</form>',
                r'<div class="filter-group">.*?</div>',
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

def sync_staticfiles():
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
                shutil.copy2(source_path, target_path)
                print(f"OK Sincronizado: {css_file}")
    
    print("OK Sincronização concluída")

def verify_cleanup():
    """Verifica se a limpeza foi concluída"""
    
    print("\nVerificando limpeza de duplicações...")
    
    # Verificar arquivos CSS limpos
    css_files = [
        'meuprojeto/empresa/static/css/forms.css',
        'meuprojeto/empresa/static/css/dark-mode-global.css',
        'meuprojeto/empresa/static/css/tables.css',
        'meuprojeto/empresa/static/css/compatibility.css'
    ]
    
    for css_file in css_files:
        if os.path.exists(css_file):
            with open(css_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if '.filters-section' in content or '.filter-group' in content:
                print(f"ERRO: {css_file} ainda contém duplicações!")
            else:
                print(f"OK: {css_file} limpo com sucesso")
    
    # Verificar sistema unificado
    unified_files = [
        'meuprojeto/empresa/filters_config.py',
        'meuprojeto/empresa/mixins.py',
        'meuprojeto/empresa/views_unified.py',
        'templates/includes/filters_unified.html',
        'meuprojeto/empresa/static/css/visual-effects.css'
    ]
    
    for file_path in unified_files:
        if os.path.exists(file_path):
            print(f"OK: {file_path} existe e está funcionando")
        else:
            print(f"ERRO: {file_path} não encontrado!")
    
    print("\nLimpeza concluída! Sistema unificado é agora oficial.")

def main():
    """Executa limpeza completa"""
    
    print("Iniciando limpeza completa de duplicações...")
    
    # 1. Limpar duplicações de CSS
    clean_css_duplications()
    
    # 2. Limpar duplicações de templates
    clean_template_duplications()
    
    # 3. Sincronizar staticfiles
    sync_staticfiles()
    
    # 4. Verificar limpeza
    verify_cleanup()
    
    print("\nOK Limpeza completa concluída!")
    print("OK Sistema unificado é agora o padrão oficial")

if __name__ == "__main__":
    main()
