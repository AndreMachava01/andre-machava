"""Views RH — núcleo (dashboard, funcionários, dept, cargo, API)."""
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


def _checkbox_sim(post, field='ativo'):
    """Interpreta checkbox HTML (valor 'on' ou '1')."""
    return post.get(field) in ('on', '1')


def _resolver_sucursal_departamento(post, sucursais):
    """Resolve sucursal do POST ou usa a primeira disponível."""
    sucursal_id = post.get('sucursal')
    if sucursal_id:
        return get_object_or_404(Sucursal, pk=sucursal_id)
    if sucursais.exists():
        return sucursais.first()
    return None
from .views import (
    generate_pdf_report,
    generate_pdf_from_html,
    render_pdf_from_url,
    render_pdf_from_html_string,
)

logger = logging.getLogger(__name__)


@login_required
def rh_main(request):
    """Página principal do módulo RH"""
    from .services.rh_service import obter_estatisticas_rh
    context = obter_estatisticas_rh()
    return render(request, 'rh/main.html', context)

@login_required
def rh_funcionarios(request):
    """Lista de funcionários com filtros e paginação"""
    # Parâmetros de busca e filtro
    search_query = request.GET.get('q', '')
    departamento_id = request.GET.get('departamento')
    cargo_id = request.GET.get('cargo')
    status = request.GET.get('status')

    # Query base
    funcionarios = Funcionario.objects.all()

    # Aplicar filtros
    if search_query:
        funcionarios = funcionarios.filter(
            Q(nome_completo__icontains=search_query) |
            Q(codigo_funcionario__icontains=search_query) |
            Q(nuit__icontains=search_query)
        )

    if departamento_id:
        funcionarios = funcionarios.filter(departamento_id=departamento_id)

    if cargo_id:
        funcionarios = funcionarios.filter(cargo_id=cargo_id)

    if status:
        status_map = {
            'ATIVO': 'AT',
            'INATIVO': 'IN',
            'AT': 'AT',
            'IN': 'IN',
            'AF': 'AF',
            'FE': 'FE',
        }
        status_code = status_map.get((status or '').upper())
        if status_code:
            funcionarios = funcionarios.filter(status=status_code)

    # Ordenação
    funcionarios = funcionarios.order_by('nome_completo')

    # Paginação
    paginator = Paginator(funcionarios, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    from .services.rh_service import obter_stats_funcionarios_lista

    context = {
        'funcionarios': page_obj,
        'departamentos': Departamento.objects.all(),
        'cargos': Cargo.objects.all(),
        'search_query': search_query,
        'departamento_id': departamento_id,
        'cargo_id': cargo_id,
        'status': status,
        'page_obj': page_obj,
        **obter_stats_funcionarios_lista(),
    }

    return render(request, 'rh/funcionarios/main.html', context)

@login_required
def rh_funcionario_detail(request, id):
    """Detalhes de um funcionário específico"""
    funcionario = get_object_or_404(Funcionario, id=id)
    
    # Calcular dados adicionais
    hoje = date.today()
    
    # Calcular idade
    if funcionario.data_nascimento:
        idade = hoje.year - funcionario.data_nascimento.year
        if hoje.month < funcionario.data_nascimento.month or (hoje.month == funcionario.data_nascimento.month and hoje.day < funcionario.data_nascimento.day):
            idade -= 1
    else:
        idade = None
    
    # Calcular tempo de empresa
    if funcionario.data_admissao:
        tempo_empresa = hoje - funcionario.data_admissao
        anos = tempo_empresa.days // 365
        meses = (tempo_empresa.days % 365) // 30
        dias = tempo_empresa.days % 30
        tempo_empresa_str = f"{anos} anos, {meses} meses e {dias} dias"
    else:
        tempo_empresa_str = "Não informado"
    
    # Buscar folhas recentes do funcionário
    from meuprojeto.empresa.models_rh import FolhaSalarial, FuncionarioFolha
    folhas_recentes = FolhaSalarial.objects.filter(
        funcionarios_folha__funcionario=funcionario
    ).order_by('-mes_referencia')[:5]
    
    # Calcular remunerações
    remuneracao_hora_real = funcionario.get_remuneracao_por_hora()
    remuneracao_hora_teorica = funcionario.get_remuneracao_por_hora_teorica()
    remuneracao_dia_real = funcionario.get_remuneracao_por_dia()
    
    context = {
        'funcionario': funcionario,
        'idade': idade,
        'tempo_empresa': tempo_empresa_str,
        'folhas_recentes': folhas_recentes,
        'remuneracao_hora_real': remuneracao_hora_real,
        'remuneracao_hora_teorica': remuneracao_hora_teorica,
        'remuneracao_dia_real': remuneracao_dia_real,
    }
    
    return render(request, 'rh/funcionarios/detail.html', context)

@login_required
def rh_departamentos(request):
    """Lista de departamentos"""
    departamentos = Departamento.objects.select_related('sucursal').all().order_by('sucursal__nome', 'nome')
    
    # Paginação
    paginator = Paginator(departamentos, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    from .services.rh_service import obter_stats_departamentos_lista

    context = {
        'departamentos': page_obj,
        **obter_stats_departamentos_lista(),
    }
    
    return render(request, 'rh/departamentos/main.html', context)

@login_required
def rh_departamento_add(request):
    """Adicionar novo departamento"""
    sucursais = Sucursal.objects.filter(ativa=True).order_by('nome')

    if request.method == 'POST':
        try:
            sucursal = _resolver_sucursal_departamento(request.POST, sucursais)
            if not sucursal:
                messages.error(request, 'Nenhuma sucursal encontrada. Cadastre uma sucursal primeiro.')
                return redirect('rh:departamentos')

            departamento = Departamento(
                nome=request.POST['nome'].strip(),
                codigo='',
                tipo=request.POST.get('tipo', 'ADM'),
                descricao=request.POST.get('descricao', '').strip(),
                ativo=_checkbox_sim(request.POST),
                sucursal=sucursal,
            )
            departamento.full_clean()
            departamento.save()
            messages.success(request, 'Departamento adicionado com sucesso!')
            return redirect('rh:departamentos')
        except ValidationError as e:
            messages.error(request, f'Erro de validação: {e}')
        except Exception as e:
            messages.error(request, f'Erro ao adicionar departamento: {e}')

    context = {
        'tipos_departamento': Departamento.TIPO_CHOICES,
        'sucursais': sucursais,
        'sucursal': sucursais.first(),
    }

    return render(request, 'rh/departamentos/form.html', context)

@login_required
def rh_departamento_edit(request, id):
    """Editar departamento existente"""
    departamento = get_object_or_404(Departamento, id=id)
    
    if request.method == 'POST':
        try:
            departamento.nome = request.POST['nome'].strip()
            departamento.tipo = request.POST.get('tipo', 'ADM')
            departamento.descricao = request.POST.get('descricao', '').strip()
            departamento.ativo = _checkbox_sim(request.POST)
            departamento.full_clean()
            departamento.save()
            messages.success(request, 'Departamento atualizado com sucesso!')
            return redirect('rh:departamentos')
        except ValidationError as e:
            messages.error(request, f'Erro de validação: {e}')
        except Exception as e:
            messages.error(request, f'Erro ao atualizar departamento: {e}')

    context = {
        'departamento': departamento,
        'tipos_departamento': Departamento.TIPO_CHOICES,
        'sucursal': departamento.sucursal,
    }
    
    return render(request, 'rh/departamentos/form.html', context)

@login_required
def rh_departamento_delete(request, id):
    """Excluir departamento com migração automática de dados vinculados"""
    departamento = get_object_or_404(Departamento, id=id)
    
    # Verificar se há funcionários vinculados
    funcionarios_vinculados = Funcionario.objects.filter(departamento=departamento)
    cargos_vinculados = Cargo.objects.filter(departamento=departamento)
    
    if request.method == 'POST':
        try:
            
            # Se há dados vinculados, verificar se foi selecionado um departamento de destino
            if funcionarios_vinculados.exists() or cargos_vinculados.exists():
                departamento_destino_id = request.POST.get('departamento_destino')
                if not departamento_destino_id:
                    messages.error(request, 'Selecione um departamento de destino para migrar os dados vinculados.')
                    return redirect('rh:departamento_delete', id=departamento.id)
                
                departamento_destino = get_object_or_404(Departamento, id=departamento_destino_id)
                # Migrar funcionários
                funcionarios_migrados = 0
                if funcionarios_vinculados.exists():
                    funcionarios_vinculados.update(departamento=departamento_destino)
                    funcionarios_migrados = funcionarios_vinculados.count()
                
                # Migrar cargos
                cargos_migrados = 0
                if cargos_vinculados.exists():
                    cargos_vinculados.update(departamento=departamento_destino)
                    cargos_migrados = cargos_vinculados.count()
                
                # Agora pode deletar o departamento
                departamento.delete()
                
                # Mensagem de sucesso com detalhes da migração
                mensagem = f'Departamento "{departamento.nome}" excluído com sucesso!'
                if funcionarios_migrados > 0:
                    mensagem += f' {funcionarios_migrados} funcionário(s) migrado(s) para "{departamento_destino.nome}".'
                if cargos_migrados > 0:
                    mensagem += f' {cargos_migrados} cargo(s) migrado(s) para "{departamento_destino.nome}".'
                
                messages.success(request, mensagem)
                return redirect('rh:departamentos')
            else:
                # Não há dados vinculados, pode deletar diretamente
                departamento.delete()
                messages.success(request, 'Departamento excluído com sucesso!')
                return redirect('rh:departamentos')
                
        except Exception as e:
            messages.error(request, f'Erro ao excluir departamento: {e}')
    
    # Buscar departamentos disponíveis para migração (excluindo o próprio)
    departamentos_disponiveis = Departamento.objects.exclude(id=departamento.id).filter(ativo=True).order_by('nome')
    
    context = {
        'departamento': departamento,
        'funcionarios_vinculados': funcionarios_vinculados,
        'cargos_vinculados': cargos_vinculados,
        'departamentos_disponiveis': departamentos_disponiveis,
    }
    
    return render(request, 'rh/departamentos/delete.html', context)

@login_required
def rh_cargos(request):
    """Lista de cargos"""
    cargos = Cargo.objects.filter(ativo=True).order_by('nome')
    
    # Paginação
    paginator = Paginator(cargos, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'cargos': page_obj,
    }
    
    return render(request, 'rh/cargos/main.html', context)

@login_required
def rh_cargo_add(request):
    """Adicionar novo cargo"""
    if request.method == 'POST':
        try:
            cargo = Cargo(
                nome=request.POST['nome'],
                nivel=request.POST['nivel'],
                categoria=request.POST.get('categoria', 'OP'),
                departamento_id=request.POST.get('departamento'),
                descricao=request.POST.get('descricao', ''),
                ativo=request.POST.get('ativo') == 'on'
            )
            cargo.full_clean()
            cargo.save()
            messages.success(request, 'Cargo adicionado com sucesso!')
            return redirect('rh:cargos')
        except ValidationError as e:
            messages.error(request, f'Erro de validação: {e}')
        except Exception as e:
            messages.error(request, f'Erro ao adicionar cargo: {e}')
    
    # Buscar departamentos disponíveis (próprios + vinculados)
    
    # Buscar sucursal atual (primeira disponível)
    sucursal_atual = Sucursal.objects.first()
    
    # Departamentos próprios da sucursal
    dept_proprios = Departamento.objects.filter(
        sucursal=sucursal_atual, 
        ativo=True
    ).select_related('sucursal')
    
    # Departamentos vinculados de outras sucursais
    dept_vinculados = Departamento.objects.filter(
        sucursais_vinculadas__sucursal=sucursal_atual,
        sucursais_vinculadas__ativo=True,
        ativo=True
    ).exclude(sucursal=sucursal_atual).select_related('sucursal')
    
    # Combinar e ordenar
    departamentos = (dept_proprios | dept_vinculados).distinct().order_by('sucursal__nome', 'nome')
    
    context = {
        'departamentos': departamentos,
        'sucursal_atual': sucursal_atual,
    }
    
    return render(request, 'rh/cargos/form.html', context)

@login_required
def rh_cargo_edit(request, id):
    """Editar cargo existente"""
    cargo = get_object_or_404(Cargo, id=id)
    
    if request.method == 'POST':
        try:
            cargo.nome = request.POST['nome']
            cargo.nivel = request.POST['nivel']
            cargo.categoria = request.POST.get('categoria', 'OP')
            # Código não é editável - é gerado automaticamente
            cargo.departamento_id = request.POST.get('departamento')
            cargo.descricao = request.POST.get('descricao', '')
            cargo.ativo = request.POST.get('ativo') == 'on'
            cargo.full_clean()
            cargo.save()
            messages.success(request, 'Cargo atualizado com sucesso!')
            return redirect('rh:cargos')
        except ValidationError as e:
            messages.error(request, f'Erro de validação: {e}')
        except Exception as e:
            messages.error(request, f'Erro ao atualizar cargo: {e}')
    
    context = {
        'cargo': cargo,
        'departamentos': Departamento.objects.filter(ativo=True),
    }
    
    return render(request, 'rh/cargos/form.html', context)

@login_required
def rh_cargo_delete(request, id):
    """Excluir cargo com migração automática de funcionários vinculados"""
    cargo = get_object_or_404(Cargo, id=id)
    
    # Verificar se há funcionários vinculados
    funcionarios_vinculados = Funcionario.objects.filter(cargo=cargo)
    
    if request.method == 'POST':
        try:
            # Se há funcionários vinculados, verificar se foi selecionado um cargo de destino
            if funcionarios_vinculados.exists():
                cargo_destino_id = request.POST.get('cargo_destino')
                
                if not cargo_destino_id:
                    messages.error(request, 'Selecione um cargo de destino para migrar os funcionários vinculados.')
                    return redirect('rh:cargo_delete', id=cargo.id)
                
                cargo_destino = get_object_or_404(Cargo, id=cargo_destino_id)
                
                # Migrar funcionários
                funcionarios_migrados = 0
                if funcionarios_vinculados.exists():
                    funcionarios_vinculados.update(cargo=cargo_destino)
                    funcionarios_migrados = funcionarios_vinculados.count()
                
                # Agora pode deletar o cargo
                cargo.delete()
                
                # Mensagem de sucesso com detalhes da migração
                mensagem = f'Cargo "{cargo.nome}" excluído com sucesso!'
                if funcionarios_migrados > 0:
                    mensagem += f' {funcionarios_migrados} funcionário(s) migrado(s) para "{cargo_destino.nome}".'
                
                messages.success(request, mensagem)
                return redirect('rh:cargos')
            else:
                # Não há funcionários vinculados, pode deletar diretamente
                cargo.delete()
                messages.success(request, 'Cargo excluído com sucesso!')
                return redirect('rh:cargos')
                
        except Exception as e:
            messages.error(request, f'Erro ao excluir cargo: {e}')
    
    # Buscar cargos disponíveis para migração (excluindo o próprio e do mesmo departamento)
    cargos_disponiveis = Cargo.objects.exclude(id=cargo.id).filter(
        departamento=cargo.departamento, 
        ativo=True
    ).order_by('nome')
    
    context = {
        'cargo': cargo,
        'funcionarios_vinculados': funcionarios_vinculados,
        'cargos_disponiveis': cargos_disponiveis,
    }
    
    return render(request, 'rh/cargos/delete.html', context)

@login_required
def rh_funcionario_add(request):
    """Adicionar novo funcionário"""
    
    if request.method == 'POST':
        try:
            # Dados básicos
            nome_completo = request.POST.get('nome_completo')
            nuit = request.POST.get('nuit')
            data_nascimento = request.POST.get('data_nascimento')
            genero = request.POST.get('genero')
            estado_civil = request.POST.get('estado_civil')
            nacionalidade = request.POST.get('nacionalidade')
            naturalidade = request.POST.get('naturalidade')
            
            # Dados de contato
            telefone = request.POST.get('telefone')
            email = request.POST.get('email')
            endereco = request.POST.get('endereco')
            
            # Dados de localização
            provincia = request.POST.get('provincia')
            cidade = request.POST.get('cidade')
            bairro = request.POST.get('bairro')
            
            # Dados profissionais
            sucursal_id = request.POST.get('sucursal')
            departamento_id = request.POST.get('departamento')
            cargo_id = request.POST.get('cargo')
            data_admissao = request.POST.get('data_admissao')
            salario_atual = request.POST.get('salario_atual')
            
            # Dados bancários
            banco = request.POST.get('banco')
            outro_banco = request.POST.get('outro_banco')
            conta = request.POST.get('conta')
            nib = request.POST.get('nib')
            
            # Se "Outro" foi selecionado, usar o valor do campo outro_banco
            if banco == 'Outro' and outro_banco:
                banco = outro_banco
            
            # Validações básicas - apenas campos realmente obrigatórios
            if not nome_completo or not sucursal_id or not departamento_id or not cargo_id:
                messages.error(request, 'Preencha todos os campos obrigatórios.')
                # Buscar dados para os dropdowns
                sucursais = Sucursal.objects.filter(ativa=True).order_by('nome')
                departamentos = Departamento.objects.filter(ativo=True).order_by('nome')
                cargos = Cargo.objects.filter(ativo=True).order_by('nome')
                
                # Buscar benefícios e descontos disponíveis
                from meuprojeto.empresa.models_rh import BeneficioSalarial, DescontoSalarial
                beneficios_disponiveis = BeneficioSalarial.objects.filter(ativo=True).order_by('nome')
                descontos_disponiveis = DescontoSalarial.objects.filter(ativo=True).order_by('nome')
                
                context = {
                    'sucursais': sucursais,
                    'departamentos': departamentos,
                    'cargos': cargos,
                    'beneficios_disponiveis': beneficios_disponiveis,
                    'descontos_disponiveis': descontos_disponiveis,
                }
                return render(request, 'rh/funcionarios/form.html', context)
            
            # Verificar se NUIT já existe
            if Funcionario.objects.filter(nuit=nuit).exists():
                messages.error(request, 'Este NUIT já está sendo usado por outro funcionário.')
                # Buscar dados para os dropdowns
                sucursais = Sucursal.objects.filter(ativa=True).order_by('nome')
                departamentos = Departamento.objects.filter(ativo=True).order_by('nome')
                cargos = Cargo.objects.filter(ativo=True).order_by('nome')
                
                # Buscar benefícios e descontos disponíveis
                from meuprojeto.empresa.models_rh import BeneficioSalarial, DescontoSalarial
                beneficios_disponiveis = BeneficioSalarial.objects.filter(ativo=True).order_by('nome')
                descontos_disponiveis = DescontoSalarial.objects.filter(ativo=True).order_by('nome')
                
                context = {
                    'sucursais': sucursais,
                    'departamentos': departamentos,
                    'cargos': cargos,
                    'beneficios_disponiveis': beneficios_disponiveis,
                    'descontos_disponiveis': descontos_disponiveis,
                }
                return render(request, 'rh/funcionarios/form.html', context)
            
            # Buscar sucursal, departamento, cargo e localização
            sucursal = get_object_or_404(Sucursal, id=sucursal_id)
            departamento = get_object_or_404(Departamento, id=departamento_id)
            cargo = get_object_or_404(Cargo, id=cargo_id)
            
            # Criar funcionário
            funcionario = Funcionario.objects.create(
                nome_completo=nome_completo,
                nuit=nuit,
                data_nascimento=data_nascimento if data_nascimento else None,
                genero=genero if genero else 'M',
                estado_civil=estado_civil if estado_civil else 'S',
                nacionalidade=nacionalidade if nacionalidade else 'Moçambicana',
                naturalidade=naturalidade if naturalidade else '',
                telefone=telefone if telefone else '',
                email=email if email else '',
                endereco=endereco if endereco else '',
                provincia=provincia,
                cidade=cidade,
                bairro=bairro,
                sucursal=sucursal,
                departamento=departamento,
                cargo=cargo,
                data_admissao=data_admissao if data_admissao else date.today(),
                salario_atual=float(salario_atual) if salario_atual else 0.0,
                banco=banco if banco else '',
                conta=conta if conta else '',
                nib=nib if nib else '',
                status='AT'
            )
            
            # Processar benefícios e descontos
            beneficios_ids = request.POST.getlist('beneficios')
            descontos_ids = request.POST.getlist('descontos')
            
            # Atualizar benefícios
            funcionario.beneficios.set(beneficios_ids)
            
            # Atualizar descontos
            funcionario.descontos.set(descontos_ids)
            
            messages.success(request, f'Funcionário "{funcionario.nome_completo}" adicionado com sucesso!')
            return redirect('rh:funcionario_detail', id=funcionario.id)
            
        except Exception as e:
            messages.error(request, f'Erro ao adicionar funcionário: {e}')
            # Buscar dados para os dropdowns
            sucursais = Sucursal.objects.filter(ativa=True).order_by('nome')
            departamentos = Departamento.objects.filter(ativo=True).order_by('nome')
            cargos = Cargo.objects.filter(ativo=True).order_by('nome')
            
            # Buscar benefícios e descontos disponíveis
            from meuprojeto.empresa.models_rh import BeneficioSalarial, DescontoSalarial
            beneficios_disponiveis = BeneficioSalarial.objects.filter(ativo=True).order_by('nome')
            descontos_disponiveis = DescontoSalarial.objects.filter(ativo=True).order_by('nome')
            
            context = {
                'sucursais': sucursais,
                'departamentos': departamentos,
                'cargos': cargos,
                'beneficios_disponiveis': beneficios_disponiveis,
                'descontos_disponiveis': descontos_disponiveis,
            }
            return render(request, 'rh/funcionarios/form.html', context)
    
    # Buscar dados para os dropdowns
    sucursais = Sucursal.objects.filter(ativa=True).order_by('nome')
    departamentos = Departamento.objects.filter(ativo=True).order_by('nome')
    cargos = Cargo.objects.filter(ativo=True).order_by('nome')
    
    # Buscar benefícios e descontos disponíveis
    from meuprojeto.empresa.models_rh import BeneficioSalarial, DescontoSalarial
    beneficios_disponiveis = BeneficioSalarial.objects.filter(ativo=True).order_by('nome')
    descontos_disponiveis = DescontoSalarial.objects.filter(ativo=True).order_by('nome')
    
    context = {
        'sucursais': sucursais,
        'departamentos': departamentos,
        'cargos': cargos,
        'beneficios_disponiveis': beneficios_disponiveis,
        'descontos_disponiveis': descontos_disponiveis,
    }
    
    return render(request, 'rh/funcionarios/form.html', context)

@login_required
def rh_funcionario_edit(request, id):
    """Editar funcionário existente"""
    funcionario = get_object_or_404(Funcionario, id=id)
    
    
    if request.method == 'POST':
        try:
            # PRIMEIRO: Validar dados ANTES de atualizar o funcionário
            nome_completo = request.POST.get('nome_completo')
            nuit = request.POST.get('nuit')
            provincia = request.POST.get('provincia')
            cidade = request.POST.get('cidade')
            bairro = request.POST.get('bairro')
            sucursal_id = request.POST.get('sucursal')
            departamento_id = request.POST.get('departamento')
            cargo_id = request.POST.get('cargo')
            
            # Validações básicas ANTES de modificar o funcionário
            # Validações básicas - apenas campos realmente obrigatórios
            if not nome_completo or not sucursal_id or not departamento_id or not cargo_id:
                messages.error(request, 'Preencha todos os campos obrigatórios.')
                # Renderizar o template com os dados atuais em vez de redirecionar
                context = {
                    'funcionario': funcionario,
                    'sucursais': Sucursal.objects.filter(ativa=True).order_by('nome'),
                    'departamentos': Departamento.objects.filter(ativo=True).order_by('nome'),
                    'cargos': Cargo.objects.filter(ativo=True).order_by('nome'),
                    'beneficios_disponiveis': BeneficioSalarial.objects.filter(ativo=True).order_by('nome'),
                    'descontos_disponiveis': DescontoSalarial.objects.filter(ativo=True).order_by('nome'),
                }
                return render(request, 'rh/funcionarios/form.html', context)
            
            # Verificar se NUIT já existe (exceto para o próprio funcionário)
            if Funcionario.objects.filter(nuit=nuit).exclude(id=funcionario.id).exists():
                messages.error(request, 'Este NUIT já está sendo usado por outro funcionário.')
                # Renderizar o template com os dados atuais em vez de redirecionar
                context = {
                    'funcionario': funcionario,
                    'sucursais': Sucursal.objects.filter(ativa=True).order_by('nome'),
                    'departamentos': Departamento.objects.filter(ativo=True).order_by('nome'),
                    'cargos': Cargo.objects.filter(ativo=True).order_by('nome'),
                    'beneficios_disponiveis': BeneficioSalarial.objects.filter(ativo=True).order_by('nome'),
                    'descontos_disponiveis': DescontoSalarial.objects.filter(ativo=True).order_by('nome'),
                }
                return render(request, 'rh/funcionarios/form.html', context)
            
            # SEGUNDO: Agora que validamos, atualizar os dados do funcionário
            # Dados básicos
            funcionario.nome_completo = nome_completo
            funcionario.nuit = nuit
            funcionario.data_nascimento = request.POST.get('data_nascimento') if request.POST.get('data_nascimento') else None
            funcionario.genero = request.POST.get('genero')
            funcionario.estado_civil = request.POST.get('estado_civil')
            funcionario.nacionalidade = request.POST.get('nacionalidade')
            funcionario.naturalidade = request.POST.get('naturalidade')
            
            # Dados de contato
            funcionario.telefone = request.POST.get('telefone')
            funcionario.email = request.POST.get('email')
            funcionario.endereco = request.POST.get('endereco')
            
            # Dados de localização
            funcionario.provincia = provincia
            funcionario.cidade = cidade
            funcionario.bairro = bairro
            
            # Dados profissionais
            funcionario.data_admissao = request.POST.get('data_admissao') if request.POST.get('data_admissao') else funcionario.data_admissao
            funcionario.salario_atual = float(request.POST.get('salario_atual')) if request.POST.get('salario_atual') else funcionario.salario_atual
            
            # Dados bancários
            banco = request.POST.get('banco')
            outro_banco = request.POST.get('outro_banco')
            
            # Se "Outro" foi selecionado, usar o valor do campo outro_banco
            if banco == 'Outro' and outro_banco:
                funcionario.banco = outro_banco
            else:
                funcionario.banco = banco
                
            funcionario.conta = request.POST.get('conta')
            funcionario.nib = request.POST.get('nib')
            
            # Buscar sucursal, departamento, cargo
            sucursal = get_object_or_404(Sucursal, id=sucursal_id)
            departamento = get_object_or_404(Departamento, id=departamento_id)
            cargo = get_object_or_404(Cargo, id=cargo_id)
            
            # Atualizar sucursal, departamento, cargo
            funcionario.sucursal = sucursal
            funcionario.departamento = departamento
            funcionario.cargo = cargo
            
            # Processar benefícios e descontos
            beneficios_ids = request.POST.getlist('beneficios')
            descontos_ids = request.POST.getlist('descontos')
            
            # Atualizar benefícios
            funcionario.beneficios.set(beneficios_ids)
            
            # Atualizar descontos
            funcionario.descontos.set(descontos_ids)
            
            # Salvar alterações
            funcionario.save()
            
            messages.success(request, f'Funcionário "{funcionario.nome_completo}" atualizado com sucesso!')
            return redirect('rh:funcionario_detail', id=funcionario.id)
            
        except Exception as e:
            messages.error(request, f'Erro ao atualizar funcionário: {e}')
    
    # Buscar dados para os dropdowns
    sucursais = Sucursal.objects.filter(ativa=True).order_by('nome')
    departamentos = Departamento.objects.filter(ativo=True).order_by('nome')
    cargos = Cargo.objects.filter(ativo=True).order_by('nome')
    
    # Buscar benefícios e descontos disponíveis
    from meuprojeto.empresa.models_rh import BeneficioSalarial, DescontoSalarial
    beneficios_disponiveis = BeneficioSalarial.objects.filter(ativo=True).order_by('nome')
    descontos_disponiveis = DescontoSalarial.objects.filter(ativo=True).order_by('nome')
    
    context = {
        'funcionario': funcionario,
        'sucursais': sucursais,
        'departamentos': departamentos,
        'cargos': cargos,
        'beneficios_disponiveis': beneficios_disponiveis,
        'descontos_disponiveis': descontos_disponiveis,
    }
    
    return render(request, 'rh/funcionarios/form.html', context)

@login_required
def rh_funcionario_delete(request, id):
    """Deletar funcionário"""
    funcionario = get_object_or_404(Funcionario, id=id)
    
    if request.method == 'POST':
        try:
            nome_funcionario = funcionario.nome_completo
            funcionario.delete()
            messages.success(request, f'Funcionário "{nome_funcionario}" excluído com sucesso!')
            return redirect('rh:funcionarios')
        except Exception as e:
            messages.error(request, f'Erro ao excluir funcionário: {e}')
    
    context = {
        'funcionario': funcionario,
    }
    
    return render(request, 'rh/funcionarios/delete.html', context)

@login_required
def rh_funcionario_dados_remuneracao(request, id):
    """Endpoint AJAX para obter dados de remuneração do funcionário"""
    if request.method == 'GET':
        try:
            funcionario = get_object_or_404(Funcionario, id=id)
            
            # Obter remuneração por hora real
            remuneracao_real = funcionario.get_remuneracao_por_hora()
            remuneracao_real_valor = remuneracao_real['remuneracao_por_hora'] if remuneracao_real else None
            
            # Obter remuneração por hora teórica
            remuneracao_teorica = funcionario.get_remuneracao_por_hora_teorica()
            remuneracao_teorica_valor = remuneracao_teorica['remuneracao_por_hora_teorica'] if remuneracao_teorica else None
            
            # Obter salário atual
            salario_atual = funcionario.get_salario_atual()
            
            # Obter tipo de horas extras se fornecido
            tipo_horas_extras = request.GET.get('tipo', 'DI')
            
            # Criar instância temporária para calcular valor
            from meuprojeto.empresa.models_rh import HorasExtras
            horas_extras_temp = HorasExtras(
                funcionario=funcionario,
                tipo=tipo_horas_extras
            )
            
            # Calcular valor por hora das horas extras
            calculo_horas_extras = horas_extras_temp.calcular_valor_por_hora_automatico()
            
            return JsonResponse({
                'success': True,
                'salario_atual': float(salario_atual) if salario_atual else None,
                'remuneracao_real': remuneracao_real_valor,
                'remuneracao_teorica': remuneracao_teorica_valor,
                'funcionario_nome': funcionario.nome_completo,
                'calculo_horas_extras': calculo_horas_extras
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({'success': False, 'error': 'Método não permitido'})

@login_required
def rh_departamento_vinculacao(request, id):
    """Gerenciar vinculação de departamento a outras sucursais"""
    departamento = get_object_or_404(Departamento, id=id)
    
    if request.method == 'POST':
        sucursal_id = request.POST.get('sucursal')
        acao = request.POST.get('acao')
        
        try:
            sucursal = Sucursal.objects.get(id=sucursal_id)
            
            if acao == 'vincular':
                DepartamentoSucursal.objects.get_or_create(
                    departamento=departamento,
                    sucursal=sucursal,
                    defaults={'ativo': True}
                )
                messages.success(request, f'Departamento vinculado à {sucursal.nome}')
            elif acao == 'desvincular':
                DepartamentoSucursal.objects.filter(
                    departamento=departamento,
                    sucursal=sucursal
                ).delete()
                messages.success(request, f'Departamento desvinculado de {sucursal.nome}')
            
            return redirect('rh:departamento_vinculacao', id=departamento.id)
            
        except Sucursal.DoesNotExist:
            messages.error(request, 'Sucursal não encontrada')
        except Exception as e:
            messages.error(request, f'Erro: {e}')
    
    # Buscar sucursais disponíveis e vinculações
    sucursais_disponiveis = Sucursal.objects.exclude(id=departamento.sucursal.id).order_by('nome')
    vinculacoes = DepartamentoSucursal.objects.filter(departamento=departamento).select_related('sucursal')
    
    context = {
        'departamento': departamento,
        'sucursais_disponiveis': sucursais_disponiveis,
        'vinculacoes': vinculacoes,
    }
    
    return render(request, 'rh/departamentos/vinculacao.html', context)

@login_required
def api_funcionarios_search(request):
    return JsonResponse([], safe=False)

@login_required
def empresa_info(request):
    from .models_base import DadosEmpresa, Sucursal
    
    # Buscar dados da empresa (assumindo que há apenas uma empresa sede)
    dados_empresa = DadosEmpresa.objects.filter(is_sede=True).first()
    
    # Buscar sucursais da empresa
    sucursais = []
    if dados_empresa:
        sucursais = Sucursal.objects.filter(empresa_sede=dados_empresa, ativa=True).order_by('nome')
    
    context = {
        'dados_empresa': dados_empresa,
        'sucursais': sucursais,
    }
    
    return render(request, 'empresa/info.html', context)

@login_required
def api_departamentos_por_sucursal(request, sucursal_id):
    """API para buscar departamentos por sucursal"""
    try:
        sucursal = Sucursal.objects.get(id=sucursal_id)
        
        # Buscar departamentos da sucursal e departamentos vinculados
        departamentos_da_sucursal = Departamento.objects.filter(sucursal=sucursal).order_by('nome')
        departamentos_vinculados = Departamento.objects.filter(
            sucursais_vinculadas__sucursal=sucursal,
            sucursais_vinculadas__ativo=True
        ).order_by('nome')
        
        # Combinar e remover duplicatas
        todos_departamentos = list(departamentos_da_sucursal) + list(departamentos_vinculados)
        departamentos_unicos = list({dept.id: dept for dept in todos_departamentos}.values())
        
        results = []
        for departamento in departamentos_unicos:
            results.append({
                'id': departamento.id,
                'nome': departamento.nome,
                'codigo': departamento.codigo,
            })
        return JsonResponse({'results': results})
    except Sucursal.DoesNotExist:
        return JsonResponse({'results': []})
    except Exception as e:
        return JsonResponse({'results': [], 'error': str(e)})
