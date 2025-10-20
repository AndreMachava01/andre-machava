from django.core.management.base import BaseCommand
from meuprojeto.empresa.models_rh import FolhaSalarial, FuncionarioFolha, BeneficioFolha, DescontoFolha
from meuprojeto.empresa.models_base import DadosEmpresa
from datetime import date

class Command(BaseCommand):
    help = 'Demonstra as melhorias do canhoto: dados reais da empresa e folha mais concisa'

    def handle(self, *args, **options):
        self.stdout.write('=== CANHOTO MELHORADO - DADOS REAIS E FOLHA CONCISA ===')
        self.stdout.write('')
        
        # Buscar dados da empresa
        empresa = DadosEmpresa.objects.filter(is_sede=True).first()
        if empresa:
            self.stdout.write('🏢 DADOS DA EMPRESA (REAIS):')
            self.stdout.write(f'  Nome: {empresa.nome}')
            self.stdout.write(f'  NUIT: {empresa.nuit}')
            self.stdout.write(f'  Endereço: {empresa.endereco}, {empresa.bairro}, {empresa.cidade}')
            self.stdout.write('')
        else:
            self.stdout.write('❌ Nenhuma empresa encontrada no sistema')
            return
        
        # Buscar uma folha existente
        folha = FolhaSalarial.objects.filter(status='FECHADA').first()
        if not folha:
            folha = FolhaSalarial.objects.first()
        
        if not folha:
            self.stdout.write('❌ Nenhuma folha encontrada. Crie uma folha primeiro.')
            return
        
        self.stdout.write(f'📋 FOLHA: {folha.mes_referencia.strftime("%B/%Y")} - {folha.get_status_display()}')
        
        # Buscar um funcionário da folha
        funcionario_folha = folha.funcionarios_folha.first()
        if not funcionario_folha:
            self.stdout.write('❌ Nenhum funcionário encontrado na folha.')
            return
        
        self.stdout.write(f'👤 FUNCIONÁRIO: {funcionario_folha.funcionario.nome_completo}')
        self.stdout.write('')
        
        # Mostrar estrutura do canhoto melhorado
        self.stdout.write('📄 ESTRUTURA DO CANHOTO MELHORADO:')
        self.stdout.write('=' * 60)
        
        self.stdout.write('')
        self.stdout.write('1. 📄 CABEÇALHO OFICIAL')
        self.stdout.write('   • "Modelo de Recibo de Salário – Conforme Ministério do Trabalho"')
        self.stdout.write('   • "RECIBO DE SALÁRIO"')
        self.stdout.write('   • Mês de Referência')
        self.stdout.write('')
        
        self.stdout.write('2. 🧑‍💼 DADOS DO TRABALHADOR')
        self.stdout.write('   • Nome, Código, Cargo, Departamento, Sucursal')
        self.stdout.write('   • Data de Admissão, Categoria Profissional')
        self.stdout.write('')
        
        self.stdout.write('3. 🏢 DADOS DO EMPREGADOR (REAIS)')
        self.stdout.write(f'   • Nome da Empresa: {empresa.nome}')
        self.stdout.write(f'   • NUIT: {empresa.nuit}')
        self.stdout.write(f'   • Endereço: {empresa.endereco}, {empresa.bairro}, {empresa.cidade}')
        self.stdout.write('')
        
        self.stdout.write('4. 💰 RESUMO SALARIAL (CONFORME MODELO OFICIAL)')
        self.stdout.write('   • Salário Base')
        self.stdout.write('   • Subsídio de Alimentação')
        self.stdout.write('   • Subsídio de Transporte')
        self.stdout.write('   • Horas Extras (Xh)')
        self.stdout.write('   • Salário Bruto')
        self.stdout.write('   • INSS (3%)')
        self.stdout.write('   • IRPS')
        self.stdout.write('   • Desconto Adicional')
        self.stdout.write('   • Total Descontos')
        self.stdout.write('   • Salário Líquido')
        self.stdout.write('')
        
        self.stdout.write('5. 📋 DETALHAMENTO (SIMPLIFICADO)')
        self.stdout.write('   • Benefícios e descontos em uma única tabela')
        self.stdout.write('   • Apenas se houver benefícios ou descontos')
        self.stdout.write('')
        
        self.stdout.write('6. 📆 INFORMAÇÕES DE PRESENÇA (CONCISA)')
        self.stdout.write('   • Uma linha: "Dias Trabalhados: X | Horas: Xh | Extras: Xh"')
        self.stdout.write('')
        
        self.stdout.write('7. 📝 DECLARAÇÃO OFICIAL')
        self.stdout.write('   • Texto conforme modelo do Ministério do Trabalho')
        self.stdout.write('   • "conforme os termos legais vigentes"')
        self.stdout.write('   • Assinatura: "Data: ___/09/2025" e "Assinatura do Trabalhador"')
        self.stdout.write('')
        
        # Mostrar melhorias implementadas
        self.stdout.write('✅ MELHORIAS IMPLEMENTADAS:')
        self.stdout.write('=' * 60)
        self.stdout.write('')
        
        self.stdout.write('🔧 DADOS REAIS DA EMPRESA:')
        self.stdout.write('  • Busca automática dos dados da empresa sede')
        self.stdout.write('  • Nome, NUIT e endereço completos')
        self.stdout.write('  • Fallback para placeholders se não houver dados')
        self.stdout.write('')
        
        self.stdout.write('📄 FOLHA MAIS CONCISA:')
        self.stdout.write('  • Seções de benefícios e descontos unificadas')
        self.stdout.write('  • Informações de presença em uma linha')
        self.stdout.write('  • Tabelas mais compactas')
        self.stdout.write('  • Menos espaçamento desnecessário')
        self.stdout.write('  • Foco no essencial para impressão')
        self.stdout.write('')
        
        self.stdout.write('🎯 CONFORMIDADE OFICIAL:')
        self.stdout.write('  • Estrutura idêntica ao modelo do Ministério do Trabalho')
        self.stdout.write('  • Textos legais adequados')
        self.stdout.write('  • Formatação profissional')
        self.stdout.write('  • Layout otimizado para impressão')
        self.stdout.write('')
        
        # URLs de acesso
        self.stdout.write('🔗 ACESSO AO CANHOTO MELHORADO:')
        self.stdout.write('=' * 60)
        self.stdout.write(f'  Visualizar HTML: /rh/folha-salarial/canhoto-visualizar/{folha.id}/{funcionario_folha.funcionario.id}/')
        self.stdout.write(f'  Baixar PDF: /rh/folha-salarial/canhoto/{folha.id}/{funcionario_folha.funcionario.id}/')
        self.stdout.write('')
        
        self.stdout.write('🎉 CANHOTO OTIMIZADO E CONFORME MODELO OFICIAL!')
        self.stdout.write('   Agora usa dados reais da empresa e é mais conciso!')
