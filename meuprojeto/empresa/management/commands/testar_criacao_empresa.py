from django.core.management.base import BaseCommand
from meuprojeto.empresa.models_base import DadosEmpresa, Sucursal
from datetime import date

class Command(BaseCommand):
    help = 'Testa a criação automática de empresa sede e sucursal'

    def handle(self, *args, **options):
        self.stdout.write("=== TESTANDO CRIAÇÃO AUTOMÁTICA DE EMPRESA SEDE ===\n")
        
        # Verificar dados existentes
        empresas_existentes = DadosEmpresa.objects.count()
        sucursais_existentes = Sucursal.objects.count()
        
        self.stdout.write(f"Dados existentes: {empresas_existentes} empresas, {sucursais_existentes} sucursais")
        
        if empresas_existentes > 0:
            self.stdout.write("⚠️  Já existem empresas no sistema. Testando com dados existentes...")
            empresa = DadosEmpresa.objects.first()
            self.stdout.write(f"Usando empresa: {empresa.nome} (É sede: {empresa.is_sede})")
            
            # Verificar sucursais existentes
            sucursais = Sucursal.objects.filter(empresa_sede=empresa)
            self.stdout.write(f"Sucursais existentes: {sucursais.count()}")
            for sucursal in sucursais:
                self.stdout.write(f"  - {sucursal.codigo} - {sucursal.nome} ({sucursal.tipo})")
            
            return
        
        self.stdout.write("1. Criando nova empresa...")
        empresa = DadosEmpresa.objects.create(
            nome="Empresa Teste Lda",
            nuit="987654321",
            alvara="ALV-TEST-001",
            data_constituicao=date.today(),
            provincia="MP",
            cidade="Maputo",
            bairro="Centro",
            endereco="Av. 25 de Setembro, 123",
            telefone="+258841234567",
            email="teste@empresa.co.mz",
            is_sede=True,  # Marcando como sede
            tipo_societario="Sociedade por Quotas"
        )
        
        self.stdout.write(f"   ✅ Empresa criada: {empresa.nome}")
        self.stdout.write(f"   ✅ É sede: {empresa.is_sede}")
        
        # Verificar se a sucursal foi criada automaticamente
        sucursais = Sucursal.objects.filter(empresa_sede=empresa)
        self.stdout.write(f"\n2. Sucursais criadas automaticamente: {sucursais.count()}")
        
        for sucursal in sucursais:
            self.stdout.write(f"   ✅ {sucursal.codigo} - {sucursal.nome}")
            self.stdout.write(f"      Tipo: {sucursal.tipo}")
            self.stdout.write(f"      Ativa: {sucursal.ativa}")
        
        self.stdout.write(f"\n3. Testando criação de filial...")
        filial = Sucursal.objects.create(
            empresa_sede=empresa,
            nome="Filial Norte",
            codigo="FIL-001",
            tipo="FILIAL",
            responsavel="João Silva",
            provincia="NA",
            cidade="Nampula",
            bairro="Cidade de Nampula",
            endereco="Av. 25 de Setembro, 456",
            telefone="+258987654321",
            email="nampula@empresa.co.mz",
            data_abertura=date.today(),
            ativa=True
        )
        
        self.stdout.write(f"   ✅ Filial criada: {filial.codigo} - {filial.nome}")
        
        # Resumo final
        total_sucursais = Sucursal.objects.filter(empresa_sede=empresa).count()
        self.stdout.write(f"\n=== RESUMO ===")
        self.stdout.write(f"Empresa: {empresa.nome}")
        self.stdout.write(f"Total de sucursais: {total_sucursais}")
        self.stdout.write(f"Sucursais ativas: {Sucursal.objects.filter(empresa_sede=empresa, ativa=True).count()}")
        
        self.stdout.write(self.style.SUCCESS('\n✅ Teste concluído com sucesso!'))
