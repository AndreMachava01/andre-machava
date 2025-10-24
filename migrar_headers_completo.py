#!/usr/bin/env python3
"""
Script Completo para Verificação e Correção de Headers em Templates Django
Verifica e corrige todos os headers dos templates para usar o sistema unificado
"""

import os
import re
import shutil
from pathlib import Path
from datetime import datetime

class HeaderMigrator:
    def __init__(self, templates_dir="templates"):
        self.templates_dir = Path(templates_dir)
        self.backup_dir = Path("backups_headers")
        self.log_file = Path("header_migracao_log.txt")
        self.stats = {
            'total_templates': 0,
            'headers_corrected': 0,
            'headers_already_correct': 0,
            'backups_created': 0,
            'errors': 0,
            'skipped': 0
        }
        
    def log(self, message, level="INFO"):
        """Registra mensagens no log"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] [{level}] {message}"
        print(log_message)
        
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_message + "\n")
    
    def create_backup_dir(self):
        """Cria diretório de backups"""
        if not self.backup_dir.exists():
            self.backup_dir.mkdir(parents=True)
            self.log(f"Diretório de backup criado: {self.backup_dir}")
    
    def is_template_with_header(self, file_path):
        """Verifica se é um template que deve ter header unificado"""
        # Templates que devem ter header unificado
        include_patterns = [
            'main.html',
            'list.html',
            'lista.html',
            'index.html'
        ]
        
        # Templates que NÃO devem ter header unificado
        exclude_patterns = [
            'base_admin.html',
            'base_list.html',
            'form.html',
            'detail.html',
            'delete.html',
            'create.html',
            'edit.html',
            'print.html',
            'documento.html',
            'relatorio.html',
            'calendario.html',
            'inscrever.html',
            'inscricoes.html',
            'dashboard.html',
            'login.html',
            'custom_login.html',
            'base_site.html',
            'page_header.html',
            'filters_unified.html',
            'filters_usage_example.html',
            'pdf_template.html',
            'preview.html',
            'canhoto.html',
            'calcular.html',
            'marcar_paga.html',
            'reabrir.html',
            'validar_fechamento.html',
            'aprovar.html',
            'rejeitar.html',
            'implementar.html',
            'efetivar.html',
            'implement.html',
            'reject.html',
            'approve.html',
            'avaliar.html',
            'deletar_inscricao.html',
            'add_batch.html',
            'criterios.html',
            'criterio_delete.html',
            'criterio_form.html',
            'vinculacao.html',
            'associar_produto.html',
            'editar_associacao.html',
            'produtos.html',
            'print_contagem.html',
            'print_blank.html',
            'rastreamento_form.html',
            'form_unified.html',
            'add_item.html',
            'compra_externa_add_item.html',
            'compra_externa_create.html',
            'compra_externa_create_order.html',
            'compra_externa_detail.html',
            'compra_externa_detail_new.html',
            'compra_externa_documento.html',
            'edit_quantidade_atendida.html',
            'guia_recebimento.html',
            'guia_recebimento_preview.html',
            'guia_transferencia.html',
            'guia_transferencia_preview.html',
            'ordem_compra_confirm_items.html',
            'ordem_compra_confirm_tipo.html',
            'ordem_compra_enviar_email.html',
            'ordem_compra_historico_envios.html',
            'ordem_compra_preview.html',
            'ordem_compra_print.html',
            'ordem_compra_receipt_note.html',
            'ordem_compra_receive.html',
            'quick_add_item.html',
            'transfer_preview.html',
            'produto_sucursal.html',
            'nota_recebimento.html',
            'receber.html',
            'verificar_stock.html',
            'atribuir.html',
            'concluir.html',
            'confirmar_coleta.html',
            'confirmar_entrega.html',
            'editar_prioridade.html',
            'iniciar_transporte.html',
            'assinatura_form.html',
            'documento_form.html',
            'etiqueta_detail.html',
            'etiqueta_form.html',
            'guia_detail.html',
            'guia_form.html',
            'prova_detail.html',
            'prova_form.html',
            'validar_prova_form.html',
            'comprovante_recebimento.html',
            'guia_coleta.html',
            'guia_entrega.html',
            'delay_notification.html',
            'delivery_confirmation.html',
            'tracking_update.html',
            'change_form.html',
            'sucursal_inline.html',
            'change_list.html'
        ]
        
        filename = file_path.name.lower()
        
        # Verifica se deve ser excluído
        for exclude in exclude_patterns:
            if exclude in filename:
                return False
        
        # Verifica se é um template que deve ter header
        for pattern in include_patterns:
            if pattern in filename:
                return True
                
        return False
    
    def backup_template(self, file_path):
        """Cria backup do template"""
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
    
    def has_unified_header(self, content):
        """Verifica se o template já tem header unificado"""
        unified_patterns = [
            r'{% include [\'"]components/page_header\.html[\'"] %}',
            r'{% include [\'"]includes/page_header\.html[\'"] %}',
            r'{% include [\'"]page_header\.html[\'"] %}',
            r'<div class="page-header">',
            r'<header class="page-header">',
            r'class="page-header-unified"',
            r'class="unified-header"'
        ]
        
        for pattern in unified_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        return False
    
    def has_old_header(self, content):
        """Verifica se o template tem header antigo/personalizado"""
        old_patterns = [
            r'<div class="header[^"]*">',
            r'<header[^>]*class="[^"]*header[^"]*"[^>]*>',
            r'<div class="[^"]*title[^"]*">',
            r'<h1[^>]*class="[^"]*title[^"]*"[^>]*>',
            r'<div class="[^"]*breadcrumb[^"]*">',
            r'<nav[^>]*class="[^"]*breadcrumb[^"]*"[^>]*>',
            r'<div class="[^"]*page-title[^"]*">',
            r'<div class="[^"]*main-title[^"]*">',
            r'<div class="[^"]*section-title[^"]*">',
            r'<div class="[^"]*content-header[^"]*">',
            r'<div class="[^"]*list-header[^"]*">',
            r'<div class="[^"]*table-header[^"]*">'
        ]
        
        for pattern in old_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        return False
    
    def get_entity_name_from_path(self, file_path):
        """Extrai o nome da entidade do caminho do arquivo"""
        path_str = str(file_path).lower()
        
        # Padrões para extrair nome da entidade
        patterns = [
            r'/([^/]+)/main\.html$',
            r'/([^/]+)/list\.html$',
            r'/([^/]+)/lista\.html$',
            r'/([^/]+)/index\.html$'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, path_str)
            if match:
                entity = match.group(1)
                # Mapear nomes específicos
                entity_map = {
                    'funcionarios': 'funcionarios',
                    'cargos': 'cargos',
                    'departamentos': 'departamentos',
                    'presencas': 'presencas',
                    'treinamentos': 'treinamentos',
                    'avaliacoes': 'avaliacoes',
                    'feriados': 'feriados',
                    'transferencias': 'transferencias',
                    'folha_salarial': 'folha_salarial',
                    'salarios': 'salarios',
                    'promocoes': 'promocoes',
                    'produtos': 'produtos',
                    'materiais': 'materiais',
                    'fornecedores': 'fornecedores',
                    'categorias': 'categorias',
                    'inventario': 'inventario',
                    'requisicoes': 'requisicoes',
                    'transferencias': 'transferencias',
                    'notificacoes': 'notificacoes',
                    'movimentos': 'movimentos',
                    'alertas': 'alertas',
                    'operacoes': 'operacoes_logisticas',
                    'checklist': 'checklists',
                    'coletas': 'coletas',
                    'rastreamento': 'rastreamento',
                    'transportadoras': 'transportadoras',
                    'viaturas': 'viaturas',
                    'veiculos': 'veiculos',
                    'etiquetas': 'etiquetas_pod',
                    'guias': 'guias_pod',
                    'provas': 'provas_pod',
                    'ordens_compra': 'ordens_compra',
                    'por_sucursal': 'por_sucursal',
                    'sucursal_detail': 'stock_sucursal_detail',
                    'verificar_stock_baixo': 'stock_baixo',
                    'ajustes_list': 'ajustes_inventario',
                    'horas_extras_lista': 'horas_extras',
                    'detalhes_mes': 'detalhes_presenca',
                    'inscricoes': 'inscricoes_treinamento',
                    'inscrever': 'treinamentos_inscrever',
                    'relatorio': 'transferencias_relatorio',
                    'beneficios': 'beneficios_salario',
                    'descontos': 'descontos_salario',
                    'criterios': 'criterios_avaliacao'
                }
                return entity_map.get(entity, entity)
        
        return 'default'
    
    def get_title_from_content(self, content):
        """Extrai o título do template"""
        # Padrões para extrair título
        title_patterns = [
            r'{% block title %}([^%]+){% endblock %}',
            r'<title>([^<]+)</title>',
            r'<h1[^>]*>([^<]+)</h1>',
            r'<div[^>]*class="[^"]*title[^"]*"[^>]*>([^<]+)</div>',
            r'<div[^>]*class="[^"]*page-title[^"]*"[^>]*>([^<]+)</div>',
            r'<div[^>]*class="[^"]*main-title[^"]*"[^>]*>([^<]+)</div>'
        ]
        
        for pattern in title_patterns:
            match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
            if match:
                title = match.group(1).strip()
                # Limpar tags HTML se houver
                title = re.sub(r'<[^>]+>', '', title)
                return title
        
        return None
    
    def replace_old_header(self, content, entity_name, title=None):
        """Substitui header antigo pelo header unificado"""
        if not title:
            title = entity_name.replace('_', ' ').title()
        
        # Header unificado
        unified_header = f'''<!-- HEADER UNIFICADO -->
{{% include 'components/page_header.html' with title="{title}" entity_name="{entity_name}" %}}'''
        
        # Padrões para remover headers antigos
        old_header_patterns = [
            r'<!-- HEADER[^>]*-->.*?(?=\n\n|\n{%|\n<div|\n<header|\n<h1|\Z)',
            r'<div class="[^"]*header[^"]*"[^>]*>.*?</div>',
            r'<header[^>]*>.*?</header>',
            r'<div class="[^"]*title[^"]*"[^>]*>.*?</div>',
            r'<div class="[^"]*page-title[^"]*"[^>]*>.*?</div>',
            r'<div class="[^"]*main-title[^"]*"[^>]*>.*?</div>',
            r'<div class="[^"]*section-title[^"]*"[^>]*>.*?</div>',
            r'<div class="[^"]*content-header[^"]*"[^>]*>.*?</div>',
            r'<div class="[^"]*list-header[^"]*"[^>]*>.*?</div>',
            r'<div class="[^"]*table-header[^"]*"[^>]*>.*?</div>',
            r'<h1[^>]*class="[^"]*title[^"]*"[^>]*>.*?</h1>',
            r'<div class="[^"]*breadcrumb[^"]*"[^>]*>.*?</div>',
            r'<nav[^>]*class="[^"]*breadcrumb[^"]*"[^>]*>.*?</nav>'
        ]
        
        # Remover headers antigos
        for pattern in old_header_patterns:
            content = re.sub(pattern, '', content, flags=re.IGNORECASE | re.DOTALL)
        
        # Limpar linhas vazias extras
        content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
        
        # Adicionar header unificado após extends
        extends_pattern = r'({% extends [\'"][^\'"]+[\'"] %})'
        if re.search(extends_pattern, content):
            content = re.sub(
                extends_pattern,
                r'\1\n\n' + unified_header,
                content,
                count=1
            )
        else:
            # Se não encontrar extends, adicionar no início
            content = unified_header + '\n\n' + content
        
        return content
    
    def migrate_template_header(self, file_path):
        """Migra header de um template"""
        try:
            # Ler conteúdo
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Verificar se já tem header unificado
            if self.has_unified_header(content):
                self.stats['headers_already_correct'] += 1
                self.log(f"Header já unificado: {file_path}")
                return True
            
            # Verificar se tem header antigo
            if not self.has_old_header(content):
                self.stats['skipped'] += 1
                self.log(f"Sem header para migrar: {file_path}")
                return True
            
            # Criar backup
            if not self.backup_template(file_path):
                return False
            
            # Extrair informações
            entity_name = self.get_entity_name_from_path(file_path)
            title = self.get_title_from_content(content)
            
            # Migrar header
            content = self.replace_old_header(content, entity_name, title)
            
            # Escrever arquivo modificado
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            self.stats['headers_corrected'] += 1
            self.log(f"Header migrado com sucesso: {file_path} (entidade: {entity_name})")
            return True
            
        except Exception as e:
            self.stats['errors'] += 1
            self.log(f"Erro ao migrar header de {file_path}: {e}", "ERROR")
            return False
    
    def scan_templates(self):
        """Escaneia todos os templates HTML"""
        html_files = list(self.templates_dir.rglob("*.html"))
        self.stats['total_templates'] = len(html_files)
        
        self.log(f"Encontrados {len(html_files)} templates HTML")
        
        templates_to_migrate = []
        
        for file_path in html_files:
            if self.is_template_with_header(file_path):
                templates_to_migrate.append(file_path)
            else:
                self.stats['skipped'] += 1
                self.log(f"Pulando (não precisa de header): {file_path}")
        
        return templates_to_migrate
    
    def verify_migration(self):
        """Verifica se a migração foi bem-sucedida"""
        self.log("=== VERIFICAÇÃO PÓS-MIGRAÇÃO ===")
        
        unified_headers = 0
        old_headers = 0
        
        for file_path in self.templates_dir.rglob("*.html"):
            if self.is_template_with_header(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    if self.has_unified_header(content):
                        unified_headers += 1
                    elif self.has_old_header(content):
                        old_headers += 1
                        self.log(f"Ainda tem header antigo: {file_path}", "WARNING")
                        
                except Exception as e:
                    self.log(f"Erro ao verificar {file_path}: {e}", "ERROR")
        
        self.log(f"Templates com header unificado: {unified_headers}")
        self.log(f"Templates com header antigo: {old_headers}")
        
        return unified_headers, old_headers
    
    def run_migration(self):
        """Executa a migração completa"""
        self.log("=== INICIANDO MIGRAÇÃO DE HEADERS ===")
        
        # Criar diretório de backup
        self.create_backup_dir()
        
        # Escanear templates
        templates_to_migrate = self.scan_templates()
        
        self.log(f"Templates para migrar header: {len(templates_to_migrate)}")
        
        # Migrar templates
        for file_path in templates_to_migrate:
            self.migrate_template_header(file_path)
        
        # Verificar migração
        unified_headers, old_headers = self.verify_migration()
        
        # Relatório final
        self.log("=== RELATÓRIO FINAL ===")
        self.log(f"Total de templates encontrados: {self.stats['total_templates']}")
        self.log(f"Headers migrados: {self.stats['headers_corrected']}")
        self.log(f"Headers já unificados: {self.stats['headers_already_correct']}")
        self.log(f"Backups criados: {self.stats['backups_created']}")
        self.log(f"Templates pulados: {self.stats['skipped']}")
        self.log(f"Erros encontrados: {self.stats['errors']}")
        self.log(f"Templates com header unificado: {unified_headers}")
        self.log(f"Templates com header antigo: {old_headers}")
        
        if self.stats['errors'] == 0:
            self.log("MIGRAÇÃO DE HEADERS CONCLUÍDA COM SUCESSO!", "SUCCESS")
        else:
            self.log(f"MIGRAÇÃO DE HEADERS CONCLUÍDA COM {self.stats['errors']} ERROS", "WARNING")

def main():
    """Função principal"""
    print("=== SCRIPT DE MIGRAÇÃO DE HEADERS DJANGO ===")
    print("Verificando e corrigindo todos os headers dos templates...")
    
    # Verificar se diretório templates existe
    if not Path("templates").exists():
        print("ERRO: Diretório 'templates' não encontrado!")
        return
    
    # Executar migração
    migrator = HeaderMigrator()
    migrator.run_migration()
    
    print("\n=== MIGRAÇÃO DE HEADERS CONCLUÍDA ===")
    print("Verifique o arquivo 'header_migracao_log.txt' para detalhes completos.")

if __name__ == "__main__":
    main()
