"""Views RH — presenças, calendário, feriados, horas extras."""
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
def rh_presencas(request):
    """Lista de presenças com resumo mensal por funcionário"""
    # Parâmetros de filtro
    mes = request.GET.get('mes', date.today().month)
    ano = request.GET.get('ano', date.today().year)
    funcionario_id = request.GET.get('funcionario')
    
    try:
        mes = int(mes)
        ano = int(ano)
    except (ValueError, TypeError):
        mes = date.today().month
        ano = date.today().year
    
    # Filtrar presenças do mês
    presencas = Presenca.objects.filter(
        data__year=ano,
        data__month=mes
    ).select_related('funcionario', 'tipo_presenca')
    
    if funcionario_id:
        presencas = presencas.filter(funcionario_id=funcionario_id)
    
    # Agrupar presenças por funcionário e tipo para resumo mensal
    resumo_funcionarios = presencas.values(
        'funcionario__id',
        'funcionario__nome_completo',
        'funcionario__codigo_funcionario'
    ).annotate(
        total_presente=Count(Case(When(tipo_presenca__codigo='PR', then=1), output_field=IntegerField())),
        total_ausente=Count(Case(When(tipo_presenca__codigo='AU', then=1), output_field=IntegerField())),
        total_falta_justificada=Count(Case(When(tipo_presenca__codigo='FJ', then=1), output_field=IntegerField())),
        total_atraso=Count(Case(When(tipo_presenca__codigo='AT', then=1), output_field=IntegerField())),
        total_licenca=Count(Case(When(tipo_presenca__codigo='LI', then=1), output_field=IntegerField())),
        total_ferias=Count(Case(When(tipo_presenca__codigo='FE', then=1), output_field=IntegerField())),
        total_registros=Count('id')
    ).order_by('funcionario__nome_completo')
    
    # Calcular dias úteis do mês (excluindo feriados)
    dias_uteis = calcular_dias_uteis(ano, mes)
    
    # Calcular estatísticas adicionais
    total_presencas = presencas.count()
    total_funcionarios = Funcionario.objects.filter(status='AT').count()
    
    # Resumo por tipo de presença
    resumo_por_tipo = presencas.values('tipo_presenca__codigo', 'tipo_presenca__nome').annotate(
        total=Count('id')
    ).order_by('-total')
    
    # Anos disponíveis (últimos 5 anos)
    anos_disponiveis = list(range(ano - 2, ano + 3))
    
    # Calcular horas extras do mês atual
    from meuprojeto.empresa.models_rh import HorasExtras
    from django.db.models import Sum
    
    horas_extras_mes = HorasExtras.objects.filter(
        data__year=ano,
        data__month=mes
    ).aggregate(
        total_horas=Sum('quantidade_horas'),
        total_valor=Sum('valor_total')
    )
    
    total_horas_extras_mes = float(horas_extras_mes['total_horas'] or 0)
    total_valor_horas_extras_mes = float(horas_extras_mes['total_valor'] or 0)
    
    # Criar dados para resumo anual (simulado)
    page_obj = []
    for mes_num in range(1, 13):
        mes_nome = calendar.month_name[mes_num]
        
        # Calcular horas extras para cada mês
        horas_extras_mes_anual = HorasExtras.objects.filter(
            data__year=ano,
            data__month=mes_num
        ).aggregate(
            total_horas=Sum('quantidade_horas'),
            total_valor=Sum('valor_total')
        )
        
        
        # Calcular presenças por tipo para o mês
        presencas_mes = Presenca.objects.filter(
            data__year=ano,
            data__month=mes_num
        ).values('tipo_presenca__codigo').annotate(
            total=Count('id')
        )
        
        # Inicializar contadores
        total_presente = 0
        total_ausente = 0
        total_falta_justificada = 0
        total_atraso = 0
        total_licenca = 0
        total_ferias = 0
        total_registros = 0
        
        # Processar presenças
        for presenca in presencas_mes:
            codigo = presenca['tipo_presenca__codigo']
            total = presenca['total']
            total_registros += total
            
            if codigo == 'PR':
                total_presente = total
            elif codigo == 'AU':
                total_ausente = total
            elif codigo == 'FJ':
                total_falta_justificada = total
            elif codigo == 'AT':
                total_atraso = total
            elif codigo == 'LI':
                total_licenca = total
            elif codigo == 'FE':
                total_ferias = total
        
        page_obj.append({
            'mes_num': mes_num,
            'mes_nome': mes_nome,
            'total_presente': total_presente,
            'total_ausente': total_ausente,
            'total_falta_justificada': total_falta_justificada,
            'total_atraso': total_atraso,
            'total_licenca': total_licenca,
            'total_ferias': total_ferias,
            'total_horas_extras': float(horas_extras_mes_anual['total_horas'] or 0),
            'total_valor_horas_extras': float(horas_extras_mes_anual['total_valor'] or 0),
            'total_registros': total_registros,
            'dias_uteis': len(calcular_dias_uteis(ano, mes_num)),
            'primeiro_dia': date(ano, mes_num, 1),
            'ultimo_dia': date(ano, mes_num, calendar.monthrange(ano, mes_num)[1])
        })
    
    from django.utils import timezone
    
    context = {
        'presencas': presencas,
        'resumo_funcionarios': resumo_funcionarios,
        'mes': mes,
        'ano': ano,
        'dias_uteis': len(dias_uteis),
        'funcionarios': Funcionario.objects.filter(status='AT').order_by('nome_completo'),
        'funcionario_id': funcionario_id,
        'total_presencas': total_presencas,
        'total_funcionarios': total_funcionarios,
        'resumo_por_tipo': resumo_por_tipo,
        'anos_disponiveis': anos_disponiveis,
        'page_obj': page_obj,
        'mes_atual': date.today().month,
        'total_horas_extras': total_horas_extras_mes,
        'total_valor_horas_extras': total_valor_horas_extras_mes,
        'timestamp': int(timezone.now().timestamp()),
    }
    
    return render(request, 'rh/presencas/main.html', context)

@login_required
def rh_calendario_presencas(request, template_name='rh/presencas/calendario.html'):
    """Calendário de presenças com marcação visual"""
    import calendar
    from datetime import datetime
    
    # Parâmetros
    mes = request.GET.get('mes', date.today().month)
    ano = request.GET.get('ano', date.today().year)
    funcionario_id = request.GET.get('funcionario')
    
    try:
        mes = int(mes)
        ano = int(ano)
    except (ValueError, TypeError):
        mes = date.today().month
        ano = date.today().year
    
    # Buscar presenças do mês
    presencas = Presenca.objects.filter(
        data__year=ano,
        data__month=mes
    ).select_related('funcionario', 'tipo_presenca')
    
    if funcionario_id:
        presencas = presencas.filter(funcionario_id=funcionario_id)
    
    # Criar dicionário de presenças por data
    presencas_por_data = {}
    for presenca in presencas:
        data_str = presenca.data.strftime('%Y-%m-%d')
        if data_str not in presencas_por_data:
            presencas_por_data[data_str] = []
        presencas_por_data[data_str].append(presenca)
    
    # Calcular dias úteis
    dias_uteis = calcular_dias_uteis(ano, mes)
    
    # Gerar dados dos dias do mês
    dias_detalhados = []
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    
    for dia in range(1, ultimo_dia + 1):
        data_atual = date(ano, mes, dia)
        dia_semana = data_atual.weekday()  # 0=segunda, 6=domingo
        e_fim_semana = dia_semana >= 5  # sábado=5, domingo=6
        
        dias_detalhados.append({
            'dia': dia,
            'dia_semana': dia_semana,
            'e_fim_semana': e_fim_semana,
            'data': data_atual
        })
    
    # Funcionários para exibir
    funcionarios_exibir = Funcionario.objects.filter(status='AT').order_by('nome_completo')
    if funcionario_id:
        funcionarios_exibir = funcionarios_exibir.filter(id=funcionario_id)
    
    # Criar dicionário de presenças para JavaScript
    presencas_dict = {}
    for presenca in presencas:
        chave = f"{presenca.funcionario.id}_{presenca.data.day}"
        presencas_dict[chave] = {
            'id': presenca.id,
            'tipo': presenca.tipo_presenca.codigo,
            'tipo_nome': presenca.tipo_presenca.nome,
            'tipo_cor': presenca.tipo_presenca.cor,
            'observacoes': presenca.observacoes or ''
        }
    
    
    # Lista de meses
    meses = [
        'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
        'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'
    ]
    
    # Lista de anos (últimos 5 anos + próximos 2)
    anos = list(range(ano - 5, ano + 3))
    
    import json
    from django.core.serializers import serialize
    
    # Serializar os tipos de presença para JSON
    tipos_presenca = TipoPresenca.objects.all()
    tipos_presenca_json = json.dumps([{
        'id': tp.id,
        'nome': tp.nome,
        'codigo': tp.codigo,
        'cor': tp.cor or '#cccccc',
        'desconta_salario': tp.desconta_salario,
        'ativo': tp.ativo
    } for tp in tipos_presenca])
    
    # Buscar feriados do mês
    feriados = Feriado.objects.filter(
        data__year=ano,
        data__month=mes,
        ativo=True
    ).order_by('data')
    
    # Criar dicionário de feriados para JavaScript
    feriados_dict = {}
    for feriado in feriados:
        chave = f"feriado_{feriado.data.day}"
        feriados_dict[chave] = {
            'nome': feriado.nome,
            'tipo': feriado.tipo,
            'descricao': feriado.descricao or ''
        }
    
    context = {
        'mes': mes,
        'ano': ano,
        'mes_nome': meses[mes - 1],
        'mes_atual': date.today().month,
        'ano_atual': date.today().year,
        'presencas_por_data': presencas_por_data,
        'presencas_dict': json.dumps(presencas_dict),
        'dias_uteis': dias_uteis,
        'dias_detalhados': dias_detalhados,
        'funcionarios': Funcionario.objects.filter(status='AT').order_by('nome_completo'),
        'funcionarios_exibir': funcionarios_exibir,
        'funcionario_id': funcionario_id,
        'tipos_presenca': tipos_presenca,
        'tipos_presenca_json': tipos_presenca_json,
        'feriados': feriados,
        'feriados_dict': json.dumps(feriados_dict),
        'meses': meses,
        'anos': anos,
    }
    
    return render(request, template_name, context)

