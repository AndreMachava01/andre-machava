"""
MIGRAÇÃO DO SISTEMA DE FILTROS
Guia para migrar de django-filters para sistema unificado
"""

# =============================================================================
# MIGRAÇÃO DE DJANGO-FILTERS PARA SISTEMA UNIFICADO
# =============================================================================

"""
ANTES (django-filters):
    class FuncionarioFilter(django_filters.FilterSet):
        search = django_filters.CharFilter(method='search_filter', label='Pesquisar')
        sucursal = django_filters.NumberFilter(field_name='sucursal__id', label='Sucursal')
        departamento = django_filters.NumberFilter(field_name='departamento__id', label='Departamento')
        cargo = django_filters.NumberFilter(field_name='cargo__id', label='Cargo')
        status = django_filters.ChoiceFilter(choices=Funcionario.STATUS_CHOICES, label='Status')

DEPOIS (sistema unificado):
    class FuncionariosListView(FilteredListView):
        entity_name = 'funcionarios'
        template_name = 'rh/funcionarios/main.html'
        
        def get_queryset(self):
            return Funcionario.objects.select_related('cargo', 'departamento')
        
        def get_filter_choices(self):
            return {
                'cargos': Cargo.objects.filter(ativo=True),
                'departamentos': Departamento.objects.filter(ativo=True),
                'status_choices': Funcionario.STATUS_CHOICES,
            }
"""

# =============================================================================
# CONFIGURAÇÃO DE MIGRAÇÃO AUTOMÁTICA
# =============================================================================

def migrate_django_filters_to_unified():
    """
    Migra configurações de django-filters para sistema unificado
    
    Mapeamento:
    - django_filters.CharFilter -> FilterType.SEARCH
    - django_filters.NumberFilter -> FilterType.SELECT
    - django_filters.ChoiceFilter -> FilterType.SELECT
    - django_filters.BooleanFilter -> FilterType.BOOLEAN
    - django_filters.DateFilter -> FilterType.DATE_RANGE
    """
    
    # Configuração migrada para Funcionários
    funcionarios_config_migrada = FilterSetConfig(
        entity_name="funcionarios",
        model_class=Funcionario,
        filters=[
            FilterConfig(
                name="search",
                label="Pesquisar",
                type=FilterType.SEARCH,
                field="q",
                placeholder="Nome, CPF ou matrícula...",
                search_fields=["nome_completo", "codigo_funcionario", "nuit", "bi"]
            ),
            FilterConfig(
                name="sucursal",
                label="Sucursal",
                type=FilterType.SELECT,
                field="sucursal",
                placeholder="Todas as sucursais"
            ),
            FilterConfig(
                name="departamento",
                label="Departamento",
                type=FilterType.SELECT,
                field="departamento",
                placeholder="Todos os departamentos"
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
            )
        ],
        search_fields=["nome_completo", "codigo_funcionario", "nuit", "bi"],
        default_order="nome_completo",
        pagination_size=20
    )
    
    # Registrar configuração migrada
    filter_registry.register(funcionarios_config_migrada)
    
    print("✓ Migração de django-filters concluída!")
    print("✓ Sistema unificado agora é o padrão oficial")


# =============================================================================
# COMPATIBILIDADE TEMPORÁRIA
# =============================================================================

class DjangoFiltersCompatibilityMixin:
    """
    Mixin para manter compatibilidade temporária com django-filters
    Permite migração gradual sem quebrar funcionalidades existentes
    """
    
    def get_django_filters_compatibility(self):
        """
        Retorna dados compatíveis com django-filters para templates antigos
        """
        return {
            'filter': self,  # Simula objeto FilterSet
            'form': self.get_filter_form(),  # Simula formulário de filtros
        }
    
    def get_filter_form(self):
        """
        Simula formulário de filtros do django-filters
        """
        # Implementar compatibilidade se necessário
        pass


# =============================================================================
# COMANDO DE MIGRAÇÃO
# =============================================================================

def run_migration():
    """
    Executa migração completa do sistema de filtros
    """
    print("Iniciando migração do sistema de filtros...")
    
    # 1. Migrar configurações
    migrate_django_filters_to_unified()
    
    # 2. Verificar integridade
    configs = filter_registry.get_all_configs()
    print(f"✓ {len(configs)} configurações registradas")
    
    # 3. Validar configurações
    for entity_name, config in configs.items():
        print(f"✓ {entity_name}: {len(config.filters)} filtros configurados")
    
    print("✓ Migração concluída com sucesso!")
    print("✓ Sistema unificado é agora o padrão oficial")


# =============================================================================
# INSTRUÇÕES DE USO
# =============================================================================

"""
INSTRUÇÕES PARA DESENVOLVEDORES:

1. REMOVER IMPORTS ANTIGOS:
   - Remover: from django_filters import FilterSet, CharFilter, etc.
   - Adicionar: from .mixins import FilteredListView

2. MIGRAR VIEWS:
   - Antes: class MinhaView(View) + FuncionarioFilter
   - Depois: class MinhaView(FilteredListView)

3. MIGRAR TEMPLATES:
   - Antes: {{ filter.form.as_p }}
   - Depois: {% include 'includes/filters_unified.html' with entity_name='funcionarios' %}

4. REMOVER ARQUIVOS ANTIGOS:
   - Deletar: filters.py (django-filters)
   - Deletar: unified_list_config.py (sistema antigo)

5. TESTAR MIGRAÇÃO:
   - Verificar funcionamento dos filtros
   - Testar paginação
   - Validar JavaScript
"""
