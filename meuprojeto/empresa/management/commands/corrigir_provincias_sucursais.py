from django.core.management.base import BaseCommand
from meuprojeto.empresa.models_base import DadosEmpresa, Sucursal

class Command(BaseCommand):
    help = 'Corrige as províncias das sucursais que estão vazias'

    def handle(self, *args, **options):
        self.stdout.write('Iniciando correção das províncias das sucursais...')
        
        # Mapear a província da empresa para o formato da sucursal
        provincia_mapping = {
            'Maputo Cidade': 'MP',
            'Maputo Província': 'MA', 
            'Gaza': 'GA',
            'Inhambane': 'IN',
            'Manica': 'MN',
            'Sofala': 'SO',
            'Zambézia': 'ZA',
            'Tete': 'TE',
            'Nampula': 'NA',
            'Niassa': 'NI',
            'Cabo Delgado': 'CD'
        }
        
        # Processar sucursais com província vazia
        sucursais_sem_provincia = Sucursal.objects.filter(provincia='')
        total_corrigidas = 0
        
        for sucursal in sucursais_sem_provincia:
            if sucursal.empresa_sede:
                provincia_empresa = sucursal.empresa_sede.provincia
                provincia_sucursal = provincia_mapping.get(provincia_empresa, 'MP')
                
                sucursal.provincia = provincia_sucursal
                sucursal.save()
                
                self.stdout.write(f'Sucursal "{sucursal.nome}": Província corrigida para {provincia_sucursal}')
                total_corrigidas += 1
        
        self.stdout.write(self.style.SUCCESS(f'Correção concluída! {total_corrigidas} sucursais corrigidas.'))


