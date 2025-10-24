from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.template.loader import render_to_string
from django.core.paginator import Paginator
from django.db.models import Q, F, Count, Sum, Max
from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import json
import logging

# Configurar logger
logger = logging.getLogger(__name__)

from .decorators import require_stock_access
from .models_stock import (
    InventarioFisico, ItemInventario, AjusteInventario, HistoricoContagem,
    Item, Sucursal, StockItem, MovimentoItem, TipoMovimentoStock
)
from django.contrib.auth.models import User


@login_required
@require_stock_access
def inventario_list(request):
    """Lista de inventários físicos"""
    # Obter parâmetros de filtro
    search_query = request.GET.get('search', '').strip()
    status = request.GET.get('status', '').strip()
    sucursal_id = request.GET.get('sucursal', '').strip()
    data_inicio = request.GET.get('data_inicio', '').strip()
    data_fim = request.GET.get('data_fim', '').strip()
    ordenar = request.GET.get('ordenar', '-data_criacao').strip()
    
    # Buscar inventários
    inventarios = InventarioFisico.objects.select_related(
        'sucursal', 'usuario_responsavel', 'usuario_criador'
    ).prefetch_related('itens_inventario')
    
    # Aplicar filtros
    if search_query:
        inventarios = inventarios.filter(
            Q(codigo__icontains=search_query) |
            Q(nome__icontains=search_query) |
            Q(sucursal__nome__icontains=search_query) |
            Q(observacoes__icontains=search_query)
        )
    
    if status:
        inventarios = inventarios.filter(status=status)
    
    if sucursal_id:
        inventarios = inventarios.filter(sucursal_id=sucursal_id)
    
    if data_inicio:
        inventarios = inventarios.filter(data_inicio__date__gte=data_inicio)
    
    if data_fim:
        inventarios = inventarios.filter(data_inicio__date__lte=data_fim)
    
    # Aplicar ordenação
    if ordenar:
        inventarios = inventarios.order_by(ordenar)
    
    # Paginação
    paginator = Paginator(inventarios, 20)
    page_number = request.GET.get('page')
    inventarios_page = paginator.get_page(page_number)
    
    # Contadores para estatísticas
    total_inventarios = InventarioFisico.objects.count()
    inventarios_planejados = InventarioFisico.objects.filter(status='PLANEJADO').count()
    inventarios_andamento = InventarioFisico.objects.filter(status='EM_ANDAMENTO').count()
    inventarios_concluidos = InventarioFisico.objects.filter(status='CONCLUIDO').count()
    
    # Dados para filtros
    sucursais = Sucursal.objects.all()
    
    context = {
        'inventarios': inventarios_page,
        'search_query': search_query,
        'status': status,
        'sucursal_id': sucursal_id,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'ordenar': ordenar,
        'total_inventarios': total_inventarios,
        'inventarios_planejados': inventarios_planejados,
        'inventarios_andamento': inventarios_andamento,
        'inventarios_concluidos': inventarios_concluidos,
        'sucursais': sucursais,
    }
    
    return render(request, 'stock/inventario/list.html', context)