@login_required
def rh_calendario_debug(request):
    """Calendário de presenças - versão debug"""
    import calendar
    from datetime import datetime, date
    
    # Parâmetros
    mes = request.GET.get('mes', date.today().month)
    ano = request.GET.get('ano', date.today().year)
    funcionario_id = request.GET.get('funcionario')
    
    try:
        mes = int(mes)
        ano = int(ano)
    except (ValueError, TypeError):
        mes = date.today().month
        ano = date.today().year
    
    # Buscar presenças do mês
    presencas = Presenca.objects.filter(
        data__year=ano,
        data__month=mes
    ).select_related('funcionario', 'tipo_presenca')
    
    if funcionario_id:
        presencas = presencas.filter(funcionario_id=funcionario_id)
    
    # Gerar dados dos dias do mês
    dias_detalhados = []
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    
    for dia in range(1, ultimo_dia + 1):
        data_atual = date(ano, mes, dia)
        dia_semana = data_atual.weekday()  # 0=segunda, 6=domingo
        e_fim_semana = dia_semana >= 5  # sábado=5, domingo=6
        
        dias_detalhados.append({
            'dia': dia,
            'dia_semana': dia_semana,
            'e_fim_semana': e_fim_semana,
            'data': data_atual
        })
    
    # Funcionários para exibir
    funcionarios_exibir = Funcionario.objects.filter(status='AT').order_by('nome_completo')
    if funcionario_id:
        funcionarios_exibir = funcionarios_exibir.filter(id=funcionario_id)
    
    # Criar dicionário de presenças para JavaScript
    presencas_dict = {}
    for presenca in presencas:
        chave = f"{presenca.funcionario.id}_{presenca.data.day}"
        presencas_dict[chave] = {
            'id': presenca.id,
            'tipo': presenca.tipo_presenca.codigo,
            'tipo_nome': presenca.tipo_presenca.nome,
            'tipo_cor': presenca.tipo_presenca.cor,
            'observacoes': presenca.observacoes or ''
        }
    
    import json
    
    context = {
        'mes': mes,
        'ano': ano,
        'presencas_dict': json.dumps(presencas_dict),
        'dias_detalhados': dias_detalhados,
        'funcionarios': Funcionario.objects.filter(status='AT').order_by('nome_completo'),
        'funcionarios_exibir': funcionarios_exibir,
        'funcionario_id': funcionario_id,
    }
    
    return render(request, 'rh/presencas/calendario_debug.html', context)

