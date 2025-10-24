# SISTEMA UNIFICADO DE BOTÕES

## 📋 Visão Geral

O Sistema Unificado de Botões é uma solução completa para padronizar e gerenciar todos os tipos de botões no sistema, garantindo consistência visual, funcionalidade e acessibilidade.

## 🎯 Tipos de Botões

### 1. **Botões de Módulos Principais**
- **Função**: Acesso aos módulos principais (RH, Stock, Logística)
- **Características**: Tamanho grande, cores distintivas, efeitos visuais
- **Uso**: Páginas principais e dashboards

### 2. **Botões de Submódulos**
- **Função**: Acesso aos submódulos (Funcionários, Produtos, Materiais, etc.)
- **Características**: Tamanho médio, cores específicas por módulo
- **Uso**: Páginas de módulos específicos

### 3. **Botões de Navegação**
- **Função**: Navegação entre páginas (Voltar, Próximo, Anterior)
- **Características**: Tamanho pequeno, cores neutras
- **Uso**: Barras de navegação e rodapés

### 4. **Botões de Ação**
- **Função**: Ações específicas (Ver Detalhes, Editar, Apagar)
- **Características**: Tamanho pequeno, cores por ação
- **Uso**: Listas, formulários e detalhes

### 5. **Botões de Confirmação**
- **Função**: Confirmação de ações (Guardar, Cancelar, Confirmar)
- **Características**: Tamanho médio, cores de confirmação
- **Uso**: Formulários e modais

## 🚀 Como Usar

### Template Tags

```django
{% load button_tags %}

<!-- Botão individual -->
{% button_unified type='module' text='RH' icon='fas fa-users' url='/rh/' %}

<!-- Botões de módulos -->
{% module_buttons %}

<!-- Botões de submódulos -->
{% submodule_buttons %}

<!-- Botões de navegação -->
{% navigation_buttons %}

<!-- Botões de ação -->
{% action_buttons %}

<!-- Botões de confirmação -->
{% confirmation_buttons %}
```

### Inclusão Direta

```django
<!-- Botão individual -->
{% include 'components/button_unified.html' with type='action' action='edit' text='Editar' icon='fas fa-edit' %}

<!-- Grupo de botões -->
{% include 'components/button_group_unified.html' with buttons=button_list layout='horizontal' %}
```

## 🎨 Classes CSS

### Classes por Tipo
- `.btn-module` - Módulos principais
- `.btn-submodule` - Submódulos
- `.btn-navigation` - Navegação
- `.btn-action` - Ações
- `.btn-confirmation` - Confirmação

### Classes por Ação
- `.btn-view` - Ver detalhes
- `.btn-edit` - Editar
- `.btn-delete` - Apagar
- `.btn-save` - Guardar
- `.btn-cancel` - Cancelar

### Classes por Tamanho
- `.btn-xs` - Extra pequeno
- `.btn-sm` - Pequeno
- `.btn-md` - Médio (padrão)
- `.btn-lg` - Grande
- `.btn-xl` - Extra grande

### Classes por Estado
- `.btn-loading` - Carregando
- `.btn-disabled` - Desabilitado
- `.btn-icon` - Com ícone

## 📁 Estrutura de Arquivos

```
meuprojeto/empresa/
├── static/css/
│   └── buttons-unified.css          # CSS principal dos botões
├── templatetags/
│   └── button_tags.py               # Template tags personalizados
├── buttons_config.py                # Configuração dos botões
templates/
├── components/
│   ├── button_unified.html          # Template base de botão
│   ├── button_group_unified.html    # Template de grupo de botões
│   ├── module_buttons.html          # Template de módulos
│   ├── submodule_buttons.html       # Template de submódulos
│   ├── navigation_buttons.html      # Template de navegação
│   ├── action_buttons.html          # Template de ações
│   └── confirmation_buttons.html    # Template de confirmação
└── examples/
    └── buttons_unified_example.html # Exemplo de uso
```

## ⚙️ Configuração

### Arquivo de Configuração (`buttons_config.py`)

```python
# Módulos principais
MODULES = [
    {
        'id': 'rh-module',
        'name': 'Recursos Humanos',
        'description': 'Gestão de funcionários, salários e RH',
        'icon': 'fas fa-users',
        'url': '/rh/',
        'stats': [...]
    }
]

# Submódulos
RH_SUBMODULES = [
    {'id': 'funcionarios', 'name': 'Funcionários', 'icon': 'fas fa-user', 'url': '/rh/funcionarios/'}
]
```

## 🔧 Migração

### Script de Migração

```bash
python migrar_botoes_unificado.py
```

O script migra automaticamente:
- Botões de módulos principais
- Botões de submódulos
- Botões de ação
- Botões de confirmação
- Botões de navegação

## 📱 Responsividade

O sistema é totalmente responsivo:
- **Desktop**: Layout completo com todos os recursos
- **Tablet**: Adaptação de tamanhos e espaçamentos
- **Mobile**: Layout vertical e botões em tela cheia

## ♿ Acessibilidade

Todos os botões incluem:
- `aria-label` para screen readers
- `title` para tooltips
- `tabindex` para navegação por teclado
- Contraste adequado de cores
- Estados visuais claros

## 🎨 Personalização

### Variáveis CSS

```css
:root {
  --btn-primary-color: #007bff;
  --btn-module-color: #2c3e50;
  --btn-submodule-color: #3498db;
  --btn-navigation-color: #95a5a6;
  --btn-action-color: #e74c3c;
  --btn-confirmation-color: #27ae60;
}
```

### Layouts Disponíveis

- **Grid**: Layout em grade responsiva
- **Cards**: Layout em cartões
- **Sidebar**: Layout em barra lateral
- **Inline**: Layout em linha
- **Toolbar**: Layout em barra de ferramentas
- **Dropdown**: Layout em menu dropdown

## 🔍 Exemplos de Uso

### Página Principal
```django
{% module_buttons layout='cards' %}
```

### Lista de Funcionários
```django
{% submodule_buttons layout='grid' %}
{% action_buttons layout='inline' %}
```

### Formulário
```django
{% confirmation_buttons layout='centered' %}
```

### Navegação
```django
{% navigation_buttons position='both' %}
```

## 📊 Benefícios

1. **Consistência**: Todos os botões seguem o mesmo padrão visual
2. **Manutenibilidade**: Fácil de atualizar e modificar
3. **Acessibilidade**: Atende padrões de acessibilidade
4. **Responsividade**: Funciona em todos os dispositivos
5. **Performance**: CSS otimizado e carregamento eficiente
6. **Flexibilidade**: Fácil de personalizar e estender

## 🚀 Próximos Passos

1. Execute o script de migração
2. Teste os botões em diferentes páginas
3. Personalize as cores conforme necessário
4. Adicione novos tipos de botão se necessário
5. Documente casos de uso específicos

## 📞 Suporte

Para dúvidas ou problemas:
1. Verifique o arquivo de log da migração
2. Consulte os exemplos em `templates/examples/`
3. Teste em ambiente de desenvolvimento primeiro
4. Faça backup antes de aplicar em produção
