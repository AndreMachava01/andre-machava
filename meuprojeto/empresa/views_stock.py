from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Sum, F, Count, Case, When, IntegerField
from django.http import JsonResponse, HttpResponseBadRequest
from django.core.exceptions import ValidationError
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.core.serializers.json import DjangoJSONEncoder
from decimal import Decimal, InvalidOperation
import json
import logging

logger = logging.getLogger(__name__)

from .models_stock import (
    CategoriaProduto, Fornecedor, Receita, ItemReceita,
    StockItem, TipoMovimentoStock, MovimentoItem, FornecedorProduto,
    Item, MovimentoItem
)
from .models_base import Sucursal
from .decorators import require_stock_access, require_sucursal_access, get_user_sucursais

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_chart_data_for_entity(entity_model, status_field='status', categoria_field='categoria'):
    """Helper function to get chart data for any entity (Produto, Material, etc.)"""
    try:
        # Status data
        ativos = entity_model.objects.filter(**{status_field: 'ATIVO'}).count()
        inativos = entity_model.objects.filter(**{status_field: 'INATIVO'}).count()
        pendentes = entity_model.objects.filter(**{status_field: 'PENDENTE'}).count()
        
        # Estoque baixo (if applicable)
        estoque_baixo = 0
        if hasattr(entity_model, 'quantidade_atual') and hasattr(entity_model, 'estoque_minimo'):
            estoque_baixo = entity_model.objects.filter(
                quantidade_atual__lte=F('estoque_minimo')
            ).count()
        
        # Top categorias
        if categoria_field:
            # Para o modelo Item unificado, contar usando o campo 'categoria'
            top_categorias = CategoriaProduto.objects.annotate(
                total_items=Count('item')
            ).filter(
                Q(tipo='PRODUTO') | Q(tipo='AMBOS') | Q(tipo='TODOS'),
                ativa=True
            ).order_by('-total_items')[:5]
            
            categorias_labels = json.dumps([cat.nome for cat in top_categorias], cls=DjangoJSONEncoder)
            categorias_data = json.dumps([cat.total_items for cat in top_categorias], cls=DjangoJSONEncoder)
        else:
            categorias_labels = json.dumps([], cls=DjangoJSONEncoder)
            categorias_data = json.dumps([], cls=DjangoJSONEncoder)
        
        return {
            'ativos': ativos,
            'inativos': inativos,
            'pendentes': pendentes,
            'estoque_baixo': estoque_baixo,
            'categorias_count': CategoriaProduto.objects.filter(ativa=True).count(),
            'categorias_labels': categorias_labels,
            'categorias_data': categorias_data,
        }
    except Exception as e:
        logger.error(f"Erro ao obter dados de gráfico para {entity_model.__name__}: {e}")
        return {
            'ativos': 0,
            'inativos': 0,
            'pendentes': 0,
            'estoque_baixo': 0,
            'categorias_count': 0,
            'categorias_labels': json.dumps([], cls=DjangoJSONEncoder),
            'categorias_data': json.dumps([], cls=DjangoJSONEncoder),
        }

# =============================================================================
# VIEWS PRINCIPAIS DO STOCK
# =============================================================================

@login_required
@require_stock_access
def stock_main(request):
    """Página principal do módulo de gestão de stock"""
    try:
        # Usuários podem ver todas as sucursais
        sucursais_permitidas = get_user_sucursais(request, for_modification=False)
        
        # Contadores de notificações
        from .models_stock import NotificacaoStock
        total_notificacoes = NotificacaoStock.objects.filter(
            Q(usuario_destinatario=request.user) | Q(usuario_destinatario__isnull=True)
        ).count()
        
        notificacoes_nao_lidas = NotificacaoStock.objects.filter(
            Q(usuario_destinatario=request.user) | Q(usuario_destinatario__isnull=True),
            lida=False
        ).count()
        
        # Período para movimentações (últimos 30 dias)
        from django.utils import timezone
        from datetime import timedelta
        data_limite = timezone.now() - timedelta(days=30)
        
        # Métricas de Logística
        from .models_stock import RastreamentoEntrega
        
        # Rastreamentos em trânsito
        rastreamentos_em_transito = RastreamentoEntrega.objects.filter(
            status_atual__in=['COLETADO', 'EM_TRANSITO', 'EM_DISTRIBUICAO']
        ).count()
        
        # Entregas pendentes (últimos 7 dias)
        from datetime import timedelta
        data_limite_entregas = timezone.now() - timedelta(days=7)
        entregas_pendentes = RastreamentoEntrega.objects.filter(
            status_atual='PENDENTE',
            data_criacao__gte=data_limite_entregas
        ).count()

        context = {
            # Contadores principais - estatísticas gerais
            'total_produtos': Item.objects.filter(status='ATIVO', tipo='PRODUTO').count(),
            'total_materiais': Item.objects.filter(status='ATIVO', tipo='MATERIAL').count(),
            'total_fornecedores': Fornecedor.objects.filter(status='ATIVO').count(),
            'total_movimentos': MovimentoItem.objects.filter(data_movimento__gte=data_limite).count(),
            
            # Contadores de notificações
            'total_notificacoes': total_notificacoes,
            'notificacoes_nao_lidas': notificacoes_nao_lidas,
            
            # Dados adicionais para contexto
            'total_receitas': Receita.objects.filter(status='ATIVA').count(),
            'total_categorias': CategoriaProduto.objects.filter(ativa=True).count(),
            'sucursais': sucursais_permitidas,
            'produtos_baixo_estoque': StockItem.objects.select_related('item').filter(
                item__tipo='PRODUTO',
                quantidade_atual__lte=F('item__estoque_minimo')
            ).count(),
            'materiais_baixo_estoque': StockItem.objects.select_related('item').filter(
                item__tipo='MATERIAL',
                quantidade_atual__lte=F('item__estoque_minimo')
            ).count(),
            
            # Métricas de Logística
            'rastreamentos_em_transito': rastreamentos_em_transito,
            'entregas_pendentes': entregas_pendentes,
        }
        return render(request, 'stock/main.html', context)
    except Exception as e:
        logger.error(f"Erro na página principal do stock: {e}")
        messages.error(request, 'Erro ao carregar dados do módulo de stock.')
        return render(request, 'stock/main.html', {'sucursais': []})

# =============================================================================
# GESTÃO DE CATEGORIAS
# =============================================================================

