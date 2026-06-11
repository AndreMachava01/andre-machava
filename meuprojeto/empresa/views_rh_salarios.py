"""Views RH — salários, benefícios e descontos."""
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
def rh_salarios(request):
    """Lista de salários"""
    salarios = Salario.objects.select_related('funcionario').order_by('-data_inicio')
    
    # Paginação
    paginator = Paginator(salarios, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Dados para filtros
    funcionarios = Funcionario.objects.filter(status='AT').order_by('nome_completo')
    departamentos = Departamento.objects.filter(ativo=True).order_by('nome')
    status_choices = Salario.STATUS_CHOICES
    
    context = {
        'page_obj': page_obj,
        'funcionarios': funcionarios,
        'departamentos': departamentos,
        'status_choices': status_choices,
    }
    
    return render(request, 'rh/salarios/main.html', context)

@login_required
def rh_salario_add(request):
    """Adicionar novo salário"""
    if request.method == 'POST':
        try:
            # Obter dados do formulário
            funcionario_id = request.POST.get('funcionario')
            valor_base = request.POST.get('valor_base')
            data_inicio = request.POST.get('data_inicio')
            data_fim = request.POST.get('data_fim')
            status = request.POST.get('status')
            observacoes = request.POST.get('observacoes', '')
            
            # Validações básicas
            if not funcionario_id or not valor_base or not data_inicio or not status:
                messages.error(request, 'Todos os campos obrigatórios devem ser preenchidos.')
                return redirect('rh:salario_add')
            
            # Converter valor base
            try:
                valor_base = Decimal(valor_base)
                if valor_base <= 0:
                    raise ValueError("Valor deve ser positivo")
            except (InvalidOperation, ValueError):
                messages.error(request, 'Valor base deve ser um número válido maior que zero.')
                return redirect('rh:salario_add')
            
            # Obter funcionário
            funcionario = get_object_or_404(Funcionario, id=funcionario_id)
            
            # Converter datas
            try:
                data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
                data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date() if data_fim else None
                
                # Validar datas
                if data_fim and data_fim <= data_inicio:
                    messages.error(request, 'Data de fim deve ser posterior à data de início.')
                    return redirect('rh:salario_add')
                    
            except ValueError:
                messages.error(request, 'Formato de data inválido.')
                return redirect('rh:salario_add')
            
            # Criar salário
            salario = Salario.objects.create(
                funcionario=funcionario,
                valor_base=valor_base,
                data_inicio=data_inicio,
                data_fim=data_fim,
                status=status,
                observacoes=observacoes
            )
            
            messages.success(request, f'Salário de {funcionario.nome_completo} adicionado com sucesso!')
            return redirect('rh:salarios')
            
        except Exception as e:
            messages.error(request, f'Erro ao adicionar salário: {str(e)}')
            return redirect('rh:salario_add')
    
    # GET - Mostrar formulário
    funcionarios = Funcionario.objects.filter(status='AT').order_by('nome_completo')
    status_choices = Salario.STATUS_CHOICES
    
    context = {
        'funcionarios': funcionarios,
        'status_choices': status_choices,
    }
    
    return render(request, 'rh/salarios/form.html', context)

@login_required
def rh_salario_edit(request, salario_id):
    """Editar salário"""
    try:
        salario = Salario.objects.get(id=salario_id)
        
        if request.method == 'POST':
            funcionario_id = request.POST.get('funcionario')
            valor_base = request.POST.get('valor_base')
            data_inicio = request.POST.get('data_inicio')
            data_fim = request.POST.get('data_fim')
            status = request.POST.get('status')
            observacoes = request.POST.get('observacoes', '')
            
            if not all([funcionario_id, valor_base, data_inicio, data_fim, status]):
                messages.error(request, 'Todos os campos obrigatórios devem ser preenchidos.')
            else:
                try:
                    salario.funcionario_id = funcionario_id
                    salario.valor_base = Decimal(valor_base)
                    salario.data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
                    salario.data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
                    salario.status = status
                    salario.observacoes = observacoes
                    salario.save()
                    
                    messages.success(request, 'Salário atualizado com sucesso!')
                    return redirect('rh:salarios')
                except ValueError as e:
                    messages.error(request, f'Erro nos dados: {str(e)}')
                except Exception as e:
                    messages.error(request, f'Erro ao salvar: {str(e)}')
        
        funcionarios = Funcionario.objects.filter(status='AT').order_by('nome_completo')
        
        context = {
            'salario': salario,
            'funcionarios': funcionarios,
            'STATUS_CHOICES': Salario.STATUS_CHOICES,
        }
        
        return render(request, 'rh/salarios/form.html', context)
        
    except Salario.DoesNotExist:
        messages.error(request, 'Salário não encontrado.')
        return redirect('rh:salarios')

@login_required
def rh_salario_delete(request, salario_id):
    """Deletar salário"""
    try:
        salario = Salario.objects.get(id=salario_id)
        
        if request.method == 'POST':
            try:
                salario.delete()
                messages.success(request, 'Salário deletado com sucesso!')
                return redirect('rh:salarios')
            except Exception as e:
                messages.error(request, f'Erro ao deletar salário: {str(e)}')
        
        context = {'salario': salario}
        return render(request, 'rh/salarios/delete.html', context)
        
    except Salario.DoesNotExist:
        messages.error(request, 'Salário não encontrado.')
        return redirect('rh:salarios')

@login_required
def rh_beneficios_salariais(request):
    """Lista de benefícios salariais"""
    beneficios = BeneficioSalarial.objects.filter(ativo=True).order_by('-data_criacao')
    
    # Paginação
    paginator = Paginator(beneficios, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Dados para filtros
    tipo_choices = BeneficioSalarial.TIPO_CHOICES
    
    context = {
        'page_obj': page_obj,
        'tipo_choices': tipo_choices,
    }
    
    return render(request, 'rh/salarios/beneficios/main.html', context)

@login_required
def rh_beneficio_salarial_add(request):
    """Adicionar novo benefício salarial"""
    if request.method == 'POST':
        try:
            # Obter dados do formulário
            nome = request.POST.get('nome')
            tipo = request.POST.get('tipo')
            tipo_valor = request.POST.get('tipo_valor')
            valor = request.POST.get('valor')
            base_calculo = request.POST.get('base_calculo')
            base_calculo_personalizada = request.POST.get('base_calculo_personalizada', '')
            valor_minimo_isencao = request.POST.get('valor_minimo_isencao', '0')
            valor_maximo_isencao = request.POST.get('valor_maximo_isencao', '0')
            aplicar_automaticamente = request.POST.get('aplicar_automaticamente') == 'on'
            is_nao_monetario = request.POST.get('is_nao_monetario') == 'on'
            fornecedor = request.POST.get('fornecedor', '')
            observacoes = request.POST.get('observacoes', '')
            descricao = request.POST.get('descricao', '')
            ativo = request.POST.get('ativo') == 'on'
            
            # Validações básicas
            if not nome or not tipo:
                messages.error(request, 'Nome e tipo são obrigatórios.')
                return redirect('rh:beneficio_salarial_add')
            
            # Para benefícios monetários, validar base de cálculo, tipo_valor e valor
            if not is_nao_monetario:
                if not base_calculo:
                    messages.error(request, 'Base de cálculo é obrigatória para benefícios monetários.')
                    return redirect('rh:beneficio_salarial_add')
                if not tipo_valor or not valor:
                    messages.error(request, 'Tipo de valor e valor são obrigatórios para benefícios monetários.')
                    return redirect('rh:beneficio_salarial_add')
            
            # Converter valores
            try:
                # Para benefícios não monetários, valor é sempre zero
                if is_nao_monetario:
                    valor = Decimal('0')
                    tipo_valor = 'NAO_MONETARIO'  # Definir tipo_valor correto para não monetários
                    base_calculo = 'SALARIO_BASE'  # Base padrão para não monetários (não usada no cálculo)
                else:
                    if not valor or valor.strip() == '':
                        raise ValueError("Valor é obrigatório para benefícios monetários")
                    valor = Decimal(valor)
                    if valor < 0:
                        raise ValueError("Valor deve ser positivo")
                
                valor_minimo_isencao = Decimal(valor_minimo_isencao) if valor_minimo_isencao else Decimal('0')
                valor_maximo_isencao = Decimal(valor_maximo_isencao) if valor_maximo_isencao else Decimal('0')
            except (InvalidOperation, ValueError) as e:
                messages.error(request, f'Erro nos valores: {str(e)}')
                return redirect('rh:beneficio_salarial_add')
            
            # Criar benefício
            beneficio = BeneficioSalarial(
                nome=nome,
                tipo=tipo,
                tipo_valor=tipo_valor,
                valor=valor,
                base_calculo=base_calculo,
                base_calculo_personalizada=base_calculo_personalizada,
                fornecedor=fornecedor,
                observacoes=observacoes,
                ativo=ativo
            )
            beneficio.save()  # Salvar para gerar código automaticamente
            
            messages.success(request, f'Benefício "{nome}" adicionado com sucesso!')
            return redirect('rh:beneficios_salariais')
            
        except Exception as e:
            messages.error(request, f'Erro ao adicionar benefício: {str(e)}')
            return redirect('rh:beneficio_salarial_add')
    
    # GET - Mostrar formulário
    context = {
        'tipo_choices': BeneficioSalarial.TIPO_CHOICES,
        'tipo_valor_choices': BeneficioSalarial.TIPO_VALOR_CHOICES,
        'base_calculo_choices': BeneficioSalarial.BASE_CALCULO_CHOICES,
    }
    
    return render(request, 'rh/salarios/beneficios/form.html', context)

@login_required
def rh_beneficio_salarial_edit(request, beneficio_id):
    """Editar benefício salarial"""
    try:
        beneficio = BeneficioSalarial.objects.get(id=beneficio_id)
        
        if request.method == 'POST':
            nome = request.POST.get('nome')
            tipo = request.POST.get('tipo')
            tipo_valor = request.POST.get('tipo_valor')
            valor = request.POST.get('valor')
            base_calculo = request.POST.get('base_calculo')
            base_calculo_personalizada = request.POST.get('base_calculo_personalizada', '')
            is_nao_monetario = request.POST.get('is_nao_monetario') == 'on'
            # Campos de fornecedor/contato (para benefícios não monetários)
            fornecedor = request.POST.get('fornecedor', '')
            localizacao = request.POST.get('localizacao', '')
            horario_funcionamento = request.POST.get('horario_funcionamento', '')
            limite_uso = request.POST.get('limite_uso', '')
            documento_necessario = request.POST.get('documento_necessario', '')
            contato_responsavel = request.POST.get('contato_responsavel', '')
            telefone_contato = request.POST.get('telefone_contato', '')
            email_contato = request.POST.get('email_contato', '')
            observacoes = request.POST.get('observacoes', '')
            ativo = request.POST.get('ativo') == 'on'
            
            # Validações básicas
            if not nome or not tipo:
                messages.error(request, 'Nome e tipo são obrigatórios.')
            elif not is_nao_monetario and not base_calculo:
                messages.error(request, 'Base de cálculo é obrigatória para benefícios monetários.')
            elif not is_nao_monetario and (not tipo_valor or not valor):
                messages.error(request, 'Tipo de valor e valor são obrigatórios para benefícios monetários.')
            else:
                try:
                    # Converter valor com validação para benefícios não monetários
                    if is_nao_monetario:
                        valor_decimal = Decimal('0')  # Benefícios não monetários sempre têm valor zero
                        tipo_valor = 'NAO_MONETARIO'  # Definir tipo_valor correto para não monetários
                        base_calculo = 'SALARIO_BASE'  # Base padrão para não monetários (não usada no cálculo)
                    else:
                        if not valor or valor.strip() == '':
                            raise ValueError("Valor é obrigatório para benefícios monetários")
                        valor_decimal = Decimal(valor)
                        if valor_decimal < 0:
                            raise ValueError("Valor deve ser positivo")
                    
                    beneficio.nome = nome
                    beneficio.tipo = tipo
                    beneficio.tipo_valor = tipo_valor
                    beneficio.valor = valor_decimal
                    beneficio.base_calculo = base_calculo
                    beneficio.base_calculo_personalizada = base_calculo_personalizada
                    # Campos de fornecedor/contato (existem apenas em BeneficioSalarial)
                    beneficio.fornecedor = fornecedor
                    beneficio.localizacao = localizacao
                    beneficio.horario_funcionamento = horario_funcionamento
                    beneficio.limite_uso = limite_uso
                    beneficio.documento_necessario = documento_necessario
                    beneficio.contato_responsavel = contato_responsavel
                    beneficio.telefone_contato = telefone_contato
                    beneficio.email_contato = email_contato
                    beneficio.observacoes = observacoes
                    beneficio.ativo = ativo
                    beneficio.save()
                    
                    messages.success(request, 'Benefício salarial atualizado com sucesso!')
                    return redirect('rh:beneficios_salariais')
                except ValueError as e:
                    messages.error(request, f'Erro nos dados: {str(e)}')
                except Exception as e:
                    messages.error(request, f'Erro ao salvar: {str(e)}')
        
        context = {
            'beneficio': beneficio,
            'tipo_choices': BeneficioSalarial.TIPO_CHOICES,
            'tipo_valor_choices': BeneficioSalarial.TIPO_VALOR_CHOICES,
            'base_calculo_choices': BeneficioSalarial.BASE_CALCULO_CHOICES,
        }
        
        return render(request, 'rh/salarios/beneficios/form.html', context)
        
    except BeneficioSalarial.DoesNotExist:
        messages.error(request, 'Benefício salarial não encontrado.')
        return redirect('rh:beneficios_salariais')

@login_required
def rh_beneficio_salarial_delete(request, beneficio_id):
    """Deletar benefício salarial"""
    try:
        beneficio = BeneficioSalarial.objects.get(id=beneficio_id)
        
        if request.method == 'POST':
            try:
                beneficio.delete()
                messages.success(request, 'Benefício salarial deletado com sucesso!')
                return redirect('rh:beneficios_salariais')
            except Exception as e:
                messages.error(request, f'Erro ao deletar benefício salarial: {str(e)}')
        
        context = {'beneficio': beneficio}
        return render(request, 'rh/salarios/beneficios/delete.html', context)
        
    except BeneficioSalarial.DoesNotExist:
        messages.error(request, 'Benefício salarial não encontrado.')
        return redirect('rh:beneficios_salariais')

@login_required
def rh_descontos_salariais(request):
    """Lista de descontos salariais"""
    descontos = DescontoSalarial.objects.filter(ativo=True).order_by('-data_criacao')
    
    # Paginação
    paginator = Paginator(descontos, 20)
    page_number = request.GET.get('page')
    descontos = paginator.get_page(page_number)
    
    context = {
        'page_obj': descontos,
    }
    
    return render(request, 'rh/salarios/descontos/main.html', context)

@login_required
def rh_desconto_salarial_add(request):
    """Adicionar novo desconto salarial"""
    if request.method == 'POST':
        try:
            # Obter dados do formulário
            nome = request.POST.get('nome')
            tipo = request.POST.get('tipo')
            tipo_valor = request.POST.get('tipo_valor')
            valor_raw = request.POST.get('valor')
            base_calculo = request.POST.get('base_calculo')
            base_calculo_personalizada = request.POST.get('base_calculo_personalizada', '')
            vmin_raw = request.POST.get('valor_minimo_isencao', '0')
            vmax_raw = request.POST.get('valor_maximo_isencao', '0')
            aplicar_automaticamente = request.POST.get('aplicar_automaticamente') == 'on'
            descricao = request.POST.get('descricao', '')
            observacoes = request.POST.get('observacoes', '')
            ativo = request.POST.get('ativo') == 'on'

            # Validações básicas
            if not all([nome, tipo, tipo_valor, valor_raw, base_calculo]):
                messages.error(request, 'Nome, tipo, tipo de valor, valor e base de cálculo são obrigatórios.')
                return redirect('rh:desconto_salarial_add')

            # Normalizar separadores decimais (vírgula -> ponto)
            def norm(v):
                return (v or '').replace(',', '.')

            try:
                valor = Decimal(norm(valor_raw))
                vmin = Decimal(norm(vmin_raw)) if vmin_raw else Decimal('0')
                vmax = Decimal(norm(vmax_raw)) if vmax_raw else Decimal('0')
                if valor < 0 or vmin < 0 or vmax < 0:
                    raise ValueError('Valores não podem ser negativos')
            except (InvalidOperation, ValueError) as e:
                messages.error(request, f'Valores devem ser números válidos. {str(e)}')
                return redirect('rh:desconto_salarial_add')

            # Criar desconto
            DescontoSalarial.objects.create(
                nome=nome,
                tipo=tipo,
                tipo_valor=tipo_valor,
                valor=valor,
                base_calculo=base_calculo,
                base_calculo_personalizada=base_calculo_personalizada,
                valor_minimo_isencao=vmin,
                valor_maximo_isencao=vmax,
                aplicar_automaticamente=aplicar_automaticamente,
                descricao=descricao,
                observacoes=observacoes,
                ativo=ativo
            )

            messages.success(request, f'Desconto "{nome}" adicionado com sucesso!')
            return redirect('rh:descontos_salariais')

        except Exception as e:
            messages.error(request, f'Erro ao adicionar desconto: {str(e)}')
            return redirect('rh:desconto_salarial_add')
    
    # GET - Mostrar formulário
    context = {
        'tipo_choices': DescontoSalarial.TIPO_CHOICES,
        'tipo_valor_choices': DescontoSalarial.TIPO_VALOR_CHOICES,
        'base_calculo_choices': DescontoSalarial.BASE_CALCULO_CHOICES,
    }
    
    return render(request, 'rh/salarios/descontos/form.html', context)

@login_required
def rh_desconto_salarial_edit(request, desconto_id):
    """Editar desconto salarial"""
    try:
        desconto = DescontoSalarial.objects.get(id=desconto_id)
        
        if request.method == 'POST':
            nome = request.POST.get('nome')
            tipo = request.POST.get('tipo')
            tipo_valor = request.POST.get('tipo_valor')
            valor = request.POST.get('valor')
            base_calculo = request.POST.get('base_calculo')
            base_calculo_personalizada = request.POST.get('base_calculo_personalizada', '')
            valor_minimo_isencao = request.POST.get('valor_minimo_isencao', '0')
            valor_maximo_isencao = request.POST.get('valor_maximo_isencao', '0')
            aplicar_automaticamente = request.POST.get('aplicar_automaticamente') == 'on'
            observacoes = request.POST.get('observacoes', '')
            ativo = request.POST.get('ativo') == 'on'

            # Validações básicas
            if not all([nome, tipo, tipo_valor, valor, base_calculo]):
                messages.error(request, 'Nome, tipo, tipo de valor, valor e base de cálculo são obrigatórios.')
            else:
                try:
                    # Conversões seguras para Decimal
                    valor_decimal = Decimal(valor)
                    if valor_decimal < 0:
                        raise ValueError('Valor deve ser positivo')
                    vmin = Decimal(valor_minimo_isencao) if valor_minimo_isencao else Decimal('0')
                    vmax = Decimal(valor_maximo_isencao) if valor_maximo_isencao else Decimal('0')

                    # Atualizar campos existentes no modelo
                    desconto.nome = nome
                    desconto.tipo = tipo
                    desconto.tipo_valor = tipo_valor
                    desconto.valor = valor_decimal
                    desconto.base_calculo = base_calculo
                    desconto.base_calculo_personalizada = base_calculo_personalizada
                    desconto.valor_minimo_isencao = vmin
                    desconto.valor_maximo_isencao = vmax
                    desconto.aplicar_automaticamente = aplicar_automaticamente
                    desconto.observacoes = observacoes
                    desconto.ativo = ativo
                    desconto.save()

                    messages.success(request, 'Desconto salarial atualizado com sucesso!')
                    return redirect('rh:descontos_salariais')
                except (InvalidOperation, ValueError) as e:
                    messages.error(request, f'Erro nos dados: {str(e)}')
                except Exception as e:
                    messages.error(request, f'Erro ao salvar: {str(e)}')
        
        context = {
            'desconto': desconto,
            'tipo_choices': DescontoSalarial.TIPO_CHOICES,
            'tipo_valor_choices': DescontoSalarial.TIPO_VALOR_CHOICES,
            'base_calculo_choices': DescontoSalarial.BASE_CALCULO_CHOICES,
        }
        
        return render(request, 'rh/salarios/descontos/form.html', context)
        
    except DescontoSalarial.DoesNotExist:
        messages.error(request, 'Desconto salarial não encontrado.')
        return redirect('rh:descontos_salariais')

@login_required
def rh_desconto_salarial_delete(request, desconto_id):
    """Deletar desconto salarial"""
    try:
        desconto = DescontoSalarial.objects.get(id=desconto_id)
        
        if request.method == 'POST':
            try:
                desconto.delete()
                messages.success(request, 'Desconto salarial deletado com sucesso!')
                return redirect('rh:descontos_salariais')
            except Exception as e:
                messages.error(request, f'Erro ao deletar desconto salarial: {str(e)}')
        
        context = {'desconto': desconto}
        return render(request, 'rh/salarios/descontos/delete.html', context)
        
    except DescontoSalarial.DoesNotExist:
        messages.error(request, 'Desconto salarial não encontrado.')
        return redirect('rh:descontos_salariais')
