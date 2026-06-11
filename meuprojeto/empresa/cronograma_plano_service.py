"""
Serviço para o cronograma físico do plano de execução de ordens de serviço.
Centraliza a lógica de actividades, progresso, atrasos e Gantt.
"""
from datetime import date, timedelta
from django.utils import timezone


def _to_date(val):
    """Converte date ou datetime para date (evita mistura date/datetime)."""
    if val is None:
        return None
    if isinstance(val, date):
        return val
    if hasattr(val, 'date'):
        return val.date()
    return None


def _local_date(dt):
    """Converte datetime para date no timezone local. Nunca levanta exceção."""
    if not dt:
        return None
    try:
        if isinstance(dt, date) and type(dt) is date:
            return dt
        if hasattr(dt, 'date'):
            if getattr(dt, 'tzinfo', None) is not None:
                return timezone.localtime(dt).date()
            return dt.date()
    except (ValueError, TypeError, AttributeError):
        pass
    return None


def build_atividades_flat(ordem):
    """
    Constrói lista plana de actividades (raízes + subactividades) com metadados.
    Retorna lista de dicts: {'atividade', 'nivel', 'e_subactividade', 'parcela_id'}.
    Usa query directa para garantir dados actualizados (evita cache de prefetch com datas antigas).
    """
    from .models_stock import AtividadeExecucao
    atividades_flat = []
    ordem_id = ordem.pk if hasattr(ordem, 'pk') else ordem
    raizes = list(
        AtividadeExecucao.objects.filter(ordem_servico_id=ordem_id, parent__isnull=True)
        .order_by('numero_ordem', 'id')
    )
    for idx_raiz, r in enumerate(raizes, start=1):
        atividades_flat.append({
            'atividade': r,
            'nivel': 0,
            'e_subactividade': False,
            'parcela_id': r.parcela_id,
            'numero_display': str(idx_raiz),
        })
        sublist = list(AtividadeExecucao.objects.filter(parent_id=r.id).order_by('numero_ordem', 'id'))
        for idx_sub, sub in enumerate(sublist, start=1):
            atividades_flat.append({
                'atividade': sub,
                'nivel': 1,
                'e_subactividade': True,
                'parcela_id': r.parcela_id,
                'numero_display': f"{idx_raiz}.{idx_sub}",
            })
    return atividades_flat


def calcular_progresso(ordem, atividades_flat):
    """
    Calcula progresso do plano.
    Quando parcelas somam 100%, usa ponderação por parcela; senão, contagem simples.
    Retorna dict: {total, concluidas, percent, por_parcelas}
    """
    total = len(atividades_flat)
    concluidas = sum(1 for x in atividades_flat if x['atividade'].status == 'CONCLUIDA')
    parcelas_qs = getattr(ordem, 'parcelas_pagamento', None)
    if not parcelas_qs or not parcelas_qs.exists():
        return {'total': total, 'concluidas': concluidas, 'percent': round((concluidas / total * 100) if total else 0, 0), 'por_parcelas': False}
    parcelas = list(parcelas_qs.order_by('numero_ordem'))
    if sum(p.percentagem for p in parcelas) != 100:
        return {'total': total, 'concluidas': concluidas, 'percent': round((concluidas / total * 100) if total else 0, 0), 'por_parcelas': False}
    percent_acum = 0
    for parcela in parcelas:
        acts = [x for x in atividades_flat if x.get('parcela_id') == parcela.id or x['atividade'].parcela_id == parcela.id]
        if acts:
            concl = sum(1 for x in acts if x['atividade'].status == 'CONCLUIDA')
            percent_acum += parcela.percentagem * (concl / len(acts))
    return {'total': total, 'concluidas': concluidas, 'percent': round(percent_acum, 0), 'por_parcelas': True}


