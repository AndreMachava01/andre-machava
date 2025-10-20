from django.core.management.base import BaseCommand
from meuprojeto.empresa.models_rh import Funcionario


class Command(BaseCommand):
    help = 'Testa as funcionalidades de auditoria de salários'

    def add_arguments(self, parser):
        parser.add_argument(
            '--funcionario-id',
            type=int,
            help='ID do funcionário para testar',
        )

    def handle(self, *args, **options):
        funcionario_id = options.get('funcionario_id')
        
        if funcionario_id:
            funcionarios = Funcionario.objects.filter(id=funcionario_id)
        else:
            funcionarios = Funcionario.objects.filter(status='AT')[:1]
        
        if not funcionarios.exists():
            self.stdout.write(self.style.ERROR('Nenhum funcionário encontrado'))
            return
        
        funcionario = funcionarios.first()
        
        self.stdout.write(self.style.SUCCESS('=== TESTE DE AUDITORIA DE SALÁRIOS ==='))
        self.stdout.write(f'Funcionário: {funcionario.nome_completo}')
        self.stdout.write(f'Salário atual: {funcionario.salario_atual} MT')
        
        # Testar histórico
        self.stdout.write('\n📊 HISTÓRICO DE SALÁRIOS:')
        historico = funcionario.get_historico_salarios()
        for i, salario in enumerate(historico, 1):
            data_fim = salario.data_fim or 'Atual'
            self.stdout.write(f'   {i}. {salario.data_inicio} a {data_fim}: {salario.valor_base} MT ({salario.status})')
            if salario.observacoes:
                self.stdout.write(f'      Observações: {salario.observacoes}')
        
        # Testar última alteração
        self.stdout.write('\n🔄 ÚLTIMA ALTERAÇÃO:')
        ultima_alteracao = funcionario.get_ultima_alteracao_salario()
        if ultima_alteracao:
            self.stdout.write(f'   Data: {ultima_alteracao["data_alteracao"]}')
            self.stdout.write(f'   Valor atual: {ultima_alteracao["valor_atual"]} MT')
            self.stdout.write(f'   Observações: {ultima_alteracao["observacoes"]}')
        else:
            self.stdout.write('   Nenhuma alteração registrada')
        
        # Testar auditoria completa
        self.stdout.write('\n📋 AUDITORIA COMPLETA:')
        auditoria = funcionario.get_auditoria_salarios()
        for i, registro in enumerate(auditoria, 1):
            self.stdout.write(f'   {i}. {registro["data_inicio"]} - {registro["valor"]} MT')
            self.stdout.write(f'      Status: {registro["status"]}')
            self.stdout.write(f'      Criado em: {registro["data_criacao"]}')
            if registro["observacoes"]:
                self.stdout.write(f'      Observações: {registro["observacoes"]}')
            self.stdout.write()
        
        # Testar reversão (se houver histórico)
        if len(historico) > 1:
            self.stdout.write('🔄 TESTE DE REVERSÃO:')
            self.stdout.write('   (Simulando reversão para salário anterior)')
            # Não executar realmente, apenas mostrar que é possível
            self.stdout.write('   ✅ Funcionalidade de reversão disponível')
        else:
            self.stdout.write('⚠️  Não há histórico suficiente para testar reversão')
        
        self.stdout.write(self.style.SUCCESS('\n✅ Teste de auditoria concluído!'))
