"""
Comando de teste completo para requisição interna de stock
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from meuprojeto.empresa.models_stock import (
    RequisicaoStock, ItemRequisicaoStock, Item, StockItem, Sucursal, 
    TransferenciaStock, ItemTransferencia
)
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Testa o fluxo completo de uma requisição interna de stock'

    def add_arguments(self, parser):
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Remove a requisição de teste após o teste',
        )

    def handle(self, *args, **options):
        cleanup = options['cleanup']
        
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('TESTE COMPLETO DE REQUISICAO INTERNA'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        
        erros = []
        avisos = []
        requisicao_teste = None
        
        try:
            # 1. Preparar dados de teste
            self.stdout.write('\n[1] Preparando dados de teste...')
            
            # Buscar usuário admin
            try:
                usuario = User.objects.filter(is_superuser=True).first()
                if not usuario:
                    usuario = User.objects.first()
                if not usuario:
                    raise Exception("Nenhum usuario encontrado no sistema")
                self.stdout.write(self.style.SUCCESS(f'   [OK] Usuario de teste: {usuario.username}'))
            except Exception as e:
                erros.append(f"Erro ao buscar usuario: {e}")
                self._print_erros(erros, avisos)
                return
            
            # Buscar sucursais
            try:
                sucursal_origem = Sucursal.objects.first()
                sucursal_destino = Sucursal.objects.exclude(id=sucursal_origem.id).first() if Sucursal.objects.count() > 1 else sucursal_origem
                
                if not sucursal_origem:
                    raise Exception("Nenhuma sucursal encontrada no sistema")
                if not sucursal_destino:
                    avisos.append("Apenas uma sucursal encontrada. Usando a mesma para origem e destino.")
                    sucursal_destino = sucursal_origem
                
                self.stdout.write(self.style.SUCCESS(f'   [OK] Sucursal origem: {sucursal_origem.nome}'))
                self.stdout.write(self.style.SUCCESS(f'   [OK] Sucursal destino: {sucursal_destino.nome}'))
            except Exception as e:
                erros.append(f"Erro ao buscar sucursais: {e}")
                self._print_erros(erros, avisos)
                return
            
            # Buscar itens com stock disponível na sucursal destino
            try:
                itens_com_stock = []
                for stock_item in StockItem.objects.filter(
                    sucursal=sucursal_destino,
                    quantidade_atual__gt=0
                )[:3]:  # Pegar ate 3 itens
                    itens_com_stock.append(stock_item.item)
                
                if not itens_com_stock:
                    # Se nao ha stock, criar stock de teste para alguns itens
                    itens = Item.objects.filter(tipo='MATERIAL')[:3]
                    if not itens.exists():
                        itens = Item.objects.all()[:3]
                    
                    for item in itens:
                        stock_item, created = StockItem.objects.get_or_create(
                            item=item,
                            sucursal=sucursal_destino,
                            defaults={'quantidade_atual': 10}
                        )
                        if not created:
                            stock_item.quantidade_atual = 10
                            stock_item.save()
                        itens_com_stock.append(item)
                
                if not itens_com_stock:
                    raise Exception("Nenhum item disponivel para teste")
                
                self.stdout.write(self.style.SUCCESS(f'   [OK] Itens para teste: {len(itens_com_stock)}'))
                for item in itens_com_stock:
                    stock = StockItem.objects.get(item=item, sucursal=sucursal_destino)
                    self.stdout.write(f'      - {item.nome} ({item.codigo}): Stock = {stock.quantidade_atual}')
            except Exception as e:
                erros.append(f"Erro ao preparar itens: {e}")
                self._print_erros(erros, avisos)
                return
            
            # 2. Criar requisição
            self.stdout.write('\n[2] Criando requisicao...')
            try:
                with transaction.atomic():
                    requisicao_teste = RequisicaoStock.objects.create(
                        sucursal_origem=sucursal_origem,
                        sucursal_destino=sucursal_destino,
                        observacoes="Requisicao de teste automatico",
                        criado_por=usuario,
                        status='RASCUNHO'
                    )
                    self.stdout.write(self.style.SUCCESS(f'   [OK] Requisicao criada: {requisicao_teste.codigo}'))
                    self.stdout.write(f'      Status: {requisicao_teste.status}')
                    self.stdout.write(f'      Origem: {requisicao_teste.sucursal_origem.nome}')
                    self.stdout.write(f'      Destino: {requisicao_teste.sucursal_destino.nome if requisicao_teste.sucursal_destino else "Nao definido"}')
            except Exception as e:
                erros.append(f"Erro ao criar requisicao: {e}")
                import traceback
                traceback.print_exc()
                self._print_erros(erros, avisos)
                return
            
            # 3. Adicionar itens
            self.stdout.write('\n[3] Adicionando itens a requisicao...')
            try:
                itens_adicionados = []
                for item in itens_com_stock:
                    stock_destino = StockItem.objects.get(item=item, sucursal=sucursal_destino)
                    quantidade_solicitada = min(5, stock_destino.quantidade_atual)  # Solicitar ate 5 ou o disponivel
                    
                    item_req = ItemRequisicaoStock.objects.create(
                        requisicao=requisicao_teste,
                        item=item,
                        quantidade_solicitada=quantidade_solicitada,
                        quantidade_atendida=0,
                        observacoes=f"Item de teste - {item.nome}"
                    )
                    itens_adicionados.append(item_req)
                    self.stdout.write(f'   [OK] {item.nome}: {quantidade_solicitada} unidades')
                
                if not itens_adicionados:
                    erros.append("Nenhum item foi adicionado a requisicao")
                    self._print_erros(erros, avisos)
                    return
                
                # Verificar se a requisicao tem itens
                requisicao_teste.refresh_from_db()
                if not requisicao_teste.itens.exists():
                    erros.append("Requisicao criada mas itens nao foram salvos")
                    self._print_erros(erros, avisos)
                    return
                
                self.stdout.write(self.style.SUCCESS(f'   [OK] Total de itens: {requisicao_teste.itens.count()}'))
            except Exception as e:
                erros.append(f"Erro ao adicionar itens: {e}")
                import traceback
                traceback.print_exc()
                self._print_erros(erros, avisos)
                return
            
            # 4. Submeter requisicao
            self.stdout.write('\n[4] Submetendo requisicao (RASCUNHO -> PENDENTE)...')
            try:
                requisicao_teste.refresh_from_db()
                status_antes = requisicao_teste.status
                
                if requisicao_teste.status != 'RASCUNHO':
                    avisos.append(f"Status antes de submeter nao era RASCUNHO: {requisicao_teste.status}")
                
                # Simular submissao
                if requisicao_teste.promover_para_pendente():
                    requisicao_teste.refresh_from_db()
                    self.stdout.write(self.style.SUCCESS(f'   [OK] Requisicao submetida com sucesso'))
                    self.stdout.write(f'      Status: {status_antes} -> {requisicao_teste.status}')
                else:
                    erros.append("Falha ao promover requisicao para PENDENTE")
                    self._print_erros(erros, avisos)
                    return
            except Exception as e:
                erros.append(f"Erro ao submeter requisicao: {e}")
                import traceback
                traceback.print_exc()
                self._print_erros(erros, avisos)
                return
            
            # 5. Aprovar requisicao
            self.stdout.write('\n[5] Aprovando requisicao (PENDENTE -> APROVADA)...')
            try:
                requisicao_teste.refresh_from_db()
                if requisicao_teste.status != 'PENDENTE':
                    erros.append(f"Status nao e PENDENTE antes de aprovar: {requisicao_teste.status}")
                    self._print_erros(erros, avisos)
                    return
                
                requisicao_teste.status = 'APROVADA'
                requisicao_teste.data_aprovacao = timezone.now()
                requisicao_teste.aprovado_por = usuario
                requisicao_teste.save()
                
                requisicao_teste.refresh_from_db()
                self.stdout.write(self.style.SUCCESS(f'   [OK] Requisicao aprovada'))
                self.stdout.write(f'      Status: {requisicao_teste.status}')
                self.stdout.write(f'      Aprovado por: {requisicao_teste.aprovado_por.username if requisicao_teste.aprovado_por else "N/A"}')
                self.stdout.write(f'      Data aprovacao: {requisicao_teste.data_aprovacao}')
            except Exception as e:
                erros.append(f"Erro ao aprovar requisicao: {e}")
                import traceback
                traceback.print_exc()
                self._print_erros(erros, avisos)
                return
            
            # 6. Verificar transferencia
            self.stdout.write('\n[6] Verificando transferencia de stock...')
            try:
                # Verificar se ja existe transferencia (buscar pelo codigo que segue o padrao TRF{requisicao.codigo})
                codigo_transferencia = f"TRF{requisicao_teste.codigo}"
                transferencia = TransferenciaStock.objects.filter(codigo=codigo_transferencia).first()
                
                if not transferencia:
                    # Tambem verificar se ha transferencia relacionada pela observacao
                    transferencia = TransferenciaStock.objects.filter(
                        observacoes__icontains=f"requisicao {requisicao_teste.codigo}"
                    ).first()
                
                if not transferencia:
                    self.stdout.write(self.style.WARNING("   [INFO] Transferencia ainda nao foi criada (normal se nao foi executada)"))
                    self.stdout.write(f"      A transferencia seria criada quando a requisicao for processada para transferencia")
                else:
                    self.stdout.write(self.style.SUCCESS(f'   [OK] Transferencia encontrada: {transferencia.codigo}'))
                    self.stdout.write(f'      Status: {transferencia.status}')
                    self.stdout.write(f'      Itens: {transferencia.itens.count()}')
                    
                    # Verificar itens da transferencia
                    for item_transf in transferencia.itens.all():
                        self.stdout.write(f'      - {item_transf.item.nome if item_transf.item else "Item N/A"}: {item_transf.quantidade_solicitada} solicitados, {item_transf.quantidade_recebida} recebidos')
            except Exception as e:
                avisos.append(f"Erro ao verificar transferencia: {e}")
                import traceback
                traceback.print_exc()
            
            # 7. Verificar calculos de valores
            self.stdout.write('\n[7] Verificando calculos de valores...')
            try:
                for item_req in requisicao_teste.itens.all():
                    valor_total = item_req.valor_total
                    valor_atendido = item_req.valor_atendido
                    
                    # Verificar se os valores sao calculados corretamente
                    preco_esperado = item_req.item.preco_custo if item_req.item.preco_custo else 0
                    valor_total_esperado = item_req.quantidade_solicitada * preco_esperado
                    valor_atendido_esperado = item_req.quantidade_atendida * preco_esperado
                    
                    if abs(float(valor_total) - float(valor_total_esperado)) > 0.01:
                        erros.append(f"Valor total incorreto para {item_req.item.nome}: esperado {valor_total_esperado}, obtido {valor_total}")
                    else:
                        self.stdout.write(f'   [OK] {item_req.item.nome}: Valor total = {valor_total} MT')
                    
                    if abs(float(valor_atendido) - float(valor_atendido_esperado)) > 0.01:
                        erros.append(f"Valor atendido incorreto para {item_req.item.nome}: esperado {valor_atendido_esperado}, obtido {valor_atendido}")
            except Exception as e:
                erros.append(f"Erro ao verificar valores: {e}")
                import traceback
                traceback.print_exc()
            
            # 8. Verificar propriedades
            self.stdout.write('\n[8] Verificando propriedades da requisicao...')
            try:
                # Verificar quantidade_pendente
                for item_req in requisicao_teste.itens.all():
                    quantidade_pendente = item_req.quantidade_pendente
                    quantidade_pendente_esperada = item_req.quantidade_solicitada - item_req.quantidade_atendida
                    
                    if quantidade_pendente != quantidade_pendente_esperada:
                        erros.append(f"Quantidade pendente incorreta para {item_req.item.nome}: esperado {quantidade_pendente_esperada}, obtido {quantidade_pendente}")
                    else:
                        self.stdout.write(f'   [OK] {item_req.item.nome}: Pendente = {quantidade_pendente}')
                    
                    # Verificar totalmente_atendido
                    totalmente_atendido = item_req.totalmente_atendido
                    totalmente_atendido_esperado = item_req.quantidade_atendida >= item_req.quantidade_solicitada
                    
                    if totalmente_atendido != totalmente_atendido_esperado:
                        erros.append(f"totalmente_atendido incorreto para {item_req.item.nome}")
                    else:
                        self.stdout.write(f'   [OK] {item_req.item.nome}: Totalmente atendido = {totalmente_atendido}')
            except Exception as e:
                erros.append(f"Erro ao verificar propriedades: {e}")
                import traceback
                traceback.print_exc()
            
            # 9. Verificar integridade dos dados
            self.stdout.write('\n[9] Verificando integridade dos dados...')
            try:
                # Verificar se a requisicao tem sucursal destino definida
                requisicao_teste.refresh_from_db()
                if not requisicao_teste.sucursal_destino:
                    avisos.append("Sucursal destino nao esta definida na requisicao")
                else:
                    self.stdout.write(self.style.SUCCESS(f'   [OK] Sucursal destino definida: {requisicao_teste.sucursal_destino.nome}'))
                
                # Verificar se todos os itens tem item associado
                itens_sem_item = requisicao_teste.itens.filter(item__isnull=True)
                if itens_sem_item.exists():
                    erros.append(f"{itens_sem_item.count()} itens sem item associado")
                else:
                    self.stdout.write(self.style.SUCCESS(f'   [OK] Todos os itens tem item associado'))
                
                # Verificar se todos os itens tem quantidade_solicitada > 0
                itens_sem_quantidade = requisicao_teste.itens.filter(quantidade_solicitada__lte=0)
                if itens_sem_quantidade.exists():
                    erros.append(f"{itens_sem_quantidade.count()} itens com quantidade_solicitada <= 0")
                else:
                    self.stdout.write(self.style.SUCCESS(f'   [OK] Todas as quantidades solicitadas sao validas'))
            except Exception as e:
                erros.append(f"Erro ao verificar integridade: {e}")
                import traceback
                traceback.print_exc()
            
            # 10. Resumo final
            self.stdout.write('\n' + '=' * 80)
            self.stdout.write(self.style.SUCCESS('RESUMO DO TESTE'))
            self.stdout.write('=' * 80)
            self.stdout.write(f'Requisicao criada: {requisicao_teste.codigo}')
            self.stdout.write(f'Status final: {requisicao_teste.status}')
            self.stdout.write(f'Itens: {requisicao_teste.itens.count()}')
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
                self.stdout.write(self.style.SUCCESS('\n[OK] TESTE CONCLUIDO COM SUCESSO!'))
            else:
                self.stdout.write(self.style.ERROR('\n[ERRO] TESTE CONCLUIDO COM ERROS'))
            
            # Limpar requisicao de teste se solicitado
            if cleanup and requisicao_teste:
                self.stdout.write(f'\n[LIMPEZA] Removendo requisicao de teste {requisicao_teste.codigo}...')
                try:
                    requisicao_teste.delete()
                    self.stdout.write(self.style.SUCCESS('   [OK] Requisicao removida'))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'   [ERRO] Erro ao remover: {e}'))
            elif requisicao_teste:
                self.stdout.write(f'\n[INFO] Requisicao de teste mantida: {requisicao_teste.codigo}')
                self.stdout.write(f'        Execute com --cleanup para remover apos o teste')
            
        except Exception as e:
            erros.append(f"Erro geral no teste: {e}")
            import traceback
            traceback.print_exc()
            self._print_erros(erros, avisos)
    
    def _print_erros(self, erros, avisos):
        """Imprime erros e avisos"""
        if erros:
            self.stdout.write(self.style.ERROR('\nERROS:'))
            for i, erro in enumerate(erros, 1):
                self.stdout.write(self.style.ERROR(f'  {i}. {erro}'))
        
        if avisos:
            self.stdout.write(self.style.WARNING('\nAVISOS:'))
            for i, aviso in enumerate(avisos, 1):
                self.stdout.write(self.style.WARNING(f'  {i}. {aviso}'))

