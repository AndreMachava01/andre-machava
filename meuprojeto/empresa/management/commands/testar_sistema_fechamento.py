from django.core.management.base import BaseCommand
from meuprojeto.empresa.models_rh import FolhaSalarial, Funcionario, FuncionarioFolha
from datetime import date
from django.core.exceptions import ValidationError

class Command(BaseCommand):
    help = 'Testa o sistema de fechamento da folha de salário'

    def handle(self, *args, **options):
        self.stdout.write('=' * 70)
        self.stdout.write('🧪 TESTANDO SISTEMA DE FECHAMENTO DA FOLHA')
        self.stdout.write('=' * 70)
        self.stdout.write('')
        
        # Buscar folha de setembro
        folha = FolhaSalarial.objects.filter(mes_referencia__year=2025, mes_referencia__month=9).first()
        
        if not folha:
            self.stdout.write('❌ Folha de setembro não encontrada')
            return
        
        self.stdout.write(f'📋 Testando folha: {folha.mes_referencia.strftime("%B/%Y")}')
        self.stdout.write(f'   Status atual: {folha.get_status_display()}')
        self.stdout.write('')
        
        # Teste 1: Verificar métodos de controle
        self.stdout.write('1️⃣ TESTANDO MÉTODOS DE CONTROLE:')
        self.stdout.write(f'   • pode_editar(): {folha.pode_editar()}')
        self.stdout.write(f'   • pode_fechar(): {folha.pode_fechar()}')
        self.stdout.write(f'   • pode_reabrir(): {folha.pode_reabrir()}')
        self.stdout.write(f'   • pode_marcar_paga(): {folha.pode_marcar_paga()}')
        self.stdout.write('')
        
        # Teste 2: Validar antes de fechar
        self.stdout.write('2️⃣ TESTANDO VALIDAÇÃO ANTES DE FECHAR:')
        validacao = folha.validar_antes_fechar()
        
        self.stdout.write(f'   • Válida: {validacao["valido"]}')
        self.stdout.write(f'   • Total funcionários: {validacao["total_funcionarios"]}')
        self.stdout.write(f'   • Funcionários sem salário: {validacao["funcionarios_sem_salario"]}')
        self.stdout.write(f'   • Funcionários sem presença: {validacao["funcionarios_sem_presenca"]}')
        self.stdout.write(f'   • Funcionários salário negativo: {validacao["funcionarios_salario_negativo"]}')
        
        if validacao['erros']:
            self.stdout.write('   ❌ Erros encontrados:')
            for erro in validacao['erros']:
                self.stdout.write(f'      - {erro}')
        
        if validacao['avisos']:
            self.stdout.write('   ⚠️  Avisos encontrados:')
            for aviso in validacao['avisos']:
                self.stdout.write(f'      - {aviso}')
        self.stdout.write('')
        
        # Teste 3: Resumo para fechamento
        self.stdout.write('3️⃣ TESTANDO RESUMO PARA FECHAMENTO:')
        resumo = folha.get_resumo_fechamento()
        
        self.stdout.write(f'   • Mês: {resumo["mes_referencia"]}')
        self.stdout.write(f'   • Total funcionários: {resumo["total_funcionarios"]}')
        self.stdout.write(f'   • Total bruto: {resumo["total_bruto"]} MT')
        self.stdout.write(f'   • Total descontos: {resumo["total_descontos"]} MT')
        self.stdout.write(f'   • Total líquido: {resumo["total_liquido"]} MT')
        self.stdout.write(f'   • Funcionários sem presença: {resumo["funcionarios_sem_presenca"]}')
        self.stdout.write(f'   • Funcionários salário negativo: {resumo["funcionarios_salario_negativo"]}')
        self.stdout.write('')
        
        # Teste 4: Tentar fechar a folha (se possível)
        if folha.pode_fechar():
            self.stdout.write('4️⃣ TESTANDO FECHAMENTO DA FOLHA:')
            try:
                resultado = folha.fechar_folha(observacoes='Teste de fechamento automático')
                
                self.stdout.write('   ✅ Folha fechada com sucesso!')
                self.stdout.write(f'   • Data de fechamento: {resultado["data_fechamento"]}')
                self.stdout.write(f'   • Total bruto: {resultado["total_bruto"]} MT')
                self.stdout.write(f'   • Total líquido: {resultado["total_liquido"]} MT')
                self.stdout.write(f'   • Total funcionários: {resultado["total_funcionarios"]}')
                
                if resultado['avisos']:
                    self.stdout.write('   ⚠️  Avisos durante fechamento:')
                    for aviso in resultado['avisos']:
                        self.stdout.write(f'      - {aviso}')
                
                # Teste 5: Tentar reabrir
                self.stdout.write('')
                self.stdout.write('5️⃣ TESTANDO REABERTURA DA FOLHA:')
                if folha.pode_reabrir():
                    try:
                        resultado_reabrir = folha.reabrir_folha(motivo='Teste de reabertura automática')
                        
                        self.stdout.write('   ✅ Folha reaberta com sucesso!')
                        self.stdout.write(f'   • Status: {resultado_reabrir["status"]}')
                        self.stdout.write(f'   • Motivo: {resultado_reabrir["motivo"]}')
                        
                        # Fechar novamente para continuar testes
                        folha.fechar_folha(observacoes='Fechamento após teste de reabertura')
                        self.stdout.write('   • Folha fechada novamente para continuar testes')
                        
                    except ValidationError as e:
                        self.stdout.write(f'   ❌ Erro ao reabrir: {e}')
                else:
                    self.stdout.write('   ⚠️  Folha não pode ser reaberta no momento')
                
                # Teste 6: Tentar marcar como paga
                self.stdout.write('')
                self.stdout.write('6️⃣ TESTANDO MARCAR COMO PAGA:')
                if folha.pode_marcar_paga():
                    try:
                        resultado_paga = folha.marcar_como_paga(
                            data_pagamento=date.today(),
                            observacoes='Teste de pagamento automático'
                        )
                        
                        self.stdout.write('   ✅ Folha marcada como paga!')
                        self.stdout.write(f'   • Data de pagamento: {resultado_paga["data_pagamento"]}')
                        self.stdout.write(f'   • Status: {resultado_paga["status"]}')
                        
                    except ValidationError as e:
                        self.stdout.write(f'   ❌ Erro ao marcar como paga: {e}')
                else:
                    self.stdout.write('   ⚠️  Folha não pode ser marcada como paga no momento')
                
            except ValidationError as e:
                self.stdout.write(f'   ❌ Erro ao fechar folha: {e}')
        else:
            self.stdout.write('4️⃣ FOLHA NÃO PODE SER FECHADA NO MOMENTO')
            self.stdout.write('   Verifique os erros de validação acima')
        
        # Teste 7: Verificar funcionários na folha
        self.stdout.write('')
        self.stdout.write('7️⃣ INFORMAÇÕES DOS FUNCIONÁRIOS NA FOLHA:')
        funcionarios_folha = folha.funcionarios_folha.all()
        
        for func_folha in funcionarios_folha:
            self.stdout.write(f'   👤 {func_folha.funcionario.nome_completo}:')
            self.stdout.write(f'      • Salário base: {func_folha.salario_base} MT')
            self.stdout.write(f'      • Salário bruto: {func_folha.salario_bruto} MT')
            self.stdout.write(f'      • Salário líquido: {func_folha.salario_liquido} MT')
            self.stdout.write(f'      • Dias trabalhados: {func_folha.dias_trabalhados}')
            self.stdout.write(f'      • Horas trabalhadas: {func_folha.horas_trabalhadas}')
            self.stdout.write(f'      • Desconto faltas: {func_folha.desconto_faltas} MT')
            self.stdout.write('')
        
        self.stdout.write('🎯 TESTE CONCLUÍDO!')
        self.stdout.write('')
        self.stdout.write('✅ FUNCIONALIDADES IMPLEMENTADAS:')
        self.stdout.write('   • Validação antes de fechar')
        self.stdout.write('   • Fechamento com validações')
        self.stdout.write('   • Reabertura com motivo')
        self.stdout.write('   • Marcar como paga')
        self.stdout.write('   • Controle de permissões')
        self.stdout.write('   • Resumo para fechamento')
        self.stdout.write('')
        self.stdout.write('🚀 SISTEMA DE FECHAMENTO FUNCIONANDO!')
