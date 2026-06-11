"""
Comando para remover ContratoEmpreitada sem trabalhos associados.
Contratos vazios podem resultar da migração 0226 (um contrato por trabalho avulso)
ou de trabalhos eliminados posteriormente.
"""
from django.core.management.base import BaseCommand
from django.db.models import Count

from meuprojeto.empresa.models_rh import ContratoEmpreitada


class Command(BaseCommand):
    help = 'Remove contratos de empreitada que não têm trabalhos associados'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Apenas mostra o que seria removido sem deletar',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        vazios = ContratoEmpreitada.objects.annotate(
            num_trab=Count('trabalhos')
        ).filter(num_trab=0)

        total = vazios.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS('Nenhum contrato vazio encontrado.'))
            return

        if dry_run:
            self.stdout.write(
                self.style.WARNING(f'[DRY-RUN] Seriam removidos {total} contrato(s) vazio(s):')
            )
            for c in vazios.select_related('prestador', 'ordem_servico'):
                ref = c.ordem_servico.codigo if c.ordem_servico else 'Avulso'
                self.stdout.write(f'  - ID {c.id}: {c.prestador.nome} — {ref}')
            self.stdout.write(
                self.style.WARNING('Execute sem --dry-run para remover efectivamente.')
            )
            return

        ids = list(vazios.values_list('id', flat=True))
        vazios.delete()
        self.stdout.write(
            self.style.SUCCESS(f'{len(ids)} contrato(s) vazio(s) removido(s): {ids}')
        )
