"""
Elimina todas as requisições de compra externa (stock/requisicoes/compra-externa/) e dados relacionados.

Para cada requisição de compra externa:
1. Ordens de compra (OrdemCompra) com requisicao_origem nessas requisições.
2. Se a ordem estiver RECEBIDA: reverte stock (MovimentoItem ENT_COMPRA + StockItem), remove lançamentos COMPRAS.
3. Elimina todas as RequisicaoCompraExterna (cascade: ItemRequisicaoCompraExterna, OrdemCompra, ItemOrdemCompra,
   NotificacaoLogisticaUnificada, etc.).

Uso: python manage.py eliminar_compras_externas [--dry-run] [--yes]
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction, connection


class Command(BaseCommand):
    help = 'Elimina todas as requisições de compra externa e ordens/movimentos/lançamentos associados.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Apenas mostra o que seria eliminado, sem alterar a base de dados.',
        )
        parser.add_argument(
            '--yes',
            action='store_true',
            help='Não pedir confirmação antes de eliminar.',
        )

    def handle(self, *args, **options):
        from meuprojeto.empresa.models_financas import LancamentoFinanceiro
        from meuprojeto.empresa.models_stock import (
            RequisicaoCompraExterna,
            OrdemCompra,
            ItemOrdemCompra,
            MovimentoItem,
            TipoMovimentoStock,
            StockItem,
        )

        dry_run = options['dry_run']
        yes = options['yes']

        requisicoes = RequisicaoCompraExterna.objects.all().order_by('id')
        n_req = requisicoes.count()
        if n_req == 0:
            self.stdout.write(self.style.WARNING('Nenhuma requisição de compra externa encontrada.'))
            return

        ordens = OrdemCompra.objects.filter(requisicao_origem__in=requisicoes).order_by('id')
        n_ordens = ordens.count()
        ordens_recebidas = ordens.filter(status='RECEBIDA')
        n_recebidas = ordens_recebidas.count()

        self.stdout.write(
            f'Requisições de compra externa: {n_req}\n'
            f'Ordens de compra associadas: {n_ordens} ({n_recebidas} recebidas)'
        )
        for r in requisicoes:
            self.stdout.write(f'  - {r.codigo} (id={r.id})')
        for oc in ordens:
            self.stdout.write(f'  Ordem {oc.codigo} (id={oc.id}) status={oc.status}')

        try:
            tipo_entrada = TipoMovimentoStock.objects.get(codigo='ENT_COMPRA')
        except TipoMovimentoStock.DoesNotExist:
            tipo_entrada = None
            self.stdout.write(self.style.ERROR('Tipo de movimento ENT_COMPRA não existe. Stock não será revertido.'))

        if n_recebidas > 0 and tipo_entrada:
            total_movs = 0
            total_lans = 0
            for oc in ordens_recebidas:
                movs = MovimentoItem.objects.filter(
                    observacoes__icontains=f'Recebimento da ordem {oc.codigo}',
                    tipo_movimento=tipo_entrada,
                )
                lans = LancamentoFinanceiro.objects.filter(origem_tipo='COMPRAS', origem_id=oc.id)
                total_movs += movs.count()
                total_lans += lans.count()
            self.stdout.write(
                f'Serão revertidos: {total_movs} movimento(s) de stock e {total_lans} lançamento(s) financeiros COMPRAS.'
            )

        if not dry_run and not yes:
            confirm = input('Eliminar todas as requisições de compra externa e dados relacionados? [y/N]: ')
            if confirm.strip().lower() != 'y':
                self.stdout.write('Operação cancelada.')
                return

        if dry_run:
            self.stdout.write(self.style.WARNING('Dry-run: nenhuma alteração feita.'))
            return

        with transaction.atomic():
            # 1. Reverter ordens RECEBIDAS: stock + lançamentos COMPRAS
            if tipo_entrada:
                for oc in ordens_recebidas:
                    movimentos = MovimentoItem.objects.filter(
                        observacoes__icontains=f'Recebimento da ordem {oc.codigo}',
                        tipo_movimento=tipo_entrada,
                    ).select_related('item', 'sucursal')
                    for mov in movimentos:
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
                    LancamentoFinanceiro.objects.filter(
                        origem_tipo='COMPRAS',
                        origem_id=oc.id,
                    ).delete()
                    ItemOrdemCompra.objects.filter(ordem_compra=oc).update(quantidade_recebida=0)
                    self.stdout.write(f'  Revertida ordem {oc.codigo} (stock + lançamentos)')

            # 2. Eliminar ordens e requisições por SQL (evita cascade que carrega tabelas em falta, ex. empresa_custologistico)
            ids_req = list(requisicoes.values_list('id', flat=True))
            ordem_ids = list(ordens.values_list('id', flat=True))
            placeholders_ordem = ','.join('%s' for _ in ordem_ids) if ordem_ids else '0'
            placeholders_req = ','.join('%s' for _ in ids_req) if ids_req else '0'
            params_ordem = tuple(ordem_ids) if ordem_ids else ()
            params_req = tuple(ids_req) if ids_req else ()
            cursor = connection.cursor()

            # Tabelas que referenciam OrdemCompra (eliminar antes de empresa_ordemcompra).
            # Ordem: filhos de OrdemCompra; depois EventoRastreamento (rastreamento_id); depois RastreamentoEntrega.
            for sql, params in [
                (f'DELETE FROM empresa_itemordemcompra WHERE ordem_compra_id IN ({placeholders_ordem})', params_ordem),
                (f'DELETE FROM empresa_historicoenvioemail WHERE ordem_compra_id IN ({placeholders_ordem})', params_ordem),
                (f'DELETE FROM empresa_notificacaologisticaunificada WHERE ordem_compra_id IN ({placeholders_ordem})', params_ordem),
            ]:
                cursor.execute(sql, params)

            # EventoRastreamento: obter ids de RastreamentoEntrega e depois apagar eventos (evita subquery com mesmo params)
            cursor.execute(
                f'SELECT id FROM empresa_rastreamentoentrega WHERE ordem_compra_id IN ({placeholders_ordem})',
                params_ordem,
            )
            rastreamento_ids = [row[0] for row in cursor.fetchall()]
            if rastreamento_ids:
                ph_rast = ','.join('%s' for _ in rastreamento_ids)
                cursor.execute(
                    f'DELETE FROM empresa_eventorastreamento WHERE rastreamento_id IN ({ph_rast})',
                    tuple(rastreamento_ids),
                )
            cursor.execute(
                f'DELETE FROM empresa_rastreamentoentrega WHERE ordem_compra_id IN ({placeholders_ordem})',
                params_ordem,
            )

            if ordem_ids:
                cursor.execute(f'DELETE FROM empresa_ordemcompra WHERE id IN ({placeholders_ordem})', params_ordem)
            cursor.execute(f'DELETE FROM empresa_itemrequisicaocompraexterna WHERE requisicao_id IN ({placeholders_req})', params_req)
            cursor.execute(f'DELETE FROM empresa_requisicaocompraexterna WHERE id IN ({placeholders_req})', params_req)

            self.stdout.write(self.style.SUCCESS(f'Eliminadas {n_req} requisição(ões) de compra externa e {n_ordens} ordem(ns) de compra.'))
