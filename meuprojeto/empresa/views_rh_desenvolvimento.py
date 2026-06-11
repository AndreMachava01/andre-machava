"""Views RH — treinos, avaliações, promoções, transferências."""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Count, Case, When, IntegerField, Sum, Avg
from django.http import JsonResponse, HttpResponse
from django.core.exceptions import ValidationError
from django.contrib import messages
from django.utils import timezone
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
import calendar
import logging
import os
import tempfile
from urllib.parse import urlencode
from django.urls import reverse

from .models_rh import (
    Funcionario, Departamento, Cargo, Presenca, TipoPresenca, Feriado, HorasExtras,
    Salario, BeneficioSalarial, DescontoSalarial, Treinamento, AvaliacaoDesempenho,
    CriterioAvaliacao, CriterioAvaliado, FolhaSalarial, FuncionarioFolha, Promocao,
    DepartamentoSucursal, TransferenciaFuncionario, InscricaoTreinamento,
)
from .models_base import Sucursal
from .views import (
    generate_pdf_report,
    generate_pdf_from_html,
    render_pdf_from_url,
    render_pdf_from_html_string,
)

logger = logging.getLogger(__name__)


@login_required
def rh_treinamentos(request):
    """Lista de treinamentos"""
    from datetime import date, timedelta
    from django.db.models import Q
    
    # Filtros
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    tipo_filter = request.GET.get('tipo', '')
    prioridade_filter = request.GET.get('prioridade', '')
    
    # Query base
    treinamentos = Treinamento.objects.all()
    
    # Aplicar filtros
    if search_query:
        treinamentos = treinamentos.filter(
            Q(nome__icontains=search_query) |
            Q(instrutor__icontains=search_query) |
            Q(instituicao__icontains=search_query)
        )
    
    if status_filter:
        treinamentos = treinamentos.filter(status=status_filter)
    
    if tipo_filter:
        treinamentos = treinamentos.filter(tipo=tipo_filter)
    
    if prioridade_filter:
        treinamentos = treinamentos.filter(prioridade=prioridade_filter)
    
    # Ordenação
    treinamentos = treinamentos.order_by('-data_inicio')
    
    # Paginação
    paginator = Paginator(treinamentos, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    from .services.rh_service import obter_stats_treinamentos_lista

    # Choices para os filtros
    status_choices = Treinamento.STATUS_CHOICES
    tipo_choices = Treinamento.TIPO_CHOICES
    prioridade_choices = Treinamento.PRIORIDADE_CHOICES
    
    context = {
        'treinamentos': page_obj,
        'search_query': search_query,
        'status_filter': status_filter,
        'tipo_filter': tipo_filter,
        'prioridade_filter': prioridade_filter,
        'status_choices': status_choices,
        'tipo_choices': tipo_choices,
        'prioridade_choices': prioridade_choices,
        'stats': obter_stats_treinamentos_lista(),
    }
    
    return render(request, 'rh/treinamentos/main.html', context)

@login_required
def treinamento_add(request):
    """Adicionar treinamento"""
    from datetime import datetime
    from decimal import Decimal
    
    if request.method == 'POST':
        nome = request.POST.get('nome')
        descricao = request.POST.get('descricao', '')
        tipo = request.POST.get('tipo')
        status = request.POST.get('status')
        prioridade = request.POST.get('prioridade')
        data_inicio = request.POST.get('data_inicio')
        data_fim = request.POST.get('data_fim')
        capacidade_maxima = request.POST.get('capacidade_maxima')
        instrutor = request.POST.get('instrutor', '')
        instituicao = request.POST.get('instituicao', '')
        local = request.POST.get('local', '')
        observacoes = request.POST.get('observacoes', '')
        
        if not all([nome, tipo, status, prioridade, data_inicio, data_fim, capacidade_maxima]):
            messages.error(request, 'Todos os campos obrigatórios devem ser preenchidos.')
        else:
            try:
                data_limite_inscricao = request.POST.get('data_limite_inscricao')
                if data_limite_inscricao:
                    data_limite_inscricao = datetime.strptime(data_limite_inscricao, '%Y-%m-%d').date()
                
                Treinamento.objects.create(
                    nome=nome,
                    descricao=descricao,
                    tipo=tipo,
                    status=status,
                    prioridade=prioridade,
                    data_inicio=datetime.strptime(data_inicio, '%Y-%m-%d').date(),
                    data_fim=datetime.strptime(data_fim, '%Y-%m-%d').date(),
                    capacidade_maxima=int(capacidade_maxima),
                    instrutor=instrutor,
                    instituicao=instituicao,
                    local=local,
                    custo_por_participante=Decimal(request.POST.get('custo_por_participante', '0')),
                    custo_total=Decimal(request.POST.get('custo_total', '0')),
                    carga_horaria=int(request.POST.get('carga_horaria', '0')),
                    data_limite_inscricao=data_limite_inscricao,
                    objetivos=request.POST.get('objetivos', ''),
                    requisitos=request.POST.get('requisitos', ''),
                    conteudo_programatico=request.POST.get('conteudo_programatico', ''),
                    emite_certificado='emite_certificado' in request.POST,
                    ativo='ativo' in request.POST,
                    observacoes=observacoes
                )
                messages.success(request, 'Treinamento criado com sucesso!')
                return redirect('rh:treinamentos')
            except ValueError as e:
                messages.error(request, f'Erro nos dados: {str(e)}')
            except Exception as e:
                messages.error(request, f'Erro ao salvar: {str(e)}')
    
    context = {
        'status_choices': Treinamento.STATUS_CHOICES,
        'tipo_choices': Treinamento.TIPO_CHOICES,
        'prioridade_choices': Treinamento.PRIORIDADE_CHOICES,
    }
    
    return render(request, 'rh/treinamentos/form.html', context)

@login_required
def treinamento_edit(request, treinamento_id):
    """Editar treinamento"""
    from datetime import datetime
    from decimal import Decimal
    
    try:
        treinamento = Treinamento.objects.get(id=treinamento_id)
        
        if request.method == 'POST':
            nome = request.POST.get('nome')
            descricao = request.POST.get('descricao', '')
            tipo = request.POST.get('tipo')
            status = request.POST.get('status')
            prioridade = request.POST.get('prioridade')
            data_inicio = request.POST.get('data_inicio')
            data_fim = request.POST.get('data_fim')
            capacidade_maxima = request.POST.get('capacidade_maxima')
            instrutor = request.POST.get('instrutor', '')
            instituicao = request.POST.get('instituicao', '')
            local = request.POST.get('local', '')
            observacoes = request.POST.get('observacoes', '')
            
            if not all([nome, tipo, status, prioridade, data_inicio, data_fim, capacidade_maxima]):
                messages.error(request, 'Todos os campos obrigatórios devem ser preenchidos.')
            else:
                try:
                    treinamento.nome = nome
                    treinamento.descricao = descricao
                    treinamento.tipo = tipo
                    treinamento.status = status
                    treinamento.prioridade = prioridade
                    treinamento.data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
                    treinamento.data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
                    treinamento.capacidade_maxima = int(capacidade_maxima)
                    treinamento.instrutor = instrutor
                    treinamento.instituicao = instituicao
                    treinamento.local = local
                    treinamento.custo_por_participante = Decimal(request.POST.get('custo_por_participante', '0'))
                    treinamento.custo_total = Decimal(request.POST.get('custo_total', '0'))
                    treinamento.carga_horaria = int(request.POST.get('carga_horaria', '0'))
                    treinamento.data_limite_inscricao = request.POST.get('data_limite_inscricao') or None
                    if treinamento.data_limite_inscricao:
                        treinamento.data_limite_inscricao = datetime.strptime(treinamento.data_limite_inscricao, '%Y-%m-%d').date()
                    treinamento.objetivos = request.POST.get('objetivos', '')
                    treinamento.requisitos = request.POST.get('requisitos', '')
                    treinamento.conteudo_programatico = request.POST.get('conteudo_programatico', '')
                    treinamento.emite_certificado = 'emite_certificado' in request.POST
                    treinamento.ativo = 'ativo' in request.POST
                    treinamento.observacoes = observacoes
                    treinamento.save()
                    
                    messages.success(request, 'Treinamento atualizado com sucesso!')
                    return redirect('rh:treinamentos')
                except ValueError as e:
                    messages.error(request, f'Erro nos dados: {str(e)}')
                except Exception as e:
                    messages.error(request, f'Erro ao salvar: {str(e)}')
        
        context = {
            'treinamento': treinamento,
            'status_choices': Treinamento.STATUS_CHOICES,
            'tipo_choices': Treinamento.TIPO_CHOICES,
            'prioridade_choices': Treinamento.PRIORIDADE_CHOICES,
        }
        
        return render(request, 'rh/treinamentos/form.html', context)
        
    except Treinamento.DoesNotExist:
        messages.error(request, 'Treinamento não encontrado.')
        return redirect('rh:treinamentos')

@login_required
def treinamento_detail(request, treinamento_id):
    """Detalhes do treinamento"""
    try:
        treinamento = Treinamento.objects.get(id=treinamento_id)
        
        # Buscar inscrições (se existir o modelo)
        inscricoes = []
        try:
            from meuprojeto.empresa.models_rh import InscricaoTreinamento
            inscricoes = InscricaoTreinamento.objects.filter(treinamento=treinamento)
        except:
            pass
        
        context = {
            'treinamento': treinamento,
            'inscricoes': inscricoes,
        }
        
        return render(request, 'rh/treinamentos/detail.html', context)
        
    except Treinamento.DoesNotExist:
        messages.error(request, 'Treinamento não encontrado.')
        return redirect('rh:treinamentos')

@login_required
def treinamento_delete(request, treinamento_id):
    """Deletar treinamento"""
    try:
        treinamento = Treinamento.objects.get(id=treinamento_id)
        
        if request.method == 'POST':
            try:
                treinamento.delete()
                messages.success(request, 'Treinamento deletado com sucesso!')
                return redirect('rh:treinamentos')
            except Exception as e:
                messages.error(request, f'Erro ao deletar treinamento: {str(e)}')
        
        context = {'treinamento': treinamento}
        return render(request, 'rh/treinamentos/delete.html', context)
        
    except Treinamento.DoesNotExist:
        messages.error(request, 'Treinamento não encontrado.')
        return redirect('rh:treinamentos')

@login_required
def treinamento_inscrever(request, treinamento_id):
    """Inscrever funcionário em treinamento"""
    try:
        treinamento = Treinamento.objects.get(id=treinamento_id)
        
        if request.method == 'POST':
            funcionario_id = request.POST.get('funcionario')
            observacoes = request.POST.get('observacoes', '')
            
            if not funcionario_id:
                messages.error(request, 'Funcionário é obrigatório.')
            else:
                try:
                    # Verificar se já existe inscrição
                    from meuprojeto.empresa.models_rh import InscricaoTreinamento
                    if InscricaoTreinamento.objects.filter(treinamento=treinamento, funcionario_id=funcionario_id).exists():
                        messages.error(request, 'Funcionário já está inscrito neste treinamento.')
                    else:
                        InscricaoTreinamento.objects.create(
                            treinamento=treinamento,
                            funcionario_id=funcionario_id,
                            observacoes=observacoes,
                            status='PENDENTE'
                        )
                        messages.success(request, 'Inscrição realizada com sucesso!')
                        return redirect('rh:treinamento_inscricoes', treinamento_id=treinamento_id)
                except Exception as e:
                    messages.error(request, f'Erro ao inscrever: {str(e)}')
        
        # Filtros
        search_query = request.GET.get('search', '')
        departamento_filter = request.GET.get('departamento', '')
        
        funcionarios = Funcionario.objects.filter(status='AT')
        
        # Aplicar filtros
        if search_query:
            funcionarios = funcionarios.filter(
                Q(nome_completo__icontains=search_query) |
                Q(cargo__nome__icontains=search_query)
            )
        
        if departamento_filter:
            funcionarios = funcionarios.filter(cargo__departamento_id=departamento_filter)
        
        # Excluir funcionários já inscritos
        try:
            from meuprojeto.empresa.models_rh import InscricaoTreinamento
            funcionarios_inscritos = InscricaoTreinamento.objects.filter(
                treinamento=treinamento
            ).values_list('funcionario_id', flat=True)
            funcionarios = funcionarios.exclude(id__in=funcionarios_inscritos)
        except:
            pass
        
        funcionarios = funcionarios.order_by('nome_completo')
        
        # Obter departamentos para o dropdown
        from meuprojeto.empresa.models import Departamento
        departamentos = Departamento.objects.filter(ativo=True).order_by('nome')
        
        context = {
            'treinamento': treinamento,
            'funcionarios': funcionarios,
            'search_query': search_query,
            'departamento_filter': departamento_filter,
            'departamentos': departamentos,
        }
        return render(request, 'rh/treinamentos/inscrever.html', context)
        
    except Treinamento.DoesNotExist:
        messages.error(request, 'Treinamento não encontrado.')
        return redirect('rh:treinamentos')

@login_required
def treinamento_inscricoes(request, treinamento_id):
    """Lista de inscrições do treinamento"""
    try:
        treinamento = Treinamento.objects.get(id=treinamento_id)
        
        # Buscar inscrições (se existir o modelo)
        inscricoes = []
        status_choices = []
        try:
            from meuprojeto.empresa.models_rh import InscricaoTreinamento
            inscricoes = InscricaoTreinamento.objects.filter(treinamento=treinamento).order_by('-data_inscricao')
            status_choices = InscricaoTreinamento.STATUS_CHOICES
        except:
            pass
        
        # Filtros
        search_query = request.GET.get('search', '')
        status_filter = request.GET.get('status', '')
        
        # Aplicar filtros
        if search_query:
            inscricoes = inscricoes.filter(
                Q(funcionario__nome_completo__icontains=search_query) |
                Q(funcionario__cargo__nome__icontains=search_query)
            )
        
        if status_filter:
            inscricoes = inscricoes.filter(status=status_filter)
        
        # Calcular estatísticas
        total_inscricoes = inscricoes.count()
        confirmadas = inscricoes.filter(status='CONFIRMADA').count()
        pendentes = inscricoes.filter(status='PENDENTE').count()
        canceladas = inscricoes.filter(status='CANCELADA').count()
        concluidas = inscricoes.filter(status='CONCLUIDA').count()
        
        context = {
            'treinamento': treinamento,
            'inscricoes': inscricoes,
            'search_query': search_query,
            'status_filter': status_filter,
            'status_choices': status_choices,
            'total_inscricoes': total_inscricoes,
            'confirmadas': confirmadas,
            'pendentes': pendentes,
            'canceladas': canceladas,
            'concluidas': concluidas,
        }
        return render(request, 'rh/treinamentos/inscricoes.html', context)
        
    except Treinamento.DoesNotExist:
        messages.error(request, 'Treinamento não encontrado.')
        return redirect('rh:treinamentos')

@login_required
def inscricao_alterar_status(request, inscricao_id):
    """Alterar status da inscrição"""
    try:
        from meuprojeto.empresa.models_rh import InscricaoTreinamento
        inscricao = InscricaoTreinamento.objects.get(id=inscricao_id)
        
        if request.method == 'POST':
            status = request.POST.get('status')
            observacoes = request.POST.get('observacoes', '')
            
            if status:
                inscricao.status = status
                if observacoes:
                    inscricao.observacoes = observacoes
                inscricao.save()
                messages.success(request, 'Status da inscrição atualizado com sucesso!')
                return redirect('rh:treinamento_inscricoes', treinamento_id=inscricao.treinamento.id)
        
        context = {
            'inscricao': inscricao,
            'STATUS_CHOICES': [
                ('INSCRITO', 'Inscrito'),
                ('CONFIRMADO', 'Confirmado'),
                ('CANCELADO', 'Cancelado'),
                ('CONCLUIDO', 'Concluído'),
            ]
        }
        return render(request, 'rh/treinamentos/alterar_status.html', context)
        
    except Exception as e:
        messages.error(request, 'Inscrição não encontrada.')
        return redirect('rh:treinamentos')

@login_required
def inscricao_avaliar(request, inscricao_id):
    """Avaliar inscrição de treinamento"""
    try:
        from meuprojeto.empresa.models_rh import InscricaoTreinamento
        inscricao = InscricaoTreinamento.objects.get(id=inscricao_id)
        
        if request.method == 'POST':
            nota = request.POST.get('nota')
            observacoes = request.POST.get('observacoes', '')
            
            if nota:
                inscricao.nota = float(nota)
                inscricao.observacoes = observacoes
                inscricao.save()
                messages.success(request, 'Inscrição avaliada com sucesso!')
                return redirect('rh:treinamento_inscricoes', treinamento_id=inscricao.treinamento.id)
        
        context = {'inscricao': inscricao}
        return render(request, 'rh/treinamentos/avaliar.html', context)
        
    except Exception as e:
        messages.error(request, 'Inscrição não encontrada.')
        return redirect('rh:treinamentos')

@login_required
def inscricao_deletar(request, inscricao_id):
    """Deletar inscrição de treinamento"""
    try:
        from meuprojeto.empresa.models_rh import InscricaoTreinamento
        inscricao = InscricaoTreinamento.objects.get(id=inscricao_id)
        
        if request.method == 'POST':
            inscricao.delete()
            messages.success(request, 'Inscrição deletada com sucesso!')
            return redirect('rh:treinamento_inscricoes', treinamento_id=inscricao.treinamento.id)
        
        context = {'inscricao': inscricao}
        return render(request, 'rh/treinamentos/deletar_inscricao.html', context)
        
    except Exception as e:
        messages.error(request, 'Inscrição não encontrada.')
        return redirect('rh:treinamentos')

@login_required
def rh_avaliacoes(request):
    """Lista de avaliações de desempenho"""
    avaliacoes = AvaliacaoDesempenho.objects.all().order_by('-data_avaliacao')
    
    # Filtros
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    tipo_filter = request.GET.get('tipo', '')
    ano_filter = request.GET.get('ano', '')
    departamento_filter = request.GET.get('departamento', '')
    cargo_filter = request.GET.get('cargo', '')
    
    # Aplicar filtros
    if search_query:
        avaliacoes = avaliacoes.filter(
            Q(funcionario__nome_completo__icontains=search_query) |
            Q(avaliador__nome_completo__icontains=search_query)
        )
    
    if status_filter:
        avaliacoes = avaliacoes.filter(status=status_filter)
    
    if tipo_filter:
        avaliacoes = avaliacoes.filter(tipo=tipo_filter)
    
    if ano_filter:
        avaliacoes = avaliacoes.filter(data_avaliacao__year=ano_filter)
    
    if departamento_filter:
        avaliacoes = avaliacoes.filter(funcionario__departamento_id=departamento_filter)
    
    if cargo_filter:
        avaliacoes = avaliacoes.filter(funcionario__cargo_id=cargo_filter)
    
    # Obter anos disponíveis para o dropdown (de todas as avaliações, não apenas as filtradas)
    todos_anos = AvaliacaoDesempenho.objects.exclude(data_avaliacao__isnull=True).values_list('data_avaliacao__year', flat=True).distinct()
    anos = sorted([ano for ano in todos_anos if ano is not None], reverse=True)
    
    # Obter departamentos e cargos para os dropdowns
    from meuprojeto.empresa.models import Departamento, Cargo
    departamentos = Departamento.objects.filter(ativo=True).order_by('nome')
    cargos = Cargo.objects.filter(ativo=True).order_by('nome')
    
    # Calcular estatísticas (usando todas as avaliações, não apenas as filtradas)
    todas_avaliacoes = AvaliacaoDesempenho.objects.all()
    
    stats = {
        'total_avaliacoes': todas_avaliacoes.count(),
        'planejadas': todas_avaliacoes.filter(status='PLANEJADA').count(),
        'em_andamento': todas_avaliacoes.filter(status='EM_ANDAMENTO').count(),
        'concluidas': todas_avaliacoes.filter(status='CONCLUIDA').count(),
        'canceladas': todas_avaliacoes.filter(status='CANCELADA').count(),
    }
    
    # Calcular nota média das avaliações concluídas
    from django.db import models
    avaliacoes_com_nota = todas_avaliacoes.filter(status='CONCLUIDA').exclude(nota_geral__isnull=True)
    if avaliacoes_com_nota.exists():
        stats['nota_media'] = avaliacoes_com_nota.aggregate(avg_nota=models.Avg('nota_geral'))['avg_nota']
    else:
        stats['nota_media'] = 0
    
    # Calcular percentagens
    total = stats['total_avaliacoes']
    if total > 0:
        stats['percent_planejadas'] = round((stats['planejadas'] / total) * 100, 1)
        stats['percent_em_andamento'] = round((stats['em_andamento'] / total) * 100, 1)
        stats['percent_concluidas'] = round((stats['concluidas'] / total) * 100, 1)
        stats['percent_canceladas'] = round((stats['canceladas'] / total) * 100, 1)
    else:
        stats['percent_planejadas'] = 0
        stats['percent_em_andamento'] = 0
        stats['percent_concluidas'] = 0
        stats['percent_canceladas'] = 0
    
    # Paginação
    paginator = Paginator(avaliacoes, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'avaliacoes': page_obj,
        'search_query': search_query,
        'status_filter': status_filter,
        'tipo_filter': tipo_filter,
        'ano_filter': ano_filter,
        'departamento_filter': departamento_filter,
        'cargo_filter': cargo_filter,
        'status_choices': AvaliacaoDesempenho.STATUS_CHOICES,
        'tipo_choices': AvaliacaoDesempenho.TIPO_CHOICES,
        'anos': anos,
        'departamentos': departamentos,
        'cargos': cargos,
        'stats': stats,
    }
    
    return render(request, 'rh/avaliacoes/main.html', context)

@login_required
def avaliacao_add_batch(request):
    """Adicionar avaliações em lote por departamento ou cargo"""
    if request.method == 'POST':
        departamento_id = request.POST.get('departamento')
        cargo_id = request.POST.get('cargo')
        avaliador_id = request.POST.get('avaliador')
        tipo = request.POST.get('tipo')
        data_inicio = request.POST.get('data_inicio')
        data_fim = request.POST.get('data_fim')
        
        if not all([avaliador_id, tipo, data_inicio, data_fim]):
            messages.error(request, 'Todos os campos obrigatórios devem ser preenchidos.')
        else:
            try:
                # Obter funcionários baseado nos filtros
                funcionarios = Funcionario.objects.filter(status='AT')
                
                if departamento_id:
                    funcionarios = funcionarios.filter(departamento_id=departamento_id)
                
                if cargo_id:
                    funcionarios = funcionarios.filter(cargo_id=cargo_id)
                
                if not funcionarios.exists():
                    messages.warning(request, 'Nenhum funcionário encontrado com os critérios selecionados.')
                    return redirect('rh:avaliacao_add_batch')
                
                # Criar avaliações para cada funcionário
                avaliacoes_criadas = 0
                for funcionario in funcionarios:
                    # Verificar se já existe avaliação para este funcionário no período
                    avaliacao_existente = AvaliacaoDesempenho.objects.filter(
                        funcionario=funcionario,
                        data_inicio__lte=datetime.strptime(data_fim, '%Y-%m-%d').date(),
                        data_fim__gte=datetime.strptime(data_inicio, '%Y-%m-%d').date()
                    ).exists()
                    
                    if not avaliacao_existente:
                        AvaliacaoDesempenho.objects.create(
                            funcionario=funcionario,
                            avaliador_id=avaliador_id,
                            tipo=tipo,
                            status='PLANEJADA',
                            data_inicio=datetime.strptime(data_inicio, '%Y-%m-%d').date(),
                            data_fim=datetime.strptime(data_fim, '%Y-%m-%d').date()
                        )
                        avaliacoes_criadas += 1
                
                if avaliacoes_criadas > 0:
                    messages.success(request, f'{avaliacoes_criadas} avaliações criadas com sucesso!')
                else:
                    messages.warning(request, 'Nenhuma avaliação foi criada. Verifique se já existem avaliações para o período selecionado.')
                
                return redirect('rh:avaliacoes')
                
            except ValueError as e:
                messages.error(request, f'Erro nos dados: {str(e)}')
            except Exception as e:
                messages.error(request, f'Erro ao criar avaliações: {str(e)}')
    
    # Buscar dados para o formulário
    funcionarios = Funcionario.objects.filter(status='AT').order_by('nome_completo')
    departamentos = Departamento.objects.filter(ativo=True).order_by('nome')
    cargos = Cargo.objects.filter(ativo=True).order_by('nome')
    
    context = {
        'funcionarios': funcionarios,
        'departamentos': departamentos,
        'cargos': cargos,
        'STATUS_CHOICES': AvaliacaoDesempenho.STATUS_CHOICES,
        'TIPO_CHOICES': AvaliacaoDesempenho.TIPO_CHOICES,
    }
    
    return render(request, 'rh/avaliacoes/add_batch.html', context)

@login_required
def avaliacao_add(request):
    """Adicionar avaliação de desempenho"""
    if request.method == 'POST':
        funcionario_id = request.POST.get('funcionario')
        avaliador_id = request.POST.get('avaliador')
        tipo = request.POST.get('tipo')
        status = request.POST.get('status')
        data_inicio = request.POST.get('data_inicio')
        data_fim = request.POST.get('data_fim')
        nota_geral = request.POST.get('nota_geral')
        classificacao = request.POST.get('classificacao')
        metas_estabelecidas = request.POST.get('metas_estabelecidas')
        metas_alcancadas = request.POST.get('metas_alcancadas')
        pontos_fortes = request.POST.get('pontos_fortes')
        pontos_melhoria = request.POST.get('pontos_melhoria')
        observacoes_avaliador = request.POST.get('observacoes_avaliador')
        observacoes_funcionario = request.POST.get('observacoes_funcionario')
        plano_desenvolvimento = request.POST.get('plano_desenvolvimento')
        
        if not all([funcionario_id, avaliador_id, tipo, status, data_inicio, data_fim]):
            messages.error(request, 'Todos os campos obrigatórios devem ser preenchidos.')
        else:
            try:
                avaliacao = AvaliacaoDesempenho.objects.create(
                    funcionario_id=funcionario_id,
                    avaliador_id=avaliador_id,
                    tipo=tipo,
                    status=status,
                    data_inicio=datetime.strptime(data_inicio, '%Y-%m-%d').date(),
                    data_fim=datetime.strptime(data_fim, '%Y-%m-%d').date(),
                    nota_geral=float(nota_geral) if nota_geral else None,
                    classificacao=classificacao,
                    metas_estabelecidas=metas_estabelecidas,
                    metas_alcancadas=metas_alcancadas,
                    pontos_fortes=pontos_fortes,
                    pontos_melhoria=pontos_melhoria,
                    observacoes_avaliador=observacoes_avaliador,
                    observacoes_funcionario=observacoes_funcionario,
                    plano_desenvolvimento=plano_desenvolvimento
                )
                
                # Actualizar status automaticamente
                avaliacao.actualizar_status_automatico()
                
                # Processar critérios de avaliação
                criterios = CriterioAvaliacao.objects.filter(ativo=True)
                for criterio in criterios:
                    nota_key = f'nota_{criterio.id}'
                    obs_key = f'obs_{criterio.id}'
                    
                    if nota_key in request.POST and request.POST[nota_key]:
                        nota = float(request.POST[nota_key])
                        observacoes = request.POST.get(obs_key, '')
                        
                        CriterioAvaliado.objects.create(
                            avaliacao=avaliacao,
                            criterio=criterio,
                            nota=nota,
                            observacoes=observacoes
                        )
                        
                        # Actualizar status após adicionar critério
                        avaliacao.actualizar_status_automatico()
                
                # Recalcular nota geral e classificação após processar critérios
                avaliacao.nota_geral = avaliacao.calcular_nota_geral()
                avaliacao.classificacao = avaliacao.definir_classificacao()
                avaliacao.save()
                
                messages.success(request, 'Avaliação criada com sucesso!')
                return redirect('rh:avaliacao_detail', avaliacao_id=avaliacao.id)
                
            except ValueError as e:
                messages.error(request, f'Erro nos dados: {str(e)}')
            except Exception as e:
                messages.error(request, f'Erro ao salvar: {str(e)}')
    
    funcionarios = Funcionario.objects.filter(status='AT').order_by('nome_completo')
    criterios = CriterioAvaliacao.objects.filter(ativo=True)
    
    context = {
        'funcionarios': funcionarios,
        'criterios': criterios,
        'STATUS_CHOICES': AvaliacaoDesempenho.STATUS_CHOICES,
        'TIPO_CHOICES': AvaliacaoDesempenho.TIPO_CHOICES,
        'CLASSIFICACAO_CHOICES': AvaliacaoDesempenho.CLASSIFICACAO_CHOICES,
    }
    
    return render(request, 'rh/avaliacoes/form.html', context)

@login_required
def avaliacao_iniciar(request, avaliacao_id):
    """Iniciar uma avaliação (mudar status para EM_ANDAMENTO)"""
    try:
        avaliacao = AvaliacaoDesempenho.objects.get(id=avaliacao_id)
        
        if avaliacao.status == 'PLANEJADA':
            avaliacao.status = 'EM_ANDAMENTO'
            from django.utils import timezone
            avaliacao.data_avaliacao = timezone.now().date()
            avaliacao.save()
            messages.success(request, 'Avaliação iniciada com sucesso!')
        else:
            messages.warning(request, 'Esta avaliação não pode ser iniciada no estado actual.')
            
    except AvaliacaoDesempenho.DoesNotExist:
        messages.error(request, 'Avaliação não encontrada.')
    
    return redirect('rh:avaliacao_detail', avaliacao_id=avaliacao_id)

@login_required
def avaliacao_concluir(request, avaliacao_id):
    """Concluir uma avaliação (mudar status para CONCLUIDA)"""
    try:
        avaliacao = AvaliacaoDesempenho.objects.get(id=avaliacao_id)
        
        if avaliacao.marcar_como_concluida():
            messages.success(request, 'Avaliação concluída com sucesso!')
        else:
            messages.warning(request, 'Esta avaliação não pode ser concluída. Verifique se tem nota geral e critérios avaliados.')
            
    except AvaliacaoDesempenho.DoesNotExist:
        messages.error(request, 'Avaliação não encontrada.')
    
    return redirect('rh:avaliacao_detail', avaliacao_id=avaliacao_id)

@login_required
def avaliacao_edit(request, avaliacao_id):
    """Editar uma avaliação de desempenho"""
    try:
        avaliacao = AvaliacaoDesempenho.objects.get(id=avaliacao_id)
        
        if request.method == 'POST':
            # Processar dados do formulário
            funcionario_id = request.POST.get('funcionario')
            avaliador_id = request.POST.get('avaliador')
            tipo = request.POST.get('tipo')
            status = request.POST.get('status')
            data_inicio = request.POST.get('data_inicio')
            data_fim = request.POST.get('data_fim')
            nota_geral = request.POST.get('nota_geral')
            classificacao = request.POST.get('classificacao')
            metas_estabelecidas = request.POST.get('metas_estabelecidas')
            metas_alcancadas = request.POST.get('metas_alcancadas')
            pontos_fortes = request.POST.get('pontos_fortes')
            pontos_melhoria = request.POST.get('pontos_melhoria')
            observacoes_avaliador = request.POST.get('observacoes_avaliador')
            observacoes_funcionario = request.POST.get('observacoes_funcionario')
            plano_desenvolvimento = request.POST.get('plano_desenvolvimento')
            
            # Validações básicas
            if not all([funcionario_id, avaliador_id, tipo, status, data_inicio, data_fim]):
                messages.error(request, 'Todos os campos obrigatórios devem ser preenchidos.')
            else:
                try:
                    # Atualizar avaliação
                    avaliacao.funcionario_id = funcionario_id
                    avaliacao.avaliador_id = avaliador_id
                    avaliacao.tipo = tipo
                    avaliacao.status = status
                    avaliacao.data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
                    avaliacao.data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
                    
                    if nota_geral:
                        avaliacao.nota_geral = float(nota_geral)
                    if classificacao:
                        avaliacao.classificacao = classificacao
                    if metas_estabelecidas:
                        avaliacao.metas_estabelecidas = metas_estabelecidas
                    if metas_alcancadas:
                        avaliacao.metas_alcancadas = metas_alcancadas
                    if pontos_fortes:
                        avaliacao.pontos_fortes = pontos_fortes
                    if pontos_melhoria:
                        avaliacao.pontos_melhoria = pontos_melhoria
                    if observacoes_avaliador:
                        avaliacao.observacoes_avaliador = observacoes_avaliador
                    if observacoes_funcionario:
                        avaliacao.observacoes_funcionario = observacoes_funcionario
                    if plano_desenvolvimento:
                        avaliacao.plano_desenvolvimento = plano_desenvolvimento
                    
                    avaliacao.save()
                    
                    # Actualizar status automaticamente
                    avaliacao.actualizar_status_automatico()
                    
                    # Processar critérios de avaliação
                    criterios = CriterioAvaliacao.objects.filter(ativo=True)
                    for criterio in criterios:
                        nota_key = f'nota_{criterio.id}'
                        obs_key = f'obs_{criterio.id}'
                        
                        if nota_key in request.POST and request.POST[nota_key]:
                            nota = float(request.POST[nota_key])
                            observacoes = request.POST.get(obs_key, '')
                            
                            # Atualizar ou criar avaliação do critério
                            criterio_avaliado, created = CriterioAvaliado.objects.get_or_create(
                                avaliacao=avaliacao,
                                criterio=criterio,
                                defaults={
                                    'nota': nota,
                                    'observacoes': observacoes
                                }
                            )
                            
                            if not created:
                                criterio_avaliado.nota = nota
                                criterio_avaliado.observacoes = observacoes
                                criterio_avaliado.save()
                            
                            # Actualizar status após modificar critério
                            avaliacao.actualizar_status_automatico()
                    
                    # Recalcular nota geral e classificação após processar critérios
                    avaliacao.nota_geral = avaliacao.calcular_nota_geral()
                    avaliacao.classificacao = avaliacao.definir_classificacao()
                    avaliacao.save()
                    
                    messages.success(request, 'Avaliação atualizada com sucesso!')
                    return redirect('rh:avaliacao_detail', avaliacao_id=avaliacao.id)
                    
                except ValueError as e:
                    messages.error(request, f'Erro nos dados: {str(e)}')
                except Exception as e:
                    messages.error(request, f'Erro ao salvar: {str(e)}')
        
        # Buscar dados para o formulário
        funcionarios = Funcionario.objects.filter(status='AT').order_by('nome_completo')
        criterios = CriterioAvaliacao.objects.filter(ativo=True)
        avaliacoes_criterios = CriterioAvaliado.objects.filter(avaliacao=avaliacao)
        
        # Criar dicionário de notas para facilitar o acesso no template
        notas_criterios = {}
        for ac in avaliacoes_criterios:
            notas_criterios[ac.criterio.id] = {
                'nota': ac.nota,
                'observacoes': ac.observacoes
            }
        
        context = {
            'avaliacao': avaliacao,
            'funcionarios': funcionarios,
            'criterios': criterios,
            'notas_criterios': notas_criterios,
            'STATUS_CHOICES': AvaliacaoDesempenho.STATUS_CHOICES,
            'TIPO_CHOICES': AvaliacaoDesempenho.TIPO_CHOICES,
            'CLASSIFICACAO_CHOICES': AvaliacaoDesempenho.CLASSIFICACAO_CHOICES,
        }
        
        return render(request, 'rh/avaliacoes/form.html', context)
        
    except AvaliacaoDesempenho.DoesNotExist:
        messages.error(request, 'Avaliação não encontrada.')
        return redirect('rh:avaliacoes')

@login_required
def avaliacao_detail(request, avaliacao_id):
    """Detalhes de uma avaliação específica"""
    try:
        avaliacao = AvaliacaoDesempenho.objects.get(id=avaliacao_id)
        
        # Buscar critérios de avaliação
        criterios = CriterioAvaliacao.objects.filter(ativo=True)
        
        # Buscar avaliações dos critérios para esta avaliação
        avaliacoes_criterios = CriterioAvaliado.objects.filter(avaliacao=avaliacao)
        
        context = {
            'avaliacao': avaliacao,
            'criterios': criterios,
            'avaliacoes_criterios': avaliacoes_criterios,
        }
        
        return render(request, 'rh/avaliacoes/detail.html', context)
        
    except AvaliacaoDesempenho.DoesNotExist:
        messages.error(request, 'Avaliação não encontrada.')
        return redirect('rh:avaliacoes')

@login_required
def avaliacao_delete(request, avaliacao_id):
    """Deletar avaliação de desempenho"""
    try:
        avaliacao = AvaliacaoDesempenho.objects.get(id=avaliacao_id)
        
        if request.method == 'POST':
            try:
                avaliacao.delete()
                messages.success(request, 'Avaliação deletada com sucesso!')
                return redirect('rh:avaliacoes')
            except Exception as e:
                messages.error(request, f'Erro ao deletar avaliação: {str(e)}')
        
        context = {'avaliacao': avaliacao}
        return render(request, 'rh/avaliacoes/delete.html', context)
        
    except AvaliacaoDesempenho.DoesNotExist:
        messages.error(request, 'Avaliação não encontrada.')
        return redirect('rh:avaliacoes')

@login_required
def avaliacao_print(request, avaliacao_id):
    """Gerar PDF da avaliação de desempenho"""
    try:
        avaliacao = AvaliacaoDesempenho.objects.get(id=avaliacao_id)
        
        # Por enquanto, redirecionar para a versão HTML
        # Em uma implementação completa, aqui seria gerado o PDF
        return redirect('rh:avaliacao_print_html', avaliacao_id=avaliacao_id)
        
    except AvaliacaoDesempenho.DoesNotExist:
        messages.error(request, 'Avaliação não encontrada.')
        return redirect('rh:avaliacoes')

@login_required
def avaliacao_print_html(request, avaliacao_id):
    """Visualização da avaliação para impressão"""
    try:
        avaliacao = AvaliacaoDesempenho.objects.get(id=avaliacao_id)
        
        # Buscar critérios de avaliação
        criterios = CriterioAvaliacao.objects.filter(ativo=True)
        
        # Buscar avaliações dos critérios para esta avaliação
        avaliacoes_criterios = CriterioAvaliado.objects.filter(avaliacao=avaliacao)
        
        context = {
            'avaliacao': avaliacao,
            'criterios': criterios,
            'avaliacoes_criterios': avaliacoes_criterios,
        }
        
        return render(request, 'rh/avaliacoes/print.html', context)
        
    except AvaliacaoDesempenho.DoesNotExist:
        messages.error(request, 'Avaliação não encontrada.')
        return redirect('rh:avaliacoes')

@login_required
def criterios(request):
    """Lista de critérios de avaliação"""
    criterios = CriterioAvaliacao.objects.filter(ativo=True).order_by('nome')
    
    # Filtros
    search_query = request.GET.get('search', '')
    if search_query:
        criterios = criterios.filter(nome__icontains=search_query)
    
    # Paginação
    paginator = Paginator(criterios, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'criterios': page_obj,
        'search_query': search_query,
    }
    
    return render(request, 'rh/avaliacoes/criterios/main.html', context)

@login_required
def criterio_add(request):
    """Adicionar critério de avaliação"""
    if request.method == 'POST':
        nome = request.POST.get('nome')
        descricao = request.POST.get('descricao', '')
        peso = request.POST.get('peso')
        ativo = request.POST.get('ativo') == 'on'
        
        if not all([nome, peso]):
            messages.error(request, 'Nome e peso são obrigatórios.')
        else:
            try:
                CriterioAvaliacao.objects.create(
                    nome=nome,
                    descricao=descricao,
                    peso=int(peso),
                    ativo=ativo
                )
                messages.success(request, 'Critério de avaliação criado com sucesso!')
                return redirect('rh:criterios')
            except ValueError as e:
                messages.error(request, f'Erro nos dados: {str(e)}')
            except Exception as e:
                messages.error(request, f'Erro ao salvar: {str(e)}')
    
    return render(request, 'rh/avaliacoes/criterios/form.html')

@login_required
def criterio_edit(request, criterio_id):
    """Editar critério de avaliação"""
    try:
        criterio = CriterioAvaliacao.objects.get(id=criterio_id)
        
        if request.method == 'POST':
            nome = request.POST.get('nome')
            descricao = request.POST.get('descricao', '')
            peso = request.POST.get('peso')
            ativo = request.POST.get('ativo') == 'on'
            
            if not all([nome, peso]):
                messages.error(request, 'Nome e peso são obrigatórios.')
            else:
                try:
                    criterio.nome = nome
                    criterio.descricao = descricao
                    criterio.peso = int(peso)
                    criterio.ativo = ativo
                    criterio.save()
                    
                    messages.success(request, 'Critério de avaliação atualizado com sucesso!')
                    return redirect('rh:criterios')
                except ValueError as e:
                    messages.error(request, f'Erro nos dados: {str(e)}')
                except Exception as e:
                    messages.error(request, f'Erro ao salvar: {str(e)}')
        
        context = {'criterio': criterio}
        return render(request, 'rh/avaliacoes/criterios/form.html', context)
        
    except CriterioAvaliacao.DoesNotExist:
        messages.error(request, 'Critério de avaliação não encontrado.')
        return redirect('rh:criterios')

@login_required
def criterio_delete(request, criterio_id):
    """Deletar critério de avaliação"""
    try:
        criterio = CriterioAvaliacao.objects.get(id=criterio_id)
        
        if request.method == 'POST':
            try:
                # Verificar se há avaliações usando este critério
                avaliacoes_count = CriterioAvaliado.objects.filter(criterio=criterio).count()
                if avaliacoes_count > 0:
                    messages.error(request, f'Não é possível deletar este critério pois existem {avaliacoes_count} avaliações associadas.')
                    return redirect('rh:criterios')
                
                criterio.delete()
                messages.success(request, 'Critério de avaliação deletado com sucesso!')
                return redirect('rh:criterios')
            except Exception as e:
                messages.error(request, f'Erro ao deletar critério: {str(e)}')
        
        context = {'criterio': criterio}
        return render(request, 'rh/avaliacoes/criterios/delete.html', context)
        
    except CriterioAvaliacao.DoesNotExist:
        messages.error(request, 'Critério de avaliação não encontrado.')
        return redirect('rh:criterios')

@login_required
def rh_promocoes(request):
    """Lista de promoções"""
    promocoes = Promocao.objects.all().order_by('-data_solicitacao')
    
    # Filtros
    status_filter = request.GET.get('status', '')
    if status_filter:
        promocoes = promocoes.filter(status=status_filter)
    
    tipo_filter = request.GET.get('tipo', '')
    if tipo_filter:
        promocoes = promocoes.filter(tipo=tipo_filter)
    
    funcionario_filter = request.GET.get('funcionario', '')
    if funcionario_filter:
        promocoes = promocoes.filter(funcionario__nome_completo__icontains=funcionario_filter)
    
    # Paginação
    paginator = Paginator(promocoes, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Estatísticas
    total_promocoes = promocoes.count()
    promocoes_pendentes = promocoes.filter(status='PENDENTE').count()
    promocoes_aprovadas = promocoes.filter(status='APROVADO').count()
    promocoes_implementadas = promocoes.filter(status='IMPLEMENTADO').count()
    promocoes_rejeitadas = promocoes.filter(status='REJEITADO').count()
    
    # Choices para os filtros
    status_choices = Promocao.STATUS_CHOICES
    tipo_choices = Promocao.TIPO_CHOICES
    
    context = {
        'promocoes': page_obj,
        'status_filter': status_filter,
        'tipo_filter': tipo_filter,
        'funcionario_filter': funcionario_filter,
        'status_choices': status_choices,
        'tipo_choices': tipo_choices,
        'stats': {
            'total': total_promocoes,
            'pendentes': promocoes_pendentes,
            'aprovadas': promocoes_aprovadas,
            'implementadas': promocoes_implementadas,
            'rejeitadas': promocoes_rejeitadas,
        }
    }
    
    return render(request, 'rh/promocoes/main.html', context)

@login_required
def rh_promocao_add(request):
    """Adicionar promoção"""
    if request.method == 'POST':
        from datetime import date
        funcionario_id = request.POST.get('funcionario')
        tipo = request.POST.get('tipo')
        cargo_novo_id = request.POST.get('cargo_novo')
        salario_novo = request.POST.get('salario_novo')
        motivo = request.POST.get('motivo', '')
        justificativa = request.POST.get('justificativa', '')
        observacoes = request.POST.get('observacoes', '')

        # Validações mínimas: funcionário, tipo e salário novo
        if not funcionario_id or not tipo or not salario_novo:
            messages.error(request, 'Selecione o funcionário, o tipo e informe o salário novo.')
        else:
            try:
                funcionario = get_object_or_404(Funcionario, id=funcionario_id)
                salario_anterior_val = Decimal(funcionario.get_salario_atual())
                cargo_anterior_obj = funcionario.cargo

                # Se for promoção de cargo, cargo_novo é opcional (pode manter o mesmo)
                cargo_novo_val = cargo_novo_id if cargo_novo_id else None

                promocao = Promocao.objects.create(
                    funcionario=funcionario,
                    tipo=tipo,
                    status='PENDENTE',
                    cargo_anterior=cargo_anterior_obj,
                    cargo_novo_id=cargo_novo_val,
                    data_solicitacao=date.today(),
                    salario_anterior=salario_anterior_val,
                    salario_novo=Decimal(salario_novo),
                    motivo=motivo,
                    justificativa=justificativa,
                    observacoes=observacoes,
                )
                messages.success(request, 'Promoção/Aumento criado com sucesso!')
                return redirect('rh:promocao_detail', promocao_id=promocao.id)
            except (InvalidOperation, ValueError) as e:
                messages.error(request, f'Erro nos valores informados: {str(e)}')
            except Exception as e:
                messages.error(request, f'Erro ao salvar: {str(e)}')
    
    funcionarios = Funcionario.objects.filter(status='AT').order_by('nome_completo')
    cargos = Cargo.objects.filter(ativo=True).order_by('nome')
    tipo_choices = Promocao.TIPO_CHOICES
    
    context = {
        'funcionarios': funcionarios,
        'cargos': cargos,
        'tipo_choices': tipo_choices,
    }
    return render(request, 'rh/promocoes/form.html', context)

@login_required
def rh_promocao_detail(request, promocao_id):
    """Detalhes da promoção"""
    try:
        promocao = Promocao.objects.get(id=promocao_id)
        context = {'promocao': promocao}
        return render(request, 'rh/promocoes/detail.html', context)
    except Promocao.DoesNotExist:
        messages.error(request, 'Promoção não encontrada.')
        return redirect('rh:promocoes')

@login_required
def rh_promocao_edit(request, promocao_id):
    """Editar promoção"""
    try:
        promocao = Promocao.objects.get(id=promocao_id)
        
        if request.method == 'POST':
            funcionario_id = request.POST.get('funcionario')
            tipo = request.POST.get('tipo')
            cargo_novo_id = request.POST.get('cargo_novo')
            salario_novo = request.POST.get('salario_novo')
            motivo = request.POST.get('motivo', '')
            justificativa = request.POST.get('justificativa', '')
            observacoes = request.POST.get('observacoes', '')

            if not funcionario_id or not tipo or not salario_novo:
                messages.error(request, 'Selecione o funcionário, o tipo e informe o salário novo.')
            else:
                try:
                    funcionario = get_object_or_404(Funcionario, id=funcionario_id)
                    promocao.funcionario = funcionario
                    promocao.tipo = tipo
                    promocao.cargo_anterior = funcionario.cargo
                    promocao.cargo_novo_id = cargo_novo_id if cargo_novo_id else None
                    # Mantemos data_solicitacao original
                    promocao.salario_anterior = Decimal(funcionario.get_salario_atual())
                    promocao.salario_novo = Decimal(salario_novo)
                    promocao.motivo = motivo
                    promocao.justificativa = justificativa
                    promocao.observacoes = observacoes
                    promocao.save()

                    messages.success(request, 'Promoção/Aumento atualizado com sucesso!')
                    return redirect('rh:promocao_detail', promocao_id=promocao.id)
                except (InvalidOperation, ValueError) as e:
                    messages.error(request, f'Erro nos valores informados: {str(e)}')
                except Exception as e:
                    messages.error(request, f'Erro ao salvar: {str(e)}')
        
        funcionarios = Funcionario.objects.filter(status='AT').order_by('nome_completo')
        cargos = Cargo.objects.filter(ativo=True).order_by('nome')
        tipo_choices = Promocao.TIPO_CHOICES
        
        context = {
            'promocao': promocao,
            'funcionarios': funcionarios,
            'cargos': cargos,
            'tipo_choices': tipo_choices,
        }
        return render(request, 'rh/promocoes/form.html', context)
        
    except Promocao.DoesNotExist:
        messages.error(request, 'Promoção não encontrada.')
        return redirect('rh:promocoes')

@login_required
def rh_promocao_delete(request, promocao_id):
    """Deletar promoção"""
    try:
        promocao = Promocao.objects.get(id=promocao_id)
        
        if request.method == 'POST':
            promocao.delete()
            messages.success(request, 'Promoção deletada com sucesso!')
            return redirect('rh:promocoes')
        
        context = {'promocao': promocao}
        return render(request, 'rh/promocoes/delete.html', context)
        
    except Promocao.DoesNotExist:
        messages.error(request, 'Promoção não encontrada.')
        return redirect('rh:promocoes')

@login_required
def rh_promocao_aprovar(request, promocao_id):
    """Aprovar promoção"""
    try:
        promocao = Promocao.objects.get(id=promocao_id)
        
        if request.method == 'POST':
            observacoes = request.POST.get('observacoes', '')
            promocao.status = 'APROVADO'
            if observacoes:
                promocao.observacoes = observacoes
            promocao.save()
            messages.success(request, 'Promoção aprovada com sucesso!')
            return redirect('rh:promocao_detail', promocao_id=promocao.id)
        
        context = {'promocao': promocao}
        return render(request, 'rh/promocoes/aprovar.html', context)
        
    except Promocao.DoesNotExist:
        messages.error(request, 'Promoção não encontrada.')
        return redirect('rh:promocoes')

@login_required
def rh_promocao_rejeitar(request, promocao_id):
    """Rejeitar promoção"""
    try:
        promocao = Promocao.objects.get(id=promocao_id)
        
        if request.method == 'POST':
            motivo_rejeicao = request.POST.get('motivo_rejeicao', '')
            if not motivo_rejeicao:
                messages.error(request, 'Motivo da rejeição é obrigatório.')
            else:
                promocao.status = 'REJEITADO'
                promocao.observacoes = motivo_rejeicao
                promocao.save()
                messages.success(request, 'Promoção rejeitada com sucesso!')
                return redirect('rh:promocao_detail', promocao_id=promocao.id)
        
        context = {'promocao': promocao}
        return render(request, 'rh/promocoes/rejeitar.html', context)
        
    except Promocao.DoesNotExist:
        messages.error(request, 'Promoção não encontrada.')
        return redirect('rh:promocoes')

@login_required
def rh_promocao_implementar(request, promocao_id):
    """Implementar promoção"""
    try:
        promocao = Promocao.objects.get(id=promocao_id)
        
        if request.method == 'POST':
            data_implementacao = request.POST.get('data_implementacao')
            if not data_implementacao:
                messages.error(request, 'Data de implementação é obrigatória.')
            else:
                try:
                    # Atualizar dados do funcionário de forma segura
                    implement_date = datetime.strptime(data_implementacao, '%Y-%m-%d').date()

                    funcionario = promocao.funcionario
                    # Atualizar salário
                    if promocao.salario_novo is not None:
                        funcionario.salario_atual = promocao.salario_novo
                    # Atualizar cargo somente se foi definido um novo cargo
                    if promocao.cargo_novo is not None:
                        funcionario.cargo = promocao.cargo_novo
                    funcionario.save()

                    # Atualizar status e datas da promoção
                    promocao.status = 'IMPLEMENTADO'
                    promocao.data_implementacao = implement_date
                    promocao.data_efetivacao = implement_date
                    promocao.save()

                    messages.success(request, 'Promoção/Aumento implementado com sucesso!')
                    return redirect('rh:promocao_detail', promocao_id=promocao.id)
                except ValueError as e:
                    messages.error(request, f'Erro na data: {str(e)}')
        
        context = {'promocao': promocao}
        return render(request, 'rh/promocoes/implementar.html', context)
        
    except Promocao.DoesNotExist:
        messages.error(request, 'Promoção não encontrada.')
        return redirect('rh:promocoes')

@login_required
def rh_promocoes_relatorio(request):
    """Relatório de promoções"""
    promocoes = Promocao.objects.all().order_by('-data_solicitacao')

    status_filter = request.GET.get('status', '')
    if status_filter:
        promocoes = promocoes.filter(status=status_filter)

    data_inicio = request.GET.get('data_inicio')
    if data_inicio:
        try:
            promocoes = promocoes.filter(data_solicitacao__gte=datetime.strptime(data_inicio, '%Y-%m-%d').date())
        except ValueError:
            pass

    data_fim = request.GET.get('data_fim')
    if data_fim:
        try:
            promocoes = promocoes.filter(data_solicitacao__lte=datetime.strptime(data_fim, '%Y-%m-%d').date())
        except ValueError:
            pass

    paginator = Paginator(promocoes, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    total_promocoes = promocoes.count()
    promocoes_aprovadas = promocoes.filter(status='APROVADO').count()
    promocoes_pendentes = promocoes.filter(status='PENDENTE').count()
    promocoes_implementadas = promocoes.filter(status='IMPLEMENTADO').count()

    context = {
        'promocoes': page_obj,
        'status_filter': status_filter,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'total_promocoes': total_promocoes,
        'promocoes_aprovadas': promocoes_aprovadas,
        'promocoes_pendentes': promocoes_pendentes,
        'promocoes_implementadas': promocoes_implementadas,
        'STATUS_CHOICES': [
            ('PENDENTE', 'Pendente'),
            ('APROVADO', 'Aprovado'),
            ('REJEITADO', 'Rejeitado'),
            ('IMPLEMENTADO', 'Implementado'),
        ]
    }

    return render(request, 'rh/promocoes/relatorio.html', context)

@login_required
def rh_transferencias(request):
    """Lista de transferências de funcionários"""
    transferencias = TransferenciaFuncionario.objects.select_related(
        'funcionario', 'sucursal_origem', 'sucursal_destino', 
        'departamento_origem', 'departamento_destino'
    ).all().order_by('-data_solicitacao')
    
    # Filtros
    status = request.GET.get('status', '')
    funcionario_id = request.GET.get('funcionario', '')
    sucursal_id = request.GET.get('sucursal', '')
    
    if status:
        transferencias = transferencias.filter(status=status)
    
    if funcionario_id:
        transferencias = transferencias.filter(funcionario_id=funcionario_id)
    
    if sucursal_id:
        transferencias = transferencias.filter(
            Q(sucursal_origem_id=sucursal_id) | Q(sucursal_destino_id=sucursal_id)
        )
    
    paginator = Paginator(transferencias, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'status': status,
        'funcionario_id': funcionario_id,
        'sucursal_id': sucursal_id,
        'funcionarios': Funcionario.objects.filter(status='AT').order_by('nome_completo'),
        'sucursais': Sucursal.objects.filter(ativa=True).order_by('nome'),
        'status_choices': TransferenciaFuncionario.STATUS_CHOICES,
    }
    return render(request, 'rh/transferencias/main.html', context)

@login_required
def rh_transferencia_add(request):
    """Adicionar nova transferência"""
    if request.method == 'POST':
        funcionario_id = request.POST.get('funcionario')
        sucursal_destino_id = request.POST.get('sucursal_destino')
        departamento_destino_id = request.POST.get('departamento_destino')
        cargo_novo_id = request.POST.get('cargo_novo', '')
        data_efetiva = request.POST.get('data_efetiva')
        motivo = request.POST.get('motivo')
        observacoes = request.POST.get('observacoes', '')
        
        if not all([funcionario_id, sucursal_destino_id, departamento_destino_id, data_efetiva, motivo]):
            messages.error(request, 'Todos os campos obrigatórios devem ser preenchidos.')
            return redirect('rh:transferencia_add')
        
        try:
            funcionario = Funcionario.objects.get(id=funcionario_id)
            # Verificar se já existe transferência pendente para este funcionário
            transferencia_pendente = TransferenciaFuncionario.objects.filter(
                funcionario=funcionario,
                status__in=['PENDENTE', 'APROVADO']
            ).exists()
            
            if transferencia_pendente:
                messages.error(request, 'Este funcionário já possui uma transferência pendente ou aprovada.')
                return redirect('rh:transferencia_add')
            transferencia = TransferenciaFuncionario.objects.create(
                funcionario=funcionario,
                sucursal_origem=funcionario.sucursal,
                departamento_origem=funcionario.departamento,
                sucursal_destino_id=sucursal_destino_id,
                departamento_destino_id=departamento_destino_id,
                cargo_novo_id=cargo_novo_id if cargo_novo_id else None,
                data_solicitacao=timezone.now().date(),
                data_efetiva=data_efetiva,
                motivo=motivo,
                observacoes=observacoes,
                criado_por=request.user
            )
            messages.success(request, 'Transferência solicitada com sucesso.')
            return redirect('rh:transferencias')
        except Exception as e:
            messages.error(request, f'Erro ao criar transferência: {str(e)}')
    
    context = {
        'funcionarios': Funcionario.objects.filter(status='AT').select_related('sucursal', 'departamento', 'cargo').order_by('nome_completo'),
        'sucursais': Sucursal.objects.filter(ativa=True).order_by('nome'),
        'cargos': Cargo.objects.filter(ativo=True).order_by('nome'),
    }
    return render(request, 'rh/transferencias/form.html', context)

@login_required
def rh_transferencia_detail(request, transferencia_id):
    """Detalhes da transferência"""
    transferencia = get_object_or_404(TransferenciaFuncionario, id=transferencia_id)
    
    context = {
        'transferencia': transferencia,
    }
    return render(request, 'rh/transferencias/detail.html', context)

@login_required
def rh_transferencia_edit(request, transferencia_id):
    """Editar transferência"""
    transferencia = get_object_or_404(TransferenciaFuncionario, id=transferencia_id)
    
    # Só permite editar se estiver pendente
    if transferencia.status != 'PENDENTE':
        messages.error(request, 'Apenas transferências pendentes podem ser editadas.')
        return redirect('rh:transferencia_detail', transferencia_id=transferencia_id)
    
    if request.method == 'POST':
        transferencia.sucursal_destino_id = request.POST.get('sucursal_destino')
        transferencia.departamento_destino_id = request.POST.get('departamento_destino')
        transferencia.cargo_novo_id = request.POST.get('cargo_novo') or None
        transferencia.data_efetiva = request.POST.get('data_efetiva')
        transferencia.motivo = request.POST.get('motivo')
        transferencia.observacoes = request.POST.get('observacoes', '')
        
        try:
            transferencia.save()
            messages.success(request, 'Transferência atualizada com sucesso.')
            return redirect('rh:transferencia_detail', transferencia_id=transferencia_id)
        except Exception as e:
            messages.error(request, f'Erro ao atualizar transferência: {str(e)}')
    
    context = {
        'transferencia': transferencia,
        'sucursais': Sucursal.objects.filter(ativa=True).order_by('nome'),
        'cargos': Cargo.objects.filter(ativo=True).order_by('nome'),
    }
    return render(request, 'rh/transferencias/form.html', context)

@login_required
def rh_transferencia_delete(request, transferencia_id):
    """Excluir transferência"""
    transferencia = get_object_or_404(TransferenciaFuncionario, id=transferencia_id)
    
    # Só permite excluir se estiver pendente
    if transferencia.status != 'PENDENTE':
        messages.error(request, 'Apenas transferências pendentes podem ser excluídas.')
        return redirect('rh:transferencias')
    
    if request.method == 'POST':
        try:
            transferencia.delete()
            messages.success(request, 'Transferência excluída com sucesso.')
        except Exception as e:
            messages.error(request, f'Erro ao excluir transferência: {str(e)}')
        return redirect('rh:transferencias')
    
    context = {'transferencia': transferencia}
    return render(request, 'rh/transferencias/delete.html', context)

@login_required
def rh_transferencia_aprovar(request, transferencia_id):
    """Aprovar transferência"""
    transferencia = get_object_or_404(TransferenciaFuncionario, id=transferencia_id)
    
    if not transferencia.pode_aprovar:
        messages.error(request, 'Esta transferência não pode ser aprovada.')
        return redirect('rh:transferencia_detail', transferencia_id=transferencia_id)
    
    if request.method == 'POST':
        try:
            transferencia.status = 'APROVADO'
            transferencia.data_aprovacao = timezone.now().date()
            transferencia.aprovado_por = request.user
            transferencia.save()
            messages.success(request, 'Transferência aprovada com sucesso.')
        except Exception as e:
            messages.error(request, f'Erro ao aprovar transferência: {str(e)}')
        return redirect('rh:transferencia_detail', transferencia_id=transferencia_id)
    
    context = {'transferencia': transferencia}
    return render(request, 'rh/transferencias/approve.html', context)

@login_required
def rh_transferencia_rejeitar(request, transferencia_id):
    """Rejeitar transferência"""
    transferencia = get_object_or_404(TransferenciaFuncionario, id=transferencia_id)
    
    if not transferencia.pode_aprovar:
        messages.error(request, 'Esta transferência não pode ser rejeitada.')
        return redirect('rh:transferencia_detail', transferencia_id=transferencia_id)
    
    if request.method == 'POST':
        motivo_rejeicao = request.POST.get('motivo_rejeicao', '')
        if not motivo_rejeicao:
            messages.error(request, 'Motivo da rejeição é obrigatório.')
            return redirect('rh:transferencia_rejeitar', transferencia_id=transferencia_id)
        
        try:
            transferencia.status = 'REJEITADO'
            transferencia.motivo_rejeicao = motivo_rejeicao
            transferencia.rejeitado_por = request.user
            transferencia.save()
            messages.success(request, 'Transferência rejeitada com sucesso.')
        except Exception as e:
            messages.error(request, f'Erro ao rejeitar transferência: {str(e)}')
        return redirect('rh:transferencia_detail', transferencia_id=transferencia_id)
    
    context = {'transferencia': transferencia}
    return render(request, 'rh/transferencias/reject.html', context)

@login_required
def rh_transferencia_implementar(request, transferencia_id):
    """Implementar transferência"""
    transferencia = get_object_or_404(TransferenciaFuncionario, id=transferencia_id)
    
    if not transferencia.pode_implementar:
        messages.error(request, 'Esta transferência não pode ser implementada.')
        return redirect('rh:transferencia_detail', transferencia_id=transferencia_id)
    
    if request.method == 'POST':
        try:
            # Atualizar dados do funcionário
            funcionario = transferencia.funcionario
            funcionario.sucursal = transferencia.sucursal_destino
            funcionario.departamento = transferencia.departamento_destino
            
            if transferencia.cargo_novo:
                funcionario.cargo = transferencia.cargo_novo
            
            funcionario.save()
            
            # Atualizar status da transferência
            transferencia.status = 'IMPLEMENTADO'
            transferencia.data_implementacao = timezone.now().date()
            transferencia.save()
            
            messages.success(request, 'Transferência implementada com sucesso.')
        except Exception as e:
            messages.error(request, f'Erro ao implementar transferência: {str(e)}')
        return redirect('rh:transferencia_detail', transferencia_id=transferencia_id)
    
    context = {'transferencia': transferencia}
    return render(request, 'rh/transferencias/implement.html', context)

@login_required
def rh_transferencia_efetivar(request, transferencia_id):
    """Efetivar transferência"""
    transferencia = get_object_or_404(TransferenciaFuncionario, id=transferencia_id)
    
    if transferencia.status != 'IMPLEMENTADO':
        messages.error(request, 'Apenas transferências implementadas podem ser efetivadas.')
        return redirect('rh:transferencia_detail', transferencia_id=transferencia_id)
    
    if request.method == 'POST':
        try:
            transferencia.status = 'EFETIVADO'
            transferencia.data_efetivacao = timezone.now().date()
            transferencia.save()
            messages.success(request, 'Transferência efetivada com sucesso.')
        except Exception as e:
            messages.error(request, f'Erro ao efetivar transferência: {str(e)}')
        return redirect('rh:transferencia_detail', transferencia_id=transferencia_id)
    
    context = {'transferencia': transferencia}
    return render(request, 'rh/transferencias/efetivar.html', context)

@login_required
def rh_transferencias_relatorio(request):
    """Relatório de transferências"""
    transferencias = TransferenciaFuncionario.objects.select_related(
        'funcionario', 'sucursal_origem', 'sucursal_destino'
    ).all().order_by('-data_solicitacao')
    
    # Filtros
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    status = request.GET.get('status')
    
    if data_inicio:
        transferencias = transferencias.filter(data_solicitacao__gte=data_inicio)
    
    if data_fim:
        transferencias = transferencias.filter(data_solicitacao__lte=data_fim)
    
    if status:
        transferencias = transferencias.filter(status=status)
    
    context = {
        'transferencias': transferencias,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'status': status,
        'status_choices': TransferenciaFuncionario.STATUS_CHOICES,
    }
    return render(request, 'rh/transferencias/relatorio.html', context)
