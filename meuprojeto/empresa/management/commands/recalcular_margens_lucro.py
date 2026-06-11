"""
Comando para recalcular margens de lucro de todos os produtos.
A margem de lucro é calculada como: ((preco_venda - preco_custo) / preco_custo) * 100
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from decimal import Decimal
from meuprojeto.empresa.models_stock import Item
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Recalcula margens de lucro de todos os produtos'

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
        
        # Buscar todos os produtos com preço de venda e custo
        produtos = Item.objects.filter(
            tipo='PRODUTO',
            preco_venda__isnull=False,
            preco_custo__isnull=False
        ).exclude(preco_custo=0)
        
        self.stdout.write(f'Encontrados {produtos.count()} produtos para recalcular')
        
        produtos_atualizados = 0
        produtos_com_erro = 0
        
        for produto in produtos:
            try:
                # Calcular margem correta
                if produto.preco_custo and produto.preco_custo > 0:
                    margem_correta = ((produto.preco_venda - produto.preco_custo) / produto.preco_custo) * 100
                    
                    # Verificar se precisa atualizar
                    margem_atual = produto.margem_lucro or 0
                    diferenca = abs(margem_atual - margem_correta)
                    
                    if diferenca > Decimal('0.01'):  # Se diferença maior que 0.01%
                        if not dry_run:
                            with transaction.atomic():
                                produto.margem_lucro = margem_correta
                                # Usar update_fields para evitar recalcular margem novamente no save()
                                produto.save(update_fields=['margem_lucro'])
                                
                                self.stdout.write(
                                    self.style.SUCCESS(
                                        f'{produto.codigo} - {produto.nome}: Margem atualizada de {margem_atual:.2f}% para {margem_correta:.2f}%'
                                    )
                                )
                        else:
                            self.stdout.write(
                                f'[DRY-RUN] {produto.codigo} - {produto.nome}: Atualizaria margem de {margem_atual:.2f}% para {margem_correta:.2f}%'
                            )
                        
                        produtos_atualizados += 1
                    else:
                        self.stdout.write(
                            self.style.WARNING(
                                f'{produto.codigo} - {produto.nome}: Margem já está correta ({margem_atual:.2f}%)'
                            )
                        )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f'{produto.codigo} - {produto.nome}: Preço de custo inválido ou zero'
                        )
                    )
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'Erro ao processar produto {produto.codigo}: {str(e)}'
                    )
                )
                produtos_com_erro += 1
                logger.error(f"Erro ao processar produto {produto.codigo}: {e}", exc_info=True)
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'Processamento concluído:'))
        self.stdout.write(f'  - Produtos atualizados: {produtos_atualizados}')
        if produtos_com_erro > 0:
            self.stdout.write(self.style.ERROR(f'  - Produtos com erro: {produtos_com_erro}'))

