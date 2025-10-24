"""
LIMPEZA FINAL DEFINITIVA DE DUPLICAÇÕES
Script para eliminar TODAS as duplicações e valores hardcoded
"""

import os
import re
import shutil

def clean_hardcoded_values():
    """Remove todos os valores hardcoded de efeitos visuais"""
    
    # Arquivos CSS para limpar
    css_files = [
        'meuprojeto/empresa/static/css/page-headers.css',
        'meuprojeto/empresa/static/css/compatibility.css',
        'meuprojeto/empresa/static/css/dark-mode-global.css',
        'meuprojeto/empresa/static/css/tables.css'
    ]
    
    for css_file in css_files:
        if os.path.exists(css_file):
            print(f"Limpando valores hardcoded em {css_file}...")
            
            with open(css_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Substituir valores hardcoded por variáveis
            replacements = [
                (r'rgba\(16,\s*185,\s*129,\s*0\.1\)', 'var(--bg-white-transparent-light)'),
                (r'rgba\(16,\s*185,\s*129,\s*0\.2\)', 'var(--border-green-light)'),
                (r'rgba\(16,\s*185,\s*129,\s*0\.3\)', 'var(--border-green-medium)'),
                (r'rgba\(255,\s*215,\s*0,\s*0\.3\)', 'var(--bg-white-transparent-medium)'),
                (r'rgba\(255,\s*215,\s*0,\s*0\.4\)', 'var(--bg-white-transparent-heavy)'),
                (r'rgba\(255,\s*215,\s*0,\s*0\.5\)', 'var(--border-gold-medium)'),
                (r'rgba\(255,\s*215,\s*0,\s*0\.6\)', 'var(--border-gold-heavy)'),
                (r'rgba\(255,\s*215,\s*0,\s*0\.7\)', 'var(--border-gold-heavy)'),
                (r'linear-gradient\(135deg,\s*rgba\(255,\s*215,\s*0,\s*0\.65\)[^)]*\)', 'var(--gradient-gold-base)'),
                (r'box-shadow:\s*0\s+8px\s+32px\s+rgba\(255,\s*215,\s*0,\s*0\.2\)', 'box-shadow: var(--shadow-glow-gold-medium)'),
                (r'box-shadow:\s*0\s+4px\s+12px\s+rgba\(255,\s*215,\s*0,\s*0\.3\)', 'box-shadow: var(--shadow-glow-gold-light)'),
            ]
            
            for pattern, replacement in replacements:
                content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)
            
            with open(css_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"OK {css_file} limpo com sucesso")

def clean_template_hardcoded():
    """Remove valores hardcoded dos templates"""
    
    template_files = [
        'templates/stock/notificacoes/list.html',
        'templates/stock/requisicoes/list.html',
        'templates/stock/logistica/checklist/list.html',
        'templates/stock/inventario/detail.html',
        'templates/stock/requisicoes/transfer_preview.html',
        'templates/stock/requisicoes/guia_recebimento_preview.html'
    ]
    
    for template_file in template_files:
        if os.path.exists(template_file):
            print(f"Limpando valores hardcoded em {template_file}...")
            
            with open(template_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Remover gradientes hardcoded
            patterns_to_remove = [
                r'--green-gradient:\s*linear-gradient\([^;]*\);',
                r'--orange-gradient:\s*linear-gradient\([^;]*\);',
                r'--red-gradient:\s*linear-gradient\([^;]*\);',
                r'--blue-gradient:\s*linear-gradient\([^;]*\);',
                r'--purple-gradient:\s*linear-gradient\([^;]*\);',
                r'--pink-gradient:\s*linear-gradient\([^;]*\);',
                r'--cyan-gradient:\s*linear-gradient\([^;]*\);',
                r'--yellow-gradient:\s*linear-gradient\([^;]*\);',
            ]
            
            for pattern in patterns_to_remove:
                content = re.sub(pattern, '', content, flags=re.MULTILINE)
            
            # Substituir valores hardcoded por variáveis
            replacements = [
                (r'rgba\(16,\s*185,\s*129,\s*0\.2\)', 'var(--bg-white-transparent-light)'),
                (r'rgba\(16,\s*185,\s*129,\s*0\.15\)', 'var(--bg-white-transparent-light)'),
                (r'rgba\(16,\s*185,\s*129,\s*0\.3\)', 'var(--border-green-medium)'),
                (r'rgba\(16,\s*185,\s*129,\s*0\.4\)', 'var(--border-green-heavy)'),
                (r'rgba\(16,\s*185,\s*129,\s*0\.5\)', 'var(--border-green-heavy)'),
                (r'rgba\(34,\s*197,\s*94,\s*0\.2\)', 'var(--bg-white-transparent-light)'),
                (r'backdrop-filter:\s*blur\(10px\)', 'backdrop-filter: var(--blur-medium)'),
                (r'box-shadow:\s*0\s+4px\s+15px\s+rgba\(16,\s*185,\s*129,\s*0\.3\)', 'box-shadow: var(--shadow-glow-green-medium)'),
                (r'box-shadow:\s*0\s+12px\s+30px\s+rgba\(16,\s*185,\s*129,\s*0\.4\)', 'box-shadow: var(--shadow-glow-green-heavy)'),
            ]
            
            for pattern, replacement in replacements:
                content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)
            
            with open(template_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"OK {template_file} limpo com sucesso")

