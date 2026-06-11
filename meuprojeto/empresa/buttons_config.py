# CONFIGURAÇÃO UNIFICADA DE BOTÕES
# Arquivo de configuração para definir botões padrão do sistema

# MÓDULOS PRINCIPAIS
MODULES = [
    {
        'id': 'rh-module',
        'name': 'Recursos Humanos',
        'description': 'Gestão de funcionários, salários e RH',
        'icon': 'fas fa-users',
        'url': '/rh/',
        'stats': [
            {'label': 'Funcionários', 'value': '{{ funcionarios_count|default:0 }}'},
            {'label': 'Departamentos', 'value': '{{ departamentos_count|default:0 }}'},
            {'label': 'Cargos', 'value': '{{ cargos_count|default:0 }}'}
        ]
    },
    {
        'id': 'stock-module',
        'name': 'Stock',
        'description': 'Gestão de inventário e produtos',
        'icon': 'fas fa-boxes',
        'url': '/stock/',
        'stats': [
            {'label': 'Produtos', 'value': '{{ produtos_count|default:0 }}'},
            {'label': 'Materiais', 'value': '{{ materiais_count|default:0 }}'},
            {'label': 'Fornecedores', 'value': '{{ fornecedores_count|default:0 }}'}
        ]
    },
    {
        'id': 'logistica-module',
        'name': 'Logística',
        'description': 'Gestão de transporte e distribuição',
        'icon': 'fas fa-truck',
        'url': '/stock/logistica/',
        'stats': [
            {'label': 'Viaturas', 'value': '{{ viaturas_count|default:0 }}'},
            {'label': 'Operações', 'value': '{{ operacoes_count|default:0 }}'},
            {'label': 'Transportadoras', 'value': '{{ transportadoras_count|default:0 }}'}
        ]
    }
]

# SUBMÓDULOS RH
RH_SUBMODULES = [
    {'id': 'funcionarios', 'name': 'Funcionários', 'icon': 'fas fa-user', 'url': '/rh/funcionarios/', 'count': '{{ funcionarios_count|default:0 }}'},
    {'id': 'departamentos', 'name': 'Departamentos', 'icon': 'fas fa-building', 'url': '/rh/departamentos/', 'count': '{{ departamentos_count|default:0 }}'},
    {'id': 'cargos', 'name': 'Cargos', 'icon': 'fas fa-briefcase', 'url': '/rh/cargos/', 'count': '{{ cargos_count|default:0 }}'},
    {'id': 'salarios', 'name': 'Salários', 'icon': 'fas fa-money-bill', 'url': '/rh/salarios/', 'count': '{{ salarios_count|default:0 }}'},
    {'id': 'presencas', 'name': 'Presenças', 'icon': 'fas fa-calendar-check', 'url': '/rh/presencas/', 'count': '{{ presencas_count|default:0 }}'},
    {'id': 'treinamentos', 'name': 'Treinamentos', 'icon': 'fas fa-graduation-cap', 'url': '/rh/treinamentos/', 'count': '{{ treinamentos_count|default:0 }}'},
    {'id': 'avaliacoes', 'name': 'Avaliações', 'icon': 'fas fa-star', 'url': '/rh/avaliacoes/', 'count': '{{ avaliacoes_count|default:0 }}'},
    {'id': 'feriados', 'name': 'Feriados', 'icon': 'fas fa-calendar-times', 'url': '/rh/feriados/', 'count': '{{ feriados_count|default:0 }}'},
    {'id': 'transferencias', 'name': 'Transferências', 'icon': 'fas fa-exchange-alt', 'url': '/rh/transferencias/', 'count': '{{ transferencias_count|default:0 }}'},
    {'id': 'folha_salarial', 'name': 'Folha Salarial', 'icon': 'fas fa-file-invoice', 'url': '/rh/folha_salarial/', 'count': '{{ folha_salarial_count|default:0 }}'},
    {'id': 'promocoes', 'name': 'Promoções', 'icon': 'fas fa-arrow-up', 'url': '/rh/promocoes/', 'count': '{{ promocoes_count|default:0 }}'},
    {'id': 'relatorios', 'name': 'Relatórios', 'icon': 'fas fa-chart-bar', 'url': '/rh/relatorios/', 'count': '{{ relatorios_count|default:0 }}'}
]

