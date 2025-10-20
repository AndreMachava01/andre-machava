from django.core.management.base import BaseCommand
from meuprojeto.empresa.models_rh import Funcionario, FuncionarioFolha, FolhaSalarial, Presenca
from datetime import date, timedelta
import calendar

class Command(BaseCommand):
    help = 'Investiga como os dias trabalhados são calculados'

    def handle(self, *args, **options):
        self.stdout.write('=== INVESTIGAÇÃO: CÁLCULO DE DIAS TRABALHADOS ===')
        self.stdout.write('')
        
        joao = Funcionario.objects.filter(nome_completo__icontains='joao silva').first()
        folha = FolhaSalarial.objects.filter(mes_referencia__year=2025, mes_referencia__month=9).first()
        funcionario_folha = FuncionarioFolha.objects.filter(folha=folha, funcionario=joao).first()
        
        self.stdout.write(f'📋 FUNCIONÁRIO: {joao.nome_completo}')
        self.stdout.write(f'📊 Dias trabalhados na folha: {funcionario_folha.dias_trabalhados}')
        self.stdout.write('')
        
        # Verificar presenças por tipo
        presencas_presente = Presenca.objects.filter(
            funcionario=joao,
            data__year=2025,
            data__month=9,
            tipo_presenca__codigo='PR'
        ).count()
        
        presencas_feriado = Presenca.objects.filter(
            funcionario=joao,
            data__year=2025,
            data__month=9,
            tipo_presenca__codigo='FD'
        ).count()
        
        presencas_desconta = Presenca.objects.filter(
            funcionario=joao,
            data__year=2025,
            data__month=9,
            tipo_presenca__desconta_salario=True
        ).count()
        
        self.stdout.write('📊 ANÁLISE DE PRESENÇAS:')
        self.stdout.write(f'   • Presenças tipo Presente: {presencas_presente}')
        self.stdout.write(f'   • Presenças tipo Feriado: {presencas_feriado}')
        self.stdout.write(f'   • Presenças que descontam: {presencas_desconta}')
        self.stdout.write('')
        
        # Verificar método calcular_horas_trabalhadas
        self.stdout.write('🔍 VERIFICANDO MÉTODO calcular_horas_trabalhadas:')
        funcionario_folha.calcular_horas_trabalhadas()
        self.stdout.write(f'   • Dias trabalhados após recálculo: {funcionario_folha.dias_trabalhados}')
        self.stdout.write(f'   • Horas trabalhadas: {funcionario_folha.horas_trabalhadas}')
        self.stdout.write('')
        
        # Verificar presenças detalhadas
        self.stdout.write('📅 PRESENÇAS DETALHADAS:')
        presencas = Presenca.objects.filter(
            funcionario=joao,
            data__year=2025,
            data__month=9
        ).order_by('data')
        
        for p in presencas:
            self.stdout.write(f'   {p.data.strftime("%d/%m")} - {p.tipo_presenca.nome} (desconta: {p.tipo_presenca.desconta_salario})')
        
        self.stdout.write('')
        
        # Verificar se há dias úteis sem presença
        dias_uteis = []
        for dia in range(1, 31):
            try:
                data = date(2025, 9, dia)
                if data.weekday() < 5:  # Segunda a sexta
                    dias_uteis.append(data)
            except ValueError:
                pass
        
        presencas_existentes = set(p.data for p in presencas)
        dias_sem_presenca = [d for d in dias_uteis if d not in presencas_existentes]
        
        self.stdout.write(f'📊 DIAS ÚTEIS SEM PRESENÇA: {len(dias_sem_presenca)}')
        for d in dias_sem_presenca:
            self.stdout.write(f'   {d.strftime("%d/%m")} - {d.strftime("%A")}')
        
        self.stdout.write('')
        self.stdout.write('🎯 INVESTIGAÇÃO CONCLUÍDA!')
