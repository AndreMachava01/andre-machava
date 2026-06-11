"""
Elimina ordens de compra por código (ex.: OC-TESTE-001, OC-TESTE-002, OC-TESTE-003).
Remove dependências (itens, notificações, rastreamentos, etc.) e, se RECEBIDA, reverte stock e lançamentos COMPRAS.

Uso: python manage.py eliminar_ordens_compra_por_codigo OC-TESTE-001 OC-TESTE-002 OC-TESTE-003 [--dry-run] [--yes]
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction, connection


class Command(BaseCommand):
    help = 'Elimina ordens de compra pelos códigos indicados (ex.: OC-TESTE-001 OC-TESTE-002).'

    def add_arguments(self, parser):
        parser.add_argument(
            'codigos',
            nargs='+',
            type=str,
            help='Códigos das ordens (ex.: OC-TESTE-001 OC-TESTE-002)',
        )
        parser.add_argument('--dry-run', action='store_true', help='Só mostrar o que seria eliminado.')
        parser.add_argument('--yes', action='store_true', help='Não pedir confirmação.')

    def handle(self, *args, **options):
        from meuprojeto.empresa.models_financas import LancamentoFinanceiro
        from meuprojeto.empresa.models_stock import (
            OrdemCompra,
            ItemOrdemCompra,
            MovimentoItem,
            TipoMovimentoStock,
            StockItem,
        )

        codigos = [c.strip() for c in options['codigos'] if c.strip()]
        dry_run = options['dry_run']
        yes = options['yes']

        if not codigos:
            self.stdout.write(self.style.ERROR('Indique pelo menos um código de ordem.'))
            return

        ordens = OrdemCompra.objects.filter(codigo__in=codigos).order_by('codigo')
        ordem_ids = list(ordens.values_list('id', flat=True))
        n = len(ordem_ids)

        if n == 0:
            self.stdout.write(self.style.WARNING('Nenhuma ordem encontrada com os códigos indicados.'))
            return

        for oc in ordens:
            self.stdout.write(f'  {oc.codigo} (id={oc.id}) {oc.get_status_display()} {oc.valor_total} MT')
        self.stdout.write(f'Total: {n} ordem(ns) a eliminar.')

        if not dry_run and not yes:
            confirm = input('Eliminar estas ordens e dependências? [y/N]: ')
            if confirm.strip().lower() != 'y':
                self.stdout.write('Operação cancelada.')
                return

        if dry_run:
            self.stdout.write(self.style.WARNING('Dry-run: nenhuma alteração feita.'))
            return

        with transaction.atomic():
            tipo_entrada = None
            try:
                tipo_entrada = TipoMovimentoStock.objects.get(codigo='ENT_COMPRA')
            except TipoMovimentoStock.DoesNotExist:
                pass

            ordens_recebidas = ordens.filter(status='RECEBIDA')
            for oc in ordens_recebidas:
                if tipo_entrada:
                    movimentos = MovimentoItem.objects.filter(
                        observacoes__icontains=f'Recebimento da ordem {oc.codigo}',
                        tipo_movimento=tipo_entrada,
                    ).select_related('item', 'sucursal')
                    for mov in movimentos:
                        stock_item = StockItem.objects.filter(item=mov.item, sucursal=mov.sucursal).first()
                        if stock_item:
                            nova_qty = stock_item.quantidade_atual - Decimal(mov.quantidade)
                            if nova_qty < 0:
                                nova_qty = Decimal('0')
                            stock_item.quantidade_atual = nova_qty
                            stock_item.save(update_fields=['quantidade_atual'])
                        mov.delete()
                LancamentoFinanceiro.objects.filter(origem_tipo='COMPRAS', origem_id=oc.id).delete()
                ItemOrdemCompra.objects.filter(ordem_compra=oc).update(quantidade_recebida=0)
                self.stdout.write(f'  Revertida ordem {oc.codigo} (stock + lançamentos)')

            placeholders = ','.join('%s' for _ in ordem_ids)
            params = tuple(ordem_ids)
            cursor = connection.cursor()

            for sql, p in [
                (f'DELETE FROM empresa_itemordemcompra WHERE ordem_compra_id IN ({placeholders})', params),
                (f'DELETE FROM empresa_historicoenvioemail WHERE ordem_compra_id IN ({placeholders})', params),
                (f'DELETE FROM empresa_notificacaologisticaunificada WHERE ordem_compra_id IN ({placeholders})', params),
            ]:
                cursor.execute(sql, p)

            cursor.execute(
                f'SELECT id FROM empresa_rastreamentoentrega WHERE ordem_compra_id IN ({placeholders})',
                params,
            )
            rast_ids = [row[0] for row in cursor.fetchall()]
            if rast_ids:
                ph = ','.join('%s' for _ in rast_ids)
                cursor.execute(f'DELETE FROM empresa_eventorastreamento WHERE rastreamento_id IN ({ph})', tuple(rast_ids))
            cursor.execute(f'DELETE FROM empresa_rastreamentoentrega WHERE ordem_compra_id IN ({placeholders})', params)
            cursor.execute(f'DELETE FROM empresa_ordemcompra WHERE id IN ({placeholders})', params)

            self.stdout.write(self.style.SUCCESS(f'Eliminadas {n} ordem(ns) de compra.'))
