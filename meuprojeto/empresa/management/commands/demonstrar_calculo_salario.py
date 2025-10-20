from django.core.management.base import BaseCommand
from meuprojeto.empresa.models_rh import Funcionario, FolhaSalarial, FuncionarioFolha, BeneficioFolha, DescontoFolha
from datetime import date

class Command(BaseCommand):
    help = 'Demonstra como o sistema calcula o salário'

    def handle(self, *args, **options):
        self.stdout.write('=== COMO O SISTEMA CALCULA O SALÁRIO ===')
        self.stdout.write('')
        
        # Buscar um funcionário para exemplo
        funcionario = Funcionario.objects.filter(status='AT').first()
        if funcionario:
            self.stdout.write(f'📋 FUNCIONÁRIO: {funcionario.nome_completo}')
            self.stdout.write(f'💰 Salário Atual: {funcionario.get_salario_atual()} MT')
            self.stdout.write('')
            
            # Buscar folha de setembro
            folha = FolhaSalarial.objects.filter(mes_referencia__year=2025, mes_referencia__month=9).first()
            
            if folha:
                self.stdout.write(f'📅 FOLHA: {folha.mes_referencia.strftime("%B/%Y")}')
                self.stdout.write(f'📊 Status: {folha.get_status_display()}')
                self.stdout.write('')
                
                # Buscar funcionário na folha
                funcionario_folha = FuncionarioFolha.objects.filter(folha=folha, funcionario=funcionario).first()
                
                if funcionario_folha:
                    self.stdout.write('🔍 CÁLCULO DETALHADO:')
                    self.stdout.write(f'   1. Salário Base: {funcionario_folha.salario_base} MT')
                    
                    # Benefícios
                    beneficios = BeneficioFolha.objects.filter(funcionario_folha=funcionario_folha)
                    total_beneficios = sum(b.valor for b in beneficios)
                    self.stdout.write(f'   2. Total Benefícios: {total_beneficios} MT')
                    for b in beneficios:
                        self.stdout.write(f'      - {b.beneficio.nome}: {b.valor} MT')
                    
                    # Descontos
                    descontos = DescontoFolha.objects.filter(funcionario_folha=funcionario_folha)
                    total_descontos = sum(d.valor for d in descontos)
                    self.stdout.write(f'   3. Total Descontos: {total_descontos} MT')
                    for d in descontos:
                        self.stdout.write(f'      - {d.desconto.nome}: {d.valor} MT')
                    
                    # Cálculos finais
                    salario_bruto = funcionario_folha.salario_base + total_beneficios
                    salario_liquido = salario_bruto - total_descontos
                    
                    self.stdout.write('')
                    self.stdout.write('📊 FÓRMULA DE CÁLCULO:')
                    self.stdout.write(f'   Salário Bruto = Salário Base + Benefícios')
                    self.stdout.write(f'   Salário Bruto = {funcionario_folha.salario_base} + {total_beneficios} = {salario_bruto} MT')
                    self.stdout.write('')
                    self.stdout.write(f'   Salário Líquido = Salário Bruto - Descontos')
                    self.stdout.write(f'   Salário Líquido = {salario_bruto} - {total_descontos} = {salario_liquido} MT')
                    self.stdout.write('')
                    
                    # Verificar valores salvos
                    self.stdout.write('💾 VALORES SALVOS NO SISTEMA:')
                    self.stdout.write(f'   salario_bruto: {funcionario_folha.salario_bruto} MT')
                    self.stdout.write(f'   salario_liquido: {funcionario_folha.salario_liquido} MT')
                    self.stdout.write(f'   total_beneficios: {funcionario_folha.total_beneficios} MT')
                    self.stdout.write(f'   total_descontos: {funcionario_folha.total_descontos} MT')
                    self.stdout.write(f'   dias_trabalhados: {funcionario_folha.dias_trabalhados}')
                    self.stdout.write(f'   horas_trabalhadas: {funcionario_folha.horas_trabalhadas}')
                    self.stdout.write(f'   horas_extras: {funcionario_folha.horas_extras}')
                    
                    self.stdout.write('')
                    self.stdout.write('🔄 PROCESSO DE CÁLCULO:')
                    self.stdout.write('   1. FuncionarioFolha.calcular_salario() é chamado')
                    self.stdout.write('   2. Salário base é sincronizado com Funcionario.salario_atual')
                    self.stdout.write('   3. Benefícios são somados da tabela BeneficioFolha')
                    self.stdout.write('   4. Descontos são somados da tabela DescontoFolha')
                    self.stdout.write('   5. Salário bruto = base + benefícios')
                    self.stdout.write('   6. Salário líquido = bruto - descontos')
                    self.stdout.write('   7. Valores são salvos no FuncionarioFolha')
                    
                else:
                    self.stdout.write('❌ Funcionário não encontrado na folha')
            else:
                self.stdout.write('❌ Folha de setembro não encontrada')
        else:
            self.stdout.write('❌ Nenhum funcionário ativo encontrado')
        
        self.stdout.write('')
        self.stdout.write('📋 FONTES DE DADOS:')
        self.stdout.write('   • Salário Base: Funcionario.salario_atual (FONTE PRINCIPAL)')
        self.stdout.write('   • Benefícios: BeneficioFolha.valor')
        self.stdout.write('   • Descontos: DescontoFolha.valor')
        self.stdout.write('   • Horas: Calculadas baseadas em Presenca + horários de expediente')
        self.stdout.write('   • Histórico: Tabela Salario (para auditoria)')