@login_required
@require_stock_access
@require_http_methods(["GET", "POST"])
def inventario_create(request):
    """Criar novo inventário físico"""
    logger.info(f"Iniciando criação de inventário - Usuário: {request.user.username}")
    
    if request.method == 'POST':
        logger.info("Método POST detectado")
        try:
            # Log dos dados recebidos
            nome = request.POST.get('nome', '').strip()
            sucursal_id = request.POST.get('sucursal', '').strip()
            data_inicio = request.POST.get('data_inicio', '').strip()
            data_fim = request.POST.get('data_fim', '').strip()
            funcionario_responsavel_id = request.POST.get('usuario_responsavel', '').strip()
            observacoes = request.POST.get('observacoes', '').strip()
            
            logger.info(f"Dados recebidos - Nome: {nome}, Sucursal: {sucursal_id}, Data: {data_inicio}, Funcionário: {funcionario_responsavel_id}")
            
            if not all([nome, sucursal_id, data_inicio, funcionario_responsavel_id]):
                logger.warning("Campos obrigatórios não preenchidos")
                messages.error(request, 'Todos os campos obrigatórios devem ser preenchidos.')
                return redirect('stock:inventario:create')
            
            logger.info("Validando sucursal...")
            sucursal = get_object_or_404(Sucursal, id=sucursal_id)
            logger.info(f"Sucursal encontrada: {sucursal.nome}")
            
            logger.info("Importando modelo Funcionario...")
            from .models_rh import Funcionario
            logger.info("Modelo Funcionario importado com sucesso")
            
            logger.info(f"Buscando funcionário com ID: {funcionario_responsavel_id}")
            funcionario_responsavel = get_object_or_404(Funcionario, id=funcionario_responsavel_id)
            logger.info(f"Funcionário encontrado: {funcionario_responsavel.nome_completo}")
            
            logger.info("Convertendo data...")
            data_inicio_dt = datetime.strptime(data_inicio, '%Y-%m-%dT%H:%M')
            data_inicio_tz = timezone.make_aware(data_inicio_dt)
            logger.info(f"Data convertida: {data_inicio_tz}")
            
            # Processar data_fim se fornecida
            data_fim_tz = None
            if data_fim:
                data_fim_dt = datetime.strptime(data_fim, '%Y-%m-%dT%H:%M')
                data_fim_tz = timezone.make_aware(data_fim_dt)
                logger.info(f"Data fim convertida: {data_fim_tz}")
            
            logger.info("Criando inventário...")
            inventario = InventarioFisico.objects.create(
                nome=nome,
                sucursal=sucursal,
                data_inicio=data_inicio_tz,
                data_fim=data_fim_tz,
                usuario_responsavel=request.user,  # Usar o usuário logado como responsável
                observacoes=observacoes,
                usuario_criador=request.user
            )
            logger.info(f"Inventário criado com sucesso: {inventario.codigo}")
            
            logger.info("Adicionando itens ao inventário...")
            stock_items = StockItem.objects.filter(sucursal=sucursal).select_related('item')
            logger.info(f"Encontrados {stock_items.count()} itens de stock na sucursal")
            
            for stock_item in stock_items:
                ItemInventario.objects.create(
                    inventario=inventario,
                    item=stock_item.item,
                    quantidade_sistema=stock_item.quantidade_atual
                )
            
            logger.info(f"Inventário {inventario.codigo} criado com sucesso!")
            messages.success(request, f'Inventário {inventario.codigo} criado com sucesso!')
            return redirect('stock:inventario:detail', id=inventario.pk)
            
        except Exception as e:
            logger.error(f"Erro ao criar inventário: {str(e)}", exc_info=True)
            messages.error(request, f'Erro ao criar inventário: {str(e)}')
            return redirect('stock:inventario:create')
    
    # GET - mostrar formulário
    logger.info("Método GET - Carregando formulário de criação")
    sucursais = Sucursal.objects.all()
    logger.info(f"Encontradas {sucursais.count()} sucursais")
    
    # Buscar funcionários do módulo RH
    from .models_rh import Funcionario
    
    funcionarios_ativos = Funcionario.objects.filter(
        status='AT'  # Status 'AT' = Ativo
    ).select_related('sucursal', 'departamento', 'cargo').order_by('nome_completo')
    
    logger.info(f"Encontrados {funcionarios_ativos.count()} funcionários ativos")
    
    # Criar lista com informações dos funcionários
    funcionarios_info = []
    for funcionario in funcionarios_ativos:
        funcionarios_info.append({
            'funcionario': funcionario,
            'nome_display': funcionario.nome_completo,
            'codigo': funcionario.codigo_funcionario,
            'email': funcionario.email or 'N/A',
            'sucursal': funcionario.sucursal.nome,
            'departamento': funcionario.departamento.nome,
            'cargo': funcionario.cargo.nome
        })
    
    usuarios = funcionarios_info
    logger.info(f"Preparados {len(usuarios)} funcionários para o dropdown")
    
    context = {
        'sucursais': sucursais,
        'usuarios': usuarios,
    }
    
    logger.info("Renderizando template de criação")
    return render(request, 'stock/inventario/create.html', context)


