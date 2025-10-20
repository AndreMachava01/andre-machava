from django.core.management.base import BaseCommand
from meuprojeto.empresa.models_base import DadosEmpresa, Sucursal

class Command(BaseCommand):
    help = 'Corrige os códigos das sucursais para o novo formato'

    def handle(self, *args, **options):
        self.stdout.write('Iniciando correção dos códigos das sucursais...')
        
        # Processar cada empresa
        for empresa in DadosEmpresa.objects.all():
            self.stdout.write(f'Processando empresa: {empresa.nome} (Código: {empresa.codigo_empresa})')
            
            # Obter código da empresa (primeiros 3 dígitos do código_empresa)
            codigo_empresa = empresa.codigo_empresa[:3] if empresa.codigo_empresa else "001"
            
            # Obter iniciais da empresa
            nome_empresa = empresa.nome.replace(' ', '').replace('-', '')
            iniciais = ''.join([c.upper() for c in nome_empresa if c.isalpha()])[:3]
            
            # Se não conseguir 3 letras, usar as disponíveis
            if len(iniciais) < 3:
                iniciais = iniciais.ljust(3, 'X')
            
            # Processar sucursais desta empresa
            sucursais = Sucursal.objects.filter(empresa_sede=empresa).order_by('id')
            
            for i, sucursal in enumerate(sucursais, 1):
                novo_codigo = f"{codigo_empresa}{iniciais}(SUCURSAL){i:03d}"
                codigo_antigo = sucursal.codigo
                sucursal.codigo = novo_codigo
                sucursal.save()
                
                self.stdout.write(f'  Sucursal "{sucursal.nome}": {codigo_antigo} -> {novo_codigo}')
        
        self.stdout.write(self.style.SUCCESS('Correção dos códigos concluída com sucesso!'))
