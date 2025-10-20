from django.core.management.base import BaseCommand
from django.db import transaction
from meuprojeto.empresa.models_base import DadosEmpresa

class Command(BaseCommand):
    help = 'Corrige códigos de empresas que não foram gerados automaticamente'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostra o que seria feito sem fazer alterações',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Buscar empresas sem código
        empresas_sem_codigo = DadosEmpresa.objects.filter(
            codigo_empresa__isnull=True
        ) | DadosEmpresa.objects.filter(codigo_empresa='')
        
        if not empresas_sem_codigo.exists():
            self.stdout.write(
                self.style.SUCCESS('Todas as empresas já possuem códigos válidos.')
            )
            return
        
        self.stdout.write(f'Encontradas {empresas_sem_codigo.count()} empresas sem código.')
        
        if dry_run:
            self.stdout.write('Modo dry-run ativado. Nenhuma alteração será feita.')
        
        with transaction.atomic():
            for empresa in empresas_sem_codigo:
                codigo_antigo = empresa.codigo_empresa or 'N/A'
                novo_codigo = empresa.gerar_codigo_empresa_sequencial()
                
                self.stdout.write(
                    f'Empresa: {empresa.nome} | '
                    f'Código antigo: {codigo_antigo} | '
                    f'Novo código: {novo_codigo}'
                )
                
                if not dry_run:
                    empresa.codigo_empresa = novo_codigo
                    empresa.save(update_fields=['codigo_empresa'])
        
        if not dry_run:
            self.stdout.write(
                self.style.SUCCESS('Códigos das empresas corrigidos com sucesso!')
            )
        else:
            self.stdout.write(
                self.style.WARNING('Execute sem --dry-run para aplicar as correções.')
            )



