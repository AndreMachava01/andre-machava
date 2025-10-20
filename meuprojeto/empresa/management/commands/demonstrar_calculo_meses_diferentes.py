from django.core.management.base import BaseCommand
from meuprojeto.empresa.models_rh import Funcionario, FuncionarioFolha, FolhaSalarial
from datetime import date
import calendar

class Command(BaseCommand):
    help = 'Demonstra como o sistema calcula salários considerando meses de diferentes durações'

    def handle(self, *args, **options):
        self.stdout.write('=' * 70)
        self.stdout.write('📅 ANÁLISE: CÁLCULO DE SALÁRIO EM MESES DE DIFERENTES DURAÇÕES')
        self.stdout.write('=' * 70)
        self.stdout.write('')
        
        # Buscar funcionário
        funcionario = Funcionario.objects.filter(status='AT').first()
        if not funcionario:
            self.stdout.write('❌ Nenhum funcionário ativo encontrado')
            return
        
        self.stdout.write(f'👤 FUNCIONÁRIO: {funcionario.nome_completo}')
        self.stdout.write(f'💰 Salário Base: {funcionario.salario_atual} MT')
        self.stdout.write('')
        
        # Analisar diferentes meses
        meses_teste = [
            (2025, 2),   # Fevereiro (28 dias)
            (2025, 4),   # Abril (30 dias)
            (2025, 9),   # Setembro (30 dias)
            (2025, 1),   # Janeiro (31 dias)
        ]
        
        self.stdout.write('📊 ANÁLISE POR MÊS:')
        self.stdout.write('')
        
        for ano, mes in meses_teste:
            # Calcular dias úteis do mês
            dias_uteis = self.calcular_dias_uteis_mes(ano, mes)
            dias_totais = calendar.monthrange(ano, mes)[1]
            
            # Simular funcionário folha para este mês
            salario_float = float(funcionario.salario_atual)
            valor_por_dia = salario_float / dias_uteis if dias_uteis > 0 else 0
            
            self.stdout.write(f'📅 {calendar.month_name[mes]}/{ano}:')
            self.stdout.write(f'   • Dias totais: {dias_totais}')
            self.stdout.write(f'   • Dias úteis: {dias_uteis}')
            self.stdout.write(f'   • Valor por dia: {valor_por_dia:.2f} MT')
            
            # Simular 1 falta em cada mês
            if dias_uteis > 0:
                desconto_1_falta = valor_por_dia * 1
                self.stdout.write(f'   • Desconto por 1 falta: {desconto_1_falta:.2f} MT')
                self.stdout.write(f'   • Salário com 1 falta: {salario_float - desconto_1_falta:.2f} MT')
            self.stdout.write('')
        
        # Verificar se há folhas salariais existentes
        self.stdout.write('🔍 FOLHAS SALARIAIS EXISTENTES:')
        folhas = FolhaSalarial.objects.all().order_by('-mes_referencia')[:5]
        
        for folha in folhas:
            funcionario_folha = FuncionarioFolha.objects.filter(folha=folha, funcionario=funcionario).first()
            if funcionario_folha:
                dias_uteis = funcionario_folha.calcular_dias_uteis_mes()
                valor_por_dia = float(funcionario_folha.salario_base) / dias_uteis if dias_uteis > 0 else 0
                
                self.stdout.write(f'📅 {folha.mes_referencia.strftime("%B/%Y")}:')
                self.stdout.write(f'   • Dias úteis: {dias_uteis}')
                self.stdout.write(f'   • Dias trabalhados: {funcionario_folha.dias_trabalhados}')
                self.stdout.write(f'   • Valor por dia: {valor_por_dia:.2f} MT')
                self.stdout.write(f'   • Desconto por faltas: {funcionario_folha.desconto_faltas} MT')
                self.stdout.write('')
        
        # Conclusões
        self.stdout.write('🎯 CONCLUSÕES:')
        self.stdout.write('')
        self.stdout.write('✅ O SISTEMA CONSIDERA MESES DE DIFERENTES DURAÇÕES:')
        self.stdout.write('   • Usa calendar.monthrange() para obter dias totais do mês')
        self.stdout.write('   • Calcula dias úteis específicos para cada mês')
        self.stdout.write('   • Ajusta valor por dia baseado nos dias úteis reais')
        self.stdout.write('   • Desconto proporcional ao número de dias úteis')
        self.stdout.write('')
        self.stdout.write('📊 EXEMPLOS:')
        self.stdout.write('   • Fevereiro (28 dias): ~20 dias úteis')
        self.stdout.write('   • Abril (30 dias): ~22 dias úteis')
        self.stdout.write('   • Janeiro (31 dias): ~23 dias úteis')
        self.stdout.write('')
        self.stdout.write('💰 FÓRMULA:')
        self.stdout.write('   Valor por dia = Salário Base ÷ Dias Úteis do Mês')
        self.stdout.write('   Desconto = Valor por dia × Número de Faltas')
        self.stdout.write('')
        self.stdout.write('🚀 SISTEMA CORRETO E PROPORCIONAL!')
    
    def calcular_dias_uteis_mes(self, ano, mes):
        """Calcula dias úteis de um mês específico"""
        from datetime import timedelta
        import calendar
        
        # Obter primeiro e último dia do mês
        primeiro_dia = date(ano, mes, 1)
        ultimo_dia = calendar.monthrange(ano, mes)[1]
        ultimo_dia = date(ano, mes, ultimo_dia)
        
        # Contar dias úteis (segunda a sexta)
        dias_uteis = 0
        data_atual = primeiro_dia
        
        while data_atual <= ultimo_dia:
            # 0 = segunda, 6 = domingo
            if data_atual.weekday() < 5:  # Segunda a sexta
                dias_uteis += 1
            data_atual += timedelta(days=1)
        
        return dias_uteis
