from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum, F, Count
from django.http import JsonResponse
from django.utils import timezone
from decimal import Decimal

from .models_stock import (
    TransferenciaStock, ItemTransferencia, Item, StockItem, 
    MovimentoItem, TipoMovimentoStock
)
from .models_base import Sucursal
from .decorators import require_stock_access, get_user_sucursais


# =============================================================================
# VIEWS DE TRANSFERÊNCIAS
# =============================================================================

@login_required
@require_stock_access
def transferencias_list(request):
    """Lista de transferências"""
    # Obter sucursais que o usuário pode ver
    sucursais_permitidas = get_user_sucursais(request, for_modification=False)
    sucursais_ids = [s.id for s in sucursais_permitidas]
    
    # Filtrar transferências onde o usuário está envolvido
    transferencias = TransferenciaStock.objects.filter(
        Q(sucursal_origem_id__in=sucursais_ids) | 
        Q(sucursal_destino_id__in=sucursais_ids)
    ).select_related('sucursal_origem', 'sucursal_destino', 'criado_por').order_by('-data_criacao')
    
    # Filtros e pesquisa
    search = request.GET.get('search', '').strip()
    status = request.GET.get('status')
    sucursal_id = request.GET.get('sucursal')
    
    # Aplicar pesquisa
    if search:
        transferencias = transferencias.filter(
            Q(codigo__icontains=search) |
            Q(criado_por__username__icontains=search) |
            Q(confirmado_por__username__icontains=search) |
            Q(sucursal_origem__nome__icontains=search) |
            Q(sucursal_destino__nome__icontains=search) |
            Q(observacoes__icontains=search)
        )
    
    # Aplicar filtros
    if status:
        transferencias = transferencias.filter(status=status)
    if sucursal_id and int(sucursal_id) in sucursais_ids:
        transferencias = transferencias.filter(
            Q(sucursal_origem_id=sucursal_id) | Q(sucursal_destino_id=sucursal_id)
        )
    
    # Paginação
    paginator = Paginator(transferencias, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'sucursais': sucursais_permitidas,
        'status_choices': TransferenciaStock.STATUS_CHOICES,
        'search': search,
        'status': status,
        'sucursal_selecionada': int(sucursal_id) if sucursal_id else None,
    }
    return render(request, 'stock/transferencias/list.html', context)


@login_required
@require_stock_access
def transferencia_create(request):
    """Criar nova transferência"""
    # Obter sucursais que o usuário pode modificar
    sucursais_permitidas = get_user_sucursais(request, for_modification=True)
    
    if not sucursais_permitidas:
        messages.error(request, 'Você não tem permissão para criar transferências.')
        return redirect('stock:transferencias:list')
    
    # Para administradores, permitir escolher qualquer sucursal de origem
    is_admin = request.user.perfil.pode_acessar_todas_sucursais if hasattr(request.user, 'perfil') else False
    
    if request.method == 'POST':
        sucursal_destino_id = request.POST.get('sucursal_destino')
        observacoes = request.POST.get('observacoes', '')
        
        if not sucursal_destino_id:
            messages.error(request, 'Selecione a sucursal de destino.')
            return redirect('stock:transferencias:create')
        
        try:
            sucursal_destino = Sucursal.objects.get(id=sucursal_destino_id)
            
            # Para administradores, permitir escolher sucursal de origem
            if is_admin:
                sucursal_origem_id = request.POST.get('sucursal_origem')
                if not sucursal_origem_id:
                    messages.error(request, 'Selecione a sucursal de origem.')
                    return redirect('stock:transferencias:create')
                sucursal_origem = Sucursal.objects.get(id=sucursal_origem_id)
            else:
                sucursal_origem = sucursais_permitidas[0]  # Usuário só pode ter uma sucursal para modificação
            
            if sucursal_origem.id == sucursal_destino.id:
                messages.error(request, 'Não é possível transferir para a mesma sucursal.')
                return redirect('stock:transferencias:create')
            
            # Criar transferência
            transferencia = TransferenciaStock.objects.create(
                sucursal_origem=sucursal_origem,
                sucursal_destino=sucursal_destino,
                observacoes=observacoes,
                criado_por=request.user
            )
            
            return redirect('stock:transferencias:detail', id=transferencia.id)
            
        except Sucursal.DoesNotExist:
            messages.error(request, 'Sucursal de destino não encontrada.')
            return redirect('stock:transferencias:create')
        except Exception as e:
            messages.error(request, f'Erro ao criar transferência: {str(e)}')
            return redirect('stock:transferencias:create')
    
    # Obter sucursais disponíveis
    if is_admin:
        # Administradores podem escolher qualquer sucursal
        sucursais_origem = Sucursal.objects.filter(ativa=True).order_by('nome')
        sucursais_destino = Sucursal.objects.filter(ativa=True).order_by('nome')
        sucursal_origem_default = None
    else:
        # Usuários normais só podem usar sua própria sucursal
        sucursal_origem_default = sucursais_permitidas[0] if sucursais_permitidas else None
        sucursais_origem = [sucursal_origem_default] if sucursal_origem_default else []
        sucursais_destino = Sucursal.objects.filter(ativa=True).exclude(
            id=sucursal_origem_default.id
        ).order_by('nome') if sucursal_origem_default else Sucursal.objects.filter(ativa=True).order_by('nome')
    
    context = {
        'sucursais_destino': sucursais_destino,
        'sucursais_origem': sucursais_origem,
        'sucursal_origem_default': sucursal_origem_default,
        'is_admin': is_admin,
    }
    return render(request, 'stock/transferencias/create.html', context)


