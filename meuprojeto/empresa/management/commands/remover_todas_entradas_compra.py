"""
Remove todas as entradas por compra (movimentos ENT_COMPRA) e reverte o stock.

Para cada MovimentoItem com tipo ENT_COMPRA:
1. Reduz a quantidade em StockItem (item + sucursal) na mesma quantidade.
2. Elimina o movimento.

Não altera ordens de compra nem lançamentos financeiros (use reverter_todas_ordens_compra
ou reverter_registo_compras para isso).
"""
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = 'Remove todos os movimentos de entrada por compra (ENT_COMPRA) e reverte o stock.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Apenas mostra quantos movimentos seriam removidos, sem alterar a base de dados.',
        )

    def handle(self, *args, **options):
        from meuprojeto.empresa.models_stock import (
            MovimentoItem,
            TipoMovimentoStock,
            StockItem,
        )

        dry_run = options['dry_run']

        try:
            tipo_entrada = TipoMovimentoStock.objects.get(codigo='ENT_COMPRA')
        except TipoMovimentoStock.DoesNotExist:
            self.stdout.write(self.style.ERROR('Tipo de movimento ENT_COMPRA não existe.'))
            return

        movimentos = MovimentoItem.objects.filter(
            tipo_movimento=tipo_entrada,
        ).select_related('item', 'sucursal').order_by('id')
        n = movimentos.count()

        if n == 0:
            self.stdout.write(self.style.WARNING('Nenhum movimento ENT_COMPRA encontrado.'))
            return

        self.stdout.write(f'Encontrados {n} movimento(s) de entrada por compra (ENT_COMPRA).')

        if dry_run:
            for mov in movimentos[:20]:
                self.stdout.write(
                    f'  id={mov.id} {mov.codigo} item={mov.item_id} sucursal={mov.sucursal_id} qty={mov.quantidade}'
                )
            if n > 20:
                self.stdout.write(f'  ... e mais {n - 20}.')
            self.stdout.write(self.style.WARNING('Dry-run: nenhuma alteração feita.'))
            return

        removidos = 0
        erros = []

        with transaction.atomic():
            for mov in movimentos:
                try:
                    stock_item = StockItem.objects.filter(
                        item=mov.item,
                        sucursal=mov.sucursal,
                    ).first()
                    if stock_item:
                        nova_qty = stock_item.quantidade_atual - Decimal(mov.quantidade)
                        if nova_qty < 0:
                            nova_qty = Decimal('0')
                        stock_item.quantidade_atual = nova_qty
                        stock_item.save(update_fields=['quantidade_atual'])
                    mov.delete()
                    removidos += 1
                except Exception as e:
                    erros.append(f'id={mov.id}: {e}')
                    self.stdout.write(self.style.ERROR(f'  Erro em movimento id={mov.id}: {e}'))

        if erros:
            self.stdout.write(self.style.WARNING(f'Concluído com {len(erros)} erro(s). Removidos {removidos}.'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Removidos {removidos} movimento(s) de entrada por compra. Stock revertido.'))
