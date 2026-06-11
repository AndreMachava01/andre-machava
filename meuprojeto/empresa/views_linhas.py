"""
Views para gestão de linhas de produção
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django.utils import timezone
import logging

from .models_stock import LinhaProducao, Maquina, ProcessoProducao
from .models_base import Sucursal
from django.contrib.auth.models import User

logger = logging.getLogger(__name__)


@login_required
def producao_linhas(request):
    """Lista de linhas de produção com filtros e paginação"""
    try:
        # Parâmetros de busca e filtro
        search_query = request.GET.get('q', '').strip()
        status = request.GET.get('status')
        tipo = request.GET.get('tipo')
        sucursal_id = request.GET.get('sucursal')
        
        # Query base com otimizações
        linhas = LinhaProducao.objects.select_related(
            'sucursal', 'criado_por', 'responsavel'
        ).prefetch_related('maquinas', 'processos').all()
        
        # Aplicar filtros
        if search_query:
            linhas = linhas.filter(
                Q(codigo__icontains=search_query) |
                Q(nome__icontains=search_query) |
                Q(descricao__icontains=search_query) |
                Q(localizacao__icontains=search_query)
            )
        
        if status:
            linhas = linhas.filter(status=status)
        
        if tipo:
            linhas = linhas.filter(tipo=tipo)
        
        if sucursal_id:
            linhas = linhas.filter(sucursal_id=sucursal_id)
        
        # Ordenação
        linhas = linhas.order_by('-data_criacao')
        
        # Paginação
        paginator = Paginator(linhas, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Estatísticas
        total_linhas = LinhaProducao.objects.count()
        linhas_ativas = LinhaProducao.objects.filter(status='ATIVA').count()
        linhas_inativas = LinhaProducao.objects.filter(status='INATIVA').count()
        linhas_manutencao = LinhaProducao.objects.filter(status='MANUTENCAO').count()
        
        # Sucursais para filtro
        sucursais = Sucursal.objects.all().order_by('nome')
        
        context = {
            'page_obj': page_obj,
            'search_query': search_query,
            'status_filter': status,
            'tipo_filter': tipo,
            'sucursal_filter': sucursal_id,
            'total_linhas': total_linhas,
            'linhas_ativas': linhas_ativas,
            'linhas_inativas': linhas_inativas,
            'linhas_manutencao': linhas_manutencao,
            'sucursais': sucursais,
            'status_choices': LinhaProducao.STATUS_CHOICES,
            'tipo_choices': LinhaProducao.TIPO_CHOICES,
        }
        
        return render(request, 'producao/linhas/main.html', context)
    except Exception as e:
        logger.error(f"Erro ao carregar lista de linhas: {e}", exc_info=True)
        messages.error(request, 'Erro ao carregar lista de linhas.')
        context = {
            'page_obj': None,
            'search_query': '',
            'status_filter': None,
            'tipo_filter': None,
            'sucursal_filter': None,
            'total_linhas': 0,
            'linhas_ativas': 0,
            'linhas_inativas': 0,
            'linhas_manutencao': 0,
            'sucursais': Sucursal.objects.all().order_by('nome'),
            'status_choices': LinhaProducao.STATUS_CHOICES,
            'tipo_choices': LinhaProducao.TIPO_CHOICES,
            'error_message': str(e),
        }
        return render(request, 'producao/linhas/main.html', context)


@login_required
def producao_linha_add(request):
    """Adicionar nova linha de produção"""
    if request.method == 'POST':
        try:
            with transaction.atomic():
                nome = request.POST.get('nome', '').strip()
                tipo = request.POST.get('tipo', 'LINHA')
                descricao = request.POST.get('descricao', '').strip()
                status = request.POST.get('status', 'ATIVA')
                sucursal_id = request.POST.get('sucursal')
                localizacao = request.POST.get('localizacao', '').strip()
                capacidade_horaria = request.POST.get('capacidade_horaria', '').strip()
                responsavel_id = request.POST.get('responsavel', '').strip() or None
                observacoes = request.POST.get('observacoes', '').strip()
                
                if not nome:
                    messages.error(request, 'O nome da linha é obrigatório.')
                    return redirect('producao:linha_add')
                
                if not sucursal_id:
                    messages.error(request, 'A sucursal é obrigatória.')
                    return redirect('producao:linha_add')
                
                # Converter capacidade
                capacidade_decimal = None
                if capacidade_horaria:
                    try:
                        from decimal import Decimal, InvalidOperation
                        capacidade_decimal = Decimal(capacidade_horaria)
                    except (ValueError, InvalidOperation):
                        pass
                
                linha = LinhaProducao.objects.create(
                    nome=nome,
                    tipo=tipo,
                    descricao=descricao,
                    status=status,
                    sucursal_id=sucursal_id,
                    localizacao=localizacao,
                    capacidade_horaria=capacidade_decimal,
                    responsavel_id=responsavel_id,
                    observacoes=observacoes,
                    criado_por=request.user
                )
                
                # Processar máquinas (ManyToMany)
                maquinas_str = request.POST.get('maquinas', '').strip()
                if maquinas_str:
                    maquinas_ids = [int(id) for id in maquinas_str.split(',') if id.strip()]
                    if maquinas_ids:
                        maquinas = Maquina.objects.filter(id__in=maquinas_ids)
                        linha.maquinas.set(maquinas)
                
                # Processar processos (ManyToMany)
                processos_str = request.POST.get('processos', '').strip()
                if processos_str:
                    processos_ids = [int(id) for id in processos_str.split(',') if id.strip()]
                    if processos_ids:
                        processos = ProcessoProducao.objects.filter(id__in=processos_ids)
                        linha.processos.set(processos)
                
                messages.success(request, f'Linha de produção {linha.codigo} cadastrada com sucesso.')
                return redirect('producao:linha_detail', id=linha.id)
        except Exception as e:
            logger.error(f"Erro ao adicionar linha: {e}", exc_info=True)
            messages.error(request, f'Erro ao cadastrar linha: {str(e)}')
    
    # GET - exibir formulário
    sucursais = Sucursal.objects.all().order_by('nome')
    maquinas = Maquina.objects.filter(status__in=['DISPONIVEL', 'EM_USO']).order_by('nome')
    processos = ProcessoProducao.objects.filter(status__in=['ATIVO', 'APROVADO']).order_by('nome')
    usuarios = User.objects.filter(is_active=True).order_by('username')
    
    context = {
        'linha': None,
        'sucursais': sucursais,
        'maquinas': maquinas,
        'processos': processos,
        'usuarios': usuarios,
        'status_choices': LinhaProducao.STATUS_CHOICES,
        'tipo_choices': LinhaProducao.TIPO_CHOICES,
    }
    return render(request, 'producao/linhas/form.html', context)


@login_required
def producao_linha_edit(request, id):
    """Editar linha de produção existente"""
    linha = get_object_or_404(LinhaProducao, id=id)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                linha.nome = request.POST.get('nome', '').strip()
                linha.tipo = request.POST.get('tipo', 'LINHA')
                linha.descricao = request.POST.get('descricao', '').strip()
                linha.status = request.POST.get('status', 'ATIVA')
                sucursal_id = request.POST.get('sucursal')
                linha.localizacao = request.POST.get('localizacao', '').strip()
                capacidade_horaria = request.POST.get('capacidade_horaria', '').strip()
                responsavel_id = request.POST.get('responsavel', '').strip() or None
                linha.observacoes = request.POST.get('observacoes', '').strip()
                
                if not linha.nome:
                    messages.error(request, 'O nome da linha é obrigatório.')
                    return redirect('producao:linha_edit', id=id)
                
                if not sucursal_id:
                    messages.error(request, 'A sucursal é obrigatória.')
                    return redirect('producao:linha_edit', id=id)
                
                linha.sucursal_id = sucursal_id
                linha.responsavel_id = responsavel_id
                
                # Converter capacidade
                if capacidade_horaria:
                    try:
                        from decimal import Decimal, InvalidOperation
                        linha.capacidade_horaria = Decimal(capacidade_horaria)
                    except (ValueError, InvalidOperation):
                        pass
                else:
                    linha.capacidade_horaria = None
                
                linha.save()
                
                # Processar máquinas (ManyToMany)
                maquinas_str = request.POST.get('maquinas', '').strip()
                if maquinas_str:
                    maquinas_ids = [int(id) for id in maquinas_str.split(',') if id.strip()]
                    if maquinas_ids:
                        maquinas = Maquina.objects.filter(id__in=maquinas_ids)
                        linha.maquinas.set(maquinas)
                    else:
                        linha.maquinas.clear()
                else:
                    linha.maquinas.clear()
                
                # Processar processos (ManyToMany)
                processos_str = request.POST.get('processos', '').strip()
                if processos_str:
                    processos_ids = [int(id) for id in processos_str.split(',') if id.strip()]
                    if processos_ids:
                        processos = ProcessoProducao.objects.filter(id__in=processos_ids)
                        linha.processos.set(processos)
                    else:
                        linha.processos.clear()
                else:
                    linha.processos.clear()
                
                messages.success(request, f'Linha de produção {linha.codigo} atualizada com sucesso.')
                return redirect('producao:linha_detail', id=linha.id)
        except Exception as e:
            logger.error(f"Erro ao editar linha {id}: {e}", exc_info=True)
            messages.error(request, f'Erro ao atualizar linha: {str(e)}')
    
    # GET - exibir formulário
    sucursais = Sucursal.objects.all().order_by('nome')
    maquinas = Maquina.objects.filter(status__in=['DISPONIVEL', 'EM_USO']).order_by('nome')
    processos = ProcessoProducao.objects.filter(status__in=['ATIVO', 'APROVADO']).order_by('nome')
    usuarios = User.objects.filter(is_active=True).order_by('username')
    
    context = {
        'linha': linha,
        'sucursais': sucursais,
        'maquinas': maquinas,
        'processos': processos,
        'usuarios': usuarios,
        'status_choices': LinhaProducao.STATUS_CHOICES,
        'tipo_choices': LinhaProducao.TIPO_CHOICES,
    }
    return render(request, 'producao/linhas/form.html', context)


@login_required
def producao_linha_detail(request, id):
    """Detalhes da linha de produção"""
    try:
        linha = get_object_or_404(
            LinhaProducao.objects.select_related('sucursal', 'criado_por', 'responsavel')
            .prefetch_related('maquinas', 'processos'),
            id=id
        )
        
        context = {
            'linha': linha,
        }
        
        return render(request, 'producao/linhas/detail.html', context)
    except Exception as e:
        logger.error(f"Erro ao exibir detalhes da linha {id}: {e}", exc_info=True)
        messages.error(request, 'Erro ao carregar detalhes da linha.')
        return redirect('producao:linhas')


@login_required
@require_http_methods(["POST"])
def producao_linha_delete(request, id):
    """Deletar linha de produção"""
    linha = get_object_or_404(LinhaProducao, id=id)
    
    try:
        codigo_linha = linha.codigo
        linha.delete()
        messages.success(request, f'Linha de produção {codigo_linha} deletada com sucesso.')
    except Exception as e:
        logger.error(f"Erro ao deletar linha {id}: {e}", exc_info=True)
        messages.error(request, f'Erro ao deletar linha: {str(e)}')
    
    return redirect('producao:linhas')