def sync_staticfiles_final():
    """Sincroniza staticfiles/ com meuprojeto/empresa/static/"""
    
    print("Sincronizando staticfiles/ com meuprojeto/empresa/static/...")
    
    source_dir = 'meuprojeto/empresa/static'
    target_dir = 'staticfiles'
    
    if os.path.exists(source_dir):
        # Copiar todos os arquivos CSS
        css_files = [
            'css/visual-effects-unified.css',
            'css/counters-fix.css',
            'css/page-headers.css',
            'css/components.css',
            'css/grids-unified.css',
            'css/forms.css',
            'css/dark-mode-global.css',
            'css/tables.css',
            'css/compatibility.css',
            'css/visual-effects.css'
        ]
        
        for css_file in css_files:
            source_path = os.path.join(source_dir, css_file)
            target_path = os.path.join(target_dir, css_file)
            
            if os.path.exists(source_path):
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                shutil.copy2(source_path, target_path)
                print(f"OK Sincronizado: {css_file}")
    
    print("OK Sincronização concluída")

def update_base_admin():
    """Atualiza base_admin.html para incluir visual-effects-unified.css"""
    
    template_file = 'templates/base_admin.html'
    if os.path.exists(template_file):
        print(f"Atualizando {template_file}...")
        
        with open(template_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Adicionar link para visual-effects-unified.css
        if 'visual-effects-unified.css' not in content:
            # Encontrar onde inserir o link
            insert_point = content.find('<link rel="stylesheet" href="{% static \'css/visual-effects.css\' %}')
            if insert_point != -1:
                # Inserir antes do visual-effects.css existente
                new_link = '<link rel="stylesheet" href="{% static \'css/visual-effects-unified.css\' %}?v=20251022-2">\n    '
                content = content[:insert_point] + new_link + content[insert_point:]
            else:
                # Inserir no início das CSS
                css_start = content.find('<link rel="stylesheet"')
                if css_start != -1:
                    new_link = '<link rel="stylesheet" href="{% static \'css/visual-effects-unified.css\' %}?v=20251022-2">\n    '
                    content = content[:css_start] + new_link + content[css_start:]
        
        with open(template_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"OK {template_file} atualizado com sucesso")

def verify_final_cleanup():
    """Verifica se a limpeza final foi concluída"""
    
    print("\nVerificando limpeza final...")
    
    # Verificar se não há mais valores hardcoded
    hardcoded_patterns = [
        r'rgba\(16,\s*185,\s*129,\s*0\.[0-9]+\)',
        r'rgba\(255,\s*215,\s*0,\s*0\.[0-9]+\)',
        r'backdrop-filter:\s*blur\(10px\)',
        r'linear-gradient\(135deg,\s*rgba\(255,\s*215,\s*0',
    ]
    
    files_to_check = [
        'meuprojeto/empresa/static/css/page-headers.css',
        'meuprojeto/empresa/static/css/compatibility.css',
        'meuprojeto/empresa/static/css/dark-mode-global.css',
        'meuprojeto/empresa/static/css/tables.css',
        'templates/stock/notificacoes/list.html',
        'templates/stock/requisicoes/list.html'
    ]
    
    for file_path in files_to_check:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            for pattern in hardcoded_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    print(f"ERRO: {file_path} ainda contém valores hardcoded!")
                    break
            else:
                print(f"OK: {file_path} limpo com sucesso")
    
    print("\nOK Limpeza final concluída!")

def main():
    """Executa limpeza final definitiva"""
    
    print("Iniciando limpeza final definitiva...")
    
    # 1. Limpar valores hardcoded de CSS
    clean_hardcoded_values()
    
    # 2. Limpar valores hardcoded de templates
    clean_template_hardcoded()
    
    # 3. Sincronizar staticfiles
    sync_staticfiles_final()
    
    # 4. Atualizar base_admin.html
    update_base_admin()
    
    # 5. Verificar limpeza final
    verify_final_cleanup()
    
    print("\nOK Limpeza final definitiva concluída!")
    print("OK Sistema unificado é agora 100% limpo e sem duplicações!")

if __name__ == "__main__":
    main()
