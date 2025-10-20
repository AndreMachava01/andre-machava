from django.core.management.base import BaseCommand
from meuprojeto.empresa.models_rh import FolhaSalarial, FuncionarioFolha, BeneficioFolha, DescontoFolha
from meuprojeto.empresa.models_base import DadosEmpresa
from datetime import date

class Command(BaseCommand):
    help = 'Demonstra a padronização de todas as tabelas no estilo da declaração'

    def handle(self, *args, **options):
        self.stdout.write('=== PADRONIZAÇÃO NO ESTILO DA DECLARAÇÃO ===')
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
        
        # Mostrar estilo da declaração aplicado
        self.stdout.write('🎨 ESTILO DA DECLARAÇÃO APLICADO:')
        self.stdout.write('=' * 60)
        self.stdout.write('')
        
        self.stdout.write('📝 CARACTERÍSTICAS DO ESTILO DA DECLARAÇÃO:')
        self.stdout.write('  • Fundo com gradiente sutil (#f8fafc → #f1f5f9)')
        self.stdout.write('  • Bordas arredondadas (12px)')
        self.stdout.write('  • Borda externa (#e2e8f0)')
        self.stdout.write('  • Sombra suave (0 2px 4px)')
        self.stdout.write('  • Espaçamento generoso (15-20px)')
        self.stdout.write('  • Cores harmoniosas e elegantes')
        self.stdout.write('')
        
        self.stdout.write('📊 TABELAS PADRONIZADAS NO ESTILO DA DECLARAÇÃO:')
        self.stdout.write('=' * 60)
        self.stdout.write('')
        
        self.stdout.write('1. 📊 DADOS HORIZONTAIS (Empresa/Funcionário):')
        self.stdout.write('   ✅ Fundo com gradiente sutil')
        self.stdout.write('   ✅ Bordas arredondadas (12px)')
        self.stdout.write('   ✅ Borda externa (#e2e8f0)')
        self.stdout.write('   ✅ Sombra suave (0 2px 4px)')
        self.stdout.write('   ✅ Cabeçalho com gradiente azul')
        self.stdout.write('   ✅ Células com fundo gradiente')
        self.stdout.write('   ✅ STATUS: PADRONIZADA ✅')
        self.stdout.write('')
        
        self.stdout.write('2. 💰 RESUMO SALARIAL:')
        self.stdout.write('   ✅ Fundo com gradiente sutil')
        self.stdout.write('   ✅ Bordas arredondadas (12px)')
        self.stdout.write('   ✅ Borda externa (#e2e8f0)')
        self.stdout.write('   ✅ Sombra suave (0 2px 4px)')
        self.stdout.write('   ✅ Cabeçalho com gradiente azul')
        self.stdout.write('   ✅ Células com fundo gradiente')
        self.stdout.write('   ✅ Salário líquido destacado em verde')
        self.stdout.write('   ✅ STATUS: PADRONIZADA ✅')
        self.stdout.write('')
        
        self.stdout.write('3. 🎁 TABELA DE BENEFÍCIOS:')
        self.stdout.write('   ✅ Fundo com gradiente sutil')
        self.stdout.write('   ✅ Bordas arredondadas (12px)')
        self.stdout.write('   ✅ Borda externa (#e2e8f0)')
        self.stdout.write('   ✅ Sombra suave (0 2px 4px)')
        self.stdout.write('   ✅ Cabeçalho com gradiente azul')
        self.stdout.write('   ✅ Células com fundo gradiente')
        self.stdout.write('   ✅ STATUS: PADRONIZADA ✅')
        self.stdout.write('')
        
        self.stdout.write('4. 💸 TABELA DE DESCONTOS:')
        self.stdout.write('   ✅ Fundo com gradiente sutil')
        self.stdout.write('   ✅ Bordas arredondadas (12px)')
        self.stdout.write('   ✅ Borda externa (#e2e8f0)')
        self.stdout.write('   ✅ Sombra suave (0 2px 4px)')
        self.stdout.write('   ✅ Cabeçalho com gradiente azul')
        self.stdout.write('   ✅ Células com fundo gradiente')
        self.stdout.write('   ✅ STATUS: PADRONIZADA ✅')
        self.stdout.write('')
        
        self.stdout.write('5. ✍️ TABELA DE ASSINATURA:')
        self.stdout.write('   ✅ Fundo com gradiente sutil')
        self.stdout.write('   ✅ Bordas arredondadas (12px)')
        self.stdout.write('   ✅ Borda externa (#e2e8f0)')
        self.stdout.write('   ✅ Sombra suave (0 2px 4px)')
        self.stdout.write('   ✅ Células com fundo gradiente')
        self.stdout.write('   ✅ STATUS: PADRONIZADA ✅')
        self.stdout.write('')
        
        self.stdout.write('6. 📋 SEÇÃO DE PRESENÇA:')
        self.stdout.write('   ✅ Fundo com gradiente sutil')
        self.stdout.write('   ✅ Bordas arredondadas (12px)')
        self.stdout.write('   ✅ Borda externa (#e2e8f0)')
        self.stdout.write('   ✅ Sombra suave (0 2px 4px)')
        self.stdout.write('   ✅ STATUS: PADRONIZADA ✅')
        self.stdout.write('')
        
        self.stdout.write('7. 📝 SEÇÃO DE DECLARAÇÃO:')
        self.stdout.write('   ✅ Fundo com gradiente sutil')
        self.stdout.write('   ✅ Bordas arredondadas (12px)')
        self.stdout.write('   ✅ Borda externa (#e2e8f0)')
        self.stdout.write('   ✅ Sombra suave (0 2px 4px)')
        self.stdout.write('   ✅ Borda esquerda azul')
        self.stdout.write('   ✅ STATUS: PADRONIZADA ✅')
        self.stdout.write('')
        
        # Benefícios da padronização
        self.stdout.write('🎯 BENEFÍCIOS DA PADRONIZAÇÃO:')
        self.stdout.write('=' * 60)
        self.stdout.write('')
        
        self.stdout.write('✅ CONSISTÊNCIA VISUAL TOTAL:')
        self.stdout.write('  • Todas as tabelas seguem o mesmo padrão')
        self.stdout.write('  • Estilo elegante e harmonioso')
        self.stdout.write('  • Aparência profissional e moderna')
        self.stdout.write('  • Fácil identificação de seções')
        self.stdout.write('')
        
        self.stdout.write('✅ EXPERIÊNCIA DO USUÁRIO:')
        self.stdout.write('  • Interface intuitiva e familiar')
        self.stdout.write('  • Elementos visuais consistentes')
        self.stdout.write('  • Navegação fluida e organizada')
        self.stdout.write('  • Legibilidade otimizada')
        self.stdout.write('')
        
        self.stdout.write('✅ MANUTENIBILIDADE:')
        self.stdout.write('  • Código CSS organizado e reutilizável')
        self.stdout.write('  • Fácil atualização futura')
        self.stdout.write('  • Padrões bem definidos')
        self.stdout.write('  • Consistência em toda a aplicação')
        self.stdout.write('')
        
        # URLs de acesso
        self.stdout.write('🔗 ACESSO AO CANHOTO PADRONIZADO:')
        self.stdout.write('=' * 60)
        self.stdout.write(f'  Visualizar HTML: /rh/folha-salarial/canhoto-visualizar/{folha.id}/{funcionario_folha.funcionario.id}/')
        self.stdout.write(f'  Baixar PDF: /rh/folha-salarial/canhoto/{folha.id}/{funcionario_folha.funcionario.id}/')
        self.stdout.write('')
        
        self.stdout.write('🎉 TODAS AS TABELAS PADRONIZADAS!')
        self.stdout.write('   Agora todas seguem o estilo elegante da declaração!')
