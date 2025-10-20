from django.core.management.base import BaseCommand
from meuprojeto.empresa.models_rh import Funcionario, FolhaSalarial, FuncionarioFolha, Presenca, TipoPresenca
from datetime import date, timedelta

class Command(BaseCommand):
    help = 'Simula faltas para demonstrar o desconto automático'

    def handle(self, *args, **options):
        self.stdout.write('=== SIMULAÇÃO DE FALTAS E DESCONTO AUTOMÁTICO ===')
        self.stdout.write('')
        
        # Buscar funcionário e folha
        funcionario = Funcionario.objects.filter(status='AT').first()
        folha = FolhaSalarial.objects.filter(mes_referencia__year=2025, mes_referencia__month=9).first()
        
        if not funcionario or not folha:
            self.stdout.write('❌ Funcionário ou folha não encontrados')
            return
        
        funcionario_folha = FuncionarioFolha.objects.filter(folha=folha, funcionario=funcionario).first()
        
        if not funcionario_folha:
            self.stdout.write('❌ Funcionário não encontrado na folha')
            return
        
        self.stdout.write(f'📋 FUNCIONÁRIO: {funcionario.nome_completo}')
        self.stdout.write(f'💰 Salário Base: {funcionario_folha.salario_base} MT')
        self.stdout.write('')
        
        # Buscar tipo de presença "Falta Injustificada"
        tipo_falta = TipoPresenca.objects.filter(codigo='FI').first()
        if not tipo_falta:
            self.stdout.write('❌ Tipo de presença "Falta Injustificada" não encontrado')
            return
        
        # Simular 2 faltas no mês
        self.stdout.write('🔧 SIMULANDO 2 FALTAS NO MÊS:')
        
        # Datas de falta (dias úteis)
        data_falta1 = date(2025, 9, 3)  # Terça-feira
        data_falta2 = date(2025, 9, 10)  # Terça-feira
        
        # Criar presenças de falta
        falta1, created1 = Presenca.objects.get_or_create(
            funcionario=funcionario,
            data=data_falta1,
            defaults={
                'tipo_presenca': tipo_falta,
                'observacoes': 'Falta simulada para teste de desconto'
            }
        )
        
        falta2, created2 = Presenca.objects.get_or_create(
            funcionario=funcionario,
            data=data_falta2,
            defaults={
                'tipo_presenca': tipo_falta,
                'observacoes': 'Falta simulada para teste de desconto'
            }
        )
        
        if created1:
            self.stdout.write(f'   ✅ Falta criada: {data_falta1.strftime("%d/%m/%Y")} - {tipo_falta.nome}')
        else:
            self.stdout.write(f'   ℹ️  Falta já existia: {data_falta1.strftime("%d/%m/%Y")}')
            
        if created2:
            self.stdout.write(f'   ✅ Falta criada: {data_falta2.strftime("%d/%m/%Y")} - {tipo_falta.nome}')
        else:
            self.stdout.write(f'   ℹ️  Falta já existia: {data_falta2.strftime("%d/%m/%Y")}')
        
        self.stdout.write('')
        
        # Recalcular salário
        self.stdout.write('🔄 RECALCULANDO SALÁRIO...')
        funcionario_folha.calcular_salario()
        
        # Mostrar resultado
        self.stdout.write('💰 RESULTADO APÓS SIMULAÇÃO:')
        self.stdout.write(f'   • Desconto por faltas: {funcionario_folha.desconto_faltas} MT')
        self.stdout.write(f'   • Total de descontos: {funcionario_folha.total_descontos} MT')
        self.stdout.write(f'   • Salário bruto: {funcionario_folha.salario_bruto} MT')
        self.stdout.write(f'   • Salário líquido: {funcionario_folha.salario_liquido} MT')
        self.stdout.write('')
        
        # Verificar cálculo manual
        dias_uteis = funcionario_folha.calcular_dias_uteis_mes()
        valor_por_dia = float(funcionario_folha.salario_base) / dias_uteis
        desconto_esperado = valor_por_dia * 2  # 2 faltas
        
        self.stdout.write('🧮 VERIFICAÇÃO DO CÁLCULO:')
        self.stdout.write(f'   • Dias úteis no mês: {dias_uteis}')
        self.stdout.write(f'   • Valor por dia: {valor_por_dia:.2f} MT')
        self.stdout.write(f'   • Faltas registradas: 2')
        self.stdout.write(f'   • Desconto esperado: {desconto_esperado:.2f} MT')
        self.stdout.write(f'   • Desconto aplicado: {funcionario_folha.desconto_faltas} MT')
        
        if abs(float(funcionario_folha.desconto_faltas) - desconto_esperado) < 0.01:
            self.stdout.write('   ✅ Cálculo correto!')
        else:
            self.stdout.write('   ❌ Erro no cálculo!')
        
        self.stdout.write('')
        self.stdout.write('🎯 SISTEMA FUNCIONANDO:')
        self.stdout.write('   • Desconto automático por faltas implementado')
        self.stdout.write('   • Integração com folha salarial')
        self.stdout.write('   • Cálculo baseado em dias úteis')
        self.stdout.write('   • Exibição na interface')
