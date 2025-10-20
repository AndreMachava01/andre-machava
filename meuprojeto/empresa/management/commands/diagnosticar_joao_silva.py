from django.core.management.base import BaseCommand
from meuprojeto.empresa.models_rh import Funcionario, FolhaSalarial, FuncionarioFolha, Presenca
from datetime import date, timedelta

class Command(BaseCommand):
    help = 'Diagnostica o problema do João Silva com dias de trabalho'

    def handle(self, *args, **options):
        self.stdout.write('=== DIAGNÓSTICO: JOÃO SILVA ===')
        self.stdout.write('')
        
        # Buscar João Silva
        joao = Funcionario.objects.filter(nome_completo__icontains='joao silva').first()
        if not joao:
            self.stdout.write('❌ João Silva não encontrado')
            return
        
        self.stdout.write(f'✅ FUNCIONÁRIO: {joao.nome_completo}')
        self.stdout.write(f'   Status: {joao.status}')
        self.stdout.write(f'   Salário atual: {joao.salario_atual} MT')
        self.stdout.write('')
        
        # Buscar folha de setembro
        folha = FolhaSalarial.objects.filter(mes_referencia__year=2025, mes_referencia__month=9).first()
        if not folha:
            self.stdout.write('❌ Folha de setembro não encontrada')
            return
        
        funcionario_folha = FuncionarioFolha.objects.filter(folha=folha, funcionario=joao).first()
        if not funcionario_folha:
            self.stdout.write('❌ Funcionário não encontrado na folha de setembro')
            return
        
        self.stdout.write('💰 DADOS DA FOLHA:')
        self.stdout.write(f'   • Salário Base: {funcionario_folha.salario_base} MT')
        self.stdout.write(f'   • Dias Trabalhados: {funcionario_folha.dias_trabalhados}')
        self.stdout.write(f'   • Horas Trabalhadas: {funcionario_folha.horas_trabalhadas}')
        self.stdout.write(f'   • Desconto por Faltas: {funcionario_folha.desconto_faltas} MT')
        self.stdout.write(f'   • Total Descontos: {funcionario_folha.total_descontos} MT')
        self.stdout.write(f'   • Salário Líquido: {funcionario_folha.salario_liquido} MT')
        self.stdout.write('')
        
        # Verificar presenças do mês
        primeiro_dia = folha.mes_referencia.replace(day=1)
        ultimo_dia = (primeiro_dia + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        presencas = Presenca.objects.filter(
            funcionario=joao,
            data__gte=primeiro_dia,
            data__lte=ultimo_dia
        ).order_by('data')
        
        self.stdout.write(f'📅 PRESENÇAS EM SETEMBRO ({presencas.count()} registros):')
        for p in presencas:
            self.stdout.write(f'   {p.data.strftime("%d/%m")} - {p.tipo_presenca.nome}')
        
        self.stdout.write('')
        
        # Análise
        dias_uteis = funcionario_folha.calcular_dias_uteis_mes()
        self.stdout.write('🔍 ANÁLISE:')
        self.stdout.write(f'   • Dias úteis no mês: {dias_uteis}')
        self.stdout.write(f'   • Dias trabalhados: {funcionario_folha.dias_trabalhados}')
        self.stdout.write(f'   • Diferença: {dias_uteis - funcionario_folha.dias_trabalhados} dias')
        
        if funcionario_folha.dias_trabalhados < dias_uteis:
            self.stdout.write(f'   ⚠️  FUNCIONÁRIO TEM {dias_uteis - funcionario_folha.dias_trabalhados} DIA(S) A MENOS!')
            
            # Verificar se há desconto por faltas
            if funcionario_folha.desconto_faltas > 0:
                self.stdout.write(f'   ✅ Desconto por faltas aplicado: {funcionario_folha.desconto_faltas} MT')
            else:
                self.stdout.write(f'   ❌ PROBLEMA: Nenhum desconto por faltas aplicado!')
                
                # Verificar presenças que descontam
                presencas_faltas = presencas.filter(tipo_presenca__desconta_salario=True)
                self.stdout.write(f'   • Presenças que descontam: {presencas_faltas.count()}')
                
                if presencas_faltas.count() == 0:
                    self.stdout.write(f'   🔧 SOLUÇÃO: Marcar as faltas como tipo que desconta salário')
                    self.stdout.write(f'      Tipos que descontam: Ausente (AU), Falta Injustificada (FI), Suspensão (SU)')
        else:
            self.stdout.write(f'   ✅ Funcionário trabalhou todos os dias úteis')
        
        self.stdout.write('')
        self.stdout.write('🎯 DIAGNÓSTICO COMPLETO!')
