from django.core.management.base import BaseCommand
from meuprojeto.empresa.models_rh import Funcionario, Presenca, TipoPresenca, FuncionarioFolha, FolhaSalarial
from datetime import date
import calendar

class Command(BaseCommand):
    help = 'Investiga por que João Silva não tem desconto por faltas'

    def handle(self, *args, **options):
        self.stdout.write('=== INVESTIGAÇÃO: FALTAS DO JOÃO SILVA ===')
        self.stdout.write('')
        
        joao = Funcionario.objects.filter(nome_completo__icontains='joao silva').first()
        folha = FolhaSalarial.objects.filter(mes_referencia__year=2025, mes_referencia__month=9).first()
        funcionario_folha = FuncionarioFolha.objects.filter(folha=folha, funcionario=joao).first()
        
        self.stdout.write(f'📋 FUNCIONÁRIO: {joao.nome_completo}')
        self.stdout.write(f'💰 Salário Base: {funcionario_folha.salario_base} MT')
        self.stdout.write(f'📊 Dias Trabalhados: {funcionario_folha.dias_trabalhados}')
        self.stdout.write(f'💸 Desconto por Faltas: {funcionario_folha.desconto_faltas} MT')
        self.stdout.write('')
        
        # Verificar presenças que descontam salário
        presencas_faltas = Presenca.objects.filter(
            funcionario=joao,
            data__year=2025,
            data__month=9,
            tipo_presenca__desconta_salario=True
        )
        
        self.stdout.write(f'❌ PRESENÇAS QUE DESCONTAM SALÁRIO: {presencas_faltas.count()}')
        for p in presencas_faltas:
            self.stdout.write(f'   {p.data.strftime("%d/%m")} - {p.tipo_presenca.nome}')
        self.stdout.write('')
        
        # Verificar todos os tipos de presença
        self.stdout.write('🔍 TIPOS DE PRESENÇA:')
        for tipo in TipoPresenca.objects.all():
            self.stdout.write(f'   {tipo.codigo}: {tipo.nome} (desconta: {tipo.desconta_salario})')
        self.stdout.write('')
        
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
        
        dias_sem_presenca = [d for d in dias_uteis if d not in presencas_existentes]
        
        self.stdout.write('📅 ANÁLISE DE DIAS:')
        self.stdout.write(f'   • Dias úteis: {len(dias_uteis)}')
        self.stdout.write(f'   • Dias com presença: {len([d for d in dias_uteis if d in presencas_existentes])}')
        self.stdout.write(f'   • Dias sem presença: {len(dias_sem_presenca)}')
        self.stdout.write('')
        
        if len(dias_sem_presenca) > 0:
            self.stdout.write('❌ DIAS ÚTEIS SEM PRESENÇA:')
            for d in dias_sem_presenca:
                self.stdout.write(f'   {d.strftime("%d/%m")} - {d.strftime("%A")}')
            self.stdout.write('')
            self.stdout.write('🔧 SOLUÇÃO: Criar presenças de falta para estes dias')
        else:
            self.stdout.write('✅ TODOS OS DIAS ÚTEIS TÊM PRESENÇA REGISTRADA')
            self.stdout.write('')
            self.stdout.write('🤔 PERGUNTA: Se não há dias faltantes, por que o usuário diz que há falta?')
            self.stdout.write('   • Verificar se há presenças marcadas como tipo que NÃO desconta')
            self.stdout.write('   • Verificar se há presenças marcadas incorretamente')
        
        # Verificar presenças detalhadas
        self.stdout.write('📋 TODAS AS PRESENÇAS:')
        presencas = Presenca.objects.filter(
            funcionario=joao,
            data__year=2025,
            data__month=9
        ).order_by('data')
        
        for p in presencas:
            self.stdout.write(f'   {p.data.strftime("%d/%m")} - {p.tipo_presenca.nome} (desconta: {p.tipo_presenca.desconta_salario})')
        
        self.stdout.write('')
        self.stdout.write('🎯 INVESTIGAÇÃO CONCLUÍDA!')