def detectar_atrasos(atividades_flat, hoje):
    """
    Detecta actividades em atraso ou concluídas com atraso.
    - concluida_atrasada: concluída mas data_conclusao > data_prevista_conclusao
    - em_atraso: não concluída e (data_prevista_conclusao já passou OU data_prevista_inicio já passou e ainda não iniciou)
    Retorna lista de dicts: {atividade, tipo: 'em_atraso'|'concluida_atrasada', dias}
    """
    atrasos = []
    for item in atividades_flat:
        atv = item['atividade']
        dp = _to_date(getattr(atv, 'data_prevista_conclusao', None))
        dpi = _to_date(getattr(atv, 'data_prevista_inicio', None))
        di = _to_date(_local_date(atv.data_inicio))

        if atv.status == 'CONCLUIDA' and atv.data_conclusao and dp:
            dt_real = timezone.localtime(atv.data_conclusao) if atv.data_conclusao else None
            data_real = dt_real.date() if dt_real else None
            if data_real and data_real > dp:
                atrasos.append({'atividade': atv, 'tipo': 'concluida_atrasada', 'dias': (data_real - dp).days})
        elif atv.status != 'CONCLUIDA':
            # Atraso por conclusão: prazo previsto já passou
            if dp and hoje > dp:
                atrasos.append({'atividade': atv, 'tipo': 'em_atraso', 'dias': (hoje - dp).days})
            # Atraso por início: data prevista de início já passou e ainda não iniciou
            elif dpi and hoje > dpi and not di:
                atrasos.append({'atividade': atv, 'tipo': 'em_atraso', 'dias': (hoje - dpi).days})
    return atrasos


def _data_prevista_efectiva(item):
    """Data prevista da actividade (própria ou herdada do parent). Nunca levanta exceção."""
    atv = item['atividade']
    dp = _to_date(getattr(atv, 'data_prevista_conclusao', None))
    if dp is not None:
        return dp
    if getattr(atv, 'parent_id', None) is None:
        return None
    try:
        parent = getattr(atv, 'parent', None)
        return _to_date(getattr(parent, 'data_prevista_conclusao', None)) if parent else None
    except Exception:
        return None


