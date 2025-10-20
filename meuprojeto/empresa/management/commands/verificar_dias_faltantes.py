from django.core.management.base import BaseCommand
from meuprojeto.empresa.models_rh import Funcionario, Presenca
from datetime import date
import calendar

class Command(BaseCommand):
    help = 'Verifica exatamente quais dias úteis estão faltando'

    def handle(self, *args, **options):
        self.stdout.write('=== VERIFICAÇÃO DE DIAS FALTANTES ===')
        self.stdout.write('')
        
        joao = Funcionario.objects.filter(nome_completo__icontains='joao silva').first()
        
        # Calcular dias úteis de setembro
        dias_uteis = []
        for dia in range(1, 31):
            try:
                data = date(2025, 9, dia)
                if data.weekday() < 5:  # Segunda a sexta
                    dias_uteis.append(data)
            except ValueError:
                pass
        
        self.stdout.write(f'📅 DIAS ÚTEIS DE SETEMBRO ({len(dias_uteis)}):')
        for d in dias_uteis:
            self.stdout.write(f'   {d.strftime("%d/%m")} - {d.strftime("%A")}')
        self.stdout.write('')
        
        # Verificar presenças existentes
        presencas_existentes = set()
        for p in Presenca.objects.filter(funcionario=joao, data__year=2025, data__month=9):
            presencas_existentes.add(p.data)
        
        self.stdout.write('📋 DIAS COM PRESENÇA REGISTRADA:')
        dias_com_presenca = [d for d in dias_uteis if d in presencas_existentes]
        for d in dias_com_presenca:
            self.stdout.write(f'   {d.strftime("%d/%m")} - {d.strftime("%A")}')
        self.stdout.write('')
        
        # Encontrar dias faltantes
        dias_faltantes = [d for d in dias_uteis if d not in presencas_existentes]
        
        self.stdout.write(f'❌ DIAS ÚTEIS SEM PRESENÇA ({len(dias_faltantes)}):')
        for d in dias_faltantes:
            self.stdout.write(f'   {d.strftime("%d/%m")} - {d.strftime("%A")}')
        self.stdout.write('')
        
        self.stdout.write('📊 RESUMO:')
        self.stdout.write(f'   • Total de dias úteis: {len(dias_uteis)}')
        self.stdout.write(f'   • Dias com presença: {len(dias_com_presenca)}')
        self.stdout.write(f'   • Dias faltantes: {len(dias_faltantes)}')
        self.stdout.write('')
        
        if len(dias_faltantes) > 0:
            self.stdout.write('🔧 AÇÃO NECESSÁRIA:')
            self.stdout.write('   • Criar presenças de falta para os dias faltantes')
            self.stdout.write('   • Marcar como tipo que desconta salário')
        else:
            self.stdout.write('✅ NENHUM DIA FALTANTE ENCONTRADO')
            self.stdout.write('   • Verificar se o cálculo de dias trabalhados está correto')
        
        self.stdout.write('')
        self.stdout.write('🎯 VERIFICAÇÃO CONCLUÍDA!')
