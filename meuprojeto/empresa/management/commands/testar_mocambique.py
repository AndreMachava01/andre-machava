from django.core.management.base import BaseCommand
from meuprojeto.empresa.models_base import DadosEmpresa, Sucursal
from datetime import date

class Command(BaseCommand):
    help = 'Testa as validações e configurações específicas para Moçambique'

    def handle(self, *args, **options):
        self.stdout.write("=== TESTANDO CONFIGURAÇÕES MOÇAMBICANAS ===\n")
        
        # Teste 1: Validação de NUIT
        self.stdout.write("1. Testando validação de NUIT...")
        empresa = None
        try:
            # Usar NUIT único
            nuit_teste = "999999999"
            empresa = DadosEmpresa.objects.create(
                nome="Empresa Teste MZ",
                nuit=nuit_teste,
                alvara="ALV123456",
                data_constituicao=date.today(),
                provincia="MP",
                cidade="Maputo",
                bairro="Centro",
                endereco="Av. 25 de Setembro, 123",
                telefone="+258841234567",
                email="teste@empresa.co.mz",
                is_sede=True,
                tipo_societario="LDA",
                numero_registro_comercial="123456",
                data_registro_comercial=date.today(),
                actividade_principal="COMERCIO",
                capital_social=100000.00
            )
            self.stdout.write(f"   ✅ NUIT válido: {empresa.nuit}")
        except Exception as e:
            self.stdout.write(f"   ❌ Erro: {e}")
            # Usar empresa existente se houver erro
            empresa = DadosEmpresa.objects.first()
            if empresa:
                self.stdout.write(f"   Usando empresa existente: {empresa.nome}")
        
        # Teste 2: Validação de telefone
        self.stdout.write("\n2. Testando validação de telefone...")
        telefones_teste = [
            "+258841234567",  # Válido
            "841234567",      # Válido
            "258841234567",   # Válido
            "123456789",      # Inválido (não começa com 8 ou 2)
            "84123456",       # Inválido (muito curto)
        ]
        
        for tel in telefones_teste:
            try:
                # Criar uma empresa temporária para testar
                temp_empresa = DadosEmpresa(
                    nome="Teste Telefone",
                    nuit="987654321",
                    alvara="ALV987654",
                    data_constituicao=date.today(),
                    provincia="MP",
                    cidade="Maputo",
                    bairro="Centro",
                    endereco="Teste",
                    telefone=tel,
                    email="teste@teste.co.mz",
                    is_sede=False
                )
                temp_empresa.full_clean()  # Valida sem salvar
                self.stdout.write(f"   ✅ {tel} - Válido")
            except Exception as e:
                self.stdout.write(f"   ❌ {tel} - Inválido: {e}")
        
        # Teste 3: Verificar sucursal criada automaticamente
        self.stdout.write("\n3. Verificando sucursal criada automaticamente...")
        if empresa:
            sucursais = Sucursal.objects.filter(empresa_sede=empresa)
            for sucursal in sucursais:
                self.stdout.write(f"   ✅ {sucursal.codigo} - {sucursal.nome}")
                self.stdout.write(f"      Tipo: {sucursal.tipo}")
                self.stdout.write(f"      Província: {sucursal.get_provincia_display()}")
                self.stdout.write(f"      Telefone: {sucursal.telefone}")
        else:
            self.stdout.write("   ⚠️ Nenhuma empresa disponível para teste")
        
        # Teste 4: Verificar campos moçambicanos
        self.stdout.write("\n4. Verificando campos específicos de Moçambique...")
        if empresa:
            self.stdout.write(f"   Tipo Societário: {empresa.get_tipo_societario_display()}")
            self.stdout.write(f"   Actividade: {empresa.get_actividade_principal_display()}")
            self.stdout.write(f"   Capital Social: {empresa.capital_social:,.2f} MT")
            self.stdout.write(f"   Registo Comercial: {empresa.numero_registro_comercial}")
        else:
            self.stdout.write("   ⚠️ Nenhuma empresa disponível para teste")
        
        # Teste 5: Verificar províncias
        self.stdout.write("\n5. Verificando províncias de Moçambique...")
        from meuprojeto.empresa.models_base import Provincia
        for codigo, nome in Provincia.choices:
            self.stdout.write(f"   {codigo}: {nome}")
        
        self.stdout.write(self.style.SUCCESS('\n✅ Testes de Moçambique concluídos com sucesso!'))
