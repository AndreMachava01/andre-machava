from django.core.management.base import BaseCommand
from django.db.models import Q
from meuprojeto.empresa.models_base import DadosEmpresa

class Command(BaseCommand):
    help = 'Verifica o status das empresas e seus códigos'

    def handle(self, *args, **options):
        total_empresas = DadosEmpresa.objects.count()
        
        if total_empresas == 0:
            self.stdout.write(
                self.style.WARNING('Nenhuma empresa encontrada no banco de dados.')
            )
            return
        
        self.stdout.write(f'Total de empresas: {total_empresas}')
        self.stdout.write('=' * 50)
        
        # Empresas com código
        empresas_com_codigo = DadosEmpresa.objects.exclude(
            Q(codigo_empresa__isnull=True) | Q(codigo_empresa='')
        )
        
        # Empresas sem código
        empresas_sem_codigo = DadosEmpresa.objects.filter(
            Q(codigo_empresa__isnull=True) | Q(codigo_empresa='')
        )
        
        self.stdout.write(f'Empresas com código: {empresas_com_codigo.count()}')
        self.stdout.write(f'Empresas sem código: {empresas_sem_codigo.count()}')
        self.stdout.write('')
        
        # Listar todas as empresas
        for empresa in DadosEmpresa.objects.all().order_by('id'):
            status_codigo = '✅' if empresa.codigo_empresa else '❌'
            status_sede = '🏢' if empresa.is_sede else '🏪'
            
            self.stdout.write(
                f'{status_codigo} {status_sede} ID: {empresa.id} | '
                f'Código: {empresa.codigo_empresa or "N/A"} | '
                f'Nome: {empresa.nome} | '
                f'Tipo: {empresa.tipo_societario}'
            )
        
        if empresas_sem_codigo.exists():
            self.stdout.write('')
            self.stdout.write(
                self.style.WARNING(
                    'Execute: python manage.py corrigir_codigos_empresas para corrigir os códigos faltantes.'
                )
            )



