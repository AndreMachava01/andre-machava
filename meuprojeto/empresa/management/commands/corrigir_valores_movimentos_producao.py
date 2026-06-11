"""
Comando para corrigir valores incorretos nos movimentos de produção.
O problema era que o código estava dividindo o custo por produto pelo rendimento novamente,
quando calcular_custo_por_produto() já retorna o custo por unidade.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from decimal import Decimal
from meuprojeto.empresa.models_stock import MovimentoItem, TipoMovimentoStock, OrdemProducao
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Corrige valores incorretos nos movimentos de produção'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Executa sem fazer alterações (apenas mostra o que seria feito)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('MODO DRY-RUN: Nenhuma alteração será feita'))
        
        # Buscar tipo de movimento de produção
        tipo_entrada_producao = TipoMovimentoStock.objects.filter(
            codigo='ENT_PRODUCAO'
        ).first()
        
        if not tipo_entrada_producao:
            self.stdout.write(self.style.ERROR('Tipo de movimento ENT_PRODUCAO não encontrado'))
            return
        
        # Buscar movimentos de produção
        movimentos = MovimentoItem.objects.filter(
            tipo_movimento=tipo_entrada_producao
        ).select_related('item', 'tipo_movimento')
        
        self.stdout.write(f'Encontrados {movimentos.count()} movimentos de produção')
        
        movimentos_corrigidos = 0
        movimentos_com_erro = 0
        
        for movimento in movimentos:
            # Extrair código da ordem do código do movimento
            # Formato: MOVOP2025110002PROD ou MOVOP2025110002PROD01
            codigo_mov = movimento.codigo
            if not codigo_mov.startswith('MOV') or 'PROD' not in codigo_mov:
                continue
            
            # Extrair código da ordem (ex: OP2025110002)
            # Remover prefixo MOV e sufixo PROD
            codigo_limpo = codigo_mov.replace('MOV', '')
            if 'PROD' in codigo_limpo:
                codigo_ordem = codigo_limpo.split('PROD')[0]
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f'Movimento {movimento.codigo}: Formato de código inválido'
                    )
                )
                continue
            
            # Tentar encontrar a ordem
            try:
                ordem = OrdemProducao.objects.get(codigo=codigo_ordem)
            except OrdemProducao.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(
                        f'Movimento {movimento.codigo}: Ordem {codigo_ordem} não encontrada'
                    )
                )
                continue
            except OrdemProducao.MultipleObjectsReturned:
                self.stdout.write(
                    self.style.WARNING(
                        f'Movimento {movimento.codigo}: Múltiplas ordens encontradas com código {codigo_ordem}'
                    )
                )
                continue
            
            if not ordem.receita:
                self.stdout.write(
                    self.style.WARNING(
                        f'Movimento {movimento.codigo}: Ordem {ordem.codigo} não tem receita'
                    )
                )
                continue
            
            try:
                # Calcular valor correto
                custo_correto = ordem.receita.calcular_custo_por_produto()
                valor_correto = custo_correto * Decimal(str(movimento.quantidade))
                
                # Verificar se precisa corrigir
                if abs(movimento.valor_total - valor_correto) > Decimal('0.01'):
                    if not dry_run:
                        with transaction.atomic():
                            movimento.preco_unitario = custo_correto
                            movimento.valor_total = valor_correto
                            movimento.save(update_fields=['preco_unitario', 'valor_total'])
                            
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'Movimento {movimento.codigo}: Corrigido de {movimento.valor_total} para {valor_correto} MT'
                                )
                            )
                    else:
                        self.stdout.write(
                            f'[DRY-RUN] Movimento {movimento.codigo}: Corrigiria de {movimento.valor_total} para {valor_correto} MT'
                        )
                    
                    movimentos_corrigidos += 1
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f'Movimento {movimento.codigo}: Valor já está correto ({movimento.valor_total} MT)'
                        )
                    )
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'Erro ao processar movimento {movimento.codigo}: {str(e)}'
                    )
                )
                movimentos_com_erro += 1
                logger.error(f"Erro ao processar movimento {movimento.codigo}: {e}", exc_info=True)
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'Processamento concluído:'))
        self.stdout.write(f'  - Movimentos corrigidos: {movimentos_corrigidos}')
        if movimentos_com_erro > 0:
            self.stdout.write(self.style.ERROR(f'  - Movimentos com erro: {movimentos_com_erro}'))

