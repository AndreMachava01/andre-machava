"""
Views para gestão de máquinas e equipamentos de produção
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.views.decorators.http import require_http_methods
from django.db import transaction
from decimal import Decimal, InvalidOperation
from django.utils import timezone
from datetime import datetime
import logging

from .models_stock import Maquina
from .models_base import Sucursal

logger = logging.getLogger(__name__)


@login_required
def producao_maquinas(request):
    """Lista de máquinas e equipamentos com filtros e paginação"""
    try:
        # Parâmetros de busca e filtro
        search_query = request.GET.get('q', '').strip()
        status = request.GET.get('status')
        tipo = request.GET.get('tipo')
        sucursal_id = request.GET.get('sucursal')
        
        # Query base com otimizações
        maquinas = Maquina.objects.select_related(
            'sucursal', 'criado_por'
        ).all()
        
        # Aplicar filtros
        if search_query:
            maquinas = maquinas.filter(
                Q(codigo__icontains=search_query) |
                Q(nome__icontains=search_query) |
                Q(descricao__icontains=search_query) |
                Q(marca__icontains=search_query) |
                Q(modelo__icontains=search_query) |
                Q(numero_serie__icontains=search_query) |
                Q(localizacao__icontains=search_query)
            )
        
        if status:
            maquinas = maquinas.filter(status=status)
        
        if tipo:
            maquinas = maquinas.filter(tipo=tipo)
        
        if sucursal_id:
            maquinas = maquinas.filter(sucursal_id=sucursal_id)
        
        # Ordenação
        maquinas = maquinas.order_by('-data_criacao')
        
        # Paginação
        paginator = Paginator(maquinas, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Estatísticas
        total_maquinas = Maquina.objects.count()
        maquinas_disponiveis = Maquina.objects.filter(status='DISPONIVEL').count()
        maquinas_em_uso = Maquina.objects.filter(status='EM_USO').count()
        maquinas_manutencao = Maquina.objects.filter(status='MANUTENCAO').count()
        
        # Sucursais para filtro
        sucursais = Sucursal.objects.all().order_by('nome')
        
        context = {
            'page_obj': page_obj,
            'search_query': search_query,
            'status_filter': status,
            'tipo_filter': tipo,
            'sucursal_filter': sucursal_id,
            'total_maquinas': total_maquinas,
            'maquinas_disponiveis': maquinas_disponiveis,
            'maquinas_em_uso': maquinas_em_uso,
            'maquinas_manutencao': maquinas_manutencao,
            'sucursais': sucursais,
            'status_choices': Maquina.STATUS_CHOICES,
            'tipo_choices': Maquina.TIPO_CHOICES,
        }
        
        return render(request, 'producao/maquinas/main.html', context)
    except Exception as e:
        logger.error(f"Erro ao carregar lista de máquinas: {e}", exc_info=True)
        messages.error(request, 'Erro ao carregar lista de máquinas.')
        context = {
            'page_obj': None,
            'search_query': '',
            'status_filter': None,
            'tipo_filter': None,
            'sucursal_filter': None,
            'total_maquinas': 0,
            'maquinas_disponiveis': 0,
            'maquinas_em_uso': 0,
            'maquinas_manutencao': 0,
            'sucursais': Sucursal.objects.all().order_by('nome'),
            'status_choices': Maquina.STATUS_CHOICES,
            'tipo_choices': Maquina.TIPO_CHOICES,
            'error_message': str(e),
        }
        return render(request, 'producao/maquinas/main.html', context)


@login_required
def producao_maquina_add(request):
    """Adicionar nova máquina"""
    if request.method == 'POST':
        try:
            with transaction.atomic():
                nome = request.POST.get('nome', '').strip()
                tipo = request.POST.get('tipo', 'MAQUINA')
                descricao = request.POST.get('descricao', '').strip()
                marca = request.POST.get('marca', '').strip()
                modelo = request.POST.get('modelo', '').strip()
                numero_serie = request.POST.get('numero_serie', '').strip()
                capacidade = request.POST.get('capacidade', '').strip()
                unidade_capacidade = request.POST.get('unidade_capacidade', '').strip()
                status = request.POST.get('status', 'DISPONIVEL')
                sucursal_id = request.POST.get('sucursal')
                localizacao = request.POST.get('localizacao', '').strip()
                data_aquisicao = request.POST.get('data_aquisicao', '').strip() or None
                data_proxima_manutencao = request.POST.get('data_proxima_manutencao', '').strip() or None
                observacoes = request.POST.get('observacoes', '').strip()
                
                if not nome:
                    messages.error(request, 'O nome da máquina é obrigatório.')
                    return redirect('producao:maquina_add')
                
                if not sucursal_id:
                    messages.error(request, 'A sucursal é obrigatória.')
                    return redirect('producao:maquina_add')
                
                # Converter datas
                data_aquisicao_obj = None
                if data_aquisicao:
                    try:
                        data_aquisicao_obj = datetime.strptime(data_aquisicao, '%Y-%m-%d').date()
                    except ValueError:
                        pass
                
                data_proxima_manutencao_obj = None
                if data_proxima_manutencao:
                    try:
                        data_proxima_manutencao_obj = datetime.strptime(data_proxima_manutencao, '%Y-%m-%d').date()
                    except ValueError:
                        pass
                
                # Converter capacidade
                capacidade_decimal = None
                if capacidade:
                    try:
                        capacidade_decimal = Decimal(capacidade)
                    except (ValueError, InvalidOperation):
                        pass
                
                maquina = Maquina.objects.create(
                    nome=nome,
                    tipo=tipo,
                    descricao=descricao,
                    marca=marca,
                    modelo=modelo,
                    numero_serie=numero_serie,
                    capacidade=capacidade_decimal,
                    unidade_capacidade=unidade_capacidade if unidade_capacidade else '',
                    status=status,
                    sucursal_id=sucursal_id,
                    localizacao=localizacao,
                    data_aquisicao=data_aquisicao_obj,
                    data_proxima_manutencao=data_proxima_manutencao_obj,
                    observacoes=observacoes,
                    criado_por=request.user
                )
                
                messages.success(request, f'Máquina {maquina.codigo} cadastrada com sucesso.')
                return redirect('producao:maquina_detail', id=maquina.id)
        except Exception as e:
            logger.error(f"Erro ao adicionar máquina: {e}", exc_info=True)
            messages.error(request, f'Erro ao cadastrar máquina: {str(e)}')
    
    # GET - exibir formulário
    sucursais = Sucursal.objects.all().order_by('nome')
    context = {
        'maquina': None,
        'sucursais': sucursais,
        'status_choices': Maquina.STATUS_CHOICES,
        'tipo_choices': Maquina.TIPO_CHOICES,
        'unidade_capacidade_choices': Maquina.UNIDADE_CAPACIDADE_CHOICES,
    }
    return render(request, 'producao/maquinas/form.html', context)


@login_required
def producao_maquina_edit(request, id):
    """Editar máquina existente"""
    maquina = get_object_or_404(Maquina, id=id)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                maquina.nome = request.POST.get('nome', '').strip()
                maquina.tipo = request.POST.get('tipo', 'MAQUINA')
                maquina.descricao = request.POST.get('descricao', '').strip()
                maquina.marca = request.POST.get('marca', '').strip()
                maquina.modelo = request.POST.get('modelo', '').strip()
                maquina.numero_serie = request.POST.get('numero_serie', '').strip()
                capacidade = request.POST.get('capacidade', '').strip()
                maquina.unidade_capacidade = request.POST.get('unidade_capacidade', '').strip()
                maquina.status = request.POST.get('status', 'DISPONIVEL')
                sucursal_id = request.POST.get('sucursal')
                maquina.localizacao = request.POST.get('localizacao', '').strip()
                data_aquisicao = request.POST.get('data_aquisicao', '').strip() or None
                data_proxima_manutencao = request.POST.get('data_proxima_manutencao', '').strip() or None
                maquina.observacoes = request.POST.get('observacoes', '').strip()
                
                if not maquina.nome:
                    messages.error(request, 'O nome da máquina é obrigatório.')
                    return redirect('producao:maquina_edit', id=id)
                
                if not sucursal_id:
                    messages.error(request, 'A sucursal é obrigatória.')
                    return redirect('producao:maquina_edit', id=id)
                
                maquina.sucursal_id = sucursal_id
                
                # Converter datas
                if data_aquisicao:
                    try:
                        maquina.data_aquisicao = datetime.strptime(data_aquisicao, '%Y-%m-%d').date()
                    except ValueError:
                        pass
                else:
                    maquina.data_aquisicao = None
                
                if data_proxima_manutencao:
                    try:
                        maquina.data_proxima_manutencao = datetime.strptime(data_proxima_manutencao, '%Y-%m-%d').date()
                    except ValueError:
                        pass
                else:
                    maquina.data_proxima_manutencao = None
                
                # Converter capacidade
                if capacidade:
                    try:
                        maquina.capacidade = Decimal(capacidade)
                    except (ValueError, InvalidOperation):
                        pass
                else:
                    maquina.capacidade = None
                
                maquina.save()
                
                messages.success(request, f'Máquina {maquina.codigo} atualizada com sucesso.')
                return redirect('producao:maquina_detail', id=maquina.id)
        except Exception as e:
            logger.error(f"Erro ao editar máquina {id}: {e}", exc_info=True)
            messages.error(request, f'Erro ao atualizar máquina: {str(e)}')
    
    # GET - exibir formulário
    sucursais = Sucursal.objects.all().order_by('nome')
    context = {
        'maquina': maquina,
        'sucursais': sucursais,
        'status_choices': Maquina.STATUS_CHOICES,
        'tipo_choices': Maquina.TIPO_CHOICES,
        'unidade_capacidade_choices': Maquina.UNIDADE_CAPACIDADE_CHOICES,
    }
    return render(request, 'producao/maquinas/form.html', context)


@login_required
def producao_maquina_detail(request, id):
    """Detalhes da máquina"""
    try:
        maquina = get_object_or_404(
            Maquina.objects.select_related('sucursal', 'criado_por'),
            id=id
        )
        
        context = {
            'maquina': maquina,
        }
        
        return render(request, 'producao/maquinas/detail.html', context)
    except Exception as e:
        logger.error(f"Erro ao exibir detalhes da máquina {id}: {e}", exc_info=True)
        messages.error(request, 'Erro ao carregar detalhes da máquina.')
        return redirect('producao:maquinas')


@login_required
@require_http_methods(["POST"])
def producao_maquina_delete(request, id):
    """Deletar máquina"""
    maquina = get_object_or_404(Maquina, id=id)
    
    try:
        codigo_maquina = maquina.codigo
        maquina.delete()
        messages.success(request, f'Máquina {codigo_maquina} deletada com sucesso.')
    except Exception as e:
        logger.error(f"Erro ao deletar máquina {id}: {e}", exc_info=True)
        messages.error(request, f'Erro ao deletar máquina: {str(e)}')
    
    return redirect('producao:maquinas')

