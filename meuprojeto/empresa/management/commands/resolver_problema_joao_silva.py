from django.core.management.base import BaseCommand
from meuprojeto.empresa.models_rh import Funcionario, Presenca, TipoPresenca, FuncionarioFolha, FolhaSalarial
from datetime import date
import calendar

class Command(BaseCommand):
    help = 'Resolve o problema do João Silva com dias trabalhados'

    def handle(self, *args, **options):
        self.stdout.write('=== RESOLVENDO PROBLEMA: JOÃO SILVA ===')
        self.stdout.write('')
        
        joao = Funcionario.objects.filter(nome_completo__icontains='joao silva').first()
        tipo_falta = TipoPresenca.objects.filter(codigo='FI').first()
        
        if not joao or not tipo_falta:
            self.stdout.write('❌ Dados não encontrados')
            return
        
        # Calcular dias úteis
        dias_uteis = []
        for dia in range(1, 31):
            try:
                data = date(2025, 9, dia)
                if data.weekday() < 5:  # Segunda a sexta
                    dias_uteis.append(data)
            except ValueError:
                pass
        
        # Verificar presenças existentes
        presencas_existentes = set()
        for p in Presenca.objects.filter(funcionario=joao, data__year=2025, data__month=9):
            presencas_existentes.add(p.data)
        
        # Encontrar dias faltantes
        dias_faltantes = [d for d in dias_uteis if d not in presencas_existentes]
        
        self.stdout.write(f'📊 ANÁLISE:')
        self.stdout.write(f'   • Dias úteis: {len(dias_uteis)}')
        self.stdout.write(f'   • Dias com presença: {len([d for d in dias_uteis if d in presencas_existentes])}')
        self.stdout.write(f'   • Dias faltantes: {len(dias_faltantes)}')
        self.stdout.write('')
        
        if len(dias_faltantes) > 0:
            self.stdout.write('❌ DIAS FALTANTES:')
            for d in dias_faltantes:
                self.stdout.write(f'   {d.strftime("%d/%m")} - {d.strftime("%A")}')
            
            self.stdout.write('')
            self.stdout.write('🔧 CRIANDO PRESENÇAS DE FALTA...')
            
            for dia_falta in dias_faltantes:
                presenca, created = Presenca.objects.get_or_create(
                    funcionario=joao,
                    data=dia_falta,
                    defaults={
                        'tipo_presenca': tipo_falta,
                        'observacoes': 'Falta identificada automaticamente'
                    }
                )
                if created:
                    self.stdout.write(f'   ✅ Falta criada: {dia_falta.strftime("%d/%m")}')
                else:
                    presenca.tipo_presenca = tipo_falta
                    presenca.save()
                    self.stdout.write(f'   🔄 Falta atualizada: {dia_falta.strftime("%d/%m")}')
            
            self.stdout.write('')
            self.stdout.write('🔄 RECALCULANDO SALÁRIO...')
            
            # Recalcular salário
            folha = FolhaSalarial.objects.filter(mes_referencia__year=2025, mes_referencia__month=9).first()
            if folha:
                funcionario_folha = FuncionarioFolha.objects.filter(folha=folha, funcionario=joao).first()
                if funcionario_folha:
                    funcionario_folha.calcular_horas_trabalhadas()
                    funcionario_folha.calcular_salario()
                    
                    self.stdout.write('💰 RESULTADO FINAL:')
                    self.stdout.write(f'   • Dias trabalhados: {funcionario_folha.dias_trabalhados}')
                    self.stdout.write(f'   • Desconto por faltas: {funcionario_folha.desconto_faltas} MT')
                    self.stdout.write(f'   • Salário líquido: {funcionario_folha.salario_liquido} MT')
                    
                    if funcionario_folha.desconto_faltas > 0:
                        self.stdout.write('')
                        self.stdout.write('✅ PROBLEMA RESOLVIDO!')
                        self.stdout.write('   • Desconto por faltas aplicado')
                        self.stdout.write('   • Salário ajustado corretamente')
                    else:
                        self.stdout.write('')
                        self.stdout.write('❌ PROBLEMA PERSISTE!')
        else:
            self.stdout.write('✅ NENHUM DIA FALTANTE ENCONTRADO')
            self.stdout.write('   • Verificar se o cálculo está correto')
        
        self.stdout.write('')
        self.stdout.write('🎯 RESOLUÇÃO CONCLUÍDA!')
