"""
Elimina todos os lançamentos financeiros de uma conta (ex.: 26 Caixa, 32 Fornecedores).

O saldo da conta é a soma dos valores dos lançamentos; ao removê-los, o saldo passa a zero.
Uso: python manage.py eliminar_lancamentos_conta 26 --yes
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum


class Command(BaseCommand):
    help = 'Elimina todos os lançamentos de uma conta (ex.: 26, 32).'

    def add_arguments(self, parser):
        parser.add_argument(
            'codigo',
            type=str,
            help='Código da conta (ex.: 26, 32)',
        )
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

        codigo = options['codigo'].strip()
        dry_run = options['dry_run']
        yes = options['yes']

        try:
            conta = Conta.objects.get(codigo=codigo)
        except Conta.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Conta {codigo!r} não existe.'))
            return

        qs = LancamentoFinanceiro.objects.filter(conta=conta).order_by('data', 'id')
        n = qs.count()
        agg = qs.aggregate(total=Sum('valor'))
        total = agg['total'] or Decimal('0.00')

        self.stdout.write(
            f'Conta: {conta.codigo} - {conta.nome}\n'
            f'Lançamentos a eliminar: {n}\n'
            f'Soma dos valores: {total} MT'
        )

        if n == 0:
            self.stdout.write(self.style.WARNING(f'Nenhum lançamento na conta {codigo}.'))
            return

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
            self.stdout.write(self.style.SUCCESS(f'Eliminados {deleted} lançamento(s) da conta {codigo}. Saldo da conta passa a zero.'))