@login_required
@require_stock_access
def inventario_detail(request, id):
    """Detalhes do inventário físico"""
    inventario = get_object_or_404(InventarioFisico, id=id)
    
    # Obter itens do inventário
    itens_inventario = ItemInventario.objects.filter(
        inventario=inventario
    ).select_related('item', 'usuario_contador').order_by('item__nome')
    
    # Estatísticas
    total_itens = inventario.total_itens
    itens_contados = inventario.itens_contados
    progresso = inventario.progresso_percentual
    
    # Itens com diferenças
    itens_com_diferenca = itens_inventario.exclude(diferenca=0)
    
    # NOVA LÓGICA: Calcular botões baseado no fluxo correto
    itens_com_diferenca_nao_finalizados = itens_com_diferenca.filter(
        contagem_finalizada=False,
        numero_contagem__lt=3
    )
    
    # Itens finalizados (3 contagens)
    itens_finalizados = itens_inventario.filter(contagem_finalizada=True)
    
    # Calcular fase atual baseada no número máximo de contagens
    max_contagem = itens_inventario.aggregate(max_contagem=models.Max('numero_contagem'))['max_contagem'] or 0
    
    # Determinar fase atual
    if max_contagem == 0:
        fase_atual = 1  # Primeira contagem
    elif max_contagem == 1:
        if itens_com_diferenca.exists():
            fase_atual = 2  # Segunda contagem necessária
        else:
            fase_atual = 4  # Concluído após primeira contagem
    elif max_contagem == 2:
        if itens_com_diferenca_nao_finalizados.exists():
            fase_atual = 3  # Terceira contagem necessária
        else:
            fase_atual = 4  # Concluído após segunda contagem
    elif max_contagem >= 3:
        fase_atual = 4  # Concluído após terceira contagem
    
    # Determinar qual botão mostrar
    pode_finalizar = False
    pode_proxima_contagem = False
    
    if not itens_com_diferenca.exists():
        # Não há diferenças - pode finalizar
        pode_finalizar = True
    elif itens_com_diferenca_nao_finalizados.exists():
        # Há diferenças que ainda podem ser recontadas - próxima contagem
        pode_proxima_contagem = True
    else:
        # Todos os itens com diferenças já fizeram 3 contagens - pode finalizar
        pode_finalizar = True
    
    # Estatísticas de contagem
    contagem_stats = {
        'total_itens': total_itens,
        'itens_contados': itens_contados,
        'itens_com_diferenca': itens_com_diferenca.count(),
        'itens_para_recontar': itens_com_diferenca_nao_finalizados.count(),
        'itens_finalizados': itens_finalizados.count(),
        'progresso': progresso,
        'pode_finalizar': pode_finalizar,
        'pode_proxima_contagem': pode_proxima_contagem,
        'fase_atual': fase_atual
    }
    
    # Ajustes pendentes
    ajustes_pendentes = AjusteInventario.objects.filter(
        inventario=inventario,
        aprovado=False
    ).count()
    
    # Determinar quais itens mostrar na tabela baseado na fase atual
    if fase_atual == 1:
        # Primeira contagem - mostrar todos os itens
        itens_para_exibir = itens_inventario
    elif fase_atual == 2:
        # Segunda contagem - mostrar apenas itens com diferenças que podem ser recontados
        itens_para_exibir = itens_com_diferenca_nao_finalizados
    elif fase_atual == 3:
        # Terceira contagem - mostrar apenas itens com diferenças que podem ser recontados
        itens_para_exibir = itens_com_diferenca_nao_finalizados
    else:
        # Inventário concluído - mostrar todos os itens
        itens_para_exibir = itens_inventario
    
    context = {
        'object': inventario,
        'object_name': inventario.nome,
        'entity_name': 'inventario',
        'breadcrumb_url': 'stock:inventario:list',
        'breadcrumb_title': 'Inventários',
        'header_icon': 'clipboard-list',
        'page_subtitle': 'Detalhes completos do inventário',
        'back_url': 'stock:inventario:list',
        'edit_url': 'stock:inventario:update_item',
        'inventario': inventario,
        'itens_inventario': itens_para_exibir,
        'total_itens': total_itens,
        'itens_contados': itens_contados,
        'contagem_stats': contagem_stats,
        'itens_com_diferenca': itens_com_diferenca,
        'itens_para_recontar': itens_com_diferenca_nao_finalizados,
        'itens_finalizados': itens_finalizados,
        'ajustes_pendentes': ajustes_pendentes,
    }
    
    return render(request, 'stock/inventario/detail.html', context)


