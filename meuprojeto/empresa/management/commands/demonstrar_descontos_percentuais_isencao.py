from django.core.management.base import BaseCommand
from meuprojeto.empresa.models_rh import (
    FolhaSalarial, Funcionario, FuncionarioFolha, 
    DescontoSalarial, DescontoFolha
)
from decimal import Decimal

class Command(BaseCommand):
    help = 'Demonstra o sistema de descontos percentuais e isenções'

    def handle(self, *args, **options):
        self.stdout.write('=' * 80)
        self.stdout.write('💰 DEMONSTRAÇÃO: DESCONTOS PERCENTUAIS E ISENÇÕES')
        self.stdout.write('=' * 80)
        self.stdout.write('')
        
        # 1. Configurar descontos automáticos
        self.stdout.write('1️⃣ CONFIGURANDO DESCONTOS AUTOMÁTICOS:')
        self.stdout.write('')
        
        # INSS - 3% fixo, sem isenção
        inss, created = DescontoSalarial.objects.get_or_create(
            codigo='IN001',
            defaults={
                'nome': 'INSS Moçambique',
                'tipo': 'IN',
                'tipo_valor': 'PERCENTUAL',
                'valor': 3.00,  # 3%
                'base_calculo': 'SALARIO_BRUTO',
                'valor_minimo_isencao': 0.00,  # Sem isenção
                'aplicar_automaticamente': True,
                'ativo': True,
                'observacoes': 'Contribuição para a Segurança Social - 3% sobre salário bruto'
            }
        )
        
        if created:
            self.stdout.write(f'   ✅ INSS criado: {inss.nome}')
        else:
            self.stdout.write(f'   ℹ️  INSS já existe: {inss.nome}')
        
        # IRPS - 5% sobre salário bruto, isento até 19.000 MT
        irps, created = DescontoSalarial.objects.get_or_create(
            codigo='IR001',
            defaults={
                'nome': 'IRPS (Imposto de Renda)',
                'tipo': 'IR',
                'tipo_valor': 'PERCENTUAL',
                'valor': 5.00,  # 5%
                'base_calculo': 'SALARIO_BRUTO',
                'valor_minimo_isencao': 19000.00,  # Isento até 19.000 MT
                'aplicar_automaticamente': True,
                'ativo': True,
                'observacoes': 'Imposto de Renda sobre Pessoas Singulares - 5% sobre salário bruto, isento até 19.000 MT'
            }
        )
        
        if created:
            self.stdout.write(f'   ✅ IRPS criado: {irps.nome}')
        else:
            self.stdout.write(f'   ℹ️  IRPS já existe: {irps.nome}')
        
        # Desconto adicional - 2% sobre salário base, isento até 15.000 MT
        desconto_adicional, created = DescontoSalarial.objects.get_or_create(
            codigo='AD001',
            defaults={
                'nome': 'Desconto Adicional',
                'tipo': 'OU',
                'tipo_valor': 'PERCENTUAL',
                'valor': 2.00,  # 2%
                'base_calculo': 'SALARIO_BASE',
                'valor_minimo_isencao': 15000.00,  # Isento até 15.000 MT
                'aplicar_automaticamente': True,
                'ativo': True,
                'observacoes': 'Desconto adicional - 2% sobre salário base, isento até 15.000 MT'
            }
        )
        
        if created:
            self.stdout.write(f'   ✅ Desconto Adicional criado: {desconto_adicional.nome}')
        else:
            self.stdout.write(f'   ℹ️  Desconto Adicional já existe: {desconto_adicional.nome}')
        
        self.stdout.write('')
        
        # 2. Mostrar descontos configurados
        self.stdout.write('2️⃣ DESCONTOS CONFIGURADOS:')
        descontos = DescontoSalarial.objects.filter(ativo=True, aplicar_automaticamente=True)
        
        for desconto in descontos:
            self.stdout.write(f'   💸 {desconto.nome} ({desconto.codigo})')
            self.stdout.write(f'      • Tipo: {desconto.get_tipo_display()}')
            self.stdout.write(f'      • Valor: {desconto.valor}% (percentual)')
            self.stdout.write(f'      • Base: {desconto.get_base_calculo_display()}')
            self.stdout.write(f'      • Isenção: {desconto.get_descricao_isencao()}')
            self.stdout.write('')
        
        # 3. Buscar folha de setembro
        folha = FolhaSalarial.objects.filter(mes_referencia__year=2025, mes_referencia__month=9).first()
        
        if not folha:
            self.stdout.write('❌ Folha de setembro não encontrada')
            return
        
        self.stdout.write('3️⃣ FUNCIONÁRIOS NA FOLHA:')
        funcionarios_folha = folha.funcionarios_folha.all().order_by('funcionario__nome_completo')
        
        for func_folha in funcionarios_folha:
            self.stdout.write(f'   👤 {func_folha.funcionario.nome_completo}:')
            self.stdout.write(f'      • Salário Base: {func_folha.salario_base} MT')
            self.stdout.write(f'      • Salário Bruto: {func_folha.salario_bruto} MT')
            self.stdout.write('')
        
        # 4. Demonstrar cálculo de descontos para diferentes salários
        self.stdout.write('4️⃣ DEMONSTRAÇÃO DE CÁLCULO DE DESCONTOS:')
        self.stdout.write('')
        
        # Testar com diferentes valores de salário
        valores_teste = [10000, 15000, 19000, 25000, 50000]
        
        for salario_bruto in valores_teste:
            self.stdout.write(f'   💰 SALÁRIO BRUTO: {salario_bruto} MT')
            self.stdout.write('   ' + '-' * 50)
            
            total_descontos = Decimal('0.00')
            
            for desconto in descontos:
                # Calcular valor do desconto
                valor_desconto = desconto.calcular_valor_desconto(
                    salario_bruto,  # Usando salário bruto como base
                    salario_bruto,
                    salario_bruto
                )
                
                deve_aplicar = desconto.deve_aplicar_desconto(salario_bruto)
                
                if deve_aplicar and valor_desconto > 0:
                    self.stdout.write(f'      ✅ {desconto.nome}: {valor_desconto} MT')
                    total_descontos += valor_desconto
                else:
                    self.stdout.write(f'      ❌ {desconto.nome}: ISENTO ({desconto.get_descricao_isencao()})')
            
            salario_liquido = salario_bruto - total_descontos
            self.stdout.write(f'      💸 Total Descontos: {total_descontos} MT')
            self.stdout.write(f'      💵 Salário Líquido: {salario_liquido} MT')
            self.stdout.write('')
        
        # 5. Aplicar descontos automáticos na folha
        self.stdout.write('5️⃣ APLICANDO DESCONTOS AUTOMÁTICOS NA FOLHA:')
        self.stdout.write('')
        
        for func_folha in funcionarios_folha:
            self.stdout.write(f'   👤 {func_folha.funcionario.nome_completo}:')
            
            # Recalcular salário para aplicar descontos automáticos
            func_folha.calcular_salario()
            
            # Buscar descontos aplicados
            descontos_aplicados = DescontoFolha.objects.filter(funcionario_folha=func_folha)
            
            if descontos_aplicados.exists():
                for desconto_folha in descontos_aplicados:
                    self.stdout.write(f'      💸 {desconto_folha.desconto.nome}: {desconto_folha.valor} MT')
                    if 'automático' in desconto_folha.observacoes:
                        self.stdout.write(f'         (Aplicado automaticamente)')
            else:
                self.stdout.write(f'      ℹ️  Nenhum desconto aplicado')
            
            self.stdout.write(f'      💵 Salário Líquido: {func_folha.salario_liquido} MT')
            self.stdout.write('')
        
        # 6. Recalcular totais da folha
        self.stdout.write('6️⃣ RECALCULANDO TOTAIS DA FOLHA:')
        folha.calcular_totais()
        
        self.stdout.write(f'   • Total Bruto: {folha.total_bruto} MT')
        self.stdout.write(f'   • Total Descontos: {folha.total_descontos} MT')
        self.stdout.write(f'   • Total Líquido: {folha.total_liquido} MT')
        self.stdout.write('')
        
        # 7. Resumo das regras implementadas
        self.stdout.write('7️⃣ RESUMO DAS REGRAS IMPLEMENTADAS:')
        self.stdout.write('')
        
        self.stdout.write('   📋 DESCONTOS AUTOMÁTICOS:')
        self.stdout.write('      • INSS: 3% sobre salário bruto (sem isenção)')
        self.stdout.write('      • IRPS: 5% sobre salário bruto (isento até 19.000 MT)')
        self.stdout.write('      • Desconto Adicional: 2% sobre salário base (isento até 15.000 MT)')
        self.stdout.write('')
        
        self.stdout.write('   🔄 FLUXO AUTOMÁTICO:')
        self.stdout.write('      1. FuncionarioFolha.calcular_salario() é chamado')
        self.stdout.write('      2. Salário bruto é calculado (base + benefícios)')
        self.stdout.write('      3. Descontos automáticos são aplicados baseados nas regras')
        self.stdout.write('      4. Verificação de isenções é feita automaticamente')
        self.stdout.write('      5. Descontos são criados na tabela DescontoFolha')
        self.stdout.write('      6. Salário líquido é calculado')
        self.stdout.write('')
        
        self.stdout.write('   ⚙️ CONFIGURAÇÃO:')
        self.stdout.write('      • Acesse: /admin/empresa/descontosalarial/')
        self.stdout.write('      • Marque "Aplicar Automaticamente" para descontos automáticos')
        self.stdout.write('      • Configure "Valor Mínimo para Isenção" para regras de isenção')
        self.stdout.write('      • Use "Base de Cálculo" para definir sobre o que calcular')
        self.stdout.write('')
        
        self.stdout.write('🎉 SISTEMA DE DESCONTOS PERCENTUAIS E ISENÇÕES FUNCIONANDO!')
        self.stdout.write('')
        self.stdout.write('✅ O sistema permite:')
        self.stdout.write('   • Descontos percentuais automáticos')
        self.stdout.write('   • Regras de isenção por faixa salarial')
        self.stdout.write('   • Diferentes bases de cálculo')
        self.stdout.write('   • Aplicação automática na folha')
        self.stdout.write('   • Cálculo correto do IRPS para salários acima de 19.000 MT')