# SUBMÓDULOS STOCK
STOCK_SUBMODULES = [
    {'id': 'produtos', 'name': 'Produtos', 'icon': 'fas fa-box', 'url': '/stock/produtos/', 'count': '{{ produtos_count|default:0 }}'},
    {'id': 'materiais', 'name': 'Materiais', 'icon': 'fas fa-cube', 'url': '/stock/materiais/', 'count': '{{ materiais_count|default:0 }}'},
    {'id': 'fornecedores', 'name': 'Fornecedores', 'icon': 'fas fa-truck-loading', 'url': '/stock/fornecedores/', 'count': '{{ fornecedores_count|default:0 }}'},
    {'id': 'categorias', 'name': 'Categorias', 'icon': 'fas fa-tags', 'url': '/stock/categorias/', 'count': '{{ categorias_count|default:0 }}'},
    {'id': 'inventario', 'name': 'Inventário', 'icon': 'fas fa-clipboard-list', 'url': '/stock/inventario/', 'count': '{{ inventario_count|default:0 }}'},
    {'id': 'requisicoes', 'name': 'Requisições', 'icon': 'fas fa-file-alt', 'url': '/stock/requisicoes/', 'count': '{{ requisicoes_count|default:0 }}'},
    {'id': 'transferencias', 'name': 'Transferências', 'icon': 'fas fa-exchange-alt', 'url': '/stock/transferencias/', 'count': '{{ transferencias_count|default:0 }}'},
    {'id': 'relatorios', 'name': 'Relatórios', 'icon': 'fas fa-chart-bar', 'url': '/stock/relatorios/', 'count': '{{ relatorios_count|default:0 }}'}
]

# SUBMÓDULOS LOGÍSTICA
LOGISTICA_SUBMODULES = [
    {'id': 'viaturas', 'name': 'Viaturas', 'icon': 'fas fa-car', 'url': '/stock/logistica/viaturas/', 'count': '{{ viaturas_count|default:0 }}'},
    {'id': 'transportadoras', 'name': 'Transportadoras', 'icon': 'fas fa-shipping-fast', 'url': '/stock/logistica/transportadoras/', 'count': '{{ transportadoras_count|default:0 }}'},
    {'id': 'operacoes', 'name': 'Operações', 'icon': 'fas fa-cogs', 'url': '/stock/logistica/operacoes/', 'count': '{{ operacoes_count|default:0 }}'},
    {'id': 'rastreamento', 'name': 'Rastreamento', 'icon': 'fas fa-map-marker-alt', 'url': '/stock/logistica/rastreamento/', 'count': '{{ rastreamento_count|default:0 }}'},
    {'id': 'checklist', 'name': 'Checklist', 'icon': 'fas fa-check-square', 'url': '/stock/logistica/checklist/', 'count': '{{ checklist_count|default:0 }}'},
    {'id': 'pod', 'name': 'POD', 'icon': 'fas fa-file-signature', 'url': '/stock/logistica/pod/', 'count': '{{ pod_count|default:0 }}'},
    {'id': 'guias', 'name': 'Guias', 'icon': 'fas fa-file-export', 'url': '/stock/logistica/guias/', 'count': '{{ guias_count|default:0 }}'},
    {'id': 'cotacao', 'name': 'Cotação', 'icon': 'fas fa-dollar-sign', 'url': '/stock/logistica/cotacao/', 'count': '{{ cotacao_count|default:0 }}'}
]

# BOTÕES DE NAVEGAÇÃO PADRÃO
NAVIGATION_BUTTONS = [
    {'type': 'navigation', 'text': 'Voltar', 'icon': 'fas fa-arrow-left', 'onclick': 'history.back()'},
    {'type': 'navigation', 'text': 'Início', 'icon': 'fas fa-home', 'url': '/'},
    {'type': 'navigation', 'text': 'Próximo', 'icon': 'fas fa-arrow-right', 'onclick': 'history.forward()'}
]

# BOTÕES DE AÇÃO PADRÃO
ACTION_BUTTONS = [
    {'type': 'action', 'action': 'view', 'text': 'Ver Detalhes', 'icon': 'fas fa-eye', 'url': '#'},
    {'type': 'action', 'action': 'edit', 'text': 'Editar', 'icon': 'fas fa-edit', 'url': '#'},
    {'type': 'action', 'action': 'delete', 'text': 'Apagar', 'icon': 'fas fa-trash', 'onclick': 'confirmDelete()'}
]

# BOTÕES DE CONFIRMAÇÃO PADRÃO
CONFIRMATION_BUTTONS = [
    {'type': 'confirmation', 'action': 'save', 'text': 'Guardar', 'icon': 'fas fa-save'},
    {'type': 'confirmation', 'action': 'cancel', 'text': 'Cancelar', 'icon': 'fas fa-times', 'onclick': 'history.back()'}
]

# CONFIGURAÇÕES DE LAYOUT
LAYOUT_CONFIG = {
    'modules': 'cards',
    'submodules': 'grid',
    'navigation': 'both',
    'actions': 'inline',
    'confirmations': 'centered'
}