@login_required
@require_stock_access
@require_http_methods(["POST"])
def inventario_update_item(request, id, item_id):
    """Atualizar contagem de item do inventário com controle de 3 contagens"""
    inventario = get_object_or_404(InventarioFisico, id=id)
    item_inventario = get_object_or_404(ItemInventario, id=item_id, inventario=inventario)
    
    if inventario.status not in ['PLANEJADO', 'EM_ANDAMENTO']:
        messages.error(request, 'Não é possível editar inventários concluídos ou cancelados.')
        return redirect('stock:inventario:detail', id=inventario.id)
    
    # Verificar se já atingiu o limite de 3 contagens
    if item_inventario.numero_contagem >= 3:
        messages.warning(request, f'Item {item_inventario.item.nome} já atingiu o limite de 3 contagens.')
        return redirect('stock:inventario:detail', id=inventario.id)
    
    try:
        quantidade_contada = request.POST.get('quantidade_contada', '').strip()
        observacoes = request.POST.get('observacoes', '').strip()
        
        if quantidade_contada:
            quantidade = int(quantidade_contada)
            if quantidade < 0:
                messages.error(request, 'Quantidade não pode ser negativa.')
                return redirect('stock:inventario:detail', id=inventario.id)
            
            # Incrementar número da contagem
            item_inventario.numero_contagem += 1
            
            # Atualizar dados da contagem atual
            item_inventario.quantidade_contada = quantidade
            item_inventario.observacoes = observacoes
            item_inventario.data_contagem = timezone.now()
            item_inventario.usuario_contador = request.user
            
            # Calcular diferença
            diferenca = quantidade - item_inventario.quantidade_sistema
            item_inventario.diferenca = diferenca
            
            # Marcar como finalizado se atingiu 3 contagens
            if item_inventario.numero_contagem >= 3:
                item_inventario.contagem_finalizada = True
                item_inventario.precisa_recontagem = False
            else:
                item_inventario.contagem_finalizada = False
                # Verificar se precisa recontagem (se há diferença e ainda não atingiu 3 contagens)
                if diferenca != 0:
                    item_inventario.precisa_recontagem = True
                else:
                    item_inventario.precisa_recontagem = False
            
            # Salvar item do inventário
            item_inventario.save()
            
            # Criar registro no histórico de contagens
            from .models_stock import HistoricoContagem
            HistoricoContagem.objects.create(
                item_inventario=item_inventario,
                numero_contagem=item_inventario.numero_contagem,
                quantidade_contada=quantidade,
                diferenca=diferenca,
                observacoes=observacoes,
                data_contagem=timezone.now(),
                usuario_contador=request.user
            )
            
            # Atualizar status do inventário para "Em Andamento"
            if inventario.status == 'PLANEJADO':
                inventario.status = 'EM_ANDAMENTO'
                inventario.save()
            
            # Mensagem baseada no número da contagem
            if item_inventario.numero_contagem == 1:
                messages.success(request, f'1ª contagem de {item_inventario.item.nome}: {quantidade}')
            elif item_inventario.numero_contagem == 2:
                messages.success(request, f'2ª contagem de {item_inventario.item.nome}: {quantidade}')
            else:
                messages.success(request, f'3ª contagem de {item_inventario.item.nome}: {quantidade} (FINALIZADA)')
            
            # Aviso se há diferença e ainda pode recontar
            if diferenca != 0 and item_inventario.numero_contagem < 3:
                messages.warning(request, f'Diferença detectada! Item será incluído na próxima recontagem.')
            
        else:
            messages.error(request, 'Quantidade é obrigatória.')
            
    except ValueError:
        messages.error(request, 'Quantidade deve ser um número válido.')
    except Exception as e:
        messages.error(request, f'Erro ao atualizar contagem: {str(e)}')
    
    return redirect('stock:inventario:detail', id=inventario.id)


@login_required
@require_stock_access
@require_http_methods(["POST"])
def inventario_proxima_contagem(request, id):
    """Iniciar próxima contagem apenas dos itens com diferenças"""
    inventario = get_object_or_404(InventarioFisico, id=id)
    
    if inventario.status not in ['PLANEJADO', 'EM_ANDAMENTO']:
        messages.error(request, 'Não é possível editar inventários concluídos ou cancelados.')
        return redirect('stock:inventario:detail', id=inventario.id)
    
    # NOVA LÓGICA: Buscar itens com diferenças que ainda podem ser recontados
    itens_com_diferenca = inventario.itens_inventario.exclude(diferenca=0)
    itens_para_recontar = itens_com_diferenca.filter(
        contagem_finalizada=False,
        numero_contagem__lt=3
    )
    
    if not itens_para_recontar.exists():
        messages.info(request, 'Não há itens para recontagem. Todos os itens estão corretos ou já foram contados 3 vezes.')
        return redirect('stock:inventario:detail', id=inventario.id)
    
    # Resetar flag de recontagem para permitir nova contagem
    itens_para_recontar.update(precisa_recontagem=False)
    
    # Atualizar status do inventário
    if inventario.status == 'PLANEJADO':
        inventario.status = 'EM_ANDAMENTO'
        inventario.save()
    
    count = itens_para_recontar.count()
    messages.success(request, f'Próxima contagem iniciada! {count} item(s) com diferenças serão recontados.')
    
    return redirect('stock:inventario:detail', id=inventario.id)


