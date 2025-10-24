# 🔍 Sistema de Verificação e Correção de Filtros

Este conjunto de scripts fornece uma solução completa para verificar, corrigir e migrar todos os filtros de pesquisa do sistema Conception.

## 📋 Scripts Disponíveis

### 1. `gerenciar_filtros.py` - Script Principal (RECOMENDADO)
**Script orquestrador principal com interface interativa**

```bash
python gerenciar_filtros.py
```

**Funcionalidades:**
- ✅ Interface de menu interativo
- ✅ Execução completa do workflow
- ✅ Verificação, correção, migração e testes
- ✅ Relatórios consolidados
- ✅ Ajuda integrada

### 2. `verificar_corrigir_filtros.py` - Verificação e Correção
**Script para verificar problemas e aplicar correções automáticas**

```bash
python verificar_corrigir_filtros.py
```

**Funcionalidades:**
- 🔍 Verifica estrutura de arquivos
- 📊 Analisa templates com filtros
- ⚙️ Valida configurações no `filters_config.py`
- 🔄 Verifica consistência entre templates e configurações
- 🔧 Aplica correções automáticas
- 📄 Gera relatório detalhado

### 3. `migrar_corrigir_filtros.py` - Migração Completa
**Script para migrar filtros antigos para o sistema unificado**

```bash
python migrar_corrigir_filtros.py
```

**Funcionalidades:**
- 🚀 Identifica templates com filtros manuais
- 📝 Cria configurações automáticas
- 🔄 Migra templates para sistema unificado
- 🎨 Remove CSS e JavaScript inline
- ✅ Valida migrações realizadas

### 4. `testar_filtros.py` - Testes e Validação
**Script para testar e validar o funcionamento dos filtros**

```bash
python testar_filtros.py
```

**Funcionalidades:**
- 🧪 Testa estrutura de arquivos
- ⚙️ Valida configurações de filtros
- 📄 Testa templates migrados
- 🔄 Verifica consistência
- 🎨 Testa CSS e JavaScript

## 🚀 Como Usar

### Uso Recomendado (Iniciantes)
```bash
python gerenciar_filtros.py
```
Escolha a opção **1** para execução completa.

### Uso Avançado (Desenvolvedores)
```bash
# 1. Verificar problemas
python verificar_corrigir_filtros.py

# 2. Migrar filtros antigos
python migrar_corrigir_filtros.py

# 3. Testar funcionamento
python testar_filtros.py
```

## 📊 Relatórios Gerados

### Relatórios JSON
- `relatorio_filtros.json` - Relatório de verificação
- `relatorio_migracao_filtros.json` - Relatório de migração
- `relatorio_testes_filtros.json` - Relatório de testes
- `relatorio_workflow_filtros.json` - Relatório completo do workflow

### Logs de Execução
- `filtros_verificacao.log` - Log de verificação
- `filtros_migracao.log` - Log de migração
- `filtros_testes.log` - Log de testes
- `filtros_principal.log` - Log do script principal

## 🔧 Problemas que Podem Ser Corrigidos Automaticamente

### ✅ Correções Automáticas
- **CSRF Token faltante** - Adiciona `{% csrf_token %}` em formulários
- **CSS inline** - Remove CSS inline dos templates de filtros
- **JavaScript inline** - Remove JavaScript inline dos templates
- **Configurações faltantes** - Cria configurações básicas no `filters_config.py`
- **Filtros antigos** - Migra para sistema unificado

### ⚠️ Problemas que Requerem Intervenção Manual
- **Configurações complexas** - Filtros com lógica específica
- **Templates com problemas de sintaxe** - Erros de Django template
- **Dependências faltantes** - Arquivos ou módulos não encontrados
- **Conflitos de configuração** - Configurações duplicadas ou conflitantes

## 📋 Estrutura do Sistema de Filtros

### Arquivos Principais
```
meuprojeto/empresa/
├── filters_config.py          # Configurações de filtros
├── mixins.py                  # Mixin para views
└── views_unified.py          # Exemplos de views

templates/
├── includes/
│   └── filters_unified.html  # Template unificado de filtros
└── [outros templates]        # Templates que usam filtros
```

### Configuração de Filtros
```python
# Exemplo de configuração no filters_config.py
funcionarios_config = FilterSetConfig(
    entity_name="funcionarios",
    filters=[
        FilterConfig(
            name="search",
            label="Pesquisar",
            type=FilterType.SEARCH,
            field="q",
            placeholder="Nome, código ou email...",
            search_fields=["nome", "codigo", "email"]
        ),
        FilterConfig(
            name="departamento",
            label="Departamento",
            type=FilterType.SELECT,
            field="departamento",
            placeholder="Todos os departamentos"
        )
    ],
    search_fields=["nome", "codigo", "email"],
    default_order="nome",
    pagination_size=20
)

filter_registry.register(funcionarios_config)
```

