"""
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
    choices: Optional[List[tuple]] = None
    placeholder: Optional[str] = None
    help_text: Optional[str] = None
    required: bool = False
    multiple: bool = False
    search_fields: Optional[List[str]] = None


@dataclass
class FilterSetConfig:
    """Configuração completa de um conjunto de filtros"""
    entity_name: str
    model_class: Any
    base_queryset: Optional[Any] = None
    filters: List[FilterConfig] = None
    default_order: str = "nome"
    search_fields: List[str] = None
    pagination_size: int = 20
    custom_filters: Optional[Dict[str, Any]] = None


class UnifiedFilterRegistry:
    """Registro centralizado de todas as configurações de filtros"""
    
    def __init__(self):
        self._configs: Dict[str, FilterSetConfig] = {}
        self._register_default_configs()
    
    def register(self, config: FilterSetConfig):
        """Registra uma nova configuração de filtros"""
        self._configs[config.entity_name] = config
    
    def get_config(self, entity_name: str) -> Optional[FilterSetConfig]:
        """Obtém configuração de filtros por nome da entidade"""
        return self._configs.get(entity_name)
    
    def get_all_configs(self) -> Dict[str, FilterSetConfig]:
        """Obtém todas as configurações registradas"""
        return self._configs.copy()
    
    def _register_default_configs(self):
        """Registra configurações padrão do sistema"""
        
        # Configuração para Produtos
        produtos_config = FilterSetConfig(
            entity_name="produtos",
            model_class=None,  # Será definido dinamicamente
            filters=[
                FilterConfig(
                    name="search",
                    label="Pesquisar",
                    type=FilterType.SEARCH,
                    field="q",
                    placeholder="Nome, código ou descrição...",
                    search_fields=["nome", "codigo", "codigo_barras", "descricao"]
                ),
                FilterConfig(
                    name="categoria",
                    label="Categoria",
                    type=FilterType.SELECT,
                    field="categoria",
                    choices=None,  # Será preenchido dinamicamente
                    placeholder="Todas as categorias"
                ),
                FilterConfig(
                    name="status",
                    label="Status",
                    type=FilterType.SELECT,
                    field="status",
                    choices=None,  # Será preenchido dinamicamente
                    placeholder="Todos os status"
                ),
                FilterConfig(
                    name="tipo",
                    label="Tipo",
                    type=FilterType.SELECT,
                    field="tipo",
                    choices=None,  # Será preenchido dinamicamente
                    placeholder="Todos os tipos"
                )
            ],
            search_fields=["nome", "codigo", "codigo_barras", "descricao"],
            default_order="nome",
            pagination_size=20
        )
        self.register(produtos_config)
        
        # Configuração para Materiais
        materiais_config = FilterSetConfig(
            entity_name="materiais",
            model_class=None,
            filters=[
                FilterConfig(
                    name="search",
                    label="Pesquisar",
                    type=FilterType.SEARCH,
                    field="q",
                    placeholder="Nome, código ou descrição...",
                    search_fields=["nome", "codigo", "codigo_barras", "descricao"]
                ),
                FilterConfig(
                    name="categoria",
                    label="Categoria",
                    type=FilterType.SELECT,
                    field="categoria",
                    placeholder="Todas as categorias"
                ),
                FilterConfig(
                    name="tipo",
                    label="Tipo",
                    type=FilterType.SELECT,
                    field="tipo",
                    placeholder="Todos os tipos"
                ),
                FilterConfig(
                    name="status",
                    label="Status",
                    type=FilterType.SELECT,
                    field="status",
                    placeholder="Todos os status"
                )
            ],
            search_fields=["nome", "codigo", "codigo_barras", "descricao"],
            default_order="nome",
            pagination_size=20
        )
        self.register(materiais_config)
        
        # Configuração para Fornecedores
        fornecedores_config = FilterSetConfig(
            entity_name="fornecedores",
            model_class=None,
            filters=[
                FilterConfig(
                    name="search",
                    label="Pesquisar",
                    type=FilterType.SEARCH,
                    field="q",
                    placeholder="Nome, CNPJ ou email...",
                    search_fields=["nome", "cnpj", "email", "telefone"]
                ),
                FilterConfig(
                    name="status",
                    label="Status",
                    type=FilterType.SELECT,
                    field="status",
                    placeholder="Todos os status"
                ),
                FilterConfig(
                    name="cidade",
                    label="Cidade",
                    type=FilterType.SELECT,
                    field="cidade",
                    placeholder="Todas as cidades"
                )
            ],
            search_fields=["nome", "cnpj", "email", "telefone"],
            default_order="nome",
            pagination_size=20
        )
        self.register(fornecedores_config)
        
        # Configuração para Funcionários
        funcionarios_config = FilterSetConfig(
            entity_name="funcionarios",
            model_class=None,
            filters=[
                FilterConfig(
                    name="search",
                    label="Pesquisar",
                    type=FilterType.SEARCH,
                    field="q",
                    placeholder="Nome, CPF ou matrícula...",
                    search_fields=["nome", "cpf", "matricula", "email"]
                ),
                FilterConfig(
                    name="cargo",
                    label="Cargo",
                    type=FilterType.SELECT,
                    field="cargo",
                    placeholder="Todos os cargos"
                ),
                FilterConfig(
                    name="status",
                    label="Status",
                    type=FilterType.SELECT,
                    field="status",
                    placeholder="Todos os status"
                ),
                FilterConfig(
                    name="departamento",
                    label="Departamento",
                    type=FilterType.SELECT,
                    field="departamento",
                    placeholder="Todos os departamentos"
                )
            ],
            search_fields=["nome", "cpf", "matricula", "email"],
            default_order="nome",
            pagination_size=20
        )
        self.register(funcionarios_config)
        
        # Configuração para Operações Logísticas
        operacoes_logisticas_config = FilterSetConfig(
            entity_name="operacoes_logisticas",
            model_class=None,
            filters=[
                FilterConfig(
                    name="search",
                    label="Pesquisar",
                    type=FilterType.SEARCH,
                    field="search",
                    placeholder="Código, fornecedor...",
                    search_fields=["codigo_operacao", "origem_operacao", "destino_operacao"]
                ),
                FilterConfig(
                    name="tipo_operacao",
                    label="Tipo",
                    type=FilterType.SELECT,
                    field="tipo_operacao",
                    placeholder="Todos os tipos"
                ),
                FilterConfig(
                    name="status",
                    label="Status",
                    type=FilterType.SELECT,
                    field="status",
                    placeholder="Todos os status"
                ),
                FilterConfig(
                    name="prioridade",
                    label="Prioridade",
                    type=FilterType.SELECT,
                    field="prioridade",
                    placeholder="Todas as prioridades"
                )
            ],
            search_fields=["codigo_operacao", "origem_operacao", "destino_operacao"],
            default_order="data_notificacao",
            pagination_size=20
        )
        self.register(operacoes_logisticas_config)
        
        # Configuração para Transferências Logísticas
        transferencias_logisticas_config = FilterSetConfig(
            entity_name="transferencias_logisticas",
            model_class=None,
            filters=[
                FilterConfig(
                    name="search",
                    label="Pesquisar",
                    type=FilterType.SEARCH,
                    field="search",
                    placeholder="Código, sucursal...",
                    search_fields=["transferencia__codigo", "origem_operacao", "destino_operacao"]
                ),
                FilterConfig(
                    name="status",
                    label="Status",
                    type=FilterType.SELECT,
                    field="status",
                    placeholder="Todos os status"
                ),
                FilterConfig(
                    name="prioridade",
                    label="Prioridade",
                    type=FilterType.SELECT,
                    field="prioridade",
                    placeholder="Todas as prioridades"
                )
            ],
            search_fields=["transferencia__codigo", "origem_operacao", "destino_operacao"],
            default_order="data_notificacao",
            pagination_size=20
        )
        self.register(transferencias_logisticas_config)
        
        # Configuração para Ajustes de Inventário
        ajustes_inventario_config = FilterSetConfig(
            entity_name="ajustes_inventario",
            model_class=None,
            filters=[
                FilterConfig(
                    name="search",
                    label="Pesquisar",
                    type=FilterType.SEARCH,
                    field="search",
                    placeholder="Código, item, motivo...",
                    search_fields=["codigo", "item__nome", "motivo"]
                ),
                FilterConfig(
                    name="tipo",
                    label="Tipo",
                    type=FilterType.SELECT,
                    field="tipo",
                    placeholder="Todos os tipos"
                ),
                FilterConfig(
                    name="status",
                    label="Status",
                    type=FilterType.SELECT,
                    field="status",
                    placeholder="Todos os status"
                ),
                FilterConfig(
                    name="data_inicio",
                    label="Data Início",
                    type=FilterType.DATE_RANGE,
                    field="data_inicio",
                    placeholder="Data inicial"
                ),
                FilterConfig(
                    name="data_fim",
                    label="Data Fim",
                    type=FilterType.DATE_RANGE,
                    field="data_fim",
                    placeholder="Data final"
                )
            ],
            search_fields=["codigo", "item__nome", "motivo"],
            default_order="data_criacao",
            pagination_size=20
        )
        self.register(ajustes_inventario_config)
        
        # Configuração para Requisições
        requisicoes_config = FilterSetConfig(
            entity_name="requisicoes",
            model_class=None,
            filters=[
                FilterConfig(
                    name="search",
                    label="Pesquisar",
                    type=FilterType.SEARCH,
                    field="search",
                    placeholder="Código, solicitante...",
                    search_fields=["codigo", "sucursal_origem__nome", "sucursal_destino__nome"]
                ),
                FilterConfig(
                    name="status",
                    label="Status",
                    type=FilterType.SELECT,
                    field="status",
                    placeholder="Todos os status"
                ),
                FilterConfig(
                    name="sucursal",
                    label="Sucursal",
                    type=FilterType.SELECT,
                    field="sucursal",
                    placeholder="Todas as sucursais"
                ),
                FilterConfig(
                    name="data_inicio",
                    label="Data Início",
                    type=FilterType.DATE_RANGE,
                    field="data_inicio",
                    placeholder="Data inicial"
                ),
                FilterConfig(
                    name="data_fim",
                    label="Data Fim",
                    type=FilterType.DATE_RANGE,
                    field="data_fim",
                    placeholder="Data final"
                )
            ],
            search_fields=["codigo", "sucursal_origem__nome", "sucursal_destino__nome"],
            default_order="data_criacao",
            pagination_size=20
        )
        self.register(requisicoes_config)
        
        # Configuração para Checklists de Viaturas
        checklists_config = FilterSetConfig(
            entity_name="checklists",
            model_class=None,
            filters=[
                FilterConfig(
                    name="search",
                    label="Pesquisar",
                    type=FilterType.SEARCH,
                    field="search",
                    placeholder="Código, viatura...",
                    search_fields=["codigo", "viatura__nome", "motorista__nome"]
                ),
                FilterConfig(
                    name="veiculo",
                    label="Veículo",
                    type=FilterType.SELECT,
                    field="veiculo",
                    placeholder="Todos os veículos"
                ),
                FilterConfig(
                    name="motorista",
                    label="Motorista",
                    type=FilterType.SELECT,
                    field="motorista",
                    placeholder="Todos os motoristas"
                ),
                FilterConfig(
                    name="status",
                    label="Status",
                    type=FilterType.SELECT,
                    field="status",
                    placeholder="Todos os status"
                ),
                FilterConfig(
                    name="data_inicio",
                    label="Data Início",
                    type=FilterType.DATE_RANGE,
                    field="data_inicio",
                    placeholder="Data inicial"
                ),
                FilterConfig(
                    name="data_fim",
                    label="Data Fim",
                    type=FilterType.DATE_RANGE,
                    field="data_fim",
                    placeholder="Data final"
                )
            ],
            search_fields=["codigo", "viatura__nome", "motorista__nome"],
            default_order="data_criacao",
            pagination_size=20
        )
        self.register(checklists_config)
        


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
        """Aplica filtro de busca"""
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
    return filter_registry.get_config(entity_name)


def create_filter_processor(entity_name: str, queryset) -> Optional[FilterProcessor]:
    """Função helper para criar processador de filtros"""
    config = get_filter_config(entity_name)
    if config:
        return FilterProcessor(config, queryset)
    return None
