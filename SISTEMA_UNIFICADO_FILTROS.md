# Sistema Unificado de Filtros de Busca

## Visão Geral

O Sistema Unificado de Filtros de Busca é uma arquitetura profissional e escalável para gerenciar todos os filtros de pesquisa e listagem do sistema. Ele elimina duplicação de código, padroniza comportamentos e facilita manutenção futura.

## Arquitetura

### Componentes Principais

1. **`filters_config.py`** - Configuração centralizada de filtros
2. **`mixins.py`** - Mixin Django para lógica unificada
3. **`views_unified.py`** - Exemplos de views refatoradas
4. **`templates/includes/filters_unified.html`** - Template unificado

### Fluxo de Funcionamento

```
Request → FilteredListView → FilterProcessor → Queryset Filtrado → Template
    ↓              ↓              ↓                    ↓
Configuração → Mixin → Aplicação de Filtros → Renderização
```

## Configuração

### 1. Definir Configuração de Filtros

```python
# Em filters_config.py
produtos_config = FilterSetConfig(
    entity_name="produtos",
    model_class=Item,
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
```

### 2. Criar View Unificada

```python
# Em views_unified.py
class ProdutosListView(FilteredListView):
    entity_name = 'produtos'
    template_name = 'stock/produtos/main.html'
    
    def get_queryset(self):
        return Item.objects.filter(tipo='PRODUTO').select_related('categoria')
    
    def get_filter_choices(self):
        return {
            'categorias': CategoriaProduto.objects.filter(ativa=True),
            'status_choices': Item.STATUS_CHOICES,
        }
```

### 3. Usar Template Unificado

```html
<!-- Em templates/stock/produtos/main.html -->
{% include 'includes/filters_unified.html' with entity_name='produtos' %}
```

## Tipos de Filtros Suportados

### 1. Search (Pesquisa)
```python
FilterConfig(
    name="search",
    type=FilterType.SEARCH,
    field="q",
    search_fields=["nome", "codigo", "descricao"]
)
```

### 2. Select (Seleção Única)
```python
FilterConfig(
    name="categoria",
    type=FilterType.SELECT,
    field="categoria"
)
```

### 3. Date Range (Intervalo de Datas)
```python
FilterConfig(
    name="data_criacao",
    type=FilterType.DATE_RANGE,
    field="data_criacao"
)
```

### 4. Boolean (Sim/Não)
```python
FilterConfig(
    name="ativo",
    type=FilterType.BOOLEAN,
    field="ativo"
)
```

### 5. Multi Select (Seleção Múltipla)
```python
FilterConfig(
    name="tags",
    type=FilterType.MULTI_SELECT,
    field="tags",
    multiple=True
)
```

## Migração de Views Existentes

### Antes (Código Duplicado)
```python
@login_required
def stock_produtos(request):
    # 50+ linhas de código duplicado
    search_query = request.GET.get('q', '').strip()
    categoria_id = request.GET.get('categoria')
    status = request.GET.get('status')
    
    produtos = Item.objects.filter(tipo='PRODUTO')
    
    if search_query:
        produtos = produtos.filter(
            Q(nome__icontains=search_query) |
            Q(codigo__icontains=search_query) |
            Q(descricao__icontains=search_query)
        )
    
    if categoria_id:
        produtos = produtos.filter(categoria_id=categoria_id)
    
    if status:
        produtos = produtos.filter(status=status)
    
    # ... mais código duplicado
```

### Depois (Sistema Unificado)
```python
class ProdutosListView(FilteredListView):
    entity_name = 'produtos'
    template_name = 'stock/produtos/main.html'
    
    def get_queryset(self):
        return Item.objects.filter(tipo='PRODUTO')
    
    def get_filter_choices(self):
        return {
            'categorias': CategoriaProduto.objects.filter(ativa=True),
            'status_choices': Item.STATUS_CHOICES,
        }
```

## Migração de Templates