### Uso em Templates
```html
<!-- Incluir sistema unificado de filtros -->
{% include 'includes/filters_unified.html' with entity_name='funcionarios' %}
```

### Uso em Views
```python
from meuprojeto.empresa.mixins import UnifiedFilterMixin

class FuncionariosListView(UnifiedFilterMixin, ListView):
    entity_name = 'funcionarios'
    template_name = 'rh/funcionarios/main.html'
    
    def get_queryset(self):
        return Funcionario.objects.all()
```

## 🎯 Entidades Suportadas

### RH (Recursos Humanos)
- `funcionarios` - Funcionários
- `cargos` - Cargos
- `departamentos` - Departamentos
- `salarios` - Salários
- `promocoes` - Promoções
- `presencas` - Presenças
- `treinamentos` - Treinamentos
- `avaliacoes` - Avaliações
- `feriados` - Feriados
- `transferencias` - Transferências

### Stock (Estoque)
- `produtos` - Produtos
- `materiais` - Materiais
- `fornecedores` - Fornecedores
- `categorias` - Categorias
- `inventario` - Inventário
- `requisicoes` - Requisições
- `checklists` - Checklists
- `viaturas` - Viaturas
- `transportadoras` - Transportadoras

### Logística
- `operacoes_logisticas` - Operações Logísticas
- `transferencias_logisticas` - Transferências Logísticas
- `ajustes_inventario` - Ajustes de Inventário

## 🔍 Tipos de Filtros Suportados

### 1. Filtro de Pesquisa (SEARCH)
```python
FilterConfig(
    name="search",
    type=FilterType.SEARCH,
    field="q",
    search_fields=["nome", "codigo", "descricao"]
)
```

### 2. Filtro de Seleção (SELECT)
```python
FilterConfig(
    name="status",
    type=FilterType.SELECT,
    field="status",
    placeholder="Todos os status"
)
```

### 3. Filtro de Data (DATE_RANGE)
```python
FilterConfig(
    name="data_inicio",
    type=FilterType.DATE_RANGE,
    field="data_inicio",
    placeholder="Data de início"
)
```

### 4. Filtro Booleano (BOOLEAN)
```python
FilterConfig(
    name="ativo",
    type=FilterType.BOOLEAN,
    field="ativo",
    placeholder="Status"
)
```

### 5. Filtro de Seleção Múltipla (MULTI_SELECT)
```python
FilterConfig(
    name="categorias",
    type=FilterType.MULTI_SELECT,
    field="categorias",
    placeholder="Selecionar categorias"
)
```

## 🚨 Solução de Problemas

### Problema: Script não executa
**Solução:**
```bash
# Verificar Python
python --version

# Instalar dependências
pip install -r requirements.txt

# Verificar permissões
chmod +x *.py
```

### Problema: Arquivos não encontrados
**Solução:**
```bash
# Verificar estrutura
ls -la meuprojeto/empresa/
ls -la templates/includes/

# Executar do diretório correto
cd /caminho/para/projeto
python gerenciar_filtros.py
```

### Problema: Erro de sintaxe nos templates
**Solução:**
1. Verificar sintaxe Django nos templates
2. Validar tags e filtros
3. Verificar variáveis de contexto
4. Executar migração novamente

### Problema: Filtros não funcionam
**Solução:**
1. Verificar configuração no `filters_config.py`
2. Validar variáveis de contexto na view
3. Testar template manualmente
4. Verificar JavaScript no navegador

## 📚 Recursos Adicionais

### Documentação do Sistema
- `SISTEMA_UNIFICADO_FILTROS.md` - Documentação técnica
- `SISTEMA_FILTROS_MIGRACAO_COMPLETA.md` - Guia de migração
- `DIAGNOSTICO_FILTROS.md` - Diagnóstico de problemas

### Exemplos de Uso
- `templates/examples/filters_usage_example.html` - Exemplo de uso
- `meuprojeto/empresa/views_unified.py` - Exemplos de views

### Configurações de Desenvolvimento
- `pyproject.toml` - Configuração do projeto
- `requirements.txt` - Dependências Python
- `mypy.ini` - Configuração de tipos

## 🤝 Contribuição

Para contribuir com melhorias nos scripts:

1. **Fork** o repositório
2. **Crie** uma branch para sua feature
3. **Implemente** as melhorias
4. **Teste** com os scripts existentes
5. **Documente** as mudanças
6. **Submeta** um pull request

## 📞 Suporte

Em caso de problemas:

1. **Consulte** os logs gerados
2. **Revise** os relatórios JSON
3. **Execute** os testes de validação
4. **Verifique** a documentação
5. **Abra** uma issue no repositório

---

**Sistema Conception - Filtros Unificados**  
*Versão 2025 - Desenvolvido para máxima eficiência e manutenibilidade*
