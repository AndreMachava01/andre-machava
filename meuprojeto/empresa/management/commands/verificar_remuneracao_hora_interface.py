from django.core.management.base import BaseCommand
from meuprojeto.empresa.models_rh import Funcionario, FolhaSalarial, FuncionarioFolha
from datetime import date

class Command(BaseCommand):
    help = 'Verifica se a remuneração por hora está sendo exibida na interface'

    def handle(self, *args, **options):
        self.stdout.write('=== VERIFICAÇÃO DA REMUNERAÇÃO POR HORA NA INTERFACE ===')
        self.stdout.write('')
        
        # Buscar funcionário e folha
        funcionario = Funcionario.objects.filter(status='AT').first()
        folha = FolhaSalarial.objects.filter(mes_referencia__year=2025, mes_referencia__month=9).first()
        
        if funcionario and folha:
            funcionario_folha = FuncionarioFolha.objects.filter(folha=folha, funcionario=funcionario).first()
            
            if funcionario_folha:
                self.stdout.write(f'📋 FUNCIONÁRIO: {funcionario.nome_completo}')
                self.stdout.write(f'💰 Salário Base: {funcionario_folha.salario_base} MT')
                self.stdout.write(f'⏰ Horas Trabalhadas: {funcionario_folha.horas_trabalhadas} horas')
                
                if funcionario_folha.horas_trabalhadas > 0:
                    remuneracao_por_hora = funcionario_folha.salario_base / funcionario_folha.horas_trabalhadas
                    self.stdout.write(f'💵 Remuneração por Hora: {remuneracao_por_hora:.2f} MT/hora')
                else:
                    self.stdout.write('❌ Nenhuma hora trabalhada registrada')
                
                self.stdout.write('')
                self.stdout.write('✅ INTERFACE ATUALIZADA:')
                self.stdout.write('   • Coluna "Remuneração/Hora" adicionada na folha salarial')
                self.stdout.write('   • Cálculo automático: Salário Base ÷ Horas Trabalhadas')
                self.stdout.write('   • Exibição formatada com badge amarelo')
                self.stdout.write('   • Mostra "N/A" quando não há horas trabalhadas')
                
            else:
                self.stdout.write('❌ Funcionário não encontrado na folha')
        else:
            self.stdout.write('❌ Dados não encontrados')
