"""
Elimina todos os lançamentos financeiros da conta 32 (Fornecedores e outros credores).

O saldo dessa conta é a soma dos valores dos lançamentos; ao removê-los, o saldo passa a zero.
Atenção: isto deixa desequilibradas as contas correspondentes (ex.: 26 Caixa, 21 Inventários)
se não forem revertidas as operações de origem ou removidos também esses lançamentos.
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum


class Command(BaseCommand):
    help = 'Elimina todos os lançamentos da conta 32 (Fornecedores e outros credores).'

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
        from meuprojeto.empresa.models_financas import Conta, LancamentoFinanceiro

        dry_run = options['dry_run']
        yes = options['yes']

        try:
            conta_32 = Conta.objects.get(codigo='32')
        except Conta.DoesNotExist:
            self.stdout.write(self.style.ERROR('Conta 32 (Fornecedores e outros credores) não existe.'))
            return

        qs = LancamentoFinanceiro.objects.filter(conta=conta_32).order_by('data', 'id')
        n = qs.count()
        agg = qs.aggregate(total=Sum('valor'))
        total = agg['total'] or Decimal('0.00')

        self.stdout.write(
            f'Conta: {conta_32.codigo} - {conta_32.nome}\n'
            f'Lançamentos a eliminar: {n}\n'
            f'Soma dos valores: {total} MT'
        )

        if n == 0:
            self.stdout.write(self.style.WARNING('Nenhum lançamento na conta 32.'))
            return

        # Mostrar alguns exemplos
        for lanc in qs[:10]:
            self.stdout.write(
                f'  id={lanc.id} data={lanc.data} valor={lanc.valor} descricao={lanc.descricao[:50]!r}'
            )
        if n > 10:
            self.stdout.write(f'  ... e mais {n - 10} lançamento(s).')

        if not dry_run and not yes:
            confirm = input('Eliminar todos estes lançamentos? [y/N]: ')
            if confirm.strip().lower() != 'y':
                self.stdout.write('Operação cancelada.')
                return

        if dry_run:
            self.stdout.write(self.style.WARNING('Dry-run: nenhuma alteração feita.'))
            return

        with transaction.atomic():
            deleted, _ = qs.delete()
            self.stdout.write(self.style.SUCCESS(f'Eliminados {deleted} lançamento(s) da conta 32. Saldo da conta passa a zero.'))
