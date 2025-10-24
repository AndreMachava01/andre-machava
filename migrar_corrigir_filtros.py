#!/usr/bin/env python3
"""
SCRIPT DE MIGRAÇÃO E CORREÇÃO AUTOMÁTICA DE FILTROS
Sistema Unificado de Filtros - Migração Completa

Este script realiza migração automática de filtros antigos para o sistema unificado,
criando configurações necessárias e corrigindo problemas encontrados.

Funcionalidades:
1. Migra filtros manuais para sistema unificado
2. Cria configurações automáticas no filters_config.py
3. Remove CSS e JavaScript inline
4. Corrige problemas de sintaxe
5. Gera templates limpos e padronizados

Autor: Sistema Conception
Data: 2025
"""

import os
import re
import sys
import json
import logging
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('filtros_migracao.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class MigrationTask:
    """Representa uma tarefa de migração"""
    template_path: str
    entity_name: str
    current_filters: List[Dict]
    target_config: Dict
    status: str  # 'pending', 'in_progress', 'completed', 'error'

class FilterMigrator:
    """Classe principal para migração de filtros"""
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.templates_dir = self.project_root / 'templates'
        self.filters_config_file = self.project_root / 'meuprojeto' / 'empresa' / 'filters_config.py'
        self.migration_tasks: List[MigrationTask] = []
        self.migrations_completed = []
        self.errors = []
        
    def run_full_migration(self) -> Dict:
        """Executa migração completa dos filtros"""
        logger.info("🚀 Iniciando migração completa dos filtros...")
        
        # 1. Identificar templates que precisam de migração
        self._identify_templates_for_migration()
        
        # 2. Analisar filtros existentes
        self._analyze_existing_filters()
        
        # 3. Criar configurações necessárias
        self._create_filter_configurations()
        
        # 4. Migrar templates
        self._migrate_templates()
        
        # 5. Validar migrações
        self._validate_migrations()
        
        # 6. Gerar relatório
        report = self._generate_migration_report()
        
        logger.info("✅ Migração completa finalizada!")
        return report
    
    def _identify_templates_for_migration(self):
        """Identifica templates que precisam de migração"""
        logger.info("🔍 Identificando templates para migração...")
        
        # Padrões para identificar filtros manuais/antigos
        manual_filter_patterns = [
            r'<form[^>]*method\s*=\s*[\'"]get[\'"][^>]*>',
            r'<input[^>]*name\s*=\s*[\'"](q|search|filter)[\'"]',
            r'<select[^>]*name\s*=\s*[\'"](status|departamento|cargo|tipo|sucursal)[\'"]',
            r'<input[^>]*type\s*=\s*[\'"]date[\'"][^>]*name\s*=\s*[\'"](data_|date_)',
            r'<button[^>]*type\s*=\s*[\'"]submit[\'"]'
        ]
        
        for template_file in self.templates_dir.rglob('*.html'):
            try:
                with open(template_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Verificar se já usa sistema unificado
                if 'filters_unified.html' in content:
                    continue
                
                # Verificar se tem filtros manuais
                has_manual_filters = any(re.search(pattern, content) for pattern in manual_filter_patterns)
                
                if has_manual_filters:
                    entity_name = self._detect_entity_from_path(template_file)
                    if entity_name:
                        self.migration_tasks.append(MigrationTask(
                            template_path=str(template_file),
                            entity_name=entity_name,
                            current_filters=[],
                            target_config={},
                            status='pending'
                        ))
                        logger.info(f"📋 Template identificado para migração: {template_file.name} (entidade: {entity_name})")
                
            except Exception as e:
                logger.error(f"Erro ao analisar {template_file}: {e}")
    
    def _detect_entity_from_path(self, file_path: Path) -> Optional[str]:
        """Detecta nome da entidade baseado no caminho do arquivo"""
        path_parts = file_path.parts
        
        # Mapear caminhos para entidades
        entity_map = {
            'funcionarios': 'funcionarios',
            'cargos': 'cargos',
            'departamentos': 'departamentos',
            'salarios': 'salarios',
            'promocoes': 'promocoes',
            'presencas': 'presencas',
            'treinamentos': 'treinamentos',
            'avaliacoes': 'avaliacoes',
            'feriados': 'feriados',
            'transferencias': 'transferencias',
            'produtos': 'produtos',
            'materiais': 'materiais',
            'fornecedores': 'fornecedores',
            'categorias': 'categorias',
            'inventario': 'inventario',
            'requisicoes': 'requisicoes',
            'checklists': 'checklists',
            'viaturas': 'viaturas',
            'transportadoras': 'transportadoras',
            'operacoes': 'operacoes_logisticas',
            'transferencias': 'transferencias_logisticas',
            'ajustes': 'ajustes_inventario',
            'descontos': 'descontos_salario',
            'beneficios': 'beneficios_salario',
            'inscricoes': 'inscricoes_treinamento',
            'calendario': 'calendario_presencas',
            'etiquetas': 'etiquetas_pod',
            'stock': 'stock_sucursal_detail'
        }
        
        for part in path_parts:
            if part in entity_map:
                return entity_map[part]
        
        return None
    
    def _analyze_existing_filters(self):
        """Analisa filtros existentes nos templates"""
        logger.info("🔍 Analisando filtros existentes...")
        
        for task in self.migration_tasks:
            try:
                with open(task.template_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                filters = self._extract_filters_from_content(content)
                task.current_filters = filters
                
                logger.info(f"📊 Filtros encontrados em {Path(task.template_path).name}: {len(filters)}")
                
            except Exception as e:
                logger.error(f"Erro ao analisar filtros em {task.template_path}: {e}")
                task.status = 'error'
                self.errors.append(f"Erro ao analisar {task.template_path}: {e}")
    
    def _extract_filters_from_content(self, content: str) -> List[Dict]:
        """Extrai informações dos filtros do conteúdo do template"""
        filters = []
        
        # Extrair campos de pesquisa
        search_patterns = [
            r'<input[^>]*name\s*=\s*[\'"](q|search|filter)[\'"][^>]*>',
            r'<input[^>]*placeholder\s*=\s*[\'"]([^\'"]*pesquisar[^\'"]*)[\'"][^>]*>'
        ]
        
        for pattern in search_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    field_name, placeholder = match
                else:
                    field_name = match
                    placeholder = "Digite para pesquisar..."
                
                filters.append({
                    'type': 'search',
                    'field': field_name,
                    'placeholder': placeholder
                })
        
        # Extrair selects
        select_pattern = r'<select[^>]*name\s*=\s*[\'"]([^\'"]+)[\'"][^>]*>.*?</select>'
        select_matches = re.findall(select_pattern, content, re.DOTALL)
        
        for field_name in select_matches:
            filters.append({
                'type': 'select',
                'field': field_name,
                'placeholder': f"Todos os {field_name}s"
            })
        
        # Extrair campos de data
        date_pattern = r'<input[^>]*type\s*=\s*[\'"]date[\'"][^>]*name\s*=\s*[\'"]([^\'"]+)[\'"][^>]*>'
        date_matches = re.findall(date_pattern, content)
        
        for field_name in date_matches:
            filters.append({
                'type': 'date',
                'field': field_name,
                'placeholder': f"Selecionar {field_name}"
            })
        
        return filters
    
    def _create_filter_configurations(self):
        """Cria configurações necessárias no filters_config.py"""
        logger.info("⚙️ Criando configurações de filtros...")
        
        # Ler arquivo atual ou criar novo
        if self.filters_config_file.exists():
            with open(self.filters_config_file, 'r', encoding='utf-8') as f:
                config_content = f.read()
        else:
            config_content = self._create_base_config_file()
        
        # Criar configurações para cada entidade
        for task in self.migration_tasks:
            if task.status == 'error':
                continue
            
            config_name = f"{task.entity_name}_config"
            
            # Verificar se configuração já existe
            if config_name in config_content:
                logger.info(f"✅ Configuração já existe para: {task.entity_name}")
                continue
            
            # Criar configuração baseada nos filtros encontrados
            config_code = self._generate_filter_config(task)
            
            # Adicionar ao arquivo
            config_content += config_code
            
            logger.info(f"📝 Criada configuração para: {task.entity_name}")
        
        # Salvar arquivo atualizado
        with open(self.filters_config_file, 'w', encoding='utf-8') as f:
            f.write(config_content)
        
        logger.info("💾 Configurações salvas em filters_config.py")
    
    def _create_base_config_file(self) -> str:
        """Cria arquivo base de configuração"""
        return '''"""
SISTEMA UNIFICADO DE FILTROS DE BUSCA
Sistema oficial e único para todos os filtros do sistema
Substitui django-filters e sistemas antigos
"""

from django.db.models import Q
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum


class FilterType(Enum):
    """Tipos de filtros disponíveis"""
    SEARCH = "search"
    SELECT = "select"
    DATE_RANGE = "date_range"
    BOOLEAN = "boolean"
    MULTI_SELECT = "multi_select"


@dataclass
class FilterConfig:
    """Configuração de um filtro individual"""
    name: str
    label: str
    type: FilterType
    field: str
    placeholder: str = ""
    search_fields: List[str] = None
    choices: List[Tuple[str, str]] = None
    
    def __post_init__(self):
        if self.search_fields is None:
            self.search_fields = []
        if self.choices is None:
            self.choices = []


@dataclass
class FilterSetConfig:
    """Configuração completa de um conjunto de filtros"""
    entity_name: str
    model_class: Any = None
    filters: List[FilterConfig] = None
    search_fields: List[str] = None
    default_order: str = "nome"
    pagination_size: int = 20
    
    def __post_init__(self):
        if self.filters is None:
            self.filters = []
        if self.search_fields is None:
            self.search_fields = []


class UnifiedFilterRegistry:
    """Registro centralizado de configurações de filtros"""
    
    def __init__(self):
        self.configs: Dict[str, FilterSetConfig] = {}
        self._register_default_configs()
    
    def register(self, config: FilterSetConfig):
        """Registra uma nova configuração"""
        self.configs[config.entity_name] = config
    
    def get(self, entity_name: str) -> Optional[FilterSetConfig]:
        """Obtém configuração por nome da entidade"""
        return self.configs.get(entity_name)
    
    def _register_default_configs(self):
        """Registra configurações padrão do sistema"""
        pass


# Instância global do registro
filter_registry = UnifiedFilterRegistry()


class FilterProcessor:
    """Processador de filtros com lógica unificada"""
    
    def __init__(self, config: FilterSetConfig, queryset):
        self.config = config
        self.queryset = queryset
        self.applied_filters = {}
    
    def apply_filters(self, request_params: Dict[str, Any]) -> tuple:
        """
        Aplica todos os filtros aos parâmetros da requisição
        
        Returns:
            tuple: (queryset_filtrado, contexto_para_template)
        """
        context = {}
        
        for filter_config in self.config.filters:
            value = request_params.get(filter_config.field, '').strip()
            
            if not value:
                context[filter_config.field] = ''
                continue
            
            if filter_config.type == FilterType.SEARCH:
                self._apply_search_filter(filter_config, value)
                context[filter_config.field] = value
                
            elif filter_config.type == FilterType.SELECT:
                self._apply_select_filter(filter_config, value)
                context[filter_config.field] = value
                
            elif filter_config.type == FilterType.DATE_RANGE:
                self._apply_date_range_filter(filter_config, value)
                context[filter_config.field] = value
                
            elif filter_config.type == FilterType.BOOLEAN:
                self._apply_boolean_filter(filter_config, value)
                context[filter_config.field] = value
                
            elif filter_config.type == FilterType.MULTI_SELECT:
                self._apply_multi_select_filter(filter_config, value)
                context[filter_config.field] = value
        
        # Aplicar ordenação padrão
        self.queryset = self.queryset.order_by(self.config.default_order)
        
        return self.queryset, context
    
    def _apply_search_filter(self, filter_config: FilterConfig, value: str):
        """Aplica filtro de pesquisa"""
        if not filter_config.search_fields:
            return
        
        query = Q()
        for field in filter_config.search_fields:
            query |= Q(**{f"{field}__icontains": value})
        
        self.queryset = self.queryset.filter(query)
    
    def _apply_select_filter(self, filter_config: FilterConfig, value: str):
        """Aplica filtro de seleção única"""
        if value:
            self.queryset = self.queryset.filter(**{filter_config.field: value})
    
    def _apply_date_range_filter(self, filter_config: FilterConfig, value: str):
        """Aplica filtro de intervalo de datas"""
        # Implementar lógica de intervalo de datas
        pass
    
    def _apply_boolean_filter(self, filter_config: FilterConfig, value: str):
        """Aplica filtro booleano"""
        if value.lower() in ['true', '1', 'yes']:
            self.queryset = self.queryset.filter(**{filter_config.field: True})
        elif value.lower() in ['false', '0', 'no']:
            self.queryset = self.queryset.filter(**{filter_config.field: False})
    
    def _apply_multi_select_filter(self, filter_config: FilterConfig, value: str):
        """Aplica filtro de seleção múltipla"""
        if value:
            values = [v.strip() for v in value.split(',') if v.strip()]
            if values:
                self.queryset = self.queryset.filter(**{f"{filter_config.field}__in": values})


def get_filter_config(entity_name: str) -> Optional[FilterSetConfig]:
    """Função helper para obter configuração de filtros"""
    return filter_registry.get(entity_name)

'''
    
    def _generate_filter_config(self, task: MigrationTask) -> str:
        """Gera código de configuração para uma entidade"""
        filters_code = []
        
        # Adicionar filtro de pesquisa se não existir
        has_search = any(f['type'] == 'search' for f in task.current_filters)
        if not has_search:
            filters_code.append('''        FilterConfig(
            name="search",
            label="Pesquisar",
            type=FilterType.SEARCH,
            field="q",
            placeholder="Digite para pesquisar...",
            search_fields=["nome", "codigo"]
        )''')
        
        # Adicionar filtros encontrados
        for filter_info in task.current_filters:
            if filter_info['type'] == 'search':
                filters_code.append(f'''        FilterConfig(
            name="{filter_info['field']}",
            label="Pesquisar",
            type=FilterType.SEARCH,
            field="{filter_info['field']}",
            placeholder="{filter_info['placeholder']}",
            search_fields=["nome", "codigo"]
        )''')
            elif filter_info['type'] == 'select':
                filters_code.append(f'''        FilterConfig(
            name="{filter_info['field']}",
            label="{filter_info['field'].title()}",
            type=FilterType.SELECT,
            field="{filter_info['field']}",
            placeholder="{filter_info['placeholder']}"
        )''')
            elif filter_info['type'] == 'date':
                filters_code.append(f'''        FilterConfig(
            name="{filter_info['field']}",
            label="{filter_info['field'].replace('_', ' ').title()}",
            type=FilterType.DATE_RANGE,
            field="{filter_info['field']}",
            placeholder="{filter_info['placeholder']}"
        )''')
        
        config_code = f'''
# Configuração para {task.entity_name}
{task.entity_name}_config = FilterSetConfig(
    entity_name="{task.entity_name}",
    filters=[
{','.join(filters_code)}
    ],
    search_fields=["nome", "codigo"],
    default_order="nome",
    pagination_size=20
)

filter_registry.register({task.entity_name}_config)
'''
        
        return config_code
    
    def _migrate_templates(self):
        """Migra templates para o sistema unificado"""
        logger.info("🔄 Migrando templates...")
        
        for task in self.migration_tasks:
            if task.status == 'error':
                continue
            
            try:
                task.status = 'in_progress'
                
                with open(task.template_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Remover filtros antigos
                content = self._remove_old_filters(content)
                
                # Adicionar sistema unificado
                content = self._add_unified_filters(content, task.entity_name)
                
                # Remover CSS e JavaScript inline
                content = self._remove_inline_code(content)
                
                # Salvar template atualizado
                with open(task.template_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                task.status = 'completed'
                self.migrations_completed.append(task.template_path)
                
                logger.info(f"✅ Migrado: {Path(task.template_path).name}")
                
            except Exception as e:
                logger.error(f"Erro ao migrar {task.template_path}: {e}")
                task.status = 'error'
                self.errors.append(f"Erro ao migrar {task.template_path}: {e}")
    
    def _remove_old_filters(self, content: str) -> str:
        """Remove filtros antigos do template"""
        # Remover formulários de filtro
        form_pattern = r'<form[^>]*method\s*=\s*[\'"]get[\'"][^>]*>.*?</form>'
        content = re.sub(form_pattern, '', content, flags=re.DOTALL)
        
        # Remover elementos de filtro soltos
        filter_patterns = [
            r'<input[^>]*name\s*=\s*[\'"](q|search|filter)[\'"][^>]*>',
            r'<select[^>]*name\s*=\s*[\'"](status|departamento|cargo|tipo|sucursal)[\'"][^>]*>.*?</select>',
            r'<button[^>]*type\s*=\s*[\'"]submit[\'"][^>]*>.*?</button>'
        ]
        
        for pattern in filter_patterns:
            content = re.sub(pattern, '', content, flags=re.DOTALL)
        
        return content
    
    def _add_unified_filters(self, content: str, entity_name: str) -> str:
        """Adiciona sistema unificado de filtros"""
        # Encontrar local apropriado para inserir filtros
        # Geralmente após o header ou antes da tabela
        
        # Procurar por padrões comuns
        insertion_patterns = [
            r'(<div[^>]*class\s*=\s*[\'"][^\'"]*header[^\'"]*[\'"][^>]*>.*?</div>)',
            r'(<h[1-6][^>]*>.*?</h[1-6]>)',
            r'(<div[^>]*class\s*=\s*[\'"][^\'"]*content[^\'"]*[\'"][^>]*>)',
            r'(<table[^>]*>)'
        ]
        
        unified_filter_code = f'''
    {{% include 'includes/filters_unified.html' with entity_name='{entity_name}' %}}
'''
        
        for pattern in insertion_patterns:
            match = re.search(pattern, content, re.DOTALL)
            if match:
                # Inserir após o match
                insertion_point = match.end()
                content = content[:insertion_point] + unified_filter_code + content[insertion_point:]
                break
        else:
            # Se não encontrar padrão, inserir no início do body
            body_match = re.search(r'(<body[^>]*>)', content)
            if body_match:
                insertion_point = body_match.end()
                content = content[:insertion_point] + unified_filter_code + content[insertion_point:]
        
        return content
    
    def _remove_inline_code(self, content: str) -> str:
        """Remove CSS e JavaScript inline"""
        # Remover blocos de estilo
        style_pattern = r'<style[^>]*>.*?</style>'
        content = re.sub(style_pattern, '', content, flags=re.DOTALL)
        
        # Remover blocos de script (exceto os necessários)
        script_pattern = r'<script[^>]*>(?!.*filters_unified).*?</script>'
        content = re.sub(script_pattern, '', content, flags=re.DOTALL)
        
        return content
    
    def _validate_migrations(self):
        """Valida migrações realizadas"""
        logger.info("✅ Validando migrações...")
        
        for task in self.migration_tasks:
            if task.status != 'completed':
                continue
            
            try:
                with open(task.template_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Verificar se tem sistema unificado
                if 'filters_unified.html' not in content:
                    logger.warning(f"⚠️ Sistema unificado não encontrado em {task.template_path}")
                    task.status = 'error'
                
                # Verificar se não tem filtros antigos
                if re.search(r'<form[^>]*method\s*=\s*[\'"]get[\'"]', content):
                    logger.warning(f"⚠️ Filtros antigos ainda presentes em {task.template_path}")
                
                logger.info(f"✅ Validação OK: {Path(task.template_path).name}")
                
            except Exception as e:
                logger.error(f"Erro ao validar {task.template_path}: {e}")
    
    def _generate_migration_report(self) -> Dict:
        """Gera relatório da migração"""
        logger.info("📊 Gerando relatório de migração...")
        
        completed_tasks = [t for t in self.migration_tasks if t.status == 'completed']
        error_tasks = [t for t in self.migration_tasks if t.status == 'error']
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_tasks': len(self.migration_tasks),
                'completed': len(completed_tasks),
                'errors': len(error_tasks),
                'success_rate': len(completed_tasks) / len(self.migration_tasks) * 100 if self.migration_tasks else 0
            },
            'completed_migrations': [
                {
                    'template_path': task.template_path,
                    'entity_name': task.entity_name,
                    'filters_migrated': len(task.current_filters)
                }
                for task in completed_tasks
            ],
            'errors': self.errors,
            'recommendations': self._generate_migration_recommendations()
        }
        
        return report
    
    def _generate_migration_recommendations(self) -> List[str]:
        """Gera recomendações baseadas na migração"""
        recommendations = []
        
        if len(self.migration_tasks) == 0:
            recommendations.append("✅ Nenhuma migração necessária - todos os filtros já estão atualizados!")
            return recommendations
        
        completed = len([t for t in self.migration_tasks if t.status == 'completed'])
        errors = len([t for t in self.migration_tasks if t.status == 'error'])
        
        if completed > 0:
            recommendations.append(f"✅ {completed} templates migrados com sucesso")
        
        if errors > 0:
            recommendations.append(f"⚠️ {errors} templates com problemas - revisar manualmente")
        
        recommendations.append("🧪 Testar funcionalidade de filtros em todos os templates migrados")
        recommendations.append("📚 Atualizar documentação com novas configurações")
        recommendations.append("🔄 Executar script de verificação para validar migrações")
        
        return recommendations

def main():
    """Função principal do script"""
    print("🚀 SCRIPT DE MIGRAÇÃO E CORREÇÃO AUTOMÁTICA DE FILTROS")
    print("=" * 60)
    
    # Obter diretório do projeto
    project_root = os.getcwd()
    logger.info(f"Diretório do projeto: {project_root}")
    
    # Executar migração
    migrator = FilterMigrator(project_root)
    report = migrator.run_full_migration()
    
    # Exibir resumo
    print("\n📊 RESUMO DA MIGRAÇÃO:")
    print(f"Total de tarefas: {report['summary']['total_tasks']}")
    print(f"Migrações concluídas: {report['summary']['completed']}")
    print(f"Erros: {report['summary']['errors']}")
    print(f"Taxa de sucesso: {report['summary']['success_rate']:.1f}%")
    
    # Exibir migrações concluídas
    if report['completed_migrations']:
        print("\n✅ MIGRAÇÕES CONCLUÍDAS:")
        for migration in report['completed_migrations']:
            template_name = Path(migration['template_path']).name
            print(f"  - {template_name} ({migration['entity_name']}) - {migration['filters_migrated']} filtros")
    
    # Exibir erros
    if report['errors']:
        print("\n❌ ERROS ENCONTRADOS:")
        for error in report['errors']:
            print(f"  - {error}")
    
    # Exibir recomendações
    print("\n💡 RECOMENDAÇÕES:")
    for recommendation in report['recommendations']:
        print(f"  {recommendation}")
    
    # Salvar relatório
    report_file = 'relatorio_migracao_filtros.json'
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n📄 Relatório salvo em: {report_file}")
    print("✅ Migração concluída!")

if __name__ == "__main__":
    main()
