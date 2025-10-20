from django.core.management.base import BaseCommand
from meuprojeto.empresa.models_rh import FolhaSalarial, FuncionarioFolha, BeneficioFolha, DescontoFolha
from meuprojeto.empresa.models_base import DadosEmpresa
from datetime import date

class Command(BaseCommand):
    help = 'Demonstra a padronização de todas as tabelas com design moderno'

    def handle(self, *args, **options):
        self.stdout.write('=== PADRONIZAÇÃO DE TODAS AS TABELAS ===')
        self.stdout.write('')
        
        # Buscar dados da empresa
        empresa = DadosEmpresa.objects.filter(is_sede=True).first()
        if empresa:
            self.stdout.write('🏢 DADOS DA EMPRESA:')
            self.stdout.write(f'  Nome: {empresa.nome}')
            self.stdout.write(f'  NUIT: {empresa.nuit}')
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
        
        # Mostrar padronização implementada
        self.stdout.write('🎨 PADRONIZAÇÃO IMPLEMENTADA:')
        self.stdout.write('=' * 60)
        self.stdout.write('')
        
        self.stdout.write('📊 TODAS AS TABELAS AGORA TÊM:')
        self.stdout.write('  • Bordas arredondadas (12px)')
        self.stdout.write('  • Gradientes nos cabeçalhos (#4f46e5 → #6366f1)')
        self.stdout.write('  • Sombras suaves (box-shadow)')
        self.stdout.write('  • Cores alternadas nas linhas')
        self.stdout.write('  • Espaçamento generoso (15px padding)')
        self.stdout.write('  • Tipografia moderna (Helvetica)')
        self.stdout.write('  • Cores consistentes em toda a interface')
        self.stdout.write('')
        
        self.stdout.write('📋 TABELAS PADRONIZADAS:')
        self.stdout.write('=' * 60)
        self.stdout.write('')
        
        self.stdout.write('1. 📊 TABELA DE DADOS HORIZONTAIS:')
        self.stdout.write('   • Cabeçalho com gradiente azul')
        self.stdout.write('   • Cores alternadas (f8fafc / f1f5f9)')
        self.stdout.write('   • Bordas arredondadas completas')
        self.stdout.write('   • Sombra sutil')
        self.stdout.write('')
        
        self.stdout.write('2. 💰 TABELA DE RESUMO SALARIAL:')
        self.stdout.write('   • Cabeçalho com gradiente')
        self.stdout.write('   • Linhas alternadas com cores suaves')
        self.stdout.write('   • Salário líquido destacado em verde')
        self.stdout.write('   • Bordas arredondadas')
        self.stdout.write('')
        
        self.stdout.write('3. 🎁 TABELA DE BENEFÍCIOS:')
        self.stdout.write('   • ANTES: Cabeçalho roxo (#8b5cf6)')
        self.stdout.write('   • AGORA: Cabeçalho com gradiente azul')
        self.stdout.write('   • Bordas arredondadas')
        self.stdout.write('   • Cores alternadas')
        self.stdout.write('')
        
        self.stdout.write('4. 💸 TABELA DE DESCONTOS:')
        self.stdout.write('   • ANTES: Cabeçalho vermelho (#ef4444)')
        self.stdout.write('   • AGORA: Cabeçalho com gradiente azul')
        self.stdout.write('   • Bordas arredondadas')
        self.stdout.write('   • Cores alternadas')
        self.stdout.write('')
        
        self.stdout.write('5. ✍️ TABELA DE ASSINATURA:')
        self.stdout.write('   • Fundo com gradiente sutil')
        self.stdout.write('   • Bordas arredondadas')
        self.stdout.write('   • Sombra elegante')
        self.stdout.write('   • Linha de assinatura moderna')
        self.stdout.write('')
        
        self.stdout.write('6. 📋 SEÇÃO DE PRESENÇA:')
        self.stdout.write('   • Fundo com gradiente')
        self.stdout.write('   • Bordas arredondadas')
        self.stdout.write('   • Sombra sutil')
        self.stdout.write('   • Espaçamento generoso')
        self.stdout.write('')
        
        self.stdout.write('7. 📝 SEÇÃO DE DECLARAÇÃO:')
        self.stdout.write('   • Fundo com gradiente')
        self.stdout.write('   • Borda esquerda azul')
        self.stdout.write('   • Bordas arredondadas')
        self.stdout.write('   • Sombra elegante')
        self.stdout.write('')
        
        # Benefícios da padronização
        self.stdout.write('🎯 BENEFÍCIOS DA PADRONIZAÇÃO:')
        self.stdout.write('=' * 60)
        self.stdout.write('')
        
        self.stdout.write('✅ CONSISTÊNCIA VISUAL:')
        self.stdout.write('  • Todas as tabelas seguem o mesmo padrão')
        self.stdout.write('  • Cores harmoniosas em toda a interface')
        self.stdout.write('  • Bordas arredondadas consistentes')
        self.stdout.write('  • Espaçamento uniforme')
        self.stdout.write('')
        
        self.stdout.write('✅ PROFISSIONALISMO:')
        self.stdout.write('  • Aparência moderna e elegante')
        self.stdout.write('  • Design coeso e organizado')
        self.stdout.write('  • Fácil leitura e navegação')
        self.stdout.write('  • Qualidade visual superior')
        self.stdout.write('')
        
        self.stdout.write('✅ EXPERIÊNCIA DO USUÁRIO:')
        self.stdout.write('  • Interface intuitiva e familiar')
        self.stdout.write('  • Elementos visuais consistentes')
        self.stdout.write('  • Fácil identificação de seções')
        self.stdout.write('  • Navegação fluida')
        self.stdout.write('')
        
        self.stdout.write('✅ MANUTENIBILIDADE:')
        self.stdout.write('  • Código CSS organizado')
        self.stdout.write('  • Estilos reutilizáveis')
        self.stdout.write('  • Fácil atualização futura')
        self.stdout.write('  • Padrões bem definidos')
        self.stdout.write('')
        
        # URLs de acesso
        self.stdout.write('🔗 ACESSO AO CANHOTO PADRONIZADO:')
        self.stdout.write('=' * 60)
        self.stdout.write(f'  Visualizar HTML: /rh/folha-salarial/canhoto-visualizar/{folha.id}/{funcionario_folha.funcionario.id}/')
        self.stdout.write(f'  Baixar PDF: /rh/folha-salarial/canhoto/{folha.id}/{funcionario_folha.funcionario.id}/')
        self.stdout.write('')
        
        self.stdout.write('🎉 TODAS AS TABELAS PADRONIZADAS!')
        self.stdout.write('   Agora todas seguem o mesmo design moderno e elegante!')
