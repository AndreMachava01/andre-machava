"""
Reverte todas as ordens de compra que estão RECEBIDAS.

Para cada ordem com status RECEBIDA:
1. Encontra os MovimentoItem de entrada por compra (ENT_COMPRA) dessa ordem.
2. Reduz o stock (StockItem) na mesma quantidade e elimina esses movimentos.
3. Elimina os lançamentos financeiros COMPRAS (contas 21 e 32) se existirem.
4. Repõe quantidade_recebida=0 nos itens da ordem.
5. Coloca a ordem em APROVADA e limpa data_recebimento.
"""
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = 'Reverte todas as ordens de compra recebidas: stock, lançamentos e estado da ordem.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Apenas mostra o que seria revertido, sem alterar a base de dados.',
        )

    def handle(self, *args, **options):
        from meuprojeto.empresa.models_stock import (
            OrdemCompra,
            ItemOrdemCompra,
            MovimentoItem,
            TipoMovimentoStock,
            StockItem,
        )
        from meuprojeto.empresa.models_financas import LancamentoFinanceiro

        dry_run = options['dry_run']

        ordens = OrdemCompra.objects.filter(status='RECEBIDA').order_by('id')
        n_ordens = ordens.count()

        if n_ordens == 0:
            self.stdout.write(self.style.WARNING('Nenhuma ordem de compra com status RECEBIDA.'))
            return

        try:
            tipo_entrada = TipoMovimentoStock.objects.get(codigo='ENT_COMPRA')
        except TipoMovimentoStock.DoesNotExist:
            self.stdout.write(self.style.ERROR('Tipo de movimento ENT_COMPRA não existe.'))
            return

        self.stdout.write(f'Encontradas {n_ordens} ordem(ns) de compra RECEBIDA(s).')

        if dry_run:
            for oc in ordens:
                movs = MovimentoItem.objects.filter(
                    observacoes__icontains=f'Recebimento da ordem {oc.codigo}',
                    tipo_movimento=tipo_entrada,
                )
                lans = LancamentoFinanceiro.objects.filter(origem_tipo='COMPRAS', origem_id=oc.id)
                self.stdout.write(
                    f'  {oc.codigo} (id={oc.id}): {movs.count()} movimento(s), {lans.count()} lançamento(s)'
                )
            self.stdout.write(self.style.WARNING('Dry-run: nenhuma alteração feita.'))
            return

        revertidas = 0
        erros = []

        with transaction.atomic():
            for oc in ordens:
                try:
                    # 1. Movimentos de entrada por compra desta ordem
                    movimentos = MovimentoItem.objects.filter(
                        observacoes__icontains=f'Recebimento da ordem {oc.codigo}',
                        tipo_movimento=tipo_entrada,
                    ).select_related('item', 'sucursal')

                    for mov in movimentos:
                        # Reduzir stock
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

                    # 2. Lançamentos COMPRAS
                    LancamentoFinanceiro.objects.filter(
                        origem_tipo='COMPRAS',
                        origem_id=oc.id,
                    ).delete()

                    # 3. Itens da ordem: quantidade_recebida = 0
                    ItemOrdemCompra.objects.filter(ordem_compra=oc).update(quantidade_recebida=0)

                    # 4. Ordem: APROVADA, sem data_recebimento
                    oc.status = 'APROVADA'
                    oc.data_recebimento = None
                    oc.save(update_fields=['status', 'data_recebimento'])

                    revertidas += 1
                    self.stdout.write(f'  Revertida: {oc.codigo} (id={oc.id})')
                except Exception as e:
                    erros.append(f'{oc.codigo}: {e}')
                    self.stdout.write(self.style.ERROR(f'  Erro em {oc.codigo}: {e}'))

        if erros:
            self.stdout.write(self.style.WARNING(f'Concluído com {len(erros)} erro(s).'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Todas as {revertidas} ordem(ns) de compra foram revertidas.'))
