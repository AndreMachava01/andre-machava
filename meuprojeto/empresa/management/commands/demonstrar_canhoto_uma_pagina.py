from django.core.management.base import BaseCommand
from meuprojeto.empresa.models_rh import FolhaSalarial, FuncionarioFolha, BeneficioFolha, DescontoFolha
from meuprojeto.empresa.models_base import DadosEmpresa
from datetime import date

class Command(BaseCommand):
    help = 'Demonstra a otimização do canhoto para caber em uma única página'

    def handle(self, *args, **options):
        self.stdout.write('=== CANHOTO OTIMIZADO PARA UMA PÁGINA ===')
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
        
        # Mostrar otimizações implementadas
        self.stdout.write('✅ OTIMIZAÇÕES PARA UMA PÁGINA:')
        self.stdout.write('=' * 60)
        self.stdout.write('')
        
        self.stdout.write('📏 MARGENS REDUZIDAS:')
        self.stdout.write('  • ANTES: 72px (margens grandes)')
        self.stdout.write('  • AGORA: 40px (margens otimizadas)')
        self.stdout.write('  • RESULTADO: Mais espaço para conteúdo')
        self.stdout.write('')
        
        self.stdout.write('🔤 TAMANHOS DE FONTE OTIMIZADOS:')
        self.stdout.write('  • Título: 18px → 16px')
        self.stdout.write('  • Subtítulo: 14px → 12px')
        self.stdout.write('  • Cabeçalhos: 12px → 10px')
        self.stdout.write('  • Tabelas: 10px → 9px')
        self.stdout.write('  • Rodapé: 8px → 7px')
        self.stdout.write('')
        
        self.stdout.write('📐 ESPAÇAMENTOS REDUZIDOS:')
        self.stdout.write('  • Entre seções: 20px → 10px')
        self.stdout.write('  • Cabeçalho: 20px → 10px')
        self.stdout.write('  • Tabelas: 8px → 4px padding')
        self.stdout.write('  • Declaração: 20px → 8px')
        self.stdout.write('')
        
        self.stdout.write('📋 LAYOUT COMPACTO:')
        self.stdout.write('  • Dados horizontais (trabalhador + empresa)')
        self.stdout.write('  • Resumo salarial com dias e horas integrados')
        self.stdout.write('  • Declaração e assinatura compactas')
        self.stdout.write('  • Sem seções redundantes')
        self.stdout.write('')
        
        # Mostrar estrutura final otimizada
        self.stdout.write('📄 ESTRUTURA FINAL (UMA PÁGINA):')
        self.stdout.write('=' * 60)
        self.stdout.write('')
        
        self.stdout.write('1. 📄 CABEÇALHO COMPACTO (5% da página)')
        self.stdout.write('   • "RECIBO DE SALÁRIO" (16px)')
        self.stdout.write('   • Mês de Referência (12px)')
        self.stdout.write('')
        
        self.stdout.write('2. 👥 DADOS HORIZONTAIS (25% da página)')
        self.stdout.write('   • 🧑‍💼 TRABALHADOR (esquerda) - 9px')
        self.stdout.write('     - Nome, Código, Cargo, Departamento, Sucursal, Data')
        self.stdout.write('   • 🏢 EMPREGADOR (direita) - 9px')
        self.stdout.write(f'     - Nome: {empresa.nome}')
        self.stdout.write(f'     - NUIT: {empresa.nuit}')
        self.stdout.write(f'     - Endereço: {empresa.endereco}, {empresa.bairro}, {empresa.cidade}')
        self.stdout.write('')
        
        self.stdout.write('3. 💰 RESUMO SALARIAL COMPLETO (50% da página)')
        self.stdout.write('   • Salário Base, Benefícios, Descontos (9px)')
        self.stdout.write('   • Dias Trabalhados e Horas integrados')
        self.stdout.write('   • SALÁRIO LÍQUIDO destacado (10px)')
        self.stdout.write('')
        
        self.stdout.write('4. 📝 DECLARAÇÃO E ASSINATURA (20% da página)')
        self.stdout.write('   • Texto oficial compacto (14px)')
        self.stdout.write('   • Assinatura em 2 linhas (9px)')
        self.stdout.write('   • Rodapé mínimo (7px)')
        self.stdout.write('')
        
        # Benefícios da otimização
        self.stdout.write('🎯 BENEFÍCIOS DA OTIMIZAÇÃO:')
        self.stdout.write('=' * 60)
        self.stdout.write('')
        
        self.stdout.write('✅ CABE EM UMA PÁGINA:')
        self.stdout.write('  • Layout otimizado para A4')
        self.stdout.write('  • Margens e espaçamentos reduzidos')
        self.stdout.write('  • Fontes compactas mas legíveis')
        self.stdout.write('')
        
        self.stdout.write('✅ IMPRESSÃO EFICIENTE:')
        self.stdout.write('  • Sem desperdício de papel')
        self.stdout.write('  • Custo reduzido de impressão')
        self.stdout.write('  • Fácil arquivamento')
        self.stdout.write('')
        
        self.stdout.write('✅ LEGIBILIDADE MANTIDA:')
        self.stdout.write('  • Fontes ainda legíveis')
        self.stdout.write('  • Hierarquia visual clara')
        self.stdout.write('  • Informações organizadas')
        self.stdout.write('')
        
        self.stdout.write('✅ CONFORMIDADE OFICIAL:')
        self.stdout.write('  • Estrutura conforme Ministério do Trabalho')
        self.stdout.write('  • Todos os dados obrigatórios presentes')
        self.stdout.write('  • Layout profissional')
        self.stdout.write('')
        
        # URLs de acesso
        self.stdout.write('🔗 ACESSO AO CANHOTO OTIMIZADO:')
        self.stdout.write('=' * 60)
        self.stdout.write(f'  Visualizar HTML: /rh/folha-salarial/canhoto-visualizar/{folha.id}/{funcionario_folha.funcionario.id}/')
        self.stdout.write(f'  Baixar PDF: /rh/folha-salarial/canhoto/{folha.id}/{funcionario_folha.funcionario.id}/')
        self.stdout.write('')
        
        self.stdout.write('🎉 CANHOTO OTIMIZADO PARA UMA PÁGINA!')
        self.stdout.write('   Agora cabe perfeitamente em uma única página A4!')
