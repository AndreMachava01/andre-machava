"""
Comando de teste para verificar se o recebimento de ordem de compra nao duplica stock
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from meuprojeto.empresa.models_stock import (
    OrdemCompra, ItemOrdemCompra, MovimentoItem, StockItem, Sucursal,
    TipoMovimentoStock, RequisicaoCompraExterna, ItemRequisicaoCompraExterna,
    Item, Fornecedor
)
from django.contrib.auth.models import User
from django.db.models import Sum


class Command(BaseCommand):
    help = 'Testa o recebimento de ordem de compra para verificar duplicacoes'

    def add_arguments(self, parser):
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Remove os dados de teste apos o teste',
        )

    def handle(self, *args, **options):
        cleanup = options['cleanup']
        
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('TESTE DE RECEBIMENTO DE ORDEM DE COMPRA'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        
        erros = []
        avisos = []
        ordem_teste = None
        requisicao_teste = None
        
        try:
            # 1. Preparar dados de teste
            self.stdout.write('\n[1] Preparando dados de teste...')
            
            # Buscar usuario
            usuario = User.objects.filter(is_superuser=True).first() or User.objects.first()
            if not usuario:
                erros.append("Nenhum usuario encontrado")
                self._print_resultado(erros, avisos)
                return
            
            # Buscar sucursal
            sucursal = Sucursal.objects.first()
            if not sucursal:
                erros.append("Nenhuma sucursal encontrada")
                self._print_resultado(erros, avisos)
                return
            
            # Buscar fornecedor
            fornecedor = Fornecedor.objects.filter(ativo=True).first()
            if not fornecedor:
                # Criar fornecedor de teste
                fornecedor = Fornecedor.objects.create(
                    nome="Fornecedor Teste",
                    nuit="123456789",
                    ativo=True
                )
                self.stdout.write(f'   [OK] Fornecedor de teste criado: {fornecedor.nome}')
            
            # Buscar item com preco de custo
            item = Item.objects.filter(preco_custo__gt=0).first()
            if not item:
                item = Item.objects.first()
                if item:
                    item.preco_custo = Decimal('100.00')
                    item.save()
            
            if not item:
                erros.append("Nenhum item encontrado")
                self._print_resultado(erros, avisos)
                return
            
            self.stdout.write(f'   [OK] Item de teste: {item.nome} ({item.codigo})')
            self.stdout.write(f'   [OK] Preco de custo: {item.preco_custo} MT')
            
            # Verificar stock inicial
            stock_inicial, created = StockItem.objects.get_or_create(
                item=item,
                sucursal=sucursal,
                defaults={'quantidade_atual': 0}
            )
            stock_antes = stock_inicial.quantidade_atual
            self.stdout.write(f'   [OK] Stock inicial: {stock_antes}')
            
            # 2. Criar requisicao de compra externa
            self.stdout.write('\n[2] Criando requisicao de compra externa...')
            try:
                requisicao_teste = RequisicaoCompraExterna.objects.create(
                    sucursal_solicitante=sucursal,
                    observacoes="Requisicao de teste para recebimento",
                    criado_por=usuario,
                    status='APROVADA'
                )
                self.stdout.write(f'   [OK] Requisicao criada: {requisicao_teste.codigo}')
            except Exception as e:
                erros.append(f"Erro ao criar requisicao: {e}")
                self._print_resultado(erros, avisos)
                return
            
            # 3. Adicionar item a requisicao
            self.stdout.write('\n[3] Adicionando item a requisicao...')
            try:
                quantidade_solicitada = 10
                item_req = ItemRequisicaoCompraExterna.objects.create(
                    requisicao=requisicao_teste,
                    item=item,
                    quantidade_solicitada=quantidade_solicitada,
                    quantidade_recebida=0,
                    preco_unitario_estimado=item.preco_custo
                )
                self.stdout.write(f'   [OK] Item adicionado: {quantidade_solicitada} unidades')
            except Exception as e:
                erros.append(f"Erro ao adicionar item: {e}")
                self._print_resultado(erros, avisos)
                return
            
            # 4. Criar ordem de compra
            self.stdout.write('\n[4] Criando ordem de compra...')
            try:
                ordem_teste = OrdemCompra.objects.create(
                    numero_cotacao="COT-TEST-001",
                    fornecedor=fornecedor,
                    requisicao_origem=requisicao_teste,
                    sucursal_destino=sucursal,
                    observacoes="Ordem de teste",
                    criado_por=usuario,
                    status='APROVADA',
                    tipo='COMPRA_EXTERNA',
                    cotacao_aprovada="COT-TEST-001",
                    numero_fatura="FAT-TEST-001",
                    contato_externo=fornecedor.nome,
                    empresa_externa=fornecedor.nome,
                    email_externo=fornecedor.email or 'teste@teste.com',
                    telefone_externo=fornecedor.telefone or '123456789'
                )
                self.stdout.write(f'   [OK] Ordem criada: {ordem_teste.codigo}')
            except Exception as e:
                erros.append(f"Erro ao criar ordem: {e}")
                import traceback
                traceback.print_exc()
                self._print_resultado(erros, avisos)
                return
            
            # 5. Adicionar item a ordem
            self.stdout.write('\n[5] Adicionando item a ordem...')
            try:
                preco_unitario = item.preco_custo
                item_ordem = ItemOrdemCompra.objects.create(
                    ordem_compra=ordem_teste,
                    produto=item,
                    quantidade_solicitada=quantidade_solicitada,
                    quantidade_recebida=0,
                    preco_unitario=preco_unitario,
                    categoria=item.categoria.nome if item.categoria else 'Geral',
                    descricao=item.nome,
                    especificacoes=item.descricao or 'Sem especificacoes'
                )
                self.stdout.write(f'   [OK] Item adicionado: {quantidade_solicitada} unidades a {preco_unitario} MT')
            except Exception as e:
                erros.append(f"Erro ao adicionar item a ordem: {e}")
                import traceback
                traceback.print_exc()
                self._print_resultado(erros, avisos)
                return
            
            # 6. Verificar stock antes do recebimento
            self.stdout.write('\n[6] Verificando stock antes do recebimento...')
            stock_inicial.refresh_from_db()
            stock_antes_recebimento = stock_inicial.quantidade_atual
            self.stdout.write(f'   [OK] Stock antes: {stock_antes_recebimento}')
            
            # 7. Simular recebimento (criar movimento)
            self.stdout.write('\n[7] Simulando recebimento da ordem...')
            try:
                tipo_entrada = TipoMovimentoStock.objects.get(codigo='ENT_COMPRA')
                
                # Verificar se ja existem movimentos para esta ordem
                movimentos_existentes = MovimentoItem.objects.filter(
                    observacoes__icontains=f'Recebimento da ordem {ordem_teste.codigo}'
                ).count()
                
                if movimentos_existentes > 0:
                    avisos.append(f"Ja existem {movimentos_existentes} movimento(s) para esta ordem")
                    self.stdout.write(self.style.WARNING(f'   [AVISO] Movimentos existentes: {movimentos_existentes}'))
                
                # Criar movimento (simula o recebimento)
                with transaction.atomic():
                    # Recarregar ordem
                    ordem_teste.refresh_from_db()
                    
                    if ordem_teste.status == 'RECEBIDA':
                        avisos.append("Ordem ja foi recebida anteriormente")
                    else:
                        # Atualizar quantidade recebida
                        item_ordem.quantidade_recebida = quantidade_solicitada
                        item_ordem.save()
                        
                        # Atualizar preco de custo
                        if item_ordem.preco_unitario and item_ordem.preco_unitario > 0:
                            item.preco_custo = item_ordem.preco_unitario
                            item.save(update_fields=['preco_custo'])
                        
                        # Criar movimento (signal atualizara stock automaticamente)
                        movimento = MovimentoItem.objects.create(
                            item=item,
                            sucursal=sucursal,
                            tipo_movimento=tipo_entrada,
                            quantidade=quantidade_solicitada,
                            preco_unitario=item_ordem.preco_unitario,
                            observacoes=f'Recebimento da ordem {ordem_teste.codigo} - Fatura: {ordem_teste.numero_fatura}',
                            usuario=usuario
                        )
                        
                        # Marcar ordem como recebida
                        ordem_teste.status = 'RECEBIDA'
                        ordem_teste.data_recebimento = timezone.now()
                        ordem_teste.save()
                        
                        self.stdout.write(f'   [OK] Movimento criado: {movimento.codigo}')
                        self.stdout.write(f'   [OK] Ordem marcada como RECEBIDA')
            except Exception as e:
                erros.append(f"Erro ao simular recebimento: {e}")
                import traceback
                traceback.print_exc()
                self._print_resultado(erros, avisos)
                return
            
            # 8. Verificar stock apos recebimento
            self.stdout.write('\n[8] Verificando stock apos recebimento...')
            stock_inicial.refresh_from_db()
            stock_depois = stock_inicial.quantidade_atual
            self.stdout.write(f'   [OK] Stock depois: {stock_depois}')
            
            # Calcular stock esperado
            stock_esperado = stock_antes_recebimento + quantidade_solicitada
            self.stdout.write(f'   [OK] Stock esperado: {stock_esperado}')
            
            # Verificar se houve duplicacao
            if stock_depois > stock_esperado:
                erros.append(f"DUPLICACAO DETECTADA! Stock atual ({stock_depois}) maior que esperado ({stock_esperado})")
                diferenca = stock_depois - stock_esperado
                self.stdout.write(self.style.ERROR(f'   [ERRO] Duplicacao de {diferenca} unidades'))
            elif stock_depois < stock_esperado:
                avisos.append(f"Stock atual ({stock_depois}) menor que esperado ({stock_esperado})")
                self.stdout.write(self.style.WARNING(f'   [AVISO] Stock menor que esperado'))
            else:
                self.stdout.write(self.style.SUCCESS(f'   [OK] Stock correto! Nenhuma duplicacao'))
            
            # 9. Verificar movimentos
            self.stdout.write('\n[9] Verificando movimentos de entrada...')
            try:
                movimentos = MovimentoItem.objects.filter(
                    item=item,
                    sucursal=sucursal,
                    tipo_movimento__codigo='ENT_COMPRA',
                    observacoes__icontains=f'Recebimento da ordem {ordem_teste.codigo}'
                )
                
                quantidade_total_movimentada = movimentos.aggregate(total=Sum('quantidade'))['total'] or 0
                self.stdout.write(f'   [OK] Movimentos encontrados: {movimentos.count()}')
                self.stdout.write(f'   [OK] Quantidade total movimentada: {quantidade_total_movimentada}')
                
                if quantidade_total_movimentada > quantidade_solicitada:
                    erros.append(f"DUPLICACAO NOS MOVIMENTOS! Quantidade movimentada ({quantidade_total_movimentada}) maior que solicitada ({quantidade_solicitada})")
                    self.stdout.write(self.style.ERROR(f'   [ERRO] Duplicacao de {quantidade_total_movimentada - quantidade_solicitada} unidades nos movimentos'))
                elif quantidade_total_movimentada < quantidade_solicitada:
                    avisos.append(f"Quantidade movimentada ({quantidade_total_movimentada}) menor que solicitada ({quantidade_solicitada})")
                else:
                    self.stdout.write(self.style.SUCCESS(f'   [OK] Quantidade movimentada correta'))
                
                # Listar movimentos
                for mov in movimentos:
                    self.stdout.write(f'      - {mov.codigo}: {mov.quantidade} unidades em {mov.data_movimento}')
            except Exception as e:
                erros.append(f"Erro ao verificar movimentos: {e}")
                import traceback
                traceback.print_exc()
            
            # 10. Tentar receber novamente (teste de protecao)
            self.stdout.write('\n[10] Testando protecao contra recebimento duplo...')
            try:
                ordem_teste.refresh_from_db()
                if ordem_teste.status != 'RECEBIDA':
                    avisos.append("Ordem nao esta como RECEBIDA apos o primeiro recebimento")
                else:
                    # Tentar criar movimento novamente (simula tentativa de duplicacao)
                    movimentos_antes = MovimentoItem.objects.filter(
                        observacoes__icontains=f'Recebimento da ordem {ordem_teste.codigo}'
                    ).count()
                    
                    # Verificar se a protecao funciona
                    movimentos_existentes = MovimentoItem.objects.filter(
                        observacoes__icontains=f'Recebimento da ordem {ordem_teste.codigo}'
                    ).count()
                    
                    if movimentos_existentes > movimentos_antes:
                        erros.append("Protecao contra duplicacao nao funcionou - movimento duplicado foi criado")
                    else:
                        self.stdout.write(self.style.SUCCESS(f'   [OK] Protecao funcionando - {movimentos_existentes} movimento(s) (esperado: {movimentos_antes})'))
            except Exception as e:
                avisos.append(f"Erro ao testar protecao: {e}")
            
            # 11. Verificar preco de custo atualizado
            self.stdout.write('\n[11] Verificando atualizacao de preco de custo...')
            try:
                item.refresh_from_db()
                if item.preco_custo == item_ordem.preco_unitario:
                    self.stdout.write(self.style.SUCCESS(f'   [OK] Preco de custo atualizado: {item.preco_custo} MT'))
                else:
                    avisos.append(f"Preco de custo nao foi atualizado. Atual: {item.preco_custo}, Esperado: {item_ordem.preco_unitario}")
            except Exception as e:
                avisos.append(f"Erro ao verificar preco de custo: {e}")
            
            # Resumo final
            self.stdout.write('\n' + '=' * 80)
            self.stdout.write(self.style.SUCCESS('RESUMO DO TESTE'))
            self.stdout.write('=' * 80)
            self.stdout.write(f'Ordem criada: {ordem_teste.codigo}')
            self.stdout.write(f'Item: {item.nome}')
            self.stdout.write(f'Quantidade recebida: {quantidade_solicitada}')
            self.stdout.write(f'Stock antes: {stock_antes_recebimento}')
            self.stdout.write(f'Stock depois: {stock_depois}')
            self.stdout.write(f'Stock esperado: {stock_esperado}')
            self.stdout.write(f'Erros encontrados: {len(erros)}')
            self.stdout.write(f'Avisos: {len(avisos)}')
            
            if erros:
                self.stdout.write(self.style.ERROR('\nERROS:'))
                for i, erro in enumerate(erros, 1):
                    self.stdout.write(self.style.ERROR(f'  {i}. {erro}'))
            
            if avisos:
                self.stdout.write(self.style.WARNING('\nAVISOS:'))
                for i, aviso in enumerate(avisos, 1):
                    self.stdout.write(self.style.WARNING(f'  {i}. {aviso}'))
            
            if not erros:
                self.stdout.write(self.style.SUCCESS('\n[OK] TESTE CONCLUIDO - SEM DUPLICACOES!'))
            else:
                self.stdout.write(self.style.ERROR('\n[ERRO] TESTE CONCLUIDO COM ERROS'))
            
            # Limpar dados de teste
            if cleanup:
                self.stdout.write(f'\n[LIMPEZA] Removendo dados de teste...')
                try:
                    if ordem_teste:
                        ordem_teste.delete()
                        self.stdout.write(f'   [OK] Ordem removida')
                    if requisicao_teste:
                        requisicao_teste.delete()
                        self.stdout.write(f'   [OK] Requisicao removida')
                    
                    # Reverter stock se necessario
                    if stock_depois != stock_antes_recebimento:
                        stock_inicial.quantidade_atual = stock_antes_recebimento
                        stock_inicial.save()
                        self.stdout.write(f'   [OK] Stock revertido para {stock_antes_recebimento}')
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'   [ERRO] Erro ao limpar: {e}'))
            else:
                self.stdout.write(f'\n[INFO] Dados de teste mantidos')
                self.stdout.write(f'        Ordem: {ordem_teste.codigo if ordem_teste else "N/A"}')
                self.stdout.write(f'        Execute com --cleanup para remover')
            
        except Exception as e:
            erros.append(f"Erro geral no teste: {e}")
            import traceback
            traceback.print_exc()
            self._print_resultado(erros, avisos)
    
    def _print_resultado(self, erros, avisos):
        """Imprime erros e avisos"""
        if erros:
            self.stdout.write(self.style.ERROR('\nERROS:'))
            for i, erro in enumerate(erros, 1):
                self.stdout.write(self.style.ERROR(f'  {i}. {erro}'))
        
        if avisos:
            self.stdout.write(self.style.WARNING('\nAVISOS:'))
            for i, aviso in enumerate(avisos, 1):
                self.stdout.write(self.style.WARNING(f'  {i}. {aviso}'))

