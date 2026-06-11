"""
Remove lançamentos de receita (71.01, 72.01) criados por "Importar totais".
Esses lançamentos duplicam os que já existem do fluxo normal (confirmar conta receber).
Execute para corrigir o DRE quando Total Receitas estiver inflacionado (ex.: o dobro do esperado).
"""
from decimal import Decimal
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Remove lançamentos de receita (71.01, 72.01) criados por Importar totais (documento_ref IMP-*)'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Apenas mostra o que seria removido, sem alterar.')

    def handle(self, *args, **options):
        from meuprojeto.empresa.models_financas import LancamentoFinanceiro

        dry_run = options['dry_run']
        duplicados = LancamentoFinanceiro.objects.filter(
            documento_ref__startswith='IMP-',
            conta__codigo__in=('71.01', '72.01'),
        ).select_related('conta')
        lista = list(duplicados)
        total = sum(l.valor for l in lista)
        if not lista:
            self.stdout.write(self.style.SUCCESS('Nenhum lançamento de receita duplicado (IMP-*) encontrado.'))
            return
        self.stdout.write(f'Encontrados {len(lista)} lançamento(s) de receita criados por Importar totais:')
        for l in lista:
            self.stdout.write(f'  ID {l.id}: {l.data} | {l.conta.codigo} | {l.valor} MT | doc_ref={l.documento_ref}')
        self.stdout.write(f'Total a remover: {total:.2f} MT')
        if dry_run:
            self.stdout.write(self.style.WARNING('Dry-run: nenhuma alteração feita. Execute sem --dry-run para remover.'))
            return
        n = duplicados.delete()[0]
        self.stdout.write(self.style.SUCCESS(f'Removidos {n} lançamento(s). Total Receitas no DRE deve diminuir em {total:.2f} MT.'))
