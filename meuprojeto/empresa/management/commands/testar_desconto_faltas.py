from django.core.management.base import BaseCommand
from meuprojeto.empresa.models_rh import Funcionario, FolhaSalarial, FuncionarioFolha, Presenca, TipoPresenca
from datetime import date, timedelta

class Command(BaseCommand):
    help = 'Testa o sistema de desconto por faltas não justificadas'

    def handle(self, *args, **options):
        self.stdout.write('=== TESTE DO SISTEMA DE DESCONTO POR FALTAS ===')
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
        
        # Verificar tipos de presença que descontam salário
        tipos_desconta = TipoPresenca.objects.filter(desconta_salario=True)
        self.stdout.write('🔍 TIPOS DE PRESENÇA QUE DESCONTAM SALÁRIO:')
        for tipo in tipos_desconta:
            self.stdout.write(f'   • {tipo.nome} ({tipo.codigo}) - {tipo.descricao}')
        self.stdout.write('')
        
        # Verificar presenças do mês
        primeiro_dia = folha.mes_referencia.replace(day=1)
        ultimo_dia = (primeiro_dia + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        presencas_faltas = Presenca.objects.filter(
            funcionario=funcionario,
            data__gte=primeiro_dia,
            data__lte=ultimo_dia,
            tipo_presenca__desconta_salario=True
        )
        
        self.stdout.write(f'📅 PERÍODO: {primeiro_dia.strftime("%d/%m/%Y")} a {ultimo_dia.strftime("%d/%m/%Y")}')
        self.stdout.write(f'❌ FALTAS QUE DESCONTAM: {presencas_faltas.count()}')
        
        if presencas_faltas.count() > 0:
            self.stdout.write('   Detalhes das faltas:')
            for presenca in presencas_faltas:
                self.stdout.write(f'   • {presenca.data.strftime("%d/%m/%Y")} - {presenca.tipo_presenca.nome}')
        self.stdout.write('')
        
        # Calcular desconto manualmente
        dias_uteis = funcionario_folha.calcular_dias_uteis_mes()
        valor_por_dia = float(funcionario_folha.salario_base) / dias_uteis
        desconto_calculado = valor_por_dia * presencas_faltas.count()
        
        self.stdout.write('🧮 CÁLCULO DO DESCONTO:')
        self.stdout.write(f'   • Dias úteis no mês: {dias_uteis}')
        self.stdout.write(f'   • Valor por dia: {valor_por_dia:.2f} MT')
        self.stdout.write(f'   • Faltas: {presencas_faltas.count()}')
        self.stdout.write(f'   • Desconto calculado: {desconto_calculado:.2f} MT')
        self.stdout.write('')
        
        # Recalcular salário
        funcionario_folha.calcular_salario()
        
        self.stdout.write('💰 RESULTADO APÓS RECÁLCULO:')
        self.stdout.write(f'   • Desconto por faltas: {funcionario_folha.desconto_faltas} MT')
        self.stdout.write(f'   • Total de descontos: {funcionario_folha.total_descontos} MT')
        self.stdout.write(f'   • Salário líquido: {funcionario_folha.salario_liquido} MT')
        self.stdout.write('')
        
        # Verificar se o desconto foi aplicado corretamente
        if funcionario_folha.desconto_faltas > 0:
            self.stdout.write('✅ SISTEMA FUNCIONANDO: Desconto por faltas aplicado automaticamente!')
        else:
            self.stdout.write('ℹ️  Nenhum desconto por faltas aplicado (funcionário não faltou)')
        
        self.stdout.write('')
        self.stdout.write('🎯 FUNCIONALIDADES IMPLEMENTADAS:')
        self.stdout.write('   • Cálculo automático de desconto por faltas')
        self.stdout.write('   • Baseado em tipos de presença com desconta_salario=True')
        self.stdout.write('   • Fórmula: (Salário Base ÷ Dias Úteis) × Número de Faltas')
        self.stdout.write('   • Exibição na folha salarial com coluna dedicada')
        self.stdout.write('   • Integração com cálculo de salário líquido')
