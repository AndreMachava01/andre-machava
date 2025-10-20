from django.core.management.base import BaseCommand
from meuprojeto.empresa.models_rh import (
    FolhaSalarial, Funcionario, FuncionarioFolha, 
    BeneficioSalarial, DescontoSalarial, BeneficioFolha, DescontoFolha
)
from datetime import date

class Command(BaseCommand):
    help = 'Demonstra como aplicar benefícios e descontos na folha de salário'

    def handle(self, *args, **options):
        self.stdout.write('=' * 80)
        self.stdout.write('🎁 DEMONSTRAÇÃO: APLICAÇÃO DE BENEFÍCIOS E DESCONTOS NA FOLHA')
        self.stdout.write('=' * 80)
        self.stdout.write('')
        
        # Buscar folha de setembro
        folha = FolhaSalarial.objects.filter(mes_referencia__year=2025, mes_referencia__month=9).first()
        
        if not folha:
            self.stdout.write('❌ Folha de setembro não encontrada')
            return
        
        self.stdout.write('📋 SISTEMA DE BENEFÍCIOS E DESCONTOS')
        self.stdout.write('=' * 50)
        self.stdout.write('')
        
        # 1. Mostrar benefícios disponíveis
        self.stdout.write('1️⃣ BENEFÍCIOS DISPONÍVEIS NO SISTEMA:')
        beneficios = BeneficioSalarial.objects.filter(ativo=True).order_by('nome')
        
        if beneficios.exists():
            for beneficio in beneficios:
                self.stdout.write(f'   🎁 {beneficio.nome} ({beneficio.codigo})')
                self.stdout.write(f'      • Tipo: {beneficio.get_tipo_display()}')
                self.stdout.write(f'      • Valor: {beneficio.valor} MT')
                self.stdout.write(f'      • Base: {beneficio.get_base_calculo_display()}')
                self.stdout.write('')
        else:
            self.stdout.write('   ⚠️  Nenhum benefício cadastrado')
            self.stdout.write('')
        
        # 2. Mostrar descontos disponíveis
        self.stdout.write('2️⃣ DESCONTOS DISPONÍVEIS NO SISTEMA:')
        descontos = DescontoSalarial.objects.filter(ativo=True).order_by('nome')
        
        if descontos.exists():
            for desconto in descontos:
                self.stdout.write(f'   💸 {desconto.nome} ({desconto.codigo})')
                self.stdout.write(f'      • Tipo: {desconto.get_tipo_display()}')
                self.stdout.write(f'      • Valor: {desconto.valor} MT')
                self.stdout.write(f'      • Base: {desconto.get_base_calculo_display()}')
                self.stdout.write('')
        else:
            self.stdout.write('   ⚠️  Nenhum desconto cadastrado')
            self.stdout.write('')
        
        # 3. Mostrar funcionários na folha
        self.stdout.write('3️⃣ FUNCIONÁRIOS NA FOLHA:')
        funcionarios_folha = folha.funcionarios_folha.all().order_by('funcionario__nome_completo')
        
        for func_folha in funcionarios_folha:
            self.stdout.write(f'   👤 {func_folha.funcionario.nome_completo}:')
            self.stdout.write(f'      • Salário Base: {func_folha.salario_base} MT')
            self.stdout.write(f'      • Salário Bruto: {func_folha.salario_bruto} MT')
            self.stdout.write(f'      • Salário Líquido: {func_folha.salario_liquido} MT')
            self.stdout.write(f'      • Total Benefícios: {func_folha.total_beneficios} MT')
            self.stdout.write(f'      • Total Descontos: {func_folha.total_descontos} MT')
            self.stdout.write('')
        
        # 4. Demonstrar aplicação de benefícios
        if beneficios.exists() and funcionarios_folha.exists():
            self.stdout.write('4️⃣ APLICANDO BENEFÍCIOS NA FOLHA:')
            
            # Pegar primeiro funcionário e primeiro benefício
            funcionario_folha = funcionarios_folha.first()
            beneficio = beneficios.first()
            
            # Verificar se já existe
            beneficio_existente = BeneficioFolha.objects.filter(
                funcionario_folha=funcionario_folha,
                beneficio=beneficio
            ).first()
            
            if not beneficio_existente:
                # Aplicar benefício
                BeneficioFolha.objects.create(
                    funcionario_folha=funcionario_folha,
                    beneficio=beneficio,
                    valor=beneficio.valor,
                    observacoes='Demonstração de aplicação de benefício'
                )
                
                # Recalcular salário
                funcionario_folha.calcular_salario()
                folha.calcular_totais()
                
                self.stdout.write(f'   ✅ Benefício "{beneficio.nome}" aplicado a {funcionario_folha.funcionario.nome_completo}')
                self.stdout.write(f'      • Valor aplicado: {beneficio.valor} MT')
                self.stdout.write(f'      • Novo salário bruto: {funcionario_folha.salario_bruto} MT')
                self.stdout.write(f'      • Novo salário líquido: {funcionario_folha.salario_liquido} MT')
            else:
                self.stdout.write(f'   ℹ️  Benefício "{beneficio.nome}" já aplicado a {funcionario_folha.funcionario.nome_completo}')
                self.stdout.write(f'      • Valor atual: {beneficio_existente.valor} MT')
            
            self.stdout.write('')
        
        # 5. Demonstrar aplicação de descontos
        if descontos.exists() and funcionarios_folha.exists():
            self.stdout.write('5️⃣ APLICANDO DESCONTOS NA FOLHA:')
            
            # Pegar primeiro funcionário e primeiro desconto
            funcionario_folha = funcionarios_folha.first()
            desconto = descontos.first()
            
            # Verificar se já existe
            desconto_existente = DescontoFolha.objects.filter(
                funcionario_folha=funcionario_folha,
                desconto=desconto
            ).first()
            
            if not desconto_existente:
                # Aplicar desconto
                DescontoFolha.objects.create(
                    funcionario_folha=funcionario_folha,
                    desconto=desconto,
                    valor=desconto.valor,
                    observacoes='Demonstração de aplicação de desconto'
                )
                
                # Recalcular salário
                funcionario_folha.calcular_salario()
                folha.calcular_totais()
                
                self.stdout.write(f'   ✅ Desconto "{desconto.nome}" aplicado a {funcionario_folha.funcionario.nome_completo}')
                self.stdout.write(f'      • Valor aplicado: {desconto.valor} MT')
                self.stdout.write(f'      • Novo salário bruto: {funcionario_folha.salario_bruto} MT')
                self.stdout.write(f'      • Novo salário líquido: {funcionario_folha.salario_liquido} MT')
            else:
                self.stdout.write(f'   ℹ️  Desconto "{desconto.nome}" já aplicado a {funcionario_folha.funcionario.nome_completo}')
                self.stdout.write(f'      • Valor atual: {desconto_existente.valor} MT')
            
            self.stdout.write('')
        
        # 6. Mostrar benefícios e descontos aplicados na folha
        self.stdout.write('6️⃣ BENEFÍCIOS E DESCONTOS APLICADOS NA FOLHA:')
        
        # Benefícios aplicados
        beneficios_folha = BeneficioFolha.objects.filter(
            funcionario_folha__folha=folha
        ).select_related('funcionario_folha__funcionario', 'beneficio')
        
        if beneficios_folha.exists():
            self.stdout.write('   🎁 BENEFÍCIOS:')
            for bf in beneficios_folha:
                self.stdout.write(f'      • {bf.funcionario_folha.funcionario.nome_completo}: {bf.beneficio.nome} = {bf.valor} MT')
        else:
            self.stdout.write('   ℹ️  Nenhum benefício aplicado na folha')
        
        # Descontos aplicados
        descontos_folha = DescontoFolha.objects.filter(
            funcionario_folha__folha=folha
        ).select_related('funcionario_folha__funcionario', 'desconto')
        
        if descontos_folha.exists():
            self.stdout.write('   💸 DESCONTOS:')
            for df in descontos_folha:
                self.stdout.write(f'      • {df.funcionario_folha.funcionario.nome_completo}: {df.desconto.nome} = {df.valor} MT')
        else:
            self.stdout.write('   ℹ️  Nenhum desconto aplicado na folha')
        
        self.stdout.write('')
        
        # 7. Resumo final da folha
        self.stdout.write('7️⃣ RESUMO FINAL DA FOLHA:')
        folha.calcular_totais()  # Recalcular para ter dados atualizados
        
        self.stdout.write(f'   • Mês: {folha.mes_referencia.strftime("%B/%Y")}')
        self.stdout.write(f'   • Status: {folha.get_status_display()}')
        self.stdout.write(f'   • Total Funcionários: {folha.total_funcionarios}')
        self.stdout.write(f'   • Total Bruto: {folha.total_bruto} MT')
        self.stdout.write(f'   • Total Descontos: {folha.total_descontos} MT')
        self.stdout.write(f'   • Total Líquido: {folha.total_liquido} MT')
        self.stdout.write('')
        
        # 8. Como usar o sistema
        self.stdout.write('8️⃣ COMO USAR O SISTEMA:')
        self.stdout.write('')
        
        self.stdout.write('   📋 GESTÃO DE BENEFÍCIOS E DESCONTOS:')
        self.stdout.write('      1. Acesse: /rh/salarios/beneficios/ (para benefícios)')
        self.stdout.write('      2. Acesse: /rh/salarios/descontos/ (para descontos)')
        self.stdout.write('      3. Cadastre os benefícios/descontos que serão usados')
        self.stdout.write('')
        
        self.stdout.write('   🎯 APLICAÇÃO NA FOLHA:')
        self.stdout.write('      1. Acesse a folha: /rh/folha-salarial/detalhes/<id>/')
        self.stdout.write('      2. Clique em "Benefícios" ou "Descontos"')
        self.stdout.write('      3. Selecione o funcionário e o benefício/desconto')
        self.stdout.write('      4. Defina o valor e observações')
        self.stdout.write('      5. O sistema recalcula automaticamente')
        self.stdout.write('')
        
        self.stdout.write('   🔄 FLUXO AUTOMÁTICO:')
        self.stdout.write('      1. Benefício/Desconto é aplicado na folha')
        self.stdout.write('      2. FuncionarioFolha.calcular_salario() é chamado')
        self.stdout.write('      3. Salário bruto = base + benefícios')
        self.stdout.write('      4. Salário líquido = bruto - descontos')
        self.stdout.write('      5. Totais da folha são recalculados')
        self.stdout.write('')
        
        # 9. URLs disponíveis
        self.stdout.write('9️⃣ URLs DISPONÍVEIS:')
        self.stdout.write('')
        
        self.stdout.write('   🎁 BENEFÍCIOS:')
        self.stdout.write('      • Lista: /rh/salarios/beneficios/')
        self.stdout.write('      • Adicionar: /rh/salarios/beneficios/adicionar/')
        self.stdout.write('      • Editar: /rh/salarios/beneficios/editar/<id>/')
        self.stdout.write('      • Deletar: /rh/salarios/beneficios/excluir/<id>/')
        self.stdout.write('')
        
        self.stdout.write('   💸 DESCONTOS:')
        self.stdout.write('      • Lista: /rh/salarios/descontos/')
        self.stdout.write('      • Adicionar: /rh/salarios/descontos/adicionar/')
        self.stdout.write('      • Editar: /rh/salarios/descontos/editar/<id>/')
        self.stdout.write('      • Deletar: /rh/salarios/descontos/excluir/<id>/')
        self.stdout.write('')
        
        self.stdout.write('   📊 NA FOLHA:')
        self.stdout.write('      • Benefícios: /rh/folha-salarial/beneficios/<folha_id>/')
        self.stdout.write('      • Descontos: /rh/folha-salarial/descontos/<folha_id>/')
        self.stdout.write('')
        
        self.stdout.write('🎉 SISTEMA DE BENEFÍCIOS E DESCONTOS FUNCIONANDO!')
        self.stdout.write('')
        self.stdout.write('✅ O sistema permite:')
        self.stdout.write('   • Cadastrar benefícios e descontos')
        self.stdout.write('   • Aplicar na folha de salário')
        self.stdout.write('   • Cálculo automático')
        self.stdout.write('   • Gestão completa via interface')
        self.stdout.write('   • Histórico e auditoria')
