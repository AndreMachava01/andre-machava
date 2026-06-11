"""
Comando para corrigir status de RequisicaoProducao que foi marcada como ATENDIDA
sem ter passado pela confirmação de recebimento na produção
"""
from django.core.management.base import BaseCommand
from meuprojeto.empresa.models_stock import RequisicaoProducao, MovimentoItem


class Command(BaseCommand):
    help = 'Corrige status de RequisicaoProducao que foi marcada como ATENDIDA sem confirmação na produção'

    def add_arguments(self, parser):
        parser.add_argument(
            '--codigo',
            type=str,
            help='Código específico da requisição para corrigir',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Apenas simular, não fazer alterações',
        )

    def handle(self, *args, **options):
        codigo = options.get('codigo')
        dry_run = options.get('dry_run', False)
        
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('CORRECAO DE STATUS DE REQUISICOES DE PRODUCAO'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        
        if codigo:
            requisicoes = RequisicaoProducao.objects.filter(codigo=codigo, status='ATENDIDA')
        else:
            requisicoes = RequisicaoProducao.objects.filter(status='ATENDIDA')
        
        corrigidas = 0
        mantidas = 0
        
        for requisicao in requisicoes:
            self.stdout.write(f'\nVerificando: {requisicao.codigo}')
            
            # Verificar se há movimentos de consumo criados
            # Se houver movimentos com observações contendo "Consumo para produção" e o código da requisição,
            # significa que o recebimento foi confirmado na produção
            movimentos_consumo = MovimentoItem.objects.filter(
                observacoes__icontains=f'Consumo para produção'
            ).filter(
                observacoes__icontains=requisicao.codigo
            )
            
            if movimentos_consumo.exists():
                self.stdout.write(self.style.WARNING(f'  [MANTIDA] Requisicao {requisicao.codigo} tem movimentos de consumo - recebimento foi confirmado'))
                self.stdout.write(f'            Movimentos encontrados: {movimentos_consumo.count()}')
                mantidas += 1
            else:
                # Não há movimentos de consumo - o status ATENDIDA foi marcado incorretamente
                # Deve ser revertido para APROVADA para permitir confirmação na produção
                self.stdout.write(self.style.ERROR(f'  [CORRIGIR] Requisicao {requisicao.codigo} sem movimentos de consumo'))
                self.stdout.write(f'            Status atual: {requisicao.status}')
                self.stdout.write(f'            Data atendimento: {requisicao.data_atendimento if hasattr(requisicao, "data_atendimento") and requisicao.data_atendimento else "N/A"}')
                
                if not dry_run:
                    requisicao.status = 'APROVADA'
                    if hasattr(requisicao, 'data_atendimento'):
                        requisicao.data_atendimento = None
                    requisicao.save()
                    self.stdout.write(self.style.SUCCESS(f'            [OK] Status alterado para APROVADA'))
                else:
                    self.stdout.write(self.style.WARNING(f'            [DRY-RUN] Seria alterado para APROVADA'))
                
                corrigidas += 1
        
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.SUCCESS('RESUMO'))
        self.stdout.write('=' * 80)
        self.stdout.write(f'Requisicoes verificadas: {requisicoes.count()}')
        self.stdout.write(f'Requisicoes mantidas (tem movimentos): {mantidas}')
        self.stdout.write(f'Requisicoes corrigidas: {corrigidas}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n[DRY-RUN] Nenhuma alteracao foi feita. Execute sem --dry-run para aplicar as correcoes.'))
        else:
            self.stdout.write(self.style.SUCCESS('\n[OK] Correcoes aplicadas!'))