@login_required
@require_stock_access
@require_http_methods(["POST"])
def inventario_finalizar(request, id):
    """Finalizar inventário e gerar ajustes - apenas quando todos os itens estão prontos"""
    inventario = get_object_or_404(InventarioFisico, id=id)
    
    if inventario.status != 'EM_ANDAMENTO':
        messages.error(request, 'Apenas inventários em andamento podem ser finalizados.')
        return redirect('stock:inventario:detail', id=inventario.id)
    
    try:
        # Verificar se todos os itens foram contados pelo menos uma vez
        itens_nao_contados = inventario.itens_inventario.filter(quantidade_contada__isnull=True)
        if itens_nao_contados.exists():
            messages.error(request, f'Não é possível finalizar! Ainda existem {itens_nao_contados.count()} itens não contados.')
            return redirect('stock:inventario:detail', id=inventario.id)
        
        # NOVA LÓGICA: Verificar se pode finalizar baseado no fluxo correto
        itens_com_diferenca = inventario.itens_inventario.exclude(diferenca=0)
        
        # Se não há diferenças, pode finalizar imediatamente
        if not itens_com_diferenca.exists():
            # Todos os itens estão conforme - pode finalizar
            pass
        else:
            # Há diferenças - verificar se já fez 3 contagens
            itens_com_diferenca_nao_finalizados = itens_com_diferenca.filter(
                contagem_finalizada=False,
                numero_contagem__lt=3
            )
            
            if itens_com_diferenca_nao_finalizados.exists():
                itens_nomes = [item.item.nome for item in itens_com_diferenca_nao_finalizados]
                messages.error(request, f'Não é possível finalizar! Os seguintes itens têm diferenças e ainda podem ser recontados: {", ".join(itens_nomes)}')
                return redirect('stock:inventario:detail', id=inventario.id)
        
        # Se chegou até aqui, todos os itens estão prontos para finalização
        # Criar ajustes apenas para itens que realmente têm diferenças finais
        itens_com_diferenca_final = inventario.itens_inventario.exclude(diferenca=0)
        
        ajustes_criados = 0
        for item_inv in itens_com_diferenca_final:
            AjusteInventario.objects.create(
                inventario=inventario,
                item=item_inv.item,
                sucursal=inventario.sucursal,
                quantidade_anterior=item_inv.quantidade_sistema,
                quantidade_nova=item_inv.quantidade_contada,
                motivo=f"Inventário físico {inventario.codigo} - {item_inv.numero_contagem}ª contagem",
                usuario_ajuste=request.user
            )
            ajustes_criados += 1
        
        # Finalizar inventário
        inventario.status = 'CONCLUIDO'
        inventario.data_fim = timezone.now()
        inventario.save()
        
        if ajustes_criados > 0:
            messages.success(request, f'Inventário finalizado com sucesso! {ajustes_criados} ajustes criados para itens com diferenças.')
        else:
            messages.success(request, 'Inventário finalizado com sucesso! Todos os itens estão conforme o sistema.')
        
    except Exception as e:
        messages.error(request, f'Erro ao finalizar inventário: {str(e)}')
    
    return redirect('stock:inventario:detail', id=inventario.id)


@login_required
@require_stock_access
def ajustes_list(request):
    """Lista de ajustes de inventário"""
    # Obter parâmetros de filtro
    search_query = request.GET.get('search', '').strip()
    tipo_ajuste = request.GET.get('tipo_ajuste', '').strip()
    sucursal_id = request.GET.get('sucursal', '').strip()
    aprovado = request.GET.get('aprovado', '').strip()
    data_inicio = request.GET.get('data_inicio', '').strip()
    data_fim = request.GET.get('data_fim', '').strip()
    ordenar = request.GET.get('ordenar', '-data_ajuste').strip()
    
    # Buscar ajustes
    ajustes = AjusteInventario.objects.select_related(
        'item', 'sucursal', 'usuario_ajuste', 'usuario_aprovacao', 'inventario'
    )
    
    # Aplicar filtros
    if search_query:
        ajustes = ajustes.filter(
            Q(codigo__icontains=search_query) |
            Q(item__nome__icontains=search_query) |
            Q(item__codigo__icontains=search_query) |
            Q(motivo__icontains=search_query)
        )
    
    if tipo_ajuste:
        ajustes = ajustes.filter(tipo_ajuste=tipo_ajuste)
    
    if sucursal_id:
        ajustes = ajustes.filter(sucursal_id=sucursal_id)
    
    if aprovado == 'true':
        ajustes = ajustes.filter(aprovado=True)
    elif aprovado == 'false':
        ajustes = ajustes.filter(aprovado=False)
    
    if data_inicio:
        ajustes = ajustes.filter(data_ajuste__date__gte=data_inicio)
    
    if data_fim:
        ajustes = ajustes.filter(data_ajuste__date__lte=data_fim)
    
    # Aplicar ordenação
    if ordenar:
        ajustes = ajustes.order_by(ordenar)
    
    # Paginação
    paginator = Paginator(ajustes, 20)
    page_number = request.GET.get('page')
    ajustes_page = paginator.get_page(page_number)
    
    # Contadores para estatísticas
    total_ajustes = AjusteInventario.objects.count()
    ajustes_pendentes = AjusteInventario.objects.filter(aprovado=False).count()
    ajustes_aprovados = AjusteInventario.objects.filter(aprovado=True).count()
    
    # Dados para filtros
    sucursais = Sucursal.objects.all()
    
    context = {
        'ajustes': ajustes_page,
        'search_query': search_query,
        'tipo_ajuste': tipo_ajuste,
        'sucursal_id': sucursal_id,
        'aprovado': aprovado,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'ordenar': ordenar,
        'total_ajustes': total_ajustes,
        'ajustes_pendentes': ajustes_pendentes,
        'ajustes_aprovados': ajustes_aprovados,
        'sucursais': sucursais,
    }
    
    return render(request, 'stock/inventario/ajustes_list.html', context)