@login_required
@require_stock_access
def transferencia_detail(request, id):
    """Detalhes de uma transferência"""
    transferencia = get_object_or_404(TransferenciaStock, id=id)
    
    # Verificar se é administrador
    is_admin = request.user.perfil.pode_acessar_todas_sucursais if hasattr(request.user, 'perfil') else False
    
    # Verificar se o usuário tem acesso a esta transferência
    sucursais_permitidas = get_user_sucursais(request, for_modification=False)
    sucursais_ids = [s.id for s in sucursais_permitidas]
    
    if not is_admin and transferencia.sucursal_origem.id not in sucursais_ids and transferencia.sucursal_destino.id not in sucursais_ids:
        messages.error(request, 'Você não tem acesso a esta transferência.')
        return redirect('stock:transferencias:list')
    
    # Obter itens da transferência
    itens = transferencia.itens.select_related('item').all()
    
    # Verificar se pode adicionar itens (apenas sucursal de origem e status rascunho/pendente)
    if is_admin:
        pode_adicionar_itens = transferencia.status in ['RASCUNHO', 'PENDENTE']
    else:
        pode_adicionar_itens = (
            transferencia.sucursal_origem.id in [s.id for s in get_user_sucursais(request, for_modification=True)] and
            transferencia.status in ['RASCUNHO', 'PENDENTE']
        )
    
    # Verificar se pode confirmar envio
    if is_admin:
        pode_confirmar_envio = transferencia.status == 'PENDENTE' and itens.exists()
    else:
        pode_confirmar_envio = (
            transferencia.sucursal_origem.id in [s.id for s in get_user_sucursais(request, for_modification=True)] and
            transferencia.status == 'PENDENTE' and
            itens.exists()
        )
    
    # Verificar se pode receber
    if is_admin:
        pode_receber = transferencia.status == 'ENVIADA'
    else:
        pode_receber = (
            transferencia.sucursal_destino.id in [s.id for s in get_user_sucursais(request, for_modification=True)] and
            transferencia.status == 'ENVIADA'
        )
    
    # Verificar se pode cancelar
    if is_admin:
        pode_cancelar = transferencia.pode_cancelar
    else:
        pode_cancelar = (
            transferencia.sucursal_origem.id in [s.id for s in get_user_sucursais(request, for_modification=True)] and
            transferencia.pode_cancelar
        )
    
    # Verificar se pode apagar (apenas rascunhos sem itens)
    pode_apagar = (
        transferencia.status == 'RASCUNHO' and 
        not transferencia.itens.exists() and
        (is_admin or transferencia.sucursal_origem.id in [s.id for s in get_user_sucursais(request, for_modification=True)])
    )
    
    context = {
        'transferencia': transferencia,
        'itens': itens,
        'pode_adicionar_itens': pode_adicionar_itens,
        'pode_confirmar_envio': pode_confirmar_envio,
        'pode_receber': pode_receber,
        'pode_cancelar': pode_cancelar,
        'pode_apagar': pode_apagar,
    }
    return render(request, 'stock/transferencias/detail.html', context)


