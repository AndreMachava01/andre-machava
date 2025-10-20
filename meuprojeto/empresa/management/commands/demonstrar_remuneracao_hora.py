from django.core.management.base import BaseCommand
from meuprojeto.empresa.models_rh import Funcionario, FolhaSalarial
from datetime import date

class Command(BaseCommand):
    help = 'Demonstra os métodos de remuneração por hora do sistema'

    def handle(self, *args, **options):
        self.stdout.write('=== MÉTODOS DE REMUNERAÇÃO POR HORA ===')
        self.stdout.write('')
        
        # Buscar um funcionário para exemplo
        funcionario = Funcionario.objects.filter(status='AT').first()
        if funcionario:
            self.stdout.write(f'📋 FUNCIONÁRIO: {funcionario.nome_completo}')
            self.stdout.write(f'💰 Salário Atual: {funcionario.get_salario_atual()} MT')
            self.stdout.write('')
            
            # Testar método de remuneração por hora (real)
            self.stdout.write('🕐 REMUNERAÇÃO POR HORA (REAL):')
            remuneracao_hora = funcionario.get_remuneracao_por_hora()
            if remuneracao_hora:
                self.stdout.write(f'   Remuneração por Hora: {remuneracao_hora["remuneracao_por_hora"]} MT/hora')
                self.stdout.write(f'   Salário Base: {remuneracao_hora["salario_base"]} MT')
                self.stdout.write(f'   Horas Trabalhadas: {remuneracao_hora["horas_trabalhadas"]} horas')
                self.stdout.write(f'   Dias Trabalhados: {remuneracao_hora["dias_trabalhados"]} dias')
                self.stdout.write(f'   Mês de Referência: {remuneracao_hora["mes_referencia"].strftime("%B/%Y")}')
            else:
                self.stdout.write('   ❌ Não foi possível calcular (sem folha ou horas)')
            
            self.stdout.write('')
            
            # Testar método de remuneração por dia
            self.stdout.write('📅 REMUNERAÇÃO POR DIA:')
            remuneracao_dia = funcionario.get_remuneracao_por_dia()
            if remuneracao_dia:
                self.stdout.write(f'   Remuneração por Dia: {remuneracao_dia["remuneracao_por_dia"]} MT/dia')
                self.stdout.write(f'   Salário Base: {remuneracao_dia["salario_base"]} MT')
                self.stdout.write(f'   Dias Trabalhados: {remuneracao_dia["dias_trabalhados"]} dias')
                self.stdout.write(f'   Mês de Referência: {remuneracao_dia["mes_referencia"].strftime("%B/%Y")}')
            else:
                self.stdout.write('   ❌ Não foi possível calcular (sem folha ou dias)')
            
            self.stdout.write('')
            
            # Testar método de remuneração por hora teórica
            self.stdout.write('📊 REMUNERAÇÃO POR HORA (TEÓRICA):')
            remuneracao_teorica = funcionario.get_remuneracao_por_hora_teorica()
            if remuneracao_teorica:
                self.stdout.write(f'   Remuneração por Hora Teórica: {remuneracao_teorica["remuneracao_por_hora_teorica"]} MT/hora')
                self.stdout.write(f'   Salário Atual: {remuneracao_teorica["salario_atual"]} MT')
                self.stdout.write(f'   Horas por Dia: {remuneracao_teorica["horas_por_dia"]} horas')
                self.stdout.write(f'   Dias por Mês: {remuneracao_teorica["dias_por_mes"]} dias')
                self.stdout.write(f'   Horas Mensais Teóricas: {remuneracao_teorica["horas_mensais_teoricas"]} horas')
            else:
                self.stdout.write('   ❌ Não foi possível calcular (sem sucursal ou horários)')
            
            self.stdout.write('')
            self.stdout.write('📋 RESUMO DOS MÉTODOS:')
            self.stdout.write('   1. get_remuneracao_por_hora() - Baseado em horas reais trabalhadas')
            self.stdout.write('   2. get_remuneracao_por_dia() - Baseado em dias reais trabalhados')
            self.stdout.write('   3. get_remuneracao_por_hora_teorica() - Baseado no horário de expediente')
            self.stdout.write('')
            self.stdout.write('💡 DIFERENÇAS:')
            self.stdout.write('   • REAL: Usa horas/dias efetivamente trabalhados')
            self.stdout.write('   • TEÓRICA: Usa horário de expediente da sucursal')
            self.stdout.write('   • Útil para: Comparações, planejamento, análises')
            
        else:
            self.stdout.write('❌ Nenhum funcionário ativo encontrado')
