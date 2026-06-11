"""
Reverte o registo contabilístico de todas as compras (ordens de compra recebidas).

- Remove os lançamentos financeiros com origem_tipo='COMPRAS' (conta 21 Inventários e conta 32 Fornecedores).
- Opcionalmente repõe as ordens de compra para estado APROVADA e limpa data_recebimento
  (para que o stock e a contabilidade fiquem consistentes).
"""
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = 'Reverte o registo de todas as compras: remove lançamentos COMPRAS e, opcionalmente, estado RECEBIDA das ordens.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Apenas mostra o que seria revertido, sem alterar a base de dados.',
        )
        parser.add_argument(
            '--apenas-lancamentos',
            action='store_true',
            help='Remove só os lançamentos; não altera o status/data_recebimento das ordens de compra.',
        )

    def handle(self, *args, **options):
        from meuprojeto.empresa.models_financas import LancamentoFinanceiro
        from meuprojeto.empresa.models_stock import OrdemCompra

        dry_run = options['dry_run']
        apenas_lancamentos = options['apenas_lancamentos']

        # Todos os lançamentos de compras (conta 21 e 32 com origem COMPRAS)
        lancamentos_compras = LancamentoFinanceiro.objects.filter(
            origem_tipo='COMPRAS',
        ).select_related('conta')

        ids_ordens = list(
            lancamentos_compras.values_list('origem_id', flat=True).distinct()
        )
        ids_ordens = [x for x in ids_ordens if x is not None]

        n_lanc = lancamentos_compras.count()
        self.stdout.write(
            f'Encontrados {n_lanc} lançamento(s) de COMPRAS '
            f'(ordens: {len(ids_ordens)}).'
        )

        if n_lanc == 0:
            self.stdout.write(self.style.WARNING('Nada a reverter.'))
            return

        for oid in ids_ordens:
            par = LancamentoFinanceiro.objects.filter(
                origem_tipo='COMPRAS',
                origem_id=oid,
            ).select_related('conta')
            for l in par:
                self.stdout.write(
                    f'  OrdemCompra id={oid}: lanç. id={l.id} conta={l.conta.codigo} {l.valor} MT'
                )

        if not apenas_lancamentos and ids_ordens:
            ordens = OrdemCompra.objects.filter(
                id__in=ids_ordens,
                status='RECEBIDA',
            )
            self.stdout.write(
                f'  {ordens.count()} ordem(ns) de compra serão repostas para APROVADA (data_recebimento=None).'
            )

        if dry_run:
            self.stdout.write(self.style.WARNING('Dry-run: nenhuma alteração feita.'))
            return

        with transaction.atomic():
            lancamentos_compras.delete()
            self.stdout.write(self.style.SUCCESS(f'Removidos {n_lanc} lançamento(s).'))

            if not apenas_lancamentos and ids_ordens:
                updated = OrdemCompra.objects.filter(
                    id__in=ids_ordens,
                    status='RECEBIDA',
                ).update(status='APROVADA', data_recebimento=None)
                self.stdout.write(
                    self.style.SUCCESS(
                        f'{updated} ordem(ns) de compra repostas para APROVADA (data_recebimento limpo).'
                    )
                )

        self.stdout.write(self.style.SUCCESS('Registo de compras revertido.'))