@login_required
@require_stock_access
def transferencia_add_item(request, id):
    """Adicionar item à transferência"""
    transferencia = get_object_or_404(TransferenciaStock, id=id)
    
    # Verificar se é administrador
    is_admin = request.user.perfil.pode_acessar_todas_sucursais if hasattr(request.user, 'perfil') else False
    
    # Verificar permissões
    if not is_admin:
        sucursais_permitidas = get_user_sucursais(request, for_modification=True)
        if transferencia.sucursal_origem.id not in [s.id for s in sucursais_permitidas]:
            messages.error(request, 'Você não tem permissão para modificar esta transferência.')
            return redirect('stock:transferencias:detail', id=id)
    
    if transferencia.status not in ['RASCUNHO', 'PENDENTE']:
        messages.error(request, 'Não é possível adicionar itens a uma transferência já enviada.')
        return redirect('stock:transferencias:detail', id=id)
    
    if request.method == 'POST':
        item_id = request.POST.get('item')
        quantidade = request.POST.get('quantidade')
        observacoes = request.POST.get('observacoes', '')
        
        if not all([item_id, quantidade]):
            messages.error(request, 'Preencha todos os campos obrigatórios.')
            return redirect('stock:transferencias:add_item', id=id)
        
        try:
            item = Item.objects.get(id=item_id)
            quantidade = int(quantidade)
            
            # Verificar se já existe item para este produto/material
            item_existente = ItemTransferencia.objects.filter(
                transferencia=transferencia,
                item=item
            ).first()
            
            if item_existente:
                item_existente.quantidade_solicitada += quantidade
                item_existente.observacoes = observacoes
                item_existente.save()
                messages.success(request, f'Quantidade atualizada para {item.nome}.')
            else:
                ItemTransferencia.objects.create(
                    transferencia=transferencia,
                    item=item,
                    quantidade_solicitada=quantidade,
                    observacoes=observacoes
                )
            
            # Promover transferência de RASCUNHO para PENDENTE se for o primeiro item
            if transferencia.status == 'RASCUNHO':
                transferencia.status = 'PENDENTE'
                transferencia.save()
            
            return redirect('stock:transferencias:detail', id=id)
            
        except Item.DoesNotExist:
            messages.error(request, 'Item não encontrado.')
        except ValueError:
            messages.error(request, 'Quantidade deve ser um número válido.')
        except Exception as e:
            messages.error(request, f'Erro ao adicionar item: {str(e)}')
    
    # Obter itens disponíveis na sucursal de origem
    itens_disponiveis = Item.objects.filter(
        status='ATIVO',
        stocks_sucursais__sucursal=transferencia.sucursal_origem,
        stocks_sucursais__quantidade_atual__gt=0
    ).distinct().order_by('tipo', 'nome')
    
    context = {
        'transferencia': transferencia,
        'itens': itens_disponiveis,
    }
    return render(request, 'stock/transferencias/add_item.html', context)


@login_required
@require_stock_access
def transferencia_confirmar_envio(request, id):
    """Confirmar envio da transferência"""
    transferencia = get_object_or_404(TransferenciaStock, id=id)
    
    # Verificar se é administrador
    is_admin = request.user.perfil.pode_acessar_todas_sucursais if hasattr(request.user, 'perfil') else False
    
    # Verificar permissões
    if not is_admin:
        sucursais_permitidas = get_user_sucursais(request, for_modification=True)
        if transferencia.sucursal_origem.id not in [s.id for s in sucursais_permitidas]:
            messages.error(request, 'Você não tem permissão para confirmar esta transferência.')
            return redirect('stock:transferencias:detail', id=id)
    
    if transferencia.status != 'PENDENTE':
        messages.error(request, 'Esta transferência já foi processada.')
        return redirect('stock:transferencias:detail', id=id)
    
    if not transferencia.itens.exists():
        messages.error(request, 'Não é possível enviar uma transferência sem itens.')
        return redirect('stock:transferencias:detail', id=id)
    
    # Verificar se há estoque suficiente para todos os itens
    for item_transferencia in transferencia.itens.all():
        # Usar item se disponível (sistema unificado), senão usar produto (sistema antigo)
        if item_transferencia.item:
            item_obj = item_transferencia.item
            stock_origem = StockItem.objects.filter(
                item=item_obj,
                sucursal=transferencia.sucursal_origem
            ).first()
        else:
            item_obj = item_transferencia.produto
            stock_origem = StockItem.objects.filter(
                item__codigo=item_obj.codigo,
                sucursal=transferencia.sucursal_origem
            ).first()
        
        if not stock_origem or stock_origem.quantidade_atual < item_transferencia.quantidade_solicitada:
            messages.error(request, f'Estoque insuficiente para {item_obj.nome}. Disponível: {stock_origem.quantidade_atual if stock_origem else 0}')
            return redirect('stock:transferencias:detail', id=id)
    
    # Confirmar envio
    transferencia.status = 'ENVIADA'
    transferencia.data_envio = timezone.now()
    transferencia.save()
    
    return redirect('stock:transferencias:detail', id=id)


@login_required
@require_stock_access
def transferencia_apagar(request, id):
    """Apagar transferência em rascunho"""
    transferencia = get_object_or_404(TransferenciaStock, id=id)
    
    # Verificar se é administrador
    is_admin = request.user.perfil.pode_acessar_todas_sucursais if hasattr(request.user, 'perfil') else False
    
    # Verificar permissões
    if not is_admin:
        sucursais_permitidas = get_user_sucursais(request, for_modification=True)
        if transferencia.sucursal_origem.id not in [s.id for s in sucursais_permitidas]:
            messages.error(request, 'Você não tem permissão para apagar esta transferência.')
            return redirect('stock:transferencias:detail', id=id)
    
    if transferencia.status != 'RASCUNHO':
        messages.error(request, 'Apenas transferências em rascunho podem ser apagadas.')
        return redirect('stock:transferencias:detail', id=id)
    
    if transferencia.itens.exists():
        messages.error(request, 'Não é possível apagar uma transferência que possui itens.')
        return redirect('stock:transferencias:detail', id=id)
    
    codigo = transferencia.codigo
    transferencia.delete()
    
    messages.success(request, f'Transferência {codigo} apagada com sucesso!')
    return redirect('stock:transferencias:list')


@login_required
@require_stock_access
def transferencia_receber(request, id):
    """Receber transferência"""
    transferencia = get_object_or_404(TransferenciaStock, id=id)
    
    # Verificar se é administrador
    is_admin = request.user.perfil.pode_acessar_todas_sucursais if hasattr(request.user, 'perfil') else False
    
    # Verificar permissões
    if not is_admin:
        sucursais_permitidas = get_user_sucursais(request, for_modification=True)
        if transferencia.sucursal_destino.id not in [s.id for s in sucursais_permitidas]:
            messages.error(request, 'Você não tem permissão para receber esta transferência.')
            return redirect('stock:transferencias:detail', id=id)
    
    if transferencia.status != 'ENVIADA':
        messages.error(request, 'Esta transferência não está pronta para recebimento.')
        return redirect('stock:transferencias:detail', id=id)
    
    if request.method == 'POST':
        # Processar recebimento
        itens_recebidos = []
        for item in transferencia.itens.all():
            quantidade_recebida = request.POST.get(f'quantidade_recebida_{item.id}')
            if quantidade_recebida:
                try:
                    quantidade_recebida = int(quantidade_recebida)
                    if quantidade_recebida > 0:
                        item.quantidade_recebida = quantidade_recebida
                        item.save()
                        itens_recebidos.append(item)
                except ValueError:
                    continue
        
        if not itens_recebidos:
            messages.error(request, 'Nenhum item foi recebido.')
            return redirect('stock:transferencias:detail', id=id)
        
        # Confirmar recebimento
        transferencia.status = 'RECEBIDA'
        transferencia.data_recebimento = timezone.now()
        transferencia.confirmado_por = request.user
        transferencia.save()
        
        # Criar movimentações para auditoria (o signal atualizará o stock automaticamente)
        tipo_saida = TipoMovimentoStock.objects.filter(aumenta_estoque=False).first()
        tipo_entrada = TipoMovimentoStock.objects.filter(aumenta_estoque=True).first()
        
        for item in itens_recebidos:
            # Usar item diretamente do modelo unificado
            if not item.item:
                messages.error(request, f'Item não encontrado para {item.transferencia.codigo}')
                continue
            item_obj = item.item
            
            # Criar movimento de entrada (destino) - apenas entrada, pois a saída já foi criada na origem
            if tipo_entrada:
                MovimentoItem.objects.create(
                    item=item_obj,
                    sucursal=transferencia.sucursal_destino,
                    tipo_movimento=tipo_entrada,
                    quantidade=item.quantidade_recebida,
                    preco_unitario=item_obj.preco_custo,
                    referencia=f'Recebimento {transferencia.codigo}',
                    observacoes=f'Confirmação de recebimento da transferência {transferencia.codigo}',
                    usuario=request.user
                )
        
        return redirect('stock:transferencias:detail', id=id)
    
    context = {
        'transferencia': transferencia,
        'itens': transferencia.itens.select_related('item').all(),
    }
    return render(request, 'stock/transferencias/receber.html', context)


@login_required
@require_stock_access
def transferencia_cancelar(request, id):
    """Cancelar transferência"""
    transferencia = get_object_or_404(TransferenciaStock, id=id)
    
    # Verificar permissões
    sucursais_permitidas = get_user_sucursais(request, for_modification=True)
    if transferencia.sucursal_origem.id not in [s.id for s in sucursais_permitidas]:
        messages.error(request, 'Você não tem permissão para cancelar esta transferência.')
        return redirect('stock:transferencias:detail', id=id)
    
    if not transferencia.pode_cancelar:
        messages.error(request, 'Esta transferência não pode ser cancelada.')
        return redirect('stock:transferencias:detail', id=id)
    
    transferencia.status = 'CANCELADA'
    transferencia.save()
    
    messages.success(request, f'Transferência {transferencia.codigo} cancelada.')
    return redirect('stock:transferencias:detail', id=id)


@login_required
@require_stock_access
def verificar_stock_sucursais(request):
    """Verificar stock disponível por sucursal"""
    # Obter sucursais que o usuário pode ver
    sucursais_permitidas = get_user_sucursais(request, for_modification=False)
    sucursais_ids = [s.id for s in sucursais_permitidas]
    
    # Verificar se é administrador
    is_admin = request.user.perfil.pode_acessar_todas_sucursais if hasattr(request.user, 'perfil') else False
    
    if is_admin:
        # Administradores podem ver todas as sucursais
        sucursais = Sucursal.objects.filter(ativa=True).order_by('nome')
    else:
        # Usuários normais só veem suas sucursais
        sucursais = sucursais_permitidas
    
    # Dados de stock por sucursal
    dados_stock = []
    
    for sucursal in sucursais:
        # Stock unificado de itens
        itens_stock = StockItem.objects.filter(
            sucursal=sucursal,
            quantidade_atual__gt=0
        ).select_related('item').order_by('item__tipo', 'item__nome')
        
        # Separar produtos e materiais
        produtos_stock = itens_stock.filter(item__tipo='PRODUTO')
        materiais_stock = itens_stock.filter(item__tipo='MATERIAL')
        
        # Calcular totais
        total_produtos = produtos_stock.count()
        total_materiais = materiais_stock.count()
        total_itens = total_produtos + total_materiais
        
        # Valor total do stock (aproximado)
        valor_total = sum(
            stock.quantidade_atual * stock.item.preco_custo 
            for stock in itens_stock
        )
        
        dados_stock.append({
            'sucursal': sucursal,
            'produtos': produtos_stock,
            'materiais': materiais_stock,
            'total_produtos': total_produtos,
            'total_materiais': total_materiais,
            'total_itens': total_itens,
            'valor_total': valor_total,
            'tem_stock': total_itens > 0
        })
    
    # Ordenar por sucursal com stock primeiro
    dados_stock.sort(key=lambda x: (not x['tem_stock'], x['sucursal'].nome))
    
    context = {
        'dados_stock': dados_stock,
        'is_admin': is_admin,
        'total_sucursais': len(sucursais),
        'sucursais_com_stock': len([d for d in dados_stock if d['tem_stock']]),
        'sucursais_sem_stock': len([d for d in dados_stock if not d['tem_stock']]),
        'cache_timestamp': timezone.now().timestamp(),  # Para cache busting
    }
    
    return render(request, 'stock/transferencias/verificar_stock.html', context)


@login_required
@require_stock_access
def guia_transferencia(request, id):
    """Gerar Guia de Transferência (documento impressível)"""
    transferencia = get_object_or_404(TransferenciaStock, id=id)
    
    # Verificar se é administrador
    is_admin = request.user.perfil.pode_acessar_todas_sucursais if hasattr(request.user, 'perfil') else False
    
    # Verificar permissões
    if not is_admin:
        sucursais_permitidas = get_user_sucursais(request, for_modification=False)
        if transferencia.sucursal_origem.id not in [s.id for s in sucursais_permitidas] and \
           transferencia.sucursal_destino.id not in [s.id for s in sucursais_permitidas]:
            messages.error(request, 'Você não tem permissão para visualizar esta transferência.')
            return redirect('stock:transferencias:list')
    
    # Verificar se a transferência está no status correto para gerar guia
    if transferencia.status not in ['ENVIADA', 'RECEBIDA']:
        messages.error(request, 'A guia de transferência só pode ser gerada após o envio da transferência.')
        return redirect('stock:transferencias:detail', id=id)
    
    # Buscar itens da transferência e calcular valores
    itens_transferencia_list = []
    valor_total = 0
    
    for item in transferencia.itens.all():
        preco = item.item.preco_custo if item.item else 0
        quantidade = item.quantidade_solicitada
        valor_item = quantidade * preco
        
        itens_transferencia_list.append({
            'item': item,
            'valor_item': valor_item,
            'quantidade': quantidade,
            'preco': preco
        })
        valor_total += valor_item
    
    context = {
        'transferencia': transferencia,
        'itens_transferencia': itens_transferencia_list,
        'valor_total': valor_total,
    }
    
    return render(request, 'stock/transferencias/guia_transferencia.html', context)


@login_required
@require_stock_access
def nota_recebimento(request, id):
    """Gerar Nota de Recebimento (documento impressível)"""
    transferencia = get_object_or_404(TransferenciaStock, id=id)
    
    # Verificar se é administrador
    is_admin = request.user.perfil.pode_acessar_todas_sucursais if hasattr(request.user, 'perfil') else False
    
    # Verificar permissões
    if not is_admin:
        sucursais_permitidas = get_user_sucursais(request, for_modification=False)
        if transferencia.sucursal_origem.id not in [s.id for s in sucursais_permitidas] and \
           transferencia.sucursal_destino.id not in [s.id for s in sucursais_permitidas]:
            messages.error(request, 'Você não tem permissão para visualizar esta transferência.')
            return redirect('stock:transferencias:list')
    
    # Verificar se a transferência foi recebida
    if transferencia.status != 'RECEBIDA':
        messages.error(request, 'A nota de recebimento só pode ser gerada após o recebimento da transferência.')
        return redirect('stock:transferencias:detail', id=id)
    
    # Buscar itens da transferência e calcular valores
    itens_transferencia_list = []
    valor_total = 0
    
    for item in transferencia.itens.all():
        preco = item.item.preco_custo if item.item else 0
        quantidade = item.quantidade_recebida or item.quantidade_solicitada
        valor_item = quantidade * preco
        
        itens_transferencia_list.append({
            'item': item,
            'valor_item': valor_item,
            'quantidade': quantidade,
            'preco': preco
        })
        valor_total += valor_item
    
    context = {
        'transferencia': transferencia,
        'itens_transferencia': itens_transferencia_list,
        'valor_total': valor_total,
    }
    
    return render(request, 'stock/transferencias/nota_recebimento.html', context)
