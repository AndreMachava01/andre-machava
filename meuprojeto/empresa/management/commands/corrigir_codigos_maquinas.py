from django.core.management.base import BaseCommand
from django.db import transaction
from meuprojeto.empresa.models_stock import Maquina


class Command(BaseCommand):
    help = 'Atualiza códigos de máquinas existentes para o formato sequencial simples (MAQ001, MAQ002, etc.)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostra o que seria feito sem fazer alterações',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        self.stdout.write(self.style.SUCCESS('=== ATUALIZAÇÃO DE CÓDIGOS DE MÁQUINAS ==='))
        
        # Buscar todas as máquinas
        todas_maquinas = Maquina.objects.all().order_by('data_criacao')
        total_maquinas = todas_maquinas.count()
        
        if total_maquinas == 0:
            self.stdout.write(self.style.SUCCESS('Nenhuma máquina encontrada.'))
            return
        
        self.stdout.write(f'Encontradas {total_maquinas} máquinas para processar.')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('Modo dry-run ativado. Nenhuma alteração será feita.'))
        
        maquinas_atualizadas = 0
        proximo_numero = 1
        
        with transaction.atomic():
            for maquina in todas_maquinas:
                codigo_antigo = maquina.codigo or 'N/A'
                
                # Verificar se o código já está no formato correto
                if codigo_antigo.startswith('MAQ') and len(codigo_antigo) == 6:
                    try:
                        numero = int(codigo_antigo[3:])
                        # Se já está no formato MAQ001, verificar se precisa ajustar
                        if numero == proximo_numero:
                            self.stdout.write(
                                f'[OK] {maquina.nome}: {codigo_antigo} (ja esta correto)'
                            )
                            proximo_numero += 1
                            continue
                    except ValueError:
                        pass
                
                # Gerar novo código sequencial
                novo_codigo = f"MAQ{proximo_numero:03d}"
                
                # Verificar se o novo código já existe
                while Maquina.objects.filter(codigo=novo_codigo).exclude(pk=maquina.pk).exists():
                    proximo_numero += 1
                    novo_codigo = f"MAQ{proximo_numero:03d}"
                
                self.stdout.write(
                    f'{maquina.nome}: {codigo_antigo} -> {novo_codigo}'
                )
                
                if not dry_run:
                    maquina.codigo = novo_codigo
                    maquina.save(update_fields=['codigo'])
                    maquinas_atualizadas += 1
                    self.stdout.write(self.style.SUCCESS(f'  [OK] Atualizado'))
                else:
                    self.stdout.write(self.style.WARNING(f'  [DRY-RUN] Seria atualizado'))
                
                proximo_numero += 1
        
        # Resumo
        self.stdout.write(f'\n=== RESUMO ===')
        self.stdout.write(f'Total de máquinas processadas: {total_maquinas}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING(f'Modo dry-run: Nenhuma alteração foi feita'))
        else:
            self.stdout.write(f'Maquinas atualizadas: {maquinas_atualizadas}')
            self.stdout.write(self.style.SUCCESS('[OK] Atualizacao concluida!'))

