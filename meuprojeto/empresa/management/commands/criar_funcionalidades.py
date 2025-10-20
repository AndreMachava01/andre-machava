from django.core.management.base import BaseCommand
from meuprojeto.empresa.models import Funcionalidade

FUNCIONALIDADES_PADRAO = [
    # Módulo de Vendas
    {
        'nome': 'Consultar Vendas',
        'codigo': 'VENDAS_CONSULTA',
        'modulo': 'Vendas',
        'descricao': 'Permite consultar relatórios de vendas'
    },
    {
        'nome': 'Registrar Venda',
        'codigo': 'VENDAS_REGISTRO',
        'modulo': 'Vendas',
        'descricao': 'Permite registrar novas vendas'
    },
    
    # Módulo de Estoque
    {
        'nome': 'Consultar Estoque',
        'codigo': 'ESTOQUE_CONSULTA',
        'modulo': 'Estoque',
        'descricao': 'Permite consultar níveis de estoque'
    },
    {
        'nome': 'Movimentar Estoque',
        'codigo': 'ESTOQUE_MOVIMENTO',
        'modulo': 'Estoque',
        'descricao': 'Permite registrar entradas e saídas de estoque'
    },
    
    # Módulo Financeiro
    {
        'nome': 'Consultar Financeiro',
        'codigo': 'FINANCEIRO_CONSULTA',
        'modulo': 'Financeiro',
        'descricao': 'Permite consultar informações financeiras'
    },
    {
        'nome': 'Registrar Movimento',
        'codigo': 'FINANCEIRO_MOVIMENTO',
        'modulo': 'Financeiro',
        'descricao': 'Permite registrar movimentações financeiras'
    },
    
    # Módulo de Relatórios
    {
        'nome': 'Relatórios Básicos',
        'codigo': 'RELATORIOS_BASICOS',
        'modulo': 'Relatórios',
        'descricao': 'Permite gerar relatórios básicos'
    },
    {
        'nome': 'Relatórios Avançados',
        'codigo': 'RELATORIOS_AVANCADOS',
        'modulo': 'Relatórios',
        'descricao': 'Permite gerar relatórios avançados e personalizados'
    }
]

class Command(BaseCommand):
    help = 'Cria as funcionalidades padrão do sistema'

    def handle(self, *args, **kwargs):
        for func in FUNCIONALIDADES_PADRAO:
            Funcionalidade.objects.get_or_create(
                codigo=func['codigo'],
                defaults={
                    'nome': func['nome'],
                    'modulo': func['modulo'],
                    'descricao': func['descricao']
                }
            )
        
        self.stdout.write(self.style.SUCCESS('Funcionalidades padrão criadas com sucesso!'))