from django.core.management.base import BaseCommand
from django.db.models import Q, Count
from meuprojeto.empresa.models_base import DadosEmpresa, Sucursal

class Command(BaseCommand):
    help = 'Verifica o status das sucursais agrupadas por empresa'

    def handle(self, *args, **options):
        total_sucursais = Sucursal.objects.count()
        
        if total_sucursais == 0:
            self.stdout.write(
                self.style.WARNING('Nenhuma sucursal encontrada no banco de dados.')
            )
            return
        
        self.stdout.write(f'Total de sucursais: {total_sucursais}')
        self.stdout.write('=' * 80)
        
        # Agrupar sucursais por empresa
        empresas = DadosEmpresa.objects.all().order_by('nome')
        
        for empresa in empresas:
            sucursais = Sucursal.objects.filter(empresa_sede=empresa).order_by('codigo')
            
            if sucursais.exists():
                self.stdout.write(f'\n🏢 {empresa.nome} ({empresa.codigo_empresa})')
                self.stdout.write('─' * 60)
                
                for sucursal in sucursais:
                    status_icon = '✅' if sucursal.ativa else '❌'
                    tipo_icon = '🏢' if sucursal.tipo == 'SEDE' else '📍'
                    
                    self.stdout.write(
                        f'  {status_icon} {tipo_icon} {sucursal.codigo} | '
                        f'{sucursal.nome} | '
                        f'{sucursal.get_tipo_display()} | '
                        f'{sucursal.cidade}, {sucursal.provincia} | '
                        f'Responsável: {sucursal.responsavel}'
                    )
                
                # Estatísticas da empresa
                total_empresa = sucursais.count()
                ativas_empresa = sucursais.filter(ativa=True).count()
                inativas_empresa = total_empresa - ativas_empresa
                
                self.stdout.write(
                    f'  📊 Total: {total_empresa} | '
                    f'Ativas: {ativas_empresa} | '
                    f'Inativas: {inativas_empresa}'
                )
        
        # Estatísticas gerais
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write('📊 ESTATÍSTICAS GERAIS')
        self.stdout.write('─' * 40)
        
        total_empresas = empresas.count()
        empresas_com_sucursais = sum(1 for emp in empresas if Sucursal.objects.filter(empresa_sede=emp).exists())
        sucursais_ativas = Sucursal.objects.filter(ativa=True).count()
        sucursais_inativas = total_sucursais - sucursais_ativas
        
        self.stdout.write(f'Total de empresas: {total_empresas}')
        self.stdout.write(f'Empresas com sucursais: {empresas_com_sucursais}')
        self.stdout.write(f'Total de sucursais: {total_sucursais}')
        self.stdout.write(f'Sucursais ativas: {sucursais_ativas}')
        self.stdout.write(f'Sucursais inativas: {sucursais_inativas}')
        
        # Tipos de sucursais
        self.stdout.write('\n📋 TIPOS DE SUCURSAIS')
        self.stdout.write('─' * 30)
        
        tipos = Sucursal.objects.values('tipo').annotate(
            total=Count('id'),
            ativas=Count('id', filter=Q(ativa=True))
        ).order_by('-total')
        
        for tipo in tipos:
            self.stdout.write(
                f'{tipo["tipo"]}: {tipo["total"]} total '
                f'({tipo["ativas"]} ativas)'
            )
