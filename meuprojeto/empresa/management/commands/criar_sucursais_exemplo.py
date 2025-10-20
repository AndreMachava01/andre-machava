from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, timedelta
from meuprojeto.empresa.models_base import DadosEmpresa, Sucursal

class Command(BaseCommand):
    help = 'Cria sucursais de exemplo para testar o agrupamento'

    def add_arguments(self, parser):
        parser.add_argument(
            '--empresa-id',
            type=int,
            help='ID da empresa para criar sucursais (se não especificado, usa a primeira empresa)',
        )

    def handle(self, *args, **options):
        empresa_id = options.get('empresa_id')
        
        if empresa_id:
            try:
                empresa = DadosEmpresa.objects.get(id=empresa_id)
            except DadosEmpresa.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'Empresa com ID {empresa_id} não encontrada.')
                )
                return
        else:
            empresa = DadosEmpresa.objects.first()
            if not empresa:
                self.stdout.write(
                    self.style.ERROR('Nenhuma empresa encontrada. Crie uma empresa primeiro.')
                )
                return
        
        self.stdout.write(f'Criando sucursais para: {empresa.nome} ({empresa.codigo_empresa})')
        
        # Dados de exemplo para diferentes tipos de sucursais
        sucursais_exemplo = [
            {
                'nome': 'Loja Centro',
                'tipo': 'LOJA',
                'provincia': 'MP',
                'cidade': 'Maputo',
                'bairro': 'Centro',
                'endereco': 'Av. 25 de Setembro, 1234',
                'telefone': '+258821234567',
                'email': 'centro@empresa.com',
                'responsavel': 'Ana Maria',
                'data_abertura': date.today() - timedelta(days=30),
            },
            {
                'nome': 'Armazém Industrial',
                'tipo': 'ARMAZEM',
                'provincia': 'MP',
                'cidade': 'Maputo',
                'bairro': 'Industrial',
                'endereco': 'Zona Industrial, Lote 45',
                'telefone': '+258821234568',
                'email': 'armazem@empresa.com',
                'responsavel': 'Carlos Mendes',
                'data_abertura': date.today() - timedelta(days=60),
            },
            {
                'nome': 'Escritório Regional',
                'tipo': 'ESCRITORIO',
                'provincia': 'SO',
                'cidade': 'Beira',
                'bairro': 'Centro',
                'endereco': 'Av. Samora Machel, 567',
                'telefone': '+258231234569',
                'email': 'beira@empresa.com',
                'responsavel': 'Sofia Pereira',
                'data_abertura': date.today() - timedelta(days=90),
            },
            {
                'nome': 'Posto de Venda',
                'tipo': 'POSTO_VENDA',
                'provincia': 'NA',
                'cidade': 'Nampula',
                'bairro': 'Mercado Central',
                'endereco': 'Mercado Central, Box 12',
                'telefone': '+258261234570',
                'email': 'nampula@empresa.com',
                'responsavel': 'José António',
                'data_abertura': date.today() - timedelta(days=15),
            },
            {
                'nome': 'Centro de Distribuição',
                'tipo': 'CENTRO_DIST',
                'provincia': 'ZA',
                'cidade': 'Quelimane',
                'bairro': 'Porto',
                'endereco': 'Porto de Quelimane, Armazém 3',
                'telefone': '+258241234571',
                'email': 'distribuicao@empresa.com',
                'responsavel': 'Manuel Silva',
                'data_abertura': date.today() - timedelta(days=120),
            },
        ]
        
        criadas = 0
        for dados in sucursais_exemplo:
            # Verificar se já existe uma sucursal com o mesmo nome
            if Sucursal.objects.filter(empresa_sede=empresa, nome=dados['nome']).exists():
                self.stdout.write(f'  ⚠️  Sucursal "{dados["nome"]}" já existe, pulando...')
                continue
            
            sucursal = Sucursal.objects.create(
                empresa_sede=empresa,
                **dados
            )
            
            self.stdout.write(
                f'  ✅ Criada: {sucursal.codigo} - {sucursal.nome} '
                f'({sucursal.get_tipo_display()}) em {sucursal.cidade}'
            )
            criadas += 1
        
        self.stdout.write(f'\n🎉 {criadas} sucursais criadas com sucesso!')
        
        # Mostrar estatísticas atualizadas
        total_sucursais = Sucursal.objects.filter(empresa_sede=empresa).count()
        ativas = Sucursal.objects.filter(empresa_sede=empresa, ativa=True).count()
        
        self.stdout.write(f'📊 Total de sucursais da empresa: {total_sucursais}')
        self.stdout.write(f'📊 Sucursais ativas: {ativas}')



