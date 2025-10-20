from django.core.management.base import BaseCommand
from meuprojeto.empresa.models_rh import Funcionario, Presenca, TipoPresenca, FuncionarioFolha, FolhaSalarial
from datetime import date, timedelta
import calendar

class Command(BaseCommand):
    help = 'Identifica e corrige as faltas do João Silva'

    def handle(self, *args, **options):
        self.stdout.write('=== CORREÇÃO DAS FALTAS: JOÃO SILVA ===')
        self.stdout.write('')
        
        # Buscar funcionário e tipo de falta
        joao = Funcionario.objects.filter(nome_completo__icontains='joao silva').first()
        tipo_falta = TipoPresenca.objects.filter(codigo='FI').first()
        
        if not joao or not tipo_falta:
            self.stdout.write('❌ Dados não encontrados')
            return
        
        self.stdout.write(f'✅ FUNCIONÁRIO: {joao.nome_completo}')
        self.stdout.write(f'✅ TIPO DE FALTA: {tipo_falta.nome}')
        self.stdout.write('')
        
        # Calcular dias úteis de setembro
        mes = 9
        ano = 2025
        ultimo_dia = calendar.monthrange(ano, mes)[1]
        
        dias_uteis = []
        for dia in range(1, ultimo_dia + 1):
            data = date(ano, mes, dia)
            if data.weekday() < 5:  # Segunda a sexta
                dias_uteis.append(data)
        
        self.stdout.write(f'📅 DIAS ÚTEIS DE SETEMBRO: {len(dias_uteis)}')
        for d in dias_uteis:
            self.stdout.write(f'   {d.strftime("%d/%m")} - {d.strftime("%A")}')
        self.stdout.write('')
        
        # Verificar presenças existentes
        presencas_existentes = set()
        for p in Presenca.objects.filter(funcionario=joao, data__year=ano, data__month=mes):
            presencas_existentes.add(p.data)
        
        self.stdout.write('📋 DIAS COM PRESENÇA REGISTRADA:')
        for d in sorted(presencas_existentes):
            if d.weekday() < 5:  # Apenas dias úteis
                self.stdout.write(f'   {d.strftime("%d/%m")} - {d.strftime("%A")}')
        self.stdout.write('')
        
        # Encontrar dias faltantes
        dias_faltantes = []
        for d in dias_uteis:
            if d not in presencas_existentes:
                dias_faltantes.append(d)
        
        self.stdout.write(f'❌ DIAS FALTANTES ({len(dias_faltantes)}):')
        for d in dias_faltantes:
            self.stdout.write(f'   {d.strftime("%d/%m")} - {d.strftime("%A")}')
        self.stdout.write('')
        
        if len(dias_faltantes) > 0:
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
                    # Atualizar tipo de presença existente
                    presenca.tipo_presenca = tipo_falta
                    presenca.observacoes = 'Falta identificada automaticamente'
                    presenca.save()
                    self.stdout.write(f'   🔄 Falta atualizada: {dia_falta.strftime("%d/%m")}')
            
            self.stdout.write('')
            self.stdout.write('🔄 RECALCULANDO SALÁRIO...')
            
            # Recalcular salário
            folha = FolhaSalarial.objects.filter(mes_referencia__year=2025, mes_referencia__month=9).first()
            if folha:
                funcionario_folha = FuncionarioFolha.objects.filter(folha=folha, funcionario=joao).first()
                if funcionario_folha:
                    funcionario_folha.calcular_salario()
                    
                    self.stdout.write('💰 RESULTADO APÓS CORREÇÃO:')
                    self.stdout.write(f'   • Salário Base: {funcionario_folha.salario_base} MT')
                    self.stdout.write(f'   • Dias Trabalhados: {funcionario_folha.dias_trabalhados}')
                    self.stdout.write(f'   • Desconto por Faltas: {funcionario_folha.desconto_faltas} MT')
                    self.stdout.write(f'   • Total Descontos: {funcionario_folha.total_descontos} MT')
                    self.stdout.write(f'   • Salário Líquido: {funcionario_folha.salario_liquido} MT')
                    
                    # Verificar se o desconto foi aplicado
                    if funcionario_folha.desconto_faltas > 0:
                        self.stdout.write('')
                        self.stdout.write('✅ PROBLEMA RESOLVIDO!')
                        self.stdout.write('   • Desconto por faltas aplicado automaticamente')
                        self.stdout.write('   • Salário ajustado corretamente')
                    else:
                        self.stdout.write('')
                        self.stdout.write('❌ PROBLEMA PERSISTE!')
                        self.stdout.write('   • Verificar configuração dos tipos de presença')
        else:
            self.stdout.write('ℹ️  Nenhum dia faltante identificado')
        
        self.stdout.write('')
        self.stdout.write('🎯 CORREÇÃO CONCLUÍDA!')
