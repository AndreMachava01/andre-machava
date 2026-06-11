"""
Comando para corrigir requisições de produção que não foram associadas corretamente às ordens
"""
from django.core.management.base import BaseCommand
from meuprojeto.empresa.models_stock import OrdemProducao, RequisicaoProducao


class Command(BaseCommand):
    help = 'Corrige requisições de produção que não foram associadas corretamente às ordens'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostra o que seria feito sem fazer alterações',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('MODO DRY-RUN: Nenhuma alteração será feita'))
        
        # Buscar ordens com requisicao_material_criada=True mas sem requisicao_material
        ordens_problema = OrdemProducao.objects.filter(
            requisicao_material_criada=True,
            requisicao_material__isnull=True
        )
        
        total_corrigidas = 0
        
        for ordem in ordens_problema:
            self.stdout.write(f'\nOrdem: {ordem.codigo}')
            self.stdout.write(f'  requisicao_material_criada: {ordem.requisicao_material_criada}')
            self.stdout.write(f'  requisicao_material: {ordem.requisicao_material}')
            
            # Buscar requisições associadas a esta ordem
            requisicoes = RequisicaoProducao.objects.filter(ordem_producao=ordem)
            
            if requisicoes.exists():
                requisicao = requisicoes.order_by('-data_criacao').first()
                self.stdout.write(f'  Requisição encontrada: {requisicao.codigo}')
                
                if not dry_run:
                    ordem.requisicao_material = requisicao
                    ordem.save(update_fields=['requisicao_material'])
                    self.stdout.write(self.style.SUCCESS(f'  [OK] Requisicao {requisicao.codigo} associada a ordem {ordem.codigo}'))
                    total_corrigidas += 1
                else:
                    self.stdout.write(self.style.WARNING(f'  [DRY-RUN] Associaria {requisicao.codigo} a ordem {ordem.codigo}'))
            else:
                self.stdout.write(self.style.ERROR(f'  [ERRO] Nenhuma requisicao encontrada para ordem {ordem.codigo}'))
                if not dry_run:
                    # Se não há requisição, marcar como não criada
                    ordem.requisicao_material_criada = False
                    ordem.save(update_fields=['requisicao_material_criada'])
                    self.stdout.write(self.style.WARNING(f'  [AVISO] Marcando requisicao_material_criada=False para ordem {ordem.codigo}'))
        
        if dry_run:
            self.stdout.write(self.style.WARNING(f'\n[DRY-RUN] Total de ordens que seriam corrigidas: {total_corrigidas}'))
        else:
            self.stdout.write(self.style.SUCCESS(f'\n[OK] Total de ordens corrigidas: {total_corrigidas}'))

