from django.core.management.base import BaseCommand
from meuprojeto.empresa.models_rh import Funcionario, Salario, FolhaSalarial, FuncionarioFolha
from datetime import date


class Command(BaseCommand):
    help = 'Sincroniza salários entre todas as seções do sistema'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostra o que seria feito sem executar as alterações',
        )
        parser.add_argument(
            '--funcionario-id',
            type=int,
            help='Sincroniza apenas um funcionário específico',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        funcionario_id = options.get('funcionario_id')
        
        self.stdout.write(self.style.SUCCESS('=== SINCRONIZAÇÃO DE SALÁRIOS ==='))
        
        if funcionario_id:
            funcionarios = Funcionario.objects.filter(id=funcionario_id)
        else:
            funcionarios = Funcionario.objects.filter(status='AT')
        
        total_funcionarios = funcionarios.count()
        self.stdout.write(f'Processando {total_funcionarios} funcionários...')
        
        inconsistencias_encontradas = 0
        funcionarios_corrigidos = 0
        
        for funcionario in funcionarios:
            self.stdout.write(f'\n--- {funcionario.nome_completo} ---')
            
            # Validar consistência
            validacao = funcionario.validar_consistencia_salario()
            
            if validacao['consistente']:
                self.stdout.write(self.style.SUCCESS('✅ Consistente'))
            else:
                inconsistencias_encontradas += 1
                self.stdout.write(self.style.WARNING('❌ Inconsistente:'))
                for inconsistencia in validacao['inconsistencias']:
                    self.stdout.write(f'   - {inconsistencia}')
                
                if not dry_run:
                    # Sincronizar salário
                    funcionario.sincronizar_salario_atual()
                    funcionarios_corrigidos += 1
                    self.stdout.write(self.style.SUCCESS('   ✅ Sincronizado'))
                else:
                    self.stdout.write(self.style.WARNING('   ⚠️  Seria sincronizado (dry-run)'))
        
        # Sincronizar folhas salariais abertas
        self.stdout.write(f'\n=== SINCRONIZANDO FOLHAS SALARIAIS ===')
        folhas_abertas = FolhaSalarial.objects.filter(status='ABERTA')
        
        for folha in folhas_abertas:
            self.stdout.write(f'\nFolha: {folha.mes_referencia.strftime("%B %Y")}')
            funcionarios_folha = folha.funcionarios_folha.all()
            
            for funcionario_folha in funcionarios_folha:
                salario_atual = funcionario_folha.funcionario.get_salario_atual()
                
                if funcionario_folha.salario_base != salario_atual:
                    self.stdout.write(f'   {funcionario_folha.funcionario.nome_completo}: {funcionario_folha.salario_base} → {salario_atual}')
                    
                    if not dry_run:
                        funcionario_folha.salario_base = salario_atual
                        funcionario_folha.calcular_salario()
                        funcionario_folha.save()
                        self.stdout.write('   ✅ Atualizado')
                    else:
                        self.stdout.write('   ⚠️  Seria atualizado (dry-run)')
            
            if not dry_run:
                folha.calcular_totais()
                self.stdout.write('   ✅ Totais recalculados')
        
        # Resumo
        self.stdout.write(f'\n=== RESUMO ===')
        self.stdout.write(f'Funcionários processados: {total_funcionarios}')
        self.stdout.write(f'Inconsistências encontradas: {inconsistencias_encontradas}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING(f'Modo dry-run: Nenhuma alteração foi feita'))
        else:
            self.stdout.write(f'Funcionários corrigidos: {funcionarios_corrigidos}')
            self.stdout.write(self.style.SUCCESS('✅ Sincronização concluída!'))
