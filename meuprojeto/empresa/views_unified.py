"""
SISTEMA UNIFICADO DE FILTROS DE BUSCA
Sistema oficial e único - substitui django-filters e sistemas antigos
Exemplos de views refatoradas e guia de migração
"""

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
import logging

from .mixins import FilteredListView
from .filters_config import filter_registry, FilterSetConfig, FilterConfig, FilterType
from .models_stock import Item, CategoriaProduto
from .models_rh import Funcionario, Cargo, Departamento

logger = logging.getLogger(__name__)


# =============================================================================
# VIEWS REFATORADAS COM SISTEMA UNIFICADO
# =============================================================================

class ProdutosListView(FilteredListView):
    """
    View de listagem de produtos usando sistema unificado de filtros
    
    Antes: 50+ linhas de código duplicado
    Depois: 15 linhas + configuração centralizada
    """
    entity_name = 'produtos'
    template_name = 'stock/produtos/main.html'
    
    def get_queryset(self):
        """Queryset base para produtos"""
        return Item.objects.filter(tipo='PRODUTO').select_related('categoria')
    
    def get_filter_choices(self):
        """Choices dinâmicos para filtros de produtos"""
        return {
            'categorias': CategoriaProduto.objects.filter(ativa=True).filter(
                Q(tipo='PRODUTO') | Q(tipo='AMBOS') | Q(tipo='TODOS')
            ),
            'status_choices': Item.STATUS_CHOICES,
            'tipo_choices': Item.PRODUTO_TIPO_CHOICES,
        }
    
    def apply_custom_filters(self, queryset, request):
        """Filtros customizados específicos para produtos"""
        # Adicionar informações de stock para cada produto
        from .models_stock import StockItem
        for produto in queryset:
            stocks = StockItem.objects.filter(item=produto)
            produto.quantidade_atual = sum(float(stock.quantidade_atual) for stock in stocks)
        
        return queryset
    
    def get_extra_context(self):
        """Contexto adicional específico para produtos"""
        return {
            'produtos_estoque_baixo': self._count_low_stock_products(),
        }
    
    def _count_low_stock_products(self):
        """Conta produtos com estoque baixo"""
        try:
            produtos = self.get_queryset()
            count = 0
            for produto in produtos:
                if hasattr(produto, 'quantidade_atual') and produto.quantidade_atual <= produto.estoque_minimo:
                    count += 1
            return count
        except:
            return 0


class MateriaisListView(FilteredListView):
    """
    View de listagem de materiais usando sistema unificado
    """
    entity_name = 'materiais'
    template_name = 'stock/materiais/main.html'
    
    def get_queryset(self):
        """Queryset base para materiais"""
        return Item.objects.filter(tipo='MATERIAL').select_related('categoria')
    
    def get_filter_choices(self):
        """Choices dinâmicos para filtros de materiais"""
        return {
            'categorias': CategoriaProduto.objects.filter(ativa=True).filter(
                Q(tipo='MATERIAL') | Q(tipo='AMBOS') | Q(tipo='TODOS')
            ),
            'tipos': Item.MATERIAL_TIPO_CHOICES,
            'status_choices': Item.STATUS_CHOICES,
        }
    
    def apply_custom_filters(self, queryset, request):
        """Filtros customizados específicos para materiais"""
        # Adicionar informações de stock para cada material
        from .models_stock import StockItem
        for material in queryset:
            stocks = StockItem.objects.filter(item=material)
            material.quantidade_atual = sum(float(stock.quantidade_atual) for stock in stocks)
        
        return queryset


class FuncionariosListView(FilteredListView):
    """
    View de listagem de funcionários usando sistema unificado
    """
    entity_name = 'funcionarios'
    template_name = 'rh/funcionarios/main.html'
    
    def get_queryset(self):
        """Queryset base para funcionários"""
        return Funcionario.objects.select_related('cargo', 'departamento').all()
    
    def get_filter_choices(self):
        """Choices dinâmicos para filtros de funcionários"""
        return {
            'cargos': Cargo.objects.filter(ativo=True),
            'departamentos': Departamento.objects.filter(ativo=True),
            'status_choices': Funcionario.STATUS_CHOICES,
        }


# =============================================================================
# REGISTRO DE CONFIGURAÇÕES ADICIONAIS
# =============================================================================