@login_required
def stock_categorias(request):
    """Lista de categorias de produtos com filtros e paginação"""
    try:
        # Parâmetros de busca e filtro
        search_query = request.GET.get('q', '').strip()
        tipo = request.GET.get('tipo')
        status = request.GET.get('status')

        # Query base com otimizações
        categorias = CategoriaProduto.objects.select_related('categoria_pai').all()

        # Aplicar filtros
        if search_query:
            categorias = categorias.filter(
                Q(nome__icontains=search_query) |
                Q(codigo__icontains=search_query) |
                Q(descricao__icontains=search_query)
            )
        
        if tipo:
            categorias = categorias.filter(tipo=tipo)
        
        if status:
            if status == 'ativa':
                categorias = categorias.filter(ativa=True)
            elif status == 'inativa':
                categorias = categorias.filter(ativa=False)

        # Ordenação
        categorias = categorias.order_by('nome')

        # Paginação
        paginator = Paginator(categorias, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        context = {
            'page_obj': page_obj,
            'search_query': search_query,
            'tipo': tipo,
            'status': status,
            'tipos': CategoriaProduto.TIPO_CHOICES,
        }
        return render(request, 'stock/categorias/main.html', context)
    except Exception as e:
        logger.error(f"Erro ao listar categorias: {e}")
        messages.error(request, 'Erro ao carregar lista de categorias.')
        return render(request, 'stock/categorias/main.html', {'page_obj': None})

@login_required
@require_http_methods(["GET", "POST"])
def stock_categoria_add(request):
    """Adicionar nova categoria"""
    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        codigo = request.POST.get('codigo', '').strip()
        tipo = request.POST.get('tipo')
        descricao = request.POST.get('descricao', '').strip()
        categoria_pai_id = request.POST.get('categoria_pai')
        
        # Validação
        if not nome or not codigo or not tipo:
            messages.error(request, 'Nome, código e tipo são obrigatórios.')
            return redirect('stock:categoria_add')
        
        if len(nome) > 100:
            messages.error(request, 'Nome deve ter no máximo 100 caracteres.')
            return redirect('stock:categoria_add')
        
        if len(codigo) > 20:
            messages.error(request, 'Código deve ter no máximo 20 caracteres.')
            return redirect('stock:categoria_add')
        
        try:
            with transaction.atomic():
                categoria_pai = None
                if categoria_pai_id:
                    categoria_pai = CategoriaProduto.objects.get(id=categoria_pai_id)
                
                CategoriaProduto.objects.create(
                    nome=nome,
                    codigo=codigo,
                    tipo=tipo,
                    descricao=descricao,
                    categoria_pai=categoria_pai
                )
                messages.success(request, 'Categoria adicionada com sucesso.')
                return redirect('stock:categorias')
        except ValidationError as e:
            messages.error(request, f'Erro de validação: {str(e)}')
        except Exception as e:
            logger.error(f"Erro ao adicionar categoria: {e}")
            messages.error(request, f'Erro ao adicionar categoria: {str(e)}')
    
    context = {
        'categorias_pai': CategoriaProduto.objects.filter(ativa=True),
        'tipos': CategoriaProduto.TIPO_CHOICES,
    }
    return render(request, 'stock/categorias/form.html', context)

@login_required
@require_http_methods(["GET", "POST"])
def stock_categoria_edit(request, id):
    """Editar categoria"""
    categoria = get_object_or_404(CategoriaProduto, id=id)
    
    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        codigo = request.POST.get('codigo', '').strip()
        tipo = request.POST.get('tipo')
        descricao = request.POST.get('descricao', '').strip()
        categoria_pai_id = request.POST.get('categoria_pai')
        
        # Validação
        if not nome or not codigo or not tipo:
            messages.error(request, 'Nome, código e tipo são obrigatórios.')
            return redirect('stock:categoria_edit', id=id)
        
        if len(nome) > 100:
            messages.error(request, 'Nome deve ter no máximo 100 caracteres.')
            return redirect('stock:categoria_edit', id=id)
        
        if len(codigo) > 20:
            messages.error(request, 'Código deve ter no máximo 20 caracteres.')
            return redirect('stock:categoria_edit', id=id)
        
        try:
            with transaction.atomic():
                categoria.nome = nome
                categoria.codigo = codigo
                categoria.tipo = tipo
                categoria.descricao = descricao
                categoria.categoria_pai = None
                
                if categoria_pai_id:
                    categoria.categoria_pai = CategoriaProduto.objects.get(id=categoria_pai_id)
                
                categoria.save()
                messages.success(request, 'Categoria atualizada com sucesso.')
                return redirect('stock:categorias')
        except ValidationError as e:
            messages.error(request, f'Erro de validação: {str(e)}')
        except Exception as e:
            logger.error(f"Erro ao editar categoria {id}: {e}")
            messages.error(request, f'Erro ao atualizar categoria: {str(e)}')
    
    context = {
        'categoria': categoria,
        'categorias_pai': CategoriaProduto.objects.filter(ativa=True).exclude(id=id),
        'tipos': CategoriaProduto.TIPO_CHOICES,
    }
    return render(request, 'stock/categorias/form.html', context)

@login_required
@require_http_methods(["GET", "POST"])
def stock_categoria_delete(request, id):
    """Excluir categoria"""
    categoria = get_object_or_404(CategoriaProduto, id=id)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Verificar se há produtos/materiais usando esta categoria
                produtos_count = categoria.produtos.count()
                materiais_count = categoria.materiais.count()
                
                if produtos_count > 0 or materiais_count > 0:
                    messages.error(
                        request, 
                        f'Não é possível excluir esta categoria pois ela está sendo usada por {produtos_count} produtos e {materiais_count} materiais.'
                    )
                    return redirect('stock:categorias')
                
                categoria.delete()
                messages.success(request, 'Categoria excluída com sucesso.')
        except Exception as e:
            logger.error(f"Erro ao excluir categoria {id}: {e}")
            messages.error(request, f'Erro ao excluir categoria: {str(e)}')
        return redirect('stock:categorias')
    
    context = {'categoria': categoria}
    return render(request, 'stock/categorias/delete.html', context)

# =============================================================================
# GESTÃO DE FORNECEDORES
# =============================================================================

@login_required
def stock_fornecedores(request):
    """Lista de fornecedores com filtros e paginação"""
    try:
        # Parâmetros de busca e filtro
        search_query = request.GET.get('q', '').strip()
        tipo = request.GET.get('tipo')
        status = request.GET.get('status')

        # Query base com otimizações
        fornecedores = Fornecedor.objects.all()

        # Aplicar filtros
        if search_query:
            fornecedores = fornecedores.filter(
                Q(nome__icontains=search_query) |
                Q(nuit__icontains=search_query) |
                Q(email__icontains=search_query) |
                Q(telefone__icontains=search_query)
            )
        
        if tipo:
            fornecedores = fornecedores.filter(tipo=tipo)
        
        if status:
            fornecedores = fornecedores.filter(status=status)

        # Ordenação
        fornecedores = fornecedores.order_by('nome')

        # Paginação
        paginator = Paginator(fornecedores, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        context = {
            'page_obj': page_obj,
            'search_query': search_query,
            'tipo': tipo,
            'status': status,
            'tipos': Fornecedor.TIPO_CHOICES,
            'status_choices': Fornecedor.STATUS_CHOICES,
        }
        return render(request, 'stock/fornecedores/main.html', context)
    except Exception as e:
        logger.error(f"Erro ao listar fornecedores: {e}")
        messages.error(request, 'Erro ao carregar lista de fornecedores.')
        return render(request, 'stock/fornecedores/main.html', {'page_obj': None})

@login_required
@require_http_methods(["GET", "POST"])
def stock_fornecedor_add(request):
    """Adicionar novo fornecedor"""
    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        tipo = request.POST.get('tipo')
        nuit = request.POST.get('nuit', '').strip()
        email = request.POST.get('email', '').strip()
        telefone = request.POST.get('telefone', '').strip()
        website = request.POST.get('website', '').strip()
        endereco = request.POST.get('endereco', '').strip()
        cidade = request.POST.get('cidade', '').strip()
        provincia = request.POST.get('provincia', '').strip()
        codigo_postal = request.POST.get('codigo_postal', '').strip()
        pais = request.POST.get('pais', 'Moçambique').strip()
        limite_credito = request.POST.get('limite_credito', 0)
        prazo_pagamento = request.POST.get('prazo_pagamento', 0)
        desconto_padrao = request.POST.get('desconto_padrao', 0)
        status = request.POST.get('status', 'ATIVO')
        observacoes = request.POST.get('observacoes', '').strip()
        
        # Validação dos campos obrigatórios
        if not all([nome, tipo, status]):
            messages.error(request, 'Nome, tipo e status são obrigatórios.')
            return redirect('stock:fornecedor_add')
        
        if len(nome) > 200:
            messages.error(request, 'Nome deve ter no máximo 200 caracteres.')
            return redirect('stock:fornecedor_add')
        
        try:
            with transaction.atomic():
                Fornecedor.objects.create(
                    nome=nome,
                    tipo=tipo,
                    nuit=nuit,
                    email=email,
                    telefone=telefone,
                    website=website,
                    endereco=endereco,
                    cidade=cidade,
                    provincia=provincia,
                    codigo_postal=codigo_postal,
                    pais=pais,
                    limite_credito=Decimal(limite_credito) if limite_credito else Decimal('0.00'),
                    prazo_pagamento=int(prazo_pagamento) if prazo_pagamento else 0,
                    desconto_padrao=Decimal(desconto_padrao) if desconto_padrao else Decimal('0.00'),
                    status=status,
                    observacoes=observacoes
                )
                messages.success(request, 'Fornecedor adicionado com sucesso.')
                return redirect('stock:fornecedores')
        except ValidationError as e:
            messages.error(request, f'Erro de validação: {str(e)}')
        except Exception as e:
            logger.error(f"Erro ao adicionar fornecedor: {e}")
            messages.error(request, f'Erro ao adicionar fornecedor: {str(e)}')
    
    context = {
        'tipos': Fornecedor.TIPO_CHOICES,
        'status_choices': Fornecedor.STATUS_CHOICES,
    }
    return render(request, 'stock/fornecedores/form.html', context)

@login_required
@require_http_methods(["GET", "POST"])
def stock_fornecedor_edit(request, id):
    """Editar fornecedor"""
    fornecedor = get_object_or_404(Fornecedor, id=id)
    
    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        tipo = request.POST.get('tipo')
        nuit = request.POST.get('nuit', '').strip()
        email = request.POST.get('email', '').strip()
        telefone = request.POST.get('telefone', '').strip()
        website = request.POST.get('website', '').strip()
        endereco = request.POST.get('endereco', '').strip()
        cidade = request.POST.get('cidade', '').strip()
        provincia = request.POST.get('provincia', '').strip()
        codigo_postal = request.POST.get('codigo_postal', '').strip()
        pais = request.POST.get('pais', 'Moçambique').strip()
        limite_credito = request.POST.get('limite_credito', 0)
        prazo_pagamento = request.POST.get('prazo_pagamento', 0)
        desconto_padrao = request.POST.get('desconto_padrao', 0)
        status = request.POST.get('status', 'ATIVO')
        observacoes = request.POST.get('observacoes', '').strip()
        
        # Validação dos campos obrigatórios
        if not all([nome, tipo, status]):
            messages.error(request, 'Nome, tipo e status são obrigatórios.')
            return redirect('stock:fornecedor_edit', id=id)
        
        if len(nome) > 200:
            messages.error(request, 'Nome deve ter no máximo 200 caracteres.')
            return redirect('stock:fornecedor_edit', id=id)
        
        try:
            with transaction.atomic():
                fornecedor.nome = nome
                fornecedor.tipo = tipo
                fornecedor.nuit = nuit
                fornecedor.email = email
                fornecedor.telefone = telefone
                fornecedor.website = website
                fornecedor.endereco = endereco
                fornecedor.cidade = cidade
                fornecedor.provincia = provincia
                fornecedor.codigo_postal = codigo_postal
                fornecedor.pais = pais
                fornecedor.limite_credito = Decimal(limite_credito) if limite_credito else Decimal('0.00')
                fornecedor.prazo_pagamento = int(prazo_pagamento) if prazo_pagamento else 0
                fornecedor.desconto_padrao = Decimal(desconto_padrao) if desconto_padrao else Decimal('0.00')
                fornecedor.status = status
                fornecedor.observacoes = observacoes
                fornecedor.save()
                messages.success(request, 'Fornecedor atualizado com sucesso.')
                return redirect('stock:fornecedores')
        except ValidationError as e:
            messages.error(request, f'Erro de validação: {str(e)}')
        except Exception as e:
            logger.error(f"Erro ao editar fornecedor {id}: {e}")
            messages.error(request, f'Erro ao atualizar fornecedor: {str(e)}')
    
    context = {
        'fornecedor': fornecedor,
        'tipos': Fornecedor.TIPO_CHOICES,
        'status_choices': Fornecedor.STATUS_CHOICES,
    }
    return render(request, 'stock/fornecedores/form.html', context)

@login_required
def stock_fornecedor_detail(request, id):
    """Detalhes do fornecedor"""
    fornecedor = get_object_or_404(Fornecedor, id=id)
    
    context = {
        'fornecedor': fornecedor,
    }
    return render(request, 'stock/fornecedores/detail.html', context)

@login_required
@require_http_methods(["GET", "POST"])
def stock_fornecedor_delete(request, id):
    """Excluir fornecedor"""
    fornecedor = get_object_or_404(Fornecedor, id=id)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Verificar se há produtos/materiais usando este fornecedor
                produtos_count = fornecedor.produtos_principais.count()
                materiais_count = fornecedor.materiais_principais.count()
                
                if produtos_count > 0 or materiais_count > 0:
                    messages.error(
                        request, 
                        f'Não é possível excluir este fornecedor pois ele está sendo usado por {produtos_count} produtos e {materiais_count} materiais.'
                    )
                    return redirect('stock:fornecedores')
                
                fornecedor.delete()
                messages.success(request, 'Fornecedor excluído com sucesso.')
        except Exception as e:
            logger.error(f"Erro ao excluir fornecedor {id}: {e}")
            messages.error(request, f'Erro ao excluir fornecedor: {str(e)}')
        return redirect('stock:fornecedores')
    
    context = {'fornecedor': fornecedor}
    return render(request, 'stock/fornecedores/delete.html', context)

@login_required
def stock_fornecedor_produtos(request, id):
    """Produtos de um fornecedor"""
    try:
        fornecedor = get_object_or_404(Fornecedor, id=id)
        produtos = FornecedorProduto.objects.filter(
            fornecedor=fornecedor
        ).select_related('item').order_by('item__nome')
        
        context = {
            'fornecedor': fornecedor,
            'produtos': produtos,
        }
        return render(request, 'stock/fornecedores/produtos.html', context)
    except Exception as e:
        logger.error(f"Erro ao listar produtos do fornecedor {id}: {e}")
        messages.error(request, 'Erro ao carregar produtos do fornecedor.')
        return redirect('stock:fornecedores')

@login_required
@require_http_methods(["GET", "POST"])
def stock_fornecedor_associar_produto(request, id):
    """Associar produto a um fornecedor"""
    try:
        fornecedor = get_object_or_404(Fornecedor, id=id)
        
        if request.method == 'POST':
            produto_id = request.POST.get('produto')
            material_id = request.POST.get('material')
            preco_fornecedor = request.POST.get('preco_fornecedor')
            prazo_entrega = request.POST.get('prazo_entrega')
            
            if (produto_id or material_id) and preco_fornecedor and prazo_entrega:
                if produto_id:
                    item = get_object_or_404(Item, id=produto_id, tipo='PRODUTO')
                    item_tipo = 'produto'
                else:
                    item = get_object_or_404(Item, id=material_id, tipo='MATERIAL')
                    item_tipo = 'material'
                
                # Verificar se já existe associação
                if item_tipo == 'produto':
                    if FornecedorProduto.objects.filter(fornecedor=fornecedor, produto=item).exists():
                        messages.warning(request, f'O produto {item.nome} já está associado a este fornecedor.')
                        return redirect('stock:fornecedor_produtos', id=id)
                else:
                    if FornecedorProduto.objects.filter(fornecedor=fornecedor, material=item).exists():
                        messages.warning(request, f'O material {item.nome} já está associado a este fornecedor.')
                        return redirect('stock:fornecedor_produtos', id=id)
                
                # Criar associação
                if item_tipo == 'produto':
                    FornecedorProduto.objects.create(
                        fornecedor=fornecedor,
                        produto=item,
                        preco_fornecedor=preco_fornecedor,
                        prazo_entrega=prazo_entrega,
                        ativo=True
                    )
                else:
                    FornecedorProduto.objects.create(
                        fornecedor=fornecedor,
                        material=item,
                        preco_fornecedor=preco_fornecedor,
                        prazo_entrega=prazo_entrega,
                        ativo=True
                    )
                
                messages.success(request, f'{item_tipo.title()} {item.nome} associado com sucesso!')
                return redirect('stock:fornecedor_produtos', id=id)
            else:
                messages.error(request, 'Todos os campos são obrigatórios.')
        
        # Buscar produtos e materiais não associados a este fornecedor
        produtos_associados = FornecedorProduto.objects.filter(fornecedor=fornecedor, produto__isnull=False).values_list('produto_id', flat=True)
        materiais_associados = FornecedorProduto.objects.filter(fornecedor=fornecedor, material__isnull=False).values_list('material_id', flat=True)
        
        produtos_disponiveis = Item.objects.filter(tipo='PRODUTO').exclude(id__in=produtos_associados).order_by('nome')
        materiais_disponiveis = Item.objects.filter(tipo='MATERIAL').exclude(id__in=materiais_associados).order_by('nome')
        
        context = {
            'fornecedor': fornecedor,
            'produtos_disponiveis': produtos_disponiveis,
            'materiais_disponiveis': materiais_disponiveis,
        }
        return render(request, 'stock/fornecedores/associar_produto.html', context)
    except Exception as e:
        logger.error(f"Erro ao associar produto ao fornecedor {id}: {e}")
        messages.error(request, 'Erro ao associar produto ao fornecedor.')
        return redirect('stock:fornecedores')

@login_required
@require_http_methods(["GET", "POST"])
def stock_fornecedor_editar_associacao(request, id, associacao_id):
    """Editar associação de produto/material com fornecedor"""
    try:
        fornecedor = get_object_or_404(Fornecedor, id=id)
        associacao = get_object_or_404(FornecedorProduto, id=associacao_id, fornecedor=fornecedor)
        
        if request.method == 'POST':
            preco_fornecedor = request.POST.get('preco_fornecedor')
            prazo_entrega = request.POST.get('prazo_entrega')
            ativo = request.POST.get('ativo') == 'on'
            
            if preco_fornecedor and prazo_entrega:
                associacao.preco_fornecedor = preco_fornecedor
                associacao.prazo_entrega = prazo_entrega
                associacao.ativo = ativo
                associacao.save()
                
                messages.success(request, f'{associacao.tipo_item} {associacao.item.nome} atualizado com sucesso!')
                return redirect('stock:fornecedor_produtos', id=id)
            else:
                messages.error(request, 'Todos os campos são obrigatórios.')
        
        context = {
            'fornecedor': fornecedor,
            'associacao': associacao,
        }
        return render(request, 'stock/fornecedores/editar_associacao.html', context)
    except Exception as e:
        logger.error(f"Erro ao editar associação {associacao_id} do fornecedor {id}: {e}")
        messages.error(request, 'Erro ao editar associação.')
        return redirect('stock:fornecedores')

@login_required
@require_http_methods(["POST"])
def stock_fornecedor_remover_associacao(request, id, associacao_id):
    """Remover associação de produto/material com fornecedor"""
    try:
        fornecedor = get_object_or_404(Fornecedor, id=id)
        associacao = get_object_or_404(FornecedorProduto, id=associacao_id, fornecedor=fornecedor)
        
        item_nome = associacao.item.nome
        item_tipo = associacao.tipo_item
        associacao.delete()
        
        messages.success(request, f'{item_tipo} {item_nome} removido com sucesso!')
        return redirect('stock:fornecedor_produtos', id=id)
    except Exception as e:
        logger.error(f"Erro ao remover associação {associacao_id} do fornecedor {id}: {e}")
        messages.error(request, 'Erro ao remover associação.')
        return redirect('stock:fornecedores')

# =============================================================================
# GESTÃO DE PRODUTOS
# =============================================================================

@login_required
def stock_produtos(request):
    """Lista de produtos com filtros e paginação"""
    try:
        # Parâmetros de busca e filtro
        search_query = request.GET.get('q', '').strip()
        categoria_id = request.GET.get('categoria')
        status = request.GET.get('status')
        tipo = request.GET.get('tipo')

        # Query base com otimizações - usando modelo unificado Item
        produtos = Item.objects.filter(tipo='PRODUTO').select_related('categoria')

        # Aplicar filtros
        if search_query:
            produtos = produtos.filter(
                Q(nome__icontains=search_query) |
                Q(codigo__icontains=search_query) |
                Q(codigo_barras__icontains=search_query) |
                Q(descricao__icontains=search_query)
            )
        
        if categoria_id:
            produtos = produtos.filter(categoria_id=categoria_id)
        
        if status:
            produtos = produtos.filter(status=status)
        
        if tipo:
            produtos = produtos.filter(tipo=tipo)

        # Ordenação
        produtos = produtos.order_by('nome')

        # Paginação
        paginator = Paginator(produtos, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Adicionar informações de stock para cada produto
        from .models_stock import StockItem
        for produto in page_obj:
            # Buscar stock total de todas as sucursais para este produto
            stocks = StockItem.objects.filter(item=produto)
            produto.quantidade_atual = sum(float(stock.quantidade_atual) for stock in stocks)
        
        # Dados para charts usando helper function
        chart_data = get_chart_data_for_entity(Item)
        
        context = {
            'page_obj': page_obj,
            'search_query': search_query,
            'categoria_id': categoria_id,
            'status': status,
            'tipo': tipo,
            'categorias': CategoriaProduto.objects.filter(ativa=True).filter(
                Q(tipo='PRODUTO') | Q(tipo='AMBOS') | Q(tipo='TODOS')
            ),
            'status_choices': Item.STATUS_CHOICES,
            'tipos': Item.TIPO_CHOICES,
            # Dados para charts usando helper function
            'produtos_ativos': chart_data['ativos'],
            'produtos_inativos': chart_data['inativos'],
            'produtos_pendentes': chart_data['pendentes'],
            'produtos_estoque_baixo': chart_data['estoque_baixo'],
            'categorias_count': chart_data['categorias_count'],
            'categorias_labels': chart_data['categorias_labels'],
            'categorias_data': chart_data['categorias_data'],
        }
        return render(request, 'stock/produtos/main.html', context)
    except Exception as e:
        logger.error(f"Erro ao listar produtos: {e}")
        messages.error(request, 'Erro ao carregar lista de produtos.')
        return render(request, 'stock/produtos/main.html', {'page_obj': None})

@login_required
@require_http_methods(["GET", "POST"])
def stock_produto_add(request):
    """Adicionar novo produto"""
    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        codigo = request.POST.get('codigo', '').strip()
        codigo_barras = request.POST.get('codigo_barras', '').strip()
        descricao = request.POST.get('descricao', '').strip()
        categoria_id = request.POST.get('categoria')
        unidade_medida = request.POST.get('unidade_medida')
        preco_custo = request.POST.get('preco_custo')
        preco_venda = request.POST.get('preco_venda')
        estoque_minimo = request.POST.get('estoque_minimo', 0)
        estoque_maximo = request.POST.get('estoque_maximo', 0)
        fornecedor_principal_id = request.POST.get('fornecedor_principal')
        observacoes = request.POST.get('observacoes', '').strip()
        
        # Validação
        if not all([nome, categoria_id, unidade_medida, preco_custo, preco_venda]):
            messages.error(request, 'Todos os campos obrigatórios devem ser preenchidos.')
            return redirect('stock:produto_add')
        
        if len(nome) > 200:
            messages.error(request, 'Nome deve ter no máximo 200 caracteres.')
            return redirect('stock:produto_add')
        
        try:
            with transaction.atomic():
                fornecedor_principal = None
                if fornecedor_principal_id:
                    fornecedor_principal = Fornecedor.objects.get(id=fornecedor_principal_id)
                
                Item.objects.create(
                    nome=nome,
                    codigo=codigo if codigo else '',  # Permite código vazio para geração automática
                    codigo_barras=codigo_barras,
                    descricao=descricao,
                    categoria_id=categoria_id,
                    unidade_medida=unidade_medida,
                    preco_custo=Decimal(preco_custo),
                    preco_venda=Decimal(preco_venda),
                    estoque_minimo=int(estoque_minimo),
                    estoque_maximo=int(estoque_maximo),
                    fornecedor_principal=fornecedor_principal,
                    observacoes=observacoes
                )
                messages.success(request, 'Produto adicionado com sucesso.')
                return redirect('stock:produtos')
        except ValidationError as e:
            messages.error(request, f'Erro de validação: {str(e)}')
        except Exception as e:
            logger.error(f"Erro ao adicionar produto: {e}")
            messages.error(request, f'Erro ao adicionar produto: {str(e)}')
    
    context = {
        'categorias': CategoriaProduto.objects.filter(ativa=True).filter(
            Q(tipo='PRODUTO') | Q(tipo='AMBOS') | Q(tipo='TODOS')
        ),
        'fornecedores': Fornecedor.objects.filter(status='ATIVO'),
        'tipos': Item.TIPO_CHOICES,
        'unidades': Item.UNIDADE_CHOICES,
        'status_choices': Item.STATUS_CHOICES,
    }
    return render(request, 'stock/produtos/form.html', context)

@login_required
@require_http_methods(["GET", "POST"])
def stock_produto_edit(request, id):
    """Editar produto"""
    from .models_stock import Item
    produto = get_object_or_404(Item, id=id, tipo='PRODUTO')
    
    if request.method == 'POST':
        # Obter dados do formulário
        nome = request.POST.get('nome', '').strip()
        codigo = request.POST.get('codigo', '').strip()
        descricao = request.POST.get('descricao', '').strip()
        categoria_id = request.POST.get('categoria')
        tipo = request.POST.get('tipo')
        unidade_medida = request.POST.get('unidade_medida')
        preco_custo = request.POST.get('preco_custo', '').strip()
        estoque_minimo = request.POST.get('estoque_minimo', 0)
        estoque_maximo = request.POST.get('estoque_maximo', 0)
        observacoes = request.POST.get('observacoes', '').strip()
        
        # Validação simples
        erros = []
        if not nome: erros.append('Nome é obrigatório')
        if not codigo: erros.append('Código é obrigatório')
        if not categoria_id: erros.append('Categoria é obrigatória')
        if not tipo: erros.append('Tipo é obrigatório')
        if not unidade_medida: erros.append('Unidade de medida é obrigatória')
        if not preco_custo: erros.append('Preço de custo é obrigatório')
        
        # Converter vírgula para ponto
        if preco_custo and ',' in preco_custo:
            preco_custo = preco_custo.replace(',', '.')
        
        # Validar preço
        try:
            preco_decimal = Decimal(preco_custo)
            if preco_decimal <= 0:
                erros.append('Preço deve ser maior que zero')
        except (ValueError, TypeError):
            erros.append('Preço inválido')
        
        if erros:
            for erro in erros:
                messages.error(request, erro)
            return redirect('stock:produto_edit', id=id)
        
        # Salvar dados
        try:
            with transaction.atomic():
                produto.nome = nome
                produto.codigo = codigo
                produto.descricao = descricao
                produto.categoria_id = categoria_id
                produto.tipo = tipo
                produto.unidade_medida = unidade_medida
                produto.preco_custo = preco_decimal
                produto.estoque_minimo = int(estoque_minimo)
                produto.estoque_maximo = int(estoque_maximo)
                produto.status = request.POST.get('status', 'ATIVO')
                produto.observacoes = observacoes
                produto.save()
                
                messages.success(request, 'Produto atualizado com sucesso!')
                return redirect('stock:produtos')
                
        except Exception as e:
            messages.error(request, f'Erro ao salvar: {str(e)}')
            return redirect('stock:produto_edit', id=id)
    
    # GET - Mostrar formulário
    context = {
        'produto': produto,
        'categorias': CategoriaProduto.objects.all(),
        'tipos': Item.TIPO_CHOICES,
        'status_choices': Item.STATUS_CHOICES,
        'unidades': Item.UNIDADE_CHOICES,
    }
    return render(request, 'stock/produtos/form.html', context)

@login_required
@require_http_methods(["GET", "POST"])
def stock_produto_delete(request, id):
    """Excluir produto"""
    produto = get_object_or_404(Item, id=id, tipo='PRODUTO')
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Verificar se há movimentos de stock para este produto
                movimentos_count = produto.movimentos.count()
                stocks_count = produto.stocks_sucursais.count()
                
                if movimentos_count > 0 or stocks_count > 0:
                    messages.error(
                        request, 
                        f'Não é possível excluir este produto pois ele possui {movimentos_count} movimentações e {stocks_count} registros de stock.'
                    )
                    return redirect('stock:produtos')
                
                produto.delete()
                messages.success(request, 'Produto excluído com sucesso.')
        except Exception as e:
            logger.error(f"Erro ao excluir produto {id}: {e}")
            messages.error(request, f'Erro ao excluir produto: {str(e)}')
        return redirect('stock:produtos')
    
    context = {'produto': produto}
    return render(request, 'stock/produtos/delete.html', context)

@login_required
def stock_produto_detail(request, id):
    """Detalhes do produto"""
    try:
        produto = get_object_or_404(Item, id=id, tipo='PRODUTO')
        stocks_sucursais = StockItem.objects.filter(
            item=produto
        ).select_related('sucursal').order_by('sucursal__nome')
        movimentos_recentes = MovimentoStock.objects.filter(
            produto=produto
        ).select_related('tipo_movimento', 'sucursal').order_by('-data_movimento')[:10]
        
        context = {
            'produto': produto,
            'stocks_sucursais': stocks_sucursais,
            'movimentos_recentes': movimentos_recentes,
        }
        return render(request, 'stock/produtos/detail.html', context)
    except Exception as e:
        logger.error(f"Erro ao exibir detalhes do produto {id}: {e}")
        messages.error(request, 'Erro ao carregar detalhes do produto.')
        return redirect('stock:produtos')

@login_required
@require_stock_access
def stock_por_sucursal(request):
    """Stock por sucursal"""
    try:
        # Usuários podem ver todas as sucursais
        sucursais_permitidas = get_user_sucursais(request, for_modification=False)
        sucursais_ids = [s.id for s in sucursais_permitidas]
        
        sucursais = sucursais_permitidas
        produtos = Item.objects.filter(status='ATIVO', tipo='PRODUTO').order_by('nome')
        
        # Filtrar por sucursal se especificada
        sucursal_id = request.GET.get('sucursal')
        produto_id = request.GET.get('produto')
        
        # Filtrar stocks apenas das sucursais permitidas com otimização
        stocks = StockItem.objects.select_related('item', 'sucursal').filter(
            sucursal_id__in=sucursais_ids
        ).prefetch_related('item__categoria')
        
        if sucursal_id and int(sucursal_id) in sucursais_ids:
            stocks = stocks.filter(sucursal_id=sucursal_id)
        if produto_id:
            stocks = stocks.filter(produto_id=produto_id)
        
        stocks = stocks.order_by('sucursal__nome', 'produto__nome')
        
        context = {
            'stocks': stocks,
            'sucursais': sucursais,
            'produtos': produtos,
            'sucursal_selecionada': int(sucursal_id) if sucursal_id else None,
            'produto_selecionado': int(produto_id) if produto_id else None,
        }
        return render(request, 'stock/stock/por_sucursal.html', context)
    except Exception as e:
        logger.error(f"Erro ao listar stock por sucursal: {e}")
        messages.error(request, 'Erro ao carregar stock por sucursal.')
        return render(request, 'stock/stock/por_sucursal.html', {'stocks': [], 'sucursais': []})

@login_required
def stock_sucursal_detail(request, sucursal_id):
    """Detalhes do stock de uma sucursal"""
    try:
        sucursal = get_object_or_404(Sucursal, id=sucursal_id)
        stocks = StockItem.objects.filter(
            sucursal=sucursal
        ).select_related('item').prefetch_related('item__categoria').order_by('item__nome')
        
        # Filtros
        search = request.GET.get('search', '').strip()
        status_estoque = request.GET.get('status_estoque')
        
        if search:
            stocks = stocks.filter(
                Q(produto__nome__icontains=search) | 
                Q(produto__codigo__icontains=search)
            )
        
        if status_estoque:
            if status_estoque == 'BAIXO':
                stocks = stocks.filter(quantidade_atual__lte=F('produto__estoque_minimo'))
            elif status_estoque == 'ALTO':
                stocks = stocks.filter(quantidade_atual__gte=F('produto__estoque_maximo'))
            elif status_estoque == 'NORMAL':
                stocks = stocks.filter(
                    quantidade_atual__gt=F('produto__estoque_minimo'),
                    quantidade_atual__lt=F('produto__estoque_maximo')
                )
        
        paginator = Paginator(stocks, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        context = {
            'sucursal': sucursal,
            'page_obj': page_obj,
            'search': search,
            'status_estoque': status_estoque,
        }
        return render(request, 'stock/stock/sucursal_detail.html', context)
    except Exception as e:
        logger.error(f"Erro ao exibir detalhes do stock da sucursal {sucursal_id}: {e}")
        messages.error(request, 'Erro ao carregar detalhes do stock da sucursal.')
        return redirect('stock:stock_por_sucursal')

@login_required
def stock_produto_sucursal(request, sucursal_id, produto_id):
    """Detalhes do stock de um produto em uma sucursal"""
    try:
        sucursal = get_object_or_404(Sucursal, id=sucursal_id)
        produto = get_object_or_404(Item, id=produto_id, tipo='PRODUTO')
        stock, created = StockItem.objects.get_or_create(
            item=produto,
            sucursal=sucursal,
            defaults={'quantidade_atual': 0, 'quantidade_reservada': 0}
        )
        
        movimentos = MovimentoStock.objects.filter(
            produto=produto,
            sucursal=sucursal
        ).select_related('tipo_movimento').order_by('-data_movimento')[:20]
        
        context = {
            'sucursal': sucursal,
            'produto': produto,
            'stock': stock,
            'movimentos': movimentos,
        }
        return render(request, 'stock/stock/produto_sucursal.html', context)
    except Exception as e:
        logger.error(f"Erro ao exibir stock do produto {produto_id} na sucursal {sucursal_id}: {e}")
        messages.error(request, 'Erro ao carregar detalhes do stock.')
        return redirect('stock:stock_por_sucursal')

# =============================================================================
# APIs E ENDPOINTS
# =============================================================================

@login_required
def api_produtos_search(request):
    """API para busca de produtos"""
    try:
        query = request.GET.get('q', '').strip()
        if len(query) < 2:
            return JsonResponse({'results': []})
        
        produtos = Item.objects.filter(tipo='PRODUTO').filter(
            Q(nome__icontains=query) | 
            Q(codigo__icontains=query) |
            Q(codigo_barras__icontains=query)
        ).select_related('categoria')[:10]
        
        results = []
        for produto in produtos:
            results.append({
                'id': produto.id,
                'text': f"{produto.codigo} - {produto.nome}",
                'codigo': produto.codigo,
                'nome': produto.nome,
                'preco_venda': float(produto.preco_venda),
                'unidade_medida': produto.unidade_medida,
                'categoria': produto.categoria.nome if produto.categoria else '',
            })
        
        return JsonResponse({'results': results}, cls=DjangoJSONEncoder)
    except Exception as e:
        logger.error(f"Erro na API de busca de produtos: {e}")
        return JsonResponse({'error': 'Erro interno do servidor'}, status=500)

@login_required
def api_fornecedores_search(request):
    """API para busca de fornecedores"""
    try:
        query = request.GET.get('q', '').strip()
        if len(query) < 2:
            return JsonResponse({'results': []})
        
        fornecedores = Fornecedor.objects.filter(
            Q(nome__icontains=query) | 
            Q(nuit__icontains=query)
        ).filter(status='ATIVO')[:10]
        
        results = []
        for fornecedor in fornecedores:
            results.append({
                'id': fornecedor.id,
                'text': f"{fornecedor.nome} ({fornecedor.nuit})",
                'nome': fornecedor.nome,
                'nuit': fornecedor.nuit,
                'tipo': fornecedor.get_tipo_display(),
            })
        
        return JsonResponse({'results': results}, cls=DjangoJSONEncoder)
    except Exception as e:
        logger.error(f"Erro na API de busca de fornecedores: {e}")
        return JsonResponse({'error': 'Erro interno do servidor'}, status=500)

# Dashboard Executivo
@login_required
def stock_dashboard(request):
    """Dashboard executivo com métricas importantes"""
    from .models_stock import (
        RequisicaoCompraExterna, RequisicaoStock, MovimentoItem, 
        StockItem, Item, Sucursal
    )
    from django.db.models import Count, Sum, Q, F
    from datetime import datetime, timedelta
    from django.utils import timezone
    
    # Período de análise (últimos 30 dias)
    hoje = timezone.now()
    ultimos_30_dias = hoje - timedelta(days=30)
    
    # Métricas de Requisições
    total_requisicoes = RequisicaoStock.objects.count() + RequisicaoCompraExterna.objects.count()
    requisicoes_pendentes = (
        RequisicaoStock.objects.filter(status='PENDENTE').count() + 
        RequisicaoCompraExterna.objects.filter(status='PENDENTE').count()
    )
    requisicoes_aprovadas = (
        RequisicaoStock.objects.filter(status='APROVADA').count() + 
        RequisicaoCompraExterna.objects.filter(status='APROVADA').count()
    )
    requisicoes_finalizadas = (
        RequisicaoStock.objects.filter(status='ATENDIDA').count() + 
        RequisicaoCompraExterna.objects.filter(status='FINALIZADA').count()
    )
    
    # Métricas de Movimentações
    total_movimentacoes = MovimentoItem.objects.count()
    movimentacoes_entrada = MovimentoItem.objects.filter(
        tipo_movimento__nome__icontains='entrada'
    ).count()
    movimentacoes_saida = MovimentoItem.objects.filter(
        tipo_movimento__nome__icontains='saída'
    ).count()
    
    # Valor total em movimentações (últimos 30 dias)
    valor_movimentacoes = MovimentoItem.objects.filter(
        data_movimento__gte=ultimos_30_dias
    ).aggregate(total=Sum('valor_total'))['total'] or 0
    
    # Itens com stock baixo
    itens_stock_baixo = StockItem.objects.filter(
        quantidade_atual__lte=F('item__estoque_minimo')
    ).count()
    
    # Requisições por sucursal
    requisicoes_por_sucursal = []
    for sucursal in Sucursal.objects.all():
        count_internas = RequisicaoStock.objects.filter(sucursal_origem=sucursal).count()
        count_externas = RequisicaoCompraExterna.objects.filter(sucursal_solicitante=sucursal).count()
        if count_internas > 0 or count_externas > 0:
            requisicoes_por_sucursal.append({
                'sucursal': sucursal.nome,
                'total': count_internas + count_externas,
                'internas': count_internas,
                'externas': count_externas
            })
    
    # Movimentações recentes (últimas 10)
    movimentacoes_recentes = MovimentoItem.objects.select_related(
        'item', 'sucursal', 'tipo_movimento', 'usuario'
    ).order_by('-data_movimento')[:10]
    
    # Alertas importantes
    alertas = []
    
    # Stock baixo crítico
    if itens_stock_baixo > 0:
        alertas.append({
            'tipo': 'warning',
            'titulo': 'Stock Baixo',
            'mensagem': f'{itens_stock_baixo} item(s) com stock abaixo do mínimo',
            'url': '/stock/requisicoes/verificar-stock-baixo/',
            'icone': 'fas fa-exclamation-triangle'
        })
    
    # Requisições pendentes há muito tempo
    requisicoes_antigas = (
        RequisicaoStock.objects.filter(
            status='PENDENTE',
            data_criacao__lt=hoje - timedelta(days=7)
        ).count() +
        RequisicaoCompraExterna.objects.filter(
            status='PENDENTE',
            data_criacao__lt=hoje - timedelta(days=7)
        ).count()
    )
    
    if requisicoes_antigas > 0:
        alertas.append({
            'tipo': 'danger',
            'titulo': 'Requisições Antigas',
            'mensagem': f'{requisicoes_antigas} requisição(ões) pendentes há mais de 7 dias',
            'url': '/stock/requisicoes/',
            'icone': 'fas fa-clock'
        })
    
    # Movimentações sem usuário
    movimentacoes_sem_usuario = MovimentoItem.objects.filter(usuario__isnull=True).count()
    if movimentacoes_sem_usuario > 0:
        alertas.append({
            'tipo': 'info',
            'titulo': 'Auditoria',
            'mensagem': f'{movimentacoes_sem_usuario} movimentação(ões) sem usuário registrado',
            'url': '/stock/movimentos/',
            'icone': 'fas fa-user-slash'
        })
    
    context = {
        'total_requisicoes': total_requisicoes,
        'requisicoes_pendentes': requisicoes_pendentes,
        'requisicoes_aprovadas': requisicoes_aprovadas,
        'requisicoes_finalizadas': requisicoes_finalizadas,
        'total_movimentacoes': total_movimentacoes,
        'movimentacoes_entrada': movimentacoes_entrada,
        'movimentacoes_saida': movimentacoes_saida,
        'valor_movimentacoes': valor_movimentacoes,
        'itens_stock_baixo': itens_stock_baixo,
        'requisicoes_por_sucursal': requisicoes_por_sucursal,
        'movimentacoes_recentes': movimentacoes_recentes,
        'alertas': alertas,
        'periodo_analise': 'Últimos 30 dias'
    }
    
    return render(request, 'stock/dashboard.html', context)

# Placeholder views para funcionalidades futuras
@login_required
def stock_movimentos(request):
    """Lista de movimentações de stock (SISTEMA UNIFICADO)"""
    from .models_stock import MovimentoItem, TipoMovimentoStock, Sucursal
    from django.db.models import Count, Sum, Q, F
    from django.core.paginator import Paginator
    from datetime import datetime
    
    # Obter parâmetros de filtro
    search_query = request.GET.get('search', '').strip()
    tipo = request.GET.get('tipo', '').strip()
    sucursal_id = request.GET.get('sucursal', '').strip()
    data_inicio = request.GET.get('data_inicio', '').strip()
    data_fim = request.GET.get('data_fim', '').strip()
    tipo_item = request.GET.get('tipo_item', '').strip()  # 'produto', 'material', ou ''
    
    # Buscar movimentações do sistema unificado
    movimentos = MovimentoItem.objects.select_related(
        'item', 'sucursal', 'tipo_movimento', 'usuario'
    ).order_by('-data_movimento')
    
    # Aplicar filtros
    if search_query:
        movimentos = movimentos.filter(
            Q(item__nome__icontains=search_query) |
            Q(item__codigo__icontains=search_query) |
            Q(observacoes__icontains=search_query) |
            Q(referencia__icontains=search_query)
        )
    
    if tipo:
        movimentos = movimentos.filter(tipo_movimento__nome__icontains=tipo)
    
    if sucursal_id:
        movimentos = movimentos.filter(sucursal_id=sucursal_id)
    
    if data_inicio:
        try:
            data_inicio_obj = datetime.strptime(data_inicio, '%Y-%m-%d').date()
            movimentos = movimentos.filter(data_movimento__date__gte=data_inicio_obj)
        except ValueError:
            pass
    
    if data_fim:
        try:
            data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d').date()
            movimentos = movimentos.filter(data_movimento__date__lte=data_fim_obj)
        except ValueError:
            pass
    
    if tipo_item:
        movimentos = movimentos.filter(item__tipo__iexact=tipo_item)
    
    # Adicionar informações extras para compatibilidade com template
    for movimento in movimentos:
        movimento.item_tipo = movimento.item.tipo.lower()  # 'produto' ou 'material'
        movimento.item_nome = movimento.item.nome
        movimento.item_codigo = movimento.item.codigo
        movimento.item_especifico = movimento.item.get_tipo_especifico_display()
    
    all_movements = list(movimentos)
    
    # Estatísticas (baseadas nos filtros aplicados)
    total_movimentos = len(all_movements)
    movimentos_entrada = len([m for m in all_movements if 'entrada' in m.tipo_movimento.nome.lower()])
    movimentos_saida = len([m for m in all_movements if 'saída' in m.tipo_movimento.nome.lower()])
    movimentos_ajuste = len([m for m in all_movements if 'ajuste' in m.tipo_movimento.nome.lower()])
    
    # Valor total movimentado
    valor_total = sum(m.valor_total for m in all_movements)
    
    # Paginação manual
    page_number = int(request.GET.get('page', 1))
    items_per_page = 20
    start_index = (page_number - 1) * items_per_page
    end_index = start_index + items_per_page
    
    page_movements = all_movements[start_index:end_index]
    
    # Criar objeto de paginação manual
    class ManualPage:
        def __init__(self, objects, page_number, items_per_page, total_count):
            self.object_list = objects
            self.number = page_number
            self.paginator = ManualPaginator(total_count, items_per_page)
        
        def __iter__(self):
            return iter(self.object_list)
        
        def has_other_pages(self):
            return self.paginator.num_pages > 1
        
        def has_previous(self):
            return self.number > 1
        
        def has_next(self):
            return self.number < self.paginator.num_pages
        
        @property
        def previous_page_number(self):
            return self.number - 1 if self.has_previous() else None
        
        @property
        def next_page_number(self):
            return self.number + 1 if self.has_next() else None
    
    class ManualPaginator:
        def __init__(self, total_count, items_per_page):
            self.count = total_count
            self.per_page = items_per_page
            self.num_pages = (total_count + items_per_page - 1) // items_per_page
    
    page_obj = ManualPage(page_movements, page_number, items_per_page, total_movimentos)
    
    # Obter sucursais para o filtro
    sucursais = Sucursal.objects.all().order_by('nome')
    
    context = {
        'movimentos': page_obj,
        'total_movimentos': total_movimentos,
        'movimentos_entrada': movimentos_entrada,
        'movimentos_saida': movimentos_saida,
        'movimentos_ajuste': movimentos_ajuste,
        'valor_total': valor_total,
        'sucursais': sucursais,
        'search_query': search_query,
        'tipo': tipo,
        'sucursal_id': sucursal_id,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'tipo_item': tipo_item,
    }
    
    return render(request, 'stock/movimentos/main.html', context)

@login_required
@require_stock_access
@require_sucursal_access
@require_http_methods(["GET", "POST"])
def stock_movimento_add(request):
    """Adicionar movimentação de stock unificada"""
    from .models_stock import MovimentoItem, Item, TipoMovimentoStock, Sucursal, StockItem
    from django.db import transaction
    from django.contrib import messages
    from decimal import Decimal
    from django.core.exceptions import ValidationError
    import logging
    
    logger = logging.getLogger(__name__)
    
    # Para movimentações, apenas sucursais que o usuário pode modificar
    sucursais_permitidas = get_user_sucursais(request, for_modification=True)
    sucursais_ids = [s.id for s in sucursais_permitidas]
    
    if request.method == 'POST':
        tipo_item = request.POST.get('tipo_item')
        produto_id = request.POST.get('produto')
        material_id = request.POST.get('material')
        sucursal_id = request.POST.get('sucursal')
        tipo_movimento_id = request.POST.get('tipo_movimento')
        quantidade = request.POST.get('quantidade')
        preco_unitario = request.POST.get('preco_unitario')
        referencia = request.POST.get('referencia', '').strip()
        observacoes = request.POST.get('observacoes', '').strip()
        
        # Validação dos campos obrigatórios
        if not all([tipo_item, sucursal_id, tipo_movimento_id, quantidade, preco_unitario]):
            messages.error(request, 'Todos os campos obrigatórios devem ser preenchidos.')
            return redirect('stock:movimento_add')
        
        # Validar se produto ou material foi selecionado
        if tipo_item == 'produto' and not produto_id:
            messages.error(request, 'Selecione um produto.')
            return redirect('stock:movimento_add')
        elif tipo_item == 'material' and not material_id:
            messages.error(request, 'Selecione um material.')
            return redirect('stock:movimento_add')
        
        # Verificar se a sucursal está nas permitidas
        if int(sucursal_id) not in sucursais_ids:
            messages.error(request, 'Você não tem permissão para registrar movimentações nesta sucursal.')
            return redirect('stock:movimento_add')
        
        try:
            with transaction.atomic():
                sucursal = Sucursal.objects.get(id=sucursal_id)
                tipo_movimento = TipoMovimentoStock.objects.get(id=tipo_movimento_id)
                
                if tipo_item == 'produto':
                    produto = Item.objects.get(id=produto_id, tipo='PRODUTO')
                    
                    # Verificar se há estoque suficiente para saída
                    if not tipo_movimento.aumenta_estoque:
                        estoque_atual = StockItem.objects.filter(
                            item=produto, 
                            sucursal=sucursal
                        ).first()
                        
                        if not estoque_atual or estoque_atual.quantidade_atual < int(quantidade):
                            messages.error(request, f'Estoque insuficiente. Disponível: {estoque_atual.quantidade_atual if estoque_atual else 0} unidades.')
                            return redirect('stock:movimento_add')
                    
                    # Criar movimento de produto
                    movimento = MovimentoStock(
                        produto=produto,
                        sucursal=sucursal,
                        tipo_movimento=tipo_movimento,
                        quantidade=int(quantidade),
                        preco_unitario=Decimal(preco_unitario),
                        referencia=referencia,
                        observacoes=observacoes,
                        usuario=request.user
                    )
                    movimento.save()
                    
                    # Movimento registrado com sucesso
                    
                else:  # material
                    material = Item.objects.get(id=material_id, tipo='MATERIAL')
                    
                    # Criar movimento de material
                    movimento = MovimentoItem(
                        material=material,
                        sucursal=sucursal,
                        tipo_movimento=tipo_movimento,
                        quantidade=int(quantidade),
                        preco_unitario=Decimal(preco_unitario),
                        referencia=referencia,
                        observacoes=observacoes,
                        usuario=request.user
                    )
                    movimento.save()
                    
                    # Movimento registrado com sucesso
                
                return redirect('stock:movimentos')
                
        except ValidationError as e:
            messages.error(request, f'Erro de validação: {str(e)}')
        except Exception as e:
            logger.error(f"Erro ao registrar movimentação: {e}")
            messages.error(request, f'Erro ao registrar movimentação: {str(e)}')
    
    context = {
        'produtos': Item.objects.filter(status='ATIVO', tipo='PRODUTO').order_by('nome'),
        'materiais': Item.objects.filter(status='ATIVO', tipo='MATERIAL').order_by('nome'),
        'sucursais': sucursais_permitidas,
        'tipos_movimento': TipoMovimentoStock.objects.filter(ativo=True).order_by('nome'),
    }
    return render(request, 'stock/movimentos/form.html', context)


@login_required
@require_stock_access
@require_sucursal_access
@require_http_methods(["GET", "POST"])
def stock_movimento_add_unified(request):
    """Adicionar movimentação de stock unificada (NOVA VERSÃO)"""
    sucursais_permitidas = get_user_sucursais(request, for_modification=True)
    sucursais_ids = [s.id for s in sucursais_permitidas]
    
    if request.method == 'POST':
        # Obter dados do formulário
        item_id = request.POST.get('item_id')
        sucursal_id = request.POST.get('sucursal')
        tipo_movimento_id = request.POST.get('tipo_movimento')
        quantidade = request.POST.get('quantidade')
        preco_unitario = request.POST.get('preco_unitario')
        referencia = request.POST.get('referencia', '').strip()
        observacoes = request.POST.get('observacoes', '').strip()
        
        # Validações básicas
        if not all([item_id, sucursal_id, tipo_movimento_id, quantidade, preco_unitario]):
            messages.error(request, 'Todos os campos obrigatórios devem ser preenchidos.')
            return redirect('stock:movimento_add_unified')
        
        # Verificar se a sucursal está nas permitidas
        if int(sucursal_id) not in sucursais_ids:
            messages.error(request, 'Você não tem permissão para registrar movimentações nesta sucursal.')
            return redirect('stock:movimento_add_unified')
        
        try:
            with transaction.atomic():
                item = Item.objects.get(id=item_id)
                sucursal = Sucursal.objects.get(id=sucursal_id)
                tipo_movimento = TipoMovimentoStock.objects.get(id=tipo_movimento_id)
                
                # Verificar se há estoque suficiente para saída
                if not tipo_movimento.aumenta_estoque:
                    estoque_atual = StockItem.objects.filter(
                        item=item, 
                        sucursal=sucursal
                    ).first()
                    
                    if not estoque_atual or estoque_atual.quantidade_atual < int(quantidade):
                        messages.error(request, f'Estoque insuficiente. Disponível: {estoque_atual.quantidade_atual if estoque_atual else 0} unidades.')
                        return redirect('stock:movimento_add_unified')
                
                # Criar movimento unificado
                movimento = MovimentoItem(
                    item=item,
                    sucursal=sucursal,
                    tipo_movimento=tipo_movimento,
                    quantidade=int(quantidade),
                    preco_unitario=Decimal(preco_unitario),
                    referencia=referencia,
                    observacoes=observacoes,
                    usuario=request.user
                )
                movimento.save()
                
                messages.success(request, f'Movimentação de {item.get_tipo_display().lower()} registrada com sucesso! Código: {movimento.codigo}')
                
                return redirect('stock:movimentos')
                
        except ValidationError as e:
            messages.error(request, f'Erro de validação: {str(e)}')
        except Exception as e:
            logger.error(f"Erro ao registrar movimentação unificada: {e}")
            messages.error(request, f'Erro ao registrar movimentação: {str(e)}')
    
    context = {
        'itens': Item.objects.filter(status='ATIVO').order_by('tipo', 'nome'),
        'sucursais': sucursais_permitidas,
        'tipos_movimento': TipoMovimentoStock.objects.filter(ativo=True).order_by('nome'),
    }
    return render(request, 'stock/movimentos/form_unified.html', context)

@login_required
def stock_movimento_edit(request, id):
    """Editar movimentação de stock (SISTEMA UNIFICADO)"""
    from .models_stock import MovimentoItem, TipoMovimentoStock, Sucursal, Item
    from django.shortcuts import get_object_or_404, redirect
    from django.contrib import messages
    from django.db import transaction
    
    # Buscar movimento no sistema unificado
    movimento = get_object_or_404(MovimentoItem, id=id)
    movimento_tipo = movimento.item.tipo.lower()  # 'produto' ou 'material'
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Obter dados do formulário
                tipo_movimento_id = request.POST.get('tipo_movimento')
                sucursal_id = request.POST.get('sucursal')
                quantidade = request.POST.get('quantidade')
                preco_unitario = request.POST.get('preco_unitario')
                referencia = request.POST.get('referencia', '')
                observacoes = request.POST.get('observacoes', '')
                
                # Validar dados obrigatórios
                if not all([tipo_movimento_id, sucursal_id, quantidade, preco_unitario]):
                    messages.error(request, 'Todos os campos obrigatórios devem ser preenchidos.')
                    return redirect('stock:movimento_edit', id=id)
                
                # Obter objetos relacionados
                tipo_movimento = get_object_or_404(TipoMovimentoStock, id=tipo_movimento_id)
                sucursal = get_object_or_404(Sucursal, id=sucursal_id)
                
                # Atualizar movimento
                movimento.tipo_movimento = tipo_movimento
                movimento.sucursal = sucursal
                movimento.quantidade = int(quantidade)
                movimento.preco_unitario = float(preco_unitario)
                movimento.referencia = referencia
                movimento.observacoes = observacoes
                movimento.usuario = request.user
                
                # Salvar (o valor_total é calculado automaticamente no save())
                movimento.save()
                
                messages.success(request, f'Movimentação #{movimento.id:04d} atualizada com sucesso!')
                return redirect('stock:movimento_detail', id=movimento.id)
                
        except Exception as e:
            messages.error(request, f'Erro ao atualizar movimentação: {str(e)}')
            return redirect('stock:movimento_edit', id=id)
    
    # Obter dados para o formulário
    tipos_movimento = TipoMovimentoStock.objects.all().order_by('nome')
    sucursais = Sucursal.objects.all().order_by('nome')
    itens = Item.objects.filter(status='ATIVO').order_by('tipo', 'nome')
    
    context = {
        'movimento': movimento,
        'movimento_tipo': movimento_tipo,
        'movimento_unificado': True,  # Sempre True agora (sistema unificado)
        'tipos_movimento': tipos_movimento,
        'sucursais': sucursais,
        'itens': itens,
    }
    
    return render(request, 'stock/movimentos/form.html', context)

@login_required
def stock_movimento_delete(request, id):
    """Excluir movimentação de stock"""
    return render(request, 'stock/movimentos/delete.html', {})

@login_required
def stock_movimento_detail(request, id):
    """Detalhes da movimentação de stock (SISTEMA UNIFICADO)"""
    from .models_stock import MovimentoItem
    from django.shortcuts import get_object_or_404
    
    # Buscar movimento no sistema unificado
    movimento = get_object_or_404(MovimentoItem, id=id)
    movimento_tipo = movimento.item.tipo.lower()  # 'produto' ou 'material'
    movimento.item_tipo = movimento_tipo
    movimento.item_nome = movimento.item.nome
    movimento.item_codigo = movimento.item.codigo
    movimento.item_especifico = movimento.item.get_tipo_especifico_display()
    
    context = {
        'movimento': movimento,
        'movimento_tipo': movimento_tipo,
    }
    
    return render(request, 'stock/movimentos/detail.html', context)

@login_required
def stock_tipos_movimento(request):
    """Lista de tipos de movimento"""
    return render(request, 'stock/tipos_movimento/main.html', {})

@login_required
def stock_tipo_movimento_add(request):
    """Adicionar tipo de movimento"""
    return render(request, 'stock/tipos_movimento/form.html', {})

@login_required
def stock_tipo_movimento_edit(request, id):
    """Editar tipo de movimento"""
    return render(request, 'stock/tipos_movimento/form.html', {})

@login_required
def stock_tipo_movimento_delete(request, id):
    """Excluir tipo de movimento"""
    return render(request, 'stock/tipos_movimento/delete.html', {})

@login_required
def stock_relatorios(request):
    """Relatórios de stock"""
    from .models_stock import Item, MovimentoItem, StockItem
    from django.db.models import Q, F
    
    # Estatísticas para o dashboard
    total_produtos = Item.objects.filter(tipo='PRODUTO', status='ATIVO').count()
    total_materiais = Item.objects.filter(tipo='MATERIAL', status='ATIVO').count()
    total_itens = total_produtos + total_materiais
    
    # Movimentações dos últimos 30 dias
    from datetime import datetime, timedelta
    data_limite = datetime.now() - timedelta(days=30)
    total_movimentos = MovimentoItem.objects.filter(data_movimento__gte=data_limite).count()
    
    # Itens com estoque baixo
    produtos_estoque_baixo = StockItem.objects.filter(
        item__tipo='PRODUTO',
        quantidade_atual__lt=F('item__estoque_minimo')
    ).count()
    
    materiais_estoque_baixo = StockItem.objects.filter(
        item__tipo='MATERIAL',
        quantidade_atual__lt=F('item__estoque_minimo')
    ).count()
    
    total_estoque_baixo = produtos_estoque_baixo + materiais_estoque_baixo
    
    context = {
        'total_produtos': total_itens,  # Total de itens (produtos + materiais)
        'total_movimentos': total_movimentos,
        'produtos_estoque_baixo': total_estoque_baixo,
    }
    
    return render(request, 'stock/relatorios/main.html', context)

@login_required
def stock_relatorio_estoque_baixo(request):
    """Relatório de estoque baixo"""
    return render(request, 'stock/relatorios/estoque_baixo.html', {})

@login_required
def stock_relatorio_movimentacoes(request):
    """Relatório de movimentações"""
    return render(request, 'stock/relatorios/movimentacoes.html', {})

@login_required
def stock_relatorio_valor_estoque(request):
    """Relatório de valor do estoque"""
    return render(request, 'stock/relatorios/valor_estoque.html', {})

@login_required
@require_stock_access
def relatorio_movimentacoes(request):
    """Relatório de Movimentações"""
    from .models_stock import MovimentoItem, TipoMovimentoStock
    from django.db.models import Q
    from datetime import datetime, timedelta
    
    # Parâmetros de filtro
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    tipo_movimento = request.GET.get('tipo_movimento')
    
    # Se não especificado, usar últimos 30 dias
    if not data_inicio:
        data_inicio = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    if not data_fim:
        data_fim = datetime.now().strftime('%Y-%m-%d')
    
    # Filtrar movimentações
    movimentacoes = MovimentoItem.objects.select_related(
        'item', 'tipo_movimento', 'sucursal'
    ).filter(
        data_movimento__date__range=[data_inicio, data_fim]
    ).order_by('-data_movimento')
    
    if tipo_movimento:
        movimentacoes = movimentacoes.filter(tipo_movimento_id=tipo_movimento)
    
    # Estatísticas
    total_movimentacoes = movimentacoes.count()
    tipos_movimento = TipoMovimentoStock.objects.all()
    
    context = {
        'movimentacoes': movimentacoes,
        'total_movimentacoes': total_movimentacoes,
        'tipos_movimento': tipos_movimento,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'tipo_movimento_selecionado': tipo_movimento,
        'data_relatorio': timezone.now(),
    }
    
    return render(request, 'stock/relatorios/movimentacoes_documento.html', context)

@login_required
@require_stock_access
def relatorio_estoque_minimo(request):
    """Relatório de Estoque Mínimo"""
    from .models_stock import StockItem, Item
    from django.db import models
    
    # Itens com estoque abaixo do mínimo
    itens_baixo_estoque = StockItem.objects.select_related('item', 'sucursal').filter(
        quantidade_atual__lt=models.F('item__estoque_minimo'),
        item__estoque_minimo__gt=0
    ).order_by('item__nome')
    
    # Estatísticas
    total_itens_baixo = itens_baixo_estoque.count()
    valor_total_baixo = sum(
        item.item.preco_custo * item.quantidade_atual 
        for item in itens_baixo_estoque
    )
    
    context = {
        'itens_baixo_estoque': itens_baixo_estoque,
        'total_itens_baixo': total_itens_baixo,
        'valor_total_baixo': valor_total_baixo,
        'data_relatorio': timezone.now(),
    }
    
    return render(request, 'stock/relatorios/estoque_minimo_documento.html', context)

@login_required
@require_stock_access
def relatorio_ordens_compra(request):
    """Relatório de Ordens de Compra"""
    from .models_stock import OrdemCompra
    
    # Filtrar ordens de compra
    ordens = OrdemCompra.objects.select_related('fornecedor', 'sucursal_destino').order_by('-data_criacao')
    
    # Estatísticas
    total_ordens = ordens.count()
    valor_total_ordens = sum(ordem.valor_total for ordem in ordens)
    
    # Agrupar por status
    ordens_por_status = {}
    for ordem in ordens:
        status = ordem.get_status_display()
        if status not in ordens_por_status:
            ordens_por_status[status] = []
        ordens_por_status[status].append(ordem)
    
    context = {
        'ordens': ordens,
        'ordens_por_status': ordens_por_status,
        'total_ordens': total_ordens,
        'valor_total_ordens': valor_total_ordens,
        'data_relatorio': timezone.now(),
    }
    
    return render(request, 'stock/relatorios/ordens_compra_documento.html', context)

@login_required
@require_stock_access
def relatorio_devolucoes(request):
    """Relatório de Devoluções"""
    from .models_stock import MovimentoItem, TipoMovimentoStock
    
    # Movimentações de devolução
    devolucoes = MovimentoItem.objects.select_related(
        'item', 'tipo_movimento', 'sucursal'
    ).filter(
        tipo_movimento__nome__icontains='devolução'
    ).order_by('-data_movimento')
    
    # Estatísticas
    total_devolucoes = devolucoes.count()
    valor_total_devolucoes = sum(
        item.item.preco_custo * abs(item.quantidade) 
        for item in devolucoes
    )
    
    context = {
        'devolucoes': devolucoes,
        'total_devolucoes': total_devolucoes,
        'valor_total_devolucoes': valor_total_devolucoes,
        'data_relatorio': timezone.now(),
    }
    
    return render(request, 'stock/relatorios/devolucoes_documento.html', context)

@login_required
@require_stock_access
def relatorio_transferencias(request):
    """Relatório de Transferências"""
    from .models_stock import TransferenciaStock
    
    # Transferências entre sucursais
    transferencias = TransferenciaStock.objects.select_related(
        'sucursal_origem', 'sucursal_destino', 'criado_por'
    ).order_by('-data_criacao')
    
    # Estatísticas
    total_transferencias = transferencias.count()
    
    # Agrupar por sucursal origem
    transferencias_por_origem = {}
    for transferencia in transferencias:
        origem = transferencia.sucursal_origem.nome
        if origem not in transferencias_por_origem:
            transferencias_por_origem[origem] = []
        transferencias_por_origem[origem].append(transferencia)
    
    context = {
        'transferencias': transferencias,
        'transferencias_por_origem': transferencias_por_origem,
        'total_transferencias': total_transferencias,
        'data_relatorio': timezone.now(),
    }
    
    return render(request, 'stock/relatorios/transferencias_documento.html', context)

@login_required
@require_stock_access
def relatorio_estoque_atual(request):
    """Relatório de Estoque Atual"""
    from .models_stock import StockItem, Item, Sucursal
    
    # Obter todos os itens com stock
    itens_stock = StockItem.objects.select_related('item', 'sucursal').filter(
        quantidade_atual__gt=0
    ).order_by('item__nome')
    
    # Estatísticas
    total_itens = itens_stock.count()
    total_sucursais = Sucursal.objects.count()
    valor_total = sum(item.item.preco_custo * item.quantidade_atual for item in itens_stock)
    
    # Agrupar por sucursal e calcular valores
    estoque_por_sucursal = {}
    for item in itens_stock:
        sucursal_nome = item.sucursal.nome
        if sucursal_nome not in estoque_por_sucursal:
            estoque_por_sucursal[sucursal_nome] = {
                'itens': [],
                'total_valor': 0,
                'total_itens': 0
            }
        
        # Adicionar valor total calculado
        item.valor_total = item.item.preco_custo * item.quantidade_atual
        estoque_por_sucursal[sucursal_nome]['itens'].append(item)
        estoque_por_sucursal[sucursal_nome]['total_valor'] += item.valor_total
        estoque_por_sucursal[sucursal_nome]['total_itens'] += 1
    
    context = {
        'itens_stock': itens_stock,
        'estoque_por_sucursal': estoque_por_sucursal,
        'total_itens': total_itens,
        'total_sucursais': total_sucursais,
        'valor_total': valor_total,
        'data_relatorio': timezone.now(),
    }
    
    return render(request, 'stock/relatorios/estoque_atual_documento.html', context)

@login_required

@login_required
def api_stock_atualizar(request):
    """API para atualizar stock"""
    return JsonResponse({'status': 'success'})

# ===== VIEWS PARA MATERIAIS =====

# =============================================================================
# GESTÃO DE MATERIAIS
# =============================================================================

@login_required
def stock_materiais(request):
    """Lista de materiais com filtros e paginação"""
    try:
        # Parâmetros de busca e filtro
        search_query = request.GET.get('q', '').strip()
        categoria_id = request.GET.get('categoria')
        tipo = request.GET.get('tipo')
        status = request.GET.get('status')

        # Query base com otimizações - usando modelo unificado Item
        materiais = Item.objects.filter(tipo='MATERIAL').select_related('categoria')

        # Aplicar filtros
        if search_query:
            materiais = materiais.filter(
                Q(nome__icontains=search_query) |
                Q(codigo__icontains=search_query) |
                Q(codigo_barras__icontains=search_query) |
                Q(descricao__icontains=search_query)
            )
        
        if categoria_id:
            materiais = materiais.filter(categoria_id=categoria_id)
        
        if tipo:
            materiais = materiais.filter(tipo=tipo)
        
        if status:
            materiais = materiais.filter(status=status)

        # Ordenação
        materiais = materiais.order_by('nome')

        # Paginação
        paginator = Paginator(materiais, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Adicionar informações de stock para cada material
        from .models_stock import StockItem
        for material in page_obj:
            # Buscar stock total de todas as sucursais para este material
            stocks = StockItem.objects.filter(item=material)
            material.quantidade_atual = sum(float(stock.quantidade_atual) for stock in stocks)
        
        # Contar materiais com estoque baixo
        materiais_estoque_baixo = 0
        for material in page_obj:
            if material.quantidade_atual <= material.estoque_minimo:
                materiais_estoque_baixo += 1
        
        context = {
            'page_obj': page_obj,
            'search_query': search_query,
            'categoria_id': categoria_id,
            'tipo': tipo,
            'status': status,
            'categorias': CategoriaProduto.objects.filter(ativa=True).filter(
                Q(tipo='MATERIAL') | Q(tipo='AMBOS') | Q(tipo='TODOS')
            ),
            'tipos': Item.MATERIAL_TIPO_CHOICES,
            'status_choices': Item.STATUS_CHOICES,
            'materiais_estoque_baixo': materiais_estoque_baixo,
        }
        return render(request, 'stock/materiais/main.html', context)
    except Exception as e:
        logger.error(f"Erro ao listar materiais: {e}")
        messages.error(request, 'Erro ao carregar lista de materiais.')
        return render(request, 'stock/materiais/main.html', {'page_obj': None})

@login_required
@require_http_methods(["GET", "POST"])
def stock_material_add(request):
    """Adicionar novo material"""
    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        codigo = request.POST.get('codigo', '').strip()
        codigo_barras = request.POST.get('codigo_barras', '').strip()
        descricao = request.POST.get('descricao', '').strip()
        categoria_id = request.POST.get('categoria')
        tipo = request.POST.get('tipo')
        unidade_medida = request.POST.get('unidade_medida')
        preco_custo = request.POST.get('preco_custo')
        estoque_minimo = request.POST.get('estoque_minimo', 0)
        estoque_maximo = request.POST.get('estoque_maximo', 0)
        fornecedor_principal_id = request.POST.get('fornecedor_principal')
        observacoes = request.POST.get('observacoes', '').strip()
        
        # Validação dos campos obrigatórios
        if not all([nome, categoria_id, tipo, unidade_medida, preco_custo]):
            messages.error(request, 'Todos os campos obrigatórios devem ser preenchidos.')
            return redirect('stock:material_add')
        
        if len(nome) > 200:
            messages.error(request, 'Nome deve ter no máximo 200 caracteres.')
            return redirect('stock:material_add')
        
        try:
            with transaction.atomic():
                categoria = CategoriaProduto.objects.get(id=categoria_id)
                fornecedor_principal = None
                if fornecedor_principal_id:
                    fornecedor_principal = Fornecedor.objects.get(id=fornecedor_principal_id)
                
                # Criar material sem código primeiro (será gerado automaticamente no save)
                material = Item(
                    nome=nome,
                    codigo=codigo if codigo else '',  # Código vazio será gerado automaticamente
                    codigo_barras=codigo_barras,
                    descricao=descricao,
                    categoria=categoria,
                    tipo=tipo,
                    unidade_medida=unidade_medida,
                    preco_custo=Decimal(preco_custo),
                    estoque_minimo=int(estoque_minimo),
                    estoque_maximo=int(estoque_maximo),
                    fornecedor_principal=fornecedor_principal,
                    observacoes=observacoes
                )
                material.save()  # Isso irá chamar o método save() que gera o código automaticamente
                messages.success(request, 'Material adicionado com sucesso.')
                return redirect('stock:materiais')
        except ValidationError as e:
            messages.error(request, f'Erro de validação: {str(e)}')
        except Exception as e:
            logger.error(f"Erro ao adicionar material: {e}")
            messages.error(request, f'Erro ao adicionar material: {str(e)}')
    
    context = {
        'categorias': CategoriaProduto.objects.filter(ativa=True).filter(
            Q(tipo='MATERIAL') | Q(tipo='AMBOS') | Q(tipo='TODOS')
        ),
        'fornecedores': Fornecedor.objects.filter(status='ATIVO'),
        'tipos': Item.MATERIAL_TIPO_CHOICES,
        'unidades': Item.UNIDADE_CHOICES,
        'status_choices': Item.STATUS_CHOICES,
    }
    return render(request, 'stock/materiais/form.html', context)

@login_required
@require_http_methods(["GET", "POST"])
def stock_material_edit(request, id):
    """Editar material"""
    material = get_object_or_404(Item, id=id, tipo='MATERIAL')
    
    if request.method == 'POST':
        # Obter dados do formulário
        nome = request.POST.get('nome', '').strip()
        codigo = request.POST.get('codigo', '').strip()
        descricao = request.POST.get('descricao', '').strip()
        categoria_id = request.POST.get('categoria')
        tipo = request.POST.get('tipo')
        unidade_medida = request.POST.get('unidade_medida')
        preco_custo = request.POST.get('preco_custo', '').strip()
        estoque_minimo = request.POST.get('estoque_minimo', 0)
        estoque_maximo = request.POST.get('estoque_maximo', 0)
        observacoes = request.POST.get('observacoes', '').strip()
        
        # Validação simples
        erros = []
        if not nome: erros.append('Nome é obrigatório')
        if not categoria_id: erros.append('Categoria é obrigatória')
        if not tipo: erros.append('Tipo é obrigatório')
        if not unidade_medida: erros.append('Unidade de medida é obrigatória')
        if not preco_custo: erros.append('Preço de custo é obrigatório')
        
        # Converter vírgula para ponto
        if preco_custo and ',' in preco_custo:
            preco_custo = preco_custo.replace(',', '.')
        
        # Validar preço
        try:
            preco_decimal = Decimal(preco_custo)
            if preco_decimal <= 0:
                erros.append('Preço deve ser maior que zero')
        except (ValueError, TypeError):
            erros.append('Preço inválido')
        
        if erros:
            for erro in erros:
                messages.error(request, erro)
            return redirect('stock:material_edit', id=id)
        
        # Salvar dados
        try:
            with transaction.atomic():
                material.nome = nome
                material.codigo = codigo
                material.descricao = descricao
                material.categoria_id = categoria_id
                material.tipo = tipo
                material.unidade_medida = unidade_medida
                material.preco_custo = preco_decimal
                material.estoque_minimo = int(estoque_minimo)
                material.estoque_maximo = int(estoque_maximo)
                material.status = request.POST.get('status', 'ATIVO')
                material.observacoes = observacoes
                material.save()
                
                messages.success(request, 'Material atualizado com sucesso!')
                return redirect('stock:materiais')
                
        except Exception as e:
            messages.error(request, f'Erro ao salvar: {str(e)}')
            return redirect('stock:material_edit', id=id)
    
    # GET - Mostrar formulário
    context = {
        'material': material,
        'categorias': CategoriaProduto.objects.all(),
        'tipos': Item.TIPO_CHOICES,
        'status_choices': Item.STATUS_CHOICES,
        'unidades': Item.UNIDADE_CHOICES,
    }
    return render(request, 'stock/materiais/form.html', context)

@login_required
def stock_material_detail(request, id):
    """Detalhes do material"""
    try:
        material = get_object_or_404(Item, id=id, tipo='MATERIAL')
        
        context = {
            'material': material,
        }
        return render(request, 'stock/materiais/detail.html', context)
    except Exception as e:
        logger.error(f"Erro ao exibir detalhes do material {id}: {e}")
        messages.error(request, 'Erro ao carregar detalhes do material.')
        return redirect('stock:materiais')

@login_required
@require_http_methods(["GET", "POST"])
def stock_material_delete(request, id):
    """Excluir material"""
    material = get_object_or_404(Item, id=id, tipo='MATERIAL')
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Verificar se há receitas usando este material
                receitas_count = ItemReceita.objects.filter(material=material).count()
                stocks_count = StockItem.objects.filter(item=material).count()
                
                if receitas_count > 0 or stocks_count > 0:
                    messages.error(
                        request, 
                        f'Não é possível excluir este material pois ele está sendo usado por {receitas_count} receitas e {stocks_count} registros de stock.'
                    )
                    return redirect('stock:materiais')
                
                material.delete()
                messages.success(request, 'Material excluído com sucesso!')
        except Exception as e:
            logger.error(f"Erro ao excluir material {id}: {e}")
            messages.error(request, f'Erro ao excluir material: {str(e)}')
        return redirect('stock:materiais')
    
    context = {
        'material': material,
    }
    return render(request, 'stock/materiais/delete.html', context)

# ===== VIEWS PARA RECEITAS =====

# =============================================================================
# GESTÃO DE RECEITAS
# =============================================================================

@login_required
def stock_receitas(request):
    """Lista de receitas com filtros e paginação"""
    try:
        # Parâmetros de busca e filtro
        search_query = request.GET.get('q', '').strip()
        produto_id = request.GET.get('produto')
        status = request.GET.get('status')

        # Query base com otimizações
        receitas = Receita.objects.select_related('produto').all()

        # Aplicar filtros
        if search_query:
            receitas = receitas.filter(
                Q(nome__icontains=search_query) |
                Q(codigo__icontains=search_query) |
                Q(descricao__icontains=search_query) |
                Q(produto__nome__icontains=search_query)
            )
        
        if produto_id:
            receitas = receitas.filter(produto_id=produto_id)
        
        if status:
            receitas = receitas.filter(status=status)

        # Ordenação
        receitas = receitas.order_by('produto__nome', 'nome')

        # Paginação
        paginator = Paginator(receitas, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        context = {
            'page_obj': page_obj,
            'search_query': search_query,
            'produto_id': produto_id,
            'status': status,
            'produtos': Item.objects.filter(status='ATIVO', tipo='PRODUTO'),
            'status_choices': Receita.STATUS_CHOICES,
        }
        return render(request, 'stock/receitas/main.html', context)
    except Exception as e:
        logger.error(f"Erro ao listar receitas: {e}")
        messages.error(request, 'Erro ao carregar lista de receitas.')
        return render(request, 'stock/receitas/main.html', {'page_obj': None})

@login_required
@require_http_methods(["GET", "POST"])
def stock_receita_add(request):
    """Adicionar nova receita"""
    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        codigo = request.POST.get('codigo', '').strip()
        descricao = request.POST.get('descricao', '').strip()
        versao = request.POST.get('versao', '1.0').strip()
        produto_id = request.POST.get('produto')
        rendimento = request.POST.get('rendimento', 1)
        unidade_rendimento = request.POST.get('unidade_rendimento')
        tempo_producao_horas = request.POST.get('tempo_producao_horas', '0')
        status = request.POST.get('status', 'ATIVO')
        observacoes = request.POST.get('observacoes', '').strip()
        
        # Validação dos campos obrigatórios
        if not all([nome, produto_id, unidade_rendimento]):
            messages.error(request, 'Nome, produto e unidade de rendimento são obrigatórios.')
            return redirect('stock:receita_add')
        
        if len(nome) > 200:
            messages.error(request, 'Nome deve ter no máximo 200 caracteres.')
            return redirect('stock:receita_add')
        
        try:
            with transaction.atomic():
                produto = Item.objects.get(id=produto_id, tipo='PRODUTO')
                
                # Criar receita
                receita = Receita(
                    nome=nome,
                    codigo=codigo if codigo else '',  # Código vazio será gerado automaticamente
                    descricao=descricao,
                    versao=versao,
                    produto=produto,
                    rendimento=int(rendimento),
                    unidade_rendimento=unidade_rendimento,
                    tempo_producao_horas=Decimal(str(tempo_producao_horas)),
                    status=status,
                    observacoes=observacoes
                )
                receita.save()  # Isso irá chamar o método save() que gera o código automaticamente
                
                # Processar itens da receita (materiais)
                itens_data = request.POST.get('itens_receita', '')
                if itens_data:
                    try:
                        itens_json = json.loads(itens_data)
                        for item_data in itens_json:
                            material_id = item_data.get('material_id')
                            quantidade = item_data.get('quantidade')
                            unidade = item_data.get('unidade')
                            
                            if material_id and quantidade and unidade:
                                material = Item.objects.get(id=material_id, tipo='MATERIAL')
                                ItemReceita.objects.create(
                                    receita=receita,
                                    material=material,
                                    quantidade=Decimal(quantidade),
                                    unidade_medida=unidade
                                )
                    except (json.JSONDecodeError, Item.DoesNotExist) as e:
                        logger.warning(f"Erro ao processar itens da receita: {e}")
                        messages.warning(request, f'Erro ao processar itens da receita: {str(e)}')
                
                messages.success(request, 'Receita adicionada com sucesso.')
                return redirect('stock:receitas')
        except Item.DoesNotExist:
            messages.error(request, 'Produto selecionado não encontrado.')
        except ValidationError as e:
            messages.error(request, f'Erro de validação: {str(e)}')
        except Exception as e:
            logger.error(f"Erro ao adicionar receita: {e}")
            messages.error(request, f'Erro ao adicionar receita: {str(e)}')
    
    context = {
        'produtos': Item.objects.filter(status='ATIVO', tipo='PRODUTO'),
        'materiais': Item.objects.filter(status='ATIVO', tipo='MATERIAL'),
        'materiais_json': json.dumps([{
            'id': m.id,
            'nome': m.nome,
            'codigo': m.codigo,
            'preco_custo': float(m.preco_custo),
            'unidade_medida': m.unidade_medida
        } for m in Item.objects.filter(status='ATIVO', tipo='MATERIAL')], cls=DjangoJSONEncoder),
        'status_choices': Receita.STATUS_CHOICES,
        'unidades': Item.UNIDADE_CHOICES,
    }
    return render(request, 'stock/receitas/form.html', context)

@login_required
@require_http_methods(["GET", "POST"])
def stock_receita_edit(request, id):
    """Editar receita"""
    receita = get_object_or_404(Receita, id=id)
    
    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        codigo = request.POST.get('codigo', '').strip()
        descricao = request.POST.get('descricao', '').strip()
        versao = request.POST.get('versao', '1.0').strip()
        produto_id = request.POST.get('produto')
        rendimento = request.POST.get('rendimento')
        unidade_rendimento = request.POST.get('unidade_rendimento')
        tempo_producao_horas = request.POST.get('tempo_producao_horas')
        status = request.POST.get('status')
        observacoes = request.POST.get('observacoes', '').strip()
        
        # Validação dos campos obrigatórios
        if not all([nome, produto_id, unidade_rendimento]):
            messages.error(request, 'Nome, produto e unidade de rendimento são obrigatórios.')
            return redirect('stock:receita_edit', id=id)
        
        if len(nome) > 200:
            messages.error(request, 'Nome deve ter no máximo 200 caracteres.')
            return redirect('stock:receita_edit', id=id)
        
        try:
            with transaction.atomic():
                receita.nome = nome
                receita.codigo = codigo
                receita.descricao = descricao
                receita.versao = versao
                receita.produto = Item.objects.get(id=produto_id, tipo='PRODUTO')
                if rendimento:
                    receita.rendimento = int(rendimento)
                receita.unidade_rendimento = unidade_rendimento
                if tempo_producao_horas:
                    receita.tempo_producao_horas = Decimal(str(tempo_producao_horas))
                if status:
                    receita.status = status
                receita.observacoes = observacoes
                receita.save()
                
                # Processar itens da receita (materiais)
                itens_data = request.POST.get('itens_receita', '')
                if itens_data:
                    try:
                        itens_json = json.loads(itens_data)
                        # Só limpar itens se houver dados válidos
                        if itens_json:
                            receita.itens.all().delete()
                            
                            for item_data in itens_json:
                                material_id = item_data.get('material_id')
                                quantidade = item_data.get('quantidade')
                                unidade = item_data.get('unidade')
                                
                                if material_id and quantidade and unidade:
                                    material = Item.objects.get(id=material_id, tipo='MATERIAL')
                                    ItemReceita.objects.create(
                                        receita=receita,
                                        material=material,
                                        quantidade=Decimal(quantidade),
                                        unidade_medida=unidade
                                    )
                    except (json.JSONDecodeError, Item.DoesNotExist) as e:
                        logger.warning(f"Erro ao processar itens da receita: {e}")
                        messages.warning(request, f'Erro ao processar itens da receita: {str(e)}')
                
                messages.success(request, 'Receita atualizada com sucesso.')
                return redirect('stock:receitas')
        except Item.DoesNotExist:
            messages.error(request, 'Produto selecionado não encontrado.')
        except ValidationError as e:
            messages.error(request, f'Erro de validação: {str(e)}')
        except Exception as e:
            logger.error(f"Erro ao editar receita {id}: {e}")
            messages.error(request, f'Erro ao atualizar receita: {str(e)}')
    
    context = {
        'receita': receita,
        'produtos': Item.objects.filter(status='ATIVO', tipo='PRODUTO'),
        'materiais': Item.objects.filter(status='ATIVO', tipo='MATERIAL'),
        'materiais_json': json.dumps([{
            'id': m.id,
            'nome': m.nome,
            'codigo': m.codigo,
            'preco_custo': float(m.preco_custo),
            'unidade_medida': m.unidade_medida
        } for m in Item.objects.filter(status='ATIVO', tipo='MATERIAL')], cls=DjangoJSONEncoder),
        'status_choices': Receita.STATUS_CHOICES,
        'unidades': Item.UNIDADE_CHOICES,
    }
    return render(request, 'stock/receitas/form.html', context)

@login_required
def stock_receita_detail(request, id):
    """Detalhes da receita"""
    try:
        receita = get_object_or_404(Receita, id=id)
        
        context = {
            'receita': receita,
        }
        return render(request, 'stock/receitas/detail.html', context)
    except Exception as e:
        logger.error(f"Erro ao exibir detalhes da receita {id}: {e}")
        messages.error(request, 'Erro ao carregar detalhes da receita.')
        return redirect('stock:receitas')

@login_required
@require_http_methods(["GET", "POST"])
def stock_receita_delete(request, id):
    """Excluir receita"""
    receita = get_object_or_404(Receita, id=id)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                receita.delete()
                messages.success(request, 'Receita excluída com sucesso!')
        except Exception as e:
            logger.error(f"Erro ao excluir receita {id}: {e}")
            messages.error(request, f'Erro ao excluir receita: {str(e)}')
        return redirect('stock:receitas')
    
    context = {
        'receita': receita,
    }
    return render(request, 'stock/receitas/delete.html', context)
