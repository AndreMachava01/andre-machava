# 🎯 GUIA DE IMPLEMENTAÇÃO - PADRÃO DE DETALHES

## 📋 Como Usar o Template Base

### 1. Estrutura Básica
```html
{% extends "base_detail.html" %}
{% load static %}

{% block title %}Detalhes do [Entidade]{% endblock %}

{% block detail_cards %}
    <!-- Seus cards específicos aqui -->
{% endblock %}
```

### 2. Contexto Necessário na View
```python
def [entidade]_detail(request, id):
    objeto = [Modelo].objects.get(id=id)
    
    context = {
        'object': objeto,
        'object_name': objeto.nome,  # ou campo principal
        'entity_name': 'produto',     # nome da entidade
        'breadcrumb_url': 'stock:produtos',
        'breadcrumb_title': 'Produtos',
        'header_icon': 'box',
        'page_subtitle': 'Detalhes completos do produto',
        'back_url': 'stock:produtos',
        'edit_url': 'stock:produto_edit',
        # Dados específicos da entidade
        'movimentacoes': objeto.movimentacoes.all()[:10],
    }
    
    return render(request, '[modulo]/[entidade]/detail.html', context)
```

## 🎨 Padrões de Cards

### Card Básico
```html
<div class="card">
    <div class="card-header">
        <h5 class="mb-0">
            <i class="fas fa-[icone]"></i>[Título da Seção]
        </h5>
    </div>
    <div class="card-body">
        <div class="info-row">
            <span class="info-label">
                <i class="fas fa-[icone-campo]"></i>[Nome do Campo]:
            </span>
            <span class="info-value">{{ objeto.campo }}</span>
        </div>
    </div>
</div>
```

### Card de Largura Completa
```html
<div class="card card-full-width">
    <!-- Para tabelas e listas -->
</div>
```

## 🎯 Ícones Recomendados por Tipo

### Informações Gerais
- `fa-info-circle` - Informações básicas
- `fa-cog` - Configurações
- `fa-list` - Listas e relacionamentos
- `fa-history` - Histórico

### Campos Específicos
- `fa-hashtag` - Códigos
- `fa-tag` - Nomes
- `fa-calendar` - Datas
- `fa-dollar-sign` - Valores monetários
- `fa-boxes` - Quantidades
- `fa-user` - Pessoas
- `fa-building` - Empresas
- `fa-toggle-on` - Status
- `fa-percentage` - Percentuais
- `fa-barcode` - Códigos de barras

### Status e Estados
- `fa-check-circle` - Ativo/Concluído
- `fa-times-circle` - Inativo/Cancelado
- `fa-clock` - Pendente/Em andamento
- `fa-exclamation-triangle` - Alerta/Atenção

## 🎨 Cores para Valores

### Valores Monetários
```html
<!-- Preços de compra (vermelho) -->
<span class="info-value" style="font-weight: 700; color: #dc3545;">
    {{ objeto.preco_compra|floatformat:2 }} MT
</span>

<!-- Preços de venda (verde) -->
<span class="info-value" style="font-weight: 700; color: #28a745;">
    {{ objeto.preco_venda|floatformat:2 }} MT
</span>

<!-- Margens (azul) -->
<span class="info-value" style="font-weight: 700; color: #17a2b8;">
    {{ margem }}%
</span>
```

### Quantidades
```html
<span class="info-value" style="font-weight: 700; color: #495057;">
    {{ objeto.quantidade }} unidades
</span>
```

## 🏷️ Badges para Status

### Status Padrão
```html
<!-- Ativo -->
<span class="badge bg-success">{{ objeto.get_status_display }}</span>

<!-- Inativo -->
<span class="badge bg-secondary">{{ objeto.get_status_display }}</span>

<!-- Pendente -->
<span class="badge bg-warning">{{ objeto.get_status_display }}</span>

<!-- Erro/Cancelado -->
<span class="badge bg-danger">{{ objeto.get_status_display }}</span>

<!-- Informativo -->
<span class="badge bg-info">{{ objeto.get_status_display }}</span>
```

