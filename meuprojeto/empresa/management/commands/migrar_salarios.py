from django.core.management.base import BaseCommand
from meuprojeto.empresa.models_rh import Funcionario, Salario
from datetime import date


class Command(BaseCommand):
    help = 'Migra salários do campo salario_atual para a tabela Salario'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostra o que seria feito sem executar as alterações',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        self.stdout.write(self.style.SUCCESS('=== MIGRAÇÃO DE SALÁRIOS ==='))
        
        funcionarios = Funcionario.objects.filter(status='AT')
        total_funcionarios = funcionarios.count()
        self.stdout.write(f'Processando {total_funcionarios} funcionários...')
        
        funcionarios_migrados = 0
        
        for funcionario in funcionarios:
            self.stdout.write(f'\n--- {funcionario.nome_completo} ---')
            
            # Verificar se já tem salário na tabela Salario
            salario_existente = Salario.objects.filter(
                funcionario=funcionario,
                status='AT'
            ).first()
            
            if salario_existente:
                self.stdout.write('✅ Já possui salário na tabela Salario')
                continue
            
            # Verificar se tem salario_atual
            if funcionario.salario_atual and funcionario.salario_atual > 0:
                self.stdout.write(f'Migrando salário: {funcionario.salario_atual} MT')
                
                if not dry_run:
                    # Criar registro na tabela Salario
                    Salario.objects.create(
                        funcionario=funcionario,
                        valor_base=funcionario.salario_atual,
                        data_inicio=funcionario.data_admissao,
                        status='AT',
                        observacoes='Migrado automaticamente do campo salario_atual'
                    )
                    funcionarios_migrados += 1
                    self.stdout.write('✅ Migrado com sucesso')
                else:
                    self.stdout.write('⚠️  Seria migrado (dry-run)')
            else:
                self.stdout.write('⚠️  Sem salário para migrar')
        
        # Resumo
        self.stdout.write(f'\n=== RESUMO ===')
        self.stdout.write(f'Funcionários processados: {total_funcionarios}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING(f'Modo dry-run: Nenhuma alteração foi feita'))
        else:
            self.stdout.write(f'Funcionários migrados: {funcionarios_migrados}')
            self.stdout.write(self.style.SUCCESS('✅ Migração concluída!'))
