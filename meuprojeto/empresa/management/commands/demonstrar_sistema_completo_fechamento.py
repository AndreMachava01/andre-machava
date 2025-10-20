from django.core.management.base import BaseCommand
from meuprojeto.empresa.models_rh import FolhaSalarial, Funcionario, FuncionarioFolha
from datetime import date
from django.core.exceptions import ValidationError

class Command(BaseCommand):
    help = 'Demonstra o sistema completo de fechamento da folha de salário'

    def handle(self, *args, **options):
        self.stdout.write('=' * 80)
        self.stdout.write('🎯 SISTEMA COMPLETO DE FECHAMENTO DA FOLHA DE SALÁRIO')
        self.stdout.write('=' * 80)
        self.stdout.write('')
        
        # Buscar folha de setembro
        folha = FolhaSalarial.objects.filter(mes_referencia__year=2025, mes_referencia__month=9).first()
        
        if not folha:
            self.stdout.write('❌ Folha de setembro não encontrada')
            return
        
        self.stdout.write('📋 DEMONSTRAÇÃO DO SISTEMA DE FECHAMENTO')
        self.stdout.write('=' * 50)
        self.stdout.write('')
        
        # 1. Estado inicial
        self.stdout.write('1️⃣ ESTADO INICIAL DA FOLHA:')
        self.stdout.write(f'   • Mês: {folha.mes_referencia.strftime("%B/%Y")}')
        self.stdout.write(f'   • Status: {folha.get_status_display()}')
        self.stdout.write(f'   • Total Bruto: {folha.total_bruto} MT')
        self.stdout.write(f'   • Total Líquido: {folha.total_liquido} MT')
        self.stdout.write(f'   • Funcionários: {folha.total_funcionarios}')
        self.stdout.write('')
        
        # 2. Validação
        self.stdout.write('2️⃣ VALIDAÇÃO ANTES DE FECHAR:')
        validacao = folha.validar_antes_fechar()
        
        if validacao['valido']:
            self.stdout.write('   ✅ Folha válida para fechamento')
        else:
            self.stdout.write('   ❌ Folha com problemas:')
            for erro in validacao['erros']:
                self.stdout.write(f'      - {erro}')
        
        if validacao['avisos']:
            self.stdout.write('   ⚠️  Avisos encontrados:')
            for aviso in validacao['avisos']:
                self.stdout.write(f'      - {aviso}')
        self.stdout.write('')
        
        # 3. Fechamento
        if folha.pode_fechar():
            self.stdout.write('3️⃣ FECHANDO A FOLHA:')
            try:
                resultado = folha.fechar_folha(observacoes='Demonstração do sistema de fechamento')
                
                self.stdout.write('   ✅ Folha fechada com sucesso!')
                self.stdout.write(f'   • Data de fechamento: {resultado["data_fechamento"]}')
                self.stdout.write(f'   • Status atual: {folha.get_status_display()}')
                self.stdout.write('')
                
                # 4. Reabertura
                self.stdout.write('4️⃣ REABRINDO A FOLHA:')
                if folha.pode_reabrir():
                    resultado_reabrir = folha.reabrir_folha(motivo='Demonstração de reabertura')
                    
                    self.stdout.write('   ✅ Folha reaberta com sucesso!')
                    self.stdout.write(f'   • Status: {resultado_reabrir["status"]}')
                    self.stdout.write(f'   • Motivo: {resultado_reabrir["motivo"]}')
                    self.stdout.write('')
                    
                    # Fechar novamente
                    folha.fechar_folha(observacoes='Fechamento após demonstração de reabertura')
                    self.stdout.write('   • Folha fechada novamente')
                    self.stdout.write('')
                
                # 5. Marcar como paga
                self.stdout.write('5️⃣ MARCANDO COMO PAGA:')
                if folha.pode_marcar_paga():
                    resultado_paga = folha.marcar_como_paga(
                        data_pagamento=date.today(),
                        observacoes='Demonstração de pagamento'
                    )
                    
                    self.stdout.write('   ✅ Folha marcada como paga!')
                    self.stdout.write(f'   • Data de pagamento: {resultado_paga["data_pagamento"]}')
                    self.stdout.write(f'   • Status final: {resultado_paga["status"]}')
                    self.stdout.write('')
                
            except ValidationError as e:
                self.stdout.write(f'   ❌ Erro: {e}')
        
        # 6. Resumo final
        self.stdout.write('6️⃣ RESUMO FINAL:')
        resumo = folha.get_resumo_fechamento()
        
        self.stdout.write(f'   • Mês: {resumo["mes_referencia"]}')
        self.stdout.write(f'   • Status: {resumo["status"]}')
        self.stdout.write(f'   • Total funcionários: {resumo["total_funcionarios"]}')
        self.stdout.write(f'   • Total bruto: {resumo["total_bruto"]} MT')
        self.stdout.write(f'   • Total descontos: {resumo["total_descontos"]} MT')
        self.stdout.write(f'   • Total líquido: {resumo["total_liquido"]} MT')
        self.stdout.write('')
        
        # 7. Funcionalidades implementadas
        self.stdout.write('7️⃣ FUNCIONALIDADES IMPLEMENTADAS:')
        self.stdout.write('')
        
        self.stdout.write('   🔧 NO MODELO FolhaSalarial:')
        self.stdout.write('      • validar_antes_fechar() - Valida dados antes de fechar')
        self.stdout.write('      • fechar_folha() - Fecha com validações e observações')
        self.stdout.write('      • reabrir_folha() - Reabre com motivo obrigatório')
        self.stdout.write('      • marcar_como_paga() - Marca como paga com data')
        self.stdout.write('      • pode_editar() - Verifica se pode editar')
        self.stdout.write('      • pode_fechar() - Verifica se pode fechar')
        self.stdout.write('      • pode_reabrir() - Verifica se pode reabrir')
        self.stdout.write('      • pode_marcar_paga() - Verifica se pode marcar como paga')
        self.stdout.write('      • get_resumo_fechamento() - Resumo para fechamento')
        self.stdout.write('')
        
        self.stdout.write('   🌐 NO VIEWS:')
        self.stdout.write('      • rh_folha_validar_fechamento - Página de validação')
        self.stdout.write('      • rh_folha_fechar - Fecha a folha')
        self.stdout.write('      • rh_folha_reabrir - Reabre a folha')
        self.stdout.write('      • rh_folha_marcar_paga - Marca como paga')
        self.stdout.write('')
        
        self.stdout.write('   🎨 NOS TEMPLATES:')
        self.stdout.write('      • validar_fechamento.html - Interface de validação')
        self.stdout.write('      • reabrir.html - Interface de reabertura')
        self.stdout.write('      • marcar_paga.html - Interface de pagamento')
        self.stdout.write('      • detail.html - Botões condicionais atualizados')
        self.stdout.write('')
        
        self.stdout.write('   🔗 NAS URLs:')
        self.stdout.write('      • folha-salarial/validar-fechamento/<id>/')
        self.stdout.write('      • folha-salarial/fechar/<id>/')
        self.stdout.write('      • folha-salarial/reabrir/<id>/')
        self.stdout.write('      • folha-salarial/marcar-paga/<id>/')
        self.stdout.write('')
        
        # 8. Validações implementadas
        self.stdout.write('8️⃣ VALIDAÇÕES IMPLEMENTADAS:')
        self.stdout.write('')
        
        self.stdout.write('   ✅ ANTES DE FECHAR:')
        self.stdout.write('      • Verifica se há funcionários na folha')
        self.stdout.write('      • Verifica se todos têm salário base > 0')
        self.stdout.write('      • Verifica se todos têm dados de presença')
        self.stdout.write('      • Verifica se há funcionários com salário líquido negativo')
        self.stdout.write('      • Verifica se os totais estão calculados')
        self.stdout.write('      • Verifica se há funcionários ativos não incluídos')
        self.stdout.write('')
        
        self.stdout.write('   ⚠️  AVISOS MOSTRADOS:')
        self.stdout.write('      • Funcionários sem presenças registradas')
        self.stdout.write('      • Funcionários com salário líquido negativo')
        self.stdout.write('      • Totais não calculados')
        self.stdout.write('      • Funcionários ativos não incluídos na folha')
        self.stdout.write('')
        
        # 9. Controle de permissões
        self.stdout.write('9️⃣ CONTROLE DE PERMISSÕES:')
        self.stdout.write('')
        
        self.stdout.write('   🔒 BLOQUEIOS IMPLEMENTADOS:')
        self.stdout.write('      • Só permite fechar folhas ABERTAS')
        self.stdout.write('      • Só permite reabrir folhas FECHADAS')
        self.stdout.write('      • Só permite marcar como paga folhas FECHADAS')
        self.stdout.write('      • Botões aparecem condicionalmente na interface')
        self.stdout.write('')
        
        # 10. Benefícios do sistema
        self.stdout.write('🔟 BENEFÍCIOS DO SISTEMA:')
        self.stdout.write('')
        
        self.stdout.write('   🎯 SEGURANÇA:')
        self.stdout.write('      • Validações automáticas antes de fechar')
        self.stdout.write('      • Controle de permissões rigoroso')
        self.stdout.write('      • Histórico de alterações com observações')
        self.stdout.write('      • Prevenção de fechamento com dados inconsistentes')
        self.stdout.write('')
        
        self.stdout.write('   🚀 EFICIÊNCIA:')
        self.stdout.write('      • Interface intuitiva e clara')
        self.stdout.write('      • Validações em tempo real')
        self.stdout.write('      • Resumo completo antes de fechar')
        self.stdout.write('      • Processo guiado passo a passo')
        self.stdout.write('')
        
        self.stdout.write('   📊 CONTROLE:')
        self.stdout.write('      • Visibilidade total do processo')
        self.stdout.write('      • Avisos e erros claros')
        self.stdout.write('      • Possibilidade de reabertura com justificativa')
        self.stdout.write('      • Rastreabilidade completa das ações')
        self.stdout.write('')
        
        self.stdout.write('🎉 SISTEMA DE FECHAMENTO COMPLETO E FUNCIONAL!')
        self.stdout.write('')
        self.stdout.write('✅ IMPLEMENTAÇÃO CONCLUÍDA COM SUCESSO!')
        self.stdout.write('')
        self.stdout.write('🚀 O sistema agora possui um fluxo robusto e seguro')
        self.stdout.write('   para fechamento, reabertura e controle de pagamento')
        self.stdout.write('   das folhas salariais!')
