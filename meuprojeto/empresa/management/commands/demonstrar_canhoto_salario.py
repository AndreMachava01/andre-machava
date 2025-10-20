from django.core.management.base import BaseCommand
from meuprojeto.empresa.models_rh import FolhaSalarial, FuncionarioFolha, BeneficioFolha, DescontoFolha
from datetime import date

class Command(BaseCommand):
    help = 'Demonstra o sistema de canhoto (recibo de salário)'

    def handle(self, *args, **options):
        self.stdout.write('=== SISTEMA DE CANHOTO (RECIBO DE SALÁRIO) ===')
        self.stdout.write('')
        
        # Buscar uma folha existente
        folha = FolhaSalarial.objects.filter(status='FECHADA').first()
        if not folha:
            folha = FolhaSalarial.objects.first()
        
        if not folha:
            self.stdout.write('❌ Nenhuma folha encontrada. Crie uma folha primeiro.')
            return
        
        self.stdout.write(f'📋 FOLHA: {folha.mes_referencia.strftime("%B/%Y")} - {folha.get_status_display()}')
        self.stdout.write('')
        
        # Buscar um funcionário da folha
        funcionario_folha = folha.funcionarios_folha.first()
        if not funcionario_folha:
            self.stdout.write('❌ Nenhum funcionário encontrado na folha.')
            return
        
        self.stdout.write(f'👤 FUNCIONÁRIO: {funcionario_folha.funcionario.nome_completo}')
        self.stdout.write(f'🆔 Código: {funcionario_folha.funcionario.codigo_funcionario}')
        self.stdout.write('')
        
        # Mostrar dados do canhoto
        self.stdout.write('📄 DADOS DO CANHOTO:')
        self.stdout.write('=' * 50)
        
        # Dados do funcionário
        self.stdout.write('DADOS DO FUNCIONÁRIO:')
        self.stdout.write(f'  Nome: {funcionario_folha.funcionario.nome_completo}')
        self.stdout.write(f'  Código: {funcionario_folha.funcionario.codigo_funcionario}')
        self.stdout.write(f'  Cargo: {funcionario_folha.funcionario.cargo.nome if funcionario_folha.funcionario.cargo else "N/A"}')
        self.stdout.write(f'  Departamento: {funcionario_folha.funcionario.departamento.nome if funcionario_folha.funcionario.departamento else "N/A"}')
        self.stdout.write(f'  Sucursal: {funcionario_folha.funcionario.sucursal.nome if funcionario_folha.funcionario.sucursal else "N/A"}')
        self.stdout.write(f'  Data de Admissão: {funcionario_folha.funcionario.data_admissao.strftime("%d/%m/%Y") if funcionario_folha.funcionario.data_admissao else "N/A"}')
        self.stdout.write('')
        
        # Resumo salarial
        self.stdout.write('RESUMO SALARIAL:')
        self.stdout.write(f'  Salário Base: {funcionario_folha.salario_base:,.2f} MT')
        self.stdout.write(f'  Total Benefícios: {funcionario_folha.total_beneficios:,.2f} MT')
        self.stdout.write(f'  Salário Bruto: {funcionario_folha.salario_bruto:,.2f} MT')
        self.stdout.write(f'  Total Descontos: {funcionario_folha.total_descontos:,.2f} MT')
        self.stdout.write(f'  Desconto por Faltas: {funcionario_folha.desconto_faltas:,.2f} MT')
        self.stdout.write(f'  SALÁRIO LÍQUIDO: {funcionario_folha.salario_liquido:,.2f} MT')
        self.stdout.write('')
        
        # Benefícios
        beneficios = BeneficioFolha.objects.filter(funcionario_folha=funcionario_folha)
        if beneficios.exists():
            self.stdout.write('BENEFÍCIOS:')
            for beneficio in beneficios:
                self.stdout.write(f'  {beneficio.beneficio.nome}: {beneficio.valor:,.2f} MT')
            self.stdout.write('')
        
        # Descontos
        descontos = DescontoFolha.objects.filter(funcionario_folha=funcionario_folha)
        if descontos.exists():
            self.stdout.write('DESCONTOS:')
            for desconto in descontos:
                observacoes = desconto.observacoes[:30] + '...' if len(desconto.observacoes) > 30 else desconto.observacoes
                self.stdout.write(f'  {desconto.desconto.nome}: {desconto.valor:,.2f} MT - {observacoes or "-"}')
            self.stdout.write('')
        
        # Informações de presença
        self.stdout.write('INFORMAÇÕES DE PRESENÇA:')
        self.stdout.write(f'  Dias Trabalhados: {funcionario_folha.dias_trabalhados}')
        self.stdout.write(f'  Horas Trabalhadas: {funcionario_folha.horas_trabalhadas:.2f}')
        self.stdout.write(f'  Horas Extras: {funcionario_folha.horas_extras:.2f}')
        self.stdout.write('')
        
        # Declaração
        self.stdout.write('DECLARAÇÃO:')
        self.stdout.write(f'  Declaro ter recebido o valor líquido de {funcionario_folha.salario_liquido:,.2f} MT')
        self.stdout.write(f'  referente ao mês de {folha.mes_referencia.strftime("%B/%Y")}.')
        self.stdout.write('')
        
        # URLs de acesso
        self.stdout.write('🔗 ACESSO AO CANHOTO:')
        self.stdout.write('=' * 50)
        self.stdout.write(f'  Visualizar HTML: /rh/folha-salarial/canhoto-visualizar/{folha.id}/{funcionario_folha.funcionario.id}/')
        self.stdout.write(f'  Baixar PDF: /rh/folha-salarial/canhoto/{folha.id}/{funcionario_folha.funcionario.id}/')
        self.stdout.write('')
        
        # Funcionalidades
        self.stdout.write('✅ FUNCIONALIDADES IMPLEMENTADAS:')
        self.stdout.write('  • Geração de PDF profissional com ReportLab')
        self.stdout.write('  • Visualização HTML responsiva')
        self.stdout.write('  • Dados completos do funcionário')
        self.stdout.write('  • Resumo salarial detalhado')
        self.stdout.write('  • Lista de benefícios e descontos')
        self.stdout.write('  • Informações de presença')
        self.stdout.write('  • Declaração de recebimento')
        self.stdout.write('  • Seção para assinatura')
        self.stdout.write('  • Botões de ação na folha salarial')
        self.stdout.write('  • Design profissional e impressão otimizada')
        self.stdout.write('')
        
        self.stdout.write('🎯 O sistema agora possui canhoto completo!')
        self.stdout.write('   Acesse a folha salarial e clique nos botões de canhoto.')
