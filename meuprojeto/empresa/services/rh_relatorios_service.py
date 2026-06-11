"""Montagem de contexto para relatórios consolidados de RH."""
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone

from meuprojeto.empresa.models_rh import (
    Cargo,
    Departamento,
    FolhaSalarial,
    Funcionario,
    FuncionarioFolha,
    HorasExtras,
    Presenca,
    Treinamento,
)


def _parse_filtros(get_params):
    mes_referencia = get_params.get('mes_referencia', '')
    data_inicio = get_params.get('data_inicio', '')
    data_fim = get_params.get('data_fim', '')
    departamento_id = get_params.get('departamento', '')

    inicio = None
    fim = None
    if data_inicio:
        try:
            inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
        except ValueError:
            pass
    if data_fim:
        try:
            fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
        except ValueError:
            pass
    if mes_referencia and not inicio:
        try:
            inicio = datetime.strptime(mes_referencia + '-01', '%Y-%m-%d').date()
            fim = (inicio.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        except ValueError:
            pass
    if not inicio:
        hoje = date.today()
        inicio = hoje.replace(day=1)
        fim = hoje

    return {
        'mes_referencia': mes_referencia,
        'data_inicio': inicio,
        'data_fim': fim,
        'departamento': departamento_id,
    }


def _funcionarios_qs(filtros):
    qs = Funcionario.objects.select_related('cargo', 'departamento', 'sucursal')
    if filtros['departamento']:
        qs = qs.filter(departamento_id=filtros['departamento'])
    return qs


def _folhas_qs(filtros):
    qs = FolhaSalarial.objects.all()
    if filtros['mes_referencia']:
        try:
            mes_ref = datetime.strptime(filtros['mes_referencia'], '%Y-%m').date()
            qs = qs.filter(mes_referencia=mes_ref)
        except ValueError:
            pass
    elif filtros['data_inicio']:
        qs = qs.filter(
            mes_referencia__gte=filtros['data_inicio'].replace(day=1),
            mes_referencia__lte=filtros['data_fim'],
        )
    return qs


def montar_contexto_relatorio_custos_rh(get_params):
    filtros = _parse_filtros(get_params)
    folhas = _folhas_qs(filtros)
    ff_qs = FuncionarioFolha.objects.filter(folha__in=folhas).select_related(
        'funcionario__departamento', 'folha',
    )
    if filtros['departamento']:
        ff_qs = ff_qs.filter(funcionario__departamento_id=filtros['departamento'])

    total_salarios_bruto = ff_qs.aggregate(t=Sum('salario_bruto'))['t'] or Decimal('0')
    total_salarios = ff_qs.aggregate(t=Sum('salario_liquido'))['t'] or Decimal('0')
    total_beneficios = ff_qs.aggregate(t=Sum('total_beneficios'))['t'] or Decimal('0')
    total_descontos = ff_qs.aggregate(t=Sum('total_descontos'))['t'] or Decimal('0')

    he_qs = HorasExtras.objects.filter(
        data__gte=filtros['data_inicio'],
        data__lte=filtros['data_fim'],
    )
    if filtros['departamento']:
        he_qs = he_qs.filter(funcionario__departamento_id=filtros['departamento'])
    he_agg = he_qs.aggregate(
        total_valor=Sum('valor_total'),
        total_horas=Sum('quantidade_horas'),
    )
    total_horas_extras = he_agg['total_valor'] or Decimal('0')
    quantidade_horas_extras = he_agg['total_horas'] or Decimal('0')

    tr_qs = Treinamento.objects.filter(
        data_inicio__gte=filtros['data_inicio'],
        data_inicio__lte=filtros['data_fim'],
    )
    total_treinamentos = tr_qs.aggregate(t=Sum('custo_total'))['t'] or Decimal('0')
    quantidade_treinamentos = tr_qs.count()

    total_geral = total_salarios_bruto + total_horas_extras + total_treinamentos

    custos_por_departamento = []
    for row in ff_qs.values('funcionario__departamento__nome').annotate(
        salarios=Sum('salario_liquido'),
        beneficios=Sum('total_beneficios'),
    ).order_by('-salarios'):
        dept_nome = row['funcionario__departamento__nome'] or 'Sem Departamento'
        sal = row['salarios'] or Decimal('0')
        ben = row['beneficios'] or Decimal('0')
        he_dept = he_qs.filter(
            funcionario__departamento__nome=row['funcionario__departamento__nome'],
        ).aggregate(t=Sum('valor_total'))['t'] or Decimal('0')
        total_dept = sal + ben + he_dept
        pct = float((total_dept / total_geral * 100) if total_geral else 0)
        custos_por_departamento.append({
            'departamento': dept_nome,
            'salarios': sal,
            'beneficios': ben,
            'horas_extras': he_dept,
            'total': total_dept,
            'percentual': pct,
        })

    return {
        'filtros': {
            'mes_referencia': filtros['mes_referencia'],
            'data_inicio': filtros['data_inicio'],
            'data_fim': filtros['data_fim'],
            'departamento': filtros['departamento'],
        },
        'departamentos': Departamento.objects.filter(ativo=True).order_by('nome'),
        'data_relatorio': timezone.now(),
        'total_salarios_bruto': total_salarios_bruto,
        'total_salarios': total_salarios,
        'total_beneficios': total_beneficios,
        'total_descontos': total_descontos,
        'total_horas_extras': total_horas_extras,
        'quantidade_horas_extras': quantidade_horas_extras,
        'total_treinamentos': total_treinamentos,
        'quantidade_treinamentos': quantidade_treinamentos,
        'total_geral_custos_rh': total_geral,
        'custos_por_departamento': custos_por_departamento,
    }


def montar_contexto_relatorio_geral_rh(get_params):
    filtros = _parse_filtros(get_params)
    func_qs = _funcionarios_qs(filtros)
    folhas = _folhas_qs(filtros)
    ff_qs = FuncionarioFolha.objects.filter(folha__in=folhas).select_related('funcionario', 'folha')
    if filtros['departamento']:
        ff_qs = ff_qs.filter(funcionario__departamento_id=filtros['departamento'])

    pres_qs = Presenca.objects.filter(
        data__gte=filtros['data_inicio'],
        data__lte=filtros['data_fim'],
    )
    if filtros['departamento']:
        pres_qs = pres_qs.filter(funcionario__departamento_id=filtros['departamento'])

    total_funcionarios = func_qs.count()
    funcionarios_ativos = func_qs.filter(status='AT').count()
    funcionarios_inativos = func_qs.filter(status='IN').count()
    total_folhas = folhas.count()

    total_salarios_bruto = folhas.aggregate(t=Sum('total_bruto'))['t'] or Decimal('0')
    total_salarios_liquido = folhas.aggregate(t=Sum('total_liquido'))['t'] or Decimal('0')
    total_descontos_folha = folhas.aggregate(t=Sum('total_descontos'))['t'] or Decimal('0')

    he_total = HorasExtras.objects.filter(
        data__gte=filtros['data_inicio'],
        data__lte=filtros['data_fim'],
    ).aggregate(t=Sum('valor_total'))['t'] or Decimal('0')
    total_geral_custos_rh = total_salarios_bruto + he_total

    try:
        from meuprojeto.empresa.models_base import DadosEmpresa
        empresa = DadosEmpresa.objects.first()
    except Exception:
        empresa = None

    return {
        'filtros': {
            'mes_referencia': filtros['mes_referencia'],
            'data_inicio': filtros['data_inicio'],
            'data_fim': filtros['data_fim'],
            'departamento': filtros['departamento'],
        },
        'departamentos': Departamento.objects.filter(ativo=True).order_by('nome'),
        'empresa': empresa,
        'data_relatorio': timezone.now(),
        'total_funcionarios': total_funcionarios,
        'funcionarios_ativos': funcionarios_ativos,
        'funcionarios_inativos': funcionarios_inativos,
        'total_folhas': total_folhas,
        'total_geral_custos_rh': total_geral_custos_rh,
        'funcionarios_por_departamento': func_qs.values('departamento__nome').annotate(
            total=Count('id'),
        ).order_by('-total'),
        'funcionarios_por_cargo': func_qs.values('cargo__nome').annotate(
            total=Count('id'),
        ).order_by('-total'),
        'funcionarios_por_sucursal': func_qs.values('sucursal__nome').annotate(
            total=Count('id'),
        ).order_by('-total'),
        'funcionarios': func_qs.order_by('nome_completo')[:200],
        'total_presencas': pres_qs.count(),
        'presencas_presentes': pres_qs.filter(tipo_presenca__codigo='PR').count(),
        'presencas_faltas': pres_qs.filter(tipo_presenca__codigo='FA').count(),
        'presencas_por_tipo': pres_qs.values('tipo_presenca__nome').annotate(
            total=Count('id'),
        ).order_by('-total'),
        'folhas_fechadas': folhas.filter(status='FECHADA').count(),
        'folhas_calculadas': folhas.filter(status='FECHADA').count(),
        'folhas_abertas': folhas.filter(status='ABERTA').count(),
        'total_salarios_bruto': total_salarios_bruto,
        'total_salarios_liquido': total_salarios_liquido,
        'total_descontos_folha': total_descontos_folha,
        'total_encargos': total_descontos_folha,
        'folhas_por_status': folhas.values('status').annotate(total=Count('id')),
        'dados_nuit_inss': [],
        'total_salario_bruto_nuit_inss': Decimal('0'),
        'total_inss_trabalhador_nuit_inss': Decimal('0'),
        'total_inss_empregador_nuit_inss': Decimal('0'),
        'total_inss_geral_nuit_inss': Decimal('0'),
        'total_irps_nuit_inss': Decimal('0'),
        'presencas_por_funcionario': [],
        'total_departamentos': Departamento.objects.count(),
        'total_cargos': Cargo.objects.count(),
    }