@login_required
@require_stock_access
@require_http_methods(["POST"])
def ajuste_aprovar(request, id):
    """Aprovar ajuste de inventário"""
    ajuste = get_object_or_404(AjusteInventario, id=id)
    
    if ajuste.aprovado:
        messages.error(request, 'Este ajuste já foi aprovado.')
        return redirect('stock:inventario:ajustes_list')
    
    try:
        # Aprovar ajuste
        ajuste.aprovado = True
        ajuste.usuario_aprovacao = request.user
        ajuste.data_aprovacao = timezone.now()
        ajuste.save()
        
        # Aplicar ajuste no stock
        if ajuste.aplicar_ajuste():
            messages.success(request, f'Ajuste {ajuste.codigo} aprovado e aplicado com sucesso!')
        else:
            messages.error(request, 'Erro ao aplicar ajuste no stock.')
            
    except Exception as e:
        messages.error(request, f'Erro ao aprovar ajuste: {str(e)}')
    
    return redirect('stock:inventario:ajustes_list')


@login_required
@require_stock_access
def inventario_relatorio(request, id):
    """Relatório detalhado do inventário"""
    inventario = get_object_or_404(InventarioFisico, id=id)
    
    # Dados do inventário
    itens_inventario = ItemInventario.objects.filter(
        inventario=inventario
    ).select_related('item', 'usuario_contador').order_by('item__nome')
    
    # Estatísticas
    total_itens = inventario.total_itens
    itens_contados = inventario.itens_contados
    itens_com_diferenca = itens_inventario.exclude(diferenca=0)
    
    # Resumo por tipo de diferença
    aumentos = itens_com_diferenca.filter(diferenca__gt=0)
    diminuicoes = itens_com_diferenca.filter(diferenca__lt=0)
    
    # Ajustes gerados
    ajustes = AjusteInventario.objects.filter(inventario=inventario)
    
    # Histórico de contagens
    historico_contagens = HistoricoContagem.objects.filter(
        item_inventario__inventario=inventario
    ).order_by('-data_contagem', 'item_inventario__item__nome')
    
    # Calcular fase atual
    max_contagem = itens_inventario.aggregate(max_contagem=models.Max('numero_contagem'))['max_contagem'] or 0
    itens_com_diferenca_nao_finalizados = itens_com_diferenca.filter(contagem_finalizada=False)
    
    if max_contagem == 0:
        fase_atual = 1  # Primeira contagem
    elif max_contagem == 1:
        if itens_com_diferenca.exists():
            fase_atual = 2  # Segunda contagem necessária
        else:
            fase_atual = 4  # Concluído após primeira contagem
    elif max_contagem == 2:
        if itens_com_diferenca_nao_finalizados.exists():
            fase_atual = 3  # Terceira contagem necessária
        else:
            fase_atual = 4  # Concluído após segunda contagem
    elif max_contagem >= 3:
        fase_atual = 4  # Concluído após terceira contagem
    
    # Estatísticas de contagem
    contagem_stats = {
        'fase_atual': fase_atual,
        'itens_com_diferenca': itens_com_diferenca.count(),
        'itens_conformes': itens_inventario.filter(diferenca=0).count(),
    }
    
    context = {
        'inventario': inventario,
        'itens_inventario': itens_inventario,
        'total_itens': total_itens,
        'itens_contados': itens_contados,
        'itens_com_diferenca': itens_com_diferenca,
        'aumentos': aumentos,
        'diminuicoes': diminuicoes,
        'ajustes': ajustes,
        'historico_contagens': historico_contagens,
        'contagem_stats': contagem_stats,
    }
    
    return render(request, 'stock/inventario/relatorio.html', context)