@login_required
def rh_salvar_presenca_calendario(request):
    """Salvar presença via AJAX no calendário"""
    if request.method == 'POST':
        try:
            import json
            import logging
            logger = logging.getLogger(__name__)
            
            # Verificar se é JSON
            if request.content_type == 'application/json':
                data = json.loads(request.body)
                funcionario_id = data.get('funcionario_id')
                dia = data.get('dia')
                mes = data.get('mes')
                ano = data.get('ano')
                tipo_presenca_id = data.get('tipo_presenca_id')
                observacoes = data.get('observacoes', '')
                
                # Log dos dados recebidos
                logger.info(f"Dados recebidos: funcionario_id={funcionario_id}, dia={dia}, mes={mes}, ano={ano}, tipo_presenca_id={tipo_presenca_id}, observacoes={observacoes}")
                
                # Construir data da presença
                data_presenca = date(ano, mes, dia)
            else:
                # Fallback para form data
                funcionario_id = request.POST.get('funcionario_id')
                data_presenca = request.POST.get('data')
                tipo_presenca_id = request.POST.get('tipo_presenca_id')
                observacoes = request.POST.get('observacoes', '')
            
            funcionario = get_object_or_404(Funcionario, id=funcionario_id)
            tipo_presenca = get_object_or_404(TipoPresenca, id=tipo_presenca_id)
            
            # Verificar se já existe presença para esta data
            presenca_existente = Presenca.objects.filter(
                funcionario=funcionario,
                data=data_presenca
            ).first()
            
            if presenca_existente:
                # Atualizar presença existente
                presenca_existente.tipo_presenca = tipo_presenca
                presenca_existente.observacoes = observacoes
                presenca_existente.save()
                logger.info(f"Presença atualizada: ID={presenca_existente.id}")
                action = 'updated'
            else:
                # Criar nova presença
                presenca_existente = Presenca.objects.create(
                    funcionario=funcionario,
                    data=data_presenca,
                    tipo_presenca=tipo_presenca,
                    observacoes=observacoes
                )
                logger.info(f"Presença criada: ID={presenca_existente.id}")
                action = 'created'
            
            return JsonResponse({
                'success': True,
                'action': action,
                'presenca_id': presenca_existente.id,
                'tipo_codigo': tipo_presenca.codigo,
                'tipo_nome': tipo_presenca.nome,
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({'success': False, 'error': 'Método não permitido'})

@login_required
def rh_remover_presenca_calendario(request):
    """Remover presença via AJAX do calendário"""
    if request.method == 'POST':
        try:
            import json
            
            # Verificar se é JSON
            if request.content_type == 'application/json':
                data = json.loads(request.body)
                presenca_id = data.get('presenca_id')
            else:
                # Fallback para form data
                presenca_id = request.POST.get('presenca_id')
            
            presenca = get_object_or_404(Presenca, id=presenca_id)
            presenca.delete()
            
            return JsonResponse({'success': True})
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({'success': False, 'error': 'Método não permitido'})

@login_required
def rh_marcar_dias_uteis(request):
    """Marcar automaticamente todos os dias úteis como presente"""
    if request.method == 'POST':
        try:
            funcionario_id = request.POST.get('funcionario_id')
            mes = int(request.POST.get('mes'))
            ano = int(request.POST.get('ano'))
            
            funcionario = get_object_or_404(Funcionario, id=funcionario_id)
            tipo_presente = get_object_or_404(TipoPresenca, codigo='PR')
            
            # Calcular dias úteis do mês
            dias_uteis = calcular_dias_uteis(ano, mes)
            
            presencas_criadas = 0
            presencas_atualizadas = 0
            
            for dia in dias_uteis:
                presenca_existente = Presenca.objects.filter(
                    funcionario=funcionario,
                    data=dia
                ).first()
                
                if presenca_existente:
                    presenca_existente.tipo_presenca = tipo_presente
                    presenca_existente.observacoes = "Marcação automática - Dias úteis"
                    presenca_existente.save()
                    presencas_atualizadas += 1
                else:
                    Presenca.objects.create(
                        funcionario=funcionario,
                        data=dia,
                        tipo_presenca=tipo_presente,
                        observacoes="Marcação automática - Dias úteis"
                    )
                    presencas_criadas += 1
            
            return JsonResponse({
                'success': True,
                'criadas': presencas_criadas,
                'atualizadas': presencas_atualizadas,
                'total_dias': len(dias_uteis)
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({'success': False, 'error': 'Método não permitido'})

@login_required
def rh_marcar_finais_semana(request):
    """Marcar automaticamente finais de semana"""
    if request.method == 'POST':
        try:
            funcionario_id = request.POST.get('funcionario_id')
            mes = int(request.POST.get('mes'))
            ano = int(request.POST.get('ano'))
            tipo_codigo = request.POST.get('tipo_codigo', 'AU')
            
            funcionario = get_object_or_404(Funcionario, id=funcionario_id)
            tipo_presenca = get_object_or_404(TipoPresenca, codigo=tipo_codigo)
            
            # Calcular finais de semana do mês
            finais_semana = calcular_finais_semana(ano, mes)
            
            presencas_criadas = 0
            presencas_atualizadas = 0
            
            for dia in finais_semana:
                presenca_existente = Presenca.objects.filter(
                    funcionario=funcionario,
                    data=dia
                ).first()
                
                if presenca_existente:
                    presenca_existente.tipo_presenca = tipo_presenca
                    presenca_existente.observacoes = "Marcação automática - Finais de semana"
                    presenca_existente.save()
                    presencas_atualizadas += 1
                else:
                    Presenca.objects.create(
                        funcionario=funcionario,
                        data=dia,
                        tipo_presenca=tipo_presenca,
                        observacoes="Marcação automática - Finais de semana"
                    )
                    presencas_criadas += 1
            
            return JsonResponse({
                'success': True,
                'criadas': presencas_criadas,
                'atualizadas': presencas_atualizadas,
                'total_dias': len(finais_semana)
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({'success': False, 'error': 'Método não permitido'})

@login_required
def rh_detalhes_mes(request, ano, mes):
    """Página de detalhes específicos de um mês - versão debug"""
    try:
        # Validar parâmetros
        if not (1 <= mes <= 12):
            raise ValueError("Mês inválido")
        if ano < 2000 or ano > 2100:
            raise ValueError("Ano inválido")
        
        # Buscar presenças do mês com horas extras relacionadas
        presencas = Presenca.objects.filter(
            data__year=ano,
            data__month=mes
        ).select_related('funcionario', 'tipo_presenca').prefetch_related('funcionario__horas_extras')
        
        # Calcular estatísticas básicas
        total_presencas = presencas.count()
        total_funcionarios = Funcionario.objects.filter(status='AT').count()
        dias_uteis = calcular_dias_uteis(ano, mes)
        
        # Resumo por tipo de presença (simplificado)
        resumo_tipos = []
        for presenca in presencas:
            tipo_nome = presenca.tipo_presenca.nome if presenca.tipo_presenca else 'N/A'
            tipo_codigo = presenca.tipo_presenca.codigo if presenca.tipo_presenca else 'N/A'
            
            # Procurar se já existe no resumo
            encontrado = False
            for item in resumo_tipos:
                if item['tipo_presenca__nome'] == tipo_nome:
                    item['total'] += 1
                    encontrado = True
                    break
            
            if not encontrado:
                resumo_tipos.append({
                    'tipo_presenca__nome': tipo_nome,
                    'tipo_presenca__codigo': tipo_codigo,
                    'total': 1
                })
        
        # Resumo por funcionário (simplificado)
        resumo_funcionarios = []
        funcionarios_processados = set()
        
        for presenca in presencas:
            func_id = presenca.funcionario.id
            if func_id not in funcionarios_processados:
                funcionarios_processados.add(func_id)
                
                # Contar presenças por tipo para este funcionário
                presencas_func = presencas.filter(funcionario_id=func_id)
                total_presente = presencas_func.filter(tipo_presenca__codigo='PR').count()
                total_ausente = presencas_func.filter(tipo_presenca__codigo='AU').count()
                total_falta_justificada = presencas_func.filter(tipo_presenca__codigo='FJ').count()
                total_atraso = presencas_func.filter(tipo_presenca__codigo='AT').count()
                total_licenca = presencas_func.filter(tipo_presenca__codigo='LI').count()
                total_ferias = presencas_func.filter(tipo_presenca__codigo='FE').count()
                # Calcular horas extras do modelo HorasExtras para este funcionário
                total_horas_extras = HorasExtras.objects.filter(
                    funcionario_id=func_id,
                    data__year=ano,
                    data__month=mes
                ).aggregate(
                    total=Sum('quantidade_horas')
                )['total'] or 0
                total_registros = presencas_func.count()
                
                resumo_funcionarios.append({
                    'funcionario__id': func_id,
                    'funcionario__nome_completo': presenca.funcionario.nome_completo,
                    'funcionario__codigo_funcionario': presenca.funcionario.codigo_funcionario,
                    'total_presente': total_presente,
                    'total_ausente': total_ausente,
                    'total_falta_justificada': total_falta_justificada,
                    'total_atraso': total_atraso,
                    'total_licenca': total_licenca,
                    'total_ferias': total_ferias,
                    'total_horas_extras': total_horas_extras,
                    'total_registros': total_registros,
                })
        
        # Calcular total de horas extras do mês (usando modelo HorasExtras)
        total_horas_extras = HorasExtras.objects.filter(
            data__year=ano,
            data__month=mes
        ).aggregate(
            total=Sum('quantidade_horas')
        )['total'] or 0
        
        context = {
            'ano': ano,
            'mes': mes,
            'mes_nome': calendar.month_name[mes],
            'presencas_mes': presencas,
            'resumo_por_tipo': resumo_tipos,
            'resumo_por_funcionario': resumo_funcionarios,
            'total_presencas': total_presencas,
            'total_funcionarios': total_funcionarios,
            'dias_uteis': len(dias_uteis),
            'total_horas_extras': total_horas_extras,
            'resumo_mes': {
                'total_registros': total_presencas,
                'total_horas_extras': total_horas_extras,
            },
            'primeiro_dia': date(ano, mes, 1),
            'ultimo_dia': date(ano, mes, calendar.monthrange(ano, mes)[1]),
        }
        
        return render(request, 'rh/presencas/detalhes_mes.html', context)
        
    except Exception as e:
        # Log do erro para debug
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Erro na view rh_detalhes_mes: {str(e)}")
        
        messages.error(request, f"Erro ao carregar detalhes: {str(e)}")
        return redirect('rh:presencas')

@login_required
def rh_feriados(request):
    """Lista de feriados com filtros"""
    # Parâmetros de filtro
    ano = request.GET.get('ano', date.today().year)
    tipo = request.GET.get('tipo', '')
    
    try:
        ano = int(ano)
    except (ValueError, TypeError):
        ano = date.today().year
    
    # Query base
    feriados = Feriado.objects.filter(data__year=ano)
    
    if tipo:
        feriados = feriados.filter(tipo=tipo)
    
    feriados = feriados.order_by('data')
    
    # Paginação
    paginator = Paginator(feriados, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Gerar opções para os filtros
    anos_choices = list(range(2020, 2030))  # Últimos 10 anos + próximos 5
    tipos_choices = Feriado.TIPO_CHOICES
    
    context = {
        'page_obj': page_obj,
        'feriados': page_obj,  # Para compatibilidade
        'ano': ano,
        'tipo': tipo,
        'tipos_feriado': Feriado.TIPO_CHOICES,
        'tipos_choices': tipos_choices,
        'anos_choices': anos_choices,
        'tipo_filter': tipo,
        'ano_filter': ano,
    }
    
    return render(request, 'rh/feriados/main.html', context)

@login_required
def rh_feriado_add(request):
    """Adicionar novo feriado"""
    if request.method == 'POST':
        try:
            feriado = Feriado(
                nome=request.POST['nome'],
                data=request.POST['data'],
                tipo=request.POST['tipo'],
                descricao=request.POST.get('descricao', ''),
                ativo=request.POST.get('ativo') == 'on'
            )
            feriado.full_clean()
            feriado.save()
            messages.success(request, 'Feriado adicionado com sucesso!')
            return redirect('rh:feriados')
        except ValidationError as e:
            messages.error(request, f'Erro de validação: {e}')
        except Exception as e:
            messages.error(request, f'Erro ao adicionar feriado: {e}')
    
    context = {
        'tipos_feriado': Feriado.TIPO_CHOICES,
    }
    
    return render(request, 'rh/feriados/form.html', context)

@login_required
def rh_feriado_edit(request, feriado_id):
    """Editar feriado existente"""
    feriado = get_object_or_404(Feriado, id=feriado_id)
    
    if request.method == 'POST':
        try:
            feriado.nome = request.POST['nome']
            feriado.data = request.POST['data']
            feriado.tipo = request.POST['tipo']
            feriado.descricao = request.POST.get('descricao', '')
            feriado.ativo = request.POST.get('ativo') == 'on'
            feriado.full_clean()
            feriado.save()
            messages.success(request, 'Feriado atualizado com sucesso!')
            return redirect('rh:feriados')
        except ValidationError as e:
            messages.error(request, f'Erro de validação: {e}')
        except Exception as e:
            messages.error(request, f'Erro ao atualizar feriado: {e}')
    
    context = {
        'feriado': feriado,
        'tipos_feriado': Feriado.TIPO_CHOICES,
    }
    
    return render(request, 'rh/feriados/form.html', context)

@login_required
def rh_feriado_delete(request, feriado_id):
    """Excluir feriado"""
    feriado = get_object_or_404(Feriado, id=feriado_id)
    
    if request.method == 'POST':
        try:
            feriado.delete()
            messages.success(request, 'Feriado excluído com sucesso!')
            return redirect('rh:feriados')
        except Exception as e:
            messages.error(request, f'Erro ao excluir feriado: {e}')
    
    context = {
        'feriado': feriado,
    }
    
    return render(request, 'rh/feriados/delete.html', context)

def calcular_dias_uteis(ano, mes):
    """Calcula os dias úteis de um mês (segunda a sexta, excluindo feriados)"""
    # Obter todos os dias do mês
    dias_mes = []
    for dia in range(1, calendar.monthrange(ano, mes)[1] + 1):
        data = date(ano, mes, dia)
        # Verificar se é dia útil (segunda=0, sexta=4)
        if data.weekday() < 5:  # 0-4 = segunda a sexta
            dias_mes.append(data)
    
    # Remover feriados ativos
    feriados = Feriado.objects.filter(
        data__year=ano,
        data__month=mes,
        ativo=True
    ).values_list('data', flat=True)
    
    dias_uteis = [dia for dia in dias_mes if dia not in feriados]
    return dias_uteis

def calcular_finais_semana(ano, mes):
    """Calcula os finais de semana de um mês (sábado e domingo)"""
    finais_semana = []
    for dia in range(1, calendar.monthrange(ano, mes)[1] + 1):
        data = date(ano, mes, dia)
        # Verificar se é final de semana (sábado=5, domingo=6)
        if data.weekday() >= 5:  # 5-6 = sábado e domingo
            finais_semana.append(data)
    return finais_semana

@login_required
def rh_presenca_add(request):
    """Adicionar nova presença"""
    if request.method == 'POST':
        try:
            funcionario_id = request.POST.get('funcionario')
            data = request.POST.get('data')
            tipo_presenca_id = request.POST.get('tipo_presenca')
            observacoes = request.POST.get('observacoes', '')
            
            # Validar dados
            if not all([funcionario_id, data, tipo_presenca_id]):
                messages.error(request, 'Todos os campos obrigatórios devem ser preenchidos.')
                return redirect('rh:presenca_add')
            
            # Obter objetos
            funcionario = get_object_or_404(Funcionario, id=funcionario_id)
            tipo_presenca = get_object_or_404(TipoPresenca, id=tipo_presenca_id)
            
            
            # Verificar se já existe presença para esta data
            presenca_existente = Presenca.objects.filter(
                funcionario=funcionario,
                data=data
            ).first()
            
            if presenca_existente:
                messages.warning(request, f'Já existe uma presença registrada para {funcionario.nome_completo} em {data}.')
                return redirect('rh:presenca_edit', id=presenca_existente.id)
            
            # Criar presença
            presenca = Presenca.objects.create(
                funcionario=funcionario,
                data=data,
                tipo_presenca=tipo_presenca,
                observacoes=observacoes
            )
            
            messages.success(request, f'Presença registrada com sucesso para {funcionario.nome_completo} em {data}.')
            return redirect('rh:presencas')
            
        except Exception as e:
            messages.error(request, f'Erro ao registrar presença: {str(e)}')
            return redirect('rh:presenca_add')
    
    # GET - Mostrar formulário
    funcionarios = Funcionario.objects.filter(status='AT').order_by('nome_completo')
    tipos_presenca = TipoPresenca.objects.filter(ativo=True).order_by('nome')
    
    context = {
        'funcionarios': funcionarios,
        'tipos_presenca': tipos_presenca,
    }
    
    return render(request, 'rh/presencas/form.html', context)

@login_required
def rh_presenca_detail(request, id):
    """Ver detalhes de uma presença específica"""
    try:
        presenca = Presenca.objects.select_related('funcionario', 'tipo_presenca').get(id=id)
    except Presenca.DoesNotExist:
        messages.error(request, 'Presença não encontrada.')
        return redirect('rh:presencas')
    
    context = {
        'presenca': presenca,
    }
    
    return render(request, 'rh/presencas/detail.html', context)

@login_required
def rh_presenca_edit(request, id):
    """Editar presença existente"""
    presenca = get_object_or_404(Presenca, id=id)
    
    if request.method == 'POST':
        try:
            funcionario_id = request.POST.get('funcionario')
            data = request.POST.get('data')
            tipo_presenca_id = request.POST.get('tipo_presenca')
            observacoes = request.POST.get('observacoes', '')
            
            # Validar dados
            if not all([funcionario_id, data, tipo_presenca_id]):
                messages.error(request, 'Todos os campos obrigatórios devem ser preenchidos.')
                return redirect('rh:presenca_edit', id=id)
            
            # Obter objetos
            funcionario = get_object_or_404(Funcionario, id=funcionario_id)
            tipo_presenca = get_object_or_404(TipoPresenca, id=tipo_presenca_id)
            
            
            # Verificar se já existe outra presença para esta data (exceto a atual)
            presenca_existente = Presenca.objects.filter(
                funcionario=funcionario,
                data=data
            ).exclude(id=id).first()
            
            if presenca_existente:
                messages.warning(request, f'Já existe uma presença registrada para {funcionario.nome_completo} em {data}.')
                return redirect('rh:presenca_edit', id=id)
            
            # Atualizar presença
            presenca.funcionario = funcionario
            presenca.data = data
            presenca.tipo_presenca = tipo_presenca
            presenca.observacoes = observacoes
            presenca.save()
            
            messages.success(request, f'Presença atualizada com sucesso para {funcionario.nome_completo} em {data}.')
            return redirect('rh:presencas')
            
        except Exception as e:
            messages.error(request, f'Erro ao atualizar presença: {str(e)}')
            return redirect('rh:presenca_edit', id=id)
    
    # GET - Mostrar formulário preenchido
    funcionarios = Funcionario.objects.filter(status='AT').order_by('nome_completo')
    tipos_presenca = TipoPresenca.objects.filter(ativo=True).order_by('nome')
    
    context = {
        'presenca': presenca,
        'funcionarios': funcionarios,
        'tipos_presenca': tipos_presenca,
    }
    
    return render(request, 'rh/presencas/form.html', context)

@login_required
def rh_presenca_delete(request, id):
    """Excluir presença"""
    presenca = get_object_or_404(Presenca, id=id)
    
    if request.method == 'POST':
        try:
            funcionario_nome = presenca.funcionario.nome_completo
            data = presenca.data
            presenca.delete()
            
            messages.success(request, f'Presença de {funcionario_nome} em {data} excluída com sucesso.')
            return redirect('rh:presencas')
            
        except Exception as e:
            messages.error(request, f'Erro ao excluir presença: {str(e)}')
            return redirect('rh:presencas')
    
    context = {
        'presenca': presenca,
    }
    
    return render(request, 'rh/presencas/delete.html', context)

@login_required
def rh_horas_extras(request):
    """Gestão completa de horas extras dos funcionários usando modelo HorasExtras"""
    if request.method == 'POST':
        try:
            funcionario_id = request.POST.get('funcionario')
            data = request.POST.get('data')
            hora_inicio = request.POST.get('hora_inicio')
            hora_fim = request.POST.get('hora_fim')
            observacoes = request.POST.get('observacoes', '')
            
            # Novos campos separados
            horas_diurnas = Decimal(request.POST.get('horas_diurnas', 0) or 0)
            horas_noturnas = Decimal(request.POST.get('horas_noturnas', 0) or 0)
            horas_extraordinarias = Decimal(request.POST.get('horas_extraordinarias', 0) or 0)
            
            # Validar dados obrigatórios (incluindo funcionário)
            if not all([funcionario_id, data, hora_inicio, hora_fim]):
                messages.error(request, 'Todos os campos obrigatórios devem ser preenchidos.')
                return redirect('rh:horas_extras')
            
            # Verificar se pelo menos um tipo de horas foi preenchido
            if horas_diurnas == 0 and horas_noturnas == 0 and horas_extraordinarias == 0:
                messages.error(request, 'Pelo menos um tipo de horas extras deve ser preenchido.')
                return redirect('rh:horas_extras')
            
            # Obter funcionário específico
            try:
                funcionario = Funcionario.objects.get(id=funcionario_id, status='AT')
            except Funcionario.DoesNotExist:
                messages.error(request, 'Funcionário não encontrado ou inativo.')
                return redirect('rh:horas_extras')
            
            # Calcular valor base dinamicamente baseado no funcionário
            remuneracao_teorica = funcionario.get_remuneracao_por_hora_teorica()
            if remuneracao_teorica and remuneracao_teorica.get('remuneracao_por_hora_teorica'):
                valor_base = remuneracao_teorica['remuneracao_por_hora_teorica']
            else:
                # Fallback: usar salário atual dividido por 160 horas mensais
                salario_atual = funcionario.get_salario_atual()
                valor_base = float(salario_atual) / 160 if salario_atual else 0
            
            registros_criados = []
            
            # Criar registros para o funcionário específico
            # Criar registro para horas diurnas se houver
            if horas_diurnas > 0:
                valor_por_hora_diurno = valor_base * Decimal('0.5')  # 50%
                valor_total_diurno = horas_diurnas * valor_por_hora_diurno
                
                HorasExtras.objects.create(
                    funcionario=funcionario,
                    data=data,
                    tipo='DI',
                    hora_inicio=hora_inicio,
                    hora_fim=hora_fim,
                    quantidade_horas=horas_diurnas,
                    valor_por_hora=valor_por_hora_diurno,
                    valor_total=valor_total_diurno,
                    observacoes=f"{observacoes} (Diurno)".strip(),
                    criado_por=request.user
                )
                registros_criados.append(f"{funcionario.nome_completo} - Diurno: {horas_diurnas}h - {valor_total_diurno:.2f} MT")
            
            # Criar registro para horas noturnas se houver
            if horas_noturnas > 0:
                valor_por_hora_noturno = valor_base * Decimal('1.0')  # 100%
                valor_total_noturno = horas_noturnas * valor_por_hora_noturno
                
                HorasExtras.objects.create(
                    funcionario=funcionario,
                    data=data,
                    tipo='NO',
                    hora_inicio=hora_inicio,
                    hora_fim=hora_fim,
                    quantidade_horas=horas_noturnas,
                    valor_por_hora=valor_por_hora_noturno,
                    valor_total=valor_total_noturno,
                    observacoes=f"{observacoes} (Noturno)".strip(),
                    criado_por=request.user
                )
                registros_criados.append(f"{funcionario.nome_completo} - Noturno: {horas_noturnas}h - {valor_total_noturno:.2f} MT")
            
            # Criar registro para horas extraordinárias se houver
            if horas_extraordinarias > 0:
                valor_por_hora_extraordinario = valor_base * Decimal('1.0')  # 100%
                valor_total_extraordinario = horas_extraordinarias * valor_por_hora_extraordinario
                
                HorasExtras.objects.create(
                    funcionario=funcionario,
                    data=data,
                    tipo='EX',
                    hora_inicio=hora_inicio,
                    hora_fim=hora_fim,
                    quantidade_horas=horas_extraordinarias,
                    valor_por_hora=valor_por_hora_extraordinario,
                    valor_total=valor_total_extraordinario,
                    observacoes=f"{observacoes} (Extraordinário)".strip(),
                    criado_por=request.user
                )
                registros_criados.append(f"{funcionario.nome_completo} - Extraordinário: {horas_extraordinarias}h - {valor_total_extraordinario:.2f} MT")
            
            # Calcular total geral
            total_horas = horas_diurnas + horas_noturnas + horas_extraordinarias
            total_valor = (horas_diurnas * valor_base * Decimal('0.5') + 
                          horas_noturnas * valor_base * Decimal('1.0') + 
                          horas_extraordinarias * valor_base * Decimal('1.0'))
            
            mensagem = f'Horas extras registradas para {funcionario.nome_completo} em {data}:\n'
            mensagem += '\n'.join(registros_criados)
            mensagem += f'\n\nTotal: {total_horas}h - {total_valor:.2f} MT'
            
            messages.success(request, mensagem)
            return redirect('rh:horas_extras')
            
        except Exception as e:
            messages.error(request, f'Erro ao registrar horas extras: {str(e)}')
            return redirect('rh:horas_extras')
    
    # GET - Mostrar formulário
    funcionarios = Funcionario.objects.filter(status='AT').order_by('nome_completo')
    
    # Obter horas extras recentes
    horas_extras_recentes = HorasExtras.objects.select_related(
        'funcionario', 'aprovado_por', 'criado_por'
    ).order_by('-data', '-data_criacao')[:10]
    
    context = {
        'funcionarios': funcionarios,
        'horas_extras_recentes': horas_extras_recentes,
        'tipos_choices': HorasExtras.TIPO_CHOICES,
    }
    
    return render(request, 'rh/presencas/horas_extras_form.html', context)

@login_required
def rh_horas_extras_lista(request):
    """Lista todas as horas extras registradas com opções de edição e exclusão"""
    # Parâmetros de filtro
    mes = request.GET.get('mes', date.today().month)
    ano = request.GET.get('ano', date.today().year)
    funcionario_id = request.GET.get('funcionario')
    tipo = request.GET.get('tipo')
    
    try:
        mes = int(mes)
        ano = int(ano)
    except (ValueError, TypeError):
        mes = date.today().month
        ano = date.today().year
    
    # Filtrar horas extras
    horas_extras = HorasExtras.objects.filter(
        data__year=ano,
        data__month=mes
    ).select_related('funcionario', 'criado_por', 'aprovado_por').order_by('-data', '-id')
    
    if funcionario_id:
        horas_extras = horas_extras.filter(funcionario_id=funcionario_id)
    
    if tipo:
        horas_extras = horas_extras.filter(tipo=tipo)
    
    # Calcular totais
    total_horas = horas_extras.aggregate(
        total_horas=Sum('quantidade_horas'),
        total_valor=Sum('valor_total')
    )
    
    # Anos disponíveis
    anos_disponiveis = list(range(ano - 2, ano + 3))
    
    # Funcionários para filtro
    funcionarios = Funcionario.objects.filter(status='AT').order_by('nome_completo')
    
    # Tipos de horas extras
    tipos_horas_extras = [
        ('DI', 'Diurno'),
        ('NO', 'Noturno'),
        ('EX', 'Extraordinário'),
    ]
    
    context = {
        'horas_extras': horas_extras,
        'mes': mes,
        'ano': ano,
        'funcionario_id': funcionario_id,
        'tipo': tipo,
        'total_horas': float(total_horas['total_horas'] or 0),
        'total_valor': float(total_horas['total_valor'] or 0),
        'anos_disponiveis': anos_disponiveis,
        'funcionarios': funcionarios,
        'tipos_horas_extras': tipos_horas_extras,
    }
    
    return render(request, 'rh/presencas/horas_extras_lista.html', context)

@login_required
def rh_horas_extras_editar(request, id):
    """Editar horas extras existentes"""
    horas_extras = get_object_or_404(HorasExtras, id=id)
    
    if request.method == 'POST':
        try:
            funcionario_id = request.POST.get('funcionario')
            data = request.POST.get('data')
            hora_inicio = request.POST.get('hora_inicio')
            hora_fim = request.POST.get('hora_fim')
            observacoes = request.POST.get('observacoes', '')
            
            # Novos campos separados
            horas_diurnas = Decimal(request.POST.get('horas_diurnas', 0) or 0)
            horas_noturnas = Decimal(request.POST.get('horas_noturnas', 0) or 0)
            horas_extraordinarias = Decimal(request.POST.get('horas_extraordinarias', 0) or 0)
            
            # Validar dados obrigatórios
            if not all([funcionario_id, data, hora_inicio, hora_fim]):
                messages.error(request, 'Todos os campos obrigatórios devem ser preenchidos.')
                return redirect('rh:horas_extras_editar', id=id)
            
            # Verificar se pelo menos um tipo de horas foi preenchido
            if horas_diurnas == 0 and horas_noturnas == 0 and horas_extraordinarias == 0:
                messages.error(request, 'Pelo menos um tipo de horas extras deve ser preenchido.')
                return redirect('rh:horas_extras_editar', id=id)
            
            # Obter funcionário
            funcionario = get_object_or_404(Funcionario, id=funcionario_id)
            
            # Calcular valor base do funcionário (assumindo 726 MT para CONS001)
            valor_base = 726  # Este valor deve ser obtido dinamicamente
            
            # Deletar registros existentes para esta data e funcionário
            HorasExtras.objects.filter(
                funcionario=funcionario,
                data=data
            ).delete()
            
            registros_criados = []
            
            # Criar registro para horas diurnas se houver
            if horas_diurnas > 0:
                valor_por_hora_diurno = valor_base * Decimal('0.5')  # 50%
                valor_total_diurno = horas_diurnas * valor_por_hora_diurno
                
                HorasExtras.objects.create(
                    funcionario=funcionario,
                    data=data,
                    tipo='DI',
                    hora_inicio=hora_inicio,
                    hora_fim=hora_fim,
                    quantidade_horas=horas_diurnas,
                    valor_por_hora=valor_por_hora_diurno,
                    valor_total=valor_total_diurno,
                    observacoes=f"{observacoes} (Diurno)".strip(),
                    criado_por=request.user
                )
                registros_criados.append(f"Diurno: {horas_diurnas}h - {valor_total_diurno:.2f} MT")
            
            # Criar registro para horas noturnas se houver
            if horas_noturnas > 0:
                valor_por_hora_noturno = valor_base * Decimal('1.0')  # 100%
                valor_total_noturno = horas_noturnas * valor_por_hora_noturno
                
                HorasExtras.objects.create(
                    funcionario=funcionario,
                    data=data,
                    tipo='NO',
                    hora_inicio=hora_inicio,
                    hora_fim=hora_fim,
                    quantidade_horas=horas_noturnas,
                    valor_por_hora=valor_por_hora_noturno,
                    valor_total=valor_total_noturno,
                    observacoes=f"{observacoes} (Noturno)".strip(),
                    criado_por=request.user
                )
                registros_criados.append(f"Noturno: {horas_noturnas}h - {valor_total_noturno:.2f} MT")
            
            # Criar registro para horas extraordinárias se houver
            if horas_extraordinarias > 0:
                valor_por_hora_extraordinario = valor_base * Decimal('1.0')  # 100%
                valor_total_extraordinario = horas_extraordinarias * valor_por_hora_extraordinario
                
                HorasExtras.objects.create(
                    funcionario=funcionario,
                    data=data,
                    tipo='EX',
                    hora_inicio=hora_inicio,
                    hora_fim=hora_fim,
                    quantidade_horas=horas_extraordinarias,
                    valor_por_hora=valor_por_hora_extraordinario,
                    valor_total=valor_total_extraordinario,
                    observacoes=f"{observacoes} (Extraordinário)".strip(),
                    criado_por=request.user
                )
                registros_criados.append(f"Extraordinário: {horas_extraordinarias}h - {valor_total_extraordinario:.2f} MT")
            
            # Calcular total geral
            total_horas = horas_diurnas + horas_noturnas + horas_extraordinarias
            total_valor = (horas_diurnas * valor_base * Decimal('0.5') + 
                          horas_noturnas * valor_base * Decimal('1.0') + 
                          horas_extraordinarias * valor_base * Decimal('1.0'))
            
            mensagem = f'Horas extras atualizadas para {funcionario.nome_completo} em {data}:\n'
            mensagem += '\n'.join(registros_criados)
            mensagem += f'\n\nTotal: {total_horas}h - {total_valor:.2f} MT'
            
            messages.success(request, mensagem)
            return redirect('rh:horas_extras')
            
        except Exception as e:
            messages.error(request, f'Erro ao atualizar horas extras: {str(e)}')
    
    # GET - Mostrar formulário de edição
    funcionarios = Funcionario.objects.filter(status='AT').order_by('nome_completo')
    
    context = {
        'horas_extras': horas_extras,
        'funcionarios': funcionarios,
        'tipos_choices': HorasExtras.TIPO_CHOICES,
    }
    
    return render(request, 'rh/presencas/horas_extras_editar.html', context)

@login_required
def rh_horas_extras_excluir(request, id):
    """Excluir horas extras"""
    horas_extras = get_object_or_404(HorasExtras, id=id)
    
    if request.method == 'POST':
        try:
            funcionario_nome = horas_extras.funcionario.nome_completo
            data = horas_extras.data
            horas_extras.delete()
            messages.success(request, f'Horas extras de {funcionario_nome} em {data} foram excluídas com sucesso!')
            return redirect('rh:horas_extras_lista')
        except Exception as e:
            messages.error(request, f'Erro ao excluir horas extras: {str(e)}')
    
    context = {
        'horas_extras': horas_extras,
    }
    
    return render(request, 'rh/presencas/horas_extras_excluir.html', context)

@login_required
def rh_detectar_tipo_horas_extras(request):
    """Endpoint AJAX para detectar automaticamente o tipo de horas extras"""
    if request.method == 'POST':
        try:
            import json
            from datetime import datetime
            
            data = json.loads(request.body)
            funcionario_id = data.get('funcionario_id')
            data_str = data.get('data')
            hora_inicio = data.get('hora_inicio')
            hora_fim = data.get('hora_fim')
            
            if not all([funcionario_id, data_str, hora_inicio, hora_fim]):
                return JsonResponse({'success': False, 'error': 'Dados incompletos'})
            
            # Converter data string para objeto date
            data_obj = datetime.strptime(data_str, '%Y-%m-%d').date()
            
            # Obter funcionário
            funcionario = get_object_or_404(Funcionario, id=funcionario_id)
            
            # Detectar tipo automaticamente
            tipo, justificativa, sugestao_misto = HorasExtras.determinar_tipo_automatico(
                funcionario, data_obj, hora_inicio, hora_fim
            )
            
            return JsonResponse({
                'success': True,
                'tipo': tipo,
                'justificativa': justificativa,
                'sugestao_misto': sugestao_misto
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({'success': False, 'error': 'Método não permitido'})

@login_required
def rh_calcular_horas_extras_mistas(request):
    """Endpoint AJAX para calcular horas extras mistas com percentuais separados"""
    if request.method == 'POST':
        try:
            import json
            from datetime import datetime
            
            data = json.loads(request.body)
            funcionario_id = data.get('funcionario_id')
            data_str = data.get('data')
            hora_inicio = data.get('hora_inicio')
            hora_fim = data.get('hora_fim')
            
            if not all([funcionario_id, data_str, hora_inicio, hora_fim]):
                return JsonResponse({'success': False, 'error': 'Dados incompletos'})
            
            # Converter data string para objeto date
            data_obj = datetime.strptime(data_str, '%Y-%m-%d').date()
            
            # Obter funcionário
            funcionario = get_object_or_404(Funcionario, id=funcionario_id)
            
            # Calcular horas extras mistas
            calculo_misto = HorasExtras.calcular_horas_extras_mistas(
                funcionario, data_obj, hora_inicio, hora_fim
            )
            
            if not calculo_misto:
                return JsonResponse({
                    'success': False,
                    'error': 'Não foi possível calcular as horas extras mistas'
                })
            
            # Converter Decimal para float para serialização JSON
            calculo_misto_serializado = {
                'diurno': None,
                'noturno': None,
                'total': {
                    'horas_totais': float(calculo_misto['total']['horas_totais']),
                    'valor_total': float(calculo_misto['total']['valor_total'])
                }
            }
            
            if calculo_misto['diurno']:
                calculo_misto_serializado['diurno'] = {
                    'horas': float(calculo_misto['diurno']['horas']),
                    'valor_por_hora': float(calculo_misto['diurno']['valor_por_hora']),
                    'valor_total': float(calculo_misto['diurno']['valor_total']),
                    'percentual': float(calculo_misto['diurno']['percentual']),
                    'tipo': calculo_misto['diurno']['tipo'],
                    'tipo_display': calculo_misto['diurno']['tipo_display']
                }
            
            if calculo_misto['noturno']:
                calculo_misto_serializado['noturno'] = {
                    'horas': float(calculo_misto['noturno']['horas']),
                    'valor_por_hora': float(calculo_misto['noturno']['valor_por_hora']),
                    'valor_total': float(calculo_misto['noturno']['valor_total']),
                    'percentual': float(calculo_misto['noturno']['percentual']),
                    'tipo': calculo_misto['noturno']['tipo'],
                    'tipo_display': calculo_misto['noturno']['tipo_display']
                }
            
            return JsonResponse({
                'success': True,
                'calculo_misto': calculo_misto_serializado
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({'success': False, 'error': 'Método não permitido'})

@login_required
def rh_criar_horas_extras_mistas(request):
    """Endpoint AJAX para criar registros duplos de horas extras mistas"""
    if request.method == 'POST':
        try:
            import json
            from datetime import datetime
            from decimal import Decimal
            
            data = json.loads(request.body)
            funcionario_id = data.get('funcionario_id')
            data_str = data.get('data')
            hora_inicio = data.get('hora_inicio')
            hora_fim = data.get('hora_fim')
            observacoes = data.get('observacoes', '')
            
            if not all([funcionario_id, data_str, hora_inicio, hora_fim]):
                return JsonResponse({'success': False, 'error': 'Dados incompletos'})
            
            # Converter data string para objeto date
            data_obj = datetime.strptime(data_str, '%Y-%m-%d').date()
            
            # Obter funcionário
            funcionario = get_object_or_404(Funcionario, id=funcionario_id)
            
            # Calcular horas extras mistas
            calculo_misto = HorasExtras.calcular_horas_extras_mistas(
                funcionario, data_obj, hora_inicio, hora_fim
            )
            
            if not calculo_misto:
                return JsonResponse({
                    'success': False,
                    'error': 'Não foi possível calcular as horas extras mistas'
                })
            
            # Criar registros separados
            registros_criados = []
            
            # Registrar período diurno se existir
            if calculo_misto['diurno']:
                diurno = calculo_misto['diurno']
                horas_extras_diurno = HorasExtras.objects.create(
                    funcionario=funcionario,
                    data=data_obj,
                    tipo='DI',
                    hora_inicio=hora_inicio,
                    hora_fim='20:00',  # Fim do período diurno
                    quantidade_horas=Decimal(str(diurno['horas'])),
                    valor_por_hora=Decimal(str(diurno['valor_por_hora'])),
                    valor_total=Decimal(str(diurno['valor_total'])),
                    observacoes=f"{observacoes} - Período Diurno".strip(' -'),
                    criado_por=request.user
                )
                registros_criados.append({
                    'id': horas_extras_diurno.id,
                    'tipo': 'DI',
                    'horas': float(diurno['horas']),
                    'valor_total': float(diurno['valor_total'])
                })
            
            # Registrar período noturno se existir
            if calculo_misto['noturno']:
                noturno = calculo_misto['noturno']
                horas_extras_noturno = HorasExtras.objects.create(
                    funcionario=funcionario,
                    data=data_obj,
                    tipo='NO',
                    hora_inicio='20:00',  # Início do período noturno
                    hora_fim=hora_fim,
                    quantidade_horas=Decimal(str(noturno['horas'])),
                    valor_por_hora=Decimal(str(noturno['valor_por_hora'])),
                    valor_total=Decimal(str(noturno['valor_total'])),
                    observacoes=f"{observacoes} - Período Noturno".strip(' -'),
                    criado_por=request.user
                )
                registros_criados.append({
                    'id': horas_extras_noturno.id,
                    'tipo': 'NO',
                    'horas': float(noturno['horas']),
                    'valor_total': float(noturno['valor_total'])
                })
            
            return JsonResponse({
                'success': True,
                'registros_criados': registros_criados,
                'total_valor': float(calculo_misto['total']['valor_total']),
                'total_horas': float(calculo_misto['total']['horas_totais'])
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({'success': False, 'error': 'Método não permitido'})

@login_required
def rh_tipos_presenca(request):
    """Lista de tipos de presença"""
    tipos = TipoPresenca.objects.filter(ativo=True).order_by('nome')
    
    # Filtros
    search_query = request.GET.get('search', '')
    if search_query:
        tipos = tipos.filter(nome__icontains=search_query)
    
    # Paginação
    paginator = Paginator(tipos, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    all_tipos = TipoPresenca.objects.all()
    context = {
        'tipos': page_obj,
        'search_query': search_query,
        'stats': {
            'total': all_tipos.count(),
            'activos': all_tipos.filter(ativo=True).count(),
            'desconta_salario': all_tipos.filter(desconta_salario=True).count(),
        },
    }
    
    return render(request, 'rh/presencas/tipos/main.html', context)

@login_required
def rh_tipo_presenca_add(request):
    """Adicionar tipo de presença"""
    if request.method == 'POST':
        nome = request.POST.get('nome')
        codigo = request.POST.get('codigo')
        descricao = request.POST.get('descricao', '')
        cor = request.POST.get('cor', '#28a745')
        desconta_salario = request.POST.get('desconta_salario') == 'on'
        ativo = request.POST.get('ativo', 'on') == 'on'
        
        if not nome or not codigo:
            messages.error(request, 'Nome e código são obrigatórios.')
        else:
            try:
                TipoPresenca.objects.create(
                    nome=nome,
                    codigo=codigo,
                    descricao=descricao,
                    cor=cor,
                    desconta_salario=desconta_salario,
                    ativo=ativo,
                )
                messages.success(request, 'Tipo de presença criado com sucesso!')
                return redirect('rh:tipos_presenca')
            except Exception as e:
                messages.error(request, f'Erro ao criar tipo de presença: {str(e)}')
    
    context = {
        'tipo_choices': TipoPresenca.TIPO_CHOICES,
        'cores_disponiveis': [
            ('#28a745', 'Verde'),
            ('#dc3545', 'Vermelho'),
            ('#ffc107', 'Amarelo'),
            ('#17a2b8', 'Azul'),
            ('#6f42c1', 'Roxo'),
            ('#fd7e14', 'Laranja'),
            ('#20c997', 'Verde claro'),
            ('#6c757d', 'Cinza'),
        ]
    }
    
    return render(request, 'rh/presencas/tipos/form.html', context)

@login_required
def rh_tipo_presenca_edit(request, id):
    """Editar tipo de presença"""
    try:
        tipo = TipoPresenca.objects.get(id=id)
        
        if request.method == 'POST':
            nome = request.POST.get('nome')
            codigo = request.POST.get('codigo')
            descricao = request.POST.get('descricao', '')
            cor = request.POST.get('cor', '#28a745')
            desconta_salario = request.POST.get('desconta_salario') == 'on'
            ativo = request.POST.get('ativo') == 'on'
            
            if not nome or not codigo:
                messages.error(request, 'Nome e código são obrigatórios.')
            else:
                try:
                    tipo.nome = nome
                    tipo.codigo = codigo
                    tipo.descricao = descricao
                    tipo.cor = cor
                    tipo.desconta_salario = desconta_salario
                    tipo.ativo = ativo
                    tipo.save()
                    
                    messages.success(request, 'Tipo de presença atualizado com sucesso!')
                    return redirect('rh:tipos_presenca')
                except Exception as e:
                    messages.error(request, f'Erro ao atualizar tipo de presença: {str(e)}')
        
        context = {
            'tipo': tipo,
            'tipo_choices': TipoPresenca.TIPO_CHOICES,
            'cores_disponiveis': [
                ('#28a745', 'Verde'),
                ('#dc3545', 'Vermelho'),
                ('#ffc107', 'Amarelo'),
                ('#17a2b8', 'Azul'),
                ('#6f42c1', 'Roxo'),
                ('#fd7e14', 'Laranja'),
                ('#20c997', 'Verde claro'),
                ('#6c757d', 'Cinza'),
            ]
        }
        
        return render(request, 'rh/presencas/tipos/form.html', context)
        
    except TipoPresenca.DoesNotExist:
        messages.error(request, 'Tipo de presença não encontrado.')
        return redirect('rh:tipos_presenca')

@login_required
def rh_tipo_presenca_delete(request, id):
    """Deletar tipo de presença"""
    try:
        tipo = TipoPresenca.objects.get(id=id)
        
        if request.method == 'POST':
            try:
                # Verificar se há presenças usando este tipo
                presencas_count = Presenca.objects.filter(tipo=tipo).count()
                if presencas_count > 0:
                    messages.error(request, f'Não é possível deletar este tipo de presença pois existem {presencas_count} presenças associadas.')
                    return redirect('rh:tipos_presenca')
                
                tipo.delete()
                messages.success(request, 'Tipo de presença deletado com sucesso!')
                return redirect('rh:tipos_presenca')
            except Exception as e:
                messages.error(request, f'Erro ao deletar tipo de presença: {str(e)}')
        
        context = {'tipo': tipo}
        return render(request, 'rh/presencas/tipos/delete.html', context)
        
    except TipoPresenca.DoesNotExist:
        messages.error(request, 'Tipo de presença não encontrado.')
        return redirect('rh:tipos_presenca')

@login_required
def rh_marcar_feriados_automaticos(request):
    """Marcar automaticamente os feriados no calendário de presenças"""
    if request.method == 'POST':
        try:
            import json
            
            # Verificar se é JSON
            if request.content_type == 'application/json':
                data = json.loads(request.body)
                funcionario_id = data.get('funcionario_id')
                mes = int(data.get('mes'))
                ano = int(data.get('ano'))
            else:
                # Fallback para form data
                funcionario_id = request.POST.get('funcionario_id')
                mes = int(request.POST.get('mes'))
                ano = int(request.POST.get('ano'))
            
            funcionario = get_object_or_404(Funcionario, id=funcionario_id)
            tipo_feriado = get_object_or_404(TipoPresenca, codigo='FD')  # FD = Feriado
            
            # Obter todos os feriados ativos para o mês/ano especificado
            from django.db.models.functions import ExtractMonth, ExtractYear
            
            feriados = Feriado.objects.filter(
                ativo=True,
                data__year=ano,
                data__month=mes
            )
            
            presencas_criadas = 0
            presencas_atualizadas = 0
            
            for feriado in feriados:
                presenca_existente = Presenca.objects.filter(
                    funcionario=funcionario,
                    data=feriado.data
                ).first()
                
                if presenca_existente:
                    presenca_existente.tipo_presenca = tipo_feriado
                    presenca_existente.observacoes = f"Feriado: {feriado.nome}"
                    presenca_existente.save()
                    presencas_atualizadas += 1
                else:
                    Presenca.objects.create(
                        funcionario=funcionario,
                        data=feriado.data,
                        tipo_presenca=tipo_feriado,
                        observacoes=f"Feriado: {feriado.nome}",
                        horas_extras=0
                    )
                    presencas_criadas += 1
            
            return JsonResponse({
                'success': True,
                'criadas': presencas_criadas,
                'atualizadas': presencas_atualizadas,
                'total_feriados': len(feriados),
                'message': f'Foram processados {len(feriados)} feriados: {presencas_criadas} criados, {presencas_atualizadas} atualizados.'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': 'Erro interno do servidor'
            })
    
    return JsonResponse({'success': False, 'error': 'Método não permitido'})

@login_required
def rh_marcar_finais_semana_automaticos(request):
    """Marcar automaticamente os finais de semana no calendário de presenças"""
    if request.method == 'POST':
        try:
            import json
            import calendar
            from datetime import date
            
            if request.content_type == 'application/json':
                data = json.loads(request.body)
                funcionario_id = data.get('funcionario_id')
                mes = int(data.get('mes') or date.today().month)
                ano = int(data.get('ano') or date.today().year)
            else:
                funcionario_id = request.POST.get('funcionario_id')
                mes = int(request.POST.get('mes') or date.today().month)
                ano = int(request.POST.get('ano') or date.today().year)
            
            funcionario = get_object_or_404(Funcionario, id=funcionario_id)
            tipo_folga = get_object_or_404(TipoPresenca, codigo='FG')
            
            # Obter configuração de dias de trabalho da sucursal
            sucursal = funcionario.sucursal
            dias_trabalho = sucursal.get_dias_trabalho_weekdays()
            
            # Obter todos os dias do mês
            dias_no_mes = calendar.monthrange(ano, mes)[1]
            presencas_criadas = 0
            presencas_atualizadas = 0
            
            for dia in range(1, dias_no_mes + 1):
                data_atual = date(ano, mes, dia)
                dia_semana = data_atual.weekday()  # 0=segunda, 6=domingo
                
                # Verificar se NÃO é dia de trabalho (folga)
                if dia_semana not in dias_trabalho:
                    presenca_existente = Presenca.objects.filter(
                        funcionario=funcionario,
                        data=data_atual
                    ).first()
                    
                    if presenca_existente:
                        # Só atualizar se não for um tipo mais específico (como Horas Extras)
                        if presenca_existente.tipo_presenca.codigo == 'FG':
                            nome_dia = data_atual.strftime('%A')
                            presenca_existente.observacoes = f"Folga - {nome_dia}"
                            presenca_existente.save()
                            presencas_atualizadas += 1
                    else:
                        nome_dia = data_atual.strftime('%A')
                        Presenca.objects.create(
                            funcionario=funcionario,
                            data=data_atual,
                            tipo_presenca=tipo_folga,
                            observacoes=f"Folga - {nome_dia}"
                        )
                        presencas_criadas += 1
            
            return JsonResponse({
                'success': True,
                'criadas': presencas_criadas,
                'atualizadas': presencas_atualizadas,
                'total_dias_folga': presencas_criadas + presencas_atualizadas,
                'dias_trabalho_sucursal': dias_trabalho,
                'message': f'Foram processados {presencas_criadas + presencas_atualizadas} dias de folga baseados no horário da sucursal: {presencas_criadas} criados, {presencas_atualizadas} atualizados.'
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    return JsonResponse({'success': False, 'error': 'Método não permitido'}, status=405)

@login_required
def rh_horarios_expediente(request, sucursal_id=None):
    """Gerenciar horários de expediente da sucursal"""
    
    # Obter sucursal
    if sucursal_id:
        sucursal = get_object_or_404(Sucursal, id=sucursal_id)
    else:
        # Usar primeira sucursal ativa do usuário
        sucursal = Sucursal.objects.filter(ativa=True).first()
        if not sucursal:
            messages.error(request, 'Nenhuma sucursal ativa encontrada.')
            return redirect('rh:index')
    
    # Dias da semana
    DIAS_SEMANA = [
        (0, 'Segunda-feira'),
        (1, 'Terça-feira'),
        (2, 'Quarta-feira'),
        (3, 'Quinta-feira'),
        (4, 'Sexta-feira'),
        (5, 'Sábado'),
        (6, 'Domingo'),
    ]
    
    # Processar formulário
    if request.method == 'POST':
        try:
            # Atualizar configurações básicas da sucursal
            hora_inicio = request.POST.get('hora_inicio_padrao')
            hora_fim = request.POST.get('hora_fim_padrao')
            duracao_almoco = request.POST.get('duracao_almoco_padrao')
            horas_trabalho = request.POST.get('horas_trabalho_dia')
            
            if hora_inicio:
                from datetime import time
                try:
                    sucursal.hora_inicio_expediente = time.fromisoformat(hora_inicio)
                except ValueError:
                    messages.error(request, f'Formato de hora de início inválido: {hora_inicio}')
                    return redirect('rh:horarios_expediente', sucursal_id=sucursal.id)
            
            if hora_fim:
                from datetime import time
                try:
                    sucursal.hora_fim_expediente = time.fromisoformat(hora_fim)
                except ValueError:
                    messages.error(request, f'Formato de hora de fim inválido: {hora_fim}')
                    return redirect('rh:horarios_expediente', sucursal_id=sucursal.id)
            
            if duracao_almoco:
                from datetime import timedelta
                try:
                    # Converter formato HH:MM:SS para timedelta
                    if ':' in duracao_almoco:
                        parts = duracao_almoco.split(':')
                        if len(parts) == 3:
                            hours, minutes, seconds = map(int, parts)
                            sucursal.duracao_almoco = timedelta(hours=hours, minutes=minutes, seconds=seconds)
                        else:
                            raise ValueError("Formato inválido")
                    else:
                        raise ValueError("Formato inválido")
                except ValueError:
                    messages.error(request, f'Formato de duração do almoço inválido: {duracao_almoco}')
                    return redirect('rh:horarios_expediente', sucursal_id=sucursal.id)
            
            if horas_trabalho:
                from datetime import timedelta
                try:
                    # Converter formato HH:MM:SS para timedelta
                    if ':' in horas_trabalho:
                        parts = horas_trabalho.split(':')
                        if len(parts) == 3:
                            hours, minutes, seconds = map(int, parts)
                            sucursal.horas_trabalho_dia = timedelta(hours=hours, minutes=minutes, seconds=seconds)
                        else:
                            raise ValueError("Formato inválido")
                    else:
                        raise ValueError("Formato inválido")
                except ValueError:
                    messages.error(request, f'Formato de horas de trabalho inválido: {horas_trabalho}')
                    return redirect('rh:horarios_expediente', sucursal_id=sucursal.id)
            
            # Calcular dias de trabalho baseado nos checkboxes
            dias_trabalho = []
            for dia_semana, nome_dia in DIAS_SEMANA:
                if request.POST.get(f'ativo_{dia_semana}') == 'on':
                    dias_trabalho.append(dia_semana)
            
            sucursal.dias_trabalho_semana = len(dias_trabalho)
            sucursal.save()
            
            messages.success(request, 'Horários de expediente atualizados com sucesso!')
            return redirect('rh:horarios_expediente', sucursal_id=sucursal.id)
            
        except Exception as e:
            messages.error(request, f'Erro ao atualizar horários: {str(e)}')
    
    # Obter todas as sucursais para o seletor
    sucursais = Sucursal.objects.filter(ativa=True).order_by('nome')
    
    # Determinar quais dias estão ativos baseado no dias_trabalho_semana
    dias_ativos = []
    if sucursal.dias_trabalho_semana == 5:
        dias_ativos = [0, 1, 2, 3, 4]  # Segunda a sexta
    elif sucursal.dias_trabalho_semana == 6:
        dias_ativos = [0, 1, 2, 3, 4, 5]  # Segunda a sábado
    elif sucursal.dias_trabalho_semana == 7:
        dias_ativos = [0, 1, 2, 3, 4, 5, 6]  # Todos os dias
    else:
        dias_ativos = [0, 1, 2, 3, 4]  # Padrão: segunda a sexta
    
    context = {
        'sucursal': sucursal,
        'sucursais': sucursais,
        'dias_semana': DIAS_SEMANA,
        'dias_ativos': dias_ativos,
    }
    
    return render(request, 'rh/horarios_expediente.html', context)
