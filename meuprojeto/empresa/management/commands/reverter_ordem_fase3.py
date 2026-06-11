"""
Comando para reverter uma ordem de produção finalizada de volta para a Fase 3.
Útil para testes e correções.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from meuprojeto.empresa.models_stock import OrdemProducao
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Reverte uma ordem de produção finalizada para a Fase 3'

    def add_arguments(self, parser):
        parser.add_argument(
            'codigo',
            type=str,
            help='Código da ordem de produção (ex: OP2025110002)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Executa sem fazer alterações (apenas mostra o que seria feito)',
        )

    def handle(self, *args, **options):
        codigo = options['codigo']
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('MODO DRY-RUN: Nenhuma alteração será feita'))
        
        try:
            ordem = OrdemProducao.objects.get(codigo=codigo)
            
            self.stdout.write(f'Ordem encontrada: {ordem.codigo}')
            self.stdout.write(f'  - Fase Atual: {ordem.fase_atual}')
            self.stdout.write(f'  - Produto: {ordem.receita.produto.nome if ordem.receita and ordem.receita.produto else "N/A"}')
            self.stdout.write(f'  - Quantidade: {ordem.quantidade}')
            self.stdout.write(f'  - Qualidade Aprovada: {ordem.controle_qualidade_aprovado}')
            self.stdout.write(f'  - Acabamentos Concluidos: {ordem.acabamentos_concluidos}')
            self.stdout.write(f'  - Retoques Concluidos: {ordem.retoques_concluidos}')
            self.stdout.write(f'  - Data Finalizacao: {ordem.data_finalizacao}')
            
            if ordem.fase_atual != 'FINALIZADA':
                self.stdout.write(
                    self.style.WARNING(
                        f'A ordem {codigo} nao esta finalizada. Fase atual: {ordem.fase_atual}'
                    )
                )
                return
            
            if not dry_run:
                with transaction.atomic():
                    # Reverter para Fase 3
                    ordem.fase_atual = 'FASE3_FINALIZACAO'
                    ordem.produto_disponibilizado = False
                    
                    # Manter as etapas concluídas, mas resetar aprovação de qualidade
                    # ordem.acabamentos_concluidos = False  # Opcional: resetar etapas
                    # ordem.retoques_concluidos = False
                    ordem.controle_qualidade_aprovado = False
                    ordem.aprovado_qualidade_por = None
                    ordem.data_aprovacao_qualidade = None
                    ordem.observacoes_qualidade = ''
                    
                    # Limpar dados de finalização
                    ordem.observacoes_finalizacao = ''
                    ordem.data_finalizacao = None
                    
                    ordem.save()
                    
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'[OK] Ordem {codigo} revertida para Fase 3 (FINALIZACAO) com sucesso!'
                        )
                    )
                    self.stdout.write(f'  - Fase Atual: {ordem.fase_atual}')
                    self.stdout.write(f'  - Qualidade Aprovada: {ordem.controle_qualidade_aprovado}')
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f'[DRY-RUN] Reverteria ordem {codigo} para Fase 3'
                    )
                )
                self.stdout.write('  - Fase Atual: FINALIZADA -> FASE3_FINALIZACAO')
                self.stdout.write('  - Qualidade Aprovada: True -> False')
                self.stdout.write('  - Produto Disponibilizado: True -> False')
                
        except OrdemProducao.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'[ERRO] Ordem com codigo {codigo} nao encontrada!')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'[ERRO] Erro ao reverter ordem: {str(e)}')
            )
            logger.error(f"Erro ao reverter ordem {codigo}: {e}", exc_info=True)

