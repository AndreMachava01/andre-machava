"""
Comando para corrigir recebimentos duplicados de ordens de compra
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum
from meuprojeto.empresa.models_stock import (
    OrdemCompra, ItemOrdemCompra, MovimentoItem, StockItem, 
    TipoMovimentoStock, RequisicaoCompraExterna, ItemRequisicaoCompraExterna
)


class Command(BaseCommand):
    help = 'Corrige recebimentos duplicados de ordens de compra, ajustando stock e movimentos'

    def add_arguments(self, parser):
        parser.add_argument(
            '--ordem',
            type=str,
            help='Código da ordem específica para corrigir (opcional)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simula a correção sem salvar alterações',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        ordem_codigo = options.get('ordem')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('[DRY-RUN] Modo de simulação ativado'))
        
        self.stdout.write(self.style.SUCCESS('=== CORREÇÃO DE RECEBIMENTOS DUPLICADOS ===\n'))
        
        # Buscar ordens recebidas
        if ordem_codigo:
            ordens = OrdemCompra.objects.filter(codigo=ordem_codigo, status='RECEBIDA')
            if not ordens.exists():
                self.stdout.write(self.style.ERROR(f'Ordem {ordem_codigo} não encontrada ou não está recebida.'))
                return
        else:
            ordens = OrdemCompra.objects.filter(status='RECEBIDA')
        
        if not ordens.exists():
            self.stdout.write(self.style.SUCCESS('Nenhuma ordem recebida encontrada.'))
            return
        
        self.stdout.write(f'Encontradas {ordens.count()} ordem(ns) recebida(s) para verificar.\n')
        
        total_corrigido = 0
        total_ordens_processadas = 0
        
        with transaction.atomic():
            for ordem in ordens:
                self.stdout.write(f'\n--- Processando Ordem: {ordem.codigo} ---')
                
                # Buscar todos os itens da ordem
                itens_ordem = ordem.itens.all()
                
                if not itens_ordem.exists():
                    self.stdout.write(self.style.WARNING(f'  Nenhum item encontrado na ordem.'))
                    continue
                
                ordem_tem_duplicacao = False
                
                for item_ordem in itens_ordem:
                    if not item_ordem.produto:
                        continue
                    
                    # Buscar stock atual
                    stock_item, created = StockItem.objects.get_or_create(
                        item=item_ordem.produto,
                        sucursal=ordem.sucursal_destino,
                        defaults={'quantidade_atual': 0}
                    )
                    
                    stock_atual = stock_item.quantidade_atual
                    quantidade_correta = item_ordem.quantidade_recebida
                    
                    if quantidade_correta == 0:
                        continue
                    
                    # Buscar todos os movimentos de entrada para este item nesta ordem
                    movimentos = MovimentoItem.objects.filter(
                        item=item_ordem.produto,
                        sucursal=ordem.sucursal_destino,
                        observacoes__icontains=f'Recebimento da ordem {ordem.codigo}',
                        tipo_movimento__codigo='ENT_COMPRA'
                    )
                    
                    # Calcular quantidade total movimentada
                    quantidade_movimentada = movimentos.aggregate(total=Sum('quantidade'))['total'] or 0
                    
                    # Verificar se há duplicação no stock (stock atual é maior que deveria ser)
                    # O stock deveria ser: stock antes do recebimento + quantidade recebida
                    # Se não sabemos o stock antes, assumimos que o stock atual deveria ser igual à quantidade recebida
                    # (se for uma ordem recente e única fonte de stock)
                    
                    # Verificar se há duplicação no stock ou nos movimentos
                    tem_duplicacao_stock = False
                    tem_duplicacao_movimentos = False
                    
                    # Se o stock atual é exatamente o dobro da quantidade recebida, provavelmente foi duplicado
                    if stock_atual >= quantidade_correta * 2:
                        tem_duplicacao_stock = True
                    
                    # Se há mais movimentos que o esperado
                    if quantidade_movimentada > quantidade_correta:
                        tem_duplicacao_movimentos = True
                    
                    if tem_duplicacao_stock or tem_duplicacao_movimentos:
                        ordem_tem_duplicacao = True
                        
                        self.stdout.write(
                            self.style.WARNING(
                                f'  Item: {item_ordem.produto.nome} ({item_ordem.produto.codigo})'
                            )
                        )
                        self.stdout.write(f'    Quantidade recebida (correta): {quantidade_correta}')
                        self.stdout.write(f'    Quantidade movimentada: {quantidade_movimentada}')
                        self.stdout.write(f'    Stock atual: {stock_atual}')
                        
                        if tem_duplicacao_stock:
                            diferenca_stock = stock_atual - quantidade_correta
                            self.stdout.write(f'    [DUPLICAÇÃO NO STOCK] Stock deveria ser ~{quantidade_correta}, mas está {stock_atual}')
                        
                        if tem_duplicacao_movimentos:
                            diferenca_mov = quantidade_movimentada - quantidade_correta
                            self.stdout.write(f'    [DUPLICAÇÃO NOS MOVIMENTOS] Diferença: {diferenca_mov}')
                        
                        stock_antes = stock_atual
                        
                        if not dry_run:
                            # Corrigir movimentos duplicados
                            movimentos_list = list(movimentos.order_by('id'))
                            
                            if tem_duplicacao_movimentos and len(movimentos_list) > 1:
                                # Remover movimentos duplicados (manter apenas o primeiro)
                                for movimento in movimentos_list[1:]:
                                    movimento.delete()
                                    self.stdout.write(f'    [REMOVIDO] Movimento ID {movimento.id} (quantidade: {movimento.quantidade})')
                                
                                # Atualizar o primeiro movimento para quantidade correta
                                if movimentos_list:
                                    movimento_principal = movimentos_list[0]
                                    movimento_principal.quantidade = quantidade_correta
                                    movimento_principal.save()
                                    self.stdout.write(f'    [AJUSTADO] Movimento ID {movimento_principal.id} para quantidade correta')
                            
                            # Corrigir stock duplicado
                            if tem_duplicacao_stock:
                                # Buscar todos os movimentos de entrada para este item nesta sucursal
                                # para calcular o stock correto baseado nos movimentos
                                todos_movimentos_entrada = MovimentoItem.objects.filter(
                                    item=item_ordem.produto,
                                    sucursal=ordem.sucursal_destino,
                                    tipo_movimento__aumenta_estoque=True
                                ).aggregate(total=Sum('quantidade'))['total'] or 0
                                
                                todos_movimentos_saida = MovimentoItem.objects.filter(
                                    item=item_ordem.produto,
                                    sucursal=ordem.sucursal_destino,
                                    tipo_movimento__aumenta_estoque=False
                                ).aggregate(total=Sum('quantidade'))['total'] or 0
                                
                                # Stock correto baseado em movimentos
                                stock_calculado = todos_movimentos_entrada - todos_movimentos_saida
                                
                                # Se o stock atual está duplicado (2x a quantidade recebida), corrigir
                                # Mas só se não houver outros movimentos que justifiquem o stock maior
                                if stock_atual >= quantidade_correta * 2 and stock_calculado < stock_atual:
                                    # Reduzir pela quantidade duplicada
                                    stock_correto = stock_atual - quantidade_correta
                                    stock_item.quantidade_atual = stock_correto
                                    stock_item.save()
                                    
                                    stock_depois = stock_item.quantidade_atual
                                    self.stdout.write(
                                        self.style.SUCCESS(
                                            f'    Stock ajustado: {stock_antes} -> {stock_depois}'
                                        )
                                    )
                                else:
                                    self.stdout.write(
                                        self.style.WARNING(
                                            f'    Stock não ajustado automaticamente. '
                                            f'Stock atual: {stock_atual}, Calculado: {stock_calculado}. '
                                            f'Verificar manualmente.'
                                        )
                                    )
                            else:
                                self.stdout.write(f'    Stock OK: {stock_atual}')
                            
                            # Corrigir quantidade_recebida na requisição de compra externa
                            if ordem.requisicao_origem:
                                try:
                                    # Buscar ou recriar item na requisição
                                    item_requisicao = ItemRequisicaoCompraExterna.objects.filter(
                                        requisicao=ordem.requisicao_origem,
                                        item=item_ordem.produto
                                    ).first()
                                    
                                    # Recalcular quantidade_recebida baseado nas ordens recebidas
                                    total_recebido_ordens = ItemOrdemCompra.objects.filter(
                                        ordem_compra__requisicao_origem=ordem.requisicao_origem,
                                        ordem_compra__status='RECEBIDA',
                                        produto=item_ordem.produto
                                    ).aggregate(total=Sum('quantidade_recebida'))['total'] or 0
                                    
                                    if item_requisicao:
                                        # Atualizar quantidade_recebida
                                        quantidade_solicitada_original = item_requisicao.quantidade_solicitada
                                        
                                        # Limitar ao máximo da quantidade solicitada
                                        if total_recebido_ordens > quantidade_solicitada_original:
                                            total_recebido_ordens = quantidade_solicitada_original
                                        
                                        item_requisicao.quantidade_recebida = total_recebido_ordens
                                        item_requisicao.save()
                                        
                                        self.stdout.write(
                                            self.style.SUCCESS(
                                                f'    Requisição {ordem.requisicao_origem.codigo} atualizada: '
                                                f'quantidade_recebida = {total_recebido_ordens}'
                                            )
                                        )
                                    else:
                                        # Item foi removido da requisição ao criar ordem
                                        # Recriar com quantidade correta
                                        quantidade_solicitada = ItemOrdemCompra.objects.filter(
                                            ordem_compra__requisicao_origem=ordem.requisicao_origem,
                                            produto=item_ordem.produto
                                        ).aggregate(total=Sum('quantidade_solicitada'))['total'] or quantidade_correta
                                        
                                        if not dry_run:
                                            item_requisicao = ItemRequisicaoCompraExterna.objects.create(
                                                requisicao=ordem.requisicao_origem,
                                                item=item_ordem.produto,
                                                quantidade_solicitada=quantidade_solicitada,
                                                quantidade_recebida=total_recebido_ordens,
                                                observacoes=f'Item recriado após correção de duplicação (origem: {ordem.requisicao_origem.observacoes.split("origem:")[-1].strip() if "origem:" in ordem.requisicao_origem.observacoes else ""})'
                                            )
                                            
                                            self.stdout.write(
                                                self.style.SUCCESS(
                                                    f'    Item recriado na requisição {ordem.requisicao_origem.codigo}: '
                                                    f'solicitada={quantidade_solicitada}, recebida={total_recebido_ordens}'
                                                )
                                            )
                                        else:
                                            self.stdout.write(
                                                self.style.WARNING(
                                                    f'    [DRY-RUN] Item seria recriado na requisição: '
                                                    f'solicitada={quantidade_solicitada}, recebida={total_recebido_ordens}'
                                                )
                                            )
                                except Exception as e:
                                    self.stdout.write(
                                        self.style.ERROR(f'    Erro ao atualizar requisição: {e}')
                                    )
                        else:
                            self.stdout.write(self.style.WARNING('    [DRY-RUN] Seria corrigido'))
                        
                        total_corrigido += 1
                    elif quantidade_movimentada < quantidade_correta:
                        self.stdout.write(
                            self.style.WARNING(
                                f'  Item: {item_ordem.produto.nome} - Quantidade movimentada ({quantidade_movimentada}) '
                                f'é menor que quantidade recebida ({quantidade_correta}). Verificar manualmente.'
                            )
                        )
                    else:
                        self.stdout.write(
                            f'  Item: {item_ordem.produto.nome} - OK (quantidade correta)'
                        )
                
                if ordem_tem_duplicacao:
                    total_ordens_processadas += 1
        
        # Resumo
        self.stdout.write(f'\n=== RESUMO ===')
        self.stdout.write(f'Total de itens corrigidos: {total_corrigido}')
        self.stdout.write(f'Total de ordens com correções: {total_ordens_processadas}')
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    '\n[DRY-RUN] Nenhuma alteração foi feita. '
                    'Execute sem --dry-run para aplicar as correções.'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('\nCorreções aplicadas com sucesso!')
            )

