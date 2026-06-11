from django.shortcuts import render, get_object_or_404, redirect
from django.http import Http404
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Sum, F, Count
from django.http import JsonResponse, HttpResponseBadRequest
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect, csrf_exempt
from django.db import transaction
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

from .models_stock import (
        RequisicaoStock, ItemRequisicaoStock, RequisicaoCompraExterna, ItemRequisicaoCompraExterna, Item, StockItem, Sucursal, OrdemCompra, ItemOrdemCompra, TransferenciaStock, TipoMovimentoStock, MovimentoItem, HistoricoEnvioEmail
)
from .models_base import Sucursal
from .decorators import require_stock_access, require_sucursal_access, get_user_sucursais
from .services.email_service import EmailNotificationService as EmailService

# =============================================================================
# VIEWS DE REQUISIÇÕES DE STOCK
# =============================================================================

@login_required
@require_stock_access
def requisicoes_list(request):
    """Lista de requisições de stock"""
    # Obter parâmetros de filtro
    search_query = request.GET.get('search', '').strip()
    status = request.GET.get('status', '').strip()
    sucursal_id = request.GET.get('sucursal', '').strip()
    
    # Buscar requisições de stock
    requisicoes_stock = RequisicaoStock.objects.select_related(
        'sucursal_origem', 'sucursal_destino', 'criado_por', 'aprovado_por'
    ).prefetch_related('itens').order_by('-data_criacao')
    
    # Buscar requisições de compra externa
    requisicoes_compra = RequisicaoCompraExterna.objects.select_related(
        'sucursal_solicitante', 'criado_por'
    ).prefetch_related('itens').order_by('-data_criacao')
    
    # Aplicar filtros às requisições de stock
    if search_query:
        requisicoes_stock = requisicoes_stock.filter(
            Q(codigo__icontains=search_query) |
            Q(sucursal_origem__nome__icontains=search_query) |
            Q(sucursal_destino__nome__icontains=search_query) |
            Q(observacoes__icontains=search_query)
        )
    
    if status:
        requisicoes_stock = requisicoes_stock.filter(status=status)
    
    if sucursal_id:
        requisicoes_stock = requisicoes_stock.filter(
            Q(sucursal_origem_id=sucursal_id) | Q(sucursal_destino_id=sucursal_id)
        )
    
    # Aplicar filtros às requisições de compra externa
    if search_query:
        requisicoes_compra = requisicoes_compra.filter(
            Q(codigo__icontains=search_query) |
            Q(sucursal_solicitante__nome__icontains=search_query) |
            Q(observacoes__icontains=search_query)
        )
    
    if status:
        requisicoes_compra = requisicoes_compra.filter(status=status)
    
    if sucursal_id:
        requisicoes_compra = requisicoes_compra.filter(sucursal_solicitante_id=sucursal_id)
    
    # Estatísticas
    total_requisicoes_stock = requisicoes_stock.count()
    total_requisicoes_compra = requisicoes_compra.count()
    total_requisicoes = total_requisicoes_stock + total_requisicoes_compra
    
    requisicoes_pendentes = requisicoes_stock.filter(status='PENDENTE').count() + requisicoes_compra.filter(status='PENDENTE').count()
    requisicoes_aprovadas = requisicoes_stock.filter(status='APROVADA').count() + requisicoes_compra.filter(status='APROVADA').count()
    requisicoes_atendidas = requisicoes_stock.filter(status='ATENDIDA').count() + requisicoes_compra.filter(status='FINALIZADA').count()
    
    # Combinar requisições para paginação
    from itertools import chain
    todas_requisicoes = list(chain(requisicoes_stock, requisicoes_compra))
    
    # Paginação
    paginator = Paginator(todas_requisicoes, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Obter sucursais para o filtro
    sucursais = Sucursal.objects.all().order_by('nome')
    
    context = {
        'requisicoes': page_obj,
        'requisicoes_stock': requisicoes_stock,
        'requisicoes_compra': requisicoes_compra,
        'total_requisicoes': total_requisicoes,
        'total_requisicoes_stock': total_requisicoes_stock,
        'total_requisicoes_compra': total_requisicoes_compra,
        'requisicoes_pendentes': requisicoes_pendentes,
        'requisicoes_aprovadas': requisicoes_aprovadas,
        'requisicoes_atendidas': requisicoes_atendidas,
        'sucursais': sucursais,
        'search_query': search_query,
        'status': status,
        'sucursal_id': sucursal_id,
    }
    
    return render(request, 'stock/requisicoes/list.html', context)


@login_required
@require_stock_access
@require_sucursal_access
@require_http_methods(["GET", "POST"])
def requisicao_create(request):
    """Criar nova requisição de stock"""
    # Limpar mensagens antigas para evitar confusão
    if request.method == 'GET':
        messages.get_messages(request).used = True
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                tipo_requisicao = request.POST.get('tipo_requisicao', 'interna')
                sucursal_solicitante_id = request.POST.get('sucursal_solicitante')
                sucursal_fornecedora_id = request.POST.get('sucursal_fornecedora')
                observacoes = request.POST.get('observacoes', '')
                prioridade_manual = request.POST.get('prioridade', '')  # Prioridade manual se definida
                
                # Armazenar prioridade manual na session para uso posterior
                if prioridade_manual:
                    request.session['prioridade_manual'] = prioridade_manual
                
                if not sucursal_solicitante_id:
                    messages.error(request, 'Sucursal solicitante é obrigatória.')
                    return redirect('stock:requisicoes:create')
                
                if tipo_requisicao == 'interna':
                    # Criar requisição interna (sucursal destino será definida por item)
                    requisicao = RequisicaoStock.objects.create(
                        sucursal_origem_id=sucursal_solicitante_id,  # Quem solicita
                        sucursal_destino_id=None,  # Será definida quando adicionar itens
                        observacoes=observacoes,
                        criado_por=request.user
                    )
                else:  # tipo_requisicao == 'externa'
                    # Criar requisição de compra externa
                    requisicao = RequisicaoCompraExterna.objects.create(
                        sucursal_solicitante_id=sucursal_solicitante_id,
                        observacoes=observacoes,
                        criado_por=request.user
                    )
                    
                    # Se há um item pré-selecionado, adicionar automaticamente
                    item_id = request.GET.get('item')
                    if item_id:
                        try:
                            item = Item.objects.get(id=item_id)
                            ItemRequisicaoCompraExterna.objects.create(
                                requisicao=requisicao,
                                item=item,
                                quantidade_solicitada=1,  # Quantidade padrão
                                observacoes=f"Item adicionado automaticamente do stock baixo"
                            )
                        except Item.DoesNotExist:
                            pass
                
                # Se há um item pré-selecionado, redirecionar para adicionar item rapidamente
                item_id = request.GET.get('item')
                if item_id:
                    try:
                        item = Item.objects.get(id=item_id)
                        if tipo_requisicao == 'interna':
                            # Redirecionar para a página de adicionar item rapidamente
                            return redirect(f'/stock/requisicoes/{requisicao.id}/quick-add-item/?item={item_id}')
                        else:
                            # Para compra externa, já foi adicionado automaticamente, ir para detalhes
                            pass  # Continuar para o redirecionamento normal
                    except Item.DoesNotExist:
                        messages.warning(request, 'Item pré-selecionado não encontrado.')
                
                if tipo_requisicao == 'interna':
                    return redirect('stock:requisicoes:detail', id=requisicao.id)
                else:
                    # Para compra externa, redirecionar para página de detalhes onde pode adicionar mais itens
                    return redirect('stock:requisicoes:compra_externa_detail', id=requisicao.id)
                
        except Exception as e:
            logger.error(f"Erro ao criar requisição: {e}")
            messages.error(request, 'Erro ao criar requisição.')
            return redirect('stock:requisicoes:create')
    
    # GET - Mostrar formulário
    sucursais = get_user_sucursais(request, for_modification=False)
    
    # Obter parâmetros da URL para pré-seleção
    sucursal_solicitante_id = request.GET.get('sucursal_solicitante', '')
    item_id = request.GET.get('item', '')
    
    # Buscar sucursal solicitante se especificada
    sucursal_solicitante = None
    if sucursal_solicitante_id:
        try:
            sucursal_solicitante = Sucursal.objects.get(id=sucursal_solicitante_id)
        except Sucursal.DoesNotExist:
            pass
    
    # Buscar item se especificado
    item = None
    sucursal_fornecedora_sugerida = None
    if item_id:
        try:
            item = Item.objects.get(id=item_id)
            # Sugerir sucursal fornecedora baseada no stock disponível
            # Buscar sucursal que tem mais stock deste item
            stock_items = StockItem.objects.filter(
                item=item,
                quantidade_atual__gt=0
            ).select_related('sucursal').order_by('-quantidade_atual')
            
            if stock_items.exists():
                sucursal_fornecedora_sugerida = stock_items.first().sucursal
        except Item.DoesNotExist:
            pass
    
    context = {
        'sucursais': sucursais,
        'sucursal_solicitante_pre_selecionada': sucursal_solicitante,
        'sucursal_fornecedora_sugerida': sucursal_fornecedora_sugerida,
        'item_pre_selecionado': item,
    }
    
    return render(request, 'stock/requisicoes/create.html', context)


@login_required
@require_stock_access
def requisicao_detail(request, id):
    """Detalhes de uma requisição de stock"""
    # Primeiro, tentar encontrar como RequisicaoStock
    try:
        requisicao = RequisicaoStock.objects.select_related(
            'sucursal_origem', 'sucursal_destino', 'criado_por', 'aprovado_por'
        ).prefetch_related('itens__item').get(id=id)
        
        # Buscar transferência associada se existir
        transferencia_associada = None
        try:
            from .models_stock import TransferenciaStock
            codigo_transferencia = f"TRF{requisicao.codigo}"
            transferencia_associada = TransferenciaStock.objects.get(
                codigo=codigo_transferencia
            )
        except TransferenciaStock.DoesNotExist:
            pass
        
        context = {
            'requisicao': requisicao,
            'transferencia_associada': transferencia_associada,
        }
        return render(request, 'stock/requisicoes/detail.html', context)
        
    except RequisicaoStock.DoesNotExist:
        # Se não for RequisicaoStock, verificar se é RequisicaoCompraExterna
        try:
            RequisicaoCompraExterna.objects.get(id=id)
            # Redirecionar para a URL correta de compra externa
            return redirect('stock:requisicoes:compra_externa_detail', id=id)
        except RequisicaoCompraExterna.DoesNotExist:
            # Se não for nenhum dos dois, mostrar erro 404 com informações úteis
            from django.contrib import messages
            messages.error(request, f'A requisição #{id} não foi encontrada. Pode ter sido excluída ou nunca existiu.')
            return redirect('stock:requisicoes:list')

@login_required
@require_http_methods(["GET", "POST"])
def compra_externa_create_order(request, id):
    """Criar ordem de compra a partir de requisição externa"""
    try:
        requisicao = get_object_or_404(RequisicaoCompraExterna, id=id)
        
        if requisicao.status != 'APROVADA':
            messages.error(request, 'Apenas requisições aprovadas podem gerar ordens de compra.')
            return redirect('stock:requisicoes:compra_externa_detail', id=id)
        
        # Verificar se a requisição tem itens
        itens_count = ItemRequisicaoCompraExterna.objects.filter(requisicao=requisicao).count()
        if itens_count == 0:
            messages.error(request, 'Não é possível criar ordem de compra para uma requisição sem itens.')
            return redirect('stock:requisicoes:compra_externa_detail', id=id)
        
        # Verificar se já existe uma ordem de compra para esta requisição
        if hasattr(requisicao, 'ordem_compra'):
            messages.warning(request, 'Já existe uma ordem de compra para esta requisição.')
            return redirect('stock:requisicoes:compra_externa_detail', id=id)
        
        if request.method == 'POST':
            numero_cotacao = request.POST.get('numero_cotacao')
            fornecedor_id = request.POST.get('fornecedor')
            observacoes = request.POST.get('observacoes', '')
            
            logger.info(f"Criando ordem de compra - Requisição: {requisicao.id}, Cotação: {numero_cotacao}, Fornecedor: {fornecedor_id}")
            
            if not numero_cotacao or not fornecedor_id:
                messages.error(request, 'Número da cotação e fornecedor são obrigatórios.')
                return redirect('stock:requisicoes:compra_externa_create_order', id=id)
            
            from .models_stock import Fornecedor
            
            # Lidar com fornecedores não registrados
            if fornecedor_id == 'novo_fornecedor':
                # Criar novo fornecedor
                novo_nome = request.POST.get('novo_fornecedor_nome', '').strip()
                novo_nuit = request.POST.get('novo_fornecedor_nuit', '').strip()
                
                if not novo_nome:
                    messages.error(request, 'Nome do fornecedor é obrigatório.')
                    return redirect('stock:requisicoes:compra_externa_create_order', id=id)
                
                if not novo_nuit:
                    messages.error(request, 'NUIT é obrigatório.')
                    return redirect('stock:requisicoes:compra_externa_create_order', id=id)
                
                if not novo_nuit.isdigit() or len(novo_nuit) != 9:
                    messages.error(request, 'NUIT deve ter exatamente 9 dígitos.')
                    return redirect('stock:requisicoes:compra_externa_create_order', id=id)
                
                # Verificar se NUIT já existe
                if Fornecedor.objects.filter(nuit=novo_nuit).exists():
                    messages.error(request, f'NUIT {novo_nuit} já está registrado no sistema.')
                    return redirect('stock:requisicoes:compra_externa_create_order', id=id)
                
                fornecedor = Fornecedor.objects.create(
                    nome=novo_nome,
                    nuit=novo_nuit,
                    email=request.POST.get('novo_fornecedor_email', ''),
                    telefone=request.POST.get('novo_fornecedor_telefone', ''),
                    endereco=request.POST.get('novo_fornecedor_endereco', ''),
                    ativo=True
                )
                logger.info(f"Novo fornecedor criado: {fornecedor.nome} - NUIT: {fornecedor.nuit} (ID: {fornecedor.id})")
                
            elif fornecedor_id == 'externo_temporario':
                # Criar fornecedor externo temporário
                externo_nome = request.POST.get('externo_nome', '').strip()
                externo_nuit = request.POST.get('externo_nuit', '').strip()
                
                if not externo_nome:
                    messages.error(request, 'Nome da empresa/fornecedor externo é obrigatório.')
                    return redirect('stock:requisicoes:compra_externa_create_order', id=id)
                
                if not externo_nuit:
                    messages.error(request, 'NUIT é obrigatório.')
                    return redirect('stock:requisicoes:compra_externa_create_order', id=id)
                
                if not externo_nuit.isdigit() or len(externo_nuit) != 9:
                    messages.error(request, 'NUIT deve ter exatamente 9 dígitos.')
                    return redirect('stock:requisicoes:compra_externa_create_order', id=id)
                
                # Verificar se NUIT já existe
                if Fornecedor.objects.filter(nuit=externo_nuit).exists():
                    messages.error(request, f'NUIT {externo_nuit} já está registrado no sistema.')
                    return redirect('stock:requisicoes:compra_externa_create_order', id=id)
                
                fornecedor = Fornecedor.objects.create(
                    nome=f"[EXTERNO] {externo_nome}",
                    nuit=externo_nuit,
                    email=request.POST.get('externo_email', ''),
                    telefone=request.POST.get('externo_telefone', ''),
                    ativo=True
                )
                logger.info(f"Fornecedor_externo temporário criado: {fornecedor.nome} - NUIT: {fornecedor.nuit} (ID: {fornecedor.id})")
                
            else:
                # Fornecedor existente
                fornecedor = get_object_or_404(Fornecedor, id=fornecedor_id)
                logger.info(f"Fornecedor existente selecionado: {fornecedor.nome} (ID: {fornecedor.id})")
            
            # Criar ordem de compra
            try:
                ordem_compra = OrdemCompra.objects.create(
                    numero_cotacao=numero_cotacao,
                    fornecedor=fornecedor,
                    requisicao_origem=requisicao,
                    sucursal_destino=requisicao.sucursal_solicitante,
                    observacoes=observacoes,
                    criado_por=request.user,
                    # Campos obrigatórios externos (valores padrão do modelo)
                    contato_externo=fornecedor.nome if fornecedor else 'N/A',
                    empresa_externa=fornecedor.nome if fornecedor else 'N/A',
                    email_externo=fornecedor.email if fornecedor and fornecedor.email else 'N/A',
                    telefone_externo=fornecedor.telefone if fornecedor and fornecedor.telefone else 'N/A',
                    tipo='COMPRA_EXTERNA',
                    cotacao_aprovada=numero_cotacao,
                    numero_fatura='PENDENTE'
                )
                logger.info(f"Ordem de compra criada: {ordem_compra.codigo}")
            except Exception as e:
                logger.error(f"Erro ao criar ordem de compra: {e}")
                messages.error(request, f'Erro ao criar ordem de compra: {e}')
                return redirect('stock:requisicoes:compra_externa_create_order', id=id)
            
            # Processar itens selecionados
            itens_selecionados = request.POST.getlist('item_selecionado')
            quantidades = request.POST.getlist('quantidade')
            precos = request.POST.getlist('preco_unitario')
            
            logger.info(f"Itens selecionados: {itens_selecionados}")
            logger.info(f"Quantidades: {quantidades}")
            logger.info(f"Preços: {precos}")
            
            # Verificar se há itens selecionados
            if not itens_selecionados:
                messages.error(request, 'Nenhum item foi selecionado.')
                return redirect('stock:requisicoes:compra_externa_create_order', id=id)
            
            itens_processados = 0
            
            for i, item_id in enumerate(itens_selecionados):
                try:
                    item_requisicao = get_object_or_404(ItemRequisicaoCompraExterna, id=item_id)
                    quantidade = Decimal(quantidades[i]) if quantidades[i] else Decimal('0')
                    preco_unitario = Decimal(precos[i]) if precos[i] else Decimal('0')
                    
                    logger.info(f"Processando item {item_id}: quantidade={quantidade}, preço={preco_unitario}")
                    
                    if quantidade > 0 and preco_unitario > 0:
                        # Criar item da ordem de compra
                        # Usar o modelo Item unificado (correção migração)
                        
                        ItemOrdemCompra.objects.create(
                            ordem_compra=ordem_compra,
                            produto=item_requisicao.item,  # Usar modelo Item unificado
                            quantidade_solicitada=int(quantidade),
                            preco_unitario=preco_unitario,
                            observacoes=f"Item da requisição {requisicao.codigo}",
                            categoria=item_requisicao.item.categoria.nome if item_requisicao.item.categoria else 'Geral',
                            descricao=item_requisicao.item.nome,
                            especificacoes=item_requisicao.item.descricao or 'Sem especificações'
                        )
                        
                        # Atualizar quantidade na requisição (conversão parcial)
                        item_requisicao.quantidade_solicitada -= quantidade
                        if item_requisicao.quantidade_solicitada <= 0:
                            item_requisicao.delete()  # Remove item completamente processado
                        else:
                            item_requisicao.save()
                        
                        itens_processados += 1
                        
                except (ValueError, IndexError) as e:
                    logger.error(f"Erro ao processar item {item_id}: {e}")
                    continue
            
            logger.info(f"Itens processados: {itens_processados}")
            
            if itens_processados > 0:
                # Verificar se ainda há itens na requisição
                itens_restantes = ItemRequisicaoCompraExterna.objects.filter(requisicao=requisicao).count()
                
                logger.info(f"Itens restantes na requisição: {itens_restantes}")
                
                if itens_restantes == 0:
                    # Todos os itens foram processados, finalizar requisição
                    requisicao.status = 'FINALIZADA'
                    requisicao.save()
                    logger.info(f"Requisição {requisicao.codigo} finalizada")
                    messages.success(request, f'Ordem de compra {ordem_compra.codigo} criada com sucesso! Requisição finalizada.')
                else:
                    logger.info(f"Requisição {requisicao.codigo} mantida com {itens_restantes} itens restantes")
                    messages.success(request, f'Ordem de compra {ordem_compra.codigo} criada com sucesso! {itens_restantes} itens restantes na requisição.')
                
                # Redirecionar para pré-visualização da ordem de compra
                return redirect('stock:requisicoes:ordem_compra_preview', id=ordem_compra.id)
            else:
                ordem_compra.delete()  # Remove ordem vazia
                logger.error("Nenhum item válido foi processado")
                messages.error(request, 'Nenhum item válido foi selecionado.')
                return redirect('stock:requisicoes:compra_externa_create_order', id=id)
        
        # Buscar fornecedores disponíveis
        from .models_stock import Fornecedor
        fornecedores = Fornecedor.objects.filter(ativo=True).order_by('nome')
        
        # Buscar itens da requisição
        itens_requisicao = ItemRequisicaoCompraExterna.objects.filter(requisicao=requisicao)
        
        context = {
            'requisicao': requisicao,
            'fornecedores': fornecedores,
            'itens_requisicao': itens_requisicao,
        }
        return render(request, 'stock/requisicoes/compra_externa_create_order.html', context)
        
    except Exception as e:
        logger.error(f"Erro ao criar ordem de compra para requisição {id}: {e}")
        messages.error(request, 'Erro ao criar ordem de compra.')
        return redirect('stock:requisicoes:compra_externa_detail', id=id)


@login_required
@require_stock_access
def ordem_compra_preview(request, id):
    """Pré-visualização da ordem de compra"""
    ordem_compra = get_object_or_404(OrdemCompra, id=id)
    
    context = {
        'ordem_compra': ordem_compra,
        'itens': ordem_compra.itens.all(),
    }
    return render(request, 'stock/requisicoes/ordem_compra_preview.html', context)


@login_required
@require_stock_access
@require_http_methods(["POST"])
def ordem_compra_action(request, id):
    """Ações da ordem de compra: imprimir, enviar, guardar"""
    ordem_compra = get_object_or_404(OrdemCompra, id=id)
    action = request.POST.get('action')
    
    # Proteção: não permitir alterações de status em ordens já recebidas
    if ordem_compra.status == 'RECEBIDA' and action == 'guardar':
        messages.warning(request, f'A ordem {ordem_compra.codigo} já foi recebida e não pode ser alterada.')
        return redirect('stock:requisicoes:ordem_compra_preview', id=id)
    
    if action == 'imprimir':
        # Redirecionar para página de impressão
        return redirect('stock:requisicoes:ordem_compra_print', id=id)
    elif action == 'enviar':
        # Redirecionar para página de impressão (para enviar por email/PDF)
        return redirect('stock:requisicoes:ordem_compra_print', id=id)
    elif action == 'guardar':
        # Marcar como guardada
        ordem_compra.status = 'GUARDADA'
        ordem_compra.save()
        messages.success(request, f'Ordem de compra {ordem_compra.codigo} guardada com sucesso!')
        return redirect('stock:requisicoes:ordem_compra_preview', id=id)
    elif action == 'confirmar':
        # Redirecionar para tela de confirmação (COLETA vs FORNECIMENTO)
        if ordem_compra.status == 'RASCUNHO':
            return redirect('stock:requisicoes:ordem_compra_confirm_tipo', id=id)
        else:
            messages.warning(request, f'A ordem {ordem_compra.codigo} não pode ser confirmada no status atual: {ordem_compra.get_status_display()}.')
            return redirect('stock:requisicoes:ordem_compra_preview', id=id)
    else:
        messages.error(request, 'Ação inválida.')
        return redirect('stock:requisicoes:ordem_compra_preview', id=id)


@login_required
@require_stock_access
def ordem_compra_confirm_tipo(request, id):
    """Confirmação do tipo de recebimento (COLETA vs FORNECIMENTO)"""
    ordem_compra = get_object_or_404(OrdemCompra, id=id)
    
    # Verificar se a ordem pode ser confirmada
    if ordem_compra.status != 'RASCUNHO':
        messages.warning(request, f'A ordem {ordem_compra.codigo} não pode ser confirmada no status atual: {ordem_compra.get_status_display()}.')
        return redirect('stock:requisicoes:ordem_compra_preview', id=id)
    
    if request.method == 'POST':
        tipo_recebimento = request.POST.get('tipo_recebimento')
        
        if tipo_recebimento in ['COLETAR', 'FORNECIMENTO']:
            # Marcar ordem como aprovada
            ordem_compra.status = 'APROVADA'
            ordem_compra.data_aprovacao = timezone.now()
            ordem_compra.aprovado_por = request.user
            ordem_compra.save()
            
            # Se for coleta, criar notificação para logística
            if tipo_recebimento == 'COLETAR':
                from .models_stock import NotificacaoLogisticaUnificada
                
                # Determinar prioridade (manual ou baseada no valor)
                prioridade_manual = request.session.get('prioridade_manual', '')
                if prioridade_manual:
                    prioridade = prioridade_manual
                    # Limpar da session após uso
                    if 'prioridade_manual' in request.session:
                        del request.session['prioridade_manual']
                else:
                    # Prioridade automática baseada no valor da ordem
                    valor_total = ordem_compra.valor_total
                    if valor_total > 50000:
                        prioridade = 'ALTA'
                    elif valor_total > 25000:
                        prioridade = 'NORMAL'
                    else:
                        prioridade = 'BAIXA'
                
                # Criar notificação unificada
                notificacao = NotificacaoLogisticaUnificada.objects.create(
                    tipo_operacao='COLETA',
                    ordem_compra=ordem_compra,
                    status='PENDENTE',
                    prioridade=prioridade,
                    observacoes=f'Coleta da ordem de compra {ordem_compra.codigo} - Fornecedor: {ordem_compra.fornecedor.nome}',
                    usuario_notificacao=request.user
                )
                
                messages.success(request, f'Ordem de compra {ordem_compra.codigo} confirmada para COLETA! Notificação criada para logística.')
            else:
                messages.success(request, f'Ordem de compra {ordem_compra.codigo} confirmada para FORNECIMENTO! Aguardando entrega do fornecedor.')
            
            return redirect('stock:requisicoes:ordem_compra_preview', id=id)
        else:
            messages.error(request, 'Tipo de recebimento inválido.')
    
    context = {
        'ordem_compra': ordem_compra,
        'title': f'Confirmar Tipo de Recebimento - {ordem_compra.codigo}'
    }
    return render(request, 'stock/requisicoes/ordem_compra_confirm_tipo.html', context)


@login_required
@require_stock_access
def ordem_compra_print(request, id):
    """Página de impressão da ordem de compra"""
    ordem_compra = get_object_or_404(OrdemCompra, id=id)
    
    context = {
        'ordem_compra': ordem_compra,
        'itens': ordem_compra.itens.all(),
    }
    return render(request, 'stock/requisicoes/ordem_compra_print.html', context)


@login_required
@require_stock_access
@require_http_methods(["GET", "POST"])
def ordem_compra_receive(request, id):
    """Recebimento de stock da ordem de compra"""
    ordem_compra = get_object_or_404(OrdemCompra, id=id)
    
    # Verificar se a ordem já foi recebida
    if ordem_compra.status == 'RECEBIDA':
        messages.warning(request, f'A ordem {ordem_compra.codigo} já foi recebida em {ordem_compra.data_recebimento}.')
        return redirect('stock:requisicoes:ordem_compra_preview', id=id)
    
    # Verificar se a ordem pode receber stock
    if ordem_compra.status not in ['APROVADA', 'GUARDADA', 'ENVIADA']:
        messages.error(request, f'Esta ordem não pode receber stock no momento. Status atual: {ordem_compra.get_status_display()}.')
        return redirect('stock:requisicoes:ordem_compra_preview', id=id)
    
    if request.method == 'POST':
        numero_fatura = request.POST.get('numero_fatura')
        if not numero_fatura:
            messages.error(request, 'Número da fatura é obrigatório.')
            return redirect('stock:requisicoes:ordem_compra_receive', id=id)
        
        # Atualizar ordem com número da fatura
        ordem_compra.numero_fatura = numero_fatura
        ordem_compra.data_fatura = timezone.now()
        ordem_compra.save()
        
        # Redirecionar para confirmação de itens
        return redirect('stock:requisicoes:ordem_compra_confirm_items', id=id)
    
    context = {
        'ordem_compra': ordem_compra,
    }
    return render(request, 'stock/requisicoes/ordem_compra_receive.html', context)


@login_required
@require_stock_access
@require_http_methods(["GET", "POST"])
def ordem_compra_confirm_items(request, id):
    """Confirmação de itens recebidos"""
    ordem_compra = get_object_or_404(OrdemCompra, id=id)
    
    # Verificar se a ordem já foi recebida
    if ordem_compra.status == 'RECEBIDA':
        messages.warning(request, f'A ordem {ordem_compra.codigo} já foi recebida em {ordem_compra.data_recebimento}.')
        return redirect('stock:requisicoes:ordem_compra_preview', id=id)
    
    # Verificar se a ordem está em status válido para recebimento
    if ordem_compra.status not in ['APROVADA', 'GUARDADA', 'ENVIADA']:
        messages.error(request, f'A ordem {ordem_compra.codigo} não pode ser recebida no status atual: {ordem_compra.get_status_display()}.')
        return redirect('stock:requisicoes:ordem_compra_preview', id=id)
    
    if request.method == 'POST':
        # Processar itens recebidos
        itens_recebidos = []
        for item in ordem_compra.itens.all():
            quantidade_recebida = request.POST.get(f'quantidade_recebida_{item.id}')
            estado_item = request.POST.get(f'estado_item_{item.id}')
            
            if quantidade_recebida and estado_item:
                quantidade_recebida = int(quantidade_recebida)
                if quantidade_recebida > 0:
                    # Atualizar item
                    item.quantidade_recebida = quantidade_recebida
                    item.save()
                    
                    itens_recebidos.append({
                        'item': item,
                        'quantidade': quantidade_recebida,
                        'estado': estado_item
                    })
        
        if itens_recebidos:
            # Verificar se já existem movimentos para esta ordem
            movimentos_existentes = MovimentoItem.objects.filter(
                observacoes__icontains=f'Recebimento da ordem {ordem_compra.codigo}'
            ).count()
            
            if movimentos_existentes > 0:
                messages.error(request, f'Já existem movimentos registrados para a ordem {ordem_compra.codigo}. Recebimento duplo não permitido.')
                return redirect('stock:requisicoes:ordem_compra_preview', id=id)
            
            # Atualizar stock da empresa
            sucursal_destino = ordem_compra.sucursal_destino
            
            for item_data in itens_recebidos:
                item = item_data['item']
                quantidade = item_data['quantidade']
                
                if item.produto:
                    # Atualizar stock do produto usando modelo unificado
                    stock_item, created = StockItem.objects.get_or_create(
                        sucursal=sucursal_destino,
                        item=item.produto,
                        defaults={'quantidade_atual': 0}
                    )
                    stock_item.quantidade_atual += quantidade
                    stock_item.save()
                    
                    # Criar movimento de entrada usando modelo unificado
                    MovimentoItem.objects.create(
                        item=item.produto,  # item agora aponta para Item unificado
                        sucursal=sucursal_destino,
                        tipo_movimento=TipoMovimentoStock.objects.get(codigo='ENT_COMPRA'),
                        quantidade=quantidade,
                        preco_unitario=item.preco_unitario,
                        observacoes=f'Recebimento da ordem {ordem_compra.codigo} - Fatura: {ordem_compra.numero_fatura}',
                        usuario=request.user
                    )
            
            # Verificar tipo de recebimento (já definido anteriormente)
            tipo_recebimento = request.POST.get('tipo_recebimento', 'ENTREGA')
            
            # Marcar ordem como recebida
            ordem_compra.status = 'RECEBIDA'
            ordem_compra.data_recebimento = timezone.now()
            ordem_compra.save()
            
            # A notificação logística já foi criada no ordem_compra_confirm_tipo
            # Não é necessário criar novamente aqui
            messages.success(request, f'Stock recebido com sucesso! {len(itens_recebidos)} itens processados.')
            
            return redirect('stock:requisicoes:ordem_compra_preview', id=id)
        else:
            messages.error(request, 'Nenhum item foi processado.')
    
    context = {
        'ordem_compra': ordem_compra,
        'itens': ordem_compra.itens.all(),
        'estados_item': [
            ('BOM', 'Bom'),
            ('DANIFICADO', 'Danificado'),
            ('INCOMPLETO', 'Incompleto'),
            ('DEFEITUOSO', 'Defeituoso'),
        ]
    }
    return render(request, 'stock/requisicoes/ordem_compra_confirm_items.html', context)


@login_required
@require_stock_access
def ordem_compra_receipt_note(request, id):
    """Nota de Recepção da ordem de compra"""
    ordem_compra = get_object_or_404(OrdemCompra, id=id)
    
    # Verificar se a ordem foi recebida
    if ordem_compra.status != 'RECEBIDA':
        messages.error(request, 'Esta ordem ainda não foi recebida.')
        return redirect('stock:requisicoes:ordem_compra_preview', id=id)
    
    # Buscar informações de transporte se existir notificação logística
    notificacao_logistica = None
    if hasattr(ordem_compra, 'notificacao_logistica_unificada'):
        notificacao_logistica = ordem_compra.notificacao_logistica_unificada
    
    context = {
        'ordem_compra': ordem_compra,
        'itens': ordem_compra.itens.all(),
        'notificacao_logistica': notificacao_logistica,
    }
    return render(request, 'stock/requisicoes/ordem_compra_receipt_note.html', context)


# =============================================================================
# VIEWS DE ENVIO DE EMAIL
# =============================================================================

@login_required
@require_stock_access
@require_http_methods(["GET", "POST"])
def ordem_compra_enviar_email(request, id):
    """Interface para envio de email da ordem de compra"""
    ordem_compra = get_object_or_404(OrdemCompra, id=id)
    
    if request.method == 'POST':
        email_destinatario = request.POST.get('email_destinatario')
        assunto = request.POST.get('assunto', f'Ordem de Compra {ordem_compra.codigo}')
        mensagem_personalizada = request.POST.get('mensagem_personalizada', '')
        
        if not email_destinatario:
            messages.error(request, 'Email do destinatário é obrigatório.')
            return redirect('stock:requisicoes:ordem_compra_enviar_email', id=id)
        
        # Criar registro no histórico
        historico = HistoricoEnvioEmail.objects.create(
            ordem_compra=ordem_compra,
            email_destinatario=email_destinatario,
            assunto=assunto,
            enviado_por=request.user,
            status='PENDENTE'
        )
        
        # Enviar email
        email_service = EmailService()
        sucesso, mensagem = email_service.enviar_ordem_compra(
            ordem_compra=ordem_compra,
            email_destinatario=email_destinatario,
            assunto=assunto,
            mensagem_personalizada=mensagem_personalizada
        )
        
        # Atualizar histórico
        if sucesso:
            historico.status = 'ENVIADO'
            messages.success(request, f'Email enviado com sucesso para {email_destinatario}')
        else:
            historico.status = 'FALHOU'
            historico.mensagem_erro = mensagem
            messages.error(request, f'Erro ao enviar email: {mensagem}')
        
        historico.save()
        return redirect('stock:requisicoes:ordem_compra_preview', id=id)
    
    # GET - mostrar formulário
    context = {
        'ordem_compra': ordem_compra,
        'email_padrao': ordem_compra.fornecedor.email if ordem_compra.fornecedor else '',
        'assunto_padrao': f'Ordem de Compra {ordem_compra.codigo} - {ordem_compra.fornecedor.nome if ordem_compra.fornecedor else "Fornecedor"}',
        'historico_envios': ordem_compra.historico_envios.all()[:5]  # Últimos 5 envios
    }
    return render(request, 'stock/requisicoes/ordem_compra_enviar_email.html', context)


@login_required
@require_stock_access
def ordem_compra_historico_envios(request, id):
    """Histórico completo de envios de email da ordem de compra"""
    ordem_compra = get_object_or_404(OrdemCompra, id=id)
    
    envios = ordem_compra.historico_envios.all()
    
    context = {
        'ordem_compra': ordem_compra,
        'envios': envios
    }
    return render(request, 'stock/requisicoes/ordem_compra_historico_envios.html', context)


@login_required
@require_stock_access
def ordem_compra_download_pdf(request, id):
    """Download direto do PDF da ordem de compra"""
    ordem_compra = get_object_or_404(OrdemCompra, id=id)
    
    email_service = EmailService()
    pdf_content = email_service.gerar_pdf_ordem_compra(ordem_compra)
    
    if pdf_content:
        response = HttpResponse(pdf_content, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="Ordem_Compra_{ordem_compra.codigo}.pdf"'
        return response
    else:
        messages.error(request, 'Erro ao gerar PDF.')
        return redirect('stock:requisicoes:ordem_compra_preview', id=id)


@login_required
@require_stock_access
@require_http_methods(["GET", "POST"])
def requisicao_quick_add_item(request, id):
    """Adicionar item rapidamente à requisição (vindo do stock baixo)"""
    requisicao = get_object_or_404(RequisicaoStock, id=id)
    
    if requisicao.status != 'RASCUNHO':
        messages.error(request, 'Apenas requisições em rascunho podem ser editadas.')
        return redirect('stock:requisicoes:detail', id=id)
    
    # GET - Mostrar formulário rápido
    if request.method == 'GET':
        item_id = request.GET.get('item')
        if not item_id:
            messages.error(request, 'Item não especificado.')
            return redirect('stock:requisicoes:detail', id=id)
        
        try:
            item = Item.objects.get(id=item_id)
        except Item.DoesNotExist:
            messages.error(request, 'Item não encontrado.')
            return redirect('stock:requisicoes:detail', id=id)
        
        # Verificar se o item já existe na requisição
        if ItemRequisicaoStock.objects.filter(requisicao=requisicao, item=item).exists():
            messages.warning(request, f'O item {item.nome} já está nesta requisição.')
            return redirect('stock:requisicoes:detail', id=id)
        
        # Calcular sugestões de quantidade
        stock_disponivel = StockItem.objects.filter(
            item=item,
            sucursal=requisicao.sucursal_destino
        ).first()
        
        sugestoes = {}
        if stock_disponivel and stock_disponivel.quantidade_atual > 0:
            estoque_minimo = item.estoque_minimo
            estoque_maximo = item.estoque_maximo
            stock_atual = stock_disponivel.quantidade_atual
            
            sugestoes = {
                'minima': max(1, estoque_minimo - stock_atual),
                'recomendada': max(1, (estoque_minimo + estoque_maximo) // 2 - stock_atual),
                'maxima': min(estoque_maximo - stock_atual, stock_disponivel.quantidade_atual),
                'stock_disponivel': stock_disponivel.quantidade_atual,
            }
            
            # Limitar sugestões ao stock disponível
            sugestoes['minima'] = min(sugestoes['minima'], stock_disponivel.quantidade_atual)
            sugestoes['recomendada'] = min(sugestoes['recomendada'], stock_disponivel.quantidade_atual)
        
        context = {
            'requisicao': requisicao,
            'item': item,
            'sugestoes': sugestoes,
            'stock_disponivel': stock_disponivel.quantidade_atual if stock_disponivel else 0,
        }
        
        return render(request, 'stock/requisicoes/quick_add_item.html', context)
    
    # POST - Adicionar item à requisição
    try:
        with transaction.atomic():
            item_id = request.POST.get('item')
            quantidade = request.POST.get('quantidade')
            observacoes = request.POST.get('observacoes', '')
            
            if not item_id or not quantidade:
                messages.error(request, 'Item e quantidade são obrigatórios.')
                return redirect('stock:requisicoes:detail', id=id)
            
            item = Item.objects.get(id=item_id)
            quantidade = int(quantidade)
            
            if quantidade <= 0:
                messages.error(request, 'Quantidade deve ser maior que zero.')
                return redirect('stock:requisicoes:detail', id=id)
            
            # Verificar se o item já existe na requisição
            if ItemRequisicaoStock.objects.filter(requisicao=requisicao, item=item).exists():
                messages.error(request, f'O item {item.nome} já está nesta requisição.')
                return redirect('stock:requisicoes:detail', id=id)
            
            # Verificar stock disponível na sucursal fornecedora
            stock_disponivel = StockItem.objects.filter(
                item=item,
                sucursal=requisicao.sucursal_destino
            ).first()
            
            if not stock_disponivel:
                messages.error(request, f'O item {item.nome} não está disponível na sucursal {requisicao.sucursal_destino.nome}.')
                return redirect('stock:requisicoes:detail', id=id)
            
            quantidade_disponivel = stock_disponivel.quantidade_disponivel
            
            if quantidade > quantidade_disponivel:
                messages.error(request, f'Não é possível solicitar {quantidade} unidades. A sucursal {requisicao.sucursal_destino.nome} tem apenas {quantidade_disponivel} unidades disponíveis de {item.nome}.')
                return redirect('stock:requisicoes:detail', id=id)
            
            # Criar item da requisição
            ItemRequisicaoStock.objects.create(
                requisicao=requisicao,
                item=item,
                quantidade_solicitada=quantidade,
                observacoes=observacoes
            )
            
            
    except Item.DoesNotExist:
        messages.error(request, 'Item não encontrado.')
    except ValueError:
        messages.error(request, 'Quantidade inválida.')
    except Exception as e:
        logger.error(f"Erro ao adicionar item à requisição: {e}")
        messages.error(request, 'Erro ao adicionar item.')
    
    return redirect('stock:requisicoes:detail', id=id)


@login_required
@require_stock_access
@require_http_methods(["POST"])
def requisicao_add_item(request, id):
    """Adicionar item à requisição"""
    requisicao = get_object_or_404(RequisicaoStock, id=id)
    
    if requisicao.status != 'RASCUNHO':
        messages.error(request, 'Apenas requisições em rascunho podem ser editadas.')
        return redirect('stock:requisicoes:detail', id=id)
    
    try:
        with transaction.atomic():
            item_id = request.POST.get('item')
            quantidade = request.POST.get('quantidade')
            sucursal_fornecedora_id = request.POST.get('sucursal_fornecedora')
            observacoes = request.POST.get('observacoes', '')
            
            if not item_id or not quantidade or not sucursal_fornecedora_id:
                messages.error(request, 'Item, quantidade e sucursal fornecedora são obrigatórios.')
                return redirect('stock:requisicoes:detail', id=id)
            
            item = Item.objects.get(id=item_id)
            quantidade = int(quantidade)
            
            if quantidade <= 0:
                messages.error(request, 'Quantidade deve ser maior que zero.')
                return redirect('stock:requisicoes:detail', id=id)
            
            # Verificar se o item já existe na requisição
            if ItemRequisicaoStock.objects.filter(requisicao=requisicao, item=item).exists():
                messages.error(request, f'O item {item.nome} já está nesta requisição.')
                return redirect('stock:requisicoes:detail', id=id)
            
            # Verificar stock disponível na sucursal fornecedora
            sucursal_fornecedora = Sucursal.objects.get(id=sucursal_fornecedora_id)
            stock_disponivel = StockItem.objects.filter(
                item=item,
                sucursal=sucursal_fornecedora
            ).first()
            
            if not stock_disponivel:
                messages.error(request, f'O item {item.nome} não está disponível na sucursal {sucursal_fornecedora.nome}.')
                return redirect('stock:requisicoes:detail', id=id)
            
            quantidade_disponivel = stock_disponivel.quantidade_disponivel
            
            if quantidade > quantidade_disponivel:
                messages.error(request, f'Não é possível solicitar {quantidade} unidades. A sucursal {sucursal_fornecedora.nome} tem apenas {quantidade_disponivel} unidades disponíveis de {item.nome}.')
                return redirect('stock:requisicoes:detail', id=id)
            
            # Criar item da requisição
            ItemRequisicaoStock.objects.create(
                requisicao=requisicao,
                item=item,
                quantidade_solicitada=quantidade,
                observacoes=observacoes
            )
            
            
    except Item.DoesNotExist:
        messages.error(request, 'Item não encontrado.')
    except ValueError:
        messages.error(request, 'Quantidade inválida.')
    except Exception as e:
        logger.error(f"Erro ao adicionar item à requisição: {e}")
        messages.error(request, 'Erro ao adicionar item.')
    
    return redirect('stock:requisicoes:detail', id=id)


@login_required
@require_stock_access
@require_http_methods(["POST"])
def requisicao_remove_item(request, id, item_id):
    """Remover item da requisição"""
    requisicao = get_object_or_404(RequisicaoStock, id=id)
    
    if requisicao.status != 'RASCUNHO':
        messages.error(request, 'Apenas requisições em rascunho podem ser editadas.')
        return redirect('stock:requisicoes:detail', id=id)
    
    try:
        item_requisicao = ItemRequisicaoStock.objects.get(
            requisicao=requisicao, id=item_id
        )
        item_requisicao.delete()
    except ItemRequisicaoStock.DoesNotExist:
        messages.error(request, 'Item não encontrado na requisição.')
    except Exception as e:
        logger.error(f"Erro ao remover item da requisição: {e}")
        messages.error(request, 'Erro ao remover item.')
    
    return redirect('stock:requisicoes:detail', id=id)


@login_required
@require_stock_access
@require_http_methods(["POST"])
def requisicao_submit(request, id):
    """Submeter requisição (promover para PENDENTE)"""
    requisicao = get_object_or_404(RequisicaoStock, id=id)
    
    if requisicao.status != 'RASCUNHO':
        messages.error(request, 'Apenas requisições em rascunho podem ser submetidas.')
        return redirect('stock:requisicoes:detail', id=id)
    
    if not requisicao.itens.exists():
        messages.error(request, 'A requisição deve ter pelo menos um item.')
        return redirect('stock:requisicoes:detail', id=id)
    
    if requisicao.promover_para_pendente():
        pass
    else:
        messages.error(request, 'Erro ao submeter requisição.')
    
    return redirect('stock:requisicoes:detail', id=id)


@login_required
@require_stock_access
@require_http_methods(["POST"])
def requisicao_approve(request, id):
    """Aprovar requisição"""
    requisicao = get_object_or_404(RequisicaoStock, id=id)
    
    if requisicao.status != 'PENDENTE':
        messages.error(request, 'Apenas requisições pendentes podem ser aprovadas.')
        return redirect('stock:requisicoes:detail', id=id)
    
    try:
        with transaction.atomic():
            requisicao.status = 'APROVADA'
            requisicao.aprovado_por = request.user
            requisicao.data_aprovacao = timezone.now()
            requisicao.save()
            
    except Exception as e:
        logger.error(f"Erro ao aprovar requisição: {e}")
        messages.error(request, 'Erro ao aprovar requisição.')
    
    return redirect('stock:requisicoes:detail', id=id)


@login_required
@require_stock_access
@require_http_methods(["POST"])
def requisicao_reject(request, id):
    """Rejeitar requisição"""
    requisicao = get_object_or_404(RequisicaoStock, id=id)
    
    if requisicao.status not in ['PENDENTE', 'APROVADA']:
        messages.error(request, 'Apenas requisições pendentes ou aprovadas podem ser rejeitadas.')
        return redirect('stock:requisicoes:detail', id=id)
    
    try:
        requisicao.status = 'REJEITADA'
        requisicao.save()
    except Exception as e:
        logger.error(f"Erro ao rejeitar requisição: {e}")
        messages.error(request, 'Erro ao rejeitar requisição.')
    
    return redirect('stock:requisicoes:detail', id=id)


@login_required
@require_stock_access
@require_http_methods(["POST"])
def requisicao_cancel(request, id):
    """Cancelar requisição"""
    requisicao = get_object_or_404(RequisicaoStock, id=id)
    
    if requisicao.status in ['ATENDIDA', 'CANCELADA']:
        messages.error(request, 'Esta requisição não pode ser cancelada.')
        return redirect('stock:requisicoes:detail', id=id)
    
    try:
        requisicao.status = 'CANCELADA'
        requisicao.save()
    except Exception as e:
        logger.error(f"Erro ao cancelar requisição: {e}")
        messages.error(request, 'Erro ao cancelar requisição.')
    
    return redirect('stock:requisicoes:detail', id=id)


@login_required
@require_stock_access
@require_http_methods(["POST"])
def requisicao_delete(request, id):
    """Apagar uma requisição de stock (rascunhos, pendentes e rejeitadas)"""
    requisicao = get_object_or_404(RequisicaoStock, id=id)
    
    if requisicao.status not in ['RASCUNHO', 'PENDENTE', 'REJEITADA']:
        messages.error(request, 'Apenas requisições em rascunho, pendentes ou rejeitadas podem ser apagadas.')
        return redirect('stock:requisicoes:detail', id=id)
    
    try:
        codigo_requisicao = requisicao.codigo
        requisicao.delete()
        return redirect('stock:requisicoes:list')
    except Exception as e:
        logger.error(f"Erro ao apagar requisição: {e}")
        messages.error(request, 'Erro ao apagar requisição.')
        return redirect('stock:requisicoes:detail', id=id)


@login_required
@require_stock_access
def requisicao_add_item_form(request, id):
    """Formulário para adicionar item à requisição"""
    requisicao = get_object_or_404(RequisicaoStock, id=id)
    
    if requisicao.status != 'RASCUNHO':
        messages.error(request, 'Apenas requisições em rascunho podem ser editadas.')
        return redirect('stock:requisicoes:detail', id=id)
    
    # Buscar todos os itens (não filtrar por sucursal - será selecionado por item)
    itens_disponiveis = Item.objects.all().order_by('tipo', 'nome')
    
    # Verificar se há um item específico sugerido (vindo do stock baixo)
    item_sugerido = None
    item_id = request.GET.get('item')
    if item_id:
        try:
            item_sugerido = Item.objects.get(id=item_id)
            # Não filtrar por disponibilidade - o item pode não estar disponível na sucursal de destino
            # mas ainda deve ser sugerido para que o usuário possa ver que não está disponível
        except Item.DoesNotExist:
            item_sugerido = None
    
    # Excluir a sucursal solicitante da lista de sucursais fornecedoras
    sucursais_fornecedoras = Sucursal.objects.exclude(id=requisicao.sucursal_origem.id).order_by('nome')
    
    context = {
        'requisicao': requisicao,
        'itens': itens_disponiveis,
        'item_sugerido': item_sugerido,
        'sucursais': sucursais_fornecedoras,
    }
    
    return render(request, 'stock/requisicoes/add_item.html', context)


# API para buscar itens disponíveis
@login_required
def api_itens_disponiveis(request):
    """API para buscar itens disponíveis em uma sucursal"""
    sucursal_id = request.GET.get('sucursal_id')
    
    if not sucursal_id:
        return JsonResponse({'error': 'Sucursal é obrigatória'}, status=400)
    
    try:
        itens = Item.objects.filter(
            stocks_sucursais__sucursal_id=sucursal_id,
            stocks_sucursais__quantidade_atual__gt=0
        ).distinct().order_by('tipo', 'nome')
        
        itens_data = []
        for item in itens:
            stock = item.stocks_sucursais.filter(sucursal_id=sucursal_id).first()
            itens_data.append({
                'id': item.id,
                'nome': item.nome,
                'codigo': item.codigo,
                'tipo': item.tipo,
                'unidade_medida': item.unidade_medida,
                'preco_custo': float(item.preco_custo),
                'quantidade_disponivel': float(stock.quantidade_atual) if stock else 0,
            })
        
        return JsonResponse({'itens': itens_data})
        
    except Exception as e:
        logger.error(f"Erro na API de itens disponíveis: {e}")
        return JsonResponse({'error': 'Erro interno do servidor'}, status=500)


# API para buscar stock de um item específico em uma sucursal
@login_required
def api_stock_item_sucursal(request):
    """API para buscar stock de um item específico em uma sucursal"""
    item_id = request.GET.get('item_id')
    sucursal_id = request.GET.get('sucursal_id')
    
    if not item_id or not sucursal_id:
        return JsonResponse({'error': 'Item e sucursal são obrigatórios'}, status=400)
    
    try:
        item = Item.objects.get(id=item_id)
        sucursal = Sucursal.objects.get(id=sucursal_id)
        
        stock_item = StockItem.objects.filter(
            item=item,
            sucursal=sucursal
        ).first()
        
        if stock_item:
            return JsonResponse({
                'disponivel': True,
                'quantidade_atual': stock_item.quantidade_atual,
                'quantidade_disponivel': stock_item.quantidade_disponivel,
                'sucursal_nome': sucursal.nome
            })
        else:
            return JsonResponse({
                'disponivel': False,
                'quantidade_atual': 0,
                'quantidade_disponivel': 0,
                'sucursal_nome': sucursal.nome
            })
        
    except Item.DoesNotExist:
        return JsonResponse({'error': 'Item não encontrado'}, status=404)
    except Sucursal.DoesNotExist:
        return JsonResponse({'error': 'Sucursal não encontrada'}, status=404)
    except Exception as e:
        logger.error(f"Erro na API de stock por item e sucursal: {e}")
        return JsonResponse({'error': 'Erro interno do servidor'}, status=500)


# =============================================================================
# VIEWS DE COMPRA EXTERNA
# =============================================================================

@login_required
@require_stock_access
def compra_externa_list(request):
    """Lista de requisições de compra externa"""
    try:
        # Buscar requisições de compra externa
        requisicoes = RequisicaoCompraExterna.objects.select_related(
            'sucursal_solicitante', 'criado_por'
        ).prefetch_related('itens__item').order_by('-data_criacao')
        
        # Aplicar filtros se necessário
        status_filter = request.GET.get('status')
        if status_filter:
            requisicoes = requisicoes.filter(status=status_filter)
        
        # Paginação
        from django.core.paginator import Paginator
        paginator = Paginator(requisicoes, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        context = {
            'title': 'Requisições de Compra Externa',
            'page_obj': page_obj,
            'requisicoes': page_obj,
            'status_choices': RequisicaoCompraExterna.STATUS_CHOICES,
            'current_status': status_filter,
        }
        return render(request, 'stock/requisicoes/compra_externa_list.html', context)
        
    except Exception as e:
        logger.error(f"Erro ao listar compras externas: {e}")
        messages.error(request, 'Erro ao carregar requisições de compra externa.')
        return render(request, 'stock/requisicoes/compra_externa_list.html', {'requisicoes': []})

@login_required
@require_stock_access
def ordens_compra_list(request):
    """Lista de todas as ordens de compra"""
    try:
        from .models_stock import OrdemCompra
        from django.core.paginator import Paginator
        
        # Buscar todas as ordens de compra
        ordens = OrdemCompra.objects.select_related(
            'fornecedor', 'sucursal_destino', 'requisicao_origem', 'criado_por'
        ).prefetch_related('itens').order_by('-data_criacao')
        
        # Aplicar filtros
        status_filter = request.GET.get('status', '')
        search_query = request.GET.get('search', '').strip()
        fornecedor_filter = request.GET.get('fornecedor', '')
        
        if status_filter:
            ordens = ordens.filter(status=status_filter)
        
        if search_query:
            ordens = ordens.filter(
                Q(codigo__icontains=search_query) |
                Q(fornecedor__nome__icontains=search_query) |
                Q(sucursal_destino__nome__icontains=search_query) |
                Q(requisicao_origem__codigo__icontains=search_query)
            )
        
        if fornecedor_filter:
            ordens = ordens.filter(fornecedor_id=fornecedor_filter)
        
        # Paginação
        paginator = Paginator(ordens, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Estatísticas
        total_ordens = ordens.count()
        ordens_pendentes = ordens.filter(status='PENDENTE').count()
        ordens_guardadas = ordens.filter(status='GUARDADA').count()
        ordens_enviadas = ordens.filter(status='ENVIADA').count()
        ordens_recebidas = ordens.filter(status='RECEBIDA').count()
        
        # Obter fornecedores para filtro
        from .models_stock import Fornecedor
        fornecedores = Fornecedor.objects.all().order_by('nome')
        
        # Status choices
        status_choices = OrdemCompra.STATUS_CHOICES
        
        context = {
            'title': 'Ordens de Compra',
            'page_obj': page_obj,
            'ordens': page_obj,
            'total_ordens': total_ordens,
            'ordens_pendentes': ordens_pendentes,
            'ordens_guardadas': ordens_guardadas,
            'ordens_enviadas': ordens_enviadas,
            'ordens_recebidas': ordens_recebidas,
            'status_choices': status_choices,
            'fornecedores': fornecedores,
            'current_status': status_filter,
            'current_search': search_query,
            'current_fornecedor': fornecedor_filter,
        }
        return render(request, 'stock/requisicoes/ordens_compra_list.html', context)
        
    except Exception as e:
        logger.error(f"Erro ao listar ordens de compra: {e}")
        messages.error(request, 'Erro ao carregar ordens de compra.')
        return render(request, 'stock/requisicoes/ordens_compra_list.html', {'ordens': []})

@login_required
@require_stock_access
@csrf_exempt
def compra_externa_create(request):
    """Criar requisição de compra externa"""
    # Processar parâmetros GET se existirem
    item_id_pre_selecionado = request.GET.get('item_id')
    sucursal_id_pre_selecionada = request.GET.get('sucursal_id')
    
    if request.method == 'POST':
        try:
            # Debug: Log dos dados recebidos
            logger.info(f"Dados POST recebidos: {dict(request.POST)}")
            
            # Obter dados do formulário
            item_id = request.POST.get('item_id')
            sucursal_id = request.POST.get('sucursal_id')
            quantidade = request.POST.get('quantidade')
            observacoes = request.POST.get('observacoes', '')
            
            # Validações
            if not all([item_id, sucursal_id, quantidade]):
                logger.error(f"Campos obrigatórios faltando: item_id={item_id}, sucursal_id={sucursal_id}, quantidade={quantidade}")
                messages.error(request, 'Item, sucursal e quantidade são obrigatórios.')
                return redirect('stock:requisicoes:verificar_stock_baixo')
            
            # Buscar objetos
            item = get_object_or_404(Item, id=item_id)
            sucursal = get_object_or_404(Sucursal, id=sucursal_id)
            
            # Criar requisição de compra externa
            requisicao = RequisicaoCompraExterna.objects.create(
                sucursal_solicitante=sucursal,
                observacoes=f"Compra externa para {item.nome}. {observacoes}",
                criado_por=request.user
            )
            
            # Criar item da requisição
            ItemRequisicaoCompraExterna.objects.create(
                requisicao=requisicao,
                item=item,
                quantidade_solicitada=int(quantidade),
                observacoes=observacoes
            )
            
            return redirect('stock:requisicoes:compra_externa_detail', id=requisicao.id)
            
        except Exception as e:
            logger.error(f"Erro ao criar compra externa: {e}")
            messages.error(request, 'Erro ao criar requisição de compra externa.')
            return redirect('stock:requisicoes:verificar_stock_baixo')
    
    # Se for GET, mostrar página de criação de compra externa
    context = {
        'title': 'Nova Requisição de Compra Externa',
        'sucursais': Sucursal.objects.all(),
        'itens': Item.objects.all()[:50],  # Limitar para performance
        'item_pre_selecionado': None,
        'sucursal_pre_selecionada': None,
    }
    
    # Se há item pré-selecionado, buscar o objeto
    if item_id_pre_selecionado:
        try:
            context['item_pre_selecionado'] = Item.objects.get(id=item_id_pre_selecionado)
        except Item.DoesNotExist:
            pass
    
    # Se há sucursal pré-selecionada, buscar o objeto
    if sucursal_id_pre_selecionada:
        try:
            context['sucursal_pre_selecionada'] = Sucursal.objects.get(id=sucursal_id_pre_selecionada)
        except Sucursal.DoesNotExist:
            pass
    
    return render(request, 'stock/requisicoes/compra_externa_create.html', context)


@login_required
@require_stock_access
def compra_externa_detail(request, id):
    """Detalhes de uma requisição de compra externa"""
    requisicao = get_object_or_404(RequisicaoCompraExterna.objects.select_related(
        'sucursal_solicitante', 'criado_por'
    ).prefetch_related('itens__item'), id=id)
    
    # Buscar ordens de compra criadas a partir desta requisição
    ordens_compra = OrdemCompra.objects.filter(
        requisicao_origem=requisicao
    ).select_related('fornecedor').prefetch_related('itens').order_by('-data_criacao')
    
    context = {
        'requisicao': requisicao,
        'ordens_compra': ordens_compra,
        'itens': Item.objects.all()[:50],  # Para adicionar novos itens
    }
    
    return render(request, 'stock/requisicoes/compra_externa_detail.html', context)


@login_required
@require_stock_access
def compra_externa_add_item(request, id):
    """Adicionar item a uma requisição de compra externa existente"""
    requisicao = get_object_or_404(RequisicaoCompraExterna, id=id)
    
    if request.method == 'POST':
        try:
            # Obter dados do formulário
            item_id = request.POST.get('item_id')
            quantidade = request.POST.get('quantidade')
            preco_unitario_estimado = request.POST.get('preco_unitario_estimado')
            observacoes = request.POST.get('observacoes', '')
            
            # Validações
            if not all([item_id, quantidade]):
                messages.error(request, 'Item e quantidade são obrigatórios.')
                return redirect('stock:requisicoes:compra_externa_detail', id=requisicao.id)
            
            # Buscar item
            item = get_object_or_404(Item, id=item_id)
            
            # Verificar se o item já existe na requisição
            if ItemRequisicaoCompraExterna.objects.filter(requisicao=requisicao, item=item).exists():
                messages.warning(request, f'O item {item.nome} já está nesta requisição.')
                return redirect('stock:requisicoes:compra_externa_detail', id=requisicao.id)
            
            # Processar preço estimado se fornecido
            preco_estimado = None
            if preco_unitario_estimado:
                try:
                    preco_estimado = Decimal(preco_unitario_estimado)
                    if preco_estimado <= 0:
                        messages.warning(request, 'Preço estimado deve ser maior que zero. Item adicionado sem preço.')
                        preco_estimado = None
                except (ValueError, InvalidOperation):
                    messages.warning(request, 'Preço estimado inválido. Item adicionado sem preço.')
                    preco_estimado = None
            
            # Criar item da requisição
            ItemRequisicaoCompraExterna.objects.create(
                requisicao=requisicao,
                item=item,
                quantidade_solicitada=int(quantidade),
                preco_unitario_estimado=preco_estimado,
                observacoes=observacoes
            )
            
            return redirect('stock:requisicoes:compra_externa_detail', id=requisicao.id)
            
        except Exception as e:
            logger.error(f"Erro ao adicionar item à compra externa: {e}")
            messages.error(request, 'Erro ao adicionar item à requisição.')
            return redirect('stock:requisicoes:compra_externa_detail', id=requisicao.id)
    
    # GET - mostrar formulário
    context = {
        'requisicao': requisicao,
        'itens': Item.objects.all()[:50],
    }
    
    return render(request, 'stock/requisicoes/compra_externa_add_item.html', context)


@login_required
@require_stock_access
def compra_externa_remove_item(request, id, item_id):
    """Remover item de uma requisição de compra externa"""
    requisicao = get_object_or_404(RequisicaoCompraExterna, id=id)
    item_requisicao = get_object_or_404(ItemRequisicaoCompraExterna, id=item_id, requisicao=requisicao)
    
    # Validar se a requisição pode ser editada
    if requisicao.status not in ['RASCUNHO', 'PENDENTE', 'APROVADA']:
        messages.error(request, 'Não é possível remover itens de requisições finalizadas ou processadas.')
        return redirect('stock:requisicoes:compra_externa_detail', id=requisicao.id)
    
    if request.method == 'POST':
        item_nome = item_requisicao.item.nome
        item_requisicao.delete()
        messages.success(request, f'Item "{item_nome}" removido com sucesso.')
        return redirect('stock:requisicoes:compra_externa_detail', id=requisicao.id)
    
    # Se não for POST, redirecionar
    return redirect('stock:requisicoes:compra_externa_detail', id=requisicao.id)


@login_required
@require_stock_access
def compra_externa_submit(request, id):
    """Submeter requisição de compra externa para aprovação"""
    requisicao = get_object_or_404(RequisicaoCompraExterna, id=id)
    
    if requisicao.status != 'RASCUNHO':
        messages.error(request, 'Apenas requisições em rascunho podem ser submetidas.')
        return redirect('stock:requisicoes:compra_externa_detail', id=requisicao.id)
    
    if not requisicao.itens.exists():
        messages.error(request, 'Não é possível submeter uma requisição sem itens.')
        return redirect('stock:requisicoes:compra_externa_detail', id=requisicao.id)
    
    if request.method == 'POST':
        requisicao.status = 'PENDENTE'
        requisicao.save()
        return redirect('stock:requisicoes:compra_externa_detail', id=requisicao.id)
    
    return redirect('stock:requisicoes:compra_externa_detail', id=requisicao.id)


@login_required
@require_stock_access
def compra_externa_approve(request, id):
    """Aprovar requisição de compra externa"""
    requisicao = get_object_or_404(RequisicaoCompraExterna, id=id)
    
    if requisicao.status != 'PENDENTE':
        messages.error(request, 'Apenas requisições pendentes podem ser aprovadas.')
        return redirect('stock:requisicoes:compra_externa_detail', id=requisicao.id)
    
    if request.method == 'POST':
        requisicao.status = 'APROVADA'
        requisicao.save()
        return redirect('stock:requisicoes:compra_externa_detail', id=requisicao.id)
    
    return redirect('stock:requisicoes:compra_externa_detail', id=requisicao.id)


@login_required
@require_stock_access
def compra_externa_reject(request, id):
    """Rejeitar requisição de compra externa"""
    requisicao = get_object_or_404(RequisicaoCompraExterna, id=id)
    
    if requisicao.status != 'pendente':
        messages.error(request, 'Apenas requisições pendentes podem ser rejeitadas.')
        return redirect('stock:requisicoes:compra_externa_detail', id=requisicao.id)
    
    if request.method == 'POST':
        motivo = request.POST.get('motivo', 'Sem motivo especificado')
        requisicao.status = 'rejeitada'
        requisicao.observacoes += f"\n\nRejeitada em {timezone.now().strftime('%d/%m/%Y %H:%M')}. Motivo: {motivo}"
        requisicao.save()
        return redirect('stock:requisicoes:compra_externa_detail', id=requisicao.id)
    
    return redirect('stock:requisicoes:compra_externa_detail', id=requisicao.id)


@login_required
@require_stock_access
def compra_externa_cancel(request, id):
    """Cancelar requisição de compra externa"""
    requisicao = get_object_or_404(RequisicaoCompraExterna, id=id)
    
    if requisicao.status not in ['rascunho', 'pendente']:
        messages.error(request, 'Apenas requisições em rascunho ou pendentes podem ser canceladas.')
        return redirect('stock:requisicoes:compra_externa_detail', id=requisicao.id)
    
    if request.method == 'POST':
        requisicao.status = 'cancelada'
        requisicao.save()
        return redirect('stock:requisicoes:compra_externa_detail', id=requisicao.id)
    
    return redirect('stock:requisicoes:compra_externa_detail', id=requisicao.id)


@login_required
@require_stock_access
def compra_externa_documento(request, id):
    """Gerar documento oficial da requisição de compra externa"""
    requisicao = get_object_or_404(RequisicaoCompraExterna, id=id)
    
    context = {
        'requisicao': requisicao,
    }
    
    return render(request, 'stock/requisicoes/compra_externa_documento.html', context)


@login_required
@require_stock_access
def compra_externa_duplicate(request, id):
    """Duplicar requisição de compra externa"""
    requisicao_original = get_object_or_404(RequisicaoCompraExterna, id=id)
    
    if request.method == 'POST':
        try:
            # Criar nova requisição baseada na original
            nova_requisicao = RequisicaoCompraExterna.objects.create(
                sucursal_solicitante=requisicao_original.sucursal_solicitante,
                observacoes=f"Cópia da requisição {requisicao_original.codigo}. {requisicao_original.observacoes or ''}",
                criado_por=request.user,
                status='rascunho'  # Sempre começar como rascunho
            )
            
            # Duplicar todos os itens
            for item_original in requisicao_original.itens.all():
                ItemRequisicaoCompraExterna.objects.create(
                    requisicao=nova_requisicao,
                    item=item_original.item,
                    quantidade_solicitada=item_original.quantidade_solicitada,
                    preco_unitario_estimado=item_original.preco_unitario_estimado,
                    observacoes=item_original.observacoes
                )
            
            return redirect('stock:requisicoes:compra_externa_detail', id=nova_requisicao.id)
            
        except Exception as e:
            logger.error(f"Erro ao duplicar requisição: {e}")
            messages.error(request, 'Erro ao duplicar requisição.')
            return redirect('stock:requisicoes:compra_externa_detail', id=requisicao_original.id)
    
    # Se não for POST, redirecionar
    return redirect('stock:requisicoes:compra_externa_detail', id=requisicao_original.id)


@login_required
@require_stock_access
def compra_externa_finalize(request, id):
    """Finalizar requisição de compra externa"""
    requisicao = get_object_or_404(RequisicaoCompraExterna, id=id)
    
    if request.method == 'POST':
        try:
            if requisicao.status != 'APROVADA':
                messages.error(request, 'Apenas requisições aprovadas podem ser finalizadas.')
                return redirect('stock:requisicoes:compra_externa_detail', id=requisicao.id)
            
            requisicao.status = 'FINALIZADA'
            requisicao.save()
            
            return redirect('stock:requisicoes:compra_externa_detail', id=requisicao.id)
            
        except Exception as e:
            logger.error(f"Erro ao finalizar requisição: {e}")
            messages.error(request, 'Erro ao finalizar requisição.')
            return redirect('stock:requisicoes:compra_externa_detail', id=requisicao.id)
    
    return redirect('stock:requisicoes:compra_externa_detail', id=requisicao.id)


@login_required
@require_stock_access
def requisicao_edit_quantidade_atendida(request, id, item_id):
    """Editar quantidade atendida de um item da requisição"""
    requisicao = get_object_or_404(RequisicaoStock, id=id)
    item_requisicao = get_object_or_404(ItemRequisicaoStock, id=item_id, requisicao=requisicao)
    
    # Verificar se já existe uma transferência associada que foi recebida
    try:
        from .models_stock import TransferenciaStock
        codigo_transferencia = f"TRF{requisicao.codigo}"
        transferencia = TransferenciaStock.objects.get(codigo=codigo_transferencia)
        
        if transferencia.status == 'RECEBIDA':
            messages.error(request, 'Não é possível editar quantidades de uma transferência já recebida.')
            return redirect('stock:requisicoes:detail', id=requisicao.id)
    except TransferenciaStock.DoesNotExist:
        # Não há transferência ainda, pode editar
        pass
    
    if request.method == 'POST':
        try:
            quantidade_atendida = int(request.POST.get('quantidade_atendida', 0))
            
            # Validar quantidade
            if quantidade_atendida < 0:
                messages.error(request, 'A quantidade atendida não pode ser negativa.')
                return redirect('stock:requisicoes:detail', id=requisicao.id)
            
            if quantidade_atendida > item_requisicao.quantidade_solicitada:
                messages.error(request, 'A quantidade atendida não pode ser maior que a quantidade solicitada.')
                return redirect('stock:requisicoes:detail', id=requisicao.id)
            
            # Atualizar quantidade atendida
            item_requisicao.quantidade_atendida = quantidade_atendida
            item_requisicao.save()
            
            messages.success(request, f'Quantidade atendida atualizada para {quantidade_atendida} unidades.')
            return redirect('stock:requisicoes:detail', id=requisicao.id)
            
        except ValueError:
            messages.error(request, 'Quantidade inválida.')
            return redirect('stock:requisicoes:detail', id=requisicao.id)
        except Exception as e:
            messages.error(request, f'Erro ao atualizar quantidade: {str(e)}')
            return redirect('stock:requisicoes:detail', id=requisicao.id)
    
    # Verificar status da transferência para passar ao template
    transferencia_status = None
    try:
        codigo_transferencia = f"TRF{requisicao.codigo}"
        transferencia = TransferenciaStock.objects.get(codigo=codigo_transferencia)
        transferencia_status = transferencia.status
    except TransferenciaStock.DoesNotExist:
        transferencia_status = None
    
    context = {
        'requisicao': requisicao,
        'item_requisicao': item_requisicao,
        'transferencia_status': transferencia_status,
    }
    
    return render(request, 'stock/requisicoes/edit_quantidade_atendida.html', context)

@login_required
@require_stock_access
def requisicao_transfer_preview(request, id):
    """Preview da transferência de stock antes de executar"""
    requisicao = get_object_or_404(RequisicaoStock, id=id)
    
    if requisicao.status != 'APROVADA':
        messages.error(request, 'Apenas requisições aprovadas podem ter stock transferido.')
        return redirect('stock:requisicoes:detail', id=id)
    
    # Buscar itens com quantidade atendida
    itens_com_atendimento = requisicao.itens.filter(quantidade_atendida__gt=0)
    
    if not itens_com_atendimento.exists():
        messages.error(request, 'Nenhum item com quantidade atendida encontrado.')
        return redirect('stock:requisicoes:detail', id=id)
    
    # Analisar stock disponível para cada item
    from .models_stock import StockItem
    analise_stock = []
    
    for item_requisicao in itens_com_atendimento:
        item_obj = item_requisicao.item or item_requisicao.produto
        quantidade_necessaria = item_requisicao.quantidade_atendida
        
        # Buscar stock disponível em todas as sucursais (excluindo a solicitante)
        stocks_disponiveis = StockItem.objects.filter(
            item=item_obj
        ).exclude(
            sucursal=requisicao.sucursal_origem
        ).order_by('-quantidade_atual')
        
        # Determinar sucursal fornecedora (a que tem mais stock)
        sucursal_fornecedora = stocks_disponiveis.first().sucursal if stocks_disponiveis.exists() else None
        stock_disponivel = stocks_disponiveis.first().quantidade_atual if stocks_disponiveis.exists() else 0
        
        analise_stock.append({
            'item': item_obj,
            'quantidade_necessaria': quantidade_necessaria,
            'sucursal_fornecedora': sucursal_fornecedora,
            'stock_disponivel': stock_disponivel,
            'pode_atender': stock_disponivel >= quantidade_necessaria,
            'todas_sucursais': stocks_disponiveis
        })
    
    # Verificar se todas as sucursais fornecedoras são as mesmas
    sucursais_fornecedoras = [item['sucursal_fornecedora'] for item in analise_stock if item['sucursal_fornecedora']]
    sucursal_fornecedora_unica = sucursais_fornecedoras[0] if len(set(sucursais_fornecedoras)) == 1 else None
    
    context = {
        'requisicao': requisicao,
        'analise_stock': analise_stock,
        'sucursal_fornecedora_unica': sucursal_fornecedora_unica,
        'pode_executar': all(item['pode_atender'] for item in analise_stock),
    }
    
    return render(request, 'stock/requisicoes/transfer_preview.html', context)


@login_required
@require_stock_access
def requisicao_guia_transferencia(request, id):
    """Gerar guia de transferência para impressão"""
    requisicao = get_object_or_404(RequisicaoStock, id=id)
    
    if requisicao.status != 'ATENDIDA':
        messages.error(request, 'Apenas requisições atendidas podem gerar guias de transferência.')
        return redirect('stock:requisicoes:detail', id=id)
    
    # Buscar transferência associada
    from .models_stock import TransferenciaStock
    codigo_transferencia = f"TRF{requisicao.codigo}"
    transferencia = TransferenciaStock.objects.filter(codigo=codigo_transferencia).first()
    
    if not transferencia:
        messages.error(request, 'Transferência não encontrada. Execute a transferência primeiro.')
        return redirect('stock:requisicoes:detail', id=id)
    
    if transferencia.status not in ['ENVIADA', 'RECEBIDA']:
        messages.error(request, 'Apenas transferências enviadas ou recebidas podem gerar guias.')
        return redirect('stock:requisicoes:detail', id=id)
    
    # Buscar itens da transferência
    itens_transferencia = transferencia.itens.all()
    
    # Calcular valor para cada item e valor total da transferência
    valor_total = 0
    for item in itens_transferencia:
        preco = item.item.preco_custo if item.item else 0
        item.valor_item = item.quantidade_solicitada * preco
        valor_total += item.valor_item
    
    context = {
        'requisicao': requisicao,
        'transferencia': transferencia,
        'itens_transferencia': itens_transferencia,
        'valor_total': valor_total,
    }
    
    return render(request, 'stock/requisicoes/guia_transferencia.html', context)


@login_required
@require_stock_access
def requisicao_guia_transferencia_preview(request, id):
    """Preview da guia de transferência"""
    requisicao = get_object_or_404(RequisicaoStock, id=id)
    
    if requisicao.status != 'ATENDIDA':
        messages.error(request, 'Apenas requisições atendidas podem gerar guias de transferência.')
        return redirect('stock:requisicoes:detail', id=id)
    
    # Buscar transferência associada
    from .models_stock import TransferenciaStock
    codigo_transferencia = f"TRF{requisicao.codigo}"
    transferencia = TransferenciaStock.objects.filter(codigo=codigo_transferencia).first()
    
    if not transferencia:
        messages.error(request, 'Transferência não encontrada. Execute a transferência primeiro.')
        return redirect('stock:requisicoes:detail', id=id)
    
    if transferencia.status not in ['ENVIADA', 'RECEBIDA']:
        messages.error(request, 'Apenas transferências enviadas ou recebidas podem gerar guias.')
        return redirect('stock:requisicoes:detail', id=id)
    
    # Buscar itens da transferência
    itens_transferencia = transferencia.itens.all()
    
    # Calcular valor para cada item e valor total da transferência
    valor_total = 0
    for item in itens_transferencia:
        preco = item.item.preco_custo if item.item else 0
        item.valor_item = item.quantidade_solicitada * preco
        valor_total += item.valor_item
    
    context = {
        'requisicao': requisicao,
        'transferencia': transferencia,
        'itens_transferencia': itens_transferencia,
        'valor_total': valor_total,
    }
    
    return render(request, 'stock/requisicoes/guia_transferencia_preview.html', context)


@login_required
@require_stock_access
def requisicao_guia_recebimento_preview(request, id):
    """Preview da guia de recebimento"""
    requisicao = get_object_or_404(RequisicaoStock, id=id)
    
    if requisicao.status != 'ATENDIDA':
        messages.error(request, 'Apenas requisições atendidas podem gerar guias de recebimento.')
        return redirect('stock:requisicoes:detail', id=id)
    
    # Buscar transferência associada
    from .models_stock import TransferenciaStock
    codigo_transferencia = f"TRF{requisicao.codigo}"
    transferencia = TransferenciaStock.objects.filter(codigo=codigo_transferencia).first()
    
    if not transferencia:
        messages.error(request, 'Transferência não encontrada.')
        return redirect('stock:requisicoes:detail', id=id)
    
    if transferencia.status != 'RECEBIDA':
        messages.error(request, 'Apenas transferências recebidas podem gerar guias de recebimento.')
        return redirect('stock:requisicoes:detail', id=id)
    
    # Buscar itens da transferência
    itens_transferencia = transferencia.itens.all()
    
    # Calcular valor para cada item e valor total da transferência
    valor_total = 0
    for item in itens_transferencia:
        preco = item.item.preco_custo if item.item else 0
        quantidade = item.quantidade_recebida or item.quantidade_solicitada
        item.valor_item = quantidade * preco
        valor_total += item.valor_item
    
    context = {
        'requisicao': requisicao,
        'transferencia': transferencia,
        'itens_transferencia': itens_transferencia,
        'valor_total': valor_total,
    }
    
    return render(request, 'stock/requisicoes/guia_recebimento_preview.html', context)


@login_required
@require_stock_access
def requisicao_guia_recebimento(request, id):
    """Gerar guia de recebimento para impressão"""
    requisicao = get_object_or_404(RequisicaoStock, id=id)
    
    if requisicao.status != 'ATENDIDA':
        messages.error(request, 'Apenas requisições atendidas podem gerar guias de recebimento.')
        return redirect('stock:requisicoes:detail', id=id)
    
    # Buscar transferência associada
    from .models_stock import TransferenciaStock
    codigo_transferencia = f"TRF{requisicao.codigo}"
    transferencia = TransferenciaStock.objects.filter(codigo=codigo_transferencia).first()
    
    if not transferencia:
        messages.error(request, 'Transferência não encontrada.')
        return redirect('stock:requisicoes:detail', id=id)
    
    if transferencia.status != 'RECEBIDA':
        messages.error(request, 'Apenas transferências recebidas podem gerar guias de recebimento.')
        return redirect('stock:requisicoes:detail', id=id)
    
    # Buscar itens da transferência
    itens_transferencia = transferencia.itens.all()
    
    # Calcular valor para cada item e valor total da transferência
    valor_total = 0
    for item in itens_transferencia:
        preco = item.item.preco_custo if item.item else 0
        quantidade = item.quantidade_recebida or item.quantidade_solicitada
        item.valor_item = quantidade * preco
        valor_total += item.valor_item
    
    context = {
        'requisicao': requisicao,
        'transferencia': transferencia,
        'itens_transferencia': itens_transferencia,
        'valor_total': valor_total,
    }
    
    return render(request, 'stock/requisicoes/guia_recebimento.html', context)


@login_required
@require_stock_access
def requisicao_transfer_stock(request, id):
    requisicao = get_object_or_404(RequisicaoStock, id=id)
    
    logger.info(f"=== INÍCIO TRANSFERÊNCIA REQ0004 ===")
    logger.info(f"Requisição ID: {requisicao.id}, Código: {requisicao.codigo}, Status: {requisicao.status}")
    
    if request.method == 'POST':
        try:
            logger.info(f"POST request recebido para transferência")
            if requisicao.status != 'APROVADA':
                logger.error(f"Requisição não está aprovada. Status atual: {requisicao.status}")
                messages.error(request, 'Apenas requisições aprovadas podem gerar transferências de stock.')
                return redirect('stock:requisicoes:detail', id=requisicao.id)
            
            logger.info(f"Requisição está aprovada ✓")
            
            # Verificar se há itens com quantidade atendida
            itens_com_atendimento = requisicao.itens.filter(quantidade_atendida__gt=0)
            logger.info(f"Itens com quantidade atendida: {itens_com_atendimento.count()}")
            
            if not itens_com_atendimento.exists():
                logger.warning(f"Nenhum item com quantidade atendida encontrado")
                messages.warning(request, 'Nenhum item possui quantidade atendida definida. Defina as quantidades atendidas antes de transferir o stock.')
                return redirect('stock:requisicoes:detail', id=requisicao.id)
            
            logger.info(f"Itens com quantidade atendida encontrados ✓")
            
            # Verificar se já existe uma transferência para esta requisição
            from .models_stock import TransferenciaStock, ItemTransferencia, MovimentoItem, TipoMovimentoStock
            
            codigo_transferencia = f"TRF{requisicao.codigo}"
            logger.info(f"Verificando transferência existente com código: {codigo_transferencia}")
            
            transferencia_existente = TransferenciaStock.objects.filter(
                codigo=codigo_transferencia
            ).first()
            
            if transferencia_existente:
                if transferencia_existente.status == 'RASCUNHO':
                    logger.info(f"Transferência em rascunho encontrada, deletando para reprocessar: {transferencia_existente.codigo}")
                    transferencia_existente.delete()
                else:
                    logger.warning(f"Transferência já existe: {transferencia_existente.codigo}, Status: {transferencia_existente.status}")
                    messages.warning(request, f'Já existe uma transferência para esta requisição: {transferencia_existente.codigo}')
                    return redirect('stock:requisicoes:detail', id=requisicao.id)
            
            logger.info(f"Nenhuma transferência existente encontrada ✓")
            
            # Buscar tipo de movimento para transferência
            tipo_transferencia = TipoMovimentoStock.objects.filter(
                codigo='TRF_INTERNA'
            ).first()
            
            if not tipo_transferencia:
                tipo_transferencia = TipoMovimentoStock.objects.create(
                    nome='Transferência Interna',
                    codigo='TRF_INTERNA',
                    descricao='Transferência de stock entre sucursais'
                )
            
            # Criar transferência principal
            # Para requisições internas, vamos usar a sucursal com maior estoque do primeiro item
            from .models_stock import StockItem
            
            primeiro_item = itens_com_atendimento.first()
            item_obj = primeiro_item.item or primeiro_item.produto
            logger.info(f"Primeiro item: {item_obj.nome}, Quantidade atendida: {primeiro_item.quantidade_atendida}")
            
            # Buscar sucursal com maior estoque para este item (excluindo a sucursal solicitante)
            stocks_disponiveis = StockItem.objects.filter(
                item=item_obj
            ).exclude(
                sucursal=requisicao.sucursal_origem  # Excluir a sucursal solicitante
            ).order_by('-quantidade_atual')
            
            logger.info(f"Stocks disponíveis encontrados: {stocks_disponiveis.count()}")
            
            if not stocks_disponiveis.exists():
                logger.error(f"Nenhum estoque disponível para {item_obj.nome}")
                messages.error(request, f'Nenhum estoque disponível para {item_obj.nome}.')
                return redirect('stock:requisicoes:detail', id=requisicao.id)
            
            sucursal_fornecedora = stocks_disponiveis.first().sucursal
            logger.info(f"Sucursal fornecedora: {sucursal_fornecedora.nome}")
            logger.info(f"Sucursal destino: {requisicao.sucursal_origem.nome}")
            
            logger.info(f"Criando transferência com código: {codigo_transferencia}")
            transferencia = TransferenciaStock.objects.create(
                codigo=codigo_transferencia,
                sucursal_origem=sucursal_fornecedora,  # Sucursal que fornece
                sucursal_destino=requisicao.sucursal_origem,  # Sucursal que recebe (quem solicitou)
                observacoes=f"Transferência baseada na requisição {requisicao.codigo}",
                criado_por=request.user
            )
            logger.info(f"Transferência criada com sucesso: {transferencia.id}")
            
            # Criar itens da transferência e movimentos de stock
            logger.info(f"Criando itens da transferência...")
            for item_requisicao in itens_com_atendimento:
                if item_requisicao.quantidade_atendida > 0:
                    logger.info(f"Processando item: {item_requisicao.item or item_requisicao.produto}, Quantidade: {item_requisicao.quantidade_atendida}")
                    
                    # Criar item da transferência
                    item_transferencia = ItemTransferencia.objects.create(
                        transferencia=transferencia,
                        item=item_requisicao.item or item_requisicao.produto,
                        quantidade_solicitada=item_requisicao.quantidade_atendida,
                        quantidade_recebida=0,  # Será atualizada quando confirmar recebimento
                        observacoes=f"Transferência para requisição {requisicao.codigo}"
                    )
                    logger.info(f"Item da transferência criado: {item_transferencia.id}")
                    
                    # Criar movimento de saída (sucursal fornecedora)
                    item_obj = item_requisicao.item or item_requisicao.produto
                    preco_custo = item_obj.preco_custo if hasattr(item_obj, 'preco_custo') else 0
                    
                    # Buscar tipo de movimento para saída
                    tipo_saida = TipoMovimentoStock.objects.filter(
                        codigo='SAIDA'
                    ).first()
                    
                    if not tipo_saida:
                        tipo_saida = TipoMovimentoStock.objects.create(
                            nome='Saída de Stock',
                            codigo='SAIDA',
                            descricao='Saída de stock da sucursal',
                            aumenta_estoque=False
                        )
                    
                    # Movimento de SAÍDA (sucursal fornecedora)
                    MovimentoItem.objects.create(
                        codigo=f"MOV{transferencia.codigo}{item_transferencia.id}S",
                        item=item_obj,
                        tipo_movimento=tipo_saida,
                        sucursal=sucursal_fornecedora,  # Sucursal que fornece
                        quantidade=item_requisicao.quantidade_atendida,
                        preco_unitario=preco_custo,
                        valor_total=preco_custo * item_requisicao.quantidade_atendida,
                        referencia=f"Transferência {transferencia.codigo}",
                        observacoes=f"Saída para requisição {requisicao.codigo}",
                        usuario=request.user
                    )
                    
                    # Buscar tipo de movimento para entrada
                    tipo_entrada = TipoMovimentoStock.objects.filter(
                        codigo='ENT_COMPRA'
                    ).first()
                    
                    if not tipo_entrada:
                        tipo_entrada = TipoMovimentoStock.objects.create(
                            nome='Entrada por Compra',
                            codigo='ENT_COMPRA',
                            descricao='Entrada de stock por compra',
                            aumenta_estoque=True
                        )
                    
                    # Movimento de ENTRADA (sucursal destino)
                    MovimentoItem.objects.create(
                        codigo=f"MOV{transferencia.codigo}{item_transferencia.id}E",
                        item=item_obj,
                        tipo_movimento=tipo_entrada,  # ENT_COMPRA (aumenta estoque)
                        sucursal=requisicao.sucursal_origem,  # Sucursal que recebe (quem solicitou)
                        quantidade=item_requisicao.quantidade_atendida,
                        preco_unitario=preco_custo,
                        valor_total=preco_custo * item_requisicao.quantidade_atendida,
                        referencia=f"Transferência {transferencia.codigo}",
                        observacoes=f"Entrada da requisição {requisicao.codigo}",
                        usuario=request.user
                    )
            
            # Marcar transferência como enviada (aguardando recebimento)
            logger.info(f"Marcando transferência como ENVIADA...")
            transferencia.status = 'ENVIADA'
            transferencia.data_envio = timezone.now()
            transferencia.save()
            logger.info(f"Transferência marcada como ENVIADA ✓")
            
            # Criar notificação para logística
            logger.info(f"Criando notificação para logística...")
            from .models_stock import NotificacaoLogisticaUnificada
            
            # Verificar se já existe notificação para esta transferência
            if not hasattr(transferencia, 'notificacao_logistica_unificada'):
                # Determinar prioridade (manual ou baseada no valor)
                prioridade_manual = request.session.get('prioridade_manual', '')
                if prioridade_manual:
                    prioridade = prioridade_manual
                    # Limpar da session após uso
                    if 'prioridade_manual' in request.session:
                        del request.session['prioridade_manual']
                else:
                    # Prioridade automática baseada no valor e urgência
                    valor_total = transferencia.valor_total
                    if valor_total > 10000:  # Transferências de alto valor
                        prioridade = 'ALTA'
                    elif valor_total > 5000:
                        prioridade = 'NORMAL'
                    else:
                        prioridade = 'BAIXA'
                
                # Criar notificação unificada
                notificacao = NotificacaoLogisticaUnificada.objects.create(
                    tipo_operacao='TRANSFERENCIA',
                    transferencia=transferencia,
                    status='PENDENTE',
                    prioridade=prioridade,
                    usuario_notificacao=request.user,
                    observacoes=f'Transferência automática da requisição {requisicao.codigo}'
                )
                logger.info(f"Notificação criada: {notificacao.id} ✓")
            else:
                logger.info(f"Notificação já existe para esta transferência ✓")
            
            # Marcar requisição como atendida
            logger.info(f"Marcando requisição como ATENDIDA...")
            requisicao.status = 'ATENDIDA'
            requisicao.data_atendimento = timezone.now()
            requisicao.save()
            logger.info(f"Requisição marcada como ATENDIDA ✓")
            
            logger.info(f"=== TRANSFERÊNCIA CONCLUÍDA COM SUCESSO ===")
            messages.success(request, f'Transferência de stock criada com sucesso! Código: {transferencia.codigo}')
            return redirect('stock:requisicoes:detail', id=requisicao.id)
            
        except Exception as e:
            logger.error(f"=== ERRO NA TRANSFERÊNCIA ===")
            logger.error(f"Erro ao criar transferência de stock: {e}")
            logger.error(f"Tipo do erro: {type(e).__name__}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            messages.error(request, f'Erro ao criar transferência de stock: {str(e)}')
            return redirect('stock:requisicoes:detail', id=requisicao.id)
    
    return redirect('stock:requisicoes:detail', id=requisicao.id)




@login_required
@require_stock_access
@require_http_methods(["POST"])
def compra_externa_update_preco(request, id, item_id):
    """Atualizar preço estimado de um item de compra externa"""
    requisicao = get_object_or_404(RequisicaoCompraExterna, id=id)
    item_requisicao = get_object_or_404(ItemRequisicaoCompraExterna, id=item_id, requisicao=requisicao)
    
    # Validar se a requisição pode ser editada
    if requisicao.status not in ['RASCUNHO', 'PENDENTE', 'APROVADA']:
        messages.error(request, 'Não é possível editar preços de requisições finalizadas ou processadas.')
        return redirect('stock:requisicoes:compra_externa_detail', id=requisicao.id)
    
    if request.method == 'POST':
        try:
            preco_unitario_estimado = request.POST.get('preco_unitario_estimado')
            
            if not preco_unitario_estimado:
                messages.error(request, 'Preço unitário é obrigatório.')
                return redirect('stock:requisicoes:compra_externa_detail', id=requisicao.id)
            
            preco = Decimal(preco_unitario_estimado)
            
            if preco <= 0:
                messages.error(request, 'Preço deve ser maior que zero.')
                return redirect('stock:requisicoes:compra_externa_detail', id=requisicao.id)
            
            item_requisicao.preco_unitario_estimado = preco
            item_requisicao.save()
            
            messages.success(request, f'Preço estimado atualizado para {item_requisicao.item.nome}: {preco} MT')
            return redirect('stock:requisicoes:compra_externa_detail', id=requisicao.id)
            
        except (ValueError, InvalidOperation) as e:
            messages.error(request, 'Preço inválido.')
            return redirect('stock:requisicoes:compra_externa_detail', id=requisicao.id)
        except Exception as e:
            logger.error(f"Erro ao atualizar preço: {e}")
            messages.error(request, 'Erro ao atualizar preço.')
            return redirect('stock:requisicoes:compra_externa_detail', id=requisicao.id)
    
    return redirect('stock:requisicoes:compra_externa_detail', id=requisicao.id)


@login_required
@require_stock_access
def compra_externa_delete(request, id):
    """Deletar requisição de compra externa"""
    requisicao = get_object_or_404(RequisicaoCompraExterna, id=id)
    
    if request.method == 'POST':
        try:
            if requisicao.status not in ['RASCUNHO', 'PENDENTE', 'REJEITADA']:
                messages.error(request, 'Apenas requisições em rascunho, pendentes ou rejeitadas podem ser deletadas.')
                return redirect('stock:requisicoes:compra_externa_detail', id=requisicao.id)
            
            codigo = requisicao.codigo
            requisicao.delete()
            
            return redirect('stock:requisicoes:list')
            
        except Exception as e:
            logger.error(f"Erro ao deletar requisição: {e}")
            messages.error(request, 'Erro ao deletar requisição.')
            return redirect('stock:requisicoes:compra_externa_detail', id=requisicao.id)
    
    return redirect('stock:requisicoes:compra_externa_detail', id=requisicao.id)


@login_required
def api_stock_por_sucursal(request):
    """API para buscar stock de um item específico em todas as sucursais"""
    item_id = request.GET.get('item_id')
    
    if not item_id:
        return JsonResponse({'error': 'Item é obrigatório'}, status=400)
    
    try:
        item = Item.objects.get(id=item_id)
        stocks = StockItem.objects.filter(
            item=item,
            quantidade_atual__gt=0
        ).select_related('sucursal').order_by('sucursal__nome')
        
        stocks_data = []
        for stock in stocks:
            stocks_data.append({
                'sucursal_id': stock.sucursal.id,
                'sucursal_nome': stock.sucursal.nome,
                'quantidade_disponivel': float(stock.quantidade_atual),
                'quantidade_reservada': float(stock.quantidade_reservada),
                'estoque_minimo': float(item.estoque_minimo),
                'estoque_maximo': float(item.estoque_maximo),
            })
        
        return JsonResponse({
            'item': {
                'id': item.id,
                'nome': item.nome,
                'codigo': item.codigo,
                'tipo': item.tipo,
                'unidade_medida': item.unidade_medida,
            },
            'stocks': stocks_data
        })
        
    except Item.DoesNotExist:
        return JsonResponse({'error': 'Item não encontrado'}, status=404)
    except Exception as e:
        logger.error(f"Erro na API de stock por sucursal: {e}")
        return JsonResponse({'error': 'Erro interno do servidor'}, status=500)


@login_required
def api_sugestao_quantidade(request):
    """API para calcular sugestão de quantidade baseada no stock baixo"""
    item_id = request.GET.get('item_id')
    sucursal_destino_id = request.GET.get('sucursal_destino_id')
    
    if not item_id or not sucursal_destino_id:
        return JsonResponse({'error': 'Item e sucursal são obrigatórios'}, status=400)
    
    try:
        item = Item.objects.get(id=item_id)
        stock_destino = StockItem.objects.filter(
            item=item,
            sucursal_id=sucursal_destino_id
        ).first()
        
        if not stock_destino:
            return JsonResponse({'error': 'Item não disponível na sucursal de destino'}, status=404)
        
        # Calcular sugestões baseadas em diferentes cenários
        estoque_minimo = item.estoque_minimo
        estoque_maximo = item.estoque_maximo
        stock_atual = stock_destino.quantidade_atual
        
        sugestoes = {
            'minima': max(1, estoque_minimo - stock_atual),
            'recomendada': max(1, (estoque_minimo + estoque_maximo) // 2 - stock_atual),
            'maxima': min(estoque_maximo - stock_atual, stock_destino.quantidade_atual),
            'estoque_minimo': estoque_minimo,
            'estoque_maximo': estoque_maximo,
            'stock_atual': stock_atual,
        }
        
        # Limitar sugestões ao stock disponível
        sugestoes['minima'] = min(sugestoes['minima'], stock_destino.quantidade_atual)
        sugestoes['recomendada'] = min(sugestoes['recomendada'], stock_destino.quantidade_atual)
        
        return JsonResponse({
            'item': {
                'id': item.id,
                'nome': item.nome,
                'codigo': item.codigo,
                'unidade_medida': item.unidade_medida,
            },
            'sugestoes': sugestoes,
            'stock_disponivel': stock_destino.quantidade_atual,
        })
        
    except Item.DoesNotExist:
        return JsonResponse({'error': 'Item não encontrado'}, status=404)
    except Exception as e:
        logger.error(f"Erro na API de sugestão de quantidade: {e}")
        return JsonResponse({'error': 'Erro interno do servidor'}, status=500)


@login_required
@require_stock_access
def verificar_stock_baixo(request):
    """Verificar itens com stock baixo por sucursal"""
    from django.db.models import F
    
    # Obter parâmetros de filtro
    sucursal_id = request.GET.get('sucursal', '').strip()
    
    # Buscar itens com stock baixo
    itens_stock_baixo = StockItem.objects.select_related(
        'item', 'sucursal'
    ).filter(
        quantidade_atual__lte=F('item__estoque_minimo')
    ).order_by('sucursal__nome', 'item__tipo', 'item__nome')
    
    # Aplicar filtro de sucursal se especificado
    if sucursal_id:
        itens_stock_baixo = itens_stock_baixo.filter(sucursal_id=sucursal_id)
    
    # Agrupar por sucursal
    sucursais_com_stock_baixo = {}
    for stock_item in itens_stock_baixo:
        sucursal = stock_item.sucursal
        if sucursal.id not in sucursais_com_stock_baixo:
            sucursais_com_stock_baixo[sucursal.id] = {
                'sucursal': sucursal,
                'itens': [],
                'total_itens': 0,
                'valor_total': 0
            }
        
        sucursais_com_stock_baixo[sucursal.id]['itens'].append(stock_item)
        sucursais_com_stock_baixo[sucursal.id]['total_itens'] += 1
        sucursais_com_stock_baixo[sucursal.id]['valor_total'] += stock_item.item.preco_custo * stock_item.quantidade_atual
    
    # Estatísticas gerais
    total_sucursais_afetadas = len(sucursais_com_stock_baixo)
    total_itens_stock_baixo = sum(data['total_itens'] for data in sucursais_com_stock_baixo.values())
    valor_total_stock_baixo = sum(data['valor_total'] for data in sucursais_com_stock_baixo.values())
    
    # Obter sucursais para o filtro
    sucursais = Sucursal.objects.all().order_by('nome')
    
    context = {
        'sucursais_com_stock_baixo': sucursais_com_stock_baixo,
        'total_sucursais_afetadas': total_sucursais_afetadas,
        'total_itens_stock_baixo': total_itens_stock_baixo,
        'valor_total_stock_baixo': valor_total_stock_baixo,
        'sucursais': sucursais,
        'sucursal_id': sucursal_id,
    }
    
    return render(request, 'stock/requisicoes/verificar_stock_baixo.html', context)
