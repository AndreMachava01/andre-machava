from django.core.management.base import BaseCommand
from meuprojeto.empresa.models_rh import FolhaSalarial, FuncionarioFolha, BeneficioFolha, DescontoFolha
from meuprojeto.empresa.models_base import DadosEmpresa
from datetime import date
import os

class Command(BaseCommand):
    help = 'Demonstra o novo design moderno do canhoto com logo e bordas arredondadas'

    def handle(self, *args, **options):
        self.stdout.write('=== CANHOTO MODERNO E ELEGANTE ===')
        self.stdout.write('')
        
        # Verificar se a logo existe
        logo_path = os.path.join('LOGO DA CONCEPTION.jpg')
        if os.path.exists(logo_path):
            self.stdout.write('✅ LOGO ENCONTRADA: LOGO DA CONCEPTION.jpg')
        else:
            self.stdout.write('❌ LOGO NÃO ENCONTRADA: LOGO DA CONCEPTION.jpg')
        self.stdout.write('')
        
        # Buscar dados da empresa
        empresa = DadosEmpresa.objects.filter(is_sede=True).first()
        if empresa:
            self.stdout.write('🏢 DADOS DA EMPRESA:')
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
        
        # Mostrar melhorias do design moderno
        self.stdout.write('🎨 DESIGN MODERNO IMPLEMENTADO:')
        self.stdout.write('=' * 60)
        self.stdout.write('')
        
        self.stdout.write('🖼️ CABEÇALHO ELEGANTE:')
        self.stdout.write('  • Logo da empresa (60x60px) com bordas arredondadas')
        self.stdout.write('  • Título centralizado com tipografia moderna')
        self.stdout.write('  • Informações do recibo no canto direito')
        self.stdout.write('  • Fundo com gradiente sutil')
        self.stdout.write('  • Bordas arredondadas (12px)')
        self.stdout.write('')
        
        self.stdout.write('📊 TABELAS MODERNAS:')
        self.stdout.write('  • Bordas arredondadas (12px) em todas as tabelas')
        self.stdout.write('  • Gradientes nos cabeçalhos (#4f46e5 → #6366f1)')
        self.stdout.write('  • Sombras suaves (box-shadow)')
        self.stdout.write('  • Cores alternadas nas linhas')
        self.stdout.write('  • Espaçamento generoso (15px padding)')
        self.stdout.write('  • Tipografia moderna (Helvetica)')
        self.stdout.write('')
        
        self.stdout.write('🎯 CORES E PALETA:')
        self.stdout.write('  • Azul principal: #4f46e5 (Indigo)')
        self.stdout.write('  • Verde sucesso: #059669 (Emerald)')
        self.stdout.write('  • Cinza suave: #f8fafc (Slate)')
        self.stdout.write('  • Bordas: #e2e8f0 (Gray)')
        self.stdout.write('  • Texto: #1e293b (Slate)')
        self.stdout.write('')
        
        self.stdout.write('📐 LAYOUT RESPONSIVO:')
        self.stdout.write('  • Container com max-width: 800px')
        self.stdout.write('  • Margens centralizadas')
        self.stdout.write('  • Padding generoso (30px)')
        self.stdout.write('  • Sombra elegante (0 10px 25px)')
        self.stdout.write('')
        
        self.stdout.write('✨ ELEMENTOS VISUAIS:')
        self.stdout.write('  • Gradientes lineares em cabeçalhos')
        self.stdout.write('  • Bordas arredondadas consistentes')
        self.stdout.write('  • Sombras suaves e elegantes')
        self.stdout.write('  • Espaçamento harmonioso')
        self.stdout.write('  • Tipografia hierárquica')
        self.stdout.write('')
        
        # Mostrar estrutura final
        self.stdout.write('📄 ESTRUTURA FINAL MODERNA:')
        self.stdout.write('=' * 60)
        self.stdout.write('')
        
        self.stdout.write('1. 🎨 CABEÇALHO ELEGANTE')
        self.stdout.write('   • Logo da Conception (esquerda)')
        self.stdout.write('   • "RECIBO DE SALÁRIO" (centro)')
        self.stdout.write('   • Número e data do recibo (direita)')
        self.stdout.write('   • Fundo com gradiente sutil')
        self.stdout.write('')
        
        self.stdout.write('2. 👥 DADOS HORIZONTAIS MODERNOS')
        self.stdout.write('   • Tabela com bordas arredondadas')
        self.stdout.write('   • Cabeçalho com gradiente azul')
        self.stdout.write('   • Cores alternadas (f8fafc / f1f5f9)')
        self.stdout.write('   • Sombra sutil')
        self.stdout.write('')
        
        self.stdout.write('3. 💰 RESUMO SALARIAL ELEGANTE')
        self.stdout.write('   • Cabeçalho com gradiente')
        self.stdout.write('   • Linhas alternadas com cores suaves')
        self.stdout.write('   • Salário líquido destacado em verde')
        self.stdout.write('   • Bordas arredondadas')
        self.stdout.write('')
        
        self.stdout.write('4. 📝 DECLARAÇÃO MODERNA')
        self.stdout.write('   • Caixa com fundo gradiente')
        self.stdout.write('   • Borda esquerda azul')
        self.stdout.write('   • Sombra sutil')
        self.stdout.write('   • Assinatura elegante')
        self.stdout.write('')
        
        # Benefícios do design moderno
        self.stdout.write('🎯 BENEFÍCIOS DO DESIGN MODERNO:')
        self.stdout.write('=' * 60)
        self.stdout.write('')
        
        self.stdout.write('✅ APARÊNCIA PROFISSIONAL:')
        self.stdout.write('  • Visual moderno e elegante')
        self.stdout.write('  • Logo da empresa destacada')
        self.stdout.write('  • Cores harmoniosas e profissionais')
        self.stdout.write('')
        
        self.stdout.write('✅ LEGIBILIDADE MELHORADA:')
        self.stdout.write('  • Tipografia clara e hierárquica')
        self.stdout.write('  • Espaçamento generoso')
        self.stdout.write('  • Contraste adequado')
        self.stdout.write('')
        
        self.stdout.write('✅ EXPERIÊNCIA DO USUÁRIO:')
        self.stdout.write('  • Layout intuitivo e organizado')
        self.stdout.write('  • Elementos visuais atraentes')
        self.stdout.write('  • Fácil leitura e navegação')
        self.stdout.write('')
        
        self.stdout.write('✅ CONFORMIDADE OFICIAL:')
        self.stdout.write('  • Estrutura conforme Ministério do Trabalho')
        self.stdout.write('  • Todos os dados obrigatórios presentes')
        self.stdout.write('  • Layout profissional e confiável')
        self.stdout.write('')
        
        # URLs de acesso
        self.stdout.write('🔗 ACESSO AO CANHOTO MODERNO:')
        self.stdout.write('=' * 60)
        self.stdout.write(f'  Visualizar HTML: /rh/folha-salarial/canhoto-visualizar/{folha.id}/{funcionario_folha.funcionario.id}/')
        self.stdout.write(f'  Baixar PDF: /rh/folha-salarial/canhoto/{folha.id}/{funcionario_folha.funcionario.id}/')
        self.stdout.write('')
        
        self.stdout.write('🎉 CANHOTO MODERNO E ELEGANTE IMPLEMENTADO!')
        self.stdout.write('   Design inspirado em templates profissionais modernos!')
