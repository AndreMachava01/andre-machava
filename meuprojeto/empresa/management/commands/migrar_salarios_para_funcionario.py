from django.core.management.base import BaseCommand
from meuprojeto.empresa.models_rh import Funcionario, Salario


class Command(BaseCommand):
    help = 'Migra salários da tabela Salario para o campo salario_atual do funcionário'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostra o que seria feito sem executar as alterações',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        self.stdout.write(self.style.SUCCESS('=== MIGRAÇÃO DE SALÁRIOS PARA FUNCIONÁRIO ==='))
        
        funcionarios = Funcionario.objects.filter(status='AT')
        total_funcionarios = funcionarios.count()
        self.stdout.write(f'Processando {total_funcionarios} funcionários...')
        
        funcionarios_migrados = 0
        
        for funcionario in funcionarios:
            self.stdout.write(f'\n--- {funcionario.nome_completo} ---')
            
            # Buscar salário ativo mais recente
            salario_ativo = Salario.objects.filter(
                funcionario=funcionario,
                status='AT'
            ).order_by('-data_inicio').first()
            
            if salario_ativo:
                self.stdout.write(f'Salário encontrado: {salario_ativo.valor_base} MT')
                
                if not dry_run:
                    # Atualizar campo salario_atual
                    funcionario.salario_atual = salario_ativo.valor_base
                    funcionario.save(update_fields=['salario_atual'])
                    funcionarios_migrados += 1
                    self.stdout.write('✅ Migrado com sucesso')
                else:
                    self.stdout.write('⚠️  Seria migrado (dry-run)')
            else:
                self.stdout.write('⚠️  Sem salário ativo encontrado')
        
        # Resumo
        self.stdout.write(f'\n=== RESUMO ===')
        self.stdout.write(f'Funcionários processados: {total_funcionarios}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING(f'Modo dry-run: Nenhuma alteração foi feita'))
        else:
            self.stdout.write(f'Funcionários migrados: {funcionarios_migrados}')
            self.stdout.write(self.style.SUCCESS('✅ Migração concluída!'))
