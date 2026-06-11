"""
Comando para corrigir requisições de produção duplicadas
"""
from django.core.management.base import BaseCommand
from meuprojeto.empresa.models_stock import RequisicaoProducao, OrdemProducao
from django.db import transaction, models


class Command(BaseCommand):
    help = 'Corrige requisições de produção duplicadas para a mesma ordem'

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
        
        # Buscar todas as ordens que têm múltiplas requisições
        ordens_com_multiplas = OrdemProducao.objects.annotate(
            num_requisicoes=models.Count('requisicoes_material')
        ).filter(num_requisicoes__gt=1)
        
        total_corrigidas = 0
        
        for ordem in ordens_com_multiplas:
            self.stdout.write(f'\nOrdem {ordem.codigo} tem múltiplas requisições:')
            
            # Buscar todas as requisições desta ordem
            requisicoes = RequisicaoProducao.objects.filter(
                ordem_producao=ordem
            ).order_by('data_criacao')
            
            # Identificar qual é a requisição correta (a que está associada à ordem)
            requisicao_correta = ordem.requisicao_material
            
            if not requisicao_correta:
                # Se nenhuma está associada, usar a mais recente
                requisicao_correta = requisicoes.last()
                self.stdout.write(f'  Nenhuma requisição associada. Usando a mais recente: {requisicao_correta.codigo}')
            
            self.stdout.write(f'  Requisição correta: {requisicao_correta.codigo} (Status: {requisicao_correta.status})')
            
            # Cancelar ou remover as outras requisições
            for req in requisicoes:
                if req.id != requisicao_correta.id:
                    self.stdout.write(f'  Requisição duplicada encontrada: {req.codigo} (Status: {req.status})')
                    
                    if not dry_run:
                        try:
                            with transaction.atomic():
                                # Se está pendente ou rascunho, pode cancelar
                                if req.status in ['RASCUNHO', 'PENDENTE']:
                                    req.status = 'CANCELADA'
                                    req.observacoes = f"{req.observacoes or ''}\n[CANCELADA] Requisição duplicada. Requisição correta: {requisicao_correta.codigo}".strip()
                                    req.save()
                                    self.stdout.write(self.style.SUCCESS(f'    [OK] {req.codigo} cancelada'))
                                    total_corrigidas += 1
                                else:
                                    # Se já foi processada, apenas remover
                                    req.delete()
                                    self.stdout.write(self.style.SUCCESS(f'    [OK] {req.codigo} removida'))
                                    total_corrigidas += 1
                        except Exception as e:
                            self.stdout.write(self.style.ERROR(f'    [ERRO] Erro ao processar {req.codigo}: {str(e)}'))
                    else:
                        if req.status in ['RASCUNHO', 'PENDENTE']:
                            self.stdout.write(self.style.WARNING(f'    [DRY-RUN] Cancelaria {req.codigo}'))
                        else:
                            self.stdout.write(self.style.WARNING(f'    [DRY-RUN] Removeria {req.codigo}'))
        
        if not dry_run:
            self.stdout.write(self.style.SUCCESS(f'\nTotal de requisições corrigidas: {total_corrigidas}'))
        else:
            self.stdout.write(self.style.WARNING(f'\n[DRY-RUN] Total de requisições que seriam corrigidas: {total_corrigidas}'))

