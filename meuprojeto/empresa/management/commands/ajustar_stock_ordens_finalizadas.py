"""
Comando para ajustar o stock das ordens de produção já finalizadas
que não tiveram o produto adicionado ao stock automaticamente.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from decimal import Decimal
from meuprojeto.empresa.models_stock import (
    OrdemProducao, MovimentoItem, TipoMovimentoStock, StockItem
)
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Ajusta o stock das ordens de produção finalizadas que não tiveram produto adicionado'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Executa sem fazer alterações (apenas mostra o que seria feito)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('MODO DRY-RUN: Nenhuma alteração será feita'))
        
        # Buscar ordens finalizadas
        ordens_finalizadas = OrdemProducao.objects.filter(
            fase_atual='FINALIZADA'
        ).select_related('receita', 'receita__produto', 'sucursal')
        
        self.stdout.write(f'Encontradas {ordens_finalizadas.count()} ordens finalizadas')
        
        # Buscar ou criar tipo de movimento para produção
        tipo_entrada_producao = TipoMovimentoStock.objects.filter(
            codigo='ENT_PRODUCAO'
        ).first()
        
        if not tipo_entrada_producao:
            if not dry_run:
                tipo_entrada_producao = TipoMovimentoStock.objects.create(
                    codigo='ENT_PRODUCAO',
                    nome='Entrada por Produção',
                    descricao='Entrada de produto no stock através de produção',
                    aumenta_estoque=True,
                    ativo=True
                )
                self.stdout.write(self.style.SUCCESS('Tipo de movimento ENT_PRODUCAO criado'))
            else:
                self.stdout.write(self.style.WARNING('Tipo de movimento ENT_PRODUCAO seria criado'))
        
        ordens_processadas = 0
        ordens_com_erro = 0
        
        for ordem in ordens_finalizadas:
            if not ordem.receita or not ordem.receita.produto:
                self.stdout.write(
                    self.style.WARNING(
                        f'Ordem {ordem.codigo}: Sem receita ou produto associado'
                    )
                )
                continue
            
            # Verificar se já existe movimento para esta ordem
            movimento_existente = MovimentoItem.objects.filter(
                referencia__icontains=f'Ordem de Produção {ordem.codigo}',
                tipo_movimento=tipo_entrada_producao
            ).first()
            
            if movimento_existente:
                self.stdout.write(
                    self.style.WARNING(
                        f'Ordem {ordem.codigo}: Já possui movimento de stock'
                    )
                )
                continue
            
            try:
                produto = ordem.receita.produto
                
                # Verificar se o produto é do tipo PRODUTO
                if produto.tipo != 'PRODUTO':
                    self.stdout.write(
                        self.style.WARNING(
                            f'Ordem {ordem.codigo}: Item {produto.nome} não é um produto (tipo: {produto.tipo}). Pulando.'
                        )
                    )
                    continue
                
                # Calcular preço de custo
                # IMPORTANTE: calcular_custo_por_produto() já retorna o custo por unidade (já dividido pelo rendimento)
                try:
                    preco_custo = ordem.receita.calcular_custo_por_produto()
                    if not preco_custo or preco_custo <= 0:
                        preco_custo = produto.preco_custo if hasattr(produto, 'preco_custo') and produto.preco_custo else Decimal('0.00')
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'Erro ao calcular custo: {e}'))
                    preco_custo = produto.preco_custo if hasattr(produto, 'preco_custo') and produto.preco_custo else Decimal('0.00')
                
                if not dry_run:
                    with transaction.atomic():
                        # Gerar código único para o movimento (máximo 20 caracteres)
                        codigo_ordem_curto = ordem.codigo.replace('OP', '')  # Remove OP para economizar espaço
                        codigo_base = f"MOV{codigo_ordem_curto}P"
                        
                        # Garantir que o código base não ultrapasse 18 caracteres
                        if len(codigo_base) > 18:
                            codigo_base = codigo_base[:18]
                        
                        codigo_movimento = codigo_base
                        contador = 1
                        while MovimentoItem.objects.filter(codigo=codigo_movimento).exists():
                            # Adicionar sufixo numérico (máximo 2 dígitos)
                            codigo_movimento = f"{codigo_base[:18]}{contador:02d}"
                            contador += 1
                            if contador > 99:  # Limite de segurança
                                import time
                                timestamp = str(int(time.time()))[-6:]  # Últimos 6 dígitos
                                codigo_movimento = f"MOV{timestamp}P"
                                break
                        
                        # Garantir que o código final não ultrapasse 20 caracteres
                        if len(codigo_movimento) > 20:
                            codigo_movimento = codigo_movimento[:20]
                        
                        # Criar movimento de entrada
                        movimento = MovimentoItem.objects.create(
                            codigo=codigo_movimento,
                            item=produto,
                            tipo_movimento=tipo_entrada_producao,
                            sucursal=ordem.sucursal,
                            quantidade=ordem.quantidade_produzida,
                            preco_unitario=preco_custo,
                            valor_total=preco_custo * Decimal(str(ordem.quantidade_produzida)),
                            referencia=f"Ordem de Produção {ordem.codigo}",
                            observacoes=f"Produto produzido pela ordem {ordem.codigo} (ajustado retroativamente)",
                            usuario=None  # Não há usuário para ajustes retroativos
                        )
                        
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'Ordem {ordem.codigo}: {ordem.quantidade_produzida} unidades de {produto.nome} adicionadas ao stock'
                            )
                        )
                else:
                    self.stdout.write(
                        f'[DRY-RUN] Ordem {ordem.codigo}: Adicionaria {ordem.quantidade_produzida} unidades de {produto.nome} ao stock'
                    )
                
                ordens_processadas += 1
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'Erro ao processar ordem {ordem.codigo}: {str(e)}'
                    )
                )
                ordens_com_erro += 1
                logger.error(f"Erro ao processar ordem {ordem.codigo}: {e}", exc_info=True)
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'Processamento concluído:'))
        self.stdout.write(f'  - Ordens processadas: {ordens_processadas}')
        if ordens_com_erro > 0:
            self.stdout.write(self.style.ERROR(f'  - Ordens com erro: {ordens_com_erro}'))

