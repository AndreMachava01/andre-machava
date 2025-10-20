from django.core.management.base import BaseCommand
from meuprojeto.empresa.models_rh import FolhaSalarial, FuncionarioFolha, BeneficioFolha, DescontoFolha
from meuprojeto.empresa.models_base import DadosEmpresa
from datetime import date

class Command(BaseCommand):
    help = 'Demonstra as correções do canhoto: cabeçalho limpo, dados horizontais, sem redundância'

    def handle(self, *args, **options):
        self.stdout.write('=== CANHOTO CORRIGIDO - MELHORIAS IMPLEMENTADAS ===')
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
        
        # Mostrar correções implementadas
        self.stdout.write('✅ CORREÇÕES IMPLEMENTADAS:')
        self.stdout.write('=' * 60)
        self.stdout.write('')
        
        self.stdout.write('1. ❌ REMOVIDO: "📄 Modelo de Recibo de Salário – Conforme Ministério do Trabalho"')
        self.stdout.write('   ✅ AGORA: Cabeçalho limpo com apenas "RECIBO DE SALÁRIO"')
        self.stdout.write('')
        
        self.stdout.write('2. ❌ REMOVIDO: Seção DETALHAMENTO redundante')
        self.stdout.write('   ✅ AGORA: Dados já aparecem no RESUMO SALARIAL (sem duplicação)')
        self.stdout.write('')
        
        self.stdout.write('3. ❌ ANTES: Dados do trabalhador e empresa em seções separadas')
        self.stdout.write('   ✅ AGORA: Dados organizados HORIZONTALMENTE (lado a lado)')
        self.stdout.write('')
        
        self.stdout.write('4. ❌ ANTES: Dias de trabalho e horas em seção separada')
        self.stdout.write('   ✅ AGORA: Integrados no RESUMO SALARIAL')
        self.stdout.write('')
        
        # Mostrar estrutura final
        self.stdout.write('📄 ESTRUTURA FINAL DO CANHOTO:')
        self.stdout.write('=' * 60)
        self.stdout.write('')
        
        self.stdout.write('1. 📄 CABEÇALHO LIMPO')
        self.stdout.write('   • "RECIBO DE SALÁRIO"')
        self.stdout.write('   • Mês de Referência')
        self.stdout.write('')
        
        self.stdout.write('2. 👥 DADOS HORIZONTAIS')
        self.stdout.write('   • 🧑‍💼 TRABALHADOR (esquerda)')
        self.stdout.write('     - Nome, Código, Cargo, Departamento, Sucursal, Data Admissão')
        self.stdout.write('   • 🏢 EMPREGADOR (direita)')
        self.stdout.write(f'     - Nome: {empresa.nome}')
        self.stdout.write(f'     - NUIT: {empresa.nuit}')
        self.stdout.write(f'     - Endereço: {empresa.endereco}, {empresa.bairro}, {empresa.cidade}')
        self.stdout.write('')
        
        self.stdout.write('3. 💰 RESUMO SALARIAL COMPLETO')
        self.stdout.write('   • Salário Base')
        self.stdout.write('   • Subsídio de Alimentação')
        self.stdout.write('   • Subsídio de Transporte')
        self.stdout.write('   • Horas Extras (Xh)')
        self.stdout.write('   • Salário Bruto')
        self.stdout.write('   • INSS (3%)')
        self.stdout.write('   • IRPS')
        self.stdout.write('   • Desconto Adicional')
        self.stdout.write('   • Total Descontos')
        self.stdout.write('   • [linha em branco]')
        self.stdout.write('   • Dias Trabalhados')
        self.stdout.write('   • Horas Trabalhadas')
        self.stdout.write('   • [linha em branco]')
        self.stdout.write('   • SALÁRIO LÍQUIDO')
        self.stdout.write('')
        
        self.stdout.write('4. 📝 DECLARAÇÃO')
        self.stdout.write('   • Texto oficial conforme Ministério do Trabalho')
        self.stdout.write('   • Assinatura com data e nome')
        self.stdout.write('')
        
        # Benefícios das correções
        self.stdout.write('🎯 BENEFÍCIOS DAS CORREÇÕES:')
        self.stdout.write('=' * 60)
        self.stdout.write('')
        
        self.stdout.write('✅ CABEÇALHO MAIS LIMPO:')
        self.stdout.write('  • Remove texto desnecessário')
        self.stdout.write('  • Foco no essencial')
        self.stdout.write('  • Aparência mais profissional')
        self.stdout.write('')
        
        self.stdout.write('✅ LAYOUT HORIZONTAL:')
        self.stdout.write('  • Melhor aproveitamento do espaço')
        self.stdout.write('  • Comparação visual entre trabalhador e empresa')
        self.stdout.write('  • Folha mais compacta')
        self.stdout.write('')
        
        self.stdout.write('✅ SEM REDUNDÂNCIA:')
        self.stdout.write('  • Dados aparecem apenas uma vez')
        self.stdout.write('  • Informações organizadas logicamente')
        self.stdout.write('  • Folha mais concisa')
        self.stdout.write('')
        
        self.stdout.write('✅ RESUMO SALARIAL COMPLETO:')
        self.stdout.write('  • Todos os dados financeiros em um local')
        self.stdout.write('  • Dias e horas integrados ao resumo')
        self.stdout.write('  • Fácil visualização dos totais')
        self.stdout.write('')
        
        # URLs de acesso
        self.stdout.write('🔗 ACESSO AO CANHOTO CORRIGIDO:')
        self.stdout.write('=' * 60)
        self.stdout.write(f'  Visualizar HTML: /rh/folha-salarial/canhoto-visualizar/{folha.id}/{funcionario_folha.funcionario.id}/')
        self.stdout.write(f'  Baixar PDF: /rh/folha-salarial/canhoto/{folha.id}/{funcionario_folha.funcionario.id}/')
        self.stdout.write('')
        
        self.stdout.write('🎉 CANHOTO OTIMIZADO E CORRIGIDO!')
        self.stdout.write('   Agora é mais limpo, organizado e sem redundâncias!')