@login_required
@require_stock_access
@require_http_methods(["POST"])
def inventario_submeter_contagem(request, id):
    """Submeter contagem de todos os itens e verificar diferenças"""
    inventario = get_object_or_404(InventarioFisico, id=id)
    
    if inventario.status not in ['PLANEJADO', 'EM_ANDAMENTO']:
        messages.error(request, 'Não é possível editar inventários concluídos ou cancelados.')
        return redirect('stock:inventario:detail', id=inventario.id)
    
    try:
        itens_inventario = inventario.itens_inventario.all()
        itens_com_dados = []
        itens_sem_dados = []
        
        # Processar cada item
        for item_inv in itens_inventario:
            quantidade_key = f'quantidade_{item_inv.id}'
            quantidade_contada = request.POST.get(quantidade_key, '').strip()
            
            if quantidade_contada:
                try:
                    quantidade = int(quantidade_contada)
                    if quantidade < 0:
                        messages.error(request, f'Quantidade não pode ser negativa para {item_inv.item.nome}.')
                        continue
                    
                    # Incrementar número da contagem
                    item_inv.numero_contagem += 1
                    
                    # Atualizar dados da contagem atual
                    item_inv.quantidade_contada = quantidade
                    item_inv.data_contagem = timezone.now()
                    item_inv.usuario_contador = request.user
                    
                    # Calcular diferença
                    diferenca = quantidade - item_inv.quantidade_sistema
                    item_inv.diferenca = diferenca
                    
                    # Marcar como finalizado se atingiu 3 contagens
                    if item_inv.numero_contagem >= 3:
                        item_inv.contagem_finalizada = True
                        item_inv.precisa_recontagem = False
                    else:
                        item_inv.contagem_finalizada = False
                        # Verificar se precisa recontagem (se há diferença e ainda não atingiu 3 contagens)
                        if diferenca != 0:
                            item_inv.precisa_recontagem = True
                        else:
                            item_inv.precisa_recontagem = False
                    
                    # Salvar item do inventário
                    item_inv.save()
                    
                    # Criar registro no histórico de contagens
                    from .models_stock import HistoricoContagem
                    HistoricoContagem.objects.create(
                        item_inventario=item_inv,
                        numero_contagem=item_inv.numero_contagem,
                        quantidade_contada=quantidade,
                        diferenca=diferenca,
                        data_contagem=timezone.now(),
                        usuario_contador=request.user
                    )
                    
                    itens_com_dados.append(item_inv)
                    
                except ValueError:
                    messages.error(request, f'Quantidade inválida para {item_inv.item.nome}.')
            else:
                itens_sem_dados.append(item_inv)
        
        # Atualizar status do inventário para "Em Andamento"
        if inventario.status == 'PLANEJADO':
            inventario.status = 'EM_ANDAMENTO'
            inventario.save()
        
        # Verificar se há diferenças
        itens_com_diferenca = [item for item in itens_com_dados if item.diferenca != 0]
        itens_sem_diferenca = [item for item in itens_com_dados if item.diferenca == 0]
        
        if itens_sem_dados:
            messages.warning(request, f'{len(itens_sem_dados)} item(s) não foram contados.')
        
        # Verificar se todos os itens atingiram 3 contagens
        todos_itens_finalizados = all(item.numero_contagem >= 3 for item in itens_com_dados)
        
        if todos_itens_finalizados:
            # Todos os itens atingiram 3 contagens - verificar se há diferenças
            if itens_com_diferenca:
                # Há diferenças na última contagem - perguntar sobre ajuste de stock
                return JsonResponse({
                    'status': 'success',
                    'message': f'Todas as 3 contagens foram realizadas!',
                    'action': 'ask_stock_adjustment',
                    'items_with_differences': len(itens_com_diferenca),
                    'inventario_id': inventario.id
                })
            else:
                # Não há diferenças - finalizar diretamente
                inventario.status = 'CONCLUIDO'
                inventario.data_fim = timezone.now()
                inventario.save()
                
                messages.success(request, f'Inventário finalizado! Todas as 3 contagens foram realizadas.')
        elif itens_com_diferenca:
            # Há diferenças - marcar para recontagem
            for item in itens_com_diferenca:
                if item.numero_contagem < 3:
                    item.precisa_recontagem = True
                    item.save()
            
            messages.warning(request, f'Contagem submetida! {len(itens_com_diferenca)} item(s) com diferenças serão recontados.')
        else:
            # Não há diferenças - pode finalizar
            inventario.status = 'CONCLUIDO'
            inventario.data_fim = timezone.now()
            inventario.save()
            
            messages.success(request, f'Inventário finalizado! Todos os {len(itens_sem_diferenca)} item(s) estão conforme o sistema.')
        
    except Exception as e:
        messages.error(request, f'Erro ao submeter contagem: {str(e)}')
    
    return redirect('stock:inventario:detail', id=inventario.id)