def _build_gantt_bars_direct(atividades_flat, min_date, max_date, hoje, atraso_ids):
    """
    Constrói lista cronograma_gantt.
    - Etapas principais (raízes): programadas para iniciar no fim da anterior (numero_ordem); barra prevista em sequência.
    - Subetapas: começam no início da etapa principal e correm em paralelo.
    - Real (verde): barra desde data_inicio até data_conclusão (ou até hoje se em andamento).
    """
    total_days = max(1, (max_date - min_date).days)
    min_width_pct = max(2.0, 100.0 / total_days)
    # Início previsto por actividade raiz (para subetapas e para sequência: próxima raiz começa após a anterior)
    raiz_planned_start = {}
    ultimo_fim_raiz = None
    for item in atividades_flat:
        atv = item['atividade']
        dp = _to_date(getattr(atv, 'data_prevista_conclusao', None))
        dpi = _to_date(getattr(atv, 'data_prevista_inicio', None))
        if item.get('e_subactividade'):
            continue
        if dp is not None:
            di = _to_date(_local_date(atv.data_inicio))
            # Preferir data_prevista_inicio se existir; senão data real de início; senão 7 dias antes do prazo
            planned_start = dpi if dpi is not None else (di if di is not None else (dp - timedelta(days=7)))
            if ultimo_fim_raiz is not None:
                planned_start = max(planned_start, ultimo_fim_raiz)
            if min_date and planned_start < min_date:
                planned_start = min_date
            raiz_planned_start[atv.id] = _to_date(planned_start)
            ultimo_fim_raiz = _to_date(dp)

    result = []
    for item in atividades_flat:
        atv = item['atividade']
        atv_id = getattr(atv, 'id', None)
        di = _to_date(_local_date(atv.data_inicio))
        dc = _to_date(_local_date(atv.data_conclusao))
        dp = _to_date(getattr(atv, 'data_prevista_conclusao', None))
        planned_start = planned_end = None
        if dp is not None:
            planned_end = _to_date(dp)
            dpi = _to_date(getattr(atv, 'data_prevista_inicio', None))
            if item.get('e_subactividade') and getattr(atv, 'parent_id', None):
                # Subetapa: começa no início da etapa principal ou na data prevista início se for posterior
                pai_start = raiz_planned_start.get(atv.parent_id)
                own_start = dpi if dpi is not None else (dp - timedelta(days=7))
                if min_date and own_start < min_date:
                    own_start = min_date
                planned_start = _to_date(max(own_start, pai_start) if pai_start else own_start)
            else:
                # Etapa principal: início já em raiz_planned_start (ou fallback se não tiver prazo)
                planned_start = raiz_planned_start.get(atv.id)
                if planned_start is None:
                    dpi_raiz = _to_date(getattr(atv, 'data_prevista_inicio', None))
                    di_raiz = _to_date(_local_date(atv.data_inicio))
                    planned_start = dpi_raiz if dpi_raiz is not None else (di_raiz if di_raiz is not None else (planned_end - timedelta(days=7) if planned_end else None))
                    if planned_start and min_date and planned_start < min_date:
                        planned_start = min_date
                    planned_start = _to_date(planned_start) if planned_start else None
        # Posições em % do eixo: data D está em (D - min_date).days / total_days * 100.
        # Fim da barra = fim do dia (inclusivo): right_edge = (end_date - min_date + 1).days / total_days * 100, cap 100.
        left_p = width_p = left_a = width_a = 0
        if planned_start is not None and planned_end is not None and min_date is not None:
            left_p = max(0.0, (planned_start - min_date).days / total_days * 100)
            # Inclusivo: barra estende até ao fim do dia planned_end
            end_p_days = (planned_end - min_date).days + 1
            end_p = min(100.0, end_p_days / total_days * 100)
            end_p = max(left_p, end_p)
            width_p = end_p - left_p
            if width_p <= 0:
                width_p = min_width_pct
            width_p = min(100 - left_p, width_p)
        if di is not None and min_date is not None:
            left_a = max(0.0, (di - min_date).days / total_days * 100)
            fim_real = dc if dc is not None else (hoje if di else None)
            if fim_real is not None:
                # Inclusivo: barra real estende até ao fim do dia de conclusão
                end_a_days = (fim_real - min_date).days + 1
                end_a = min(100.0, end_a_days / total_days * 100)
                end_a = max(left_a, end_a)
                width_a = end_a - left_a
            else:
                # Em andamento: até hoje (fim do dia hoje)
                end_a_days = (hoje - min_date).days + 1 if hoje else 0
                end_a = min(100.0, end_a_days / total_days * 100)
                width_a = end_a - left_a
            if width_a <= 0:
                width_a = min_width_pct
            width_a = min(100 - left_a, width_a)
        actual_end = dc or (hoje if di else None)
        left_p_r = round(left_p, 1)
        width_p_r = round(width_p, 1)
        left_a_r = round(left_a, 1)
        width_a_r = round(width_a, 1)
        style_planned = f"left: {left_p_r}%; width: {width_p_r}%;" if width_p_r > 0 else ""
        style_actual = f"left: {left_a_r}%; width: {width_a_r}%;" if width_a_r > 0 else ""
        result.append({
            'item': item,
            'atividade_id': atv_id,
            'planned_start': planned_start,
            'planned_end': planned_end,
            'actual_start': di,
            'actual_end': actual_end,
            'left_p': left_p_r,
            'width_p': width_p_r,
            'left_a': left_a_r,
            'width_a': width_a_r,
            'style_planned': style_planned,
            'style_actual': style_actual,
            'em_atraso': atv.id in atraso_ids,
        })
    return result


def _scale_from_activities(atividades_flat, hoje):
    """Calcula gantt_min e gantt_max a partir de todas as datas das actividades (previstas início/conclusão, reais)."""
    all_d = []
    for item in atividades_flat:
        atv = item['atividade']
        for d in (_local_date(atv.data_inicio), _local_date(atv.data_conclusao), _to_date(getattr(atv, 'data_prevista_inicio', None)), _to_date(getattr(atv, 'data_prevista_conclusao', None))):
            d = _to_date(d)
            if d:
                all_d.append(d)
        dp = _data_prevista_efectiva(item)
        if dp:
            all_d.append(dp)
    if all_d:
        # Margem de 7 dias à esquerda para as barras previstas (7 dias antes do prazo) não ficarem todas coladas ao início
        gantt_min = min(all_d) - timedelta(days=7)
        gantt_max = max(all_d) + timedelta(days=14)
    else:
        gantt_min = hoje - timedelta(days=7)
        gantt_max = hoje + timedelta(days=60)
    gantt_min = _to_date(gantt_min) or gantt_min
    gantt_max = _to_date(gantt_max) or gantt_max
    if hoje > gantt_max:
        gantt_max = hoje + timedelta(days=14)
        gantt_max = _to_date(gantt_max) or gantt_max
    return gantt_min, gantt_max


