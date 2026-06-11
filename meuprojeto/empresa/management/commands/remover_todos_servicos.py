from django.core.management.base import BaseCommand
from django.db import transaction
from meuprojeto.empresa.models_stock import (
    Item,
    OrdemServico,
    ServicoOrcamentoServico,
    ItemOrcamentoServico,
    TransporteOrcamentoServico,
    ClienteServico
)
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Remove todos os serviços registrados do sistema'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirmar',
            action='store_true',
            help='Confirma a remoção sem pedir confirmação interativa',
        )
        parser.add_argument(
            '--apenas-servicos',
            action='store_true',
            help='Remove apenas os serviços (Item), mantendo orçamentos e clientes',
        )

    def handle(self, *args, **options):
        confirmar = options.get('confirmar', False)
        apenas_servicos = options.get('apenas_servicos', False)
        
        # Contar registros
        servicos_count = Item.objects.filter(tipo='PRODUTO', produto_tipo='SERVICO').count()
        orcamentos_count = OrdemServico.objects.count()
        servicos_orcamento_count = ServicoOrcamentoServico.objects.count()
        itens_orcamento_count = ItemOrcamentoServico.objects.count()
        transportes_count = TransporteOrcamentoServico.objects.count()
        clientes_count = ClienteServico.objects.count()
        
        self.stdout.write(self.style.WARNING('\n' + '='*60))
        self.stdout.write(self.style.WARNING('ATENÇÃO: OPERAÇÃO IRREVERSÍVEL'))
        self.stdout.write(self.style.WARNING('='*60))
        self.stdout.write(f'\nRegistros encontrados:')
        self.stdout.write(f'  - Serviços (Item): {servicos_count}')
        
        if not apenas_servicos:
            self.stdout.write(f'  - Orçamentos de Serviços: {orcamentos_count}')
            self.stdout.write(f'  - Serviços em Orçamentos: {servicos_orcamento_count}')
            self.stdout.write(f'  - Itens em Orçamentos: {itens_orcamento_count}')
            self.stdout.write(f'  - Transportes em Orçamentos: {transportes_count}')
            self.stdout.write(f'  - Clientes de Serviços: {clientes_count}')
        
        total = servicos_count
        if not apenas_servicos:
            total += orcamentos_count + servicos_orcamento_count + itens_orcamento_count + transportes_count + clientes_count
        
        self.stdout.write(self.style.WARNING(f'\nTotal de registros a serem removidos: {total}'))
        self.stdout.write(self.style.WARNING('='*60 + '\n'))
        
        if not confirmar:
            resposta = input('Tem certeza que deseja remover TODOS os serviços? (digite "SIM" para confirmar): ')
            if resposta != 'SIM':
                self.stdout.write(self.style.ERROR('Operação cancelada.'))
                return
        
        try:
            with transaction.atomic():
                # Remover em ordem (respeitando dependências)
                if not apenas_servicos:
                    # 1. Remover transportes
                    transportes_removidos = TransporteOrcamentoServico.objects.all().delete()[0]
                    self.stdout.write(self.style.SUCCESS(f'[OK] Removidos {transportes_removidos} transportes'))
                    
                    # 2. Remover itens de orçamentos
                    itens_removidos = ItemOrcamentoServico.objects.all().delete()[0]
                    self.stdout.write(self.style.SUCCESS(f'[OK] Removidos {itens_removidos} itens de orcamentos'))
                    
                    # 3. Remover serviços de orçamentos
                    servicos_orcamento_removidos = ServicoOrcamentoServico.objects.all().delete()[0]
                    self.stdout.write(self.style.SUCCESS(f'[OK] Removidos {servicos_orcamento_removidos} servicos de orcamentos'))
                    
                    # 4. Remover orçamentos
                    orcamentos_removidos = OrdemServico.objects.all().delete()[0]
                    self.stdout.write(self.style.SUCCESS(f'[OK] Removidos {orcamentos_removidos} orcamentos'))
                    
                    # 5. Remover clientes (opcional - comentado para não remover dados importantes)
                    # clientes_removidos = ClienteServico.objects.all().delete()[0]
                    # self.stdout.write(self.style.SUCCESS(f'[OK] Removidos {clientes_removidos} clientes'))
                
                # 6. Remover serviços (Item)
                servicos_removidos = Item.objects.filter(tipo='PRODUTO', produto_tipo='SERVICO').delete()[0]
                self.stdout.write(self.style.SUCCESS(f'[OK] Removidos {servicos_removidos} servicos'))
                
                self.stdout.write(self.style.SUCCESS('\n' + '='*60))
                self.stdout.write(self.style.SUCCESS('[OK] Todos os servicos foram removidos com sucesso!'))
                self.stdout.write(self.style.SUCCESS('='*60))
                
        except Exception as e:
            logger.error(f"Erro ao remover serviços: {e}", exc_info=True)
            self.stdout.write(self.style.ERROR(f'\nErro ao remover serviços: {str(e)}'))
            raise