### Antes (HTML Duplicado)
```html
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
        <!-- ... mais HTML duplicado ... -->
    </form>
</div>
```

### Depois (Template Unificado)
```html
{% include 'includes/filters_unified.html' with entity_name='produtos' %}
```

## Funcionalidades Avançadas

### 1. Auto-submit Inteligente
- Pesquisa com debounce (500ms)
- Selects com submit automático
- Reset de paginação ao filtrar

### 2. Limpeza de Filtros
```javascript
clearFilters('produtos'); // Limpa todos os filtros
```

### 3. Toggle de Filtros
```javascript
toggleFilters('produtos'); // Mostra/oculta seção de filtros
```

### 4. Modo Compacto
```html
{% include 'includes/filters_unified.html' with entity_name='produtos' compact_mode=true %}
```

## Configurações Disponíveis

### Entidades Pré-configuradas
- `produtos` - Produtos do estoque
- `materiais` - Materiais do estoque
- `fornecedores` - Fornecedores
- `funcionarios` - Funcionários RH
- `receitas` - Receitas de produção
- `requisicoes` - Requisições

### Adicionar Nova Entidade
```python
# Em filters_config.py
nova_entidade_config = FilterSetConfig(
    entity_name="nova_entidade",
    model_class=MinhaModel,
    filters=[
        # ... configuração de filtros
    ],
    search_fields=["campo1", "campo2"],
    default_order="nome",
    pagination_size=20
)
filter_registry.register(nova_entidade_config)
```

## Benefícios

### 1. Redução de Código
- **Antes**: 50+ linhas por view
- **Depois**: 15 linhas por view
- **Redução**: ~70% menos código

### 2. Manutenção Centralizada
- Um local para gerenciar todos os filtros
- Mudanças aplicadas globalmente
- Consistência garantida

### 3. Escalabilidade
- Fácil adição de novos filtros
- Suporte a tipos customizados
- Configuração flexível

### 4. Performance
- Queries otimizadas
- Paginação eficiente
- Cache de configurações

## Testes

### Teste Manual
1. Acessar listagem com filtros
2. Testar pesquisa por texto
3. Testar filtros de seleção
4. Testar limpeza de filtros
5. Testar paginação

### Teste Automatizado
```python
# Exemplo de teste
def test_produtos_filters(self):
    view = ProdutosListView()
    view.entity_name = 'produtos'
    
    # Testar configuração
    config = view.get_filter_config()
    self.assertIsNotNone(config)
    self.assertEqual(config.entity_name, 'produtos')
    
    # Testar processamento de filtros
    request = self.factory.get('/produtos/?q=teste&categoria=1')
    queryset, context = view.process_filters(request)
    self.assertIn('q', context)
    self.assertIn('categoria', context)
```

## Troubleshooting

### Problema: Filtros não aparecem
**Solução**: Verificar se `entity_name` está registrado em `filter_registry`

### Problema: Choices não carregam
**Solução**: Implementar `get_filter_choices()` na view

### Problema: Template não renderiza
**Solução**: Verificar se `templates/includes/filters_unified.html` existe

### Problema: JavaScript não funciona
**Solução**: Verificar se jQuery está carregado antes do template

## Roadmap

### Versão 1.1
- [ ] Suporte a filtros de intervalo numérico
- [ ] Filtros de autocomplete
- [ ] Exportação de dados filtrados

### Versão 1.2
- [ ] Filtros salvos por usuário
- [ ] Filtros compartilhados
- [ ] Analytics de uso de filtros

### Versão 1.3
- [ ] Interface de configuração visual
- [ ] Filtros dinâmicos baseados em permissões
- [ ] Integração com sistema de cache

## Contribuição

Para contribuir com o sistema:

1. Seguir padrões de código existentes
2. Adicionar testes para novas funcionalidades
3. Documentar mudanças na API
4. Manter compatibilidade com versões anteriores

## Suporte

Para dúvidas ou problemas:
- Verificar documentação
- Consultar exemplos em `views_unified.py`
- Abrir issue no repositório