def build_cronograma_context(ordem, hoje=None):
    """
    Constrói o contexto completo do cronograma para uma ordem de serviço.

    Base: tabela AtividadeExecucao (campos data_prevista_conclusao, data_inicio,
    data_conclusao). A escala e as barras são calculadas só a partir dessas datas.
    Ver docs/CRONOGRAMA_PLANO_BASE.md. Para diagnóstico: detalhe da ordem com
    ?cronograma_debug=1.
    """
    # Data de referência "hoje": timezone local para coincidir com o dia que o utilizador vê
    hoje = _to_date(hoje) or _to_date(timezone.localtime(timezone.now()).date()) or timezone.localtime(timezone.now()).date()
    atividades_flat = build_atividades_flat(ordem)
    progresso_etapas = calcular_progresso(ordem, atividades_flat)
    cronograma_atrasos = detectar_atrasos(atividades_flat, hoje)
    atraso_ids = {a['atividade'].id for a in cronograma_atrasos if a['tipo'] == 'em_atraso'}

    if not atividades_flat:
        return {
            'atividades_flat': [],
            'progresso_etapas': progresso_etapas,
            'cronograma_atrasos': cronograma_atrasos,
            'cronograma_gantt': [],
            'gantt_min_date': None,
            'gantt_max_date': None,
            'gantt_ticks': [],
            'gantt_hoje_pct': None,
            'plano_tem_etapas': False,
            'data_referencia': hoje,
        }

    # Escala sempre a partir das datas das actividades (para o eixo corresponder ao plano)
    gantt_min, gantt_max = _scale_from_activities(atividades_flat, hoje)
    total_days = max(1, (gantt_max - gantt_min).days)
    # Ticks: posição (pct) = posição real da data no eixo; incluir dia 7 (primeira data do plano quando margem=7) para alinhar barra com a etiqueta
    _day_offsets = sorted(set([0, 7, round(total_days * 0.25), round(total_days * 0.5), round(total_days * 0.75), total_days]))
    _seen_pct = set()
    gantt_ticks = []
    for day_off in _day_offsets:
        pct = round(day_off / total_days * 100, 1)
        if pct not in _seen_pct or day_off == total_days:
            _seen_pct.add(pct)
            gantt_ticks.append({
                'pct': pct,
                'date': _to_date(gantt_min + timedelta(days=day_off)) or gantt_min,
            })
    hoje_pct = round((hoje - gantt_min).days / total_days * 100, 1) if gantt_min <= hoje <= gantt_max else None
    # Barras sempre a partir das datas de cada actividade (previsto = prazo; real = início–conclusão)
    cronograma_gantt = _build_gantt_bars_direct(atividades_flat, gantt_min, gantt_max, hoje, atraso_ids)

    # Detectar se todas as actividades têm o mesmo prazo (pode indicar dados errados ou plano por definir)
    prazos_previstos = [
        _to_date(getattr(item['atividade'], 'data_prevista_conclusao', None))
        for item in atividades_flat
    ]
    prazos_nao_nulos = [p for p in prazos_previstos if p is not None]
    cronograma_todas_datas_iguais = (
        len(atividades_flat) > 1
        and len(prazos_nao_nulos) > 1
        and len(set(prazos_nao_nulos)) == 1
    )

    return {
        'atividades_flat': atividades_flat,
        'progresso_etapas': progresso_etapas,
        'cronograma_atrasos': cronograma_atrasos,
        'cronograma_gantt': cronograma_gantt,
        'gantt_min_date': gantt_min,
        'gantt_max_date': gantt_max,
        'gantt_ticks': gantt_ticks,
        'gantt_hoje_pct': hoje_pct,
        'plano_tem_etapas': len(atividades_flat) > 0,
        'data_referencia': hoje,
        'cronograma_todas_datas_iguais': cronograma_todas_datas_iguais,
    }