@login_required
@require_stock_access
def inventario_imprimir_contagem(request, id, numero_contagem):
    """Imprimir documento de contagem para contagem manual"""
    inventario = get_object_or_404(InventarioFisico, id=id)
    
    if inventario.status not in ['PLANEJADO', 'EM_ANDAMENTO']:
        messages.error(request, 'Não é possível imprimir documentos de inventários concluídos ou cancelados.')
        return redirect('stock:inventario:detail', id=inventario.id)
    
    # Validar número da contagem
    if numero_contagem not in [1, 2, 3]:
        messages.error(request, 'Número de contagem inválido.')
        return redirect('stock:inventario:detail', id=inventario.id)
    
    # Obter itens baseado na fase da contagem
    itens_inventario = inventario.itens_inventario.all()
    
    if numero_contagem == 1:
        # Primeira contagem - todos os itens
        itens_para_contagem = itens_inventario
        titulo_contagem = "1ª CONTAGEM - CONTAGEM INICIAL"
    elif numero_contagem == 2:
        # Segunda contagem - apenas itens com diferenças da primeira contagem
        itens_com_diferenca = itens_inventario.exclude(diferenca=0)
        itens_para_contagem = itens_com_diferenca.filter(numero_contagem__lt=3, contagem_finalizada=False)
        titulo_contagem = "2ª CONTAGEM - RECONTAGEM DE ITENS COM DIFERENÇAS"
    else:  # numero_contagem == 3
        # Terceira contagem - apenas itens com diferenças que ainda podem ser recontados
        itens_com_diferenca = itens_inventario.exclude(diferenca=0)
        itens_para_contagem = itens_com_diferenca.filter(numero_contagem__lt=3, contagem_finalizada=False)
        titulo_contagem = "3ª CONTAGEM - CONTAGEM FINAL OBRIGATÓRIA"
    
    # Se não há itens para esta contagem, mostrar mensagem
    if not itens_para_contagem.exists():
        messages.info(request, f'Não há itens para a {numero_contagem}ª contagem.')
        return redirect('stock:inventario:detail', id=inventario.id)
    
    # Preparar dados para o template
    context = {
        'inventario': inventario,
        'itens_contagem': itens_para_contagem,
        'numero_contagem': numero_contagem,
        'titulo_contagem': titulo_contagem,
        'data_impressao': timezone.now(),
        'usuario_impressao': request.user,
    }
    
    # Renderizar template de impressão
    html_content = render_to_string('stock/inventario/print_contagem.html', context)
    
    # Criar resposta HTTP com conteúdo HTML
    response = HttpResponse(html_content, content_type='text/html; charset=utf-8')
    response['Content-Disposition'] = f'inline; filename="contagem_{numero_contagem}_{inventario.codigo}.html"'
    
    return response


@login_required
@require_stock_access
@require_http_methods(["POST"])
def inventario_finalizar_com_ajuste(request, id):
    """Finalizar inventário com ajuste de stock"""
    inventario = get_object_or_404(InventarioFisico, id=id)
    
    if inventario.status not in ['PLANEJADO', 'EM_ANDAMENTO']:
        messages.error(request, 'Não é possível editar inventários concluídos ou cancelados.')
        return redirect('stock:inventario:detail', id=inventario.id)
    
    try:
        ajustar_stock = request.POST.get('ajustar_stock') == 'true'
        
        # Finalizar inventário
        inventario.status = 'CONCLUIDO'
        inventario.data_fim = timezone.now()
        inventario.save()
        
        if ajustar_stock:
            # Ajustar stock para todos os itens com diferenças
            itens_com_diferenca = inventario.itens_inventario.filter(diferenca__ne=0)
            
            for item_inv in itens_com_diferenca:
                # Criar ajuste de inventário
                AjusteInventario.objects.create(
                    inventario=inventario,
                    item=item_inv.item,
                    sucursal=inventario.sucursal,
                    quantidade_anterior=item_inv.quantidade_sistema,
                    quantidade_nova=item_inv.quantidade_contada,
                    diferenca=item_inv.diferenca,
                    observacoes=f'Ajuste automático após inventário {inventario.codigo}',
                    usuario_responsavel=request.user
                )
                
                # Atualizar stock
                stock_item, created = StockItem.objects.get_or_create(
                    item=item_inv.item,
                    sucursal=inventario.sucursal,
                    defaults={'quantidade': 0}
                )
                
                stock_item.quantidade = item_inv.quantidade_contada
                stock_item.save()
                
                # Criar movimento de stock
                MovimentoItem.objects.create(
                    item=item_inv.item,
                    sucursal=inventario.sucursal,
                    tipo_movimento=TipoMovimentoStock.objects.get(codigo='AJUSTE_INVENTARIO'),
                    quantidade=item_inv.diferenca,
                    quantidade_anterior=item_inv.quantidade_sistema,
                    quantidade_final=item_inv.quantidade_contada,
                    observacoes=f'Ajuste automático após inventário {inventario.codigo}',
                    usuario_responsavel=request.user,
                    data_movimento=timezone.now()
                )
            
            messages.success(request, f'Inventário finalizado! Stock ajustado para {itens_com_diferenca.count()} item(s) com diferenças.')
        else:
            messages.success(request, f'Inventário finalizado! Stock mantido conforme sistema.')
        
    except Exception as e:
        messages.error(request, f'Erro ao finalizar inventário: {str(e)}')
    
    return redirect('stock:inventario:detail', id=inventario.id)