### Status Específicos
```html
<!-- Entrada/Saída -->
<span class="badge {% if mov.tipo == 'ENTRADA' %}bg-success{% else %}bg-danger{% endif %}">
    {{ mov.get_tipo_display }}
</span>

<!-- Aprovado/Rejeitado -->
<span class="badge {% if obj.aprovado %}bg-success{% else %}bg-danger{% endif %}">
    {% if obj.aprovado %}Aprovado{% else %}Rejeitado{% endif %}
</span>
```

## 📊 Tabelas de Histórico

### Estrutura Padrão
```html
<div class="card card-full-width">
    <div class="card-header">
        <h5 class="mb-0">
            <i class="fas fa-history"></i>Histórico
        </h5>
    </div>
    <div class="card-body">
        <div class="table-responsive">
            <table class="table table-hover">
                <thead>
                    <tr>
                        <th><i class="fas fa-calendar"></i> Data</th>
                        <th><i class="fas fa-user"></i> Usuário</th>
                        <th><i class="fas fa-cog"></i> Ação</th>
                        <th><i class="fas fa-comment"></i> Observações</th>
                    </tr>
                </thead>
                <tbody>
                    {% for item in historico %}
                    <tr>
                        <td><strong>{{ item.data|date:"d/m/Y H:i" }}</strong></td>
                        <td>{{ item.usuario.nome }}</td>
                        <td>{{ item.acao }}</td>
                        <td>{{ item.observacoes|default:"-" }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</div>
```

## 🚀 Checklist de Implementação

### ✅ Template
- [ ] Estende `base_detail.html`
- [ ] Define título específico
- [ ] Implementa `detail_cards`
- [ ] Usa ícones apropriados
- [ ] Organiza informações logicamente

### ✅ View
- [ ] Passa contexto necessário
- [ ] Define URLs de navegação
- [ ] Inclui dados relacionados
- [ ] Trata erros adequadamente

### ✅ URLs
- [ ] Define URL de detalhes
- [ ] Configura URLs de navegação
- [ ] Testa navegação entre páginas

### ✅ Testes
- [ ] Testa carregamento da página
- [ ] Verifica navegação
- [ ] Confirma dados exibidos
- [ ] Testa responsividade

## 📝 Exemplos de Implementação

### Produto
- **Ícone**: `fa-box`
- **Cards**: Básicas, Comerciais, Estoque, Adicionais
- **Histórico**: Movimentações

### Funcionário
- **Ícone**: `fa-user`
- **Cards**: Pessoais, Profissionais, Remuneração, Bancários
- **Histórico**: Folhas salariais

### Cliente
- **Ícone**: `fa-users`
- **Cards**: Contato, Endereço, Comercial, Histórico
- **Histórico**: Pedidos

### Fornecedor
- **Ícone**: `fa-truck`
- **Cards**: Contato, Endereço, Comercial, Produtos
- **Histórico**: Fornecimentos

## 🎯 Benefícios do Padrão

1. **Consistência Visual**: Todas as páginas seguem o mesmo design
2. **Manutenibilidade**: Mudanças no CSS afetam todas as páginas
3. **Produtividade**: Desenvolvimento mais rápido
4. **UX Uniforme**: Usuários sabem o que esperar
5. **Responsividade**: Funciona em todos os dispositivos
6. **Acessibilidade**: Estrutura semântica adequada

## 🔧 Customizações Específicas

Se precisar de customizações específicas para uma entidade:

```html
{% block extra_style %}
{{ block.super }}
<style>
    /* Estilos específicos da entidade */
    .custom-card {
        /* Customizações */
    }
</style>
{% endblock %}
```

Este padrão garante que todas as páginas de detalhes do sistema tenham a mesma qualidade visual e funcional! 🎨✨
