"""
Comando para migrar ordens de produção antigas para o novo formato de 3 fases
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from meuprojeto.empresa.models_stock import OrdemProducao


class Command(BaseCommand):
    help = 'Migra ordens de produção antigas para o novo formato de 3 fases'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simula a migração sem salvar alterações',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('[DRY-RUN] Modo de simulação ativado'))
        
        # Buscar todas as ordens que ainda não foram migradas
        # Como os campos antigos foram removidos, vamos migrar baseado no que temos
        ordens = OrdemProducao.objects.all()
        
        if not ordens.exists():
            self.stdout.write(self.style.SUCCESS('Nenhuma ordem encontrada para migrar.'))
            return
        
        self.stdout.write(f'Encontradas {ordens.count()} ordens para migrar.')
        
        migradas = 0
        for ordem in ordens:
            try:
                # Verificar se a ordem já foi migrada (tem fase diferente do padrão ou status aprovado)
                if ordem.fase_atual != 'FASE1_CRIACAO' or ordem.status_aprovacao != 'PENDENTE':
                    # Já foi migrada ou criada no novo formato
                    self.stdout.write(
                        self.style.WARNING(
                            f'Ordem {ordem.codigo} já está no formato novo: '
                            f'{ordem.fase_atual} - {ordem.get_status_aprovacao_display()}'
                        )
                    )
                    continue
                
                mudou = False
                
                # Verificar se a ordem tem quantidade_produzida > 0
                # Se sim, provavelmente estava em produção ou concluída
                if ordem.quantidade_produzida > 0:
                    if ordem.quantidade_produzida >= ordem.quantidade:
                        # Ordem estava concluída
                        ordem.fase_atual = 'FINALIZADA'
                        ordem.status_aprovacao = 'APROVADA'
                        ordem.produto_disponibilizado = True
                        if not ordem.data_finalizacao:
                            ordem.data_finalizacao = ordem.data_criacao
                        if not ordem.data_aprovacao:
                            ordem.data_aprovacao = ordem.data_criacao
                        mudou = True
                    else:
                        # Ordem estava em produção parcial - colocar na Fase 2
                        # Assumir que passou pelas etapas básicas
                        ordem.fase_atual = 'FASE2_EXECUCAO'
                        ordem.status_aprovacao = 'APROVADA'
                        ordem.requisicao_material_criada = True
                        ordem.preparacao_pecas_concluida = True
                        ordem.montagem_concluida = True
                        if not ordem.data_aprovacao:
                            ordem.data_aprovacao = ordem.data_criacao
                        if not ordem.data_inicio_fase2:
                            ordem.data_inicio_fase2 = ordem.data_criacao
                        mudou = True
                
                # Se não tem quantidade produzida, manter na Fase 1 como pendente
                # (será aprovada manualmente pelo usuário)
                
                if mudou:
                    if not dry_run:
                        ordem.save()
                    
                    migradas += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'[{"DRY-RUN" if dry_run else "OK"}] Ordem {ordem.codigo} migrada: '
                            f'{ordem.fase_atual} - {ordem.get_status_aprovacao_display()} '
                            f'(Qtd: {ordem.quantidade_produzida}/{ordem.quantidade})'
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f'Ordem {ordem.codigo} mantida na Fase 1 (Pendente) - '
                            f'sem produção iniciada'
                        )
                    )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Erro ao migrar ordem {ordem.codigo}: {str(e)}')
                )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'\n[DRY-RUN] {migradas} ordens seriam migradas. '
                    'Execute sem --dry-run para aplicar as mudanças.'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'\n{migradas} ordens migradas com sucesso!')
            )

