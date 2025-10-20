from django.core.management.base import BaseCommand
from meuprojeto.empresa.models_rh import Funcionario, Presenca, TipoPresenca, FuncionarioFolha, FolhaSalarial
from datetime import date

class Command(BaseCommand):
    help = 'Verifica por que falta não justificada não está descontando salário'

    def handle(self, *args, **options):
        self.stdout.write('=== VERIFICAÇÃO: FALTA NÃO JUSTIFICADA ===')
        self.stdout.write('')
        
        # Buscar João Silva
        joao = Funcionario.objects.filter(nome_completo__icontains='joao silva').first()
        if not joao:
            self.stdout.write('❌ João Silva não encontrado')
            return
        
        self.stdout.write(f'📋 FUNCIONÁRIO: {joao.nome_completo}')
        self.stdout.write('')
        
        # Buscar presenças de falta não justificada
        presencas_fi = Presenca.objects.filter(
            funcionario=joao,
            data__year=2025,
            data__month=9,
            tipo_presenca__codigo='FI'
        )
        
        self.stdout.write(f'❌ PRESENÇAS FALTA INJUSTIFICADA: {presencas_fi.count()}')
        for p in presencas_fi:
            self.stdout.write(f'   {p.data.strftime("%d/%m")} - {p.tipo_presenca.nome} (desconta: {p.tipo_presenca.desconta_salario})')
        self.stdout.write('')
        
        # Verificar se o tipo FI desconta salário
        tipo_fi = TipoPresenca.objects.filter(codigo='FI').first()
        if tipo_fi:
            self.stdout.write(f'🔍 TIPO FALTA INJUSTIFICADA:')
            self.stdout.write(f'   • Nome: {tipo_fi.nome}')
            self.stdout.write(f'   • Código: {tipo_fi.codigo}')
            self.stdout.write(f'   • Desconta salário: {tipo_fi.desconta_salario}')
            self.stdout.write(f'   • Ativo: {tipo_fi.ativo}')
        else:
            self.stdout.write('❌ Tipo Falta Injustificada não encontrado!')
        self.stdout.write('')
        
        # Verificar folha salarial
        folha = FolhaSalarial.objects.filter(mes_referencia__year=2025, mes_referencia__month=9).first()
        if not folha:
            self.stdout.write('❌ Folha de setembro não encontrada')
            return
        
        funcionario_folha = FuncionarioFolha.objects.filter(folha=folha, funcionario=joao).first()
        if not funcionario_folha:
            self.stdout.write('❌ Funcionário não encontrado na folha')
            return
        
        self.stdout.write('💰 DADOS DA FOLHA:')
        self.stdout.write(f'   • Salário Base: {funcionario_folha.salario_base} MT')
        self.stdout.write(f'   • Desconto por faltas: {funcionario_folha.desconto_faltas} MT')
        self.stdout.write(f'   • Total descontos: {funcionario_folha.total_descontos} MT')
        self.stdout.write(f'   • Salário líquido: {funcionario_folha.salario_liquido} MT')
        self.stdout.write('')
        
        # Recalcular salário para ver se aplica desconto
        self.stdout.write('🔄 RECALCULANDO SALÁRIO...')
        funcionario_folha.calcular_salario()
        
        self.stdout.write('💰 APÓS RECÁLCULO:')
        self.stdout.write(f'   • Desconto por faltas: {funcionario_folha.desconto_faltas} MT')
        self.stdout.write(f'   • Total descontos: {funcionario_folha.total_descontos} MT')
        self.stdout.write(f'   • Salário líquido: {funcionario_folha.salario_liquido} MT')
        self.stdout.write('')
        
        # Verificar presenças que descontam salário
        presencas_desconta = Presenca.objects.filter(
            funcionario=joao,
            data__year=2025,
            data__month=9,
            tipo_presenca__desconta_salario=True
        )
        
        self.stdout.write(f'🔍 PRESENÇAS QUE DESCONTAM SALÁRIO: {presencas_desconta.count()}')
        for p in presencas_desconta:
            self.stdout.write(f'   {p.data.strftime("%d/%m")} - {p.tipo_presenca.nome} (desconta: {p.tipo_presenca.desconta_salario})')
        self.stdout.write('')
        
        # Diagnóstico
        if presencas_fi.count() > 0 and funcionario_folha.desconto_faltas == 0:
            self.stdout.write('❌ PROBLEMA IDENTIFICADO:')
            self.stdout.write('   • Há falta não justificada registrada')
            self.stdout.write('   • Mas não há desconto aplicado')
            self.stdout.write('   • Verificar se o tipo FI está configurado para desconta_salario=True')
        elif presencas_fi.count() == 0:
            self.stdout.write('ℹ️  NENHUMA FALTA NÃO JUSTIFICADA ENCONTRADA')
            self.stdout.write('   • Verificar se a falta está marcada corretamente no calendário')
        else:
            self.stdout.write('✅ SISTEMA FUNCIONANDO CORRETAMENTE')
            self.stdout.write('   • Faltas estão sendo descontadas')
        
        self.stdout.write('')
        self.stdout.write('🎯 VERIFICAÇÃO CONCLUÍDA!')
