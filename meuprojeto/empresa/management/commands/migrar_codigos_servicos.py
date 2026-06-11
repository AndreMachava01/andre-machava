"""
Migra os códigos dos serviços do formato antigo (SERV-NOME-1234) para o formato curto
baseado no nome (ex.: ARQU, COFR01, MANP02).
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from meuprojeto.empresa.models_stock import Item


class Command(BaseCommand):
    help = 'Migra códigos dos serviços de SERV-XXX-1234 para formato curto (ARQU, COFR01, etc.)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostra o que seria feito sem fazer alterações (nenhum dado é alterado)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        self.stdout.write(self.style.SUCCESS('=== MIGRAÇÃO DE CÓDIGOS DOS SERVIÇOS ==='))

        servicos = list(Item.objects.filter(
            tipo='PRODUTO',
            produto_tipo='SERVICO'
        ).order_by('nome'))

        total = len(servicos)
        if total == 0:
            self.stdout.write(self.style.SUCCESS('Nenhum serviço encontrado.'))
            return

        self.stdout.write(f'Encontrados {total} serviços para processar.')

        if dry_run:
            self.stdout.write(self.style.WARNING('Modo dry-run: as alterações serão revertidas no final.'))

        try:
            with transaction.atomic():
                atualizados = 0
                for servico in servicos:
                    codigo_antigo = servico.codigo or ''

                    novo_codigo = servico.gerar_codigo_automatico()

                    self.stdout.write(
                        f'{servico.nome[:45]:<45} {codigo_antigo[:25]:<25} -> {novo_codigo}'
                    )

                    servico.codigo = novo_codigo
                    servico.save(update_fields=['codigo'])
                    atualizados += 1

                if dry_run:
                    raise Exception('DRY_RUN_ROLLBACK')

        except Exception as e:
            if dry_run and 'DRY_RUN_ROLLBACK' in str(e):
                pass  # Rollback esperado
            else:
                raise

        self.stdout.write(f'\n=== RESUMO ===')
        self.stdout.write(f'Total processados: {total}')
        self.stdout.write(f'Atualizados: {atualizados}' + (' (revertido - dry-run)' if dry_run else ''))
        self.stdout.write(self.style.SUCCESS('Concluído.'))