def register_additional_filter_configs():
    """
    Registra configurações adicionais de filtros específicas do sistema
    """
    
    # Configuração para Receitas
    receitas_config = FilterSetConfig(
        entity_name="receitas",
        model_class=None,
        filters=[
            FilterConfig(
                name="search",
                label="Pesquisar",
                type=FilterType.SEARCH,
                field="q",
                placeholder="Nome, código ou descrição...",
                search_fields=["nome", "codigo", "descricao", "item__nome"]
            ),
            FilterConfig(
                name="produto",
                label="Produto",
                type=FilterType.SELECT,
                field="produto",
                placeholder="Todos os produtos"
            ),
            FilterConfig(
                name="status",
                label="Status",
                type=FilterType.SELECT,
                field="status",
                placeholder="Todos os status"
            )
        ],
        search_fields=["nome", "codigo", "descricao", "item__nome"],
        default_order="item__nome",
        pagination_size=20
    )
    filter_registry.register(receitas_config)
    
    # Configuração para Requisições
    requisicoes_config = FilterSetConfig(
        entity_name="requisicoes",
        model_class=None,
        filters=[
            FilterConfig(
                name="search",
                label="Pesquisar",
                type=FilterType.SEARCH,
                field="q",
                placeholder="Código, solicitante ou observações...",
                search_fields=["codigo", "solicitante__nome", "observacoes"]
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
            ),
            FilterConfig(
                name="data_criacao",
                label="Data de Criação",
                type=FilterType.DATE_RANGE,
                field="data_criacao",
                placeholder="Período"
            )
        ],
        search_fields=["codigo", "solicitante__nome", "observacoes"],
        default_order="-data_criacao",
        pagination_size=20
    )
    filter_registry.register(requisicoes_config)


# =============================================================================
# FUNÇÕES HELPER PARA MIGRAÇÃO GRADUAL
# =============================================================================

def create_unified_view_from_legacy(entity_name: str, legacy_view_func):
    """
    Cria view unificada a partir de view legada existente
    
    Args:
        entity_name: Nome da entidade
        legacy_view_func: Função da view legada
    
    Returns:
        View unificada
    """
    
    class UnifiedView(FilteredListView):
        entity_name = entity_name
        template_name = f"{entity_name}/main.html"
        
        def get_queryset(self):
            # Extrair lógica de queryset da view legada
            # (implementar conforme necessário)
            pass
        
        def get_filter_choices(self):
            # Extrair choices da view legada
            # (implementar conforme necessário)
            pass
    
    return UnifiedView


# =============================================================================
# MIDDLEWARE PARA INICIALIZAÇÃO AUTOMÁTICA
# =============================================================================

class FilterConfigMiddleware:
    """
    Middleware para inicializar configurações de filtros automaticamente
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        # Registrar configurações adicionais
        register_additional_filter_configs()
    
    def __call__(self, request):
        response = self.get_response(request)
        return response


# =============================================================================
# COMANDO DE MIGRAÇÃO PARA VIEWS EXISTENTES
# =============================================================================

def migrate_legacy_views():
    """
    Função helper para migrar views legadas para o sistema unificado
    
    Uso:
        # No shell do Django
        from meuprojeto.empresa.views_unified import migrate_legacy_views
        migrate_legacy_views()
    """
    
    # Mapear views legadas para configurações
    legacy_mappings = {
        'stock_produtos': 'produtos',
        'stock_materiais': 'materiais',
        'rh_funcionarios': 'funcionarios',
        'stock_fornecedores': 'fornecedores',
    }
    
    print("Iniciando migração de views legadas...")
    
    for legacy_view, entity_name in legacy_mappings.items():
        config = filter_registry.get_config(entity_name)
        if config:
            print(f"✓ Configuração encontrada para {entity_name}")
        else:
            print(f"✗ Configuração não encontrada para {entity_name}")
    
    print("Migração concluída!")


# =============================================================================
# EXEMPLO DE USO EM TEMPLATE
# =============================================================================

"""
No template, substituir:

ANTES (código duplicado):
    <div class="filters-section">
        <h3 class="filters-title">
            <i class="fas fa-filter"></i>
            Filtros de Busca
        </h3>
        <form method="get" class="filters-row">
            <div class="filter-group">
                <label class="filter-label">Pesquisar</label>
                <div class="table-search">
                    <i class="fas fa-search table-search-icon"></i>
                    <input type="text" name="q" value="{{ search_query|default:'' }}" 
                           class="form-control" placeholder="Nome, código ou descrição...">
                </div>
            </div>
            <!-- ... mais código duplicado ... -->
        </form>
    </div>

DEPOIS (sistema unificado):
    {% include 'includes/filters_unified.html' with entity_name='produtos' %}
"""
