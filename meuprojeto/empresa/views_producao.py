"""
Views para o módulo de Produção
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.views.decorators.http import require_http_methods
from django.http import FileResponse, Http404, HttpResponse
import json as _json
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.core.exceptions import ValidationError
import logging
import os

from .models_stock import Receita, Item, ItemReceita, OrdemProducao, ProcessoProducao, EtapaProcesso, EtapaOrdemConcluida, Maquina, LinhaProducao, RequisicaoStock, OrdemServico, ClienteServico, ItemOrcamentoServico, TransporteOrcamentoServico, Transportadora, EquipeServico
from .models_base import Sucursal
from .models_rh import Funcionario
from django.contrib.auth.models import User
from django.db import transaction
from decimal import Decimal, InvalidOperation, ROUND_UP
from django.utils import timezone
from datetime import datetime
from django.conf import settings

logger = logging.getLogger(__name__)


def _contrato_fallback_pagamento(ctx, orcamento):
    """Preenche ctx com texto de pagamento em 2 parcelas (assinatura + conclusão)."""
    from num2words import num2words
    p_assinatura = getattr(orcamento, 'pagamento_percentagem_assinatura', None) or 50
    p_conclusao = getattr(orcamento, 'pagamento_percentagem_conclusao', None) or 50
    if p_assinatura + p_conclusao != 100:
        p_assinatura, p_conclusao = 50, 50
    try:
        p_assinatura_ext = num2words(p_assinatura, lang='pt') + ' por cento'
        p_conclusao_ext = num2words(p_conclusao, lang='pt') + ' por cento'
    except Exception:
        p_assinatura_ext = str(p_assinatura) + ' por cento'
        p_conclusao_ext = str(p_conclusao) + ' por cento'
    ctx['pagamento_estruturado'] = True
    ctx['pagamento_percentagem_assinatura'] = p_assinatura
    ctx['pagamento_percentagem_conclusao'] = p_conclusao
    ctx['pagamento_parcelas_texto'] = [
        f'{p_assinatura}% ({p_assinatura_ext}) no ato da assinatura do presente contrato',
        f'{p_conclusao}% ({p_conclusao_ext}) na conclusão dos serviços.',
    ]
    ctx['pagamento_texto'] = (
        f'O pagamento será efectuado em 2 parcelas, do seguinte modo: '
        f'(1) {p_assinatura}% ({p_assinatura_ext}) no ato da assinatura do presente contrato; '
        f'(2) {p_conclusao}% ({p_conclusao_ext}) na conclusão dos serviços.'
    )


def _contrato_prazo_garantia_context(orcamento):
    """Constrói texto jurídico para cláusulas 2 (pagamento), 3 (prazo) e 5 (garantia) a partir dos campos estruturados."""
    from num2words import num2words
    from .models_stock import ParcelaPagamentoOrcamento

    ctx = {}
    # Pagamento: parcelas (se existirem) ou fallback para 2 percentagens
    parcelas_qs = getattr(orcamento, 'parcelas_pagamento', None)
    if parcelas_qs is not None and parcelas_qs.exists():
        parcelas = list(parcelas_qs.order_by('numero_ordem'))
        total_pct = sum(p.percentagem for p in parcelas)
        if total_pct != 100:
            parcelas = []
        if parcelas:
            partes = []
            for p in parcelas:
                try:
                    p_ext = num2words(p.percentagem, lang='pt') + ' por cento'
                except Exception:
                    p_ext = str(p.percentagem) + ' por cento'
                if p.tipo == ParcelaPagamentoOrcamento.TIPO_ASSINATURA:
                    partes.append(f'({p.numero_ordem}) {p.percentagem}% ({p_ext}) no ato da assinatura do presente contrato')
                elif p.tipo == ParcelaPagamentoOrcamento.TIPO_CONCLUSAO_SERVICOS:
                    servicos = list(p.servicos.all())
                    nomes = [getattr(s, 'nome_para_documento', None) or (s.servico.nome if getattr(s, 'servico', None) else str(s)) for s in servicos]
                    nomes = [n for n in nomes if n]
                    if nomes:
                        lista_serv = '; '.join(nomes[:10])
                        if len(servicos) > 10:
                            lista_serv += '; etc.'
                        partes.append(f'({p.numero_ordem}) {p.percentagem}% ({p_ext}) na conclusão dos trabalhos correspondentes aos seguintes serviços: {lista_serv}')
                    else:
                        partes.append(f'({p.numero_ordem}) {p.percentagem}% ({p_ext}) na conclusão dos serviços seleccionados')
                else:
                    partes.append(f'({p.numero_ordem}) {p.percentagem}% ({p_ext}) na conclusão total dos serviços')
            ctx['pagamento_estruturado'] = True
            n_parcelas = len(parcelas)
            # Lista de textos por parcela (sem o prefixo "(n) ") para listagem vertical no contrato
            import re
            partes_li = [re.sub(r'^\(\d+\)\s*', '', s).strip() for s in partes]
            ctx['pagamento_parcelas_texto'] = partes_li
            if n_parcelas == 1:
                ctx['pagamento_texto'] = 'O pagamento será efectuado numa única parcela: ' + (partes_li[0] if partes_li else '') + '.'
            else:
                ctx['pagamento_texto'] = (
                    'O pagamento será efectuado em ' + str(n_parcelas) + ' parcelas, do seguinte modo: '
                    + '; '.join(partes) + '.'
                )
            ctx['pagamento_parcelas'] = parcelas
        else:
            _contrato_fallback_pagamento(ctx, orcamento)
    else:
        _contrato_fallback_pagamento(ctx, orcamento)
    # Prazo estruturado
    prazo_num = getattr(orcamento, 'prazo_execucao_numero', None) or 30
    prazo_uni = getattr(orcamento, 'prazo_execucao_unidade', None) or 'MESES'
    modo_fins = getattr(orcamento, 'prazo_fins_semana_modo', None) or ''
    if not modo_fins:
        excluir_fins = getattr(orcamento, 'prazo_excluir_fins_semana', True)
        modo_fins = 'SABADO_DOMINGO' if excluir_fins else 'CORRIDOS'
    excluir_feriados = getattr(orcamento, 'prazo_excluir_feriados', True)
    try:
        prazo_extenso = num2words(prazo_num, lang='pt')
    except Exception:
        prazo_extenso = str(prazo_num)
    unidade_label = {'DIAS': 'dias', 'MESES': 'meses', 'ANOS': 'anos'}.get(prazo_uni, 'meses')
    if modo_fins == 'CORRIDOS':
        qualificativo = 'corridos'
    elif modo_fins == 'SO_DOMINGO':
        qualificativo = 'úteis, excluindo apenas domingos' + (' e feriados nacionais em Moçambique' if excluir_feriados else '')
    elif modo_fins == 'SABADO_MEIO':
        qualificativo = 'úteis, com sábado a contar como meio dia e excluindo domingos' + (' e feriados nacionais em Moçambique' if excluir_feriados else '')
    else:
        qualificativo = 'úteis, excluindo sábados e domingos' + (' e feriados nacionais em Moçambique' if excluir_feriados else '')
    ctx['prazo_estruturado'] = True
    ctx['prazo_numero'] = prazo_num
    ctx['prazo_extenso'] = prazo_extenso
    ctx['prazo_unidade'] = unidade_label
    ctx['prazo_qualificativo'] = qualificativo
    ctx['prazo_texto'] = (
        f'O prazo para a execução dos serviços é de {prazo_num} ({prazo_extenso}) {unidade_label} {qualificativo}, '
        'contados a partir da data de assinatura do presente contrato ou do pagamento da primeira prestação, '
        'o que ocorrer por último.'
    )
    # Garantia estruturada
    garantia_dias = orcamento.validade_garantia_dias or 90
    garantia_uni = getattr(orcamento, 'validade_garantia_unidade', None) or 'DIAS'
    if garantia_uni == 'MESES':
        garantia_num = max(1, garantia_dias // 30)
    elif garantia_uni == 'ANOS':
        garantia_num = max(1, garantia_dias // 365)
    else:
        garantia_num = garantia_dias
    try:
        garantia_extenso = num2words(garantia_num, lang='pt')
    except Exception:
        garantia_extenso = str(garantia_num)
    garantia_unidade_label = {'DIAS': 'dias', 'MESES': 'meses', 'ANOS': 'anos'}.get(garantia_uni, 'dias')
    ctx['garantia_estruturado'] = True
    ctx['garantia_numero'] = garantia_num
    ctx['garantia_extenso'] = garantia_extenso
    ctx['garantia_unidade'] = garantia_unidade_label
    ctx['garantia_texto'] = (
        f'A CONTRATADA concede ao CONTRATANTE uma garantia de {garantia_num} ({garantia_extenso}) {garantia_unidade_label} '
        'sobre os serviços executados, pelos defeitos de execução ou vícios, a contar da data de conclusão dos trabalhos, '
        'nos termos da legislação aplicável na República de Moçambique.'
    )
    ctx['validade_garantia_dias'] = garantia_dias
    # Obrigações das partes (cláusula 4) – pré-definidas e editáveis
    _DEFAULT_OBRIG_C1 = 'Executar os serviços com rigor técnico, segurança e qualidade, em conformidade com a legislação aplicável.'
    _DEFAULT_OBRIG_C2 = 'Providenciar a mão-de-obra e os meios necessários à execução dos serviços.'
    _DEFAULT_OBRIG_C3 = 'Cumprir as normas de higiene e segurança no trabalho em vigor na República de Moçambique.'
    _DEFAULT_OBRIG_T1 = 'Facilitar o acesso ao local dos trabalhos e as condições necessárias à sua execução.'
    _DEFAULT_OBRIG_T2 = 'Prestar as informações e esclarecimentos necessários.'
    _DEFAULT_OBRIG_T3 = 'Cumprir os pagamentos nos prazos acordados.'
    ctx['obrigacoes_estruturado'] = True
    ctx['obrigacao_contratada_1'] = getattr(orcamento, 'obrigacao_contratada_1', None) or _DEFAULT_OBRIG_C1
    ctx['obrigacao_contratada_2'] = getattr(orcamento, 'obrigacao_contratada_2', None) or _DEFAULT_OBRIG_C2
    ctx['obrigacao_contratada_3'] = getattr(orcamento, 'obrigacao_contratada_3', None) or _DEFAULT_OBRIG_C3
    ctx['obrigacao_contratante_1'] = getattr(orcamento, 'obrigacao_contratante_1', None) or _DEFAULT_OBRIG_T1
    ctx['obrigacao_contratante_2'] = getattr(orcamento, 'obrigacao_contratante_2', None) or _DEFAULT_OBRIG_T2
    ctx['obrigacao_contratante_3'] = getattr(orcamento, 'obrigacao_contratante_3', None) or _DEFAULT_OBRIG_T3
    # Cláusula de suspensão por condições climáticas (opcional)
    ctx['incluir_clausula_suspensao_clima'] = getattr(orcamento, 'incluir_clausula_suspensao_clima', False)
    _TEXTO_PADRAO_SUSPENSAO_CLIMA = (
        'As partes reconhecem que as condições climáticas adversas (nomeadamente chuva intensa, vento forte ou outras '
        'que impeçam ou condicionem de forma relevante a execução dos trabalhos) podem determinar a suspensão das '
        'actividades. Os dias em que as actividades forem suspensas por esse motivo não contarão para o prazo de '
        'execução previsto na cláusula 3.'
    )
    ctx['clausula_suspensao_clima_texto'] = (
        getattr(orcamento, 'clausula_suspensao_clima', None) or _TEXTO_PADRAO_SUSPENSAO_CLIMA
    )
    return ctx


# Rótulos curtos para fases de ordem (gráficos)
ORDEM_FASE_LABELS = {
    'FASE1_CRIACAO': 'Fase 1',
    'FASE2_EXECUCAO': 'Fase 2',
    'FASE3_FINALIZACAO': 'Fase 3',
    'FINALIZADA': 'Finalizada',
    'CANCELADA': 'Cancelada',
}


@login_required
def producao_main(request):
    """Página principal do módulo de Produção (layout e estilo alinhados a Finanças)."""
    try:
        from django.db.models import Count, Sum
        from django.utils import timezone
        from datetime import timedelta, datetime

        hoje = timezone.now()
        # Período: parâmetros GET ou últimos 30 dias
        data_fim = hoje.date()
        try:
            data_inicio_str = request.GET.get('data_inicio')
            data_fim_str = request.GET.get('data_fim')
            if data_inicio_str:
                data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
            else:
                data_inicio = (hoje - timedelta(days=30)).date()
            if data_fim_str:
                data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            data_inicio = (hoje - timedelta(days=30)).date()

        # —— 3 indicadores (à semelhança de Finanças) ——
        total_ordens = OrdemProducao.objects.count()
        ordens_em_producao = OrdemProducao.objects.filter(
            fase_atual__in=['FASE2_EXECUCAO', 'FASE3_FINALIZACAO']
        ).count()
        ordens_periodo = OrdemProducao.objects.filter(
            data_criacao__date__gte=data_inicio,
            data_criacao__date__lte=data_fim,
        )
        quantidade_produzida = ordens_periodo.filter(
            fase_atual='FINALIZADA'
        ).aggregate(t=Sum('quantidade_produzida'))['t'] or 0

        # —— Dados para gráficos ——
        ordens_por_fase = list(
            OrdemProducao.objects.values('fase_atual')
            .annotate(total=Count('id'))
            .order_by('fase_atual')
        )
        chart_ordens_labels = [
            ORDEM_FASE_LABELS.get(r['fase_atual'], r['fase_atual'])
            for r in ordens_por_fase
        ]
        chart_ordens_data = [r['total'] for r in ordens_por_fase]

        receitas_com_ordens = list(
            Receita.objects.annotate(total_ordens=Count('ordens_producao'))
            .filter(total_ordens__gt=0)
            .order_by('-total_ordens')[:5]
        )
        chart_receitas_labels = [r.nome[:20] + ('…' if len(r.nome) > 20 else '') for r in receitas_com_ordens]
        chart_receitas_data = [r.total_ordens for r in receitas_com_ordens]
        if not chart_receitas_data:
            chart_receitas_labels = ['Nenhuma']
            chart_receitas_data = [1]

        maquinas_disponiveis = Maquina.objects.filter(status='DISPONIVEL').count()
        maquinas_em_uso = Maquina.objects.filter(status='EM_USO').count()
        maquinas_manutencao = Maquina.objects.filter(status='MANUTENCAO').count()
        chart_maquinas_labels = ['Disponíveis', 'Em uso', 'Manutenção']
        chart_maquinas_data = [maquinas_disponiveis, maquinas_em_uso, maquinas_manutencao]
        if sum(chart_maquinas_data) == 0:
            chart_maquinas_data = [1]
            chart_maquinas_labels = ['Nenhuma']

        import json
        context = {
            'title': 'Produção',
            'data_inicio': data_inicio.isoformat(),
            'data_fim': data_fim.isoformat(),
            'total_ordens': total_ordens,
            'ordens_em_producao': ordens_em_producao,
            'quantidade_produzida': quantidade_produzida,
            'chart_ordens_labels': json.dumps(chart_ordens_labels),
            'chart_ordens_data': json.dumps(chart_ordens_data),
            'chart_receitas_labels': json.dumps(chart_receitas_labels),
            'chart_receitas_data': json.dumps(chart_receitas_data),
            'chart_maquinas_labels': json.dumps(chart_maquinas_labels),
            'chart_maquinas_data': json.dumps(chart_maquinas_data),
        }
    except Exception as e:
        from datetime import timedelta
        logger.error(f"Erro ao carregar página principal de produção: {e}", exc_info=True)
        import json
        context = {
            'title': 'Produção',
            'data_inicio': (timezone.now() - timedelta(days=30)).date().isoformat(),
            'data_fim': timezone.now().date().isoformat(),
            'total_ordens': 0,
            'ordens_em_producao': 0,
            'quantidade_produzida': 0,
            'chart_ordens_labels': json.dumps([]),
            'chart_ordens_data': json.dumps([]),
            'chart_receitas_labels': json.dumps(['Nenhuma']),
            'chart_receitas_data': json.dumps([1]),
            'chart_maquinas_labels': json.dumps(['Nenhuma']),
            'chart_maquinas_data': json.dumps([1]),
        }

    return render(request, 'producao/main.html', context)


@login_required
def producao_dashboard(request):
    """Dashboard executivo do módulo de produção"""
    try:
        from django.db.models import Count, Sum, Q, Avg
        from datetime import datetime, timedelta
        
        # Período de análise (últimos 30 dias)
        hoje = timezone.now()
        ultimos_30_dias = hoje - timedelta(days=30)
        
        # Estatísticas Gerais
        total_receitas = Receita.objects.count()
        receitas_ativas = Receita.objects.filter(status__in=['ATIVA', 'APROVADA']).count()
        
        total_processos = ProcessoProducao.objects.count()
        processos_ativos = ProcessoProducao.objects.filter(status='ATIVO').count()
        processos_aprovados = ProcessoProducao.objects.filter(status='APROVADO').count()
        
        total_ordens = OrdemProducao.objects.count()
        ordens_em_producao = OrdemProducao.objects.filter(fase_atual='FASE2_EXECUCAO').count()
        ordens_planejadas = OrdemProducao.objects.filter(fase_atual='FASE1_CRIACAO', status_aprovacao='APROVADA').count()
        ordens_concluidas = OrdemProducao.objects.filter(fase_atual='FINALIZADA').count()
        ordens_pendentes = OrdemProducao.objects.filter(fase_atual='FASE1_CRIACAO', status_aprovacao__in=['PENDENTE', 'RASCUNHO']).count()
        
        total_maquinas = Maquina.objects.count()
        maquinas_disponiveis = Maquina.objects.filter(status='DISPONIVEL').count()
        maquinas_em_uso = Maquina.objects.filter(status='EM_USO').count()
        maquinas_manutencao = Maquina.objects.filter(status='MANUTENCAO').count()
        
        total_linhas = LinhaProducao.objects.count()
        linhas_ativas = LinhaProducao.objects.filter(status='ATIVA').count()
        linhas_manutencao = LinhaProducao.objects.filter(status='MANUTENCAO').count()
        
        # Ordens recentes (últimos 30 dias) - se não houver nos últimos 30 dias, mostrar as mais recentes
        ordens_recentes_30_dias = list(OrdemProducao.objects.filter(
            data_criacao__gte=ultimos_30_dias
        ).select_related('receita', 'sucursal', 'criado_por').order_by('-data_criacao')[:10])
        
        # Se não houver ordens nos últimos 30 dias, mostrar as mais recentes de todos os tempos
        if ordens_recentes_30_dias:
            ordens_recentes = ordens_recentes_30_dias
        else:
            ordens_recentes = list(OrdemProducao.objects.select_related(
                'receita', 'sucursal', 'criado_por'
            ).order_by('-data_criacao')[:10])
        
        # Estatísticas de produção (últimos 30 dias)
        ordens_periodo = OrdemProducao.objects.filter(data_criacao__gte=ultimos_30_dias)
        quantidade_total_produzida = ordens_periodo.filter(fase_atual='FINALIZADA').aggregate(
            total=Sum('quantidade_produzida')
        )['total'] or 0
        
        quantidade_total_planejada = ordens_periodo.aggregate(
            total=Sum('quantidade')
        )['total'] or 0
        
        # Taxa de conclusão
        taxa_conclusao = 0
        if quantidade_total_planejada > 0:
            taxa_conclusao = (quantidade_total_produzida / quantidade_total_planejada) * 100
        
        # Ordens por fase
        ordens_por_status = OrdemProducao.objects.values('fase_atual').annotate(
            total=Count('id')
        ).order_by('fase_atual')
        
        # Processos mais utilizados (mostrar os processos mais recentes)
        # Nota: Não há relacionamento direto entre ProcessoProducao e OrdemProducao no modelo atual
        processos_mais_utilizados = list(ProcessoProducao.objects.all().order_by('-data_criacao')[:5])
        
        # Receitas mais utilizadas (ou todas as receitas se nenhuma tiver ordens)
        receitas_com_ordens = list(Receita.objects.annotate(
            total_ordens=Count('ordens_producao')
        ).filter(total_ordens__gt=0).order_by('-total_ordens')[:5])
        
        # Se não houver receitas com ordens, mostrar as receitas mais recentes
        if receitas_com_ordens:
            receitas_mais_utilizadas = receitas_com_ordens
        else:
            receitas_mais_utilizadas = list(Receita.objects.all().order_by('-id')[:5])
        
        # Máquinas mais utilizadas (por linhas) - relacionamento ManyToMany reverso
        try:
            maquinas_mais_utilizadas = list(Maquina.objects.annotate(
                total_linhas=Count('linhas_producao')
            ).filter(total_linhas__gt=0).order_by('-total_linhas')[:5])
        except Exception as e:
            logger.warning(f"Erro ao buscar máquinas mais utilizadas: {e}")
            maquinas_mais_utilizadas = []
        
        # Linhas com mais máquinas
        linhas_com_mais_maquinas = list(LinhaProducao.objects.annotate(
            total_maquinas=Count('maquinas')
        ).filter(total_maquinas__gt=0).order_by('-total_maquinas')[:5])
        
        # Alertas e notificações
        alertas = []
        
        # Máquinas em manutenção
        if maquinas_manutencao > 0:
            alertas.append({
                'tipo': 'warning',
                'icone': 'fa-tools',
                'titulo': f'{maquinas_manutencao} Máquina(s) em Manutenção',
                'mensagem': 'Algumas máquinas estão em manutenção e podem afetar a produção.'
            })
        
        # Linhas em manutenção
        if linhas_manutencao > 0:
            alertas.append({
                'tipo': 'warning',
                'icone': 'fa-layer-group',
                'titulo': f'{linhas_manutencao} Linha(s) em Manutenção',
                'mensagem': 'Algumas linhas de produção estão em manutenção.'
            })
        
        # Ordens atrasadas (aprovadas mas não iniciadas após data planejada)
        hoje_date = hoje.date()
        ordens_atrasadas = OrdemProducao.objects.filter(
            fase_atual='FASE1_CRIACAO',
            status_aprovacao='APROVADA',
            data_inicio_fase2__isnull=True
        ).filter(
            data_criacao__lt=ultimos_30_dias
        ).count()
        
        if ordens_atrasadas > 0:
            alertas.append({
                'tipo': 'danger',
                'icone': 'fa-exclamation-triangle',
                'titulo': f'{ordens_atrasadas} Ordem(ns) Atrasada(s)',
                'mensagem': 'Existem ordens que deveriam ter iniciado mas ainda não foram iniciadas.'
            })
        
        # Processos sem receitas associadas
        processos_sem_receitas = ProcessoProducao.objects.filter(receitas__isnull=True).count()
        if processos_sem_receitas > 0:
            alertas.append({
                'tipo': 'info',
                'icone': 'fa-info-circle',
                'titulo': f'{processos_sem_receitas} Processo(s) sem Receitas',
                'mensagem': 'Alguns processos não têm receitas associadas.'
            })
        
        context = {
            # Estatísticas gerais
            'total_receitas': total_receitas,
            'receitas_ativas': receitas_ativas,
            'total_processos': total_processos,
            'processos_ativos': processos_ativos,
            'processos_aprovados': processos_aprovados,
            'total_ordens': total_ordens,
            'ordens_em_producao': ordens_em_producao,
            'ordens_planejadas': ordens_planejadas,
            'ordens_concluidas': ordens_concluidas,
            'ordens_pendentes': ordens_pendentes,
            'total_maquinas': total_maquinas,
            'maquinas_disponiveis': maquinas_disponiveis,
            'maquinas_em_uso': maquinas_em_uso,
            'maquinas_manutencao': maquinas_manutencao,
            'total_linhas': total_linhas,
            'linhas_ativas': linhas_ativas,
            'linhas_manutencao': linhas_manutencao,
            
            # Métricas de produção
            'quantidade_total_produzida': quantidade_total_produzida,
            'quantidade_total_planejada': quantidade_total_planejada,
            'taxa_conclusao': taxa_conclusao,
            
            # Dados para gráficos
            'ordens_por_status': ordens_por_status,
            'processos_mais_utilizados': processos_mais_utilizados,
            'receitas_mais_utilizadas': receitas_mais_utilizadas,
            'maquinas_mais_utilizadas': maquinas_mais_utilizadas,
            'linhas_com_mais_maquinas': linhas_com_mais_maquinas,
            
            # Ordens recentes
            'ordens_recentes': ordens_recentes,
            
            # Alertas
            'alertas': alertas,
            'ordens_atrasadas': ordens_atrasadas,
            
            # Período
            'periodo_inicio': ultimos_30_dias.date(),
            'periodo_fim': hoje.date(),
        }
        
        return render(request, 'producao/dashboard.html', context)
    except Exception as e:
        logger.error(f"Erro ao carregar dashboard de produção: {e}", exc_info=True)
        import traceback
        logger.error(f"Traceback completo: {traceback.format_exc()}")
        messages.error(request, f'Erro ao carregar dashboard de produção: {str(e)}')
        context = {
            'total_receitas': 0,
            'receitas_ativas': 0,
            'total_processos': 0,
            'processos_ativos': 0,
            'processos_aprovados': 0,
            'total_ordens': 0,
            'ordens_em_producao': 0,
            'ordens_planejadas': 0,
            'ordens_concluidas': 0,
            'ordens_pendentes': 0,
            'total_maquinas': 0,
            'maquinas_disponiveis': 0,
            'maquinas_em_uso': 0,
            'maquinas_manutencao': 0,
            'total_linhas': 0,
            'linhas_ativas': 0,
            'linhas_manutencao': 0,
            'quantidade_total_produzida': 0,
            'quantidade_total_planejada': 0,
            'taxa_conclusao': 0,
            'ordens_por_status': [],
            'processos_mais_utilizados': [],
            'receitas_mais_utilizadas': [],
            'maquinas_mais_utilizadas': [],
            'linhas_com_mais_maquinas': [],
            'ordens_recentes': [],
            'alertas': [],
            'ordens_atrasadas': 0,
        }
        return render(request, 'producao/dashboard.html', context)


@login_required
def producao_processos(request):
    """Lista de processos de produção com filtros e paginação"""
    try:
        # Parâmetros de busca e filtro
        search_query = request.GET.get('q', '').strip()
        status = request.GET.get('status')
        receita_id = request.GET.get('receita')
        
        # Query base com otimizações
        processos = ProcessoProducao.objects.prefetch_related(
            'receitas', 'receitas__produto', 'etapas', 'criado_por'
        ).all()
        
        # Aplicar filtros
        if search_query:
            processos = processos.filter(
                Q(codigo__icontains=search_query) |
                Q(nome__icontains=search_query) |
                Q(descricao__icontains=search_query)
            )
        
        if status:
            processos = processos.filter(status=status)
        
        if receita_id:
            processos = processos.filter(receitas__id=receita_id).distinct()
        
        # Ordenação
        processos = processos.order_by('-data_criacao')
        
        # Paginação
        paginator = Paginator(processos, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Estatísticas
        total_processos = ProcessoProducao.objects.count()
        processos_ativos = ProcessoProducao.objects.filter(status='ATIVO').count()
        processos_aprovados = ProcessoProducao.objects.filter(status='APROVADO').count()
        
        # Receitas para filtro (todas as receitas, não apenas ATIVA/APROVADA)
        receitas = Receita.objects.all().order_by('nome')
        
        context = {
            'page_obj': page_obj,
            'search_query': search_query,
            'status_filter': status,
            'receita_filter': receita_id,
            'receitas': receitas,
            'status_choices': ProcessoProducao.STATUS_CHOICES,
            'total_processos': total_processos,
            'processos_ativos': processos_ativos,
            'processos_aprovados': processos_aprovados,
        }
        return render(request, 'producao/processos/main.html', context)
    except Exception as e:
        logger.error(f"Erro ao listar processos de produção: {e}", exc_info=True)
        messages.error(request, f'Erro ao carregar processos de produção: {str(e)}')
        # Tentar retornar contexto mínimo mesmo em caso de erro
        try:
            receitas = Receita.objects.all().order_by('nome')
        except:
            receitas = []
        
        return render(request, 'producao/processos/main.html', {
            'page_obj': None,
            'search_query': '',
            'status_filter': None,
            'receita_filter': None,
            'receitas': receitas,
            'status_choices': ProcessoProducao.STATUS_CHOICES,
            'total_processos': 0,
            'processos_ativos': 0,
            'processos_aprovados': 0,
        })


@login_required
def producao_receitas(request):
    """Lista de receitas de produção com filtros e paginação"""
    try:
        # Parâmetros de busca e filtro
        search_query = request.GET.get('q', '').strip()
        produto_id = request.GET.get('produto')
        status = request.GET.get('status')

        # Query base com otimizações
        receitas = Receita.objects.select_related('produto').prefetch_related('itens').all()

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
        
        # Estatísticas
        total_receitas = Receita.objects.count()
        receitas_ativas = Receita.objects.filter(status='ATIVA').count()
        
        context = {
            'page_obj': page_obj,
            'receitas': page_obj,
            'search_query': search_query,
            'produto_id': produto_id,
            'status': status,
            'produtos': Item.objects.filter(status='ATIVO', tipo='PRODUTO').order_by('nome'),
            'status_choices': Receita.STATUS_CHOICES,
            'total_receitas': total_receitas,
            'receitas_ativas': receitas_ativas,
        }
        return render(request, 'producao/receitas/main.html', context)
    except Exception as e:
        logger.error(f"Erro ao listar receitas de produção: {e}")
        messages.error(request, 'Erro ao carregar lista de receitas.')
        return render(request, 'producao/receitas/main.html', {
            'page_obj': None,
            'receitas': [],
            'total_receitas': 0,
            'receitas_ativas': 0,
        })


@login_required
def producao_ordens(request):
    """Lista de ordens de produção com filtros e paginação"""
    try:
        # Parâmetros de busca e filtro
        search_query = request.GET.get('q', '').strip()
        fase = request.GET.get('fase')
        receita_id = request.GET.get('receita')
        
        # Query base com otimizações
        ordens = OrdemProducao.objects.select_related(
            'receita', 'receita__produto', 'sucursal', 'criado_por', 'aprovado_por', 'responsavel_fase2', 'responsavel_fase3'
        ).all()
        
        # Aplicar filtros
        if search_query:
            ordens = ordens.filter(
                Q(codigo__icontains=search_query) |
                Q(receita__nome__icontains=search_query) |
                Q(receita__produto__nome__icontains=search_query) |
                Q(observacoes_criacao__icontains=search_query) |
                Q(observacoes_execucao__icontains=search_query) |
                Q(observacoes_finalizacao__icontains=search_query)
            )
        
        if fase:
            ordens = ordens.filter(fase_atual=fase)
        
        if receita_id:
            ordens = ordens.filter(receita_id=receita_id)
        
        # Ordenação
        ordens = ordens.order_by('-data_criacao')
        
        # Paginação
        paginator = Paginator(ordens, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Estatísticas
        total_ordens = OrdemProducao.objects.count()
        ordens_fase1 = OrdemProducao.objects.filter(fase_atual='FASE1_CRIACAO').count()
        ordens_fase2 = OrdemProducao.objects.filter(fase_atual='FASE2_EXECUCAO').count()
        ordens_fase3 = OrdemProducao.objects.filter(fase_atual='FASE3_FINALIZACAO').count()
        ordens_finalizadas = OrdemProducao.objects.filter(fase_atual='FINALIZADA').count()
        
        context = {
            'page_obj': page_obj,
            'ordens': page_obj,
            'search_query': search_query,
            'fase': fase,
            'receita_id': receita_id,
            'receitas': Receita.objects.filter(status__in=['ATIVA', 'APROVADA']).order_by('nome'),
            'fase_choices': OrdemProducao.FASE_CHOICES,
            'total_ordens': total_ordens,
            'ordens_fase1': ordens_fase1,
            'ordens_fase2': ordens_fase2,
            'ordens_fase3': ordens_fase3,
            'ordens_finalizadas': ordens_finalizadas,
        }
        return render(request, 'producao/ordens/main.html', context)
    except Exception as e:
        logger.error(f"Erro ao listar ordens de produção: {e}", exc_info=True)
        messages.error(request, 'Erro ao carregar lista de ordens de produção.')
        return render(request, 'producao/ordens/main.html', {
            'page_obj': None,
            'ordens': [],
            'total_ordens': 0,
            'ordens_fase1': 0,
            'ordens_fase2': 0,
            'ordens_fase3': 0,
            'ordens_finalizadas': 0,
        })


# =============================================================================
# FASE 1: CRIAÇÃO E APROVAÇÃO
# =============================================================================

@login_required
@require_http_methods(["GET", "POST"])
def producao_ordem_fase1_criar(request):
    """FASE 1: Criar nova ordem de produção"""
    if request.method == 'POST':
        receita_id = request.POST.get('receita')
        quantidade = request.POST.get('quantidade')
        prioridade = request.POST.get('prioridade', 'NORMAL')
        sucursal_id = request.POST.get('sucursal')
        observacoes_criacao = request.POST.get('observacoes_criacao', '').strip()
        
        # Validação
        if not all([receita_id, quantidade, sucursal_id]):
            messages.error(request, 'Receita, quantidade e sucursal são obrigatórios.')
            return redirect('producao:ordem_fase1_criar')
        
        try:
            quantidade_int = int(quantidade)
            if quantidade_int <= 0:
                messages.error(request, 'Quantidade deve ser maior que zero.')
                return redirect('producao:ordem_fase1_criar')
        except (ValueError, TypeError):
            messages.error(request, 'Quantidade deve ser um número válido.')
            return redirect('producao:ordem_fase1_criar')
        
        try:
            with transaction.atomic():
                receita = Receita.objects.get(id=receita_id, status__in=['ATIVA', 'APROVADA'])
                sucursal = Sucursal.objects.get(id=sucursal_id, ativa=True)
                
                ordem = OrdemProducao(
                    receita=receita,
                    quantidade=quantidade_int,
                    prioridade=prioridade,
                    sucursal=sucursal,
                    observacoes_criacao=observacoes_criacao,
                    fase_atual='FASE1_CRIACAO',
                    status_aprovacao='PENDENTE',
                    criado_por=request.user
                )
                ordem.save()
                
                messages.success(request, f'Ordem de produção {ordem.codigo} criada com sucesso. Aguardando aprovação.')
                return redirect('producao:ordem_fase1', id=ordem.id)
        except Receita.DoesNotExist:
            messages.error(request, 'Receita selecionada não encontrada ou não está ativa.')
        except Sucursal.DoesNotExist:
            messages.error(request, 'Sucursal selecionada não encontrada ou não está ativa.')
        except Exception as e:
            logger.error(f"Erro ao criar ordem de produção: {e}", exc_info=True)
            messages.error(request, f'Erro ao criar ordem de produção: {str(e)}')
    
    # GET - Exibir formulário
    context = {
        'receitas': Receita.objects.filter(status__in=['ATIVA', 'APROVADA']).order_by('nome'),
        'sucursais': Sucursal.objects.filter(ativa=True).order_by('nome'),
        'prioridade_choices': OrdemProducao.PRIORIDADE_CHOICES,
    }
    return render(request, 'producao/ordens/fase1_criar.html', context)


@login_required
def producao_ordem_fase1(request, id):
    """FASE 1: Visualizar e aprovar/rejeitar ordem"""
    ordem = get_object_or_404(OrdemProducao.objects.select_related(
        'receita', 'receita__produto', 'sucursal', 'criado_por', 'aprovado_por'
    ).prefetch_related('receita__itens__material'), id=id)
    
    if ordem.fase_atual != 'FASE1_CRIACAO':
        messages.warning(request, 'Esta ordem já saiu da Fase 1.')
        return redirect('producao:ordens')
    
    # Calcular custo total da receita para exibição
    try:
        custo_receita = ordem.receita.calcular_custo_por_produto()
    except:
        custo_receita = Decimal('0.00')
    
    context = {
        'ordem': ordem,
        'custo_receita': custo_receita,
    }
    return render(request, 'producao/ordens/fase1.html', context)


@login_required
@require_http_methods(["POST"])
def producao_ordem_fase1_aprovar(request, id):
    """Aprovar ordem de produção"""
    ordem = get_object_or_404(OrdemProducao, id=id)
    
    if ordem.fase_atual != 'FASE1_CRIACAO':
        messages.error(request, 'Esta ordem não está na Fase 1.')
        return redirect('producao:ordens')
    
    if ordem.status_aprovacao == 'APROVADA':
        messages.warning(request, 'Esta ordem já foi aprovada.')
        return redirect('producao:ordem_fase1', id=id)
    
    try:
        with transaction.atomic():
            ordem.status_aprovacao = 'APROVADA'
            ordem.aprovado_por = request.user
            ordem.data_aprovacao = timezone.now()
            ordem.fase_atual = 'FASE2_EXECUCAO'
            ordem.data_inicio_fase2 = timezone.now()
            ordem.save()
            
            messages.success(request, f'Ordem {ordem.codigo} aprovada com sucesso. Avançando para Fase 2.')
            return redirect('producao:ordem_fase2', id=id)
    except Exception as e:
        logger.error(f"Erro ao aprovar ordem {id}: {e}", exc_info=True)
        messages.error(request, f'Erro ao aprovar ordem: {str(e)}')
    
    return redirect('producao:ordem_fase1', id=id)


@login_required
@require_http_methods(["POST"])
def producao_ordem_fase1_rejeitar(request, id):
    """Rejeitar ordem de produção"""
    ordem = get_object_or_404(OrdemProducao, id=id)
    
    if ordem.fase_atual != 'FASE1_CRIACAO':
        messages.error(request, 'Esta ordem não está na Fase 1.')
        return redirect('producao:ordens')
    
    motivo_rejeicao = request.POST.get('motivo_rejeicao', '').strip()
    if not motivo_rejeicao:
        messages.error(request, 'É obrigatório informar o motivo da rejeição.')
        return redirect('producao:ordem_fase1', id=id)
    
    try:
        with transaction.atomic():
            ordem.status_aprovacao = 'REJEITADA'
            ordem.motivo_rejeicao = motivo_rejeicao
            ordem.save()
            
            messages.success(request, f'Ordem {ordem.codigo} foi rejeitada.')
            return redirect('producao:ordens')
    except Exception as e:
        logger.error(f"Erro ao rejeitar ordem {id}: {e}", exc_info=True)
        messages.error(request, f'Erro ao rejeitar ordem: {str(e)}')
    
    return redirect('producao:ordem_fase1', id=id)


# =============================================================================
# FASE 2: PREPARAÇÃO E EXECUÇÃO
# =============================================================================

@login_required
def producao_ordem_fase2(request, id):
    """FASE 2: Preparação e Execução"""
    from .models_stock import RequisicaoProducao
    
    ordem = get_object_or_404(OrdemProducao.objects.select_related(
        'receita', 'receita__produto', 'sucursal', 'responsavel_fase2', 'requisicao_material',
        'requisicao_material__sucursal_origem', 'requisicao_material__aprovado_por', 'requisicao_material__ordem_producao'
    ).prefetch_related('receita__itens__material', 'requisicao_material__itens__item'), id=id)
    
    if ordem.fase_atual != 'FASE2_EXECUCAO':
        messages.warning(request, 'Esta ordem não está na Fase 2.')
        return redirect('producao:ordens')
    
    # Carregar requisição de material - tentar primeiro via relacionamento direto
    requisicao_material = ordem.requisicao_material
    
    # Se não encontrou via relacionamento, tentar buscar diretamente
    if not requisicao_material and ordem.requisicao_material_criada:
        try:
            requisicao_material = RequisicaoProducao.objects.select_related(
                'sucursal_origem', 'aprovado_por', 'ordem_producao'
            ).prefetch_related('itens__item').filter(
                ordem_producao=ordem
            ).order_by('-data_criacao').first()
            
            # Se encontrou, atualizar a ordem para manter consistência
            if requisicao_material:
                ordem.requisicao_material = requisicao_material
                ordem.save(update_fields=['requisicao_material'])
        except Exception as e:
            logger.warning(f"Erro ao carregar requisição de material para ordem {id}: {e}")
            requisicao_material = None
    
    context = {
        'ordem': ordem,
        'requisicao_material': requisicao_material,
    }
    return render(request, 'producao/ordens/fase2.html', context)


@login_required
@require_http_methods(["POST"])
def producao_ordem_fase2_criar_requisicao(request, id):
    """Criar requisição de material para a ordem"""
    ordem = get_object_or_404(OrdemProducao, id=id)
    
    if ordem.fase_atual != 'FASE2_EXECUCAO':
        messages.error(request, 'Esta ordem não está na Fase 2.')
        return redirect('producao:ordens')
    
    # Verificar se já existe uma requisição para esta ordem
    from .models_stock import RequisicaoProducao
    if ordem.requisicao_material:
        messages.info(request, f'Esta ordem já possui uma requisição de material: {ordem.requisicao_material.codigo}')
        return redirect('producao:ordem_fase2', id=id)
    
    # Verificar se existe alguma requisição pendente ou rascunho para esta ordem
    requisicao_existente = RequisicaoProducao.objects.filter(
        ordem_producao=ordem,
        status__in=['RASCUNHO', 'PENDENTE']
    ).first()
    
    if requisicao_existente:
        messages.warning(request, f'Já existe uma requisição {requisicao_existente.codigo} pendente para esta ordem.')
        return redirect('producao:ordem_fase2', id=id)
    
    try:
        with transaction.atomic():
            # Criar requisição de produção baseada nos itens da receita
            from .models_stock import ItemRequisicaoProducao, StockItem
            
            requisicao = RequisicaoProducao(
                ordem_producao=ordem,
                sucursal_origem=ordem.sucursal,
                status='RASCUNHO',
                observacoes=f'Requisição automática para Ordem de Produção {ordem.codigo}',
                criado_por=request.user
            )
            requisicao.save()
            
            # Calcular quantidades considerando o rendimento da receita
            # Se a receita tem rendimento de 2, e a ordem é para 1 unidade,
            # precisamos de 1/2 = 0.5 lotes, então multiplicamos pela quantidade do item
            if not ordem.receita:
                messages.error(request, 'A ordem não possui receita associada.')
                return redirect('producao:ordem_fase2', id=id)
            
            rendimento = ordem.receita.rendimento if ordem.receita.rendimento and ordem.receita.rendimento > 0 else 1
            if rendimento <= 0:
                rendimento = 1
            
            quantidade_lotes = Decimal(str(ordem.quantidade)) / Decimal(str(rendimento))
            
            # Log para debug
            logger.info(f"Criando requisição para ordem {ordem.codigo}: quantidade={ordem.quantidade}, rendimento={rendimento}, lotes={quantidade_lotes}")
            
            # Verificar stock disponível antes de criar itens
            itens_insuficientes = []
            for item_receita in ordem.receita.itens.all():
                # Quantidade necessária = quantidade do item na receita * número de lotes necessários
                quantidade_necessaria = int((item_receita.quantidade * quantidade_lotes).quantize(Decimal('1'), rounding=ROUND_UP))
                
                # Verificar stock disponível
                stock_item, created = StockItem.objects.get_or_create(
                    item=item_receita.material,
                    sucursal=ordem.sucursal,
                    defaults={'quantidade_atual': 0}
                )
                
                if stock_item.quantidade_atual < quantidade_necessaria:
                    itens_insuficientes.append({
                        'item': item_receita.material.nome,
                        'disponivel': stock_item.quantidade_atual,
                        'necessario': quantidade_necessaria
                    })
            
            # Se houver itens com stock insuficiente, avisar mas ainda criar a requisição
            if itens_insuficientes:
                aviso = f"Atenção: Alguns itens têm stock insuficiente (considerando rendimento da receita: {rendimento}):\n"
                for item_info in itens_insuficientes:
                    aviso += f"- {item_info['item']}: Disponível: {item_info['disponivel']}, Necessário: {item_info['necessario']}\n"
                messages.warning(request, aviso)
            
            # Adicionar itens da receita à requisição (considerando rendimento)
            for item_receita in ordem.receita.itens.all():
                # Quantidade solicitada = quantidade do item * número de lotes (arredondado para cima)
                quantidade_solicitada = int((item_receita.quantidade * quantidade_lotes).quantize(Decimal('1'), rounding=ROUND_UP))
                
                ItemRequisicaoProducao.objects.create(
                    requisicao=requisicao,
                    item=item_receita.material,
                    quantidade_solicitada=quantidade_solicitada
                )
            
            # Promover para pendente
            requisicao.promover_para_pendente()
            
            # Recarregar a requisição para garantir que está salva
            requisicao.refresh_from_db()
            
            # Atualizar ordem - garantir que o relacionamento seja salvo
            ordem.requisicao_material_criada = True
            ordem.requisicao_material = requisicao
            ordem.save(update_fields=['requisicao_material_criada', 'requisicao_material'])
            
            # Recarregar a ordem para garantir que o relacionamento está carregado
            ordem.refresh_from_db()
            
            # Verificar se a requisição foi realmente associada
            if not ordem.requisicao_material:
                logger.error(f"Erro: Requisição {requisicao.codigo} criada mas não associada à ordem {ordem.codigo}")
                # Tentar associar novamente
                ordem.requisicao_material = requisicao
                ordem.save(update_fields=['requisicao_material'])
                ordem.refresh_from_db()
            
            messages.success(request, f'Requisição de material {requisicao.codigo} criada com sucesso.')
            return redirect('producao:ordem_fase2', id=id)
    except Exception as e:
        logger.error(f"Erro ao criar requisição para ordem {id}: {e}", exc_info=True)
        messages.error(request, f'Erro ao criar requisição: {str(e)}')
    
    return redirect('producao:ordem_fase2', id=id)


@login_required
def producao_requisicao_imprimir(request, id):
    """Lista imprimível da requisição de material para coleta no stock"""
    from .models_stock import RequisicaoProducao
    requisicao = get_object_or_404(
        RequisicaoProducao.objects.select_related(
            'sucursal_origem', 'ordem_producao', 'criado_por'
        ).prefetch_related('itens__item'),
        id=id
    )
    
    context = {
        'requisicao': requisicao,
    }
    return render(request, 'producao/ordens/requisicao_imprimir.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def producao_ordem_fase2_confirmar_recebimento(request, id):
    """Confirmar recebimento de material na produção - formulário com quantidades"""
    ordem = get_object_or_404(OrdemProducao, id=id)
    
    if ordem.fase_atual != 'FASE2_EXECUCAO':
        messages.error(request, 'Esta ordem não está na Fase 2.')
        return redirect('producao:ordens')
    
    if not ordem.requisicao_material:
        messages.error(request, 'Nenhuma requisição de material associada a esta ordem.')
        return redirect('producao:ordem_fase2', id=id)
    
    from .models_stock import RequisicaoProducao, StockItem
    from django.db import transaction
    from decimal import Decimal
    
    requisicao = ordem.requisicao_material
    
    # Verificar se a requisição está aprovada (confirmada pelo armazém)
    if requisicao.status != 'APROVADA':
        messages.error(request, f'A requisição {requisicao.codigo} ainda não foi confirmada pelo armazém.')
        return redirect('producao:ordem_fase2', id=id)
    
    # Verificar se já foi processada
    if requisicao.status == 'ATENDIDA':
        messages.info(request, f'O material da requisição {requisicao.codigo} já foi recebido e processado.')
        return redirect('producao:ordem_fase2', id=id)
    
    if request.method == 'POST':
        # Processar confirmação de recebimento
        try:
            from .models_stock import MovimentoItem, TipoMovimentoStock
            
            # Processar o consumo (reduzir stock)
            with transaction.atomic():
                # Buscar ou criar tipo de movimento para consumo
                tipo_consumo = TipoMovimentoStock.objects.filter(
                    codigo='CONSUMO'
                ).first()
                
                if not tipo_consumo:
                    tipo_consumo = TipoMovimentoStock.objects.create(
                        nome='Consumo',
                        codigo='CONSUMO',
                        descricao='Consumo de material para produção',
                        aumenta_estoque=False
                    )
                
                itens_processados = []
                
                # Processar cada item da requisição
                for item_requisicao in requisicao.itens.all():
                    quantidade_recebida = request.POST.get(f'quantidade_recebida_{item_requisicao.id}')
                    
                    if quantidade_recebida:
                        try:
                            quantidade_recebida = int(quantidade_recebida)
                            
                            # Validar quantidade
                            if quantidade_recebida < 0:
                                messages.error(request, f'Quantidade inválida para {item_requisicao.item.nome}.')
                                return redirect('producao:ordem_fase2_confirmar_recebimento', id=id)
                            
                            # A quantidade recebida não pode ser maior que a quantidade atendida pelo armazém
                            if quantidade_recebida > item_requisicao.quantidade_atendida:
                                messages.error(request, f'A quantidade recebida não pode ser maior que a quantidade atendida pelo armazém para {item_requisicao.item.nome}.')
                                return redirect('producao:ordem_fase2_confirmar_recebimento', id=id)
                            
                            if quantidade_recebida == 0:
                                continue  # Pular itens com quantidade zero
                            
                            item_obj = item_requisicao.item
                            if not item_obj:
                                continue
                            
                            # Verificar stock disponível na sucursal
                            stock_item, created = StockItem.objects.get_or_create(
                                item=item_obj,
                                sucursal=requisicao.sucursal_origem,
                                defaults={'quantidade_atual': 0}
                            )
                            
                            # IMPORTANTE: A quantidade recebida não pode ser maior que a quantidade atendida pelo armazém
                            # O armazém já separou/entregou essa quantidade, então o stock deve ter sido suficiente naquele momento
                            # A verificação aqui é apenas uma validação de segurança
                            # Se o armazém entregou, assumimos que havia stock suficiente naquele momento
                            # A única validação necessária é garantir que não estamos recebendo mais do que foi entregue
                            
                            # Verificar se há stock suficiente apenas como validação de segurança
                            # Mas considerar que se o armazém entregou, o stock estava disponível
                            if stock_item.quantidade_atual < quantidade_recebida:
                                # Se o armazém já entregou essa quantidade, o stock deveria estar disponível
                                # Mas pode ter sido consumido por outra requisição entre a entrega e o recebimento
                                # Neste caso, avisar mas permitir se a quantidade foi entregue pelo armazém
                                if quantidade_recebida > item_requisicao.quantidade_atendida:
                                    messages.error(
                                        request, 
                                        f'Quantidade recebida ({quantidade_recebida}) maior que a entregue pelo armazém ({item_requisicao.quantidade_atendida}) para {item_obj.nome}.'
                                    )
                                    return redirect('producao:ordem_fase2_confirmar_recebimento', id=id)
                                else:
                                    # O armazém entregou, mas o stock atual é menor - pode ter sido consumido
                                    # Ainda assim, permitir o recebimento se não exceder o entregue
                                    messages.warning(
                                        request, 
                                        f'Atenção: Stock atual ({stock_item.quantidade_atual}) menor que quantidade recebida ({quantidade_recebida}) para {item_obj.nome}. '
                                        f'Mas o armazém já entregou {item_requisicao.quantidade_atendida}, então o recebimento será processado.'
                                    )
                            
                            preco_custo = item_obj.preco_custo if hasattr(item_obj, 'preco_custo') else Decimal('0.00')
                            
                            # Criar movimento de saída (consumo)
                            MovimentoItem.objects.create(
                                codigo=f"MOV{requisicao.codigo}{item_requisicao.id}C",
                                item=item_obj,
                                tipo_movimento=tipo_consumo,
                                sucursal=requisicao.sucursal_origem,
                                quantidade=quantidade_recebida,
                                preco_unitario=preco_custo,
                                valor_total=preco_custo * quantidade_recebida,
                                referencia=f"Requisição {requisicao.codigo}",
                                observacoes=f"Consumo para produção - Ordem {ordem.codigo} - Confirmado por {request.user.get_full_name() or request.user.username}",
                                usuario=request.user
                            )
                            
                            itens_processados.append(item_requisicao)
                            
                        except ValueError:
                            messages.error(request, f'Quantidade inválida para {item_requisicao.item.nome}.')
                            return redirect('producao:ordem_fase2_confirmar_recebimento', id=id)
                
                if not itens_processados:
                    messages.error(request, 'Nenhum item foi processado. Verifique as quantidades recebidas.')
                    return redirect('producao:ordem_fase2_confirmar_recebimento', id=id)
                
                # Marcar requisição como atendida
                requisicao.status = 'ATENDIDA'
                requisicao.data_atendimento = timezone.now()
                requisicao.save()
                
                # Marcar automaticamente a preparação de peças como concluída
                # Quando o material é recebido, assume-se que as peças estão prontas para preparação
                ordem.preparacao_pecas_concluida = True
                ordem.save()
                
                messages.success(request, f'Recebimento de material confirmado! Requisição {requisicao.codigo} processada. Stock reduzido. Preparação de peças marcada automaticamente como concluída.')
                
        except Exception as e:
            logger.error(f"Erro ao confirmar recebimento na produção: {e}", exc_info=True)
            messages.error(request, f'Erro ao confirmar recebimento: {str(e)}')
        
        return redirect('producao:ordem_fase2', id=id)
    
    # GET - Mostrar formulário de confirmação
    # Preparar dados dos itens para o formulário
    itens_com_info = []
    for item_req in requisicao.itens.all():
        if item_req.quantidade_atendida > 0:  # Só mostrar itens que foram atendidos pelo armazém
            stock_item, created = StockItem.objects.get_or_create(
                item=item_req.item,
                sucursal=requisicao.sucursal_origem,
                defaults={'quantidade_atual': 0}
            )
            
            itens_com_info.append({
                'item_requisicao': item_req,
                'quantidade_solicitada': item_req.quantidade_solicitada,
                'quantidade_atendida': item_req.quantidade_atendida,  # Quantidade que o armazém confirmou que entregou
                'stock_disponivel': stock_item.quantidade_atual,
                'preco_custo': item_req.item.preco_custo if hasattr(item_req.item, 'preco_custo') else Decimal('0.00'),
            })
    
    if not itens_com_info:
        messages.warning(request, 'Nenhum item possui quantidade atendida definida pelo armazém.')
        return redirect('producao:ordem_fase2', id=id)
    
    context = {
        'ordem': ordem,
        'requisicao': requisicao,
        'itens_com_info': itens_com_info,
    }
    
    return render(request, 'producao/ordens/confirmar_recebimento.html', context)


@login_required
@require_http_methods(["POST"])
def producao_ordem_fase2_marcar_preparacao(request, id):
    """Marcar preparação de peças como concluída"""
    ordem = get_object_or_404(OrdemProducao, id=id)
    
    if ordem.fase_atual != 'FASE2_EXECUCAO':
        messages.error(request, 'Esta ordem não está na Fase 2.')
        return redirect('producao:ordens')
    
    try:
        ordem.preparacao_pecas_concluida = True
        ordem.save()
        messages.success(request, 'Preparação de peças marcada como concluída.')
    except Exception as e:
        logger.error(f"Erro ao marcar preparação para ordem {id}: {e}", exc_info=True)
        messages.error(request, f'Erro: {str(e)}')
    
    return redirect('producao:ordem_fase2', id=id)


@login_required
@require_http_methods(["POST"])
def producao_ordem_fase2_marcar_montagem(request, id):
    """Marcar montagem como concluída"""
    ordem = get_object_or_404(OrdemProducao, id=id)
    
    if ordem.fase_atual != 'FASE2_EXECUCAO':
        messages.error(request, 'Esta ordem não está na Fase 2.')
        return redirect('producao:ordens')
    
    try:
        ordem.montagem_concluida = True
        ordem.save()
        messages.success(request, 'Montagem marcada como concluída.')
    except Exception as e:
        logger.error(f"Erro ao marcar montagem para ordem {id}: {e}", exc_info=True)
        messages.error(request, f'Erro: {str(e)}')
    
    return redirect('producao:ordem_fase2', id=id)


@login_required
@require_http_methods(["POST"])
def producao_ordem_fase2_avancar(request, id):
    """Avançar para Fase 3"""
    ordem = get_object_or_404(OrdemProducao, id=id)
    
    if ordem.fase_atual != 'FASE2_EXECUCAO':
        messages.error(request, 'Esta ordem não está na Fase 2.')
        return redirect('producao:ordens')
    
    if not ordem.pode_avancar_fase():
        messages.error(request, 'Não é possível avançar. Complete todas as etapas da Fase 2.')
        return redirect('producao:ordem_fase2', id=id)
    
    try:
        with transaction.atomic():
            ordem.fase_atual = 'FASE3_FINALIZACAO'
            ordem.data_inicio_fase3 = timezone.now()
            ordem.save()
            
            messages.success(request, f'Ordem {ordem.codigo} avançou para Fase 3.')
            return redirect('producao:ordem_fase3', id=id)
    except Exception as e:
        logger.error(f"Erro ao avançar ordem {id} para Fase 3: {e}", exc_info=True)
        messages.error(request, f'Erro ao avançar: {str(e)}')
    
    return redirect('producao:ordem_fase2', id=id)


# =============================================================================
# FASE 3: ACABAMENTOS E FINALIZAÇÕES
# =============================================================================

@login_required
def producao_ordem_fase3(request, id):
    """FASE 3: Acabamentos e Finalizações"""
    ordem = get_object_or_404(OrdemProducao.objects.select_related(
        'receita', 'receita__produto', 'sucursal', 'responsavel_fase3', 'aprovado_qualidade_por'
    ), id=id)
    
    if ordem.fase_atual != 'FASE3_FINALIZACAO':
        messages.warning(request, 'Esta ordem não está na Fase 3.')
        return redirect('producao:ordens')
    
    context = {
        'ordem': ordem,
    }
    return render(request, 'producao/ordens/fase3.html', context)


@login_required
@require_http_methods(["POST"])
def producao_ordem_fase3_marcar_acabamentos(request, id):
    """Marcar acabamentos como concluídos"""
    ordem = get_object_or_404(OrdemProducao, id=id)
    
    if ordem.fase_atual != 'FASE3_FINALIZACAO':
        messages.error(request, 'Esta ordem não está na Fase 3.')
        return redirect('producao:ordens')
    
    try:
        ordem.acabamentos_concluidos = True
        ordem.save()
        messages.success(request, 'Acabamentos marcados como concluídos.')
    except Exception as e:
        logger.error(f"Erro ao marcar acabamentos para ordem {id}: {e}", exc_info=True)
        messages.error(request, f'Erro: {str(e)}')
    
    return redirect('producao:ordem_fase3', id=id)


@login_required
@require_http_methods(["POST"])
def producao_ordem_fase3_marcar_retoques(request, id):
    """Marcar retoques como concluídos"""
    ordem = get_object_or_404(OrdemProducao, id=id)
    
    if ordem.fase_atual != 'FASE3_FINALIZACAO':
        messages.error(request, 'Esta ordem não está na Fase 3.')
        return redirect('producao:ordens')
    
    try:
        ordem.retoques_concluidos = True
        ordem.save()
        messages.success(request, 'Retoques marcados como concluídos.')
    except Exception as e:
        logger.error(f"Erro ao marcar retoques para ordem {id}: {e}", exc_info=True)
        messages.error(request, f'Erro: {str(e)}')
    
    return redirect('producao:ordem_fase3', id=id)


@login_required
def producao_qualidade_inspecoes(request):
    """Lista de inspeções de qualidade"""
    try:
        from django.db.models import Q
        from django.core.paginator import Paginator
        
        # Buscar ordens que precisam de inspeção (Fase 3)
        ordens_inspecao = OrdemProducao.objects.filter(
            fase_atual='FASE3_FINALIZACAO'
        ).select_related(
            'receita', 'receita__produto', 'sucursal', 'criado_por'
        ).order_by('-data_criacao')
        
        # Filtros
        search_query = request.GET.get('search', '').strip()
        if search_query:
            ordens_inspecao = ordens_inspecao.filter(
                Q(codigo__icontains=search_query) |
                Q(receita__nome__icontains=search_query) |
                Q(receita__produto__nome__icontains=search_query)
            )
        
        # Paginação
        paginator = Paginator(ordens_inspecao, 20)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)
        
        # Estatísticas
        total_inspecoes = ordens_inspecao.count()
        inspecoes_pendentes = ordens_inspecao.filter(
            controle_qualidade_aprovado=False
        ).count()
        inspecoes_aprovadas = ordens_inspecao.filter(
            controle_qualidade_aprovado=True
        ).count()
        
        context = {
            'page_obj': page_obj,
            'ordens': page_obj,
            'search_query': search_query,
            'total_inspecoes': total_inspecoes,
            'inspecoes_pendentes': inspecoes_pendentes,
            'inspecoes_aprovadas': inspecoes_aprovadas,
        }
        return render(request, 'producao/qualidade/inspecoes.html', context)
    except Exception as e:
        logger.error(f"Erro ao listar inspeções de qualidade: {e}", exc_info=True)
        messages.error(request, 'Erro ao carregar inspeções de qualidade.')
        return redirect('producao:main')


@login_required
def producao_qualidade_nconformidades(request):
    """Lista de não conformidades de qualidade"""
    try:
        from django.db.models import Q
        from django.core.paginator import Paginator
        
        # Buscar ordens com não conformidades (rejeitadas, canceladas, ou com observações de qualidade negativas)
        ordens_nconformidades = OrdemProducao.objects.filter(
            Q(status_aprovacao='REJEITADA') |
            Q(fase_atual='CANCELADA') |
            (Q(observacoes_qualidade__isnull=False) & ~Q(observacoes_qualidade=''))
        ).select_related(
            'receita', 'receita__produto', 'sucursal', 'criado_por', 'aprovado_qualidade_por'
        ).order_by('-data_criacao')
        
        # Filtros
        search_query = request.GET.get('search', '').strip()
        if search_query:
            ordens_nconformidades = ordens_nconformidades.filter(
                Q(codigo__icontains=search_query) |
                Q(receita__nome__icontains=search_query) |
                Q(receita__produto__nome__icontains=search_query)
            )
        
        # Paginação
        paginator = Paginator(ordens_nconformidades, 20)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)
        
        # Estatísticas
        total_nconformidades = ordens_nconformidades.count()
        nconformidades_rejeitadas = ordens_nconformidades.filter(
            status_aprovacao='REJEITADA'
        ).count()
        nconformidades_canceladas = ordens_nconformidades.filter(
            fase_atual='CANCELADA'
        ).count()
        nconformidades_com_observacoes = ordens_nconformidades.exclude(
            observacoes_qualidade=''
        ).exclude(observacoes_qualidade__isnull=True).count()
        
        context = {
            'page_obj': page_obj,
            'ordens': page_obj,
            'search_query': search_query,
            'total_nconformidades': total_nconformidades,
            'nconformidades_rejeitadas': nconformidades_rejeitadas,
            'nconformidades_canceladas': nconformidades_canceladas,
            'nconformidades_com_observacoes': nconformidades_com_observacoes,
        }
        return render(request, 'producao/qualidade/nconformidades.html', context)
    except Exception as e:
        logger.error(f"Erro ao listar não conformidades: {e}", exc_info=True)
        messages.error(request, 'Erro ao carregar não conformidades.')
        return redirect('producao:main')


@login_required
def producao_qualidade_certificados(request):
    """Lista de certificados de qualidade (ordens finalizadas e aprovadas)"""
    try:
        from django.db.models import Q
        from django.core.paginator import Paginator
        
        # Buscar ordens finalizadas com qualidade aprovada (certificados)
        ordens_certificados = OrdemProducao.objects.filter(
            fase_atual='FINALIZADA',
            controle_qualidade_aprovado=True
        ).select_related(
            'receita', 'receita__produto', 'sucursal', 'criado_por', 'aprovado_qualidade_por'
        ).order_by('-data_finalizacao')
        
        # Filtros
        search_query = request.GET.get('search', '').strip()
        if search_query:
            ordens_certificados = ordens_certificados.filter(
                Q(codigo__icontains=search_query) |
                Q(receita__nome__icontains=search_query) |
                Q(receita__produto__nome__icontains=search_query)
            )
        
        # Paginação
        paginator = Paginator(ordens_certificados, 20)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)
        
        # Estatísticas
        from datetime import timedelta
        
        total_certificados = ordens_certificados.count()
        certificados_mes = ordens_certificados.filter(
            data_finalizacao__month=timezone.now().month,
            data_finalizacao__year=timezone.now().year
        ).count()
        certificados_ultimos_30_dias = ordens_certificados.filter(
            data_finalizacao__gte=timezone.now() - timedelta(days=30)
        ).count()
        
        context = {
            'page_obj': page_obj,
            'ordens': page_obj,
            'search_query': search_query,
            'total_certificados': total_certificados,
            'certificados_mes': certificados_mes,
            'certificados_ultimos_30_dias': certificados_ultimos_30_dias,
        }
        return render(request, 'producao/qualidade/certificados.html', context)
    except Exception as e:
        logger.error(f"Erro ao listar certificados de qualidade: {e}", exc_info=True)
        messages.error(request, 'Erro ao carregar certificados de qualidade.')
        return redirect('producao:main')


@login_required
def producao_qualidade_certificado_view(request, id):
    """Visualizar certificado de qualidade de uma ordem"""
    try:
        ordem = get_object_or_404(
            OrdemProducao.objects.select_related(
                'receita', 'receita__produto', 'sucursal', 
                'criado_por', 'aprovado_qualidade_por', 'aprovado_por'
            ),
            id=id,
            fase_atual='FINALIZADA',
            controle_qualidade_aprovado=True
        )
        
        # Obter dados da empresa
        from .models_base import DadosEmpresa
        try:
            dados_empresa = DadosEmpresa.objects.first()
        except:
            dados_empresa = None
        
        context = {
            'ordem': ordem,
            'dados_empresa': dados_empresa,
            'MEDIA_URL': settings.MEDIA_URL,
        }
        return render(request, 'producao/qualidade/certificado_view.html', context)
    except Exception as e:
        logger.error(f"Erro ao visualizar certificado da ordem {id}: {e}", exc_info=True)
        messages.error(request, 'Erro ao carregar certificado de qualidade.')
        return redirect('producao:qualidade_certificados')


@login_required
def producao_planejamento_capacidade(request):
    """Planejamento de capacidade produtiva"""
    try:
        from django.db.models import Sum, Count, Q
        from django.utils import timezone
        from datetime import timedelta
        
        # Buscar máquinas e linhas
        maquinas = Maquina.objects.select_related('sucursal').all()
        linhas = LinhaProducao.objects.select_related('sucursal').prefetch_related('maquinas').all()
        
        # Estatísticas de máquinas
        total_maquinas = maquinas.count()
        maquinas_disponiveis = maquinas.filter(status='DISPONIVEL').count()
        maquinas_em_uso = maquinas.filter(status='EM_USO').count()
        maquinas_manutencao = maquinas.filter(status='MANUTENCAO').count()
        
        # Estatísticas de linhas
        total_linhas = linhas.count()
        linhas_ativas = linhas.filter(status='ATIVA').count()
        linhas_manutencao = linhas.filter(status='MANUTENCAO').count()
        
        # Capacidade total
        capacidade_total_maquinas = maquinas.filter(
            capacidade__isnull=False
        ).aggregate(total=Sum('capacidade'))['total'] or 0
        
        capacidade_total_linhas = linhas.filter(
            capacidade_horaria__isnull=False
        ).aggregate(total=Sum('capacidade_horaria'))['total'] or 0
        
        # Ordens em produção
        ordens_em_producao = OrdemProducao.objects.filter(
            fase_atual__in=['FASE2_EXECUCAO', 'FASE3_FINALIZACAO']
        ).select_related('receita', 'receita__produto', 'sucursal').count()
        
        # Ordens planejadas
        ordens_planejadas = OrdemProducao.objects.filter(
            fase_atual='FASE1_CRIACAO',
            status_aprovacao='APROVADA'
        ).count()
        
        # Capacidade por sucursal
        capacidade_por_sucursal = []
        for sucursal in Sucursal.objects.all():
            maq_suc = maquinas.filter(sucursal=sucursal, capacidade__isnull=False)
            lin_suc = linhas.filter(sucursal=sucursal, capacidade_horaria__isnull=False)
            
            cap_maq = maq_suc.aggregate(total=Sum('capacidade'))['total'] or 0
            cap_lin = lin_suc.aggregate(total=Sum('capacidade_horaria'))['total'] or 0
            
            capacidade_por_sucursal.append({
                'sucursal': sucursal,
                'capacidade_maquinas': cap_maq,
                'capacidade_linhas': cap_lin,
                'total_maquinas': maq_suc.count(),
                'total_linhas': lin_suc.count(),
            })
        
        context = {
            'total_maquinas': total_maquinas,
            'maquinas_disponiveis': maquinas_disponiveis,
            'maquinas_em_uso': maquinas_em_uso,
            'maquinas_manutencao': maquinas_manutencao,
            'total_linhas': total_linhas,
            'linhas_ativas': linhas_ativas,
            'linhas_manutencao': linhas_manutencao,
            'capacidade_total_maquinas': capacidade_total_maquinas,
            'capacidade_total_linhas': capacidade_total_linhas,
            'ordens_em_producao': ordens_em_producao,
            'ordens_planejadas': ordens_planejadas,
            'capacidade_por_sucursal': capacidade_por_sucursal,
            'maquinas': maquinas[:10],  # Últimas 10 máquinas
            'linhas': linhas[:10],  # Últimas 10 linhas
        }
        return render(request, 'producao/planejamento/capacidade.html', context)
    except Exception as e:
        logger.error(f"Erro ao carregar planejamento de capacidade: {e}", exc_info=True)
        messages.error(request, 'Erro ao carregar planejamento de capacidade.')
        return redirect('producao:main')


@login_required
def producao_planejamento_cronograma(request):
    """Cronograma de produção"""
    try:
        from django.db.models import Q
        from django.utils import timezone
        from datetime import timedelta
        from django.core.paginator import Paginator
        
        # Filtros
        search_query = request.GET.get('search', '').strip()
        fase_filter = request.GET.get('fase', '')
        prioridade_filter = request.GET.get('prioridade', '')
        
        # Buscar ordens
        ordens = OrdemProducao.objects.select_related(
            'receita', 'receita__produto', 'sucursal', 'criado_por'
        ).order_by('data_criacao')
        
        # Aplicar filtros
        if search_query:
            ordens = ordens.filter(
                Q(codigo__icontains=search_query) |
                Q(receita__nome__icontains=search_query) |
                Q(receita__produto__nome__icontains=search_query)
            )
        
        if fase_filter:
            ordens = ordens.filter(fase_atual=fase_filter)
        
        if prioridade_filter:
            ordens = ordens.filter(prioridade=prioridade_filter)
        
        # Agrupar por data
        hoje = timezone.now().date()
        semana_atual = hoje - timedelta(days=hoje.weekday())
        proxima_semana = semana_atual + timedelta(days=7)
        
        ordens_hoje = ordens.filter(data_criacao__date=hoje)
        ordens_semana = ordens.filter(
            data_criacao__date__gte=semana_atual,
            data_criacao__date__lt=proxima_semana
        )
        ordens_proxima_semana = ordens.filter(
            data_criacao__date__gte=proxima_semana,
            data_criacao__date__lt=proxima_semana + timedelta(days=7)
        )
        ordens_futuras = ordens.filter(data_criacao__date__gte=proxima_semana + timedelta(days=7))
        
        # Estatísticas
        total_ordens = ordens.count()
        ordens_em_producao = ordens.filter(
            fase_atual__in=['FASE2_EXECUCAO', 'FASE3_FINALIZACAO']
        ).count()
        ordens_finalizadas = ordens.filter(fase_atual='FINALIZADA').count()
        ordens_pendentes = ordens.filter(fase_atual='FASE1_CRIACAO').count()
        
        # Paginação
        paginator = Paginator(ordens, 50)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)
        
        context = {
            'page_obj': page_obj,
            'ordens': page_obj,
            'search_query': search_query,
            'fase_filter': fase_filter,
            'prioridade_filter': prioridade_filter,
            'ordens_hoje': ordens_hoje,
            'ordens_semana': ordens_semana,
            'ordens_proxima_semana': ordens_proxima_semana,
            'ordens_futuras': ordens_futuras,
            'total_ordens': total_ordens,
            'ordens_em_producao': ordens_em_producao,
            'ordens_finalizadas': ordens_finalizadas,
            'ordens_pendentes': ordens_pendentes,
            'hoje': hoje,
            'semana_atual': semana_atual,
            'proxima_semana': proxima_semana,
        }
        return render(request, 'producao/planejamento/cronograma.html', context)
    except Exception as e:
        logger.error(f"Erro ao carregar cronograma: {e}", exc_info=True)
        messages.error(request, 'Erro ao carregar cronograma de produção.')
        return redirect('producao:main')


@login_required
def producao_planejamento_mrp(request):
    """MRP - Planejamento de Necessidades de Materiais"""
    try:
        from django.db.models import Q, Sum, F
        from django.utils import timezone
        from decimal import Decimal, ROUND_UP
        
        # Buscar ordens que precisam de materiais (Fase 1 aprovadas e Fase 2)
        ordens_mrp = OrdemProducao.objects.filter(
            Q(fase_atual='FASE1_CRIACAO', status_aprovacao='APROVADA') |
            Q(fase_atual='FASE2_EXECUCAO')
        ).select_related('receita', 'receita__produto', 'sucursal').prefetch_related(
            'receita__itens__material'
        )
        
        # Calcular necessidades de materiais
        necessidades_materiais = {}
        ordens_por_material = {}
        
        for ordem in ordens_mrp:
            if not ordem.receita:
                continue
            
            try:
                rendimento = ordem.receita.rendimento if ordem.receita.rendimento and ordem.receita.rendimento > 0 else 1
                quantidade_lotes = Decimal(str(ordem.quantidade)) / Decimal(str(rendimento))
                
                for item_receita in ordem.receita.itens.all():
                    if not item_receita.material:
                        continue
                    
                    material = item_receita.material
                    quantidade_necessaria = (item_receita.quantidade * quantidade_lotes).quantize(Decimal('0.001'), rounding=ROUND_UP)
                    
                    if material.id not in necessidades_materiais:
                        necessidades_materiais[material.id] = {
                            'material': material,
                            'quantidade_total': Decimal('0'),
                            'ordens': [],
                            'stock_por_sucursal': {}
                        }
                        ordens_por_material[material.id] = []
                    
                    necessidades_materiais[material.id]['quantidade_total'] += quantidade_necessaria
                    ordens_por_material[material.id].append({
                        'ordem': ordem,
                        'quantidade': quantidade_necessaria,
                        'item_receita': item_receita
                    })
            except Exception as e:
                logger.warning(f"Erro ao processar ordem {ordem.codigo} no MRP: {e}")
                continue
        
        # Buscar stock disponível por sucursal
        from .models_stock import StockItem
        
        for material_id, dados in necessidades_materiais.items():
            try:
                material = dados['material']
                if not material:
                    continue
                    
                stock_items = StockItem.objects.filter(item=material)
                
                for stock_item in stock_items:
                    try:
                        sucursal_id = stock_item.sucursal.id
                        if sucursal_id not in dados['stock_por_sucursal']:
                            dados['stock_por_sucursal'][sucursal_id] = {
                                'sucursal': stock_item.sucursal,
                                'stock': Decimal('0')
                            }
                        dados['stock_por_sucursal'][sucursal_id]['stock'] += Decimal(str(stock_item.quantidade_atual))
                    except Exception as e:
                        logger.warning(f"Erro ao processar stock do material {material.id}: {e}")
                        continue
            except Exception as e:
                logger.warning(f"Erro ao buscar stock do material {material_id}: {e}")
                continue
        
        # Calcular totais e identificar materiais com stock insuficiente
        materiais_insuficientes = []
        materiais_suficientes = []
        
        for material_id, dados in necessidades_materiais.items():
            try:
                stock_total = sum(s['stock'] for s in dados['stock_por_sucursal'].values())
                necessidade_total = dados['quantidade_total']
                faltante = necessidade_total - stock_total
                
                dados['stock_total'] = stock_total
                dados['faltante'] = faltante if faltante > 0 else Decimal('0')
                dados['ordens'] = ordens_por_material.get(material_id, [])
                
                if faltante > 0:
                    materiais_insuficientes.append(dados)
                else:
                    materiais_suficientes.append(dados)
            except Exception as e:
                logger.warning(f"Erro ao calcular totais do material {material_id}: {e}")
                continue
        
        # Estatísticas
        total_materiais = len(necessidades_materiais)
        materiais_com_stock = len(materiais_suficientes)
        materiais_sem_stock = len(materiais_insuficientes)
        total_ordens = ordens_mrp.count()
        
        context = {
            'materiais_insuficientes': materiais_insuficientes,
            'materiais_suficientes': materiais_suficientes,
            'total_materiais': total_materiais,
            'materiais_com_stock': materiais_com_stock,
            'materiais_sem_stock': materiais_sem_stock,
            'total_ordens': total_ordens,
            'ordens_mrp': ordens_mrp[:20],  # Últimas 20 ordens
        }
        return render(request, 'producao/planejamento/mrp.html', context)
    except Exception as e:
        logger.error(f"Erro ao carregar MRP: {e}", exc_info=True)
        messages.error(request, 'Erro ao carregar planejamento de necessidades de materiais.')
        return redirect('producao:main')


@login_required
def producao_servicos_list(request):
    """Catálogo de serviços"""
    try:
        from django.db.models import Q
        from django.core.paginator import Paginator
        
        # Buscar itens do tipo PRODUTO com produto_tipo='SERVICO'
        servicos = Item.objects.filter(
            tipo='PRODUTO',
            produto_tipo='SERVICO'
        ).order_by('nome')
        
        # Filtros
        search_query = request.GET.get('search', '').strip()
        if search_query:
            servicos = servicos.filter(
                Q(nome__icontains=search_query) |
                Q(codigo__icontains=search_query) |
                Q(descricao__icontains=search_query)
            )
        
        status_filter = request.GET.get('status', '')
        if status_filter:
            servicos = servicos.filter(status=status_filter)
        
        # Paginação
        paginator = Paginator(servicos, 20)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)
        
        # Estatísticas
        total_servicos = servicos.count()
        servicos_ativos = servicos.filter(status='ATIVO').count()
        servicos_inativos = servicos.filter(status='INATIVO').count()
        
        context = {
            'page_obj': page_obj,
            'servicos': page_obj,
            'search_query': search_query,
            'status_filter': status_filter,
            'total_servicos': total_servicos,
            'servicos_ativos': servicos_ativos,
            'servicos_inativos': servicos_inativos,
        }
        return render(request, 'producao/servicos/list.html', context)
    except Exception as e:
        logger.error(f"Erro ao listar serviços: {e}", exc_info=True)
        messages.error(request, 'Erro ao carregar catálogo de serviços.')
        return redirect('producao:main')


@login_required
def producao_servicos_ordens(request):
    """Lista de ordens de serviço"""
    try:
        # Filtros
        search_query = request.GET.get('q', '').strip()
        status_filter = request.GET.get('status', '')
        servico_id = request.GET.get('servico', '')
        
        # Buscar apenas ordens de serviço (código começa com 'OS'), não cotações
        ordens = OrdemServico.objects.select_related('servico', 'cliente', 'responsavel', 'criado_por', 'orcamento_origem').prefetch_related(
            'servicos_orcamento__servico'
        ).filter(
            codigo__startswith='OS'
        ).distinct()
        
        # Aplicar filtros
        if search_query:
            ordens = ordens.filter(
                Q(codigo__icontains=search_query) |
                Q(cliente__nome__icontains=search_query) |
                Q(servico__nome__icontains=search_query) |
                Q(endereco_servico__icontains=search_query)
            )
        
        if status_filter:
            ordens = ordens.filter(status=status_filter)
        
        if servico_id:
            ordens = ordens.filter(servico_id=servico_id)
        
        # Ordenação
        ordens = ordens.order_by('-data_agendada', '-data_criacao')
        
        # Paginação
        paginator = Paginator(ordens, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Estatísticas (apenas ordens de serviço, não cotações)
        total_ordens = OrdemServico.objects.filter(codigo__startswith='OS').count()
        ordens_pendentes = OrdemServico.objects.filter(codigo__startswith='OS', status='AGENDADA').count()
        ordens_em_andamento = OrdemServico.objects.filter(codigo__startswith='OS', status='EM_ANDAMENTO').count()
        ordens_concluidas = OrdemServico.objects.filter(codigo__startswith='OS', status='CONCLUIDA').count()
        ordens_canceladas = OrdemServico.objects.filter(codigo__startswith='OS', status='CANCELADA').count()
        
        # Buscar serviços ativos
        servicos = Item.objects.filter(tipo='PRODUTO', produto_tipo='SERVICO', status='ATIVO').order_by('nome')
        
        context = {
            'page_obj': page_obj,
            'ordens': page_obj,
            'search_query': search_query or '',
            'status_filter': status_filter or '',
            'servico_id': servico_id or '',
            'servicos': servicos,
            'total_ordens': total_ordens,
            'ordens_pendentes': ordens_pendentes,
            'ordens_em_andamento': ordens_em_andamento,
            'ordens_concluidas': ordens_concluidas,
            'ordens_canceladas': ordens_canceladas,
        }
        return render(request, 'producao/servicos/ordens.html', context)
    except Exception as e:
        logger.error(f"Erro ao listar ordens de serviço: {e}", exc_info=True)
        messages.error(request, 'Erro ao carregar lista de ordens de serviço.')
        return render(request, 'producao/servicos/ordens.html', {
            'page_obj': None,
            'ordens': [],
            'search_query': '',
            'status_filter': '',
            'servico_id': '',
            'servicos': Item.objects.none(),
            'total_ordens': 0,
            'ordens_pendentes': 0,
            'ordens_em_andamento': 0,
            'ordens_concluidas': 0,
            'ordens_canceladas': 0,
        })


@login_required
def producao_servicos_agendamento(request):
    """Agendamento de serviços - Lista de serviços agendados"""
    try:
        from django.utils import timezone
        from datetime import datetime, timedelta
        from django.db.models import Q
        
        # Filtros
        search_query = request.GET.get('q', '').strip()
        status_filter = request.GET.get('status', '')
        data_inicio = request.GET.get('data_inicio', '')
        data_fim = request.GET.get('data_fim', '')
        responsavel_id = request.GET.get('responsavel', '')
        
        # Query base - buscar ordens com data agendada e status ativo (não concluídas nem canceladas)
        ordens = OrdemServico.objects.filter(
            data_agendada__isnull=False
        ).exclude(
            status__in=['CONCLUIDA', 'CANCELADA']
        ).select_related('cliente', 'responsavel', 'criado_por').prefetch_related(
            'servicos_orcamento__servico'
        ).order_by('data_agendada')
        
        # Aplicar filtros
        if search_query:
            ordens = ordens.filter(
                Q(codigo__icontains=search_query) |
                Q(cliente__nome__icontains=search_query) |
                Q(nome_cliente_pagamento__icontains=search_query) |
                Q(endereco_servico__icontains=search_query) |
                Q(observacoes__icontains=search_query)
            )
        
        if status_filter:
            ordens = ordens.filter(status=status_filter)
        
        if data_inicio:
            try:
                data_inicio_obj = datetime.strptime(data_inicio, '%Y-%m-%d').date()
                data_inicio_dt = timezone.make_aware(datetime.combine(data_inicio_obj, datetime.min.time()))
                ordens = ordens.filter(data_agendada__gte=data_inicio_dt)
            except ValueError:
                pass
        
        if data_fim:
            try:
                data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d').date()
                data_fim_dt = timezone.make_aware(datetime.combine(data_fim_obj, datetime.max.time()))
                ordens = ordens.filter(data_agendada__lte=data_fim_dt)
            except ValueError:
                pass
        
        if responsavel_id:
            ordens = ordens.filter(responsavel_id=responsavel_id)
        
        # Estatísticas - usar queryset base sem filtros aplicados, apenas ativos
        hoje = timezone.now().date()
        hoje_inicio = timezone.make_aware(datetime.combine(hoje, datetime.min.time()))
        hoje_fim = timezone.make_aware(datetime.combine(hoje, datetime.max.time()))
        
        ordens_base = OrdemServico.objects.filter(
            data_agendada__isnull=False
        ).exclude(
            status__in=['CONCLUIDA', 'CANCELADA']
        )
        agendamentos_hoje = ordens_base.filter(
            data_agendada__gte=hoje_inicio,
            data_agendada__lte=hoje_fim
        ).count()
        
        semana_fim = hoje + timedelta(days=7)
        semana_fim_dt = timezone.make_aware(datetime.combine(semana_fim, datetime.max.time()))
        agendamentos_semana = ordens_base.filter(
            data_agendada__gte=hoje_inicio,
            data_agendada__lte=semana_fim_dt
        ).count()
        
        mes_fim = hoje + timedelta(days=30)
        mes_fim_dt = timezone.make_aware(datetime.combine(mes_fim, datetime.max.time()))
        agendamentos_mes = ordens_base.filter(
            data_agendada__gte=hoje_inicio,
            data_agendada__lte=mes_fim_dt
        ).count()
        
        # Buscar responsáveis para filtro
        from django.contrib.auth.models import User
        responsaveis = User.objects.filter(
            is_active=True,
            ordens_servico_responsavel__data_agendada__isnull=False
        ).distinct().order_by('first_name', 'last_name', 'username')
        
        # Garantir que o queryset seja avaliado apenas uma vez
        ordens_list = list(ordens[:100])  # Limitar a 100 resultados para performance
        
        context = {
            'title': 'Agendamento de Serviços',
            'description': 'Agendar e gerenciar serviços',
            'ordens': ordens_list,
            'search_query': search_query,
            'status_filter': status_filter,
            'data_inicio': data_inicio,
            'data_fim': data_fim,
            'responsavel_id': responsavel_id,
            'responsaveis': responsaveis,
            'status_choices': OrdemServico.STATUS_CHOICES,
            'agendamentos_hoje': agendamentos_hoje,
            'agendamentos_semana': agendamentos_semana,
            'agendamentos_mes': agendamentos_mes,
            'hoje': hoje,
        }
        return render(request, 'producao/servicos/agendamento.html', context)
    except Exception as e:
        logger.error(f"Erro ao carregar agendamento: {e}", exc_info=True)
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"Traceback completo: {error_trace}")
        messages.error(request, f'Erro ao carregar página de agendamento: {str(e)}')
        # Retornar para a página principal de produção ao invés de servicos_list
        return redirect('producao:main')


@login_required
def producao_servico_agendamento_detail(request, id):
    """Detalhes do agendamento de serviço"""
    try:
        from django.utils import timezone
        from decimal import Decimal
        
        ordem = get_object_or_404(
            OrdemServico.objects.select_related('cliente', 'responsavel', 'criado_por', 'orcamento_origem').prefetch_related(
                'servicos_orcamento__servico',
                'servicos_orcamento__itens__item',
                'transportes_orcamento__transportadora'
            ),
            id=id,
            data_agendada__isnull=False
        )
        
        # Verificar se é orçamento ou ordem
        is_orcamento = ordem.codigo.startswith('COT')
        
        # Calcular totais
        total_servicos = Decimal('0.00')
        total_itens = Decimal('0.00')
        total_transporte = Decimal('0.00')
        
        for servico_orc in ordem.servicos_orcamento.all():
            total_servicos += servico_orc.valor_total or Decimal('0.00')
            for item in servico_orc.itens.all():
                total_itens += item.valor_total or Decimal('0.00')
        
        for transporte in ordem.transportes_orcamento.all():
            total_transporte += transporte.valor_frete or Decimal('0.00')
        
        subtotal = total_servicos + total_itens + total_transporte
        
        # Calcular IVA
        from .models_base import ConfiguracaoFiscal
        try:
            taxa_iva_decimal = ConfiguracaoFiscal.get_taxa_iva_atual()
            taxa_iva_percentual = taxa_iva_decimal * Decimal('100.00')
            valor_iva = subtotal * taxa_iva_decimal
            valor_final = subtotal + valor_iva
        except:
            taxa_iva_percentual = Decimal('16.00')
            valor_iva = subtotal * Decimal('0.16')
            valor_final = subtotal + valor_iva
        
        context = {
            'ordem': ordem,
            'is_orcamento': is_orcamento,
            'total_servicos': total_servicos,
            'total_itens': total_itens,
            'total_transporte': total_transporte,
            'subtotal': subtotal,
            'valor_iva': valor_iva,
            'taxa_iva': taxa_iva_percentual,
            'valor_final': valor_final,
        }
        return render(request, 'producao/servicos/agendamento_detail.html', context)
    except Exception as e:
        logger.error(f"Erro ao carregar detalhes do agendamento {id}: {e}", exc_info=True)
        messages.error(request, f'Erro ao carregar detalhes do agendamento: {str(e)}')
        return redirect('producao:servicos_agendamento')


@login_required
@require_http_methods(["GET", "POST"])
def producao_servico_agendamento_reagendar(request, id):
    """Reagendar um serviço - alterar apenas data e hora"""
    ordem = get_object_or_404(
        OrdemServico.objects.select_related('cliente', 'responsavel'),
        id=id,
        data_agendada__isnull=False
    )
    
    if request.method == 'POST':
        try:
            from django.utils import timezone
            from datetime import datetime
            
            data_agendada_str = request.POST.get('data_agendada', '')
            hora_agendada = request.POST.get('hora_agendada', '09:00')
            responsavel_id = request.POST.get('responsavel', '')
            
            if not data_agendada_str:
                messages.error(request, 'Data do agendamento é obrigatória.')
                return redirect('producao:servico_agendamento_reagendar', id=id)
            
            try:
                data_agendada = datetime.strptime(f"{data_agendada_str} {hora_agendada}", "%Y-%m-%d %H:%M")
                data_agendada = timezone.make_aware(data_agendada)
            except ValueError:
                messages.error(request, 'Data ou hora inválida.')
                return redirect('producao:servico_agendamento_reagendar', id=id)
            
            ordem.data_agendada = data_agendada
            if responsavel_id:
                ordem.responsavel_id = responsavel_id if responsavel_id else None
            ordem.save()
            
            messages.success(request, f'Agendamento {ordem.codigo} reagendado com sucesso para {data_agendada.strftime("%d/%m/%Y %H:%M")}.')
            return redirect('producao:servico_agendamento_detail', id=id)
        except Exception as e:
            logger.error(f"Erro ao reagendar serviço {id}: {e}", exc_info=True)
            messages.error(request, f'Erro ao reagendar: {str(e)}')
    
    # GET - mostrar formulário de reagendamento
    from django.contrib.auth.models import User
    usuarios = User.objects.filter(is_active=True).order_by('first_name', 'last_name', 'username')
    
    context = {
        'ordem': ordem,
        'usuarios': usuarios,
    }
    return render(request, 'producao/servicos/agendamento_reagendar.html', context)


@login_required
@require_http_methods(["POST"])
def producao_servico_agendamento_cancelar(request, id):
    """Cancelar agendamento - remover data agendada"""
    ordem = get_object_or_404(
        OrdemServico.objects.select_related('cliente'),
        id=id,
        data_agendada__isnull=False
    )
    
    try:
        ordem.data_agendada = None
        if ordem.status == 'AGENDADA':
            ordem.status = 'CANCELADA'
        ordem.save()
        
        messages.success(request, f'Agendamento {ordem.codigo} cancelado com sucesso.')
        return redirect('producao:servicos_agendamento')
    except Exception as e:
        logger.error(f"Erro ao cancelar agendamento {id}: {e}", exc_info=True)
        messages.error(request, f'Erro ao cancelar agendamento: {str(e)}')
        return redirect('producao:servico_agendamento_detail', id=id)


@login_required
def producao_servicos_orcamento(request):
    """Lista de orçamentos de serviço"""
    try:
        # Filtros
        search_query = request.GET.get('q', '').strip()
        status_filter = request.GET.get('status', '')
        servico_id = request.GET.get('servico', '')
        
        # Buscar apenas cotações/orçamentos (código começa com 'COT'), não ordens de serviço
        orcamentos = OrdemServico.objects.select_related('servico', 'cliente', 'responsavel', 'criado_por').prefetch_related(
            'servicos_orcamento__servico', 
            'servicos_orcamento__itens__item', 
            'transportes_orcamento__transportadora'
        ).filter(
            codigo__startswith='COT'
        ).distinct()
        
        # Aplicar filtros
        if search_query:
            orcamentos = orcamentos.filter(
                Q(codigo__icontains=search_query) |
                Q(cliente__nome__icontains=search_query) |
                Q(servico__nome__icontains=search_query) |
                Q(endereco_servico__icontains=search_query)
            )
        
        if status_filter:
            orcamentos = orcamentos.filter(status=status_filter)
        
        if servico_id:
            orcamentos = orcamentos.filter(servico_id=servico_id)
        
        # Ordenação
        orcamentos = orcamentos.order_by('-data_criacao', '-data_agendada')
        
        # Paginação
        paginator = Paginator(orcamentos, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Estatísticas
        total_orcamentos = orcamentos.count()
        orcamentos_agendados = orcamentos.filter(status='AGENDADA').count()
        orcamentos_concluidos = orcamentos.filter(status='CONCLUIDA').count()
        orcamentos_cancelados = orcamentos.filter(status='CANCELADA').count()
        
        # Lista de serviços para filtro
        servicos = Item.objects.filter(tipo='PRODUTO', produto_tipo='SERVICO').order_by('nome')
        
        # Possíveis duplicatas: mesmo cliente + mesma data agendada (várias cotações)
        from collections import defaultdict
        cotacoes_chave = OrdemServico.objects.filter(
            codigo__startswith='COT'
        ).values_list('id', 'cliente_id', 'nome_cliente_pagamento', 'data_agendada')
        grupos = defaultdict(list)
        for pk, cid, nome, data_ag in cotacoes_chave:
            chave = (cid, (nome or '').strip().lower(), data_ag.date() if data_ag else None)
            grupos[chave].append(pk)
        ids_possiveis_duplicados = set()
        for ids in grupos.values():
            if len(ids) > 1:
                ids_possiveis_duplicados.update(ids)
        
        context = {
            'orcamentos': page_obj,
            'search_query': search_query,
            'status_filter': status_filter,
            'servico_id': servico_id,
            'servicos': servicos,
            'total_orcamentos': total_orcamentos,
            'orcamentos_agendados': orcamentos_agendados,
            'orcamentos_concluidos': orcamentos_concluidos,
            'orcamentos_cancelados': orcamentos_cancelados,
            'status_choices': OrdemServico.STATUS_CHOICES,
            'ids_possiveis_duplicados': ids_possiveis_duplicados,
        }
        return render(request, 'producao/servicos/orcamento/list.html', context)
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Erro ao carregar lista de orçamentos: {e}\n{error_details}", exc_info=True)
        messages.error(request, f'Erro ao carregar lista de orçamentos: {str(e)}')
        context = {
            'orcamentos': [],
            'search_query': '',
            'status_filter': '',
            'servico_id': '',
            'servicos': [],
            'total_orcamentos': 0,
            'orcamentos_agendados': 0,
            'orcamentos_concluidos': 0,
            'orcamentos_cancelados': 0,
            'status_choices': OrdemServico.STATUS_CHOICES,
            'ids_possiveis_duplicados': set(),
        }
        return render(request, 'producao/servicos/orcamento/list.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def producao_servico_orcamento_add(request):
    """Criar novo orçamento de serviço. embed=1: render sem cabeçalho (para iframe em Vendas)."""
    from_vendas = request.GET.get('from') == 'vendas' or request.POST.get('from') == 'vendas'
    embed = request.GET.get('embed') == '1' or request.POST.get('embed') == '1'
    add_url = reverse('producao:servico_orcamento_add') + ('?from=vendas' if from_vendas else '')
    if embed:
        add_url += '&embed=1'
    if request.method == 'POST':
        try:
            with transaction.atomic():
                cliente_id = request.POST.get('cliente')
                data_agendada_str = request.POST.get('data_agendada', '')
                hora_agendada = request.POST.get('hora_agendada', '09:00')
                endereco_servico = request.POST.get('endereco_servico', '')
                cidade_servico = request.POST.get('cidade_servico', '')
                equipe = request.POST.get('equipe', '')
                responsavel_id = request.POST.get('responsavel')
                prioridade = request.POST.get('prioridade', 'NORMAL')
                quantidade = Decimal(request.POST.get('quantidade', '1.00'))
                valor_unitario = request.POST.get('valor_unitario')
                desconto_percentual = request.POST.get('desconto_percentual', '0')
                desconto_input = request.POST.get('desconto', '0.00')
                observacoes = request.POST.get('observacoes', '')
                problema_relatado = request.POST.get('problema_relatado', '')
                forma_pagamento = request.POST.get('forma_pagamento', 'PRONTO_PAGAMENTO')
                nome_cliente_pagamento = request.POST.get('nome_cliente_pagamento', '').strip()
                nuit_cliente_pagamento = request.POST.get('nuit_cliente_pagamento', '').strip()
                telefone_cliente_pagamento = request.POST.get('telefone_cliente_pagamento', '').strip()
                cliente_id_hidden = request.POST.get('cliente_id', '').strip()
                local_entrega_sucursal = request.POST.get('local_entrega_sucursal', '').strip()
                # Usar local_entrega_sucursal se endereco_servico estiver vazio
                if not endereco_servico:
                    endereco_servico = local_entrega_sucursal
                
                # Validar que pelo menos um serviço será adicionado (validação será feita depois)
                
                # Validar método de pagamento
                if forma_pagamento == 'PRONTO_PAGAMENTO':
                    if not nome_cliente_pagamento:
                        messages.error(request, 'Nome do cliente é obrigatório para pronto pagamento.')
                        return redirect(add_url)
                    # Para pronto pagamento, cliente_id pode ser vazio (cliente novo)
                    if cliente_id_hidden:
                        try:
                            cliente = ClienteServico.objects.get(id=cliente_id_hidden)
                        except ClienteServico.DoesNotExist:
                            cliente = None
                    else:
                        cliente = None
                else:
                    # Para CREDITO, cliente_id é obrigatório
                    if not cliente_id_hidden:
                        messages.error(request, 'Cliente é obrigatório para venda a crédito.')
                        return redirect(add_url)
                    cliente = get_object_or_404(ClienteServico, id=cliente_id_hidden)
                
                # Para orçamento, data agendada é opcional - usar data atual se não fornecida
                if data_agendada_str:
                    try:
                        data_agendada = datetime.strptime(f"{data_agendada_str} {hora_agendada}", "%Y-%m-%d %H:%M")
                        data_agendada = timezone.make_aware(data_agendada)
                    except:
                        data_agendada = timezone.now()
                else:
                    data_agendada = timezone.now()
                
                # Processar método de pagamento e endereço
                # Preservar endereço personalizado se foi informado
                # Prioridade: endereco_servico > local_entrega_sucursal > cliente.endereco > padrão sucursal
                if forma_pagamento == 'PRONTO_PAGAMENTO':
                    # Pronto pagamento: preservar endereço personalizado se informado
                    if endereco_servico and endereco_servico.strip():
                        endereco_final = endereco_servico
                    elif local_entrega_sucursal and local_entrega_sucursal.strip():
                        endereco_final = local_entrega_sucursal
                    else:
                        # Só usar o padrão da sucursal se não houver nenhum endereço definido
                        from .models_base import Sucursal
                        sucursal_padrao = Sucursal.objects.filter(tipo='SEDE').first()
                        if not sucursal_padrao:
                            sucursal_padrao = Sucursal.objects.first()
                        local_entrega = sucursal_padrao.endereco if sucursal_padrao and sucursal_padrao.endereco else (sucursal_padrao.nome if sucursal_padrao else 'Localização da sucursal')
                        endereco_final = local_entrega
                    cidade_final = cidade_servico or ''
                else:
                    # Por conta: preservar endereço personalizado se informado
                    if endereco_servico and endereco_servico.strip():
                        endereco_final = endereco_servico
                    elif local_entrega_sucursal and local_entrega_sucursal.strip():
                        endereco_final = local_entrega_sucursal
                    elif cliente and cliente.endereco:
                        endereco_final = cliente.endereco
                    else:
                        endereco_final = 'A definir'
                    cidade_final = cidade_servico or (cliente.cidade if cliente else '')
                
                # Processar desconto global
                desconto_global = Decimal(request.POST.get('desconto', '0.00') or '0.00')
                
                # Processar validade da garantia
                validade_garantia = request.POST.get('validade_garantia_dias', '90')
                try:
                    validade_garantia = int(validade_garantia)
                    if validade_garantia < 0:
                        validade_garantia = 90
                except (ValueError, TypeError):
                    validade_garantia = 90
                
                ordem = OrdemServico(
                    servico=None,  # Não usar mais o campo único, usar servicos_orcamento
                    cliente=cliente if cliente else None,
                    data_agendada=data_agendada,
                    endereco_servico=endereco_final,
                    cidade_servico=cidade_final,
                    equipe=equipe,
                    responsavel_id=responsavel_id if responsavel_id else None,
                    prioridade=prioridade,
                    quantidade=Decimal('1.00'),  # Valor padrão, não usado mais
                    valor_unitario=None,  # Não usado mais
                    desconto=desconto_global,  # Desconto global aplicado no final
                    observacoes=observacoes,
                    problema_relatado=problema_relatado,
                    criado_por=request.user,
                    status='AGENDADA',  # Orçamento criado como agendada, pode ser convertido depois
                    forma_pagamento=forma_pagamento,
                    nome_cliente_pagamento=nome_cliente_pagamento if forma_pagamento == 'PRONTO_PAGAMENTO' else None,
                    nuit_cliente_pagamento=nuit_cliente_pagamento if forma_pagamento == 'PRONTO_PAGAMENTO' else None,
                    telefone_cliente_pagamento=telefone_cliente_pagamento if forma_pagamento == 'PRONTO_PAGAMENTO' else None,
                    validade_garantia_dias=validade_garantia,
                )
                # Salvar com is_orcamento=True para gerar código COT
                ordem.save(is_orcamento=True)
                
                # Processar serviços (múltiplos)
                from .models_stock import ServicoOrcamentoServico
                servico_ids = request.POST.getlist('servico_id[]')
                servico_quantidades = request.POST.getlist('servico_quantidade[]')
                servico_valores_unitarios = request.POST.getlist('servico_valor_unitario[]')
                servico_descontos_percentuais = request.POST.getlist('servico_desconto_percentual[]')
                servico_descontos = request.POST.getlist('servico_desconto[]')
                servico_nomes_documento = request.POST.getlist('servico_nome_documento[]')
                if not servico_ids or not any(servico_ids):
                    messages.error(request, 'Pelo menos um serviço é obrigatório.')
                    return redirect(add_url)
                
                for i, servico_id in enumerate(servico_ids):
                    if servico_id and servico_id.strip():
                        try:
                            servico_item = Item.objects.get(id=servico_id, tipo='PRODUTO', produto_tipo='SERVICO')
                            quantidade_servico = Decimal(servico_quantidades[i] if i < len(servico_quantidades) else '1.00')
                            valor_unitario_servico_str = servico_valores_unitarios[i] if i < len(servico_valores_unitarios) else '0.00'
                            valor_unitario_servico = Decimal(valor_unitario_servico_str) if valor_unitario_servico_str else Decimal('0.00')
                            
                            # Se valor_unitario não foi informado ou é zero, usar preço de venda do serviço
                            if not valor_unitario_servico or valor_unitario_servico == 0:
                                valor_unitario_servico = servico_item.preco_venda if servico_item.preco_venda else Decimal('0.00')
                            
                            # Processar descontos individuais do serviço
                            desconto_percentual_servico_str = servico_descontos_percentuais[i] if i < len(servico_descontos_percentuais) else '0.00'
                            desconto_percentual_servico = Decimal(desconto_percentual_servico_str) if desconto_percentual_servico_str else Decimal('0.00')
                            
                            desconto_servico_str = servico_descontos[i] if i < len(servico_descontos) else '0.00'
                            desconto_servico = Decimal(desconto_servico_str) if desconto_servico_str else Decimal('0.00')
                            
                            nome_documento_servico = servico_nomes_documento[i].strip() if i < len(servico_nomes_documento) and servico_nomes_documento[i] else None
                            
                            ServicoOrcamentoServico.objects.create(
                                ordem_servico=ordem,
                                servico=servico_item,
                                quantidade=quantidade_servico,
                                valor_unitario=valor_unitario_servico,
                                desconto_percentual=desconto_percentual_servico,
                                desconto=desconto_servico,
                                nome_documento=nome_documento_servico
                            )
                        except (Item.DoesNotExist, ValueError, IndexError) as e:
                            logger.warning(f"Erro ao adicionar serviço ao orçamento: {e}")
                            continue
                
                # Processar produtos e materiais agrupados por serviço
                from .models_stock import ItemOrcamentoServico
                servico_index = 0
                for servico_orcamento in ordem.servicos_orcamento.all():
                    # Buscar itens deste serviço específico
                    item_ids = request.POST.getlist(f'item_servico_{servico_index}_id[]')
                    item_quantidades = request.POST.getlist(f'item_servico_{servico_index}_quantidade[]')
                    item_valores_unitarios = request.POST.getlist(f'item_servico_{servico_index}_valor_unitario[]')
                    item_descontos_percentuais = request.POST.getlist(f'item_servico_{servico_index}_desconto_percentual[]')
                    item_descontos = request.POST.getlist(f'item_servico_{servico_index}_desconto[]')
                    
                    for i, item_id in enumerate(item_ids):
                        if item_id and item_id.strip():
                            try:
                                item = Item.objects.get(id=item_id, tipo__in=['PRODUTO', 'MATERIAL'])
                                quantidade_item = Decimal(item_quantidades[i] if i < len(item_quantidades) else '1.00')
                                valor_unitario_item_str = item_valores_unitarios[i] if i < len(item_valores_unitarios) else '0.00'
                                valor_unitario_item = Decimal(valor_unitario_item_str) if valor_unitario_item_str else Decimal('0.00')
                                
                                # Se valor_unitario não foi informado ou é zero, usar preço de venda do item
                                if not valor_unitario_item or valor_unitario_item == 0:
                                    valor_unitario_item = item.preco_venda if item.preco_venda else Decimal('0.00')
                                
                                # Processar descontos individuais
                                desconto_percentual_item_str = item_descontos_percentuais[i] if i < len(item_descontos_percentuais) else '0.00'
                                desconto_percentual_item = Decimal(desconto_percentual_item_str) if desconto_percentual_item_str else Decimal('0.00')
                                
                                desconto_item_str = item_descontos[i] if i < len(item_descontos) else '0.00'
                                desconto_item = Decimal(desconto_item_str) if desconto_item_str else Decimal('0.00')
                                
                                ItemOrcamentoServico.objects.create(
                                    servico_orcamento=servico_orcamento,
                                    ordem_servico=ordem,  # Manter para compatibilidade
                                    item=item,
                                    quantidade=quantidade_item,
                                    valor_unitario=valor_unitario_item,
                                    desconto_percentual=desconto_percentual_item,
                                    desconto=desconto_item
                                )
                            except (Item.DoesNotExist, ValueError, IndexError) as e:
                                logger.warning(f"Erro ao adicionar item ao serviço {servico_orcamento.id}: {e}")
                                continue
                    servico_index += 1
                
                # Processar transportes
                transporte_tipos = request.POST.getlist('transporte_tipo[]')
                transporte_ids = request.POST.getlist('transporte_id[]')
                transporte_valores = request.POST.getlist('transporte_valor[]')
                
                for i, transporte_id in enumerate(transporte_ids):
                    if transporte_id and transporte_id.strip():
                        try:
                            transportadora = Transportadora.objects.get(id=transporte_id)
                            tipo_transporte = transporte_tipos[i] if i < len(transporte_tipos) else 'EXTERNO'
                            valor_frete = Decimal(transporte_valores[i] if i < len(transporte_valores) else '0.00')
                            
                            TransporteOrcamentoServico.objects.create(
                                ordem_servico=ordem,
                                transportadora=transportadora,
                                tipo_transporte=tipo_transporte,
                                valor_frete=valor_frete
                            )
                        except (Transportadora.DoesNotExist, ValueError, IndexError) as e:
                            logger.warning(f"Erro ao adicionar transporte ao orçamento: {e}")
                            continue
                
                # Recalcular valor_total da ordem após salvar todos os itens
                ordem.refresh_from_db()
                valor_servicos = sum(servico.valor_total for servico in ordem.servicos_orcamento.all())
                valor_itens = sum(
                    item.valor_total 
                    for servico in ordem.servicos_orcamento.all() 
                    for item in servico.itens.all()
                )
                valor_transporte = sum(
                    transporte.valor_frete or Decimal('0.00') 
                    for transporte in ordem.transportes_orcamento.all()
                )
                subtotal = valor_servicos + valor_itens + valor_transporte
                desconto = ordem.desconto or Decimal('0.00')
                novo_valor_total = max(subtotal - desconto, Decimal('0.00'))
                ordem.valor_total = novo_valor_total
                ordem.save(update_fields=['valor_total'])
                
                messages.success(request, f'Orçamento {ordem.codigo} criado com sucesso!')
                if from_vendas and embed:
                    from django.http import HttpResponse
                    from django.urls import reverse as rev
                    url_destino = rev('vendas:orcamento_detail', args=[ordem.id])
                    html = f'<!DOCTYPE html><html><head><meta charset="utf-8"></head><body><script>window.top.location.href = "{url_destino}";</script><p>Orçamento criado. A redirecionar...</p></body></html>'
                    return HttpResponse(html)
                if from_vendas:
                    return redirect('vendas:orcamento_detail', id=ordem.id)
                return redirect('producao:servico_orcamento_confirmar', id=ordem.id)
        except Exception as e:
            logger.error(f"Erro ao criar orçamento: {e}", exc_info=True)
            messages.error(request, f'Erro ao criar orçamento: {str(e)}')
    
    # Incluir todos os serviços (ATIVO e outros) para poder adicionar a cotações
    servicos = Item.objects.filter(tipo='PRODUTO', produto_tipo='SERVICO').order_by('nome')
    clientes = ClienteServico.objects.filter(ativo=True).order_by('nome')
    usuarios = User.objects.filter(is_active=True).order_by('username')
    produtos_materiais = Item.objects.filter(tipo__in=['PRODUTO', 'MATERIAL'], status='ATIVO').exclude(produto_tipo='SERVICO').order_by('nome')
    transportadoras = Transportadora.objects.filter(status='ATIVA').order_by('nome')
    
    # Buscar taxa de IVA
    from .models_base import ConfiguracaoFiscal
    taxa_iva_decimal = ConfiguracaoFiscal.get_taxa_iva_atual()
    taxa_iva_percentual = taxa_iva_decimal * Decimal('100.00')
    
    context = {
        'servicos': servicos,
        'clientes': clientes,
        'usuarios': usuarios,
        'produtos_materiais': produtos_materiais,
        'transportadoras': transportadoras,
        'prioridade_choices': OrdemServico.PRIORIDADE_CHOICES,
        'is_orcamento': True,  # Flag para identificar que é orçamento
        'taxa_iva': taxa_iva_percentual,  # Taxa de IVA em percentual
        'from_vendas': from_vendas,
        'embed': embed,
    }
    return render(request, 'producao/servicos/orcamento/form.html', context)


@require_http_methods(["GET"])
def producao_servico_debug_js_log(request):
    """Append one NDJSON line to debug log from JS (for debugging)."""
    try:
        msg = request.GET.get('message', '')
        loc = request.GET.get('location', '')
        hyp = request.GET.get('hypothesisId', '')
        data_str = request.GET.get('data', '{}')
        try:
            data = _json.loads(data_str)
        except Exception:
            data = {}
        log_path = os.path.join(settings.BASE_DIR, 'debug-js.log')
        entry = {'hypothesisId': hyp, 'location': loc, 'message': msg, 'data': data, 'timestamp': int(timezone.now().timestamp() * 1000)}
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(_json.dumps(entry) + '\n')
    except Exception:
        pass
    return HttpResponse(status=204)


@login_required
@require_http_methods(["GET", "POST"])
def producao_servico_ordem_add(request):
    """Criar nova ordem de serviço"""
    if request.method == 'POST':
        try:
            with transaction.atomic():
                cliente_id = request.POST.get('cliente')
                data_agendada_str = request.POST.get('data_agendada')
                hora_agendada = request.POST.get('hora_agendada', '09:00')
                endereco_servico = request.POST.get('endereco_servico')
                cidade_servico = request.POST.get('cidade_servico', '')
                equipe = request.POST.get('equipe', '')
                responsavel_id = request.POST.get('responsavel')
                prioridade = request.POST.get('prioridade', 'NORMAL')
                servico_id = request.POST.get('servico')
                quantidade = Decimal(request.POST.get('quantidade', '1.00'))
                valor_unitario = request.POST.get('valor_unitario')
                desconto_percentual = request.POST.get('desconto_percentual', '0')
                desconto_input = request.POST.get('desconto', '0.00')
                observacoes = request.POST.get('observacoes', '')
                problema_relatado = request.POST.get('problema_relatado', '')
                
                if not all([servico_id, cliente_id, data_agendada_str, endereco_servico]):
                    messages.error(request, 'Todos os campos obrigatórios devem ser preenchidos.')
                    return redirect('producao:servico_ordem_add')
                
                servico = get_object_or_404(Item, id=servico_id, tipo='PRODUTO', produto_tipo='SERVICO')
                cliente = get_object_or_404(ClienteServico, id=cliente_id)
                
                try:
                    data_agendada = datetime.strptime(f"{data_agendada_str} {hora_agendada}", "%Y-%m-%d %H:%M")
                    data_agendada = timezone.make_aware(data_agendada)
                except:
                    messages.error(request, 'Data ou hora inválida.')
                    return redirect('producao:servico_ordem_add')
                
                # Usar preço do serviço se valor_unitario não for fornecido
                if valor_unitario:
                    valor_unitario_decimal = Decimal(valor_unitario)
                else:
                    valor_unitario_decimal = servico.preco_venda if servico.preco_venda else None
                
                # Calcular desconto percentual (sempre percentual agora, pode ser 0% para sem desconto)
                desconto_percentual_decimal = Decimal(desconto_percentual)
                if desconto_percentual_decimal > 0 and valor_unitario_decimal:
                    valor_bruto = quantidade * valor_unitario_decimal
                    desconto = (valor_bruto * desconto_percentual_decimal / 100).quantize(Decimal('0.01'), rounding=ROUND_UP)
                else:
                    desconto = Decimal('0.00')
                
                ordem = OrdemServico.objects.create(
                    servico=servico,
                    departamento_origem='PRODUCAO',
                    cliente=cliente,
                    data_agendada=data_agendada,
                    endereco_servico=endereco_servico,
                    cidade_servico=cidade_servico,
                    equipe=equipe,
                    responsavel_id=responsavel_id if responsavel_id else None,
                    prioridade=prioridade,
                    quantidade=quantidade,
                    valor_unitario=valor_unitario_decimal,
                    desconto=desconto,
                    observacoes=observacoes,
                    problema_relatado=problema_relatado,
                    criado_por=request.user,
                    status='AGENDADA'
                )
                
                messages.success(request, f'Ordem de serviço {ordem.codigo} criada com sucesso!')
                return redirect('producao:servico_ordem_detail', id=ordem.id)
        except Exception as e:
            logger.error(f"Erro ao criar ordem de serviço: {e}", exc_info=True)
            messages.error(request, f'Erro ao criar ordem de serviço: {str(e)}')
    
    # Incluir todos os serviços (ATIVO e outros) para poder adicionar a cotações
    servicos = Item.objects.filter(tipo='PRODUTO', produto_tipo='SERVICO').order_by('nome')
    clientes = ClienteServico.objects.filter(ativo=True).order_by('nome')
    usuarios = User.objects.filter(is_active=True).order_by('username')
    
    context = {
        'servicos': servicos,
        'clientes': clientes,
        'usuarios': usuarios,
        'prioridade_choices': OrdemServico.PRIORIDADE_CHOICES,
    }
    return render(request, 'producao/servicos/ordens/form.html', context)


@login_required
def producao_servico_orcamento_confirmar(request, id):
    """Página de confirmação após criar orçamento"""
    try:
        from .models_stock import ServicoOrcamentoServico, ItemOrcamentoServico, TransporteOrcamentoServico
        from .models_base import ConfiguracaoFiscal
        
        orcamento = get_object_or_404(
            OrdemServico.objects.select_related('cliente', 'responsavel', 'criado_por').prefetch_related(
                'servicos_orcamento__servico',
                'servicos_orcamento__itens__item',
                'transportes_orcamento__transportadora'
            ), 
            id=id
        )
        
        # Forçar recarregamento do objeto para garantir dados atualizados após edição
        orcamento.refresh_from_db()
        
        # Calcular totais
        total_servicos = sum(s.valor_total for s in orcamento.servicos_orcamento.all())
        total_itens = sum(item.valor_total for servico_orc in orcamento.servicos_orcamento.all() for item in servico_orc.itens.all())
        total_transporte = sum(t.valor_frete for t in orcamento.transportes_orcamento.all())
        
        # Calcular valores brutos para calcular descontos
        total_servicos_bruto = sum((s.quantidade or Decimal('0.00')) * (s.valor_unitario or Decimal('0.00')) for s in orcamento.servicos_orcamento.all())
        total_itens_bruto = sum((item.quantidade or Decimal('0.00')) * (item.valor_unitario or Decimal('0.00')) for servico_orc in orcamento.servicos_orcamento.all() for item in servico_orc.itens.all())
        total_descontos = (total_servicos_bruto + total_itens_bruto) - (total_servicos + total_itens)
        
        subtotal = total_servicos + total_itens + total_transporte
        valor_apos_desconto = subtotal - (orcamento.desconto or Decimal('0.00'))
        
        # Calcular IVA
        taxa_iva_decimal = ConfiguracaoFiscal.get_taxa_iva_atual()
        taxa_iva_percentual = taxa_iva_decimal * Decimal('100.00')
        valor_iva = valor_apos_desconto * taxa_iva_decimal
        valor_final = valor_apos_desconto + valor_iva
        
        context = {
            'ordem': orcamento, 
            'is_orcamento': True,
            'servicos_orcamento': orcamento.servicos_orcamento.all(),
            'transportes': orcamento.transportes_orcamento.all(),
            'total_servicos': total_servicos,
            'total_itens': total_itens,
            'total_transporte': total_transporte,
            'total_descontos': total_descontos,
            'subtotal': subtotal,
            'valor_apos_desconto': valor_apos_desconto,
            'valor_iva': valor_iva,
            'taxa_iva': taxa_iva_percentual,
            'valor_final': valor_final,
        }
        return render(request, 'producao/servicos/orcamento/confirmar.html', context)
    except Exception as e:
        logger.error(f"Erro ao carregar página de confirmação do orçamento {id}: {e}")
        messages.error(request, 'Erro ao carregar página de confirmação do orçamento.')
        return redirect('producao:servicos_orcamento')


@login_required
@require_http_methods(["POST"])
def producao_servico_orcamento_confirmar_acao(request, id):
    """Confirma a cotação criando uma ordem de serviço"""
    try:
        from django.db import transaction
        from .models_stock import ServicoOrcamentoServico, ItemOrcamentoServico, TransporteOrcamentoServico
        
        orcamento = get_object_or_404(
            OrdemServico.objects.select_related('cliente', 'responsavel', 'criado_por').prefetch_related(
                'servicos_orcamento__servico',
                'servicos_orcamento__itens__item',
                'transportes_orcamento__transportadora',
                'parcelas_pagamento__servicos',
            ),
            id=id
        )
        
        # Verificar se já existe uma ordem de serviço criada a partir desta cotação usando o campo orcamento_origem
        ordem_existente = OrdemServico.objects.filter(
            codigo__startswith='OS',
            orcamento_origem=orcamento
        ).first()
        
        if ordem_existente:
            messages.warning(request, f'Já existe uma ordem de serviço criada a partir desta cotação: {ordem_existente.codigo}')
            return redirect('producao:servico_ordem_detail', id=ordem_existente.id)
        
        # Verificar método legado para compatibilidade (só se tiver cliente)
        ordem_existente_legado = None
        if orcamento.cliente:
            ordem_existente_legado = OrdemServico.objects.filter(
                codigo__startswith='OS',
                cliente=orcamento.cliente,
                data_agendada=orcamento.data_agendada,
                endereco_servico=orcamento.endereco_servico
            ).exclude(id=orcamento.id).first()
        
        if ordem_existente_legado:
            # Atualizar o campo orcamento_origem se não estiver preenchido
            if not ordem_existente_legado.orcamento_origem:
                ordem_existente_legado.orcamento_origem = orcamento
                ordem_existente_legado.save()
            messages.warning(request, f'Já existe uma ordem de serviço criada a partir desta cotação: {ordem_existente_legado.codigo}')
            return redirect('producao:servico_ordem_detail', id=ordem_existente_legado.id)
        
        with transaction.atomic():
            # Criar nova ordem de serviço baseada na cotação
            # Não passar is_orcamento=True para gerar código OS-XXX
            ordem_servico = OrdemServico(
                orcamento_origem=orcamento,  # Referência à cotação original
                departamento_origem='PRODUCAO',
                servico=None,  # Múltiplos serviços via servicos_orcamento
                cliente=orcamento.cliente,
                data_agendada=orcamento.data_agendada,
                endereco_servico=orcamento.endereco_servico,
                cidade_servico=orcamento.cidade_servico,
                equipe=orcamento.equipe,
                responsavel=orcamento.responsavel,
                prioridade=orcamento.prioridade,
                quantidade=Decimal('1.00'),  # Valor padrão
                valor_unitario=None,
                desconto=orcamento.desconto,
                observacoes=orcamento.observacoes,
                problema_relatado=orcamento.problema_relatado,
                criado_por=request.user,
                status='EM_ANDAMENTO',  # Ordem de serviço inicia em andamento
                forma_pagamento=orcamento.forma_pagamento,
                nome_cliente_pagamento=orcamento.nome_cliente_pagamento,
                nuit_cliente_pagamento=orcamento.nuit_cliente_pagamento,
                telefone_cliente_pagamento=orcamento.telefone_cliente_pagamento,
            )
            # Salvar sem is_orcamento para gerar código OS-XXX
            ordem_servico.save(is_orcamento=False)
            
            # Copiar serviços do orçamento para a ordem de serviço
            for servico_orc in orcamento.servicos_orcamento.all():
                ServicoOrcamentoServico.objects.create(
                    ordem_servico=ordem_servico,
                    servico=servico_orc.servico,
                    quantidade=servico_orc.quantidade,
                    valor_unitario=servico_orc.valor_unitario,
                    desconto_percentual=servico_orc.desconto_percentual,
                    desconto=servico_orc.desconto,
                    observacoes=servico_orc.observacoes,
                    nome_documento=servico_orc.nome_documento,
                )
            
            # Copiar itens (produtos/materiais) dos serviços
            for servico_orc in orcamento.servicos_orcamento.all():
                servico_ordem = ordem_servico.servicos_orcamento.filter(
                    servico=servico_orc.servico
                ).first()
                
                if servico_ordem:
                    for item_orc in servico_orc.itens.all():
                        ItemOrcamentoServico.objects.create(
                            servico_orcamento=servico_ordem,
                            ordem_servico=ordem_servico,
                            item=item_orc.item,
                            quantidade=item_orc.quantidade,
                            valor_unitario=item_orc.valor_unitario,
                            desconto_percentual=getattr(item_orc, 'desconto_percentual', Decimal('0.00')),
                            desconto=item_orc.desconto,
                        )
            
            # Copiar transportes
            for transporte_orc in orcamento.transportes_orcamento.all():
                TransporteOrcamentoServico.objects.create(
                    ordem_servico=ordem_servico,
                    transportadora=transporte_orc.transportadora,
                    tipo_transporte=transporte_orc.tipo_transporte,
                    valor_frete=transporte_orc.valor_frete,
                )
            
            # Atualizar status da cotação para indicar que foi convertida
            orcamento.status = 'CONCLUIDA'  # Marcar cotação como concluída/convertida
            orcamento.save()
            from .parcelas_vendas_utils import _copiar_parcelas_para_ordem, processar_parcelas_vendas_receber
            _copiar_parcelas_para_ordem(orcamento, ordem_servico)
            processar_parcelas_vendas_receber(ordem_servico, request.user, 'ASSINATURA')
        
        messages.success(request, f'Cotação {orcamento.codigo} confirmada! Ordem de serviço {ordem_servico.codigo} criada. Defina o plano de execução (etapas) para continuar.')
        return redirect('producao:servico_ordem_plano_execucao', id=ordem_servico.id)
    except Exception as e:
        logger.error(f"Erro ao confirmar cotação {id}: {e}", exc_info=True)
        messages.error(request, f'Erro ao confirmar cotação: {str(e)}')
        return redirect('producao:servico_orcamento_confirmar', id=id)


@login_required
def producao_servico_orcamento_detail(request, id):
    """Detalhes do orçamento"""
    try:
        from .models_stock import ServicoOrcamentoServico, ItemOrcamentoServico, TransporteOrcamentoServico
        from .models_base import ConfiguracaoFiscal
        from decimal import Decimal, InvalidOperation
        
        orcamento = get_object_or_404(
            OrdemServico.objects.select_related('cliente', 'responsavel', 'criado_por').prefetch_related(
                'servicos_orcamento__servico',
                'servicos_orcamento__itens__item',
                'transportes_orcamento__transportadora'
            ), 
            id=id
        )
        
        # Forçar recarregamento do objeto para garantir dados atualizados após edição
        orcamento.refresh_from_db()
        
        # Calcular totais usando valores COM descontos aplicados (para o resumo financeiro)
        # Os descontos dos serviços e itens são aplicados individualmente
        total_servicos = Decimal('0.00')
        total_servicos_bruto = Decimal('0.00')  # Para calcular o total de descontos
        try:
            servicos_list = list(orcamento.servicos_orcamento.all())
            if servicos_list:
                for s in servicos_list:
                    try:
                        # Calcular valor bruto
                        valor_bruto_servico = (s.quantidade or Decimal('0.00')) * (s.valor_unitario or Decimal('0.00'))
                        total_servicos_bruto += valor_bruto_servico
                        
                        # Usar valor_total (que já aplica descontos) para o resumo financeiro
                        valor_total_servico = s.valor_total
                        if isinstance(valor_total_servico, Decimal):
                            total_servicos += valor_total_servico
                        else:
                            total_servicos += Decimal(str(valor_total_servico))
                    except (ValueError, InvalidOperation, AttributeError, TypeError) as e:
                        logger.warning(f"Erro ao calcular valor do serviço {s.id}: {e}")
                        continue
        except Exception as e:
            logger.warning(f"Erro ao calcular total_servicos: {e}")
            total_servicos = Decimal('0.00')
        
        # Calcular total de itens (produtos e materiais) usando valores COM descontos aplicados
        total_itens = Decimal('0.00')
        total_itens_bruto = Decimal('0.00')  # Para calcular o total de descontos
        try:
            for servico_orc in orcamento.servicos_orcamento.all():
                for item in servico_orc.itens.all():
                    try:
                        # Calcular valor bruto
                        valor_bruto_item = (item.quantidade or Decimal('0.00')) * (item.valor_unitario or Decimal('0.00'))
                        total_itens_bruto += valor_bruto_item
                        
                        # Usar valor_total (que já aplica descontos) para o resumo financeiro
                        valor_total_item = item.valor_total
                        if isinstance(valor_total_item, Decimal):
                            total_itens += valor_total_item
                        else:
                            total_itens += Decimal(str(valor_total_item))
                    except (ValueError, InvalidOperation, AttributeError, TypeError) as e:
                        logger.warning(f"Erro ao calcular valor do item {item.id}: {e}")
                        continue
        except Exception as e:
            logger.warning(f"Erro ao calcular total_itens: {e}")
            total_itens = Decimal('0.00')
        
        # Calcular total de descontos aplicados
        total_descontos = (total_servicos_bruto + total_itens_bruto) - (total_servicos + total_itens)
        
        try:
            total_transporte = sum(Decimal(str(t.valor_frete)) if t.valor_frete else Decimal('0.00') for t in orcamento.transportes_orcamento.all())
        except (ValueError, InvalidOperation, TypeError) as e:
            logger.warning(f"Erro ao calcular total_transporte: {e}")
            total_transporte = Decimal('0.00')
        
        # Garantir que os valores sejam Decimal antes de somar
        if not isinstance(total_servicos, Decimal):
            total_servicos = Decimal(str(total_servicos)) if total_servicos else Decimal('0.00')
        if not isinstance(total_itens, Decimal):
            total_itens = Decimal(str(total_itens)) if total_itens else Decimal('0.00')
        if not isinstance(total_transporte, Decimal):
            total_transporte = Decimal(str(total_transporte)) if total_transporte else Decimal('0.00')
        
        # Calcular subtotal
        subtotal = total_servicos + total_itens + total_transporte
        
        # Log para debug
        logger.info(f"Totais calculados - Servicos: {total_servicos}, Itens: {total_itens}, Transporte: {total_transporte}, Subtotal: {subtotal}")
        
        try:
            desconto_global = Decimal(str(orcamento.desconto)) if orcamento.desconto else Decimal('0.00')
        except (ValueError, InvalidOperation, TypeError) as e:
            logger.warning(f"Erro ao calcular desconto_global: {e}")
            desconto_global = Decimal('0.00')
        
        try:
            valor_apos_desconto = subtotal - desconto_global
            if valor_apos_desconto < 0:
                valor_apos_desconto = Decimal('0.00')
        except (ValueError, InvalidOperation) as e:
            logger.warning(f"Erro ao calcular valor_apos_desconto: {e}")
            valor_apos_desconto = subtotal
        
        # Calcular IVA
        try:
            taxa_iva_decimal = ConfiguracaoFiscal.get_taxa_iva_atual()
            if not isinstance(taxa_iva_decimal, Decimal):
                taxa_iva_decimal = Decimal(str(taxa_iva_decimal))
        except Exception as e:
            logger.warning(f"Erro ao buscar taxa IVA: {e}")
            taxa_iva_decimal = Decimal('0.16')  # Valor padrão 16%
        
        try:
            taxa_iva_percentual = taxa_iva_decimal * Decimal('100.00')
            valor_iva = valor_apos_desconto * taxa_iva_decimal
            valor_final = valor_apos_desconto + valor_iva
            
            # Log para debug
            logger.info(f"IVA calculado - Taxa: {taxa_iva_percentual}%, Valor IVA: {valor_iva}, Valor Final: {valor_final}")
        except (ValueError, InvalidOperation) as e:
            logger.warning(f"Erro ao calcular IVA e valor final: {e}")
            taxa_iva_percentual = Decimal('16.00')
            valor_iva = Decimal('0.00')
            valor_final = valor_apos_desconto
        
        # Garantir que os serviços sejam recarregados do banco para evitar problemas de cache
        servicos_orcamento_list = list(orcamento.servicos_orcamento.all())
        # Calcular valor_total para cada serviço e adicionar como atributo para o template
        servicos_com_totais = []
        for servico_orc in servicos_orcamento_list:
            # Recarregar do banco para garantir que os valores estejam atualizados
            servico_orc.refresh_from_db()
            # Calcular valor total manualmente para garantir que funcione no template
            try:
                qtd = Decimal(str(servico_orc.quantidade)) if servico_orc.quantidade is not None else Decimal('0.00')
                valor_unit = Decimal(str(servico_orc.valor_unitario)) if servico_orc.valor_unitario is not None else Decimal('0.00')
                desconto = Decimal(str(servico_orc.desconto)) if servico_orc.desconto is not None else Decimal('0.00')
                desconto_percentual = Decimal(str(servico_orc.desconto_percentual)) if servico_orc.desconto_percentual is not None else Decimal('0.00')
                
                # Calcular valor bruto (quantidade × valor unitário)
                valor_bruto = qtd * valor_unit
                
                # Aplicar desconto: percentual OU valor em MT (mutuamente exclusivo)
                if desconto_percentual > 0:
                    # Aplicar apenas desconto percentual
                    valor_final_servico = valor_bruto * (Decimal('1') - desconto_percentual / Decimal('100'))
                elif desconto > 0:
                    # Aplicar apenas desconto em MT
                    valor_final_servico = valor_bruto - desconto
                else:
                    # Sem desconto
                    valor_final_servico = valor_bruto
                
                valor_final_servico = max(valor_final_servico, Decimal('0.00'))
                
                # Adicionar como atributos para o template
                # valor_total_bruto: valor sem descontos (para exibição no "Total do Serviço")
                servico_orc.valor_total_bruto = valor_bruto
                # valor_total_calculado: valor com descontos aplicados (para cálculos finais)
                servico_orc.valor_total_calculado = valor_final_servico
                
                # Calcular valor bruto para cada item (produto/material) do serviço
                for item in servico_orc.itens.all():
                    try:
                        qtd_item = Decimal(str(item.quantidade)) if item.quantidade is not None else Decimal('0.00')
                        valor_unit_item = Decimal(str(item.valor_unitario)) if item.valor_unitario is not None else Decimal('0.00')
                        item.valor_total_bruto = qtd_item * valor_unit_item
                    except (ValueError, TypeError, AttributeError, InvalidOperation) as e:
                        logger.warning(f"Erro ao calcular valor_total_bruto para item {item.id}: {e}")
                        try:
                            qtd_item = Decimal(str(item.quantidade)) if item.quantidade is not None else Decimal('0.00')
                            valor_unit_item = Decimal(str(item.valor_unitario)) if item.valor_unitario is not None else Decimal('0.00')
                            item.valor_total_bruto = qtd_item * valor_unit_item
                        except:
                            item.valor_total_bruto = Decimal('0.00')
            except (ValueError, TypeError, AttributeError, InvalidOperation) as e:
                logger.warning(f"Erro ao calcular valor_total para serviço {servico_orc.id}: {e}")
                # Em caso de erro, tentar calcular pelo menos o valor bruto
                try:
                    qtd = Decimal(str(servico_orc.quantidade)) if servico_orc.quantidade is not None else Decimal('0.00')
                    valor_unit = Decimal(str(servico_orc.valor_unitario)) if servico_orc.valor_unitario is not None else Decimal('0.00')
                    servico_orc.valor_total_bruto = qtd * valor_unit
                except:
                    servico_orc.valor_total_bruto = Decimal('0.00')
                servico_orc.valor_total_calculado = Decimal('0.00')
            
            servicos_com_totais.append(servico_orc)
        
        # Verificar se existe uma ordem de serviço relacionada (para mostrar botão de fatura)
        ordem_relacionada = None
        try:
            ordem_relacionada = OrdemServico.objects.filter(
                codigo__startswith='OS',
                orcamento_origem=orcamento
            ).first()
        except:
            pass
        
        # Para orçamentos, sempre permitir imprimir e gerar contrato, mesmo se houver ordem relacionada com fatura
        # Apenas a edição deve ser bloqueada se houver ordem relacionada
        pode_editar = True
        if ordem_relacionada:
            pode_editar = False

        tem_itens_servicos = any(
            any(getattr(it, 'item', None) for it in s.itens.all())
            for s in servicos_com_totais
        )
        
        context = {
            'ordem': orcamento, 
            'is_orcamento': True,
            'servicos_orcamento': servicos_com_totais,
            'tem_itens_servicos': tem_itens_servicos,
            'transportes': list(orcamento.transportes_orcamento.all()),
            'total_servicos': total_servicos,
            'total_itens': total_itens,
            'total_transporte': total_transporte,
            'total_descontos': total_descontos,
            'subtotal': subtotal,
            'valor_apos_desconto': valor_apos_desconto,
            'taxa_iva': taxa_iva_percentual,
            'valor_iva': valor_iva,
            'valor_final': valor_final,
            'ordem_relacionada': ordem_relacionada,
            'pode_editar': pode_editar,
        }
        
        # Log para debug
        logger.info(f"Orçamento {orcamento.codigo} - Total serviços calculado: {total_servicos}")
        for servico_orc in servicos_com_totais:
            logger.info(f"  Serviço {servico_orc.id}: qtd={servico_orc.quantidade}, valor_unit={servico_orc.valor_unitario}, valor_total={servico_orc.valor_total}, valor_total_calculado={getattr(servico_orc, 'valor_total_calculado', 'N/A')}")
        return render(request, 'producao/servicos/ordens/detail.html', context)
    except Exception as e:
        logger.error(f"Erro ao exibir detalhes do orçamento {id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        messages.error(request, 'Erro ao carregar detalhes do orçamento.')
        return redirect('producao:servicos_orcamento')


@login_required
def producao_servico_orcamento_imprimir(request, id):
    """Página de impressão da cotação"""
    logger.info(f"Iniciando carregamento da página de impressão da cotação {id}")
    try:
        logger.info("Importando modelos necessários...")
        from .models_stock import ServicoOrcamentoServico, ItemOrcamentoServico, TransporteOrcamentoServico
        from .models_base import DadosEmpresa, ConfiguracaoFiscal
        from django.conf import settings
        logger.info("Modelos importados com sucesso")
        
        orcamento = get_object_or_404(
            OrdemServico.objects.select_related(
                'cliente', 'responsavel', 'criado_por', 
                'criado_por__perfil', 'criado_por__perfil__funcionario'
            ).prefetch_related(
                'servicos_orcamento__servico',
                'servicos_orcamento__itens__item',
                'transportes_orcamento__transportadora'
            ), 
            id=id
        )
        
        # Calcular valores brutos e descontos para cada serviço (para exibição na impressão)
        servicos_com_totais = []
        for servico_orc in orcamento.servicos_orcamento.all():
            try:
                qtd = Decimal(str(servico_orc.quantidade)) if servico_orc.quantidade is not None else Decimal('0.00')
                valor_unit = Decimal(str(servico_orc.valor_unitario)) if servico_orc.valor_unitario is not None else Decimal('0.00')
                desconto = Decimal(str(servico_orc.desconto)) if servico_orc.desconto is not None else Decimal('0.00')
                desconto_percentual = Decimal(str(servico_orc.desconto_percentual)) if servico_orc.desconto_percentual is not None else Decimal('0.00')
                
                # Calcular total BRUTO de itens (materiais e produtos) para este serviço
                # IMPORTANTE: Usar valor bruto (sem desconto) para não duplicar desconto
                total_itens_servico_bruto = Decimal('0.00')
                total_itens_servico_com_desconto = Decimal('0.00')
                for item in servico_orc.itens.all():
                    try:
                        # Valor bruto do item (sem desconto)
                        qtd_item = Decimal(str(item.quantidade)) if item.quantidade is not None else Decimal('0.00')
                        valor_unit_item = Decimal(str(item.valor_unitario)) if item.valor_unitario is not None else Decimal('0.00')
                        valor_bruto_item = qtd_item * valor_unit_item
                        total_itens_servico_bruto += valor_bruto_item
                        
                        # Valor total do item (com desconto aplicado) - para usar no cálculo final
                        total_itens_servico_com_desconto += item.valor_total
                    except (ValueError, TypeError, AttributeError, InvalidOperation):
                        continue
                
                # Valor bruto do serviço (sem desconto)
                valor_bruto_servico = qtd * valor_unit
                
                # Valor bruto total (serviço + itens brutos) - para exibição
                valor_bruto_com_itens = valor_bruto_servico + total_itens_servico_bruto
                servico_orc.valor_total_bruto = valor_bruto_com_itens
                
                # IMPORTANTE: O desconto do serviço é aplicado APENAS sobre o valor do serviço, NÃO sobre os itens
                # Calcular valor do serviço com desconto aplicado
                valor_servico_com_desconto = valor_bruto_servico
                if desconto_percentual > 0:
                    servico_orc.desconto_aplicado = valor_bruto_servico * (desconto_percentual / Decimal('100'))
                    servico_orc.desconto_tipo = f"{desconto_percentual}%"
                    valor_servico_com_desconto = valor_bruto_servico - servico_orc.desconto_aplicado
                elif desconto > 0:
                    servico_orc.desconto_aplicado = desconto
                    servico_orc.desconto_tipo = f"{desconto:.2f} MT"
                    valor_servico_com_desconto = valor_bruto_servico - desconto
                    if valor_servico_com_desconto < 0:
                        valor_servico_com_desconto = Decimal('0.00')
                else:
                    servico_orc.desconto_aplicado = Decimal('0.00')
                    servico_orc.desconto_tipo = ""
                
                # Valor total final: serviço (com desconto do serviço) + itens (com seus próprios descontos)
                # Os itens já têm seus descontos individuais aplicados em item.valor_total
                # Garantir que total_itens_servico_com_desconto seja Decimal
                if not isinstance(total_itens_servico_com_desconto, Decimal):
                    total_itens_servico_com_desconto = Decimal(str(total_itens_servico_com_desconto)) if total_itens_servico_com_desconto else Decimal('0.00')
                if not isinstance(valor_servico_com_desconto, Decimal):
                    valor_servico_com_desconto = Decimal(str(valor_servico_com_desconto)) if valor_servico_com_desconto else Decimal('0.00')
                servico_orc.valor_total_com_itens = valor_servico_com_desconto + total_itens_servico_com_desconto
                
                # Valor unitário BRUTO do serviço incluindo itens (para exibição - ANTES do desconto)
                # Calculado como: (valor total bruto com itens) / quantidade
                if qtd > 0:
                    servico_orc.valor_unitario_bruto_com_itens = valor_bruto_com_itens / qtd
                else:
                    servico_orc.valor_unitario_bruto_com_itens = Decimal('0.00')
                
                # Valor unitário do serviço incluindo itens (para exibição - DEPOIS do desconto)
                # Calculado como: (valor total com itens) / quantidade
                if qtd > 0:
                    servico_orc.valor_unitario_com_itens = servico_orc.valor_total_com_itens / qtd
                else:
                    servico_orc.valor_unitario_com_itens = Decimal('0.00')
                
                servicos_com_totais.append(servico_orc)
            except (ValueError, TypeError, AttributeError, InvalidOperation) as e:
                logger.warning(f"Erro ao calcular valores para serviço {servico_orc.id}: {e}")
                servico_orc.valor_total_bruto = Decimal('0.00')
                servico_orc.desconto_aplicado = Decimal('0.00')
                servico_orc.desconto_tipo = ""
                servico_orc.valor_unitario_bruto_com_itens = Decimal('0.00')
                servico_orc.valor_unitario_com_itens = Decimal('0.00')
                servico_orc.valor_total_com_itens = Decimal('0.00')
                servicos_com_totais.append(servico_orc)
        
        # Calcular totais
        # Nota: Os itens já estão incluídos no valor dos serviços (valor_total_com_itens)
        total_servicos = Decimal('0.00')
        for s in servicos_com_totais:
            valor = getattr(s, 'valor_total_com_itens', None)
            if valor is None:
                valor = getattr(s, 'valor_total', Decimal('0.00'))
            if not isinstance(valor, Decimal):
                valor = Decimal(str(valor)) if valor else Decimal('0.00')
            total_servicos += valor
        
        total_itens = Decimal('0.00')  # Itens já incluídos no valor dos serviços
        
        total_transporte = Decimal('0.00')
        try:
            for t in orcamento.transportes_orcamento.all():
                if t.valor_frete:
                    if not isinstance(t.valor_frete, Decimal):
                        total_transporte += Decimal(str(t.valor_frete))
                    else:
                        total_transporte += t.valor_frete
        except Exception as e:
            logger.warning(f"Erro ao calcular total_transporte: {e}")
        
        # Calcular subtotal
        subtotal = total_servicos + total_transporte
        
        # Log para debug
        logger.info(f"Impressão - Totais calculados - Servicos: {total_servicos}, Transporte: {total_transporte}, Subtotal: {subtotal}")
        
        # Calcular total bruto (sem descontos) e total de descontos aplicados
        total_bruto_servicos = Decimal('0.00')
        total_bruto_itens = Decimal('0.00')
        total_descontos_aplicados = Decimal('0.00')
        
        for servico_orc in servicos_com_totais:
            valor_bruto = getattr(servico_orc, 'valor_total_bruto', Decimal('0.00'))
            if not isinstance(valor_bruto, Decimal):
                valor_bruto = Decimal(str(valor_bruto)) if valor_bruto else Decimal('0.00')
            total_bruto_servicos += valor_bruto
            
            desconto = getattr(servico_orc, 'desconto_aplicado', Decimal('0.00'))
            if not isinstance(desconto, Decimal):
                desconto = Decimal(str(desconto)) if desconto else Decimal('0.00')
            total_descontos_aplicados += desconto
            
            for item in servico_orc.itens.all():
                valor_bruto_item = getattr(item, 'valor_total_bruto', Decimal('0.00'))
                if not isinstance(valor_bruto_item, Decimal):
                    valor_bruto_item = Decimal(str(valor_bruto_item)) if valor_bruto_item else Decimal('0.00')
                total_bruto_itens += valor_bruto_item
                
                desconto_item = getattr(item, 'desconto_aplicado', Decimal('0.00'))
                if not isinstance(desconto_item, Decimal):
                    desconto_item = Decimal(str(desconto_item)) if desconto_item else Decimal('0.00')
                total_descontos_aplicados += desconto_item
        
        total_bruto = total_bruto_servicos + total_bruto_itens + total_transporte
        
        # Calcular desconto global
        desconto_global = Decimal('0.00')
        if orcamento.desconto:
            try:
                desconto_global = Decimal(str(orcamento.desconto)) if not isinstance(orcamento.desconto, Decimal) else orcamento.desconto
            except:
                desconto_global = Decimal('0.00')
        
        valor_apos_desconto = subtotal - desconto_global
        if valor_apos_desconto < 0:
            valor_apos_desconto = Decimal('0.00')
        
        # Calcular IVA usando configuração do sistema
        from .models_base import ConfiguracaoFiscal
        try:
            taxa_iva_decimal = ConfiguracaoFiscal.get_taxa_iva_atual()
            if not isinstance(taxa_iva_decimal, Decimal):
                taxa_iva_decimal = Decimal(str(taxa_iva_decimal))
        except Exception as e:
            logger.warning(f"Erro ao buscar taxa IVA: {e}")
            taxa_iva_decimal = Decimal('0.16')  # Valor padrão 16%
        
        taxa_iva_percentual = taxa_iva_decimal * Decimal('100.00')
        valor_iva = valor_apos_desconto * taxa_iva_decimal
        valor_final = valor_apos_desconto + valor_iva
        
        # Log para debug
        logger.info(f"Impressão - IVA calculado - Taxa: {taxa_iva_percentual}%, Valor IVA: {valor_iva}, Valor Final: {valor_final}")
        
        # Buscar dados da empresa
        logger.info("Buscando dados da empresa...")
        try:
            dados_empresa = DadosEmpresa.objects.first()
            if dados_empresa:
                logger.info(f"Dados da empresa encontrados: {dados_empresa.nome}")
                if hasattr(dados_empresa, 'logo'):
                    logger.info(f"Logotipo da empresa: {dados_empresa.logo}")
            else:
                logger.warning("Nenhum dado de empresa encontrado")
        except Exception as e:
            logger.error(f"Erro ao buscar dados da empresa: {str(e)}")
            dados_empresa = None

        # NIBs, contas e validade da cotação (Dados da Empresa)
        conta_mpesa = getattr(dados_empresa, 'conta_mpesa', None) or '' if dados_empresa else ''
        conta_emola = getattr(dados_empresa, 'conta_emola', None) or '' if dados_empresa else ''
        conta_millennium_bim = getattr(dados_empresa, 'conta_millennium_bim', None) or '' if dados_empresa else ''
        conta_bci = getattr(dados_empresa, 'conta_bci', None) or '' if dados_empresa else ''
        validade_cotacao = getattr(dados_empresa, 'validade_cotacao', None) or '' if dados_empresa else ''

        # "Processado Por": usar dados do funcionário associado ao utilizador quando existir
        # (partilha de dados: perfil liga User <-> Funcionário)
        processado_por_nome = 'Sistema'
        processado_por_email = ''
        processado_por_telefone = ''
        criado_por_id = getattr(orcamento, 'criado_por_id', None) or (orcamento.criado_por.id if orcamento.criado_por else None)
        if criado_por_id:
            from meuprojeto.empresa.models_rh import PerfilUsuario
            user = orcamento.criado_por
            perfil = PerfilUsuario.objects.select_related('funcionario').filter(usuario_id=criado_por_id).first()
            if perfil and perfil.funcionario_id and perfil.funcionario:
                f = perfil.funcionario
                processado_por_nome = (getattr(f, 'nome_completo', None) or '').strip() or (user.get_full_name() or user.username or '').strip()
                processado_por_email = (getattr(f, 'email', None) or '').strip() or (user.email or '').strip()
                processado_por_telefone = (getattr(perfil, 'telefone', None) or '').strip()
                if not processado_por_telefone:
                    processado_por_telefone = (getattr(f, 'telefone', None) or getattr(f, 'telefone_alternativo', None) or '').strip()
            else:
                processado_por_nome = (user.get_full_name() or user.username or '').strip()
                processado_por_email = (user.email or '').strip()
                if perfil:
                    processado_por_telefone = (getattr(perfil, 'telefone', None) or '').strip()
                    if not processado_por_telefone and getattr(perfil, 'funcionario', None):
                        f = perfil.funcionario
                        processado_por_telefone = (getattr(f, 'telefone', None) or getattr(f, 'telefone_alternativo', None) or '').strip()
        
        context = {
            'request': request,
            'ordem': orcamento, 
            'is_orcamento': True,
            'MEDIA_URL': settings.MEDIA_URL,
            'servicos_orcamento': servicos_com_totais,
            'transportes': orcamento.transportes_orcamento.all(),
            'total_servicos': total_servicos,
            'total_itens': total_itens,
            'total_transporte': total_transporte,
            'total_bruto': total_bruto,
            'total_descontos_aplicados': total_descontos_aplicados,
            'subtotal': subtotal,
            'valor_apos_desconto': valor_apos_desconto,
            'valor_iva': valor_iva,
            'taxa_iva': taxa_iva_percentual,
            'valor_final': valor_final,
            'para_impressao': True,
            'dados_empresa': dados_empresa,
            'conta_mpesa': conta_mpesa,
            'conta_emola': conta_emola,
            'conta_millennium_bim': conta_millennium_bim,
            'conta_bci': conta_bci,
            'validade_cotacao': validade_cotacao,
            'processado_por_nome': processado_por_nome,
            'processado_por_email': processado_por_email,
            'processado_por_telefone': processado_por_telefone,
        }
        
        logger.info("Renderizando template de impressão...")
        return render(request, 'producao/servicos/orcamento/imprimir.html', context)
        
    except Exception as e:
        import traceback
        error_msg = f"Erro ao carregar página de impressão da cotação {id}: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        messages.error(request, f'Erro ao carregar página de impressão: {str(e)}')
        return redirect('producao:servico_orcamento_detail', id=id)


@login_required
def producao_servico_orcamento_itens_imprimir(request, id):
    """Documento imprimível com lista de materiais/produtos de uma cotação."""
    logger.info(f"Iniciando impressão de itens da cotação {id}")
    try:
        from decimal import Decimal, InvalidOperation
        from django.conf import settings
        from django.db.models import Prefetch
        from .models_base import DadosEmpresa
        from .models_stock import ItemOrcamentoServico

        orcamento = get_object_or_404(
            OrdemServico.objects.select_related(
                'cliente', 'responsavel', 'criado_por',
                'criado_por__perfil', 'criado_por__perfil__funcionario'
            ).prefetch_related(
                'servicos_orcamento__servico',
                'servicos_orcamento__itens__item',
                Prefetch(
                    'itens_orcamento_legado',
                    queryset=ItemOrcamentoServico.objects.filter(
                        servico_orcamento__isnull=True,
                    ).select_related('item'),
                ),
            ),
            id=id
        )

        def _proveniencia_servico_orcamento(servico_orc):
            """Texto para coluna de proveniência: nome no documento + serviço de catálogo quando útil."""
            nome_catalogo = ''
            if getattr(servico_orc, 'servico', None):
                nome_catalogo = (servico_orc.servico.nome or '').strip()
            doc = (getattr(servico_orc, 'nome_documento', None) or '').strip()
            if doc and nome_catalogo and doc.lower() != nome_catalogo.lower():
                return f'{doc} — {nome_catalogo}'
            if doc:
                return doc
            if nome_catalogo:
                return nome_catalogo
            return 'Serviço'

        # Lista detalhada dos itens cotados (linha a linha)
        itens_detalhados = []

        # Por serviço cotado (árvore: serviço → materiais/produtos)
        itens_por_servico = []

        # Agregar itens por produto/material para o resumo
        itens_map = {}

        def _registar_material(it, servico_nome_label, bloco_itens):
            """Acrescenta um ItemOrcamentoServico (produto/material) às listas e ao mapa agregado."""
            item_obj = getattr(it, 'item', None)
            if not item_obj:
                return
            try:
                qtd = Decimal(str(it.quantidade)) if it.quantidade is not None else Decimal('0.00')
            except (InvalidOperation, TypeError, ValueError):
                qtd = Decimal('0.00')

            descricao = (getattr(item_obj, 'descricao', None) or '').strip()
            row = {
                'servico_nome': servico_nome_label,
                'codigo': getattr(item_obj, 'codigo', '') or '',
                'nome': getattr(item_obj, 'nome', '') or 'Item',
                'descricao': descricao,
                'unidade_medida': getattr(item_obj, 'unidade_medida', '') or 'UN',
                'quantidade': qtd,
            }
            itens_detalhados.append(row)
            bloco_itens.append({
                'codigo': row['codigo'],
                'nome': row['nome'],
                'descricao': descricao,
                'unidade_medida': row['unidade_medida'],
                'quantidade': qtd,
            })

            key = item_obj.id
            if key not in itens_map:
                itens_map[key] = {
                    'id': item_obj.id,
                    'codigo': getattr(item_obj, 'codigo', '') or '',
                    'nome': getattr(item_obj, 'nome', '') or 'Item',
                    'descricao': descricao,
                    'unidade_medida': getattr(item_obj, 'unidade_medida', '') or 'UN',
                    'quantidade': Decimal('0.00'),
                }
            itens_map[key]['quantidade'] += qtd

        for servico_orc in orcamento.servicos_orcamento.all():
            bloco_itens = []
            for it in servico_orc.itens.all():
                _registar_material(it, _proveniencia_servico_orcamento(servico_orc), bloco_itens)

            itens_por_servico.append({
                'servico_nome': _proveniencia_servico_orcamento(servico_orc),
                'itens': bloco_itens,
            })

        # Itens legados: gravados na cotação sem linha de serviço (servico_orcamento nulo).
        # Não aparecem em servico_orc.itens — eram omitidos da lista impressa.
        legado_label = 'Cotação (itens sem linha de serviço associada)'
        bloco_legado = []
        for it in orcamento.itens_orcamento_legado.all():
            if it.servico_orcamento_id:
                continue
            _registar_material(it, legado_label, bloco_legado)
        if bloco_legado:
            itens_por_servico.append({
                'servico_nome': legado_label,
                'itens': bloco_legado,
            })

        itens_detalhados = sorted(
            itens_detalhados,
            key=lambda x: ((x.get('servico_nome') or '').lower(), (x.get('nome') or '').lower())
        )
        itens_agrupados = sorted(itens_map.values(), key=lambda x: (x.get('nome') or '').lower())

        # Dados da empresa (para cabeçalho)
        try:
            dados_empresa = DadosEmpresa.objects.first()
        except Exception:
            dados_empresa = None

        context = {
            'request': request,
            'ordem': orcamento,
            'MEDIA_URL': settings.MEDIA_URL,
            'dados_empresa': dados_empresa,
            'itens_detalhados': itens_detalhados,
            'itens_por_servico': itens_por_servico,
            'itens_agrupados': itens_agrupados,
            'total_linhas_detalhadas': len(itens_detalhados),
            'total_itens_distintos': len(itens_agrupados),
            'para_impressao': True,
        }
        return render(request, 'producao/servicos/orcamento/itens_imprimir.html', context)
    except Exception as e:
        import traceback
        logger.error(f"Erro ao imprimir itens da cotação {id}: {e}\n{traceback.format_exc()}")
        messages.error(request, f'Erro ao gerar lista de materiais/produtos: {str(e)}')
        return redirect('producao:servico_orcamento_detail', id=id)


@login_required
def producao_servico_orcamento_horarios_disponiveis(request):
    """Retorna as datas/horas ocupadas e horários de expediente para cálculo automático de agendamento"""
    from django.http import JsonResponse
    from datetime import datetime, timedelta, time
    from django.utils import timezone
    from .models_base import HorarioExpediente, Sucursal
    
    try:
        # Buscar todas as ordens agendadas (excluindo canceladas)
        ordens_agendadas = OrdemServico.objects.filter(
            status__in=['AGENDADA', 'EM_ANDAMENTO'],
            data_agendada__isnull=False
        ).exclude(
            status='CANCELADA'
        ).values_list('data_agendada', flat=True)
        
        # Converter para lista de strings no formato YYYY-MM-DD HH:MM
        horarios_ocupados = []
        for data_agendada in ordens_agendadas:
            if data_agendada:
                try:
                    horarios_ocupados.append(data_agendada.strftime('%Y-%m-%d %H:%M'))
                except (AttributeError, ValueError) as e:
                    logger.warning(f"Erro ao formatar data_agendada: {e}")
                    continue
        
        # Buscar horários de expediente da sucursal principal (ou primeira ativa)
        sucursal = Sucursal.objects.filter(ativa=True).first()
        horarios_expediente = {}
        
        if sucursal:
            try:
                # Buscar horários detalhados por dia da semana
                horarios_detalhados = sucursal.horarios_expediente.filter(ativo=True)
                for horario in horarios_detalhados:
                    try:
                        horarios_expediente[horario.dia_semana] = {
                            'hora_inicio': horario.hora_inicio.strftime('%H:%M') if horario.hora_inicio else '08:00',
                            'hora_fim': horario.hora_fim.strftime('%H:%M') if horario.hora_fim else '17:00',
                            'duracao_almoco_minutos': int(horario.duracao_almoco.total_seconds() / 60) if horario.duracao_almoco else 60
                        }
                    except (AttributeError, ValueError) as e:
                        logger.warning(f"Erro ao processar horário detalhado: {e}")
                        continue
                
                # Se não houver horários detalhados, usar os padrões da sucursal
                if not horarios_expediente:
                    try:
                        dias_trabalho = sucursal.get_dias_trabalho_weekdays() if hasattr(sucursal, 'get_dias_trabalho_weekdays') else list(range(5))
                        hora_inicio = sucursal.hora_inicio_expediente.strftime('%H:%M') if sucursal.hora_inicio_expediente else '08:00'
                        hora_fim = sucursal.hora_fim_expediente.strftime('%H:%M') if sucursal.hora_fim_expediente else '17:00'
                        duracao_almoco_minutos = int(sucursal.duracao_almoco.total_seconds() / 60) if sucursal.duracao_almoco else 60
                        
                        for dia in dias_trabalho:
                            horarios_expediente[dia] = {
                                'hora_inicio': hora_inicio,
                                'hora_fim': hora_fim,
                                'duracao_almoco_minutos': duracao_almoco_minutos
                            }
                    except (AttributeError, ValueError) as e:
                        logger.warning(f"Erro ao processar horários padrão da sucursal: {e}")
            except Exception as e:
                logger.warning(f"Erro ao buscar horários da sucursal: {e}")
        
        # Se ainda não houver horários, usar valores padrão
        if not horarios_expediente:
            for dia in range(5):  # Segunda a sexta
                horarios_expediente[dia] = {
                    'hora_inicio': '08:00',
                    'hora_fim': '17:00',
                    'duracao_almoco_minutos': 60
                }
        
        return JsonResponse({
            'horarios_ocupados': horarios_ocupados,
            'horarios_expediente': horarios_expediente,
            'status': 'success'
        })
    except Exception as e:
        logger.error(f"Erro ao buscar horários disponíveis: {e}", exc_info=True)
        # Retornar valores padrão mesmo em caso de erro
        horarios_expediente_padrao = {}
        for dia in range(5):  # Segunda a sexta
            horarios_expediente_padrao[dia] = {
                'hora_inicio': '08:00',
                'hora_fim': '17:00',
                'duracao_almoco_minutos': 60
            }
        return JsonResponse({
            'horarios_ocupados': [],
            'horarios_expediente': horarios_expediente_padrao,
            'status': 'error',
            'message': str(e)
        })


@login_required
@require_http_methods(["GET", "POST"])
def producao_servico_orcamento_edit(request, id, from_vendas_param=False):
    """Editar orçamento. from_vendas_param: quando True (chamado por Vendas), usa URLs de Vendas."""
    from_vendas = from_vendas_param or request.GET.get('from') == 'vendas' or request.POST.get('from') == 'vendas'
    edit_url = reverse('vendas:orcamento_edit', kwargs={'id': id}) if from_vendas else reverse('producao:servico_orcamento_edit', kwargs={'id': id})
    orcamento = get_object_or_404(
        OrdemServico.objects.select_related('cliente', 'responsavel', 'criado_por').prefetch_related(
            'servicos_orcamento__servico',
            'servicos_orcamento__itens__item',
            'transportes_orcamento__transportadora'
        ),
        id=id
    )
    
    # Verificar se é uma cotação ou ordem de serviço
    # Nota: Esta view também é usada para editar ordens de serviço com múltiplos serviços
    is_orcamento = orcamento.codigo.startswith('COT')
    
    # Verificar se a fatura já foi emitida (apenas para ordens de serviço, não cotações)
    if not is_orcamento and (orcamento.numero_impressao_fatura or 0) > 0:
        messages.error(request, f'A ordem de serviço {orcamento.codigo} já teve fatura emitida e não pode ser editada.')
        return redirect('producao:servico_ordem_detail', id=id)
    
    # Verificar se é uma cotação que já foi convertida em ordem de serviço
    # Usar o campo orcamento_origem para verificar se existe uma ordem de serviço relacionada
    if is_orcamento:
        # Verificar se existe uma ordem de serviço criada a partir desta cotação usando o campo orcamento_origem
        ordem_relacionada = OrdemServico.objects.filter(
            codigo__startswith='OS',
            orcamento_origem=orcamento
        ).first()
        
        if ordem_relacionada:
            messages.error(request, f'A cotação {orcamento.codigo} já foi convertida na ordem de serviço {ordem_relacionada.codigo} e não pode ser editada.')
            if from_vendas:
                return redirect('vendas:pedido_detail', id=ordem_relacionada.id)
            return redirect('producao:servico_ordem_detail', id=ordem_relacionada.id)
        
        # Verificar método antigo (comparando dados) para compatibilidade com registros antigos
        # Só verificar se tiver cliente (caso contrário pode ser pronto pagamento)
        ordem_relacionada_legado = None
        if orcamento.cliente:
            ordem_relacionada_legado = OrdemServico.objects.filter(
                codigo__startswith='OS',
                cliente=orcamento.cliente,
                data_agendada=orcamento.data_agendada,
                endereco_servico=orcamento.endereco_servico
            ).exclude(id=orcamento.id).first()
            
            if ordem_relacionada_legado:
                # Atualizar o campo orcamento_origem se não estiver preenchido
                if not ordem_relacionada_legado.orcamento_origem:
                    ordem_relacionada_legado.orcamento_origem = orcamento
                    ordem_relacionada_legado.save()
                messages.error(request, f'A cotação {orcamento.codigo} já foi convertida na ordem de serviço {ordem_relacionada_legado.codigo} e não pode ser editada.')
                if from_vendas:
                    return redirect('vendas:pedido_detail', id=ordem_relacionada_legado.id)
                return redirect('producao:servico_ordem_detail', id=ordem_relacionada_legado.id)
        
        # Se não encontrou ordem relacionada, permitir edição mesmo com status CONCLUIDA
        # (pode ter sido marcada como concluída manualmente sem criar ordem de serviço)
    
    if request.method == 'POST':
        # #region agent log
        try:
            import json as _json, time as _time
            from .models_stock import ItemOrcamentoServico as _ItemOrcamentoServico
            _data = {
                'method': request.method,
                'is_orcamento': is_orcamento,
                'from_vendas': from_vendas,
                'ordem_id': orcamento.id,
                'servicos_count_before': orcamento.servicos_orcamento.count(),
                'itens_count_before': _ItemOrcamentoServico.objects.filter(ordem_servico=orcamento).count(),
            }
            _log = open('debug-630fd6.log', 'a', encoding='utf-8')
            _log.write(_json.dumps({
                'sessionId': '630fd6',
                'runId': 'pre-fix',
                'hypothesisId': 'H1',
                'location': 'producao_servico_orcamento_edit',
                'message': 'POST entry',
                'data': _data,
                'timestamp': int(_time.time() * 1000),
            }) + '\n')
            _log.close()
        except Exception:
            pass
        # #endregion
        try:
            with transaction.atomic():
                cliente_id = request.POST.get('cliente')
                data_agendada_str = request.POST.get('data_agendada', '')
                hora_agendada = request.POST.get('hora_agendada', '09:00')
                local_entrega_sucursal = request.POST.get('local_entrega_sucursal', '').strip()
                endereco_servico = request.POST.get('endereco_servico', '').strip()
                # Usar local_entrega_sucursal se endereco_servico estiver vazio
                endereco_servico = endereco_servico or local_entrega_sucursal
                cidade_servico = request.POST.get('cidade_servico', '')
                equipe = request.POST.get('equipe', '')
                responsavel_id = request.POST.get('responsavel')
                prioridade = request.POST.get('prioridade', 'NORMAL')
                status = request.POST.get('status', 'AGENDADA')
                observacoes = request.POST.get('observacoes', '')
                problema_relatado = request.POST.get('problema_relatado', '')
                forma_pagamento = request.POST.get('forma_pagamento', 'PRONTO_PAGAMENTO')
                nome_cliente_pagamento = request.POST.get('nome_cliente_pagamento', '').strip()
                nuit_cliente_pagamento = request.POST.get('nuit_cliente_pagamento', '').strip()
                telefone_cliente_pagamento = request.POST.get('telefone_cliente_pagamento', '').strip()
                cliente_id_hidden = request.POST.get('cliente_id', '').strip()
                
                # Validar método de pagamento
                if forma_pagamento == 'PRONTO_PAGAMENTO':
                    if not nome_cliente_pagamento:
                        messages.error(request, 'Nome do cliente é obrigatório para pronto pagamento.')
                        return redirect(edit_url)
                    # Para pronto pagamento, cliente_id pode ser vazio (cliente novo)
                    if cliente_id_hidden:
                        try:
                            cliente = ClienteServico.objects.get(id=cliente_id_hidden)
                        except ClienteServico.DoesNotExist:
                            cliente = None
                    else:
                        cliente = None
                else:
                    # Para CREDITO, cliente_id é obrigatório
                    if not cliente_id_hidden:
                        messages.error(request, 'Cliente é obrigatório para venda a crédito.')
                        return redirect(edit_url)
                    cliente = get_object_or_404(ClienteServico, id=cliente_id_hidden)
                
                # Processar desconto global
                desconto_global = Decimal(request.POST.get('desconto', '0.00') or '0.00')
                orcamento.desconto = desconto_global
                
                # Para orçamento, data agendada é opcional
                if data_agendada_str:
                    try:
                        data_agendada = datetime.strptime(f"{data_agendada_str} {hora_agendada}", "%Y-%m-%d %H:%M")
                        data_agendada = timezone.make_aware(data_agendada)
                    except:
                        data_agendada = orcamento.data_agendada
                else:
                    data_agendada = orcamento.data_agendada
                
                orcamento.servico = None  # Não usar mais o campo único
                orcamento.cliente = cliente if cliente else None
                orcamento.data_agendada = data_agendada
                
                # Migrar dados do cliente se for CREDITO
                if forma_pagamento == 'CREDITO' and cliente:
                    orcamento.endereco_servico = endereco_servico or cliente.endereco or 'A definir'
                    orcamento.cidade_servico = cidade_servico or cliente.cidade or ''
                else:
                    orcamento.endereco_servico = endereco_servico or 'A definir'
                    orcamento.cidade_servico = cidade_servico or ''
                orcamento.equipe = equipe
                orcamento.responsavel_id = responsavel_id if responsavel_id else None
                orcamento.prioridade = prioridade
                orcamento.status = status
                orcamento.quantidade = Decimal('1.00')  # Valor padrão, não usado mais
                orcamento.valor_unitario = None  # Não usado mais
                # Desconto já foi processado acima na linha 2938, não sobrescrever
                
                # Processar método de pagamento
                orcamento.forma_pagamento = forma_pagamento
                if forma_pagamento == 'PRONTO_PAGAMENTO':
                    # Pronto pagamento: usar dados informados
                    orcamento.nome_cliente_pagamento = nome_cliente_pagamento
                    orcamento.nuit_cliente_pagamento = nuit_cliente_pagamento if nuit_cliente_pagamento else None
                    orcamento.telefone_cliente_pagamento = telefone_cliente_pagamento if telefone_cliente_pagamento else None
                    
                    # Preservar endereço personalizado se foi informado
                    # Se o usuário informou um endereço personalizado, usar esse valor
                    if endereco_servico and endereco_servico.strip():
                        orcamento.endereco_servico = endereco_servico
                    elif local_entrega_sucursal and local_entrega_sucursal.strip():
                        # Se não há endereco_servico mas há local_entrega_sucursal, usar esse
                        orcamento.endereco_servico = local_entrega_sucursal
                    elif not orcamento.endereco_servico or orcamento.endereco_servico == 'A definir':
                        # Só usar o padrão da sucursal se não houver nenhum endereço definido
                        from .models_base import Sucursal
                        sucursal_padrao = Sucursal.objects.filter(tipo='SEDE').first()
                        if not sucursal_padrao:
                            sucursal_padrao = Sucursal.objects.first()
                        local_entrega = sucursal_padrao.endereco if sucursal_padrao and sucursal_padrao.endereco else (sucursal_padrao.nome if sucursal_padrao else 'Localização da sucursal')
                        orcamento.endereco_servico = local_entrega
                    # Se já existe um endereço personalizado, mantê-lo
                else:
                    # Para CREDITO, limpar campos de pronto pagamento
                    orcamento.nome_cliente_pagamento = None
                    orcamento.nuit_cliente_pagamento = None
                    orcamento.telefone_cliente_pagamento = None
                
                    # Preservar endereço personalizado se foi informado
                    if endereco_servico and endereco_servico.strip():
                        orcamento.endereco_servico = endereco_servico
                    elif local_entrega_sucursal and local_entrega_sucursal.strip():
                        # Se não há endereco_servico mas há local_entrega_sucursal, usar esse
                        orcamento.endereco_servico = local_entrega_sucursal
                    elif cliente:
                        # Se não há endereço informado, usar o do cliente como padrão
                        if not orcamento.endereco_servico or orcamento.endereco_servico == 'A definir':
                            orcamento.endereco_servico = cliente.endereco or 'A definir'
                    else:
                        # Se não há cliente nem endereço informado
                        if not orcamento.endereco_servico or orcamento.endereco_servico == 'A definir':
                            orcamento.endereco_servico = 'A definir'
                
                orcamento.observacoes = observacoes
                orcamento.problema_relatado = problema_relatado
                
                # Processar validade da garantia
                validade_garantia = request.POST.get('validade_garantia_dias', '90')
                try:
                    validade_garantia = int(validade_garantia)
                    if validade_garantia < 0:
                        validade_garantia = 90
                except (ValueError, TypeError):
                    validade_garantia = 90
                orcamento.validade_garantia_dias = validade_garantia
                
                # Processar desconto global
                desconto_global = Decimal(request.POST.get('desconto', '0.00') or '0.00')
                orcamento.desconto = desconto_global
                
                if status == 'EM_ANDAMENTO' and not orcamento.data_inicio:
                    orcamento.data_inicio = timezone.now()
                elif status == 'CONCLUIDA' and not orcamento.data_conclusao:
                    orcamento.data_conclusao = timezone.now()
                
                orcamento.save()
                
                # IMPORTANTE: Deletar na ordem correta para evitar violação de chave estrangeira
                # 1. Primeiro deletar os itens (ItemOrcamentoServico) que referenciam os serviços
                ItemOrcamentoServico.objects.filter(ordem_servico=orcamento).delete()
                
                # 2. Processar serviços (múltiplos) - adicionar novos serviços
                from .models_stock import ServicoOrcamentoServico
                servico_ids = request.POST.getlist('servico_id[]')
                servico_quantidades = request.POST.getlist('servico_quantidade[]')
                servico_valores_unitarios = request.POST.getlist('servico_valor_unitario[]')
                servico_descontos_percentuais = request.POST.getlist('servico_desconto_percentual[]')
                servico_descontos = request.POST.getlist('servico_desconto[]')
                servico_nomes_documento = request.POST.getlist('servico_nome_documento[]')
                
                # Log para debug
                logger.info(f"Editando orçamento {orcamento.codigo} - Serviços recebidos no POST: {len(servico_ids)}")
                logger.info(f"IDs de serviços: {servico_ids}")
                
                # Filtrar IDs vazios ou nulos
                servico_ids_validos = [sid for sid in servico_ids if sid and sid.strip()]
                logger.info(f"IDs válidos após filtro: {len(servico_ids_validos)} - {servico_ids_validos}")

                # #region agent log
                try:
                    import json as _json2, time as _time2
                    from .models_stock import ItemOrcamentoServico as _ItemOrcamentoServico2
                    _data2 = {
                        'ordem_id': orcamento.id,
                        'servicos_count_before': orcamento.servicos_orcamento.count(),
                        'itens_count_after_delete': _ItemOrcamentoServico2.objects.filter(ordem_servico=orcamento).count(),
                        'servico_ids_raw_len': len(servico_ids),
                        'servico_ids_validos_len': len(servico_ids_validos),
                    }
                    _log2 = open('debug-630fd6.log', 'a', encoding='utf-8')
                    _log2.write(_json2.dumps({
                        'sessionId': '630fd6',
                        'runId': 'pre-fix',
                        'hypothesisId': 'H1',
                        'location': 'producao_servico_orcamento_edit',
                        'message': 'POST services parsed',
                        'data': _data2,
                        'timestamp': int(_time2.time() * 1000),
                    }) + '\n')
                    _log2.close()
                except Exception:
                    pass
                # #endregion
                
                if not servico_ids_validos:
                    # Se não há serviços no POST, verificar se havia serviços antes
                    if orcamento.servicos_orcamento.exists():
                        # Se havia serviços mas não foram enviados no POST, não deletar
                        # Isso pode acontecer se o JavaScript não carregou corretamente
                        messages.warning(request, 'Nenhum serviço foi enviado. Os serviços existentes foram mantidos. Se você quiser remover serviços, adicione pelo menos um novo serviço primeiro.')
                        # Não deletar os serviços existentes - pular esta seção
                        servicos_orcamento_criados = []
                        # #region agent log
                        try:
                            import json as _json3, time as _time3
                            from .models_stock import ItemOrcamentoServico as _ItemOrcamentoServico3
                            _data3 = {
                                'ordem_id': orcamento.id,
                                'servicos_existentes': orcamento.servicos_orcamento.count(),
                                'itens_existentes_apos_delete': _ItemOrcamentoServico3.objects.filter(ordem_servico=orcamento).count(),
                            }
                            _log3 = open('debug-630fd6.log', 'a', encoding='utf-8')
                            _log3.write(_json3.dumps({
                                'sessionId': '630fd6',
                                'runId': 'pre-fix',
                                'hypothesisId': 'H1',
                                'location': 'producao_servico_orcamento_edit',
                                'message': 'POST sem servicos_ids_validos, mantidos servicos existentes',
                                'data': _data3,
                                'timestamp': int(_time3.time() * 1000),
                            }) + '\n')
                            _log3.close()
                        except Exception:
                            pass
                        # #endregion
                    else:
                        messages.error(request, 'Pelo menos um serviço é obrigatório.')
                        return redirect(edit_url)
                else:
                    # Deletar serviços existentes apenas se houver novos serviços para criar
                    ServicoOrcamentoServico.objects.filter(ordem_servico=orcamento).delete()
                    
                    servicos_orcamento_criados = []
                    
                    for i, servico_id in enumerate(servico_ids):
                        if servico_id and servico_id.strip():
                            servico_id_int = int(servico_id)
                            
                            try:
                                servico_item = Item.objects.get(id=servico_id_int, tipo='PRODUTO', produto_tipo='SERVICO')
                                quantidade_servico = Decimal(servico_quantidades[i] if i < len(servico_quantidades) else '1.00')
                                valor_unitario_servico_str = servico_valores_unitarios[i] if i < len(servico_valores_unitarios) else '0.00'
                                valor_unitario_servico = Decimal(valor_unitario_servico_str) if valor_unitario_servico_str else Decimal('0.00')
                                
                                # Se valor_unitario não foi informado ou é zero, usar preço de venda do serviço
                                if not valor_unitario_servico or valor_unitario_servico == 0:
                                    valor_unitario_servico = servico_item.preco_venda if servico_item.preco_venda else Decimal('0.00')
                                
                                # Processar descontos individuais do serviço
                                desconto_percentual_servico_str = servico_descontos_percentuais[i] if i < len(servico_descontos_percentuais) else '0.00'
                                desconto_percentual_servico = Decimal(desconto_percentual_servico_str) if desconto_percentual_servico_str else Decimal('0.00')
                                
                                desconto_servico_str = servico_descontos[i] if i < len(servico_descontos) else '0.00'
                                desconto_servico = Decimal(desconto_servico_str) if desconto_servico_str else Decimal('0.00')
                                
                                nome_documento_servico = servico_nomes_documento[i].strip() if i < len(servico_nomes_documento) and servico_nomes_documento[i] else None
                                
                                # Sempre criar um novo registro (já deletamos todos os serviços anteriormente)
                                # Isso permite ter múltiplos serviços iguais com nomes de documento diferentes
                                servico_orcamento = ServicoOrcamentoServico.objects.create(
                                    ordem_servico=orcamento,
                                    servico=servico_item,
                                    quantidade=quantidade_servico,
                                    valor_unitario=valor_unitario_servico,
                                    desconto_percentual=desconto_percentual_servico,
                                    desconto=desconto_servico,
                                    nome_documento=nome_documento_servico
                                )
                                
                                servicos_orcamento_criados.append((i, servico_orcamento))
                                logger.info(f"Serviço {servico_item.nome} (ID: {servico_id_int}) adicionado/atualizado com sucesso")
                            except (Item.DoesNotExist, ValueError, IndexError) as e:
                                logger.error(f"Erro ao adicionar serviço ao orçamento: {e}", exc_info=True)
                                continue
                
                logger.info(f"Total de serviços criados/atualizados: {len(servicos_orcamento_criados)}")
                
                # 4. Processar produtos e materiais agrupados por serviço - adicionar novos itens
                for servico_index, servico_orcamento in servicos_orcamento_criados:
                    # Buscar itens deste serviço específico
                    item_ids = request.POST.getlist(f'item_servico_{servico_index}_id[]')
                    item_quantidades = request.POST.getlist(f'item_servico_{servico_index}_quantidade[]')
                    item_valores_unitarios = request.POST.getlist(f'item_servico_{servico_index}_valor_unitario[]')
                    item_descontos_percentuais = request.POST.getlist(f'item_servico_{servico_index}_desconto_percentual[]')
                    item_descontos = request.POST.getlist(f'item_servico_{servico_index}_desconto[]')
                    
                    for i, item_id in enumerate(item_ids):
                        if item_id and item_id.strip():
                            try:
                                item = Item.objects.get(id=item_id, tipo__in=['PRODUTO', 'MATERIAL'])
                                quantidade_item = Decimal(item_quantidades[i] if i < len(item_quantidades) else '1.00')
                                valor_unitario_item_str = item_valores_unitarios[i] if i < len(item_valores_unitarios) else '0.00'
                                valor_unitario_item = Decimal(valor_unitario_item_str) if valor_unitario_item_str else Decimal('0.00')
                                
                                # Se valor_unitario não foi informado ou é zero, usar preço de venda do item
                                if not valor_unitario_item or valor_unitario_item == 0:
                                    valor_unitario_item = item.preco_venda if item.preco_venda else Decimal('0.00')
                                
                                # Processar descontos individuais
                                desconto_percentual_item_str = item_descontos_percentuais[i] if i < len(item_descontos_percentuais) else '0.00'
                                desconto_percentual_item = Decimal(desconto_percentual_item_str) if desconto_percentual_item_str else Decimal('0.00')
                                
                                desconto_item_str = item_descontos[i] if i < len(item_descontos) else '0.00'
                                desconto_item = Decimal(desconto_item_str) if desconto_item_str else Decimal('0.00')
                                
                                ItemOrcamentoServico.objects.create(
                                    servico_orcamento=servico_orcamento,
                                    ordem_servico=orcamento,  # Manter para compatibilidade
                                    item=item,
                                    quantidade=quantidade_item,
                                    valor_unitario=valor_unitario_item,
                                    desconto_percentual=desconto_percentual_item,
                                    desconto=desconto_item
                                )
                            except (Item.DoesNotExist, ValueError, IndexError) as e:
                                logger.warning(f"Erro ao adicionar item ao serviço {servico_orcamento.id}: {e}")
                                continue
                    servico_index += 1
                
                # Processar transportes - remover existentes e adicionar novos
                TransporteOrcamentoServico.objects.filter(ordem_servico=orcamento).delete()
                
                transporte_tipos = request.POST.getlist('transporte_tipo[]')
                transporte_ids = request.POST.getlist('transporte_id[]')
                transporte_valores = request.POST.getlist('transporte_valor[]')
                
                for i, transporte_id in enumerate(transporte_ids):
                    if transporte_id and transporte_id.strip():
                        try:
                            transportadora = Transportadora.objects.get(id=transporte_id)
                            tipo_transporte = transporte_tipos[i] if i < len(transporte_tipos) else 'EXTERNO'
                            valor_frete = Decimal(transporte_valores[i] if i < len(transporte_valores) else '0.00')
                            
                            TransporteOrcamentoServico.objects.create(
                                ordem_servico=orcamento,
                                transportadora=transportadora,
                                tipo_transporte=tipo_transporte,
                                valor_frete=valor_frete
                            )
                        except (Transportadora.DoesNotExist, ValueError, IndexError) as e:
                            logger.warning(f"Erro ao adicionar transporte ao orçamento: {e}")
                            continue
                
                # Recalcular valor_total da ordem após salvar todos os itens
                orcamento.refresh_from_db()
                valor_servicos = sum(servico.valor_total for servico in orcamento.servicos_orcamento.all())
                valor_itens = sum(
                    item.valor_total 
                    for servico in orcamento.servicos_orcamento.all() 
                    for item in servico.itens.all()
                )
                valor_transporte = sum(
                    transporte.valor_frete or Decimal('0.00') 
                    for transporte in orcamento.transportes_orcamento.all()
                )
                subtotal = valor_servicos + valor_itens + valor_transporte
                desconto = orcamento.desconto or Decimal('0.00')
                novo_valor_total = max(subtotal - desconto, Decimal('0.00'))
                orcamento.valor_total = novo_valor_total
                orcamento.save(update_fields=['valor_total'])

                # #region agent log
                try:
                    import json as _json4, time as _time4
                    from .models_stock import ItemOrcamentoServico as _ItemOrcamentoServico4, ServicoOrcamentoServico as _ServicoOrcamentoServico4
                    _data4 = {
                        'ordem_id': orcamento.id,
                        'is_orcamento': is_orcamento,
                        'from_vendas': from_vendas,
                        'servicos_count_after': _ServicoOrcamentoServico4.objects.filter(ordem_servico=orcamento).count(),
                        'itens_count_after': _ItemOrcamentoServico4.objects.filter(ordem_servico=orcamento).count(),
                        'valor_total_novo': str(novo_valor_total),
                    }
                    _log4 = open('debug-630fd6.log', 'a', encoding='utf-8')
                    _log4.write(_json4.dumps({
                        'sessionId': '630fd6',
                        'runId': 'pre-fix',
                        'hypothesisId': 'H1',
                        'location': 'producao_servico_orcamento_edit',
                        'message': 'POST final after save',
                        'data': _data4,
                        'timestamp': int(_time4.time() * 1000),
                    }) + '\n')
                    _log4.close()
                except Exception:
                    pass
                # #endregion
                
                if is_orcamento:
                    messages.success(request, f'Cotação {orcamento.codigo} atualizada com sucesso!')
                    if from_vendas:
                        return redirect('vendas:orcamento_detail', id=orcamento.id)
                    return redirect('producao:servico_orcamento_confirmar', id=orcamento.id)
                else:
                    messages.success(request, f'Ordem de serviço {orcamento.codigo} atualizada com sucesso!')
                    return redirect('producao:servico_ordem_detail', id=orcamento.id)
        except Exception as e:
            logger.error(f"Erro ao atualizar {'orçamento' if is_orcamento else 'ordem de serviço'} {id}: {e}", exc_info=True)
            messages.error(request, f'Erro ao atualizar {"cotação" if is_orcamento else "ordem de serviço"}: {str(e)}')
    
    # Incluir todos os serviços (ATIVO e outros) para poder adicionar a cotações
    servicos = Item.objects.filter(tipo='PRODUTO', produto_tipo='SERVICO').order_by('nome')
    clientes = ClienteServico.objects.filter(ativo=True).order_by('nome')
    usuarios = User.objects.filter(is_active=True).order_by('username')
    produtos_materiais = Item.objects.filter(tipo__in=['PRODUTO', 'MATERIAL'], status='ATIVO').exclude(produto_tipo='SERVICO').order_by('nome')
    transportadoras = Transportadora.objects.filter(status='ATIVA').order_by('nome')
    
    # Buscar taxa de IVA
    from .models_base import ConfiguracaoFiscal
    taxa_iva_decimal = ConfiguracaoFiscal.get_taxa_iva_atual()
    taxa_iva_percentual = taxa_iva_decimal * Decimal('100.00')
    
    url_form_action = reverse('vendas:orcamento_edit', kwargs={'id': id}) if from_vendas else None
    context = {
        'ordem': orcamento,
        'servicos': servicos,
        'clientes': clientes,
        'usuarios': usuarios,
        'produtos_materiais': produtos_materiais,
        'transportadoras': transportadoras,
        'prioridade_choices': OrdemServico.PRIORIDADE_CHOICES,
        'status_choices': OrdemServico.STATUS_CHOICES,
        'is_orcamento': is_orcamento,  # Detectar se é cotação ou ordem de serviço
        'taxa_iva': taxa_iva_percentual,  # Taxa de IVA em percentual
        'from_vendas': from_vendas,
        'url_form_action': url_form_action,
    }
    # #region agent log
    try:
        import json as _json5, time as _time5
        from .models_stock import ItemOrcamentoServico as _ItemOrcamentoServico5
        _data5 = {
            'ordem_id': orcamento.id,
            'is_orcamento': is_orcamento,
            'from_vendas': from_vendas,
            'servicos_count': orcamento.servicos_orcamento.count(),
            'itens_count': _ItemOrcamentoServico5.objects.filter(ordem_servico=orcamento).count(),
        }
        _log5 = open('debug-630fd6.log', 'a', encoding='utf-8')
        _log5.write(_json5.dumps({
            'sessionId': '630fd6',
            'runId': 'pre-fix',
            'hypothesisId': 'H1',
            'location': 'producao_servico_orcamento_edit',
            'message': 'GET render form',
            'data': _data5,
            'timestamp': int(_time5.time() * 1000),
        }) + '\n')
        _log5.close()
    except Exception:
        pass
    # #endregion
    # #region agent log
    try:
        import json
        _cnt = orcamento.servicos_orcamento.count() if getattr(orcamento, 'servicos_orcamento', None) else 0
        _log = open('debug-24ec57.log', 'a', encoding='utf-8')
        _log.write(json.dumps({'hypothesisId': 'A', 'location': 'producao_servico_orcamento_edit', 'message': 'render form GET', 'data': {'servicos_count': servicos.count() if hasattr(servicos, 'count') else len(servicos), 'has_ordem': True, 'ordem_id': id, 'ordem_servicos_count': _cnt}, 'timestamp': __import__('time').time() * 1000}) + '\n')
        _log.close()
    except Exception:
        pass
    # #endregion
    return render(request, 'producao/servicos/orcamento/form.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def producao_servico_orcamento_delete(request, id):
    """Deletar orçamento"""
    orcamento = get_object_or_404(OrdemServico, id=id)
    
    if request.method == 'POST':
        try:
            codigo = orcamento.codigo
            orcamento.delete()
            messages.success(request, f'Orçamento {codigo} excluído com sucesso!')
            return redirect('producao:servicos_orcamento')
        except Exception as e:
            logger.error(f"Erro ao excluir orçamento {id}: {e}", exc_info=True)
            messages.error(request, f'Erro ao excluir orçamento: {str(e)}')
            return redirect('producao:servicos_orcamento')
    
    context = {'orcamento': orcamento}
    return render(request, 'producao/servicos/orcamento/delete.html', context)


@login_required
def producao_servico_ordem_detail(request, id):
    """Detalhes da ordem de serviço"""
    try:
        logger.info(f"Iniciando carregamento de detalhes da ordem de serviço {id}")
        from .models_stock import ServicoOrcamentoServico, ItemOrcamentoServico, TransporteOrcamentoServico
        from .models_base import ConfiguracaoFiscal
        
        logger.info(f"Buscando ordem {id}...")
        ordem = get_object_or_404(
            OrdemServico.objects.select_related('cliente', 'responsavel', 'criado_por', 'orcamento_origem').prefetch_related(
                'servicos_orcamento__servico',
                'servicos_orcamento__itens__item',
                'transportes_orcamento__transportadora',
                'atividades_execucao__subactividades',
                'atividades_execucao__parcela',
            ),
            id=id
        )
        # Forçar recarregamento do objeto para garantir dados atualizados (incluindo numero_impressao_garantia)
        ordem.refresh_from_db()
        logger.info(f"Ordem encontrada: {ordem.codigo}, Status: {ordem.status}, Garantias emitidas: {ordem.numero_impressao_garantia or 0}")
        
        # Verificar se é uma cotação ou ordem de serviço
        is_orcamento = ordem.codigo.startswith('COT')
        logger.info(f"É orçamento: {is_orcamento}")
        
        # Calcular totais usando valores COM descontos aplicados (para o resumo financeiro)
        # Os descontos dos serviços e itens são aplicados individualmente
        total_servicos = Decimal('0.00')
        total_servicos_bruto = Decimal('0.00')  # Para calcular o total de descontos
        try:
            servicos_list = list(ordem.servicos_orcamento.all())
            if servicos_list:
                for s in servicos_list:
                    try:
                        # Calcular valor bruto
                        valor_bruto_servico = (s.quantidade or Decimal('0.00')) * (s.valor_unitario or Decimal('0.00'))
                        total_servicos_bruto += valor_bruto_servico
                        
                        # Usar valor_total (que já aplica descontos) para o resumo financeiro
                        valor_total_servico = s.valor_total
                        if isinstance(valor_total_servico, Decimal):
                            total_servicos += valor_total_servico
                        else:
                            total_servicos += Decimal(str(valor_total_servico))
                    except (ValueError, InvalidOperation, AttributeError, TypeError) as e:
                        logger.warning(f"Erro ao calcular valor do serviço {s.id}: {e}")
                        continue
        except Exception as e:
            logger.warning(f"Erro ao calcular total_servicos: {e}")
            total_servicos = Decimal('0.00')
        
        # Calcular total de itens (produtos e materiais) usando valores COM descontos aplicados
        total_itens = Decimal('0.00')
        total_itens_bruto = Decimal('0.00')  # Para calcular o total de descontos
        try:
            for servico_orc in ordem.servicos_orcamento.all():
                try:
                    for item in servico_orc.itens.all():
                        try:
                            # Calcular valor bruto
                            valor_bruto_item = (item.quantidade or Decimal('0.00')) * (item.valor_unitario or Decimal('0.00'))
                            total_itens_bruto += valor_bruto_item
                            
                            # Usar valor_total (que já aplica descontos) para o resumo financeiro
                            valor_total_item = item.valor_total
                            if isinstance(valor_total_item, Decimal):
                                total_itens += valor_total_item
                            else:
                                total_itens += Decimal(str(valor_total_item))
                        except (ValueError, InvalidOperation, AttributeError, TypeError) as e:
                            logger.warning(f"Erro ao calcular valor do item {item.id}: {e}")
                            continue
                except Exception as e:
                    logger.warning(f"Erro ao processar itens do serviço {servico_orc.id}: {e}")
                    continue
        except Exception as e:
            logger.warning(f"Erro ao calcular total_itens: {e}")
            total_itens = Decimal('0.00')
        
        # Calcular total de descontos aplicados
        total_descontos = (total_servicos_bruto + total_itens_bruto) - (total_servicos + total_itens)
        
        total_transporte = Decimal('0.00')
        try:
            transportes_list = list(ordem.transportes_orcamento.all())
            if transportes_list:
                for t in transportes_list:
                    try:
                        valor = Decimal(str(t.valor_frete)) if t.valor_frete else Decimal('0')
                        total_transporte += valor
                    except (ValueError, InvalidOperation, AttributeError, TypeError) as e:
                        logger.warning(f"Erro ao calcular valor do transporte {t.id}: {e}")
                        continue
        except Exception as e:
            logger.warning(f"Erro ao calcular total_transporte: {e}")
            total_transporte = Decimal('0.00')
        
        # Garantir que os valores sejam Decimal
        try:
            subtotal = Decimal(str(total_servicos)) + Decimal(str(total_itens)) + Decimal(str(total_transporte))
        except (ValueError, InvalidOperation):
            subtotal = Decimal('0.00')
        
        try:
            desconto_global = Decimal(str(ordem.desconto)) if ordem.desconto else Decimal('0.00')
        except (ValueError, InvalidOperation, TypeError):
            desconto_global = Decimal('0.00')
        
        try:
            valor_apos_desconto = subtotal - desconto_global
            if valor_apos_desconto < 0:
                valor_apos_desconto = Decimal('0.00')
        except (ValueError, InvalidOperation):
            valor_apos_desconto = subtotal
        
        # Calcular IVA
        try:
            taxa_iva_decimal = ConfiguracaoFiscal.get_taxa_iva_atual()
            if not isinstance(taxa_iva_decimal, Decimal):
                taxa_iva_decimal = Decimal(str(taxa_iva_decimal))
        except Exception as e:
            logger.warning(f"Erro ao buscar taxa IVA: {e}")
            taxa_iva_decimal = Decimal('0.16')  # Valor padrão 16%
        
        try:
            taxa_iva_percentual = taxa_iva_decimal * Decimal('100.00')
            valor_iva = valor_apos_desconto * taxa_iva_decimal
            valor_final = valor_apos_desconto + valor_iva
        except (ValueError, InvalidOperation):
            taxa_iva_percentual = Decimal('16.00')
            valor_iva = Decimal('0.00')
            valor_final = valor_apos_desconto
        
        logger.info(f"Totais calculados - Servicos: {total_servicos}, Itens: {total_itens}, Transporte: {total_transporte}")
        
        # Verificar se é uma cotação que já foi convertida em ordem de serviço
        pode_editar = True
        ordem_relacionada = None
        
        # Verificar se a fatura já foi emitida (não permite edição após emissão)
        if (ordem.numero_impressao_fatura or 0) > 0:
            pode_editar = False
        
        if is_orcamento:
            ordem_relacionada = OrdemServico.objects.filter(
                codigo__startswith='OS',
                orcamento_origem=ordem
            ).first()
            if ordem_relacionada:
                pode_editar = False
            elif ordem.status == 'CONCLUIDA':
                # Verificar método legado para compatibilidade
                ordem_relacionada_legado = OrdemServico.objects.filter(
                    codigo__startswith='OS',
                    cliente=ordem.cliente,
                    data_agendada=ordem.data_agendada,
                    endereco_servico=ordem.endereco_servico
                ).exclude(id=ordem.id).first()
                if ordem_relacionada_legado:
                    ordem_relacionada = ordem_relacionada_legado
                    pode_editar = False
        
        # Calcular valor_total_bruto para cada serviço e item (para exibição no template)
        servicos_orcamento_list = list(ordem.servicos_orcamento.all())
        servicos_com_totais = []
        for servico_orc in servicos_orcamento_list:
            try:
                qtd = Decimal(str(servico_orc.quantidade)) if servico_orc.quantidade is not None else Decimal('0.00')
                valor_unit = Decimal(str(servico_orc.valor_unitario)) if servico_orc.valor_unitario is not None else Decimal('0.00')
                # Valor bruto (quantidade × valor unitário) - para exibição no "Total do Serviço"
                servico_orc.valor_total_bruto = qtd * valor_unit
                
                # Calcular valor bruto para cada item (produto/material) do serviço
                for item in servico_orc.itens.all():
                    try:
                        qtd_item = Decimal(str(item.quantidade)) if item.quantidade is not None else Decimal('0.00')
                        valor_unit_item = Decimal(str(item.valor_unitario)) if item.valor_unitario is not None else Decimal('0.00')
                        item.valor_total_bruto = qtd_item * valor_unit_item
                    except (ValueError, TypeError, AttributeError, InvalidOperation) as e:
                        logger.warning(f"Erro ao calcular valor_total_bruto para item {item.id}: {e}")
                        try:
                            qtd_item = Decimal(str(item.quantidade)) if item.quantidade is not None else Decimal('0.00')
                            valor_unit_item = Decimal(str(item.valor_unitario)) if item.valor_unitario is not None else Decimal('0.00')
                            item.valor_total_bruto = qtd_item * valor_unit_item
                        except:
                            item.valor_total_bruto = Decimal('0.00')
            except (ValueError, TypeError, AttributeError, InvalidOperation) as e:
                logger.warning(f"Erro ao calcular valor_total_bruto para serviço {servico_orc.id}: {e}")
                try:
                    qtd = Decimal(str(servico_orc.quantidade)) if servico_orc.quantidade is not None else Decimal('0.00')
                    valor_unit = Decimal(str(servico_orc.valor_unitario)) if servico_orc.valor_unitario is not None else Decimal('0.00')
                    servico_orc.valor_total_bruto = qtd * valor_unit
                except:
                    servico_orc.valor_total_bruto = Decimal('0.00')
            servicos_com_totais.append(servico_orc)

        # Há pelo menos um item (produto/material) para mostrar na tabela única?
        tem_itens_servicos = any(
            any(getattr(it, 'item', None) for it in s.itens.all())
            for s in servicos_com_totais
        )

        # Plano de execução (etapas/actividades) — apenas para ordem de serviço (não cotação)
        atividades_flat = []
        progresso_etapas = {'total': 0, 'concluidas': 0, 'percent': 0}
        cronograma_atrasos = []
        cronograma_gantt = []
        min_date = max_date = None
        gantt_ticks = []
        hoje_pct = None
        cronograma_todas_datas_iguais = False
        data_referencia = None
        recebimentos_parcelas_gantt = []
        if not is_orcamento:
            from .cronograma_plano_service import build_cronograma_context
            ctx_cron = build_cronograma_context(ordem)
            atividades_flat = ctx_cron['atividades_flat']
            progresso_etapas = ctx_cron['progresso_etapas']
            cronograma_atrasos = ctx_cron['cronograma_atrasos']
            cronograma_gantt = ctx_cron['cronograma_gantt']
            min_date = ctx_cron['gantt_min_date']
            max_date = ctx_cron['gantt_max_date']
            gantt_ticks = ctx_cron['gantt_ticks']
            hoje_pct = ctx_cron['gantt_hoje_pct']
            cronograma_todas_datas_iguais = ctx_cron.get('cronograma_todas_datas_iguais', False)
            data_referencia = ctx_cron.get('data_referencia')

        # Diagrama de previsão de recebimentos das parcelas (pontos + datas, atrasos como no cronograma)
        if not is_orcamento and atividades_flat and min_date and max_date:
            try:
                from .parcelas_vendas_utils import _valor_total_com_iva_ordem, ordem_e_so_servicos
                hoje_ref = timezone.localtime(timezone.now()).date() if hasattr(timezone, 'localtime') else timezone.now().date()
                if hasattr(hoje_ref, 'date'):
                    hoje_ref = hoje_ref.date() if callable(hoje_ref.date) else hoje_ref
                if ordem_e_so_servicos(ordem):
                    valor_total_iva = _valor_total_com_iva_ordem(ordem)
                    if valor_total_iva and valor_total_iva > 0:
                        total_days = max(1, (max_date - min_date).days)
                        # parcela_id -> (data_prevista, parcela, atividade que libera)
                        parcela_to_data = {}
                        for item in atividades_flat:
                            atv = item['atividade']
                            if not getattr(atv, 'parcela_id', None):
                                continue
                            dp = getattr(atv, 'data_prevista_conclusao', None)
                            if dp is None:
                                continue
                            d = dp.date() if hasattr(dp, 'date') else dp
                            if atv.parcela_id not in parcela_to_data or (parcela_to_data[atv.parcela_id][0] is not None and d > parcela_to_data[atv.parcela_id][0]):
                                parcela_to_data[atv.parcela_id] = (d, atv.parcela, atv)
                        for _pid, (d_prev, parcela, atv) in parcela_to_data.items():
                            valor = valor_total_iva * Decimal(parcela.percentagem) / Decimal('100')
                            if valor <= 0:
                                continue
                            left_pct = max(0.0, min(100.0, (d_prev - min_date).days / total_days * 100))
                            # Atraso: data prevista já passou e etapa ainda não concluída
                            em_atraso = (d_prev < hoje_ref and getattr(atv, 'status', None) != 'CONCLUIDA')
                            recebimentos_parcelas_gantt.append({
                                'label': f"Parcela {parcela.numero_ordem} – {parcela.percentagem}%",
                                'valor': valor,
                                'data_prevista': d_prev,
                                'left_pct': round(left_pct, 1),
                                'parcela_numero': parcela.numero_ordem,
                                'percentagem': parcela.percentagem,
                                'em_atraso': em_atraso,
                            })
            except Exception:
                pass

        # Plano pode ser editado apenas se nenhuma actividade foi iniciada ou concluída
        plano_pode_ser_editado = not any(
            _atividade_bloqueada_para_edicao(item['atividade']) for item in atividades_flat
        ) if atividades_flat else True

        # Garantir que todos os valores sejam Decimal para evitar erros no template
        context = {
            'ordem': ordem,
            'is_orcamento': is_orcamento,
            'servicos_orcamento': servicos_com_totais,
            'tem_itens_servicos': tem_itens_servicos,
            'transportes': list(ordem.transportes_orcamento.all()),
            'total_servicos': total_servicos,
            'total_itens': total_itens,
            'total_transporte': total_transporte,
            'total_descontos': total_descontos,
            'subtotal': subtotal,
            'valor_apos_desconto': valor_apos_desconto,
            'valor_iva': valor_iva,
            'taxa_iva': taxa_iva_percentual,
            'valor_final': valor_final,
            'pode_editar': pode_editar,
            'ordem_relacionada': ordem_relacionada,
            'atividades_flat': atividades_flat,
            'plano_tem_etapas': len(atividades_flat) > 0,
            'plano_pode_ser_editado': plano_pode_ser_editado,
            'progresso_etapas': progresso_etapas,
            'cronograma_atrasos': cronograma_atrasos,
            'cronograma_gantt': cronograma_gantt if not is_orcamento else [],
            'gantt_min_date': min_date if not is_orcamento else None,
            'gantt_max_date': max_date if not is_orcamento else None,
            'gantt_ticks': gantt_ticks if not is_orcamento else [],
            'gantt_hoje_pct': hoje_pct if not is_orcamento else None,
            'cronograma_todas_datas_iguais': cronograma_todas_datas_iguais if not is_orcamento else False,
            'data_referencia': data_referencia,
            'recebimentos_parcelas_gantt': recebimentos_parcelas_gantt if not is_orcamento else [],
        }
        
        logger.info(f"Contexto preparado, renderizando template...")
        return render(request, 'producao/servicos/ordens/detail.html', context)
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"Erro ao exibir detalhes da ordem de serviço {id}: {e}\n{error_trace}")
        messages.error(request, f'Erro ao carregar detalhes da ordem de serviço: {str(e)}')
        # Tentar redirecionar para a lista, mas se falhar, mostrar erro genérico
        try:
            return redirect('producao:servicos_ordens')
        except:
            from django.http import HttpResponse
            return HttpResponse(f'<h1>Erro ao carregar detalhes da ordem de serviço</h1><p>{str(e)}</p><p><a href="/producao/servicos/ordens/">Voltar para lista</a></p>', status=500)


@login_required
@require_http_methods(["GET", "POST"])
def producao_servico_ordem_edit(request, id):
    """Editar ordem de serviço"""
    ordem = get_object_or_404(
        OrdemServico.objects.select_related('cliente', 'responsavel', 'criado_por').prefetch_related(
            'servicos_orcamento__servico',
            'servicos_orcamento__itens__item',
            'transportes_orcamento__transportadora'
        ),
        id=id
    )
    
    # Verificar se a fatura já foi emitida (não permite edição após emissão)
    if (ordem.numero_impressao_fatura or 0) > 0:
        messages.error(request, f'A ordem de serviço {ordem.codigo} já teve fatura emitida e não pode ser editada.')
        return redirect('producao:servico_ordem_detail', id=id)
    
    # Se a ordem tem múltiplos serviços (servicos_orcamento), usar o mesmo fluxo de edição de cotações
    if ordem.servicos_orcamento.exists():
        # Redirecionar para usar a mesma view de edição de cotações (que já suporta múltiplos serviços)
        # Mas precisamos garantir que funciona para ordens de serviço também
        return producao_servico_orcamento_edit(request, id)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                cliente_id = request.POST.get('cliente')
                data_agendada_str = request.POST.get('data_agendada')
                hora_agendada = request.POST.get('hora_agendada', '09:00')
                endereco_servico = request.POST.get('endereco_servico')
                cidade_servico = request.POST.get('cidade_servico', '')
                equipe = request.POST.get('equipe', '')
                responsavel_id = request.POST.get('responsavel')
                prioridade = request.POST.get('prioridade', 'NORMAL')
                status = request.POST.get('status', 'AGENDADA')
                servico_id = request.POST.get('servico')
                quantidade = Decimal(request.POST.get('quantidade', '1.00'))
                valor_unitario = request.POST.get('valor_unitario')
                desconto_percentual = request.POST.get('desconto_percentual', '0')
                desconto_input = request.POST.get('desconto', '0.00')
                observacoes = request.POST.get('observacoes', '')
                problema_relatado = request.POST.get('problema_relatado', '')
                solucao_aplicada = request.POST.get('solucao_aplicada', '')
                
                if not all([servico_id, cliente_id, data_agendada_str, endereco_servico]):
                    messages.error(request, 'Todos os campos obrigatórios devem ser preenchidos.')
                    return redirect('producao:servico_ordem_edit', id=id)
                
                servico = get_object_or_404(Item, id=servico_id, tipo='PRODUTO', produto_tipo='SERVICO')
                cliente = get_object_or_404(ClienteServico, id=cliente_id)
                
                try:
                    data_agendada = datetime.strptime(f"{data_agendada_str} {hora_agendada}", "%Y-%m-%d %H:%M")
                    data_agendada = timezone.make_aware(data_agendada)
                except:
                    messages.error(request, 'Data ou hora inválida.')
                    return redirect('producao:servico_ordem_edit', id=id)
                
                ordem.servico = servico
                ordem.cliente = cliente
                ordem.data_agendada = data_agendada
                ordem.endereco_servico = endereco_servico
                ordem.cidade_servico = cidade_servico
                ordem.equipe = equipe
                ordem.responsavel_id = responsavel_id if responsavel_id else None
                ordem.prioridade = prioridade
                ordem.status = status
                ordem.quantidade = quantidade
                # Usar preço do serviço se valor_unitario não for fornecido
                if valor_unitario:
                    valor_unitario_decimal = Decimal(valor_unitario)
                else:
                    valor_unitario_decimal = servico.preco_venda if servico.preco_venda else None
                ordem.valor_unitario = valor_unitario_decimal
                
                # Calcular desconto percentual (sempre percentual agora, pode ser 0% para sem desconto)
                desconto_percentual_decimal = Decimal(desconto_percentual)
                if desconto_percentual_decimal > 0 and valor_unitario_decimal:
                    valor_bruto = quantidade * valor_unitario_decimal
                    ordem.desconto = (valor_bruto * desconto_percentual_decimal / 100).quantize(Decimal('0.01'), rounding=ROUND_UP)
                else:
                    ordem.desconto = Decimal('0.00')
                ordem.observacoes = observacoes
                ordem.problema_relatado = problema_relatado
                ordem.solucao_aplicada = solucao_aplicada
                
                if status == 'EM_ANDAMENTO' and not ordem.data_inicio:
                    ordem.data_inicio = timezone.now()
                elif status == 'CONCLUIDA' and not ordem.data_conclusao:
                    ordem.data_conclusao = timezone.now()
                
                ordem.save()
                if status == 'CONCLUIDA' and ordem.codigo and ordem.codigo.startswith('OS'):
                    from .parcelas_vendas_utils import processar_parcelas_vendas_receber
                    processar_parcelas_vendas_receber(ordem, request.user, 'CONCLUSAO')
                messages.success(request, f'Ordem de serviço {ordem.codigo} atualizada com sucesso!')
                return redirect('producao:servico_ordem_detail', id=ordem.id)
        except Exception as e:
            logger.error(f"Erro ao atualizar ordem de serviço {id}: {e}", exc_info=True)
            messages.error(request, f'Erro ao atualizar ordem de serviço: {str(e)}')
    
    # Incluir todos os serviços (ATIVO e outros) para poder adicionar a cotações
    servicos = Item.objects.filter(tipo='PRODUTO', produto_tipo='SERVICO').order_by('nome')
    clientes = ClienteServico.objects.filter(ativo=True).order_by('nome')
    usuarios = User.objects.filter(is_active=True).order_by('username')
    
    context = {
        'ordem': ordem,
        'servicos': servicos,
        'clientes': clientes,
        'usuarios': usuarios,
        'prioridade_choices': OrdemServico.PRIORIDADE_CHOICES,
        'status_choices': OrdemServico.STATUS_CHOICES,
    }
    return render(request, 'producao/servicos/ordens/form.html', context)


@login_required
@require_http_methods(["POST"])
def producao_servico_ordem_alterar_status(request, id):
    """Alterar status da ordem de serviço (iniciar, pausar, retomar, concluir)"""
    ordem = get_object_or_404(OrdemServico, id=id)
    
    # Verificar se a fatura já foi emitida (não permite alteração de status após emissão)
    if (ordem.numero_impressao_fatura or 0) > 0:
        messages.error(request, f'A ordem de serviço {ordem.codigo} já teve fatura emitida e não pode ser alterada.')
        return redirect('producao:servico_ordem_detail', id=id)
    
    try:
        acao = request.POST.get('acao', '').strip()
        
        with transaction.atomic():
            if acao == 'iniciar':
                if ordem.status in ['CONCLUIDA', 'CANCELADA']:
                    messages.error(request, 'Não é possível iniciar uma ordem concluída ou cancelada.')
                    return redirect('producao:servico_ordem_detail', id=id)
                
                ordem.status = 'EM_ANDAMENTO'
                if not ordem.data_inicio:
                    ordem.data_inicio = timezone.now()
                ordem.save()
                messages.success(request, f'Ordem de serviço {ordem.codigo} iniciada com sucesso.')
                
            elif acao == 'pausar':
                if ordem.status != 'EM_ANDAMENTO':
                    messages.error(request, 'Apenas ordens em andamento podem ser pausadas.')
                    return redirect('producao:servico_ordem_detail', id=id)
                
                ordem.status = 'PAUSADA'
                ordem.save()
                messages.success(request, f'Ordem de serviço {ordem.codigo} pausada.')
                
            elif acao == 'retomar':
                if ordem.status != 'PAUSADA':
                    messages.error(request, 'Apenas ordens pausadas podem ser retomadas.')
                    return redirect('producao:servico_ordem_detail', id=id)
                
                ordem.status = 'EM_ANDAMENTO'
                ordem.save()
                messages.success(request, f'Ordem de serviço {ordem.codigo} retomada.')
                
            elif acao == 'concluir':
                if ordem.status in ['CANCELADA']:
                    messages.error(request, 'Não é possível concluir uma ordem cancelada.')
                    return redirect('producao:servico_ordem_detail', id=id)
                
                ordem.status = 'CONCLUIDA'
                if not ordem.data_conclusao:
                    ordem.data_conclusao = timezone.now()
                ordem.save()
                from .parcelas_vendas_utils import processar_parcelas_vendas_receber
                processar_parcelas_vendas_receber(ordem, request.user, 'CONCLUSAO')
                messages.success(request, f'Ordem de serviço {ordem.codigo} concluída com sucesso.')
                
            else:
                messages.error(request, 'Ação inválida.')
                
    except Exception as e:
        logger.error(f"Erro ao alterar status da ordem de serviço {id}: {e}", exc_info=True)
        messages.error(request, f'Erro ao alterar status: {str(e)}')
    
    return redirect('producao:servico_ordem_detail', id=id)


def _trabalhos_empreitada_para_ordem(ordem):
    """Trabalhos de empreitada cuja actividade pertence ao plano desta ordem (ou serviço, legado)."""
    from .models_rh import TrabalhoEmpreitada
    from django.db.models import Q
    return list(
        TrabalhoEmpreitada.objects.filter(
            Q(atividade_execucao__ordem_servico=ordem) | Q(servico_orcamento__ordem_servico=ordem)
        ).exclude(status='CANCELADO').select_related('prestador', 'atividade_execucao').order_by('descricao')
    )


def _enriquecer_etapas_trabalhos_disponiveis(etapas_flat, trabalhos_empreitada):
    """Para cada etapa, define trabalhos_disponiveis = trabalhos ainda não atribuídos a outras etapas (ou o atribuído a esta)."""
    ids_usados = set()
    for item in etapas_flat:
        atv = item.get('atividade')
        if atv and getattr(atv, 'trabalho_empreitada_id', None):
            ids_usados.add(atv.trabalho_empreitada_id)
    for item in etapas_flat:
        atv = item.get('atividade')
        id_desta = getattr(atv, 'trabalho_empreitada_id', None) if atv else None
        item['trabalhos_disponiveis'] = [
            t for t in trabalhos_empreitada
            if t.id == id_desta or t.id not in ids_usados
        ]
    return etapas_flat


def _enriquecer_etapas_servicos_disponiveis(etapas_flat, servicos_orcamento):
    """Para cada etapa, define servicos_disponiveis = serviços ainda não atribuídos a outras etapas (ou os atribuídos a esta). Assim cada serviço só aparece na etapa que o entrega."""
    ids_usados = set()
    for item in etapas_flat:
        atv = item.get('atividade')
        if atv and hasattr(atv, 'servicos_entregues'):
            ids_usados.update(atv.servicos_entregues.values_list('id', flat=True))
    for item in etapas_flat:
        atv = item.get('atividade')
        ids_desta = set(atv.servicos_entregues.values_list('id', flat=True)) if atv and hasattr(atv, 'servicos_entregues') else set()
        item['servicos_disponiveis'] = [
            s for s in servicos_orcamento
            if s.id not in ids_usados or s.id in ids_desta
        ]
    return etapas_flat


def _atividade_bloqueada_para_edicao(atividade):
    """Actividade está bloqueada para edição se foi iniciada ou concluída."""
    return (
        atividade.status in ('EM_ANDAMENTO', 'PAUSADA', 'CONCLUIDA') or
        atividade.data_inicio is not None
    )


def _plano_execucao_base_context(ordem, etapas_flat, etapa_count, roots_choices, from_vendas, servicos_orcamento, trabalhos_empreitada, parcelas_ordem):
    """Contexto base para plano_execucao.html, incluindo cronograma físico."""
    context = {
        'ordem': ordem,
        'etapas': etapas_flat,
        'etapa_count': etapa_count,
        'roots_choices': roots_choices,
        'from_vendas': from_vendas,
        'servicos_orcamento': servicos_orcamento,
        'trabalhos_empreitada': trabalhos_empreitada,
        'parcelas_ordem': parcelas_ordem,
    }
    try:
        from .cronograma_plano_service import build_cronograma_context
        ctx_cron = build_cronograma_context(ordem)
        context.update({
            'cronograma_atrasos': ctx_cron['cronograma_atrasos'],
            'cronograma_gantt': ctx_cron['cronograma_gantt'],
            'gantt_min_date': ctx_cron['gantt_min_date'],
            'gantt_max_date': ctx_cron['gantt_max_date'],
            'gantt_ticks': ctx_cron['gantt_ticks'],
            'gantt_hoje_pct': ctx_cron['gantt_hoje_pct'],
            'plano_tem_etapas': ctx_cron['plano_tem_etapas'],
        })
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning('Cronograma plano execução: falha ao construir contexto: %s', e, exc_info=True)
        context.update({
            'cronograma_atrasos': [], 'cronograma_gantt': [],
            'gantt_min_date': None, 'gantt_max_date': None, 'gantt_ticks': [], 'gantt_hoje_pct': None,
            'plano_tem_etapas': bool(etapas_flat),
        })
    return context


@login_required
def producao_servico_ordem_plano_execucao(request, id):
    """Definir ou editar o plano de execução (etapas/actividades) da ordem de serviço. Obrigatório após converter cotação em OS."""
    from .models_stock import AtividadeExecucao

    ordem = get_object_or_404(
        OrdemServico.objects.prefetch_related(
            'atividades_execucao__subactividades',
            'atividades_execucao__servicos_entregues',
            'atividades_execucao__parcela',
            'servicos_orcamento__servico',
            'parcelas_pagamento',
        ),
        id=id
    )
    from_vendas = request.GET.get('from') == 'vendas' or request.POST.get('from') == 'vendas'
    trabalhos_empreitada = _trabalhos_empreitada_para_ordem(ordem)
    if ordem.codigo and ordem.codigo.startswith('COT'):
        messages.error(request, 'O plano de execução aplica-se a ordens de serviço (OS), não a cotações.')
        return redirect('producao:servico_orcamento_detail', id=id)

    # Bloquear edição se alguma actividade foi iniciada ou concluída
    atividades_existentes = list(ordem.atividades_execucao.all())
    for atv in atividades_existentes:
        if _atividade_bloqueada_para_edicao(atv):
            messages.error(
                request,
                f'Não é possível editar o plano: a actividade «{atv.nome}» já foi iniciada ou concluída. '
                'Actividades em execução ou concluídas ficam bloqueadas para edição.'
            )
            return redirect('producao:servico_ordem_detail', id=id)

    # Ordenar: raízes por numero_ordem, depois filhos por numero_ordem (lista plana para o formulário)
    def _flat_atividades():
        raizes = list(ordem.atividades_execucao.filter(parent__isnull=True).order_by('numero_ordem', 'id'))
        flat = []
        for r in raizes:
            flat.append({'atividade': r, 'parent_flat_idx': -1})
            for sub in r.subactividades.order_by('numero_ordem', 'id'):
                parent_idx = next((i for i, x in enumerate(flat) if x['atividade'] == r), -1)
                flat.append({'atividade': sub, 'parent_flat_idx': parent_idx})
        return flat

    if request.method == 'POST':
        try:
            etape_count = request.POST.get('etapa_count', '0')
            n = int(etape_count) if etape_count.isdigit() else 0
            if n == 0:
                messages.error(request, 'Defina pelo menos uma etapa/actividade no plano de execução.')
                servicos_orcamento = list(ordem.servicos_orcamento.select_related('servico').all())
                parcelas_ordem = list(ordem.parcelas_pagamento.order_by('numero_ordem'))
                context = _plano_execucao_base_context(ordem, [], 0, [], from_vendas, servicos_orcamento, trabalhos_empreitada, parcelas_ordem)
                return render(request, 'producao/servicos/ordens/plano_execucao.html', context)

            ids_trabalhos_validos = {t.id for t in trabalhos_empreitada}
            ids_parcelas_validos = {p.id for p in ordem.parcelas_pagamento.all()}
            rows = []
            for i in range(n):
                nome = (request.POST.get(f'etapa_{i}_nome') or '').strip()
                if not nome:
                    continue
                # data_prevista_inicio e data_prevista (conclusão) vêm dos campos do formulário
                data_prev_inicio = request.POST.get(f'etapa_{i}_data_prevista_inicio') or None
                data_prev = request.POST.get(f'etapa_{i}_data_prevista') or None
                parent_idx_raw = request.POST.get(f'etapa_{i}_parent_idx', '').strip()
                parent_idx = int(parent_idx_raw) if parent_idx_raw != '' and parent_idx_raw.isdigit() else -1
                servicos_ids = [int(x) for x in request.POST.getlist(f'etapa_{i}_servicos') if str(x).isdigit()]
                trabalho_id_raw = (request.POST.get(f'etapa_{i}_trabalho_empreitada') or '').strip()
                trabalho_empreitada_id = int(trabalho_id_raw) if trabalho_id_raw.isdigit() and int(trabalho_id_raw) in ids_trabalhos_validos else None
                parcela_id_raw = (request.POST.get(f'etapa_{i}_parcela') or '').strip()
                parcela_id = int(parcela_id_raw) if parcela_id_raw.isdigit() and int(parcela_id_raw) in ids_parcelas_validos else None
                rows.append({
                    'nome': nome,
                    'data_prevista_inicio': data_prev_inicio,
                    'data_prevista': data_prev,
                    'parent_idx': parent_idx,
                    'form_idx': i,
                    'servicos_ids': servicos_ids,
                    'trabalho_empreitada_id': trabalho_empreitada_id,
                    'parcela_id': parcela_id,
                })

            if not rows:
                messages.error(request, 'Defina pelo menos uma etapa com nome.')
                etapas_flat = _flat_atividades()
                servicos_orcamento = list(ordem.servicos_orcamento.select_related('servico').all())
                if etapas_flat and trabalhos_empreitada:
                    _enriquecer_etapas_trabalhos_disponiveis(etapas_flat, trabalhos_empreitada)
                if etapas_flat and servicos_orcamento:
                    _enriquecer_etapas_servicos_disponiveis(etapas_flat, servicos_orcamento)
                roots_choices = [(i, f"{i + 1}. {etapas_flat[i]['atividade'].nome}") for i, x in enumerate(etapas_flat) if x['parent_flat_idx'] == -1] if etapas_flat else []
                parcelas_ordem = list(ordem.parcelas_pagamento.order_by('numero_ordem'))
                context = _plano_execucao_base_context(ordem, etapas_flat, max(1, len(etapas_flat)), roots_choices, from_vendas, servicos_orcamento, trabalhos_empreitada, parcelas_ordem)
                return render(request, 'producao/servicos/ordens/plano_execucao.html', context)

            with transaction.atomic():
                ordem.atividades_execucao.all().delete()
                created_ids = []
                for idx, r in enumerate(rows):
                    parent_id = None
                    if r['parent_idx'] >= 0 and r['parent_idx'] < len(created_ids):
                        parent_id = created_ids[r['parent_idx']]
                    parent_qs = AtividadeExecucao.objects.filter(pk=parent_id) if parent_id else AtividadeExecucao.objects.none()
                    parent_obj = parent_qs.first() if parent_id else None
                    # numero_ordem: no mesmo nível (mesmo parent), sequencial
                    irmaos_count = sum(1 for j in range(idx) if rows[j].get('parent_idx') == r['parent_idx'])
                    numero_ordem = irmaos_count + 1
                    data_prevista_inicio = None
                    if r.get('data_prevista_inicio'):
                        try:
                            from datetime import datetime
                            data_prevista_inicio = datetime.strptime(r['data_prevista_inicio'], '%Y-%m-%d').date()
                        except (ValueError, TypeError):
                            pass
                    data_prevista = None
                    if r['data_prevista']:
                        try:
                            from datetime import datetime
                            data_prevista = datetime.strptime(r['data_prevista'], '%Y-%m-%d').date()
                        except (ValueError, TypeError):
                            pass
                    atv = AtividadeExecucao.objects.create(
                        ordem_servico=ordem,
                        parent=parent_obj,
                        nome=r['nome'],
                        numero_ordem=numero_ordem,
                        data_prevista_inicio=data_prevista_inicio,
                        data_prevista_conclusao=data_prevista,
                        status='AGENDADA',
                        trabalho_empreitada_id=r.get('trabalho_empreitada_id'),
                        parcela_id=r.get('parcela_id'),
                    )
                    ids_servicos_validos = [sid for sid in r.get('servicos_ids', []) if ordem.servicos_orcamento.filter(pk=sid).exists()]
                    if ids_servicos_validos:
                        atv.servicos_entregues.set(ids_servicos_validos)
                    created_ids.append(atv.id)

            messages.success(request, 'Plano de execução guardado. Pode continuar para a ordem de serviço.')
            if from_vendas:
                return redirect('vendas:pedido_detail', id=ordem.id)
            return redirect('producao:servico_ordem_detail', id=ordem.id)
        except Exception as e:
            logger.error(f'Erro ao guardar plano de execução {id}: {e}', exc_info=True)
            messages.error(request, f'Erro ao guardar: {str(e)}')
            etapas_flat = _flat_atividades()
            servicos_orcamento = list(ordem.servicos_orcamento.select_related('servico').all())
            if etapas_flat and trabalhos_empreitada:
                _enriquecer_etapas_trabalhos_disponiveis(etapas_flat, trabalhos_empreitada)
            if etapas_flat and servicos_orcamento:
                _enriquecer_etapas_servicos_disponiveis(etapas_flat, servicos_orcamento)
            roots_choices = [(i, f"{i + 1}. {etapas_flat[i]['atividade'].nome}") for i, x in enumerate(etapas_flat) if x['parent_flat_idx'] == -1] if etapas_flat else []
            parcelas_ordem = list(ordem.parcelas_pagamento.order_by('numero_ordem'))
            context = _plano_execucao_base_context(ordem, etapas_flat, max(1, len(etapas_flat)), roots_choices, from_vendas, servicos_orcamento, trabalhos_empreitada, parcelas_ordem)
            return render(request, 'producao/servicos/ordens/plano_execucao.html', context)

    etapas_flat = _flat_atividades()
    servicos_orcamento = list(ordem.servicos_orcamento.select_related('servico').all())
    if etapas_flat and trabalhos_empreitada:
        _enriquecer_etapas_trabalhos_disponiveis(etapas_flat, trabalhos_empreitada)
    if etapas_flat and servicos_orcamento:
        _enriquecer_etapas_servicos_disponiveis(etapas_flat, servicos_orcamento)
    etapa_count = max(1, len(etapas_flat)) if etapas_flat else 1
    roots_choices = [(i, f"{i + 1}. {etapas_flat[i]['atividade'].nome}") for i, x in enumerate(etapas_flat) if x['parent_flat_idx'] == -1]
    parcelas_ordem = list(ordem.parcelas_pagamento.order_by('numero_ordem'))
    context = _plano_execucao_base_context(ordem, etapas_flat, etapa_count, roots_choices, from_vendas, servicos_orcamento, trabalhos_empreitada, parcelas_ordem)
    return render(request, 'producao/servicos/ordens/plano_execucao.html', context)


@login_required
def producao_servico_ordem_plano_imprimir(request, id):
    """Página para imprimir o plano de execução da ordem de serviço (cronograma físico + previsão recebimentos)."""
    ordem = get_object_or_404(OrdemServico, id=id)
    if ordem.codigo and ordem.codigo.startswith('COT'):
        messages.error(request, 'O plano de execução aplica-se a ordens de serviço (OS), não a cotações.')
        return redirect('producao:servico_ordem_detail', id=id)

    from .cronograma_plano_service import build_cronograma_context
    ctx_cron = build_cronograma_context(ordem)
    atividades_flat = ctx_cron['atividades_flat']
    min_date = ctx_cron.get('gantt_min_date')
    max_date = ctx_cron.get('gantt_max_date')

    # Segundo diagrama: previsão de recebimentos das parcelas (mesma escala)
    recebimentos_parcelas_gantt = []
    if atividades_flat and min_date and max_date:
        try:
            from .parcelas_vendas_utils import _valor_total_com_iva_ordem, ordem_e_so_servicos
            hoje_ref = timezone.localtime(timezone.now()).date() if hasattr(timezone, 'localtime') else timezone.now().date()
            if hasattr(hoje_ref, 'date'):
                hoje_ref = hoje_ref.date() if callable(hoje_ref.date) else hoje_ref
            if ordem_e_so_servicos(ordem):
                valor_total_iva = _valor_total_com_iva_ordem(ordem)
                if valor_total_iva and valor_total_iva > 0:
                    total_days = max(1, (max_date - min_date).days)
                    parcela_to_data = {}
                    for item in atividades_flat:
                        atv = item['atividade']
                        if not getattr(atv, 'parcela_id', None):
                            continue
                        dp = getattr(atv, 'data_prevista_conclusao', None)
                        if dp is None:
                            continue
                        d = dp.date() if hasattr(dp, 'date') else dp
                        if atv.parcela_id not in parcela_to_data or (parcela_to_data[atv.parcela_id][0] is not None and d > parcela_to_data[atv.parcela_id][0]):
                            parcela_to_data[atv.parcela_id] = (d, atv.parcela, atv)
                    for _pid, (d_prev, parcela, atv) in parcela_to_data.items():
                        valor = valor_total_iva * Decimal(parcela.percentagem) / Decimal('100')
                        if valor <= 0:
                            continue
                        left_pct = max(0.0, min(100.0, (d_prev - min_date).days / total_days * 100))
                        em_atraso = (d_prev < hoje_ref and getattr(atv, 'status', None) != 'CONCLUIDA')
                        recebimentos_parcelas_gantt.append({
                            'label': f"Parcela {parcela.numero_ordem} – {parcela.percentagem}%",
                            'valor': valor,
                            'data_prevista': d_prev,
                            'left_pct': round(left_pct, 1),
                            'parcela_numero': parcela.numero_ordem,
                            'percentagem': parcela.percentagem,
                            'em_atraso': em_atraso,
                        })
        except Exception:
            pass

    context = {
        'ordem': ordem,
        'atividades_flat': atividades_flat,
        'progresso_etapas': ctx_cron['progresso_etapas'],
        'cronograma_atrasos': ctx_cron['cronograma_atrasos'],
        'plano_tem_etapas': ctx_cron['plano_tem_etapas'],
        'cronograma_gantt': ctx_cron['cronograma_gantt'],
        'gantt_min_date': min_date,
        'gantt_max_date': max_date,
        'gantt_ticks': ctx_cron['gantt_ticks'],
        'gantt_hoje_pct': ctx_cron['gantt_hoje_pct'],
        'data_referencia': ctx_cron['data_referencia'],
        'recebimentos_parcelas_gantt': recebimentos_parcelas_gantt,
    }
    return render(request, 'producao/servicos/ordens/plano_imprimir.html', context)


@login_required
@require_http_methods(['POST'])
def producao_servico_atividade_alterar_status(request, id, atividade_id):
    """Alterar status de uma actividade do plano (iniciar, pausar, retomar, concluir)."""
    from .models_stock import AtividadeExecucao

    ordem = get_object_or_404(OrdemServico, id=id)
    atividade = get_object_or_404(AtividadeExecucao, id=atividade_id, ordem_servico=ordem)

    acao = (request.POST.get('acao') or '').strip().lower()
    if not acao:
        messages.error(request, 'Ação inválida.')
        return redirect('producao:servico_ordem_detail', id=id)

    try:
        with transaction.atomic():
            if acao == 'iniciar':
                if not atividade.pode_iniciar():
                    if atividade.parent_id and atividade.parent.status == 'AGENDADA':
                        messages.error(request, 'Inicie primeiro a etapa principal «%s» antes desta subetapa.' % atividade.parent.nome)
                    else:
                        messages.error(request, 'Esta actividade não pode ser iniciada agora (respeite a sequência ou o estado).')
                    return redirect('producao:servico_ordem_detail', id=id)
                now = timezone.now()
                # Subetapa: etapa principal deve ter data de início <= desta subetapa (definir se ainda não tiver)
                if atividade.parent_id and atividade.parent.data_inicio is None:
                    atividade.parent.data_inicio = now
                    atividade.parent.save(update_fields=['data_inicio'])
                atividade.status = 'EM_ANDAMENTO'
                if not atividade.data_inicio:
                    atividade.data_inicio = now
                atividade.save()
                messages.success(request, f'Actividade «{atividade.nome}» iniciada.')

            elif acao == 'pausar':
                if not atividade.pode_pausar():
                    messages.error(request, 'Apenas actividades em andamento podem ser pausadas.')
                    return redirect('producao:servico_ordem_detail', id=id)
                atividade.status = 'PAUSADA'
                atividade.save()
                messages.success(request, f'Actividade «{atividade.nome}» pausada.')

            elif acao == 'retomar':
                if not atividade.pode_retomar():
                    messages.error(request, 'Apenas actividades pausadas podem ser retomadas.')
                    return redirect('producao:servico_ordem_detail', id=id)
                atividade.status = 'EM_ANDAMENTO'
                atividade.save()
                messages.success(request, f'Actividade «{atividade.nome}» retomada.')

            elif acao == 'concluir':
                if not atividade.pode_concluir():
                    messages.error(request, 'Conclua as subactividades primeiro ou a actividade deve estar em andamento/pausada.')
                    return redirect('producao:servico_ordem_detail', id=id)
                _aplicar_conclusao_atividade(ordem, atividade, timezone.now(), request)
            else:
                messages.error(request, 'Ação inválida.')
    except Exception as e:
        logger.error(f'Erro ao alterar status da actividade {atividade_id}: {e}', exc_info=True)
        messages.error(request, f'Erro: {str(e)}')

    return redirect('producao:servico_ordem_detail', id=id)


def _aplicar_conclusao_atividade(ordem, atividade, data_conclusao_dt, request):
    """Aplica a conclusão da actividade (status, data_conclusao, empreitada, parcelas, etc.). data_conclusao_dt é datetime ou date."""
    from django.utils import timezone as tz
    from datetime import datetime as dt
    if hasattr(data_conclusao_dt, 'date') and not hasattr(data_conclusao_dt, 'hour'):
        data_conclusao_dt = tz.make_aware(dt.combine(data_conclusao_dt, dt.min.time())) if hasattr(tz, 'make_aware') else dt.combine(data_conclusao_dt, dt.min.time())
    atividade.status = 'CONCLUIDA'
    atividade.data_conclusao = data_conclusao_dt
    atividade.save()
    messages.success(request, f'Actividade «{atividade.nome}» concluída.')
    if atividade.trabalho_empreitada_id:
        try:
            trabalho = atividade.trabalho_empreitada
            if trabalho and trabalho.status != 'CONCLUIDO':
                trabalho.status = 'CONCLUIDO'
                trabalho.data_conclusao = data_conclusao_dt.date() if hasattr(data_conclusao_dt, 'date') else data_conclusao_dt
                trabalho.save()
                from .views import _processar_empreitada_concluida
                _processar_empreitada_concluida(trabalho, request.user)
                messages.success(request, 'Trabalho de empreitada marcado como concluído. Pendente de pagamento enviado a Finanças.')
        except Exception as e:
            logger.warning(f'RH empreitada ao concluir etapa: {e}')
    if atividade.parcela_id:
        try:
            from .parcelas_vendas_utils import criar_pendente_parcela_ligada_etapa
            if criar_pendente_parcela_ligada_etapa(ordem, atividade.parcela, request.user):
                messages.success(request, f'Parcela {atividade.parcela.numero_ordem} do contrato ficou exigível. Pendente de conta a receber criado em Finanças.')
        except Exception as e:
            logger.warning(f'criar_pendente_parcela_ligada_etapa: {e}')
    try:
        from .parcelas_vendas_utils import processar_parcelas_por_etapa_concluida
        n_parcelas = processar_parcelas_por_etapa_concluida(ordem, request.user)
        if n_parcelas > 0:
            messages.success(request, f'Foram gerados {n_parcelas} pendente(s) de contas a receber em Finanças (parcelas por etapa).')
    except Exception as e:
        logger.warning(f'processar_parcelas_por_etapa_concluida: {e}')
    restantes = ordem.atividades_execucao.exclude(status='CONCLUIDA').exists()
    if not restantes and ordem.status != 'CONCLUIDA':
        ordem.status = 'CONCLUIDA'
        if not ordem.data_conclusao:
            ordem.data_conclusao = data_conclusao_dt
        ordem.save()
        messages.success(request, 'Todas as etapas foram concluídas. Ordem de serviço marcada como concluída.')
        try:
            from .parcelas_vendas_utils import processar_parcelas_vendas_receber
            n = processar_parcelas_vendas_receber(ordem, request.user, 'CONCLUSAO')
            if n > 0:
                messages.success(request, f'Foram gerados {n} pendente(s) de contas a receber em Finanças (conforme parcelas do contrato).')
        except Exception as e:
            logger.warning(f'Aviso Finanças ao concluir ordem {ordem.id}: {e}')


@login_required
def producao_servico_atividade_confirmar_inicio(request, id, atividade_id):
    """Pergunta a data de início e inicia a actividade com essa data."""
    from .models_stock import AtividadeExecucao
    from datetime import datetime as dt

    ordem = get_object_or_404(OrdemServico, id=id)
    atividade = get_object_or_404(AtividadeExecucao, id=atividade_id, ordem_servico=ordem)
    if not atividade.pode_iniciar():
        if atividade.parent_id and atividade.parent.status == 'AGENDADA':
            messages.error(request, 'Inicie primeiro a etapa principal «%s» antes desta subetapa.' % atividade.parent.nome)
        else:
            messages.error(request, 'Esta actividade não pode ser iniciada agora.')
        return redirect('producao:servico_ordem_detail', id=id)

    if request.method == 'POST':
        data_inicio_str = (request.POST.get('data_inicio') or '').strip()
        if not data_inicio_str:
            messages.error(request, 'Indique a data de início.')
            return render(request, 'producao/servicos/ordens/atividade_confirmar_inicio.html', {
                'ordem': ordem, 'atividade': atividade,
                'data_inicio_value': timezone.now().date().strftime('%Y-%m-%d'),
            })
        try:
            d = dt.strptime(data_inicio_str[:10], '%Y-%m-%d').date()
            data_inicio_dt = timezone.make_aware(dt.combine(d, dt.min.time()))
            # Nenhuma subetapa pode começar antes da etapa principal
            if atividade.parent_id:
                parent = atividade.parent
                if parent.data_inicio is not None:
                    if data_inicio_dt < parent.data_inicio:
                        messages.error(
                            request,
                            'A data de início da subetapa não pode ser anterior à da etapa principal «%s» (%s).'
                            % (parent.nome, parent.data_inicio.date().strftime('%d/%m/%Y'))
                        )
                        return render(request, 'producao/servicos/ordens/atividade_confirmar_inicio.html', {
                            'ordem': ordem, 'atividade': atividade,
                            'data_inicio_value': data_inicio_str[:10],
                        })
            with transaction.atomic():
                if atividade.parent_id:
                    parent = atividade.parent
                    if parent.data_inicio is None:
                        # Primeira subetapa a iniciar: etapa principal passa a ter esta data de início
                        parent.data_inicio = data_inicio_dt
                        parent.save(update_fields=['data_inicio'])
                atividade.status = 'EM_ANDAMENTO'
                atividade.data_inicio = data_inicio_dt
                atividade.save()
            messages.success(request, f'Actividade «{atividade.nome}» iniciada com data de início {d.strftime("%d/%m/%Y")}.')
            return redirect('producao:servico_ordem_detail', id=id)
        except (ValueError, TypeError):
            messages.error(request, 'Data inválida.')
    data_inicio_value = timezone.now().date().strftime('%Y-%m-%d')
    return render(request, 'producao/servicos/ordens/atividade_confirmar_inicio.html', {
        'ordem': ordem, 'atividade': atividade, 'data_inicio_value': data_inicio_value,
    })


@login_required
def producao_servico_atividade_confirmar_conclusao(request, id, atividade_id):
    """Pergunta a data de conclusão e conclui a actividade com essa data."""
    from .models_stock import AtividadeExecucao
    from datetime import datetime as dt

    ordem = get_object_or_404(OrdemServico, id=id)
    atividade = get_object_or_404(AtividadeExecucao, id=atividade_id, ordem_servico=ordem)
    if not atividade.pode_concluir():
        messages.error(request, 'Conclua as subactividades primeiro ou a actividade deve estar em andamento/pausada.')
        return redirect('producao:servico_ordem_detail', id=id)

    if request.method == 'POST':
        data_conclusao_str = (request.POST.get('data_conclusao') or '').strip()
        if not data_conclusao_str:
            messages.error(request, 'Indique a data de conclusão.')
            return render(request, 'producao/servicos/ordens/atividade_confirmar_conclusao.html', {
                'ordem': ordem, 'atividade': atividade,
                'data_conclusao_value': timezone.now().date().strftime('%Y-%m-%d'),
            })
        try:
            d = dt.strptime(data_conclusao_str[:10], '%Y-%m-%d').date()
            data_conclusao_dt = timezone.make_aware(dt.combine(d, dt.min.time()))
            with transaction.atomic():
                _aplicar_conclusao_atividade(ordem, atividade, data_conclusao_dt, request)
            return redirect('producao:servico_ordem_detail', id=id)
        except (ValueError, TypeError):
            messages.error(request, 'Data inválida.')
    data_conclusao_value = timezone.now().date().strftime('%Y-%m-%d')
    return render(request, 'producao/servicos/ordens/atividade_confirmar_conclusao.html', {
        'ordem': ordem, 'atividade': atividade, 'data_conclusao_value': data_conclusao_value,
    })


@login_required
def producao_servico_atividade_editar_datas(request, id, atividade_id):
    """Permite definir ou editar manualmente a data de início e a data de conclusão da actividade (apenas se não estiver iniciada nem concluída)."""
    from .models_stock import AtividadeExecucao
    from datetime import datetime

    ordem = get_object_or_404(OrdemServico, id=id)
    atividade = get_object_or_404(AtividadeExecucao, id=atividade_id, ordem_servico=ordem)

    if _atividade_bloqueada_para_edicao(atividade):
        messages.error(
            request,
            'Não é possível alterar as datas de uma actividade já iniciada ou concluída. '
            'Actividades em execução ou concluídas ficam bloqueadas para edição.'
        )
        return redirect('producao:servico_ordem_detail', id=id)

    if request.method == 'POST':
        data_inicio_str = (request.POST.get('data_inicio') or '').strip()
        data_conclusao_str = (request.POST.get('data_conclusao') or '').strip()
        try:
            if data_inicio_str:
                d = datetime.strptime(data_inicio_str[:10], '%Y-%m-%d').date()
                data_inicio_dt = timezone.make_aware(datetime.combine(d, datetime.min.time()))
                # Subetapa não pode ter data de início anterior à da etapa principal
                if atividade.parent_id and atividade.parent.data_inicio is not None:
                    if data_inicio_dt < atividade.parent.data_inicio:
                        messages.error(
                            request,
                            'A data de início da subetapa não pode ser anterior à da etapa principal «%s» (%s).'
                            % (atividade.parent.nome, atividade.parent.data_inicio.date().strftime('%d/%m/%Y'))
                        )
                        data_inicio_value = data_inicio_str[:10]
                        data_conclusao_value = (request.POST.get('data_conclusao') or '').strip()[:10] or ''
                        return render(request, 'producao/servicos/ordens/atividade_editar_datas.html', {
                            'ordem': ordem, 'atividade': atividade,
                            'data_inicio_value': data_inicio_value, 'data_conclusao_value': data_conclusao_value,
                        })
                atividade.data_inicio = data_inicio_dt
            else:
                atividade.data_inicio = None
            if data_conclusao_str:
                d = datetime.strptime(data_conclusao_str[:10], '%Y-%m-%d').date()
                atividade.data_conclusao = timezone.make_aware(datetime.combine(d, datetime.min.time()))
            else:
                atividade.data_conclusao = None
            atividade.save()
            messages.success(request, f'Datas da actividade «{atividade.nome}» actualizadas.')
            return redirect('producao:servico_ordem_detail', id=id)
        except (ValueError, TypeError):
            messages.error(request, 'Formato de data inválido. Use data (ex.: dd/mm/aaaa).')

    # Valores actuais para o formulário (type="date" usa YYYY-MM-DD)
    data_inicio_value = ''
    if atividade.data_inicio:
        d = atividade.data_inicio.date() if hasattr(atividade.data_inicio, 'date') else atividade.data_inicio
        data_inicio_value = d.strftime('%Y-%m-%d') if hasattr(d, 'strftime') else ''
    data_conclusao_value = ''
    if atividade.data_conclusao:
        d = atividade.data_conclusao.date() if hasattr(atividade.data_conclusao, 'date') else atividade.data_conclusao
        data_conclusao_value = d.strftime('%Y-%m-%d') if hasattr(d, 'strftime') else ''

    context = {
        'ordem': ordem,
        'atividade': atividade,
        'data_inicio_value': data_inicio_value,
        'data_conclusao_value': data_conclusao_value,
    }
    return render(request, 'producao/servicos/ordens/atividade_editar_datas.html', context)


@login_required
def producao_servico_ordem_emitir_fatura(request, id):
    """Emitir fatura para ordem de serviço concluída"""
    from .fatura_ordem_utils import build_fatura_context
    ordem = get_object_or_404(
        OrdemServico.objects.select_related('cliente', 'responsavel', 'criado_por', 'orcamento_origem').prefetch_related(
            'servicos_orcamento__servico',
            'servicos_orcamento__itens__item',
            'transportes_orcamento__transportadora'
        ),
        id=id
    )
    if ordem.status != 'CONCLUIDA':
        messages.warning(request, 'Apenas ordens de serviço concluídas podem ter faturas emitidas.')
        return redirect('producao:servico_ordem_detail', id=id)
    try:
        context = build_fatura_context(request, ordem)
        return render(request, 'servicos/ordens/fatura.html', context)
    except ValueError as e:
        messages.warning(request, str(e))
        return redirect('producao:servico_ordem_detail', id=id)
    except Exception as e:
        logger.error(f"Erro ao emitir fatura da ordem de serviço {id}: {e}", exc_info=True)
        messages.error(request, f'Erro ao emitir fatura: {str(e)}')
        return redirect('producao:servico_ordem_detail', id=id)


@login_required
@require_http_methods(["POST"])
def producao_servico_ordem_marcar_cobrada(request, id):
    """Regista cobrança (cliente pagou): cria lançamentos 26+ e 22- e marca data_cobranca na ordem."""
    from django.db import transaction
    from .models_financas import Conta, LancamentoFinanceiro
    ordem = get_object_or_404(OrdemServico, id=id)
    if ordem.status != 'CONCLUIDA':
        messages.warning(request, 'Apenas ordens concluídas podem ter cobrança registada.')
        return redirect('producao:servico_ordem_detail', id=id)
    if not (ordem.numero_fatura_fiscal or '').strip():
        messages.warning(request, 'Emita a fatura antes de registar a cobrança.')
        return redirect('producao:servico_ordem_detail', id=id)
    if ordem.data_cobranca:
        messages.info(request, 'Esta fatura já tinha cobrança registada.')
        return redirect('producao:servico_ordem_detail', id=id)
    valor = getattr(ordem, 'valor_total', None) or Decimal('0.00')
    if isinstance(valor, (int, float)):
        valor = Decimal(str(valor))
    if valor <= 0:
        messages.error(request, 'Valor da ordem inválido.')
        return redirect('producao:servico_ordem_detail', id=id)
    try:
        with transaction.atomic():
            conta_26, _ = Conta.objects.get_or_create(
                codigo='26',
                defaults={'nome': 'Caixa e depósitos bancários', 'tipo': 'ATIVO', 'ativo': True, 'ordem': 0},
            )
            conta_22, _ = Conta.objects.get_or_create(
                codigo='22',
                defaults={'nome': 'Clientes e outros devedores', 'tipo': 'ATIVO', 'ativo': True, 'ordem': 0},
            )
            doc_ref = ordem.numero_fatura_fiscal or ordem.codigo
            descricao = f"Cobrança fatura {doc_ref} - {ordem.codigo}"
            hoje = timezone.now().date()
            LancamentoFinanceiro.objects.create(
                data=hoje, conta=conta_26, valor=valor,
                descricao=descricao, documento_ref=doc_ref, origem_tipo='MANUAL', criado_por=request.user,
            )
            LancamentoFinanceiro.objects.create(
                data=hoje, conta=conta_22, valor=-valor,
                descricao=descricao, documento_ref=doc_ref, origem_tipo='MANUAL', criado_por=request.user,
            )
            ordem.data_cobranca = hoje
            ordem.save(update_fields=['data_cobranca'])
        messages.success(request, 'Cobrança registada. Caixa (26) e Clientes (22) actualizados.')
    except Exception as e:
        logger.exception(f"Erro ao registar cobrança ordem {id}")
        messages.error(request, f'Erro ao registar cobrança: {str(e)}')
    return redirect('producao:servico_ordem_detail', id=id)


@login_required
def producao_servico_ordem_emitir_garantia(request, id):
    """Emitir garantia para ordem de serviço concluída"""
    ordem = get_object_or_404(
        OrdemServico.objects.select_related('cliente', 'responsavel', 'criado_por', 'orcamento_origem').prefetch_related(
            'servicos_orcamento__servico',
            'servicos_orcamento__itens__item',
            'transportes_orcamento__transportadora'
        ),
        id=id
    )
    
    # Verificar se a ordem está concluída
    if ordem.status != 'CONCLUIDA':
        messages.warning(request, 'Apenas ordens de serviço concluídas podem ter garantias emitidas.')
        return redirect('producao:servico_ordem_detail', id=id)
    # A garantia depende da fatura: só emitir após fatura emitida
    if not ordem.numero_impressao_fatura or ordem.numero_impressao_fatura <= 0:
        messages.warning(request, 'A garantia depende da fatura. Emita primeiro a fatura da ordem.')
        return redirect('producao:servico_ordem_detail', id=id)
    
    try:
        from .models_base import DadosEmpresa
        from datetime import datetime, timedelta
        from django.conf import settings
        
        # Buscar dados da empresa
        dados_empresa = DadosEmpresa.objects.first()
        
        # Gerar número da garantia (formato: GAR-YYYY-XXXXXX)
        hoje = datetime.now()
        data_emissao = hoje.date()
        hora_emissao = hoje.time()
        ano_atual = hoje.year
        
        # Contar garantias do ano para gerar número sequencial
        from django.db.models import Q
        garantias_antes = OrdemServico.objects.filter(
            codigo__startswith='OS',
            status='CONCLUIDA',
            numero_impressao_garantia__gt=0
        ).exclude(id=ordem.id)
        
        # Determinar data de referência desta ordem
        if ordem.data_conclusao:
            data_ref_ordem = ordem.data_conclusao.date()
            garantias_antes = garantias_antes.filter(
                Q(data_conclusao__date__year=ano_atual) & (
                    Q(data_conclusao__date__lt=data_ref_ordem) |
                    Q(data_conclusao__date=data_ref_ordem, id__lt=ordem.id)
                ) |
                Q(data_conclusao__isnull=True, data_criacao__date__year=ano_atual) & (
                    Q(data_criacao__date__lt=data_ref_ordem) |
                    Q(data_criacao__date=data_ref_ordem, id__lt=ordem.id)
                )
            )
        else:
            data_ref_ordem = ordem.data_criacao.date()
            garantias_antes = garantias_antes.filter(
                Q(data_criacao__date__year=ano_atual) & (
                    Q(data_criacao__date__lt=data_ref_ordem) |
                    Q(data_criacao__date=data_ref_ordem, id__lt=ordem.id)
                )
            )
        
        # Contar quantas garantias foram emitidas antes desta no mesmo ano
        numero_sequencial = garantias_antes.count() + 1
        numero_garantia = f"GAR-{ano_atual}-{numero_sequencial:06d}"
        
        # Incrementar contador de impressões da garantia
        from django.db import transaction
        with transaction.atomic():
            ordem.numero_impressao_garantia = (ordem.numero_impressao_garantia or 0) + 1
            ordem.save(update_fields=['numero_impressao_garantia'])
        
        # Determinar tipo de documento (ORIGINAL ou CÓPIA)
        if ordem.numero_impressao_garantia == 1:
            tipo_documento = 'ORIGINAL'
        else:
            tipo_documento = f'CÓPIA {ordem.numero_impressao_garantia - 1}'
        
        # Calcular data de validade da garantia (usar validade_garantia_dias definida na ordem, padrão 90 dias)
        if ordem.data_conclusao:
            data_inicio_garantia = ordem.data_conclusao.date()
        else:
            data_inicio_garantia = ordem.data_criacao.date()
        
        validade_dias = ordem.validade_garantia_dias if ordem.validade_garantia_dias else 90
        data_validade_garantia = data_inicio_garantia + timedelta(days=validade_dias)
        
        # Determinar dados do cliente
        if ordem.cliente:
            cliente_nome = ordem.cliente.nome
            cliente_documento = ordem.cliente.nuit if hasattr(ordem.cliente, 'nuit') else ''
            cliente_endereco = ordem.cliente.endereco if hasattr(ordem.cliente, 'endereco') else ''
            cliente_email = ordem.cliente.email if hasattr(ordem.cliente, 'email') else ''
        else:
            cliente_nome = ordem.nome_cliente_pagamento or 'Cliente não identificado'
            cliente_documento = ordem.nuit_cliente_pagamento or ''
            cliente_endereco = ordem.endereco_servico or ''
            cliente_email = ''
        
        # Lista de serviços prestados
        lista_servicos = []
        for servico_orc in ordem.servicos_orcamento.all():
            # Usar nome_para_documento (propriedade) se disponível, senão usar nome do serviço
            try:
                nome_servico = servico_orc.nome_para_documento
            except:
                if servico_orc.servico:
                    nome_servico = servico_orc.servico.nome
                else:
                    nome_servico = 'Serviço não especificado'
            quantidade = servico_orc.quantidade or 1
            unidade = getattr(getattr(servico_orc, 'servico', None), 'unidade_medida', None) or 'UN'
            lista_servicos.append(f"{quantidade} {unidade} x {nome_servico}")
        
        context = {
            'request': request,
            'ordem': ordem,
            'dados_empresa': dados_empresa,
            'servicos_orcamento': ordem.servicos_orcamento.all(),
            'numero_garantia': numero_garantia,
            'data_emissao': data_emissao,
            'hora_emissao': hora_emissao,
            'data_inicio_garantia': data_inicio_garantia,
            'data_validade_garantia': data_validade_garantia,
            'tipo_documento': tipo_documento,
            'cliente_nome': cliente_nome,
            'cliente_documento': cliente_documento,
            'cliente_endereco': cliente_endereco,
            'cliente_email': cliente_email,
            'lista_servicos': lista_servicos,
            'MEDIA_URL': settings.MEDIA_URL,
        }
        
        return render(request, 'producao/servicos/ordens/garantia.html', context)
        
    except Exception as e:
        logger.error(f"Erro ao emitir garantia da ordem de serviço {id}: {e}", exc_info=True)
        messages.error(request, f'Erro ao emitir garantia: {str(e)}')
        return redirect('producao:servico_ordem_detail', id=id)


@login_required
@require_http_methods(["GET", "POST"])
def producao_servicos_equipes(request):
    """Gestão de equipes de serviço"""
    if request.method == 'POST':
        try:
            with transaction.atomic():
                nome = request.POST.get('nome', '').strip()
                descricao = request.POST.get('descricao', '').strip()
                lider_id = request.POST.get('lider', '').strip()
                membros_ids = request.POST.getlist('membros')
                ativo = request.POST.get('ativo') == 'on'
                
                if not nome:
                    messages.error(request, 'Nome da equipe é obrigatório.')
                    return redirect('producao:servicos_equipes')
                
                equipe = EquipeServico.objects.create(
                    nome=nome,
                    descricao=descricao if descricao else None,
                    lider_id=int(lider_id) if lider_id else None,
                    ativo=ativo
                )
                
                # Adicionar membros
                if membros_ids:
                    membros = Funcionario.objects.filter(id__in=membros_ids, status='AT')
                    equipe.membros.set(membros)
                
                messages.success(request, f'Equipe "{nome}" criada com sucesso!')
                return redirect('producao:servicos_equipes')
        except Exception as e:
            logger.error(f"Erro ao criar equipe: {e}", exc_info=True)
            messages.error(request, f'Erro ao criar equipe: {str(e)}')
    
    # GET - Listar equipes
    try:
        equipes = EquipeServico.objects.all().prefetch_related('membros', 'lider')
        funcionarios_ativos = Funcionario.objects.filter(status='AT').order_by('nome_completo')
        equipes_ativas = equipes.filter(ativo=True).count()
        
        context = {
            'title': 'Equipes de Serviço',
            'description': 'Gestão de equipes e técnicos',
            'equipes': equipes,
            'funcionarios_ativos': funcionarios_ativos,
            'equipes_ativas': equipes_ativas,
        }
        return render(request, 'producao/servicos/equipes.html', context)
    except Exception as e:
        logger.error(f"Erro ao carregar equipes: {e}", exc_info=True)
        messages.error(request, 'Erro ao carregar página de equipes.')
        return redirect('producao:servicos_list')


@login_required
@require_http_methods(["GET", "POST"])
def producao_servico_equipe_edit(request, id):
    """Editar equipe de serviço"""
    equipe = get_object_or_404(EquipeServico, id=id)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                nome = request.POST.get('nome', '').strip()
                descricao = request.POST.get('descricao', '').strip()
                lider_id = request.POST.get('lider', '').strip()
                membros_ids = request.POST.getlist('membros')
                ativo = request.POST.get('ativo') == 'on'
                
                if not nome:
                    messages.error(request, 'Nome da equipe é obrigatório.')
                    return redirect('producao:servico_equipe_edit', id=id)
                
                equipe.nome = nome
                equipe.descricao = descricao if descricao else None
                equipe.lider_id = int(lider_id) if lider_id else None
                equipe.ativo = ativo
                equipe.save()
                
                # Atualizar membros
                if membros_ids:
                    membros = Funcionario.objects.filter(id__in=membros_ids, status='AT')
                    equipe.membros.set(membros)
                else:
                    equipe.membros.clear()
                
                messages.success(request, f'Equipe "{equipe.nome}" atualizada com sucesso!')
                return redirect('producao:servicos_equipes')
        except Exception as e:
            logger.error(f"Erro ao atualizar equipe {id}: {e}", exc_info=True)
            messages.error(request, f'Erro ao atualizar equipe: {str(e)}')
    
    funcionarios_ativos = Funcionario.objects.filter(status='AT').order_by('nome_completo')
    membros_selecionados = equipe.membros.all()
    
    context = {
        'equipe': equipe,
        'funcionarios_ativos': funcionarios_ativos,
        'membros_selecionados': membros_selecionados,
    }
    return render(request, 'producao/servicos/equipes/form.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def producao_servico_equipe_delete(request, id):
    """Excluir equipe de serviço"""
    equipe = get_object_or_404(EquipeServico, id=id)
    
    if request.method == 'POST':
        try:
            nome_equipe = equipe.nome
            equipe.delete()
            messages.success(request, f'Equipe "{nome_equipe}" excluída com sucesso!')
            return redirect('producao:servicos_equipes')
        except Exception as e:
            logger.error(f"Erro ao excluir equipe {id}: {e}", exc_info=True)
            messages.error(request, f'Erro ao excluir equipe: {str(e)}')
            return redirect('producao:servicos_equipes')
    
    # Verificar se a equipe está sendo usada em ordens de serviço
    # Como o campo equipe é CharField, verificamos se o nome da equipe está sendo usado
    ordens_uso = OrdemServico.objects.filter(equipe=equipe.nome).count()
    
    context = {
        'equipe': equipe,
        'ordens_uso': ordens_uso,
    }
    return render(request, 'producao/servicos/equipes/delete.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def producao_servicos_clientes(request):
    """Gestão de clientes"""
    if request.method == 'POST':
        try:
            with transaction.atomic():
                nome = request.POST.get('nome', '').strip()
                email = request.POST.get('email', '').strip()
                telefone = request.POST.get('telefone', '').strip()
                nuit = request.POST.get('nuit', '').strip()
                endereco = request.POST.get('endereco', '').strip()
                cidade = request.POST.get('cidade', '').strip()
                observacoes = request.POST.get('observacoes', '').strip()
                
                if not nome:
                    messages.error(request, 'Nome do cliente é obrigatório.')
                    return redirect('producao:servicos_clientes')
                
                ClienteServico.objects.create(
                    nome=nome,
                    email=email if email else None,
                    telefone=telefone if telefone else None,
                    nuit=nuit if nuit else None,
                    endereco=endereco if endereco else None,
                    cidade=cidade if cidade else None,
                    observacoes=observacoes if observacoes else None,
                    ativo=True
                )
                
                messages.success(request, f'Cliente "{nome}" criado com sucesso!')
                return redirect('producao:servicos_clientes')
        except Exception as e:
            logger.error(f"Erro ao criar cliente: {e}", exc_info=True)
            messages.error(request, f'Erro ao criar cliente: {str(e)}')
    
    # GET - Listar clientes
    try:
        search_query = request.GET.get('q', '').strip()
        clientes = ClienteServico.objects.all()
        
        if search_query:
            clientes = clientes.filter(
                Q(nome__icontains=search_query) |
                Q(email__icontains=search_query) |
                Q(telefone__icontains=search_query) |
                Q(nuit__icontains=search_query) |
                Q(cidade__icontains=search_query)
            )
        
        clientes = clientes.order_by('nome')
        
        # Paginação
        paginator = Paginator(clientes, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        context = {
            'page_obj': page_obj,
            'clientes': page_obj,
            'search_query': search_query or '',
            'total_clientes': ClienteServico.objects.count(),
            'clientes_ativos': ClienteServico.objects.filter(ativo=True).count(),
        }
        return render(request, 'producao/servicos/clientes.html', context)
    except Exception as e:
        logger.error(f"Erro ao listar clientes: {e}", exc_info=True)
        messages.error(request, 'Erro ao carregar lista de clientes.')
        return render(request, 'producao/servicos/clientes.html', {
            'page_obj': None,
            'clientes': [],
            'search_query': '',
            'total_clientes': 0,
            'clientes_ativos': 0,
        })


@login_required
def producao_servico_cliente_detail(request, id):
    """Detalhes do cliente de serviço"""
    try:
        cliente = get_object_or_404(ClienteServico, id=id)
        # Contar ordens do cliente
        total_ordens = cliente.ordens_servico.count()
        ordens_ativas = cliente.ordens_servico.exclude(status__in=['CONCLUIDA', 'CANCELADA']).count()
        
        context = {
            'cliente': cliente,
            'total_ordens': total_ordens,
            'ordens_ativas': ordens_ativas,
        }
        return render(request, 'producao/servicos/clientes/detail.html', context)
    except Exception as e:
        logger.error(f"Erro ao exibir detalhes do cliente {id}: {e}")
        messages.error(request, 'Erro ao carregar detalhes do cliente.')
        return redirect('producao:servicos_clientes')


@login_required
@require_http_methods(["GET", "POST"])
def producao_servico_cliente_edit(request, id):
    """Editar cliente de serviço"""
    cliente = get_object_or_404(ClienteServico, id=id)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                nome = request.POST.get('nome', '').strip()
                email = request.POST.get('email', '').strip()
                telefone = request.POST.get('telefone', '').strip()
                nuit = request.POST.get('nuit', '').strip()
                endereco = request.POST.get('endereco', '').strip()
                cidade = request.POST.get('cidade', '').strip()
                observacoes = request.POST.get('observacoes', '').strip()
                ativo = request.POST.get('ativo') == 'on'
                
                if not nome:
                    messages.error(request, 'Nome do cliente é obrigatório.')
                    return redirect('producao:servico_cliente_edit', id=id)
                
                cliente.nome = nome
                cliente.email = email if email else None
                cliente.telefone = telefone if telefone else None
                cliente.nuit = nuit if nuit else None
                cliente.endereco = endereco if endereco else None
                cliente.cidade = cidade if cidade else None
                cliente.observacoes = observacoes if observacoes else None
                cliente.ativo = ativo
                cliente.save()
                
                messages.success(request, f'Cliente "{cliente.nome}" atualizado com sucesso!')
                return redirect('producao:servico_cliente_detail', id=cliente.id)
        except Exception as e:
            logger.error(f"Erro ao atualizar cliente {id}: {e}", exc_info=True)
            messages.error(request, f'Erro ao atualizar cliente: {str(e)}')
    
    context = {
        'cliente': cliente,
    }
    return render(request, 'producao/servicos/clientes/form.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def producao_servico_cliente_delete(request, id):
    """Excluir cliente de serviço"""
    cliente = get_object_or_404(ClienteServico, id=id)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Verificar se há ordens de serviço associadas
                ordens_count = cliente.ordens_servico.count()
                
                if ordens_count > 0:
                    plural_ordem = 'ns' if ordens_count > 1 else 'm'
                    plural_associada = 's' if ordens_count > 1 else ''
                    messages.error(
                        request, 
                        f'Não é possível excluir este cliente pois ele possui {ordens_count} ordem{plural_ordem} de serviço associada{plural_associada}.'
                    )
                    return redirect('producao:servicos_clientes')
                
                nome_cliente = cliente.nome
                cliente.delete()
                messages.success(request, f'Cliente "{nome_cliente}" excluído com sucesso!')
        except Exception as e:
            logger.error(f"Erro ao excluir cliente {id}: {e}", exc_info=True)
            messages.error(request, f'Erro ao excluir cliente: {str(e)}')
        return redirect('producao:servicos_clientes')
    
    # Verificar dependências
    ordens_count = cliente.ordens_servico.count()
    
    context = {
        'cliente': cliente,
        'ordens_count': ordens_count,
    }
    return render(request, 'producao/servicos/clientes/delete.html', context)


@login_required
def producao_servicos_contratos(request):
    """Gestão de contratos de serviço"""
    try:
        # Filtros
        search_query = request.GET.get('q', '').strip()
        status_filter = request.GET.get('status', '')
        cliente_id = request.GET.get('cliente', '')
        
        # Buscar orçamentos (cotações) que podem ter contratos gerados
        # Contratos são gerados a partir de orçamentos (código começa com 'COT')
        orcamentos = OrdemServico.objects.select_related(
            'cliente', 'responsavel', 'criado_por'
        ).prefetch_related(
            'servicos_orcamento__servico',
            'ordens_servico_geradas'  # Ordens de serviço geradas a partir deste orçamento
        ).filter(
            codigo__startswith='COT'
        ).distinct()
        
        # Aplicar filtros
        if search_query:
            orcamentos = orcamentos.filter(
                Q(codigo__icontains=search_query) |
                Q(cliente__nome__icontains=search_query) |
                Q(endereco_servico__icontains=search_query)
            )
        
        if status_filter:
            orcamentos = orcamentos.filter(status=status_filter)
        
        if cliente_id:
            orcamentos = orcamentos.filter(cliente_id=cliente_id)
        
        # Ordenação
        orcamentos = orcamentos.order_by('-data_criacao', '-data_agendada')
        
        # Paginação
        paginator = Paginator(orcamentos, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Estatísticas - usar annotate para contar de forma eficiente
        total_orcamentos = orcamentos.count()
        orcamentos_com_contrato = orcamentos.annotate(
            num_ordens=Count('ordens_servico_geradas')
        ).filter(num_ordens__gt=0).count()
        orcamentos_sem_contrato = total_orcamentos - orcamentos_com_contrato
        
        # Lista de clientes para filtro
        clientes = ClienteServico.objects.filter(ativo=True).order_by('nome')
        
        context = {
            'title': 'Contratos de Serviço',
            'description': 'Gestão de contratos de serviço',
            'page_obj': page_obj,
            'orcamentos': page_obj,
            'search_query': search_query or '',
            'status_filter': status_filter,
            'cliente_id': cliente_id,
            'total_orcamentos': total_orcamentos,
            'orcamentos_com_contrato': orcamentos_com_contrato,
            'orcamentos_sem_contrato': orcamentos_sem_contrato,
            'clientes': clientes,
            'STATUS_CHOICES': OrdemServico.STATUS_CHOICES,
        }
        return render(request, 'producao/servicos/contratos.html', context)
    except Exception as e:
        logger.error(f"Erro ao carregar contratos: {e}", exc_info=True)
        messages.error(request, 'Erro ao carregar página de contratos.')
        return redirect('producao:servicos_list')


@login_required
def producao_servicos_faturamento(request):
    """Faturamento de serviços"""
    try:
        # Filtros
        search_query = request.GET.get('q', '').strip()
        cliente_id = request.GET.get('cliente', '')
        data_inicio = request.GET.get('data_inicio', '')
        data_fim = request.GET.get('data_fim', '')
        tem_fatura = request.GET.get('tem_fatura', '')
        
        # Buscar ordens de serviço concluídas (código começa com 'OS')
        ordens = OrdemServico.objects.select_related(
            'cliente', 'responsavel', 'criado_por', 'orcamento_origem'
        ).prefetch_related(
            'servicos_orcamento__servico'
        ).filter(
            codigo__startswith='OS',
            status='CONCLUIDA'
        ).distinct()
        
        # Aplicar filtros
        if search_query:
            ordens = ordens.filter(
                Q(codigo__icontains=search_query) |
                Q(cliente__nome__icontains=search_query) |
                Q(nome_cliente_pagamento__icontains=search_query) |
                Q(endereco_servico__icontains=search_query)
            )
        
        if cliente_id:
            ordens = ordens.filter(cliente_id=cliente_id)
        
        if data_inicio:
            try:
                data_inicio_obj = datetime.strptime(data_inicio, '%Y-%m-%d').date()
                ordens = ordens.filter(data_conclusao__date__gte=data_inicio_obj)
            except ValueError:
                pass
        
        if data_fim:
            try:
                data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d').date()
                ordens = ordens.filter(data_conclusao__date__lte=data_fim_obj)
            except ValueError:
                pass
        
        if tem_fatura == 'sim':
            ordens = ordens.filter(numero_impressao_fatura__gt=0)
        elif tem_fatura == 'nao':
            ordens = ordens.filter(Q(numero_impressao_fatura__isnull=True) | Q(numero_impressao_fatura=0))
        
        # Ordenação
        ordens = ordens.order_by('-data_conclusao', '-data_criacao')
        
        # Paginação
        paginator = Paginator(ordens, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Estatísticas
        total_ordens = ordens.count()
        ordens_com_fatura = ordens.filter(numero_impressao_fatura__gt=0).count()
        ordens_sem_fatura = total_ordens - ordens_com_fatura
        
        # Calcular total faturado
        total_faturado = Decimal('0.00')
        for ordem in ordens:
            if ordem.valor_total:
                total_faturado += ordem.valor_total
        
        # Lista de clientes para filtro
        clientes = ClienteServico.objects.filter(ativo=True).order_by('nome')
        
        context = {
            'title': 'Faturamento de Serviços',
            'description': 'Faturamento de serviços prestados',
            'page_obj': page_obj,
            'ordens': page_obj,
            'search_query': search_query or '',
            'cliente_id': cliente_id,
            'data_inicio': data_inicio,
            'data_fim': data_fim,
            'tem_fatura': tem_fatura,
            'total_ordens': total_ordens,
            'ordens_com_fatura': ordens_com_fatura,
            'ordens_sem_fatura': ordens_sem_fatura,
            'total_faturado': total_faturado,
            'clientes': clientes,
        }
        return render(request, 'producao/servicos/faturamento.html', context)
    except Exception as e:
        logger.error(f"Erro ao carregar faturamento: {e}", exc_info=True)
        messages.error(request, 'Erro ao carregar página de faturamento.')
        return redirect('producao:servicos_list')


@login_required
def producao_servicos_relatorios(request):
    """Relatórios de serviços"""
    try:
        from django.db.models import Sum, Count, Avg, Q
        from datetime import datetime, timedelta
        
        # Parâmetros de filtro
        periodo = request.GET.get('periodo', 'mes')  # mes, semana, ano, personalizado
        data_inicio = request.GET.get('data_inicio', '')
        data_fim = request.GET.get('data_fim', '')
        cliente_id = request.GET.get('cliente', '')
        status_filter = request.GET.get('status', '')
        
        # Calcular datas baseado no período
        hoje = timezone.now().date()
        if periodo == 'semana':
            data_inicio_periodo = hoje - timedelta(days=7)
            data_fim_periodo = hoje
        elif periodo == 'mes':
            data_inicio_periodo = hoje.replace(day=1)
            data_fim_periodo = hoje
        elif periodo == 'ano':
            data_inicio_periodo = hoje.replace(month=1, day=1)
            data_fim_periodo = hoje
        elif periodo == 'personalizado' and data_inicio and data_fim:
            try:
                data_inicio_periodo = datetime.strptime(data_inicio, '%Y-%m-%d').date()
                data_fim_periodo = datetime.strptime(data_fim, '%Y-%m-%d').date()
            except ValueError:
                data_inicio_periodo = hoje.replace(day=1)
                data_fim_periodo = hoje
        else:
            data_inicio_periodo = hoje.replace(day=1)
            data_fim_periodo = hoje
        
        # Base de dados - todas as ordens de serviço
        ordens_base = OrdemServico.objects.select_related('cliente', 'responsavel').filter(
            codigo__startswith='OS'
        )
        
        # Aplicar filtros
        if cliente_id:
            ordens_base = ordens_base.filter(cliente_id=cliente_id)
        
        if status_filter:
            ordens_base = ordens_base.filter(status=status_filter)
        
        # Estatísticas gerais
        total_ordens = ordens_base.count()
        ordens_concluidas = ordens_base.filter(status='CONCLUIDA').count()
        ordens_em_andamento = ordens_base.filter(status='EM_ANDAMENTO').count()
        ordens_agendadas = ordens_base.filter(status='AGENDADA').count()
        ordens_canceladas = ordens_base.filter(status='CANCELADA').count()
        
        # Estatísticas financeiras
        ordens_com_valor = ordens_base.filter(valor_total__isnull=False)
        total_faturado = ordens_com_valor.filter(status='CONCLUIDA').aggregate(
            total=Sum('valor_total')
        )['total'] or Decimal('0.00')
        
        total_em_aberto = ordens_com_valor.exclude(status__in=['CONCLUIDA', 'CANCELADA']).aggregate(
            total=Sum('valor_total')
        )['total'] or Decimal('0.00')
        
        # Estatísticas por período
        ordens_periodo = ordens_base.filter(
            data_criacao__date__gte=data_inicio_periodo,
            data_criacao__date__lte=data_fim_periodo
        )
        
        ordens_periodo_concluidas = ordens_periodo.filter(status='CONCLUIDA')
        total_periodo = ordens_periodo_concluidas.aggregate(
            total=Sum('valor_total')
        )['total'] or Decimal('0.00')
        
        quantidade_periodo = ordens_periodo_concluidas.count()
        
        # Estatísticas por cliente
        top_clientes = ordens_base.filter(
            status='CONCLUIDA',
            cliente__isnull=False
        ).values(
            'cliente__nome'
        ).annotate(
            total=Sum('valor_total'),
            quantidade=Count('id')
        ).order_by('-total')[:10]
        
        # Estatísticas por status
        estatisticas_status = ordens_base.values('status').annotate(
            quantidade=Count('id'),
            total=Sum('valor_total')
        ).order_by('status')
        
        # Lista de clientes para filtro
        clientes = ClienteServico.objects.filter(ativo=True).order_by('nome')
        
        context = {
            'title': 'Relatórios de Serviços',
            'description': 'Relatórios e análises de serviços',
            'periodo': periodo,
            'data_inicio': data_inicio or data_inicio_periodo.strftime('%Y-%m-%d'),
            'data_fim': data_fim or data_fim_periodo.strftime('%Y-%m-%d'),
            'data_inicio_periodo': data_inicio_periodo,
            'data_fim_periodo': data_fim_periodo,
            'cliente_id': cliente_id,
            'status_filter': status_filter,
            'total_ordens': total_ordens,
            'ordens_concluidas': ordens_concluidas,
            'ordens_em_andamento': ordens_em_andamento,
            'ordens_agendadas': ordens_agendadas,
            'ordens_canceladas': ordens_canceladas,
            'total_faturado': total_faturado,
            'total_em_aberto': total_em_aberto,
            'total_periodo': total_periodo,
            'quantidade_periodo': quantidade_periodo,
            'top_clientes': top_clientes,
            'estatisticas_status': estatisticas_status,
            'clientes': clientes,
            'STATUS_CHOICES': OrdemServico.STATUS_CHOICES,
        }
        return render(request, 'producao/servicos/relatorios.html', context)
    except Exception as e:
        logger.error(f"Erro ao carregar relatórios: {e}", exc_info=True)
        messages.error(request, 'Erro ao carregar página de relatórios.')
        return redirect('producao:servicos_list')


@login_required
def producao_servicos_relatorios_pdf(request):
    """Gerar PDF do relatório de serviços"""
    try:
        from django.db.models import Sum, Count, Avg, Q, F
        from datetime import datetime, timedelta
        from django.template.loader import render_to_string
        from meuprojeto.empresa.views import render_pdf_from_html_string
        
        # Parâmetros de filtro (mesmos da view principal)
        periodo = request.GET.get('periodo', 'mes')
        data_inicio = request.GET.get('data_inicio', '')
        data_fim = request.GET.get('data_fim', '')
        cliente_id = request.GET.get('cliente', '')
        status_filter = request.GET.get('status', '')
        
        # Calcular datas baseado no período
        hoje = timezone.now().date()
        if periodo == 'semana':
            data_inicio_periodo = hoje - timedelta(days=7)
            data_fim_periodo = hoje
        elif periodo == 'mes':
            data_inicio_periodo = hoje.replace(day=1)
            data_fim_periodo = hoje
        elif periodo == 'ano':
            data_inicio_periodo = hoje.replace(month=1, day=1)
            data_fim_periodo = hoje
        elif periodo == 'personalizado' and data_inicio and data_fim:
            try:
                data_inicio_periodo = datetime.strptime(data_inicio, '%Y-%m-%d').date()
                data_fim_periodo = datetime.strptime(data_fim, '%Y-%m-%d').date()
            except ValueError:
                data_inicio_periodo = hoje.replace(day=1)
                data_fim_periodo = hoje
        else:
            data_inicio_periodo = hoje.replace(day=1)
            data_fim_periodo = hoje
        
        # Base de dados - todas as ordens de serviço
        ordens_base = OrdemServico.objects.select_related('cliente', 'responsavel').filter(
            codigo__startswith='OS'
        )
        
        # Aplicar filtros
        if cliente_id:
            ordens_base = ordens_base.filter(cliente_id=cliente_id)
        
        if status_filter:
            ordens_base = ordens_base.filter(status=status_filter)
        
        # Estatísticas gerais
        total_ordens = ordens_base.count()
        ordens_concluidas = ordens_base.filter(status='CONCLUIDA').count()
        ordens_em_andamento = ordens_base.filter(status='EM_ANDAMENTO').count()
        ordens_agendadas = ordens_base.filter(status='AGENDADA').count()
        ordens_canceladas = ordens_base.filter(status='CANCELADA').count()
        
        # Estatísticas financeiras
        ordens_com_valor = ordens_base.filter(valor_total__isnull=False)
        total_faturado = ordens_com_valor.filter(status='CONCLUIDA').aggregate(
            total=Sum('valor_total')
        )['total'] or Decimal('0.00')
        
        total_em_aberto = ordens_com_valor.exclude(status__in=['CONCLUIDA', 'CANCELADA']).aggregate(
            total=Sum('valor_total')
        )['total'] or Decimal('0.00')
        
        # Estatísticas por período
        ordens_periodo = ordens_base.filter(
            data_criacao__date__gte=data_inicio_periodo,
            data_criacao__date__lte=data_fim_periodo
        )
        
        ordens_periodo_concluidas = ordens_periodo.filter(status='CONCLUIDA')
        total_periodo = ordens_periodo_concluidas.aggregate(
            total=Sum('valor_total')
        )['total'] or Decimal('0.00')
        
        quantidade_periodo = ordens_periodo_concluidas.count()
        
        # Estatísticas por cliente
        top_clientes = ordens_base.filter(
            status='CONCLUIDA',
            cliente__isnull=False
        ).values(
            'cliente__nome'
        ).annotate(
            total=Sum('valor_total'),
            quantidade=Count('id')
        ).order_by('-total')[:10]
        
        # Estatísticas por status
        estatisticas_status = ordens_base.values('status').annotate(
            quantidade=Count('id'),
            total=Sum('valor_total')
        ).order_by('status')
        
        # Lista completa de ordens do período (sem limite)
        ordens_detalhadas = ordens_periodo.select_related(
            'cliente', 'responsavel', 'criado_por'
        ).prefetch_related(
            'servicos_orcamento__servico',
            'servicos_orcamento__itens__item',
            'transportes_orcamento__transportadora'
        ).order_by('-data_criacao')
        
        # Estatísticas por equipe (equipe é CharField, não ForeignKey)
        estatisticas_equipe = ordens_periodo.filter(
            equipe__isnull=False
        ).exclude(equipe='').values(
            'equipe'
        ).annotate(
            quantidade=Count('id'),
            total=Sum('valor_total')
        ).order_by('-quantidade')
        
        # Estatísticas por responsável
        estatisticas_responsavel = ordens_periodo.filter(
            responsavel__isnull=False
        ).values(
            'responsavel__first_name',
            'responsavel__last_name',
            'responsavel__username'
        ).annotate(
            quantidade=Count('id'),
            total=Sum('valor_total')
        ).order_by('-quantidade')[:10]
        
        # Análise de performance diária
        from django.db.models.functions import TruncDate
        performance_diaria = ordens_periodo_concluidas.annotate(
            data=TruncDate('data_conclusao')
        ).values('data').annotate(
            quantidade=Count('id'),
            total=Sum('valor_total')
        ).order_by('data')
        
        # Tempo médio por status
        tempo_por_status = {}
        for status_code, status_name in OrdemServico.STATUS_CHOICES:
            ordens_status = ordens_periodo.filter(status=status_code)
            if ordens_status.exists():
                tempos = []
                for ordem in ordens_status[:100]:  # Limitar para performance
                    if ordem.data_criacao and ordem.data_conclusao:
                        delta = ordem.data_conclusao.date() - ordem.data_criacao.date()
                        tempos.append(delta.days)
                if tempos:
                    tempo_por_status[status_code] = {
                        'nome': status_name,
                        'tempo_medio': sum(tempos) / len(tempos),
                        'quantidade': len(tempos)
                    }
        
        # Análise de cancelamentos (usando observacoes como motivo, se disponível)
        ordens_canceladas_detalhes = ordens_periodo.filter(status='CANCELADA').count()
        motivo_cancelamento_mais_comum = ordens_periodo.filter(
            status='CANCELADA',
            observacoes__isnull=False
        ).exclude(observacoes='').values('observacoes').annotate(
            quantidade=Count('id')
        ).order_by('-quantidade')[:5]
        
        # Estatísticas por mês (últimos 6 meses)
        from django.db.models.functions import TruncMonth
        ordens_por_mes = ordens_base.filter(
            data_criacao__date__gte=data_inicio_periodo,
            data_criacao__date__lte=data_fim_periodo,
            status='CONCLUIDA'
        ).annotate(
            mes=TruncMonth('data_criacao')
        ).values('mes').annotate(
            quantidade=Count('id'),
            total=Sum('valor_total')
        ).order_by('mes')[:12]
        
        # Serviços mais utilizados (através de ServicoOrcamentoServico)
        from .models_stock import ServicoOrcamentoServico
        from django.db.models import ExpressionWrapper, DecimalField
        
        # Calcular valor total usando ExpressionWrapper
        servicos_mais_utilizados = ServicoOrcamentoServico.objects.filter(
            ordem_servico__codigo__startswith='OS',
            ordem_servico__status='CONCLUIDA',
            ordem_servico__data_criacao__date__gte=data_inicio_periodo,
            ordem_servico__data_criacao__date__lte=data_fim_periodo
        ).annotate(
            valor_calculado=ExpressionWrapper(
                (F('quantidade') * F('valor_unitario')) - F('desconto'),
                output_field=DecimalField(max_digits=10, decimal_places=2)
            )
        ).values(
            'servico__nome'
        ).annotate(
            quantidade=Count('id'),
            total=Sum('valor_calculado')
        ).order_by('-quantidade')[:10]
        
        # Média de valor por ordem
        media_valor_ordem = ordens_periodo_concluidas.aggregate(
            media=Avg('valor_total')
        )['media'] or Decimal('0.00')
        
        # Tempo médio de conclusão (em dias)
        ordens_com_tempo = ordens_periodo_concluidas.filter(
            data_criacao__isnull=False,
            data_conclusao__isnull=False
        )
        tempo_medio = None
        if ordens_com_tempo.exists():
            from django.db.models import F, ExpressionWrapper, DurationField
            tempos = []
            for ordem in ordens_com_tempo[:100]:  # Limitar para performance
                if ordem.data_criacao and ordem.data_conclusao:
                    delta = ordem.data_conclusao.date() - ordem.data_criacao.date()
                    tempos.append(delta.days)
            if tempos:
                tempo_medio = sum(tempos) / len(tempos)
        
        # Obter dados da empresa
        from .models_base import DadosEmpresa
        try:
            dados_empresa = DadosEmpresa.objects.first()
        except:
            dados_empresa = None
        
        # Contexto para o template PDF
        context = {
            'title': 'Relatório de Serviços',
            'periodo': periodo,
            'data_inicio_periodo': data_inicio_periodo,
            'data_fim_periodo': data_fim_periodo,
            'cliente_id': cliente_id,
            'status_filter': status_filter,
            'total_ordens': total_ordens,
            'ordens_concluidas': ordens_concluidas,
            'ordens_em_andamento': ordens_em_andamento,
            'ordens_agendadas': ordens_agendadas,
            'ordens_canceladas': ordens_canceladas,
            'total_faturado': total_faturado,
            'total_em_aberto': total_em_aberto,
            'total_periodo': total_periodo,
            'quantidade_periodo': quantidade_periodo,
            'top_clientes': top_clientes,
            'estatisticas_status': estatisticas_status,
            'ordens_detalhadas': ordens_detalhadas,
            'ordens_por_mes': ordens_por_mes,
            'servicos_mais_utilizados': servicos_mais_utilizados,
            'media_valor_ordem': media_valor_ordem,
            'tempo_medio': tempo_medio,
            'estatisticas_equipe': estatisticas_equipe,
            'estatisticas_responsavel': estatisticas_responsavel,
            'performance_diaria': performance_diaria,
            'tempo_por_status': tempo_por_status,
            'motivo_cancelamento_mais_comum': motivo_cancelamento_mais_comum,
            'STATUS_CHOICES': OrdemServico.STATUS_CHOICES,
            'dados_empresa': dados_empresa,
            'data_relatorio': timezone.now(),
        }
        
        # Renderizar template PDF
        html_string = render_to_string('producao/servicos/relatorios_documento.html', context, request=request)
        filename = f'relatorio_servicos_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
        return render_pdf_from_html_string(request, html_string, filename)
        
    except Exception as e:
        logger.error(f"Erro ao gerar PDF do relatório: {e}", exc_info=True)
        messages.error(request, f'Erro ao gerar PDF: {str(e)}')
        return redirect('producao:servicos_relatorios')


@login_required
@require_http_methods(["GET", "POST"])
def producao_servico_add(request):
    """Adicionar novo serviço"""
    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        codigo = request.POST.get('codigo', '').strip()
        descricao = request.POST.get('descricao', '').strip()
        categoria_id = request.POST.get('categoria')
        unidade_medida = request.POST.get('unidade_medida')
        preco_custo = request.POST.get('preco_custo')
        preco_venda = request.POST.get('preco_venda')
        status = request.POST.get('status', 'ATIVO')
        observacoes = request.POST.get('observacoes', '').strip()
        
        # Validação - apenas nome e preço de venda são obrigatórios
        if not nome:
            messages.error(request, 'O nome do serviço é obrigatório.')
            return redirect('producao:servico_add')
        
        if not preco_venda or Decimal(preco_venda) <= 0:
            messages.error(request, 'O preço de venda é obrigatório e deve ser maior que zero.')
            return redirect('producao:servico_add')
        
        # Definir valores padrão
        if not unidade_medida:
            unidade_medida = 'UN'  # Unidade padrão
        
        if not preco_custo:
            preco_custo = '0.00'
        
        # Se categoria não fornecida, buscar ou criar categoria padrão para serviços
        if not categoria_id:
            from .models_stock import CategoriaProduto
            try:
                # Tentar encontrar categoria padrão para serviços
                categoria_padrao = CategoriaProduto.objects.filter(
                    Q(tipo='SERVICO') | Q(tipo='TODOS'),
                    ativa=True
                ).first()
                
                if not categoria_padrao:
                    # Criar categoria padrão se não existir
                    categoria_padrao = CategoriaProduto.objects.create(
                        nome='Serviços Gerais',
                        codigo='SERV_GERAL',
                        tipo='SERVICO',
                        ativa=True
                    )
                
                categoria_id = categoria_padrao.id
            except Exception as e:
                logger.warning(f"Erro ao buscar/criar categoria padrão: {e}")
                # Se falhar, buscar qualquer categoria ativa
                categoria_padrao = CategoriaProduto.objects.filter(ativa=True).first()
                if categoria_padrao:
                    categoria_id = categoria_padrao.id
                else:
                    messages.error(request, 'Não foi possível criar o serviço. Configure pelo menos uma categoria no sistema.')
                    return redirect('producao:servico_add')
        
        if len(nome) > 200:
            messages.error(request, 'Nome deve ter no máximo 200 caracteres.')
            return redirect('producao:servico_add')
        
        try:
            with transaction.atomic():
                # Se não houver código, deixar vazio para o modelo gerar (prefixo + número sequencial)
                # Ex.: "Instalação" → INST ou INST01, "Manutenção Preventiva" → MANP ou MANP01
                if not codigo:
                    codigo = ''
                
                servico = Item(
                    nome=nome,
                    codigo=codigo,
                    descricao=descricao,
                    categoria_id=categoria_id if categoria_id else None,
                    tipo='PRODUTO',  # Item do tipo PRODUTO
                    produto_tipo='SERVICO',  # Mas com produto_tipo='SERVICO'
                    unidade_medida=unidade_medida,
                    preco_custo=Decimal(preco_custo),
                    preco_venda=Decimal(preco_venda),
                    estoque_minimo=0,  # Serviços não têm estoque
                    estoque_maximo=0,  # Serviços não têm estoque
                    status=status,
                    observacoes=observacoes
                )
                servico.save()
                messages.success(request, 'Serviço adicionado com sucesso.')
                return redirect('producao:servicos_list')
        except Exception as e:
            logger.error(f"Erro ao adicionar serviço: {e}", exc_info=True)
            messages.error(request, f'Erro ao adicionar serviço: {str(e)}')
    
    from .models_stock import CategoriaProduto
    context = {
        'servico': None,
        'preco_venda_val': '0.00',
        'preco_custo_val': '0.00',
        'categorias': CategoriaProduto.objects.filter(ativa=True).filter(
            Q(tipo='SERVICO') | Q(tipo='TODOS')
        ),
        'unidades': Item.UNIDADE_CHOICES,
        'status_choices': Item.STATUS_CHOICES,
    }
    return render(request, 'producao/servicos/form.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def producao_servico_edit(request, id):
    """Editar serviço"""
    servico = get_object_or_404(Item, id=id, tipo='PRODUTO', produto_tipo='SERVICO')
    
    if request.method == 'POST':
        servico.nome = request.POST.get('nome', '').strip()
        servico.descricao = request.POST.get('descricao', '').strip()
        servico.categoria_id = request.POST.get('categoria')
        servico.unidade_medida = request.POST.get('unidade_medida')
        _preco_custo = request.POST.get('preco_custo', '0') or '0'
        _preco_venda = request.POST.get('preco_venda', '0') or '0'
        servico.preco_custo = Decimal(str(_preco_custo).replace(',', '.'))
        servico.preco_venda = Decimal(str(_preco_venda).replace(',', '.'))
        servico.status = request.POST.get('status', 'ATIVO')
        servico.observacoes = request.POST.get('observacoes', '').strip()
        
        try:
            servico.save()
            messages.success(request, 'Serviço atualizado com sucesso.')
            return redirect('producao:servicos_list')
        except Exception as e:
            logger.error(f"Erro ao atualizar serviço: {e}", exc_info=True)
            messages.error(request, f'Erro ao atualizar serviço: {str(e)}')
    
    from .models_stock import CategoriaProduto
    # Formatar preços para o formulário (sempre com ponto como separador decimal)
    preco_venda_val = servico.preco_venda if servico.preco_venda is not None else Decimal('0')
    preco_custo_val = servico.preco_custo if servico.preco_custo is not None else Decimal('0')
    context = {
        'servico': servico,
        'preco_venda_val': f'{float(preco_venda_val):.2f}',
        'preco_custo_val': f'{float(preco_custo_val):.2f}',
        'categorias': CategoriaProduto.objects.filter(ativa=True).filter(
            Q(tipo='SERVICO') | Q(tipo='TODOS')
        ),
        'unidades': Item.UNIDADE_CHOICES,
        'status_choices': Item.STATUS_CHOICES,
    }
    return render(request, 'producao/servicos/form.html', context)


@login_required
def producao_servico_detail(request, id):
    """Detalhes do serviço"""
    servico = get_object_or_404(Item, id=id, tipo='PRODUTO', produto_tipo='SERVICO')
    
    context = {
        'servico': servico,
    }
    return render(request, 'producao/servicos/detail.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def producao_servico_delete(request, id):
    """Excluir serviço"""
    servico = get_object_or_404(Item, id=id, tipo='PRODUTO', produto_tipo='SERVICO')
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Verificar se há ordens de serviço usando este serviço
                # TODO: Quando o modelo OrdemServico for criado, adicionar verificação aqui
                # ordens_count = OrdemServico.objects.filter(servico=servico).count()
                # if ordens_count > 0:
                #     messages.error(request, f'Não é possível excluir este serviço pois ele está sendo usado por {ordens_count} ordem(ns) de serviço.')
                #     return redirect('producao:servicos_list')
                
                # Verificar se há movimentos de stock (improvável para serviços, mas verificar)
                # Serviços não têm stock, mas verificar se há alguma referência
                try:
                    movimentos_count = servico.movimentos.count()
                    
                    if movimentos_count > 0:
                        messages.error(
                            request, 
                            f'Não é possível excluir este serviço pois ele possui {movimentos_count} movimentação(ões) registrada(s).'
                        )
                        return redirect('producao:servicos_list')
                except:
                    pass  # Se não houver relacionamento, continuar
                
                nome_servico = servico.nome
                servico.delete()
                messages.success(request, f'Serviço "{nome_servico}" excluído com sucesso.')
        except Exception as e:
            logger.error(f"Erro ao excluir serviço {id}: {e}", exc_info=True)
            messages.error(request, f'Erro ao excluir serviço: {str(e)}')
        return redirect('producao:servicos_list')
    
    context = {
        'servico': servico,
    }
    return render(request, 'producao/servicos/delete.html', context)


@login_required
def editar_contrato_servico(request, orcamento_id, from_vendas=False):
    """
    Permite ao utilizador editar as cláusulas do contrato antes da confirmação.
    Após a confirmação, a edição fica bloqueada.
    from_vendas: quando True, usa URLs de Vendas para redirects e form.
    """
    from .models_base import ConfiguracaoContratoServico
    
    orcamento = get_object_or_404(
        OrdemServico.objects.select_related('cliente', 'responsavel', 'criado_por')
                               .prefetch_related('servicos_orcamento__servico', 'transportes_orcamento__transportadora', 'parcelas_pagamento__servicos'), 
        id=orcamento_id
    )
    
    # Verificar se o orçamento já foi confirmado (se existe ordem de serviço criada a partir dele)
    ordem_confirmada = OrdemServico.objects.filter(
        codigo__startswith='OS',
        orcamento_origem=orcamento
    ).first()
    
    if ordem_confirmada:
        messages.error(request, f'Este orçamento já foi confirmado e convertido na ordem de serviço {ordem_confirmada.codigo}. A edição do contrato não é mais permitida.')
        if from_vendas:
            return redirect('vendas:pedido_detail', id=ordem_confirmada.id)
        return redirect('producao:servico_ordem_detail', id=ordem_confirmada.id)
    
    # Carregar configuração padrão para preencher campos vazios
    config_padrao = ConfiguracaoContratoServico.objects.filter(ativo=True).order_by('-padrao', '-data_atualizacao').first()
    
    if request.method == 'POST':
        try:
            from .models_stock import ParcelaPagamentoOrcamento
            from .parcelas_vendas_utils import ordem_e_so_servicos, percentagem_minima_valor_servicos_cotacao
            mostrar_parcelas = ordem_e_so_servicos(orcamento)
            parcela_count = request.POST.get('parcela_count')
            try:
                parcela_count = int(parcela_count) if parcela_count else 0
            except (ValueError, TypeError):
                parcela_count = 0
            ids_servicos_orc = set(s.id for s in orcamento.servicos_orcamento.all())
            parcelas_ok = []
            if mostrar_parcelas and parcela_count > 0 and parcela_count <= 12:
                for i in range(parcela_count):
                    try:
                        pct = int(request.POST.get(f'parcela_{i}_percentagem') or 0)
                        tipo = (request.POST.get(f'parcela_{i}_tipo') or ParcelaPagamentoOrcamento.TIPO_CONCLUSAO_TOTAL)[:24]
                        servicos_ids = [int(x) for x in request.POST.getlist(f'parcela_{i}_servicos') if x.isdigit()]
                        servicos_ids = [sid for sid in servicos_ids if sid in ids_servicos_orc]
                        parcelas_ok.append((i + 1, pct, tipo, servicos_ids))
                    except (ValueError, TypeError):
                        continue

            def _render_post_com_mensagem():
                """
                Re-renderiza o template com os valores do POST (sem gravar), para que o utilizador
                veja a validação e não perca alterações por redirect.
                """
                # Aplicar campos simples ao objecto em memória (apenas para preencher o form)
                try:
                    orcamento.prazo_execucao_numero = int(request.POST.get('prazo_execucao_numero') or orcamento.prazo_execucao_numero or 30)
                except (ValueError, TypeError):
                    pass
                orcamento.prazo_execucao_unidade = (request.POST.get('prazo_execucao_unidade') or orcamento.prazo_execucao_unidade or 'MESES')[:10]
                modo_fins = (request.POST.get('prazo_fins_semana_modo') or '').strip()[:20]
                orcamento.prazo_fins_semana_modo = modo_fins if modo_fins in ('SABADO_DOMINGO', 'SO_DOMINGO', 'SABADO_MEIO', 'CORRIDOS') else None
                orcamento.prazo_excluir_feriados = request.POST.get('prazo_excluir_feriados') == '1'
                orcamento.incluir_clausula_suspensao_clima = request.POST.get('incluir_clausula_suspensao_clima') == '1'
                orcamento.clausula_suspensao_clima = request.POST.get('clausula_suspensao_clima', '').strip() or None

                # Montar "parcelas" de forma compatível com o template
                servicos_orcamento = list(orcamento.servicos_orcamento.select_related('servico').all())
                mapa_servicos = {s.id: s for s in servicos_orcamento}

                class _FakeServicos:
                    def __init__(self, itens):
                        self._itens = itens
                    def all(self):
                        return self._itens

                class _FakeParcela:
                    def __init__(self, numero_ordem, percentagem, tipo, servicos):
                        self.numero_ordem = numero_ordem
                        self.percentagem = percentagem
                        self.tipo = tipo
                        self.servicos = _FakeServicos(servicos)

                parcelas_ctx = []
                if mostrar_parcelas and parcelas_ok:
                    for numero_ordem, pct, tipo, servicos_ids in parcelas_ok:
                        servs = [mapa_servicos[sid] for sid in servicos_ids if sid in mapa_servicos]
                        parcelas_ctx.append(_FakeParcela(numero_ordem, pct, tipo, servs))

                # JSON (inclui valor_total para cálculo em tempo real)
                import json as _json
                servicos_orcamento_json = _json.dumps([
                    {
                        'id': s.id,
                        'nome': s.nome_para_documento or (s.servico.nome if s.servico else ''),
                        'valor_total': float(s.valor_total or 0),
                    }
                    for s in servicos_orcamento
                ])
                valor_total_contrato_json = _json.dumps(float(orcamento.valor_total or 0))
                _pm = percentagem_minima_valor_servicos_cotacao(orcamento, None)
                percentagem_min_conclusao_trabalhos = _pm if _pm > 0 else None

                from django.urls import reverse
                context = {
                    'orcamento': orcamento,
                    'mostrar_parcelas': mostrar_parcelas,
                    'percentagem_min_conclusao_trabalhos': percentagem_min_conclusao_trabalhos,
                    'parcelas': parcelas_ctx or list(orcamento.parcelas_pagamento.order_by('numero_ordem')),
                    'servicos_orcamento': servicos_orcamento,
                    'servicos_orcamento_json': servicos_orcamento_json,
                    'valor_total_contrato_json': valor_total_contrato_json,
                    'obrigacao_contratada_1': request.POST.get('obrigacao_contratada_1', '') or getattr(orcamento, 'obrigacao_contratada_1', ''),
                    'obrigacao_contratada_2': request.POST.get('obrigacao_contratada_2', '') or getattr(orcamento, 'obrigacao_contratada_2', ''),
                    'obrigacao_contratada_3': request.POST.get('obrigacao_contratada_3', '') or getattr(orcamento, 'obrigacao_contratada_3', ''),
                    'obrigacao_contratante_1': request.POST.get('obrigacao_contratante_1', '') or getattr(orcamento, 'obrigacao_contratante_1', ''),
                    'obrigacao_contratante_2': request.POST.get('obrigacao_contratante_2', '') or getattr(orcamento, 'obrigacao_contratante_2', ''),
                    'obrigacao_contratante_3': request.POST.get('obrigacao_contratante_3', '') or getattr(orcamento, 'obrigacao_contratante_3', ''),
                    'validade_garantia_dias': orcamento.validade_garantia_dias if orcamento.validade_garantia_dias else 90,
                    'textos_padrao': config_padrao.to_dict() if config_padrao and hasattr(config_padrao, 'to_dict') else {},
                    'forma_pagamento': orcamento.forma_pagamento_configurada,
                    'garantia_valor': getattr(orcamento, 'validade_garantia_dias', None) or 90,
                    'from_vendas': from_vendas,
                    'url_form_action': reverse('vendas:editar_contrato', args=[orcamento_id]) if from_vendas else reverse('producao:editar_contrato_servico', args=[orcamento_id]),
                    'url_voltar': reverse('vendas:orcamento_detail', args=[orcamento_id]) if from_vendas else reverse('producao:servico_orcamento_detail', args=[orcamento_id]),
                }
                return render(request, 'producao/servicos/orcamento/editar_contrato.html', context)

            # Valor mínimo na conclusão dos trabalhos = valor dos serviços cotados (proporção no total do contrato)
            if mostrar_parcelas and parcelas_ok and sum(p[1] for p in parcelas_ok) == 100:
                # Nota: este "mínimo" é apenas AVISO (não bloqueia). Também considera adiantamentos
                # (parcelas à assinatura) para não exigir 100% na conclusão total.
                pct_assinatura_total = sum(p[1] for p in parcelas_ok if p[2] == ParcelaPagamentoOrcamento.TIPO_ASSINATURA)
                for numero_ordem, pct, tipo, servicos_ids in parcelas_ok:
                    if tipo == ParcelaPagamentoOrcamento.TIPO_CONCLUSAO_SERVICOS:
                        min_p = percentagem_minima_valor_servicos_cotacao(
                            orcamento, servicos_ids if servicos_ids else None
                        )
                        min_ajustado = max(0, min_p - pct_assinatura_total)
                        if min_ajustado > 0 and pct < min_ajustado:
                            messages.warning(
                                request,
                                f'Aviso — Parcela {numero_ordem} (conclusão dos serviços seleccionados): '
                                f'para cobrir o valor cotado dos serviços seleccionados, recomenda-se pelo menos '
                                f'{min_ajustado}% (já considerando {pct_assinatura_total}% de adiantamento à assinatura).'
                            )
                    elif tipo == ParcelaPagamentoOrcamento.TIPO_CONCLUSAO_TOTAL:
                        min_p = percentagem_minima_valor_servicos_cotacao(orcamento, None)
                        min_ajustado = max(0, min_p - pct_assinatura_total)
                        if min_ajustado > 0 and pct < min_ajustado:
                            messages.warning(
                                request,
                                f'Aviso — Parcela {numero_ordem} (conclusão total): '
                                f'para cobrir o valor cotado dos serviços, recomenda-se pelo menos {min_ajustado}% '
                                f'(já considerando {pct_assinatura_total}% de adiantamento à assinatura).'
                            )
            elif not mostrar_parcelas:
                try:
                    p_ass_chk = int(request.POST.get('pagamento_percentagem_assinatura') or 50)
                    p_conc_chk = int(request.POST.get('pagamento_percentagem_conclusao') or 50)
                except (ValueError, TypeError):
                    p_ass_chk, p_conc_chk = 50, 50
                if p_ass_chk + p_conc_chk == 100:
                    min_p = percentagem_minima_valor_servicos_cotacao(orcamento, None)
                    min_ajustado = max(0, min_p - p_ass_chk)
                    if min_ajustado > 0 and p_conc_chk < min_ajustado:
                        messages.warning(
                            request,
                            f'Aviso — a percentagem na conclusão dos trabalhos está abaixo do recomendado '
                            f'({min_ajustado}%), considerando {p_ass_chk}% à assinatura. '
                            f'O valor desta parcela pode não cobrir o valor cotado dos serviços.'
                        )

            with transaction.atomic():
                # Condições de pagamento: parcelas só para orçamentos de SERVIÇOS (não para vendas de produtos)
                if mostrar_parcelas and parcelas_ok and sum(p[1] for p in parcelas_ok) == 100:
                    orcamento.parcelas_pagamento.all().delete()
                    for numero_ordem, pct, tipo, servicos_ids in parcelas_ok:
                        parcela = ParcelaPagamentoOrcamento.objects.create(
                            ordem_servico=orcamento,
                            numero_ordem=numero_ordem,
                            percentagem=pct,
                            tipo=tipo
                        )
                        if servicos_ids and tipo == ParcelaPagamentoOrcamento.TIPO_CONCLUSAO_SERVICOS:
                            parcela.servicos.set(servicos_ids)
                    orcamento.pagamento_percentagem_assinatura = None
                    orcamento.pagamento_percentagem_conclusao = None
                else:
                    if not mostrar_parcelas:
                        orcamento.parcelas_pagamento.all().delete()
                    try:
                        p_ass = int(request.POST.get('pagamento_percentagem_assinatura') or 50)
                        p_conc = int(request.POST.get('pagamento_percentagem_conclusao') or 50)
                    except (ValueError, TypeError):
                        p_ass, p_conc = 50, 50
                    if p_ass + p_conc != 100:
                        p_ass, p_conc = 50, 50
                    orcamento.pagamento_percentagem_assinatura = p_ass
                    orcamento.pagamento_percentagem_conclusao = p_conc
                # Prazo de execução estruturado (formulário)
                try:
                    orcamento.prazo_execucao_numero = int(request.POST.get('prazo_execucao_numero') or 30)
                except (ValueError, TypeError):
                    orcamento.prazo_execucao_numero = 30
                orcamento.prazo_execucao_unidade = (request.POST.get('prazo_execucao_unidade') or 'MESES')[:10]
                modo_fins = (request.POST.get('prazo_fins_semana_modo') or '').strip()[:20]
                orcamento.prazo_fins_semana_modo = modo_fins if modo_fins in ('SABADO_DOMINGO', 'SO_DOMINGO', 'SABADO_MEIO', 'CORRIDOS') else None
                orcamento.prazo_excluir_fins_semana = (modo_fins == 'SABADO_DOMINGO' or not modo_fins)
                orcamento.prazo_excluir_feriados = request.POST.get('prazo_excluir_feriados') == '1'
                orcamento.incluir_clausula_suspensao_clima = request.POST.get('incluir_clausula_suspensao_clima') == '1'
                orcamento.clausula_suspensao_clima = request.POST.get('clausula_suspensao_clima', '').strip() or None
                # Garantia estruturada: valor + unidade -> validade_garantia_dias
                try:
                    garantia_valor = int(request.POST.get('validade_garantia_valor') or 90)
                except (ValueError, TypeError):
                    garantia_valor = 90
                garantia_uni = request.POST.get('validade_garantia_unidade') or 'DIAS'
                if garantia_uni == 'MESES':
                    orcamento.validade_garantia_dias = max(1, garantia_valor * 30)
                elif garantia_uni == 'ANOS':
                    orcamento.validade_garantia_dias = max(1, garantia_valor * 365)
                else:
                    orcamento.validade_garantia_dias = max(1, garantia_valor)
                orcamento.validade_garantia_unidade = garantia_uni[:10]
                # Cláusulas editáveis (texto livre; cláusula 4 usa obrigações pré-definidas editáveis)
                orcamento.clausula3_prazo = request.POST.get('clausula3_prazo', '').strip() or None
                orcamento.obrigacao_contratada_1 = request.POST.get('obrigacao_contratada_1', '').strip() or None
                orcamento.obrigacao_contratada_2 = request.POST.get('obrigacao_contratada_2', '').strip() or None
                orcamento.obrigacao_contratada_3 = request.POST.get('obrigacao_contratada_3', '').strip() or None
                orcamento.obrigacao_contratante_1 = request.POST.get('obrigacao_contratante_1', '').strip() or None
                orcamento.obrigacao_contratante_2 = request.POST.get('obrigacao_contratante_2', '').strip() or None
                orcamento.obrigacao_contratante_3 = request.POST.get('obrigacao_contratante_3', '').strip() or None
                orcamento.clausula5_garantia = request.POST.get('clausula5_garantia', '').strip() or None
                orcamento.clausula6_alteracoes = request.POST.get('clausula6_alteracoes', '').strip() or None
                orcamento.clausula7_rescisao = request.POST.get('clausula7_rescisao', '').strip() or None
                orcamento.clausula8_confidencialidade = request.POST.get('clausula8_confidencialidade', '').strip() or None
                orcamento.clausula9_foro = request.POST.get('clausula9_foro', '').strip() or None
                orcamento.save()
            messages.success(request, 'Cláusulas do contrato atualizadas com sucesso!')
            
            # Redirecionar conforme ação escolhida
            acao = request.POST.get('acao', 'salvar')
            if from_vendas:
                if acao == 'preview':
                    return redirect('vendas:preview_contrato', orcamento_id=orcamento_id)
                elif acao == 'confirmar':
                    return redirect('vendas:cotacao_confirmar', id=orcamento_id)
                else:
                    return redirect('vendas:orcamento_detail', id=orcamento_id)
            else:
                if acao == 'preview':
                    return redirect('producao:preview_contrato_servico', orcamento_id=orcamento_id)
                elif acao == 'confirmar':
                    return redirect('producao:servico_orcamento_confirmar', id=orcamento_id)
                else:
                    return redirect('producao:servico_orcamento_detail', id=orcamento_id)
                
        except Exception as e:
            logger.error(f"Erro ao salvar cláusulas do contrato: {str(e)}", exc_info=True)
            messages.error(request, f'Erro ao salvar cláusulas: {str(e)}')
    
    # Textos padrão hardcoded (obrigações e demais cláusulas) para garantir que
    # apareçam na edição mesmo sem ConfiguracaoContratoServico ou com campos vazios
    DEFAULT_CLAUSULA4_OBRIGACOES = (
        '<p><strong>Da CONTRATADA:</strong></p>'
        '<ol type="a" style="margin-left: 20px; margin-bottom: 8px; font-size: 10px; line-height: 1.5;">'
        '<li style="margin: 4px 0;">Executar os serviços com rigor técnico, segurança e qualidade;</li>'
        '<li style="margin: 4px 0;">Providenciar mão-de-obra e equipamentos necessários;</li>'
        '<li style="margin: 4px 0;">Cumprir normas de higiene e segurança no trabalho.</li>'
        '</ol>'
        '<p><strong>Do CONTRATANTE:</strong></p>'
        '<ol type="a" style="margin-left: 20px; font-size: 10px; line-height: 1.5;">'
        '<li style="margin: 4px 0;">Facilitar acesso ao local dos trabalhos;</li>'
        '<li style="margin: 4px 0;">Prestar as informações necessárias;</li>'
        '<li style="margin: 4px 0;">Cumprir os pagamentos dentro dos prazos acordados.</li>'
        '</ol>'
    )
    DEFAULT_CLAUSULA5_GARANTIA = (
        '<p>Os serviços executados têm uma garantia de {{ validade_garantia_dias }} dias '
        'contra defeitos decorrentes da execução, contados da data de conclusão dos serviços.</p>'
    )
    DEFAULT_CLAUSULA6_ALTERACOES = (
        '<p>Qualquer alteração nas condições deste contrato só produzirá efeitos se formalizada por escrito e '
        'assinada por ambas as partes.</p>'
    )
    DEFAULT_CLAUSULA7_RESCISAO = (
        '<p>O contrato pode ser rescindido:</p>'
        '<ol type="a" style="margin-left: 20px; margin-bottom: 8px; font-size: 10px; line-height: 1.5;">'
        '<li style="margin: 4px 0;">Por mútuo acordo entre as partes;</li>'
        '<li style="margin: 4px 0;">Por incumprimento de qualquer das obrigações aqui estabelecidas;</li>'
        '<li style="margin: 4px 0;">Por motivo de força maior.</li>'
        '</ol>'
        '<p>Em caso de rescisão por culpa do CONTRATANTE, deverá ser pago o valor proporcional aos trabalhos '
        'já executados, acrescido de 30% (trinta por cento) a título de despesas administrativas e lucros cessantes.</p>'
    )
    DEFAULT_CLAUSULA8_CONFIDENCIALIDADE = (
        '<p>As partes comprometem-se a manter sigilo sobre todas as informações trocadas no âmbito deste contrato, '
        'não podendo divulgá-las a terceiros sem prévia autorização por escrito da parte detentora da informação.</p>'
    )
    DEFAULT_CLAUSULA9_FORO = (
        '<p>O presente contrato é regido pelas leis da República de Moçambique.</p>'
        '<p>Em caso de litígio, as partes elegem o foro da Comarca de Maputo, com renúncia expressa a qualquer outro, '
        'por mais privilegiado que seja.</p>'
    )

    # Preparar textos padrão: config se existir, senão vazio (depois preenchemos com defaults)
    if config_padrao:
        textos_padrao = {
            'clausula2_pagamento': config_padrao.clausula2_pagamento or '',
            'clausula3_prazo': config_padrao.clausula3_prazo or '',
            'clausula4_obrigacoes': config_padrao.clausula4_obrigacoes or '',
            'clausula5_garantia': config_padrao.clausula5_garantia or '',
            'clausula6_alteracoes': config_padrao.clausula6_alteracoes or '',
            'clausula7_rescisao': config_padrao.clausula7_rescisao or '',
            'clausula8_confidencialidade': config_padrao.clausula8_confidencialidade or '',
            'clausula9_foro': config_padrao.clausula9_foro or '',
        }
    else:
        textos_padrao = {k: '' for k in (
            'clausula2_pagamento', 'clausula3_prazo', 'clausula4_obrigacoes', 'clausula5_garantia',
            'clausula6_alteracoes', 'clausula7_rescisao', 'clausula8_confidencialidade', 'clausula9_foro'
        )}
    # Preencher com defaults onde estiver vazio (garantir que obrigações e demais apareçam)
    if not textos_padrao['clausula4_obrigacoes']:
        textos_padrao['clausula4_obrigacoes'] = DEFAULT_CLAUSULA4_OBRIGACOES
    # Obrigações pré-definidas editáveis (cláusula 4) – valores para o formulário
    DEFAULT_OBRIG_C1 = 'Executar os serviços com rigor técnico, segurança e qualidade, em conformidade com a legislação aplicável.'
    DEFAULT_OBRIG_C2 = 'Providenciar a mão-de-obra e os meios necessários à execução dos serviços.'
    DEFAULT_OBRIG_C3 = 'Cumprir as normas de higiene e segurança no trabalho em vigor na República de Moçambique.'
    DEFAULT_OBRIG_T1 = 'Facilitar o acesso ao local dos trabalhos e as condições necessárias à sua execução.'
    DEFAULT_OBRIG_T2 = 'Prestar as informações e esclarecimentos necessários.'
    DEFAULT_OBRIG_T3 = 'Cumprir os pagamentos nos prazos acordados.'
    obrigacao_contratada_1 = orcamento.obrigacao_contratada_1 or DEFAULT_OBRIG_C1
    obrigacao_contratada_2 = orcamento.obrigacao_contratada_2 or DEFAULT_OBRIG_C2
    obrigacao_contratada_3 = orcamento.obrigacao_contratada_3 or DEFAULT_OBRIG_C3
    obrigacao_contratante_1 = orcamento.obrigacao_contratante_1 or DEFAULT_OBRIG_T1
    obrigacao_contratante_2 = orcamento.obrigacao_contratante_2 or DEFAULT_OBRIG_T2
    obrigacao_contratante_3 = orcamento.obrigacao_contratante_3 or DEFAULT_OBRIG_T3
    if not textos_padrao['clausula5_garantia']:
        textos_padrao['clausula5_garantia'] = DEFAULT_CLAUSULA5_GARANTIA
    if not textos_padrao['clausula6_alteracoes']:
        textos_padrao['clausula6_alteracoes'] = DEFAULT_CLAUSULA6_ALTERACOES
    if not textos_padrao['clausula7_rescisao']:
        textos_padrao['clausula7_rescisao'] = DEFAULT_CLAUSULA7_RESCISAO
    if not textos_padrao['clausula8_confidencialidade']:
        textos_padrao['clausula8_confidencialidade'] = DEFAULT_CLAUSULA8_CONFIDENCIALIDADE
    if not textos_padrao['clausula9_foro']:
        textos_padrao['clausula9_foro'] = DEFAULT_CLAUSULA9_FORO

    # Preparar valores padrão para cláusulas 2 e 3 se não editadas
    if not orcamento.clausula2_pagamento:
        if not textos_padrao['clausula2_pagamento']:
            if orcamento.forma_pagamento_configurada:
                textos_padrao['clausula2_pagamento'] = orcamento.forma_pagamento_configurada.get_texto_condicoes()
            else:
                textos_padrao['clausula2_pagamento'] = '<p>50% no ato da assinatura e 50% na conclusão dos serviços</p>'
    if not orcamento.clausula3_prazo and not textos_padrao['clausula3_prazo']:
        textos_padrao['clausula3_prazo'] = '30 dias'
    
    def _editar_contrato_garantia_valor(o):
        d = o.validade_garantia_dias or 90
        u = getattr(o, 'validade_garantia_unidade', None) or 'DIAS'
        if u == 'MESES':
            return max(1, d // 30)
        if u == 'ANOS':
            return max(1, d // 365)
        return d

    from .parcelas_vendas_utils import ordem_e_so_servicos, percentagem_minima_valor_servicos_cotacao
    mostrar_parcelas = ordem_e_so_servicos(orcamento)
    parcelas = list(orcamento.parcelas_pagamento.order_by('numero_ordem'))
    servicos_orcamento = list(orcamento.servicos_orcamento.select_related('servico').all())
    import json
    servicos_orcamento_json = json.dumps([
        {
            'id': s.id,
            'nome': s.nome_para_documento or (s.servico.nome if s.servico else ''),
            'valor_total': float(s.valor_total or 0),
        }
        for s in servicos_orcamento
    ])
    # Usar base sem desconto global (mesma lógica de percentagem_minima_valor_servicos_cotacao)
    try:
        from decimal import Decimal
        valor_servicos = sum((s.valor_total or Decimal('0')) for s in servicos_orcamento)
        valor_itens = sum(
            (item.valor_total or Decimal('0'))
            for servico in servicos_orcamento
            for item in servico.itens.all()
        )
        valor_transporte = sum((t.valor_frete or Decimal('0')) for t in orcamento.transportes_orcamento.all())
        valor_total_base = valor_servicos + valor_itens + valor_transporte
    except Exception:
        valor_total_base = orcamento.valor_total or 0
    valor_total_contrato_json = json.dumps(float(valor_total_base or 0))
    _pm = percentagem_minima_valor_servicos_cotacao(orcamento, None)
    percentagem_min_conclusao_trabalhos = _pm if _pm > 0 else None

    from django.urls import reverse
    context = {
        'orcamento': orcamento,
        'mostrar_parcelas': mostrar_parcelas,
        'percentagem_min_conclusao_trabalhos': percentagem_min_conclusao_trabalhos,
        'parcelas': parcelas,
        'servicos_orcamento': servicos_orcamento,
        'servicos_orcamento_json': servicos_orcamento_json,
        'valor_total_contrato_json': valor_total_contrato_json,
        'obrigacao_contratada_1': obrigacao_contratada_1,
        'obrigacao_contratada_2': obrigacao_contratada_2,
        'obrigacao_contratada_3': obrigacao_contratada_3,
        'obrigacao_contratante_1': obrigacao_contratante_1,
        'obrigacao_contratante_2': obrigacao_contratante_2,
        'obrigacao_contratante_3': obrigacao_contratante_3,
        'validade_garantia_dias': orcamento.validade_garantia_dias if orcamento.validade_garantia_dias else 90,
        'textos_padrao': textos_padrao,
        'forma_pagamento': orcamento.forma_pagamento_configurada,
        'garantia_valor': _editar_contrato_garantia_valor(orcamento),
        'from_vendas': from_vendas,
        'url_form_action': reverse('vendas:editar_contrato', args=[orcamento_id]) if from_vendas else reverse('producao:editar_contrato_servico', args=[orcamento_id]),
        'url_voltar': reverse('vendas:orcamento_detail', args=[orcamento_id]) if from_vendas else reverse('producao:servico_orcamento_detail', args=[orcamento_id]),
    }
    return render(request, 'producao/servicos/orcamento/editar_contrato.html', context)


@login_required
def preview_contrato_servico(request, orcamento_id, from_vendas=False):
    """
    Pré-visualização do contrato de prestação de serviços (HTML).
    from_vendas: quando True, usa URLs de Vendas para Voltar e Gerar PDF.
    """
    from decimal import Decimal
    from num2words import num2words
    from django.utils import timezone
    
    try:
        # Obter o orçamento com os relacionamentos necessários
        orcamento = get_object_or_404(
            OrdemServico.objects.select_related('cliente', 'responsavel', 'criado_por')
                               .prefetch_related('servicos_orcamento__servico', 'transportes_orcamento__transportadora', 'parcelas_pagamento__servicos'), 
            id=orcamento_id
        )
        
        # Obter dados da empresa e configuração de contrato (ajuste conforme seu modelo)
        from .models_base import DadosEmpresa, ConfiguracaoContratoServico
        try:
            dados_empresa = DadosEmpresa.objects.first()
            if not dados_empresa:
                raise DadosEmpresa.DoesNotExist
        except (DadosEmpresa.DoesNotExist, AttributeError):
            # Valores padrão caso não exista configuração
            dados_empresa = type('Obj', (), {
                'nome': 'Conception Lda',
                'endereco': 'Av. 24 de Julho, Nº 123, Maputo',
                'nuit': '401932089',
                'telefone': '+258 84 000 0000',
                'email': 'geral@conception.co.mz',
                'website': 'www.conception.co.mz'
            })
        
        # Buscar configuração de contrato padrão (se existir)
        config_contrato = ConfiguracaoContratoServico.objects.filter(ativo=True).order_by('-padrao', '-data_atualizacao').first()

        # Formatar dados do contrato
        from django.utils.dateformat import format
        data_atual = timezone.now()
        ano_atual = data_atual.year
        
        # Contar quantos contratos foram gerados no mesmo ano (usando orçamentos com data de criação no mesmo ano)
        # Assumindo que cada orçamento pode gerar apenas um contrato
        from django.db.models import Q
        orcamentos_antes = OrdemServico.objects.filter(
            data_criacao__year=ano_atual
        ).filter(
            Q(data_criacao__date__lt=orcamento.data_criacao.date()) |
            Q(data_criacao__date=orcamento.data_criacao.date(), id__lt=orcamento.id)
        )
        numero_sequencial = orcamentos_antes.count() + 1
        
        # Calcular totais usando a mesma lógica da cotação
        # IMPORTANTE: Os itens (materiais e produtos) devem ser somados ao valor do serviço
        from decimal import InvalidOperation
        
        total_servicos = Decimal('0.00')
        for servico_orc in orcamento.servicos_orcamento.all():
            try:
                qtd = Decimal(str(servico_orc.quantidade)) if servico_orc.quantidade is not None else Decimal('0.00')
                valor_unit = Decimal(str(servico_orc.valor_unitario)) if servico_orc.valor_unitario is not None else Decimal('0.00')
                desconto = Decimal(str(servico_orc.desconto)) if servico_orc.desconto is not None else Decimal('0.00')
                desconto_percentual = Decimal(str(servico_orc.desconto_percentual)) if servico_orc.desconto_percentual is not None else Decimal('0.00')
                
                # Calcular total de itens (materiais e produtos) para este serviço
                total_itens_servico_com_desconto = Decimal('0.00')
                for item in servico_orc.itens.all():
                    try:
                        # Usar valor_total do item que já inclui o desconto individual
                        total_itens_servico_com_desconto += item.valor_total
                    except (ValueError, TypeError, AttributeError, InvalidOperation):
                        continue
                
                # Valor bruto do serviço (sem desconto)
                valor_bruto_servico = qtd * valor_unit
                
                # Aplicar desconto do serviço APENAS sobre o valor do serviço
                valor_servico_com_desconto = valor_bruto_servico
                if desconto_percentual > 0:
                    valor_servico_com_desconto = valor_bruto_servico * (Decimal('1') - desconto_percentual / Decimal('100'))
                elif desconto > 0:
                    valor_servico_com_desconto = valor_bruto_servico - desconto
                    if valor_servico_com_desconto < 0:
                        valor_servico_com_desconto = Decimal('0.00')
                
                # Valor total final: serviço (com desconto) + itens (com seus próprios descontos)
                valor_total_com_itens = valor_servico_com_desconto + total_itens_servico_com_desconto
                total_servicos += valor_total_com_itens
            except (ValueError, TypeError, AttributeError, InvalidOperation) as e:
                logger.warning(f"Erro ao calcular valores para serviço {servico_orc.id} no preview contrato: {e}")
                # Fallback: usar valor_total do serviço se houver erro
                valor_servico = servico_orc.valor_total
                if valor_servico is not None:
                    total_servicos += Decimal(str(valor_servico))
        
        total_transporte = Decimal('0.00')
        for transporte in orcamento.transportes_orcamento.all():
            valor_frete = transporte.valor_frete or Decimal('0.00')
            total_transporte += Decimal(str(valor_frete)) if valor_frete is not None else Decimal('0.00')
        
        subtotal = total_servicos + total_transporte
        
        # Obter taxa de IVA
        try:
            from .models_base import ConfiguracaoFiscal
            configuracao = ConfiguracaoFiscal.objects.first()
            taxa_iva = Decimal(str(configuracao.iva)) if configuracao and hasattr(configuracao, 'iva') else Decimal('0.16')
        except:
            taxa_iva = Decimal('0.16')
            
        valor_iva = subtotal * taxa_iva
        valor_total = subtotal + valor_iva
        
        # Formatar lista de serviços (usando a mesma lógica da cotação)
        lista_servicos = []
        for servico_orc in orcamento.servicos_orcamento.all():
            try:
                qtd = Decimal(str(servico_orc.quantidade)) if servico_orc.quantidade is not None else Decimal('0.00')
                valor_unit = Decimal(str(servico_orc.valor_unitario)) if servico_orc.valor_unitario is not None else Decimal('0.00')
                desconto = Decimal(str(servico_orc.desconto)) if servico_orc.desconto is not None else Decimal('0.00')
                desconto_percentual = Decimal(str(servico_orc.desconto_percentual)) if servico_orc.desconto_percentual is not None else Decimal('0.00')
                
                # Calcular total de itens para este serviço
                total_itens_servico_com_desconto = Decimal('0.00')
                for item in servico_orc.itens.all():
                    try:
                        total_itens_servico_com_desconto += item.valor_total
                    except (ValueError, TypeError, AttributeError, InvalidOperation):
                        continue
                
                # Valor bruto do serviço
                valor_bruto_servico = qtd * valor_unit
                
                # Aplicar desconto do serviço
                valor_servico_com_desconto = valor_bruto_servico
                if desconto_percentual > 0:
                    valor_servico_com_desconto = valor_bruto_servico * (Decimal('1') - desconto_percentual / Decimal('100'))
                elif desconto > 0:
                    valor_servico_com_desconto = valor_bruto_servico - desconto
                    if valor_servico_com_desconto < 0:
                        valor_servico_com_desconto = Decimal('0.00')
                
                # Valor total incluindo itens
                valor_total_com_itens = valor_servico_com_desconto + total_itens_servico_com_desconto
                
                # Usar nome personalizado se existir, senão usar nome do serviço
                nome_servico = servico_orc.nome_para_documento if servico_orc.servico else 'Serviço não especificado'
                unidade = getattr(getattr(servico_orc, 'servico', None), 'unidade_medida', None) or 'UN'
                lista_servicos.append(
                    f"{qtd} {unidade} x {nome_servico} - {valor_total_com_itens:,.2f} MT"
                )
            except (ValueError, TypeError, AttributeError, InvalidOperation) as e:
                logger.warning(f"Erro ao formatar serviço {servico_orc.id} no preview contrato: {e}")
                # Fallback
                valor_servico = servico_orc.valor_total or Decimal('0.00')
                # Usar nome personalizado se existir, senão usar nome do serviço
                nome_servico = servico_orc.nome_para_documento if servico_orc.servico else 'Serviço não especificado'
                quantidade = servico_orc.quantidade or Decimal('0.00')
                unidade = getattr(getattr(servico_orc, 'servico', None), 'unidade_medida', None) or 'UN'
                lista_servicos.append(
                    f"{quantidade} {unidade} x {nome_servico} - {valor_servico:,.2f} MT"
            )
        
        # Adicionar transportes à lista de serviços
        for transporte in orcamento.transportes_orcamento.all():
            valor_frete = transporte.valor_frete or Decimal('0.00')
            nome_transportadora = transporte.transportadora.nome if transporte.transportadora else 'Transportadora não especificada'
            lista_servicos.append(
                f"Transporte: {nome_transportadora} - {Decimal(str(valor_frete)):,.2f} MT"
            )
        
        # Contexto para o template
        from django.urls import reverse
        from django.conf import settings
        
        # Construir URL absoluta do logotipo para o PDF
        logo_url = ''
        if dados_empresa and hasattr(dados_empresa, 'logo') and dados_empresa.logo:
            try:
                # Para PDF, precisa de URL absoluta
                logo_url = f"{request.scheme}://{request.get_host()}{settings.MEDIA_URL}{dados_empresa.logo.name}"
            except:
                logo_url = ''
        
        prazo_garantia_ctx = _contrato_prazo_garantia_context(orcamento)
        
        context = {
            'request': request,
            'ano': ano_atual,
            'sequencia': numero_sequencial,
            'numero_cotacao': orcamento.codigo,
            'data_cotacao': orcamento.data_criacao.strftime("%d/%m/%Y"),
            'nome_contratante': orcamento.cliente.nome if orcamento.cliente else (orcamento.nome_cliente_pagamento or 'Cliente não especificado'),
            'doc_contratante': '',  # ClienteServico não tem numero_documento
            'nuit_contratante': orcamento.cliente.nuit if orcamento.cliente else (orcamento.nuit_cliente_pagamento or ''),
            'morada_contratante': orcamento.cliente.endereco if orcamento.cliente else '',
            'telefone_contratante': orcamento.cliente.telefone if orcamento.cliente else (orcamento.telefone_cliente_pagamento or ''),
            'email_contratante': orcamento.cliente.email if orcamento.cliente else '',
            'cidade_contratante': orcamento.cliente.cidade if orcamento.cliente else '',
            'morada_empresa': getattr(dados_empresa, 'endereco', 'Endereço não especificado'),
            'representante': dados_empresa.representante_legal.get_full_name() if dados_empresa and hasattr(dados_empresa, 'representante_legal') and dados_empresa.representante_legal else 'Representante Legal',
            'cargo_representante': getattr(dados_empresa, 'cargo_representante', 'Responsável') if dados_empresa else 'Responsável',
            'lista_servicos': lista_servicos,
            'valor_total': f"{float(valor_total):,.2f}".replace(',', ' ').replace('.', ',').replace(' ', '.'),
            'valor_extenso': num2words(float(valor_total), lang='pt', to='currency', currency='EUR').replace('euros', 'meticais').replace('euro', 'metical'),
            'prazo_execucao': orcamento.clausula3_prazo if orcamento.clausula3_prazo else '30 dias',
            'condicoes_pagamento': orcamento.clausula2_pagamento if orcamento.clausula2_pagamento else (orcamento.forma_pagamento_configurada.get_texto_condicoes() if orcamento.forma_pagamento_configurada else '50% no ato da assinatura e 50% na conclusão dos serviços'),
            'validade_garantia_dias': orcamento.validade_garantia_dias if orcamento.validade_garantia_dias else 90,
            **prazo_garantia_ctx,
            'clausula2_pagamento': orcamento.clausula2_pagamento,
            'clausula3_prazo': orcamento.clausula3_prazo,
            'clausula4_obrigacoes': (
                orcamento.clausula4_obrigacoes if (orcamento.clausula4_obrigacoes and '<li>' in orcamento.clausula4_obrigacoes)
                else (config_contrato.clausula4_obrigacoes if (config_contrato and getattr(config_contrato, 'clausula4_obrigacoes', None) and '<li>' in (config_contrato.clausula4_obrigacoes or '')) else None)
            ),
            'clausula5_garantia': orcamento.clausula5_garantia.replace('{{ validade_garantia_dias }}', str(orcamento.validade_garantia_dias if orcamento.validade_garantia_dias else 90)) if orcamento.clausula5_garantia and '{{ validade_garantia_dias }}' in orcamento.clausula5_garantia else orcamento.clausula5_garantia,
            'clausula6_alteracoes': orcamento.clausula6_alteracoes,
            'clausula7_rescisao': (
                orcamento.clausula7_rescisao if (orcamento.clausula7_rescisao and '<li>' in orcamento.clausula7_rescisao)
                else (config_contrato.clausula7_rescisao if (config_contrato and getattr(config_contrato, 'clausula7_rescisao', None) and '<li>' in (config_contrato.clausula7_rescisao or '')) else None)
            ),
            'clausula8_confidencialidade': orcamento.clausula8_confidencialidade,
            'clausula9_foro': orcamento.clausula9_foro,
            'config_contrato': config_contrato,
            'data_contrato': data_atual.strftime("%d de %B de %Y"),
            'taxa_iva_percentual': int(taxa_iva * 100),
            'valor_iva': f"{float(valor_iva):,.2f}".replace(',', ' ').replace('.', ',').replace(' ', '.'),
            'subtotal': f"{float(subtotal):,.2f}".replace(',', ' ').replace('.', ',').replace(' ', '.'),
            'dados_empresa': dados_empresa,
            'logo_url': logo_url,
            'MEDIA_URL': settings.MEDIA_URL,
            'url_voltar': reverse('vendas:orcamento_detail', args=[orcamento_id]) if from_vendas else reverse('producao:servico_orcamento_detail', args=[orcamento_id]),
            'url_gerar': reverse('vendas:gerar_contrato', args=[orcamento_id]) if from_vendas else None,
            'orcamento_id': orcamento_id
        }
        # Valores em MT de cada parcela (para exibir no contrato)
        if context.get('pagamento_parcelas_texto'):
            total_num = float(valor_total)
            _fmt = lambda x: f"{x:,.2f}".replace(',', ' ').replace('.', ',').replace(' ', '.')
            parcelas_objs = context.get('pagamento_parcelas')
            if parcelas_objs:
                valores = [_fmt(total_num * p.percentagem / 100) for p in parcelas_objs]
            else:
                p_a = context.get('pagamento_percentagem_assinatura') or 50
                p_c = context.get('pagamento_percentagem_conclusao') or 50
                valores = [_fmt(total_num * p_a / 100), _fmt(total_num * p_c / 100)]
            context['pagamento_parcelas_com_valores'] = [{'texto': t, 'valor': v} for t, v in zip(context['pagamento_parcelas_texto'], valores)]
        else:
            context['pagamento_parcelas_com_valores'] = []
        # Renderizar o template HTML diretamente (sem gerar PDF)
        return render(request, 'producao/servicos/orcamento/contrato_template.html', context)
        
    except Exception as e:
        logger.error(f"Erro ao pré-visualizar contrato: {str(e)}", exc_info=True)
        messages.error(request, f"Erro ao pré-visualizar contrato: {str(e)}")
        if from_vendas:
            return redirect('vendas:orcamento_detail', id=orcamento_id)
        return redirect('producao:servico_orcamento_detail', id=orcamento_id)


@login_required
def gerar_contrato_servico(request, orcamento_id, from_vendas=False):
    """
    Gera o contrato de prestação de serviços em PDF a partir de um orçamento.
    from_vendas: quando True, redireciona para Vendas em caso de erro.
    """
    from django.template.loader import render_to_string
    from django.http import HttpResponse
    from decimal import Decimal
    from num2words import num2words
    from django.utils import timezone
    import io
    from xhtml2pdf import pisa
    
    try:
        # Obter o orçamento com os relacionamentos necessários
        orcamento = get_object_or_404(
            OrdemServico.objects.select_related('cliente', 'responsavel', 'criado_por')
                               .prefetch_related('servicos_orcamento__servico', 'transportes_orcamento__transportadora', 'parcelas_pagamento__servicos'), 
            id=orcamento_id
        )
        
        # Obter dados da empresa e configuração de contrato (ajuste conforme seu modelo)
        from .models_base import DadosEmpresa, ConfiguracaoContratoServico
        try:
            dados_empresa = DadosEmpresa.objects.first()
            if not dados_empresa:
                raise DadosEmpresa.DoesNotExist
        except (DadosEmpresa.DoesNotExist, AttributeError):
            # Valores padrão caso não exista configuração
            dados_empresa = type('Obj', (), {
                'nome': 'Conception Lda',
                'endereco': 'Av. 24 de Julho, Nº 123, Maputo',
                'nuit': '401932089',
                'telefone': '+258 84 000 0000',
                'email': 'geral@conception.co.mz',
                'website': 'www.conception.co.mz'
            })
        
        # Buscar configuração de contrato padrão (se existir)
        config_contrato = ConfiguracaoContratoServico.objects.filter(ativo=True).order_by('-padrao', '-data_atualizacao').first()

        # Formatar dados do contrato
        from django.utils.dateformat import format
        data_atual = timezone.now()
        ano_atual = data_atual.year
        
        # Contar quantos contratos foram gerados no mesmo ano (usando orçamentos com data de criação no mesmo ano)
        # Assumindo que cada orçamento pode gerar apenas um contrato
        from django.db.models import Q
        orcamentos_antes = OrdemServico.objects.filter(
            data_criacao__year=ano_atual
        ).filter(
            Q(data_criacao__date__lt=orcamento.data_criacao.date()) |
            Q(data_criacao__date=orcamento.data_criacao.date(), id__lt=orcamento.id)
        )
        numero_sequencial = orcamentos_antes.count() + 1
        
        # Calcular totais usando a mesma lógica da cotação
        # IMPORTANTE: Os itens (materiais e produtos) devem ser somados ao valor do serviço
        from decimal import InvalidOperation
        
        total_servicos = Decimal('0.00')
        for servico_orc in orcamento.servicos_orcamento.all():
            try:
                qtd = Decimal(str(servico_orc.quantidade)) if servico_orc.quantidade is not None else Decimal('0.00')
                valor_unit = Decimal(str(servico_orc.valor_unitario)) if servico_orc.valor_unitario is not None else Decimal('0.00')
                desconto = Decimal(str(servico_orc.desconto)) if servico_orc.desconto is not None else Decimal('0.00')
                desconto_percentual = Decimal(str(servico_orc.desconto_percentual)) if servico_orc.desconto_percentual is not None else Decimal('0.00')
                
                # Calcular total de itens (materiais e produtos) para este serviço
                total_itens_servico_com_desconto = Decimal('0.00')
                for item in servico_orc.itens.all():
                    try:
                        # Usar valor_total do item que já inclui o desconto individual
                        total_itens_servico_com_desconto += item.valor_total
                    except (ValueError, TypeError, AttributeError, InvalidOperation):
                        continue
                
                # Valor bruto do serviço (sem desconto)
                valor_bruto_servico = qtd * valor_unit
                
                # Aplicar desconto do serviço APENAS sobre o valor do serviço
                valor_servico_com_desconto = valor_bruto_servico
                if desconto_percentual > 0:
                    valor_servico_com_desconto = valor_bruto_servico * (Decimal('1') - desconto_percentual / Decimal('100'))
                elif desconto > 0:
                    valor_servico_com_desconto = valor_bruto_servico - desconto
                    if valor_servico_com_desconto < 0:
                        valor_servico_com_desconto = Decimal('0.00')
                
                # Valor total final: serviço (com desconto) + itens (com seus próprios descontos)
                valor_total_com_itens = valor_servico_com_desconto + total_itens_servico_com_desconto
                total_servicos += valor_total_com_itens
            except (ValueError, TypeError, AttributeError, InvalidOperation) as e:
                logger.warning(f"Erro ao calcular valores para serviço {servico_orc.id} no gerar contrato: {e}")
                # Fallback: usar valor_total do serviço se houver erro
                valor_servico = servico_orc.valor_total
                if valor_servico is not None:
                    total_servicos += Decimal(str(valor_servico))
        
        total_transporte = Decimal('0.00')
        for transporte in orcamento.transportes_orcamento.all():
            valor_frete = transporte.valor_frete or Decimal('0.00')
            total_transporte += Decimal(str(valor_frete)) if valor_frete is not None else Decimal('0.00')
        
        subtotal = total_servicos + total_transporte
        
        # Obter taxa de IVA
        try:
            from .models_base import ConfiguracaoFiscal
            configuracao = ConfiguracaoFiscal.objects.first()
            taxa_iva = Decimal(str(configuracao.iva)) if configuracao and hasattr(configuracao, 'iva') else Decimal('0.16')
        except:
            taxa_iva = Decimal('0.16')
            
        valor_iva = subtotal * taxa_iva
        valor_total = subtotal + valor_iva
        
        # Formatar lista de serviços (usando a mesma lógica da cotação)
        lista_servicos = []
        for servico_orc in orcamento.servicos_orcamento.all():
            try:
                qtd = Decimal(str(servico_orc.quantidade)) if servico_orc.quantidade is not None else Decimal('0.00')
                valor_unit = Decimal(str(servico_orc.valor_unitario)) if servico_orc.valor_unitario is not None else Decimal('0.00')
                desconto = Decimal(str(servico_orc.desconto)) if servico_orc.desconto is not None else Decimal('0.00')
                desconto_percentual = Decimal(str(servico_orc.desconto_percentual)) if servico_orc.desconto_percentual is not None else Decimal('0.00')
                
                # Calcular total de itens para este serviço
                total_itens_servico_com_desconto = Decimal('0.00')
                for item in servico_orc.itens.all():
                    try:
                        total_itens_servico_com_desconto += item.valor_total
                    except (ValueError, TypeError, AttributeError, InvalidOperation):
                        continue
                
                # Valor bruto do serviço
                valor_bruto_servico = qtd * valor_unit
                
                # Aplicar desconto do serviço
                valor_servico_com_desconto = valor_bruto_servico
                if desconto_percentual > 0:
                    valor_servico_com_desconto = valor_bruto_servico * (Decimal('1') - desconto_percentual / Decimal('100'))
                elif desconto > 0:
                    valor_servico_com_desconto = valor_bruto_servico - desconto
                    if valor_servico_com_desconto < 0:
                        valor_servico_com_desconto = Decimal('0.00')
                
                # Valor total incluindo itens
                valor_total_com_itens = valor_servico_com_desconto + total_itens_servico_com_desconto
                
                # Usar nome personalizado se existir, senão usar nome do serviço
                nome_servico = servico_orc.nome_para_documento if servico_orc.servico else 'Serviço não especificado'
                unidade = getattr(getattr(servico_orc, 'servico', None), 'unidade_medida', None) or 'UN'
                lista_servicos.append(
                    f"{qtd} {unidade} x {nome_servico} - {valor_total_com_itens:,.2f} MT"
                )
            except (ValueError, TypeError, AttributeError, InvalidOperation) as e:
                logger.warning(f"Erro ao formatar serviço {servico_orc.id} no gerar contrato: {e}")
                # Fallback
                valor_servico = servico_orc.valor_total or Decimal('0.00')
                # Usar nome personalizado se existir, senão usar nome do serviço
                nome_servico = servico_orc.nome_para_documento if servico_orc.servico else 'Serviço não especificado'
                quantidade = servico_orc.quantidade or Decimal('0.00')
                unidade = getattr(getattr(servico_orc, 'servico', None), 'unidade_medida', None) or 'UN'
                lista_servicos.append(
                    f"{quantidade} {unidade} x {nome_servico} - {valor_servico:,.2f} MT"
                )
        
        # Adicionar transportes à lista de serviços
        for transporte in orcamento.transportes_orcamento.all():
            valor_frete = transporte.valor_frete or Decimal('0.00')
            nome_transportadora = transporte.transportadora.nome if transporte.transportadora else 'Transportadora não especificada'
            lista_servicos.append(
                f"Transporte: {nome_transportadora} - {Decimal(str(valor_frete)):,.2f} MT"
            )
        
        # Contexto para o template
        from django.urls import reverse
        from django.conf import settings
        
        # Construir URL absoluta do logotipo para o PDF
        logo_url = ''
        if dados_empresa and hasattr(dados_empresa, 'logo') and dados_empresa.logo:
            try:
                logo_url = f"{request.scheme}://{request.get_host()}{settings.MEDIA_URL}{dados_empresa.logo.name}"
            except:
                logo_url = ''
        
        prazo_garantia_ctx = _contrato_prazo_garantia_context(orcamento)
        
        context = {
            'request': request,
            'ano': ano_atual,
            'sequencia': numero_sequencial,
            'numero_cotacao': orcamento.codigo,
            'data_cotacao': orcamento.data_criacao.strftime("%d/%m/%Y"),
            'nome_contratante': orcamento.cliente.nome if orcamento.cliente else (orcamento.nome_cliente_pagamento or 'Cliente não especificado'),
            'doc_contratante': '',
            'nuit_contratante': orcamento.cliente.nuit if orcamento.cliente else (orcamento.nuit_cliente_pagamento or ''),
            'morada_contratante': orcamento.cliente.endereco if orcamento.cliente else '',
            'telefone_contratante': orcamento.cliente.telefone if orcamento.cliente else (orcamento.telefone_cliente_pagamento or ''),
            'email_contratante': orcamento.cliente.email if orcamento.cliente else '',
            'cidade_contratante': orcamento.cliente.cidade if orcamento.cliente else '',
            'morada_empresa': getattr(dados_empresa, 'endereco', 'Endereço não especificado'),
            'representante': dados_empresa.representante_legal.get_full_name() if dados_empresa and hasattr(dados_empresa, 'representante_legal') and dados_empresa.representante_legal else 'Representante Legal',
            'cargo_representante': getattr(dados_empresa, 'cargo_representante', 'Responsável') if dados_empresa else 'Responsável',
            'lista_servicos': lista_servicos,
            'valor_total': f"{float(valor_total):,.2f}".replace(',', ' ').replace('.', ',').replace(' ', '.'),
            'valor_extenso': num2words(float(valor_total), lang='pt', to='currency', currency='EUR').replace('euros', 'meticais').replace('euro', 'metical'),
            'prazo_execucao': orcamento.clausula3_prazo if orcamento.clausula3_prazo else '30 dias',
            'condicoes_pagamento': orcamento.clausula2_pagamento if orcamento.clausula2_pagamento else (orcamento.forma_pagamento_configurada.get_texto_condicoes() if orcamento.forma_pagamento_configurada else '50% no ato da assinatura e 50% na conclusão dos serviços'),
            'validade_garantia_dias': orcamento.validade_garantia_dias if orcamento.validade_garantia_dias else 90,
            **prazo_garantia_ctx,
            'clausula2_pagamento': orcamento.clausula2_pagamento,
            'clausula3_prazo': orcamento.clausula3_prazo,
            'clausula4_obrigacoes': (
                orcamento.clausula4_obrigacoes if (orcamento.clausula4_obrigacoes and '<li>' in orcamento.clausula4_obrigacoes)
                else (config_contrato.clausula4_obrigacoes if (config_contrato and getattr(config_contrato, 'clausula4_obrigacoes', None) and '<li>' in (config_contrato.clausula4_obrigacoes or '')) else None)
            ),
            'clausula5_garantia': orcamento.clausula5_garantia.replace('{{ validade_garantia_dias }}', str(orcamento.validade_garantia_dias if orcamento.validade_garantia_dias else 90)) if orcamento.clausula5_garantia and '{{ validade_garantia_dias }}' in orcamento.clausula5_garantia else orcamento.clausula5_garantia,
            'clausula6_alteracoes': orcamento.clausula6_alteracoes,
            'clausula7_rescisao': (
                orcamento.clausula7_rescisao if (orcamento.clausula7_rescisao and '<li>' in orcamento.clausula7_rescisao)
                else (config_contrato.clausula7_rescisao if (config_contrato and getattr(config_contrato, 'clausula7_rescisao', None) and '<li>' in (config_contrato.clausula7_rescisao or '')) else None)
            ),
            'clausula8_confidencialidade': orcamento.clausula8_confidencialidade,
            'clausula9_foro': orcamento.clausula9_foro,
            'config_contrato': config_contrato,
            'data_contrato': data_atual.strftime("%d de %B de %Y"),
            'taxa_iva_percentual': int(taxa_iva * 100),
            'valor_iva': f"{float(valor_iva):,.2f}".replace(',', ' ').replace('.', ',').replace(' ', '.'),
            'subtotal': f"{float(subtotal):,.2f}".replace(',', ' ').replace('.', ',').replace(' ', '.'),
            'dados_empresa': dados_empresa,
            'logo_url': logo_url,
            'MEDIA_URL': settings.MEDIA_URL,
            'url_voltar': reverse('vendas:orcamento_detail', args=[orcamento_id]) if from_vendas else reverse('producao:servico_orcamento_detail', args=[orcamento_id]),
            'url_gerar': reverse('vendas:gerar_contrato', args=[orcamento_id]) if from_vendas else None,
            'orcamento_id': orcamento_id
        }
        # Valores em MT de cada parcela (para exibir no contrato)
        if context.get('pagamento_parcelas_texto'):
            total_num = float(valor_total)
            _fmt = lambda x: f"{x:,.2f}".replace(',', ' ').replace('.', ',').replace(' ', '.')
            parcelas_objs = context.get('pagamento_parcelas')
            if parcelas_objs:
                valores = [_fmt(total_num * p.percentagem / 100) for p in parcelas_objs]
            else:
                p_a = context.get('pagamento_percentagem_assinatura') or 50
                p_c = context.get('pagamento_percentagem_conclusao') or 50
                valores = [_fmt(total_num * p_a / 100), _fmt(total_num * p_c / 100)]
            context['pagamento_parcelas_com_valores'] = [{'texto': t, 'valor': v} for t, v in zip(context['pagamento_parcelas_texto'], valores)]
        else:
            context['pagamento_parcelas_com_valores'] = []
        # Renderizar o template
        html_string = render_to_string('producao/servicos/orcamento/contrato_template.html', context)
        
        # Criar um arquivo em memória para o PDF
        pdf_file = io.BytesIO()
        
        # Gerar PDF com xhtml2pdf
        pisa_status = pisa.CreatePDF(
            html_string,
            dest=pdf_file,
            encoding='utf-8',
            link_callback=None
        )
        
        if not pisa_status.err:
            # Se não houver erros, retornar o PDF
            pdf_file.seek(0)
            response = HttpResponse(pdf_file, content_type='application/pdf')
            response['Content-Disposition'] = f'inline; filename=contrato_servico_{orcamento.codigo}.pdf'
            # Adicionar header para permitir voltar
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            return response
        else:
            raise Exception("Erro ao gerar o PDF")
        
    except Exception as e:
        logger.error(f"Erro ao gerar contrato: {str(e)}", exc_info=True)
        messages.error(request, f"Erro ao gerar contrato: {str(e)}")
        if from_vendas:
            return redirect('vendas:orcamento_detail', id=orcamento_id)
        return redirect('producao:servico_orcamento_detail', id=orcamento_id)

# =============================================================================
# GESTÃO DE CATEGORIAS DE SERVIÇOS (dentro do módulo de Produção)
# =============================================================================

@login_required
def producao_servicos_categorias(request):
    """Lista de categorias de serviços - Apenas categorias do tipo SERVICO ou TODOS"""
    try:
        from django.db.models import Q
        from .models_stock import CategoriaProduto
        
        # Parâmetros de busca e filtro
        search_query = request.GET.get('q', '').strip()
        status = request.GET.get('status')
        order_by = request.GET.get('order_by', 'nome')

        # Query base - APENAS categorias de serviços
        categorias = CategoriaProduto.objects.filter(
            Q(tipo='SERVICO') | Q(tipo='TODOS')
        ).select_related('categoria_pai')

        # Aplicar filtros
        if search_query:
            categorias = categorias.filter(
                Q(nome__icontains=search_query) |
                Q(codigo__icontains=search_query) |
                Q(descricao__icontains=search_query)
            )
        
        if status:
            if status == 'ativa':
                categorias = categorias.filter(ativa=True)
            elif status == 'inativa':
                categorias = categorias.filter(ativa=False)

        # Separar categorias principais e subcategorias
        categorias_principais = categorias.filter(categoria_pai__isnull=True).order_by(order_by)
        categorias_subcategorias = categorias.filter(categoria_pai__isnull=False).order_by(order_by)
        
        context = {
            'categorias_principais': categorias_principais,
            'categorias_subcategorias': categorias_subcategorias,
            'total_principais': categorias_principais.count(),
            'total_subcategorias': categorias_subcategorias.count(),
            'search_query': search_query,
            'status': status,
            'order_by': order_by,
        }
        return render(request, 'producao/servicos/categorias/list.html', context)
    except Exception as e:
        logger.error(f"Erro ao listar categorias de serviços: {e}", exc_info=True)
        messages.error(request, 'Erro ao carregar lista de categorias de serviços.')
        return redirect('producao:servicos_list')


@login_required
@require_http_methods(["GET", "POST"])
def producao_servicos_categoria_add(request):
    """Adicionar nova categoria de serviço"""
    from .models_stock import CategoriaProduto
    
    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        descricao = request.POST.get('descricao', '').strip()
        categoria_pai_id = request.POST.get('categoria_pai')
        
        # Validação
        if not nome:
            messages.error(request, 'Nome é obrigatório.')
            return redirect('producao:servicos_categoria_add')
        
        if len(nome) > 100:
            messages.error(request, 'Nome deve ter no máximo 100 caracteres.')
            return redirect('producao:servicos_categoria_add')
        
        try:
            with transaction.atomic():
                categoria_pai = None
                if categoria_pai_id:
                    # Verificar se a categoria pai é de serviço
                    categoria_pai = CategoriaProduto.objects.get(
                        id=categoria_pai_id,
                        ativa=True
                    )
                    if categoria_pai.tipo not in ['SERVICO', 'TODOS']:
                        messages.error(request, 'A categoria pai deve ser do tipo Serviço.')
                        return redirect('producao:servicos_categoria_add')
                
                CategoriaProduto.objects.create(
                    nome=nome,
                    tipo='SERVICO',  # Sempre tipo SERVICO
                    descricao=descricao,
                    categoria_pai=categoria_pai
                )
                messages.success(request, 'Categoria de serviço adicionada com sucesso.')
                return redirect('producao:servicos_categorias')
        except ValidationError as e:
            messages.error(request, f'Erro de validação: {str(e)}')
        except Exception as e:
            logger.error(f"Erro ao adicionar categoria de serviço: {e}", exc_info=True)
            messages.error(request, f'Erro ao adicionar categoria: {str(e)}')
    
    # Buscar apenas categorias de serviços como categorias pai
    categorias_pai = CategoriaProduto.objects.filter(
        Q(tipo='SERVICO') | Q(tipo='TODOS'),
        ativa=True,
        categoria_pai__isnull=True
    )
    
    context = {
        'categorias_pai': categorias_pai,
    }
    return render(request, 'producao/servicos/categorias/form.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def producao_servicos_categoria_edit(request, id):
    """Editar categoria de serviço"""
    from .models_stock import CategoriaProduto
    categoria = get_object_or_404(
        CategoriaProduto,
        id=id,
        tipo__in=['SERVICO', 'TODOS']  # Apenas categorias de serviços
    )
    
    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        descricao = request.POST.get('descricao', '').strip()
        categoria_pai_id = request.POST.get('categoria_pai')
        
        if not nome:
            messages.error(request, 'Nome é obrigatório.')
            return redirect('producao:servicos_categoria_edit', id=id)
        
        if len(nome) > 100:
            messages.error(request, 'Nome deve ter no máximo 100 caracteres.')
            return redirect('producao:servicos_categoria_edit', id=id)
        
        try:
            with transaction.atomic():
                categoria.nome = nome
                categoria.descricao = descricao
                categoria.tipo = 'SERVICO'  # Garantir que seja sempre SERVICO
                categoria.categoria_pai = None
                
                if categoria_pai_id:
                    categoria_pai = CategoriaProduto.objects.get(id=categoria_pai_id)
                    # Verificar se não está tentando criar loop
                    if categoria_pai.id == categoria.id:
                        messages.error(request, 'Uma categoria não pode ser pai de si mesma.')
                        return redirect('producao:servicos_categoria_edit', id=id)
                    # Verificar se a categoria pai é de serviço
                    if categoria_pai.tipo not in ['SERVICO', 'TODOS']:
                        messages.error(request, 'A categoria pai deve ser do tipo Serviço.')
                        return redirect('producao:servicos_categoria_edit', id=id)
                    categoria.categoria_pai = categoria_pai
                
                categoria.save()
                messages.success(request, 'Categoria de serviço atualizada com sucesso.')
                return redirect('producao:servicos_categorias')
        except ValidationError as e:
            messages.error(request, f'Erro de validação: {str(e)}')
        except Exception as e:
            logger.error(f"Erro ao editar categoria de serviço {id}: {e}", exc_info=True)
            messages.error(request, f'Erro ao atualizar categoria: {str(e)}')
    
    # Buscar apenas categorias de serviços como categorias pai (excluindo a própria)
    categorias_pai = CategoriaProduto.objects.filter(
        Q(tipo='SERVICO') | Q(tipo='TODOS'),
        ativa=True,
        categoria_pai__isnull=True
    ).exclude(id=id)
    
    context = {
        'categoria': categoria,
        'categorias_pai': categorias_pai,
    }
    return render(request, 'producao/servicos/categorias/form.html', context)


@login_required
@require_http_methods(["POST"])
def producao_servicos_categoria_delete(request, id):
    """Excluir categoria de serviço"""
    from .models_stock import CategoriaProduto
    categoria = get_object_or_404(
        CategoriaProduto,
        id=id,
        tipo__in=['SERVICO', 'TODOS']
    )
    
    try:
        with transaction.atomic():
            # Verificar se há subcategorias
            subcategorias_count = categoria.subcategorias.filter(
                Q(tipo='SERVICO') | Q(tipo='TODOS')
            ).count()
            
            if subcategorias_count > 0:
                messages.error(request, f'Não é possível excluir esta categoria pois ela possui {subcategorias_count} subcategoria(s). Remova as subcategorias primeiro.')
                return redirect('producao:servicos_categorias')
            
            # Verificar se há serviços usando esta categoria
            servicos_count = Item.objects.filter(
                tipo='PRODUTO',
                produto_tipo='SERVICO',
                categoria=categoria
            ).count()
            
            if servicos_count > 0:
                messages.error(request, f'Não é possível excluir esta categoria pois ela está sendo usada por {servicos_count} serviço(s).')
                return redirect('producao:servicos_categorias')
            
            categoria.delete()
            messages.success(request, 'Categoria de serviço excluída com sucesso.')
    except Exception as e:
        logger.error(f"Erro ao excluir categoria de serviço {id}: {e}", exc_info=True)
        messages.error(request, f'Erro ao excluir categoria: {str(e)}')
    
    return redirect('producao:servicos_categorias')


@login_required
@require_http_methods(["POST"])
def producao_ordem_fase3_aprovar_qualidade(request, id):
    """Aprovar controle de qualidade"""
    ordem = get_object_or_404(OrdemProducao, id=id)
    
    if ordem.fase_atual != 'FASE3_FINALIZACAO':
        messages.error(request, 'Esta ordem não está na Fase 3.')
        return redirect('producao:ordens')
    
    observacoes_qualidade = request.POST.get('observacoes_qualidade', '').strip()
    
    try:
        with transaction.atomic():
            ordem.controle_qualidade_aprovado = True
            ordem.aprovado_qualidade_por = request.user
            ordem.data_aprovacao_qualidade = timezone.now()
            ordem.observacoes_qualidade = observacoes_qualidade
            ordem.save()
            
            messages.success(request, 'Controle de qualidade aprovado.')
    except Exception as e:
        logger.error(f"Erro ao aprovar qualidade para ordem {id}: {e}", exc_info=True)
        messages.error(request, f'Erro: {str(e)}')
    
    return redirect('producao:ordem_fase3', id=id)


@login_required
@require_http_methods(["POST"])
def producao_ordem_fase3_finalizar(request, id):
    """Finalizar ordem de produção"""
    ordem = get_object_or_404(OrdemProducao, id=id)
    
    if ordem.fase_atual != 'FASE3_FINALIZACAO':
        messages.error(request, 'Esta ordem não está na Fase 3.')
        return redirect('producao:ordens')
    
    if not ordem.pode_avancar_fase():
        messages.error(request, 'Não é possível finalizar. Complete todas as etapas da Fase 3.')
        return redirect('producao:ordem_fase3', id=id)
    
    observacoes_finalizacao = request.POST.get('observacoes_finalizacao', '').strip()
    
    try:
        with transaction.atomic():
            ordem.fase_atual = 'FINALIZADA'
            ordem.quantidade_produzida = ordem.quantidade
            ordem.produto_disponibilizado = True
            ordem.observacoes_finalizacao = observacoes_finalizacao
            ordem.data_finalizacao = timezone.now()
            ordem.save()
            
            # Adicionar produto produzido ao stock
            if ordem.receita and ordem.receita.produto:
                from .models_stock import MovimentoItem, TipoMovimentoStock, StockItem
                
                produto = ordem.receita.produto
                
                # Verificar se o produto é do tipo PRODUTO
                if produto.tipo != 'PRODUTO':
                    logger.warning(f"Item {produto.nome} não é um produto (tipo: {produto.tipo}). Não será adicionado ao stock.")
                else:
                    # Buscar ou criar tipo de movimento para entrada por produção
                    tipo_entrada_producao = TipoMovimentoStock.objects.filter(
                        codigo='ENT_PRODUCAO'
                    ).first()
                    
                    if not tipo_entrada_producao:
                        tipo_entrada_producao = TipoMovimentoStock.objects.create(
                            codigo='ENT_PRODUCAO',
                            nome='Entrada por Produção',
                            descricao='Entrada de produto no stock através de produção',
                            aumenta_estoque=True,
                            ativo=True
                        )
                    
                    # Calcular preço de custo do produto (baseado no custo da receita)
                    # IMPORTANTE: calcular_custo_por_produto() já retorna o custo por unidade (já dividido pelo rendimento)
                    try:
                        preco_custo = ordem.receita.calcular_custo_por_produto()
                        if not preco_custo or preco_custo <= 0:
                            # Se não conseguir calcular, usar preço de custo do produto ou 0
                            preco_custo = produto.preco_custo if hasattr(produto, 'preco_custo') and produto.preco_custo else Decimal('0.00')
                    except Exception as e:
                        logger.warning(f"Erro ao calcular custo da receita para ordem {ordem.codigo}: {e}")
                        # Se não conseguir calcular, usar preço de custo do produto ou 0
                        preco_custo = produto.preco_custo if hasattr(produto, 'preco_custo') and produto.preco_custo else Decimal('0.00')
                    
                    # Gerar código único para o movimento (máximo 20 caracteres)
                    # Formato: MOV{CODIGO_ORDEM_SEM_OP}P ou MOV{CODIGO_ORDEM_SEM_OP}P{NN}
                    codigo_ordem_curto = ordem.codigo.replace('OP', '')  # Remove OP para economizar espaço
                    # Base: MOV + código sem OP + P = máximo 18 caracteres (deixa espaço para 2 dígitos)
                    codigo_base = f"MOV{codigo_ordem_curto}P"
                    
                    # Garantir que o código base não ultrapasse 18 caracteres
                    if len(codigo_base) > 18:
                        codigo_base = codigo_base[:18]
                    
                    codigo_movimento = codigo_base
                    contador = 1
                    while MovimentoItem.objects.filter(codigo=codigo_movimento).exists():
                        # Adicionar sufixo numérico (máximo 2 dígitos)
                        codigo_movimento = f"{codigo_base[:18]}{contador:02d}"
                        contador += 1
                        if contador > 99:  # Limite de segurança
                            # Se ainda houver conflito, usar timestamp
                            import time
                            timestamp = str(int(time.time()))[-6:]  # Últimos 6 dígitos
                            codigo_movimento = f"MOV{timestamp}P"
                            break
                    
                    # Garantir que o código final não ultrapasse 20 caracteres
                    if len(codigo_movimento) > 20:
                        codigo_movimento = codigo_movimento[:20]
                    
                    # Criar movimento de entrada (produção)
                    movimento = MovimentoItem.objects.create(
                        codigo=codigo_movimento,
                        item=produto,
                        tipo_movimento=tipo_entrada_producao,
                        sucursal=ordem.sucursal,
                        quantidade=ordem.quantidade_produzida,
                        preco_unitario=preco_custo,
                        valor_total=preco_custo * Decimal(str(ordem.quantidade_produzida)),
                        referencia=f"Ordem de Produção {ordem.codigo}",
                        observacoes=f"Produto produzido pela ordem {ordem.codigo}. {observacoes_finalizacao}",
                        usuario=request.user
                    )
                    
                    # O signal atualizará o stock automaticamente
                    logger.info(f"Produto {produto.nome} adicionado ao stock: {ordem.quantidade_produzida} unidades (Ordem {ordem.codigo})")
            
            messages.success(request, f'Ordem {ordem.codigo} finalizada com sucesso! Produto adicionado ao stock.')
            return redirect('producao:ordens')
    except Exception as e:
        logger.error(f"Erro ao finalizar ordem {id}: {e}", exc_info=True)
        messages.error(request, f'Erro ao finalizar: {str(e)}')
    
    return redirect('producao:ordem_fase3', id=id)


# =============================================================================
# CÓDIGO ANTIGO - MANTER TEMPORARIAMENTE PARA COMPATIBILIDADE
# =============================================================================

@login_required
@require_http_methods(["GET", "POST"])
def producao_ordem_edit(request, id):
    """Editar ordem de produção"""
    ordem = get_object_or_404(OrdemProducao, id=id)
    
    if request.method == 'POST':
        receita_id = request.POST.get('receita')
        quantidade = request.POST.get('quantidade')
        status = request.POST.get('status')
        prioridade = request.POST.get('prioridade')
        sucursal_id = request.POST.get('sucursal')
        data_planejada_inicio = request.POST.get('data_planejada_inicio')
        data_planejada_conclusao = request.POST.get('data_planejada_conclusao')
        quantidade_produzida = request.POST.get('quantidade_produzida', '0')
        observacoes = request.POST.get('observacoes', '').strip()
        responsavel_id = request.POST.get('responsavel')
        
        # Validação
        if not all([receita_id, quantidade, sucursal_id, status, prioridade]):
            messages.error(request, 'Todos os campos obrigatórios devem ser preenchidos.')
            return redirect('producao:ordem_edit', id=id)
        
        # Validação especial para cancelamento
        if status == 'CANCELADA':
            motivo_cancelamento = request.POST.get('motivo_cancelamento', '').strip()
            if not motivo_cancelamento:
                messages.error(request, 'É obrigatório informar o motivo do cancelamento.')
                return redirect('producao:ordem_edit', id=id)
        
        try:
            quantidade_int = int(quantidade)
            quantidade_produzida_int = int(quantidade_produzida) if quantidade_produzida else 0
            
            if quantidade_int <= 0:
                messages.error(request, 'Quantidade deve ser maior que zero.')
                return redirect('producao:ordem_edit', id=id)
            
            if quantidade_produzida_int < 0:
                messages.error(request, 'Quantidade produzida não pode ser negativa.')
                return redirect('producao:ordem_edit', id=id)
            
            if quantidade_produzida_int > quantidade_int:
                messages.error(request, 'Quantidade produzida não pode ser maior que a quantidade planejada.')
                return redirect('producao:ordem_edit', id=id)
        except (ValueError, TypeError):
            messages.error(request, 'Quantidades devem ser números válidos.')
            return redirect('producao:ordem_edit', id=id)
        
        try:
            with transaction.atomic():
                ordem.receita = Receita.objects.get(id=receita_id)
                
                # Processar processo
                processo_id = request.POST.get('processo')
                if processo_id:
                    try:
                        ordem.processo = ProcessoProducao.objects.get(id=processo_id, status__in=['ATIVO', 'APROVADO'])
                    except ProcessoProducao.DoesNotExist:
                        ordem.processo = None
                else:
                    # Tentar encontrar processo automaticamente associado à receita
                    processo = ProcessoProducao.objects.filter(
                        receitas=ordem.receita,
                        status__in=['ATIVO', 'APROVADO']
                    ).first()
                    ordem.processo = processo
                
                ordem.quantidade = quantidade_int
                ordem.status = status
                ordem.prioridade = prioridade
                ordem.sucursal = Sucursal.objects.get(id=sucursal_id)
                ordem.quantidade_produzida = quantidade_produzida_int
                ordem.observacoes = observacoes
                
                # Recalcular data de conclusão se processo foi alterado e não há data manual
                if ordem.processo and not data_planejada_conclusao and data_planejada_inicio:
                    from datetime import timedelta
                    try:
                        dt = datetime.strptime(data_planejada_inicio, '%Y-%m-%dT%H:%M')
                        ordem.data_planejada_inicio = timezone.make_aware(dt)
                        horas_totais = float(ordem.processo.tempo_total_estimado) * quantidade_int
                        ordem.data_planejada_conclusao = ordem.data_planejada_inicio + timedelta(hours=horas_totais)
                    except ValueError:
                        pass
                
                if data_planejada_inicio:
                    try:
                        dt = datetime.strptime(data_planejada_inicio, '%Y-%m-%dT%H:%M')
                        ordem.data_planejada_inicio = timezone.make_aware(dt)
                    except ValueError:
                        pass
                else:
                    ordem.data_planejada_inicio = None
                
                if data_planejada_conclusao:
                    try:
                        dt = datetime.strptime(data_planejada_conclusao, '%Y-%m-%dT%H:%M')
                        ordem.data_planejada_conclusao = timezone.make_aware(dt)
                    except ValueError:
                        pass
                else:
                    ordem.data_planejada_conclusao = None
                
                if responsavel_id:
                    ordem.responsavel = User.objects.get(id=responsavel_id)
                else:
                    ordem.responsavel = None
                
                status_anterior = ordem.status
                if status == 'EM_PRODUCAO' and not ordem.data_inicio_fase2:
                    ordem.data_inicio_fase2 = timezone.now()
                if status == 'CONCLUIDA' and not ordem.data_finalizacao:
                    ordem.data_finalizacao = timezone.now()
                
                # Tratamento especial para cancelamento
                if status == 'CANCELADA':
                    # Verificar se pode ser cancelada
                    if status_anterior == 'CONCLUIDA':
                        messages.warning(request, 'Atenção: Esta ordem já foi concluída. O cancelamento foi registrado, mas a produção já foi finalizada.')
                    
                    # Registrar data de cancelamento se ainda não foi cancelada
                    if not ordem.data_cancelamento:
                        ordem.data_cancelamento = timezone.now()
                    
                    # Capturar motivo de cancelamento se fornecido
                    motivo_cancelamento = request.POST.get('motivo_cancelamento', '').strip()
                    if motivo_cancelamento:
                        ordem.motivo_cancelamento = motivo_cancelamento
                    
                    # Se estava em produção, limpar data de início (opcional - pode manter para histórico)
                    # ordem.data_inicio = None  # Comentado para manter histórico
                
                # Se estava cancelada e está sendo reativada, limpar dados de cancelamento
                elif status_anterior == 'CANCELADA' and status != 'CANCELADA':
                    ordem.data_cancelamento = None
                    ordem.motivo_cancelamento = ''
                
                ordem.save()
                
                messages.success(request, f'Ordem de produção {ordem.codigo} atualizada com sucesso.')
                return redirect('producao:ordens')
        except Receita.DoesNotExist:
            messages.error(request, 'Receita selecionada não encontrada.')
        except Sucursal.DoesNotExist:
            messages.error(request, 'Sucursal selecionada não encontrada.')
        except User.DoesNotExist:
            messages.error(request, 'Responsável selecionado não encontrado.')
        except Exception as e:
            logger.error(f"Erro ao editar ordem de produção {id}: {e}", exc_info=True)
            messages.error(request, f'Erro ao atualizar ordem de produção: {str(e)}')
    
    # GET - Exibir formulário
    context = {
        'ordem': ordem,
        'receitas': Receita.objects.filter(status__in=['ATIVA', 'APROVADA']).order_by('nome'),
        'sucursais': Sucursal.objects.filter(ativa=True).order_by('nome'),
        'status_choices': OrdemProducao.STATUS_CHOICES,
        'prioridade_choices': OrdemProducao.PRIORIDADE_CHOICES,
        'usuarios': User.objects.filter(is_active=True).order_by('username'),
    }
    return render(request, 'producao/ordens/form.html', context)


@login_required
def producao_ordem_detail(request, id):
    """Detalhes da ordem de produção"""
    try:
        ordem = get_object_or_404(OrdemProducao.objects.select_related(
            'receita', 'receita__produto', 'sucursal', 'criado_por'
        ).prefetch_related(
            'receita__itens__material'
        ), id=id)
        
        # Obter etapas do processo agrupadas por ordem (para mostrar paralelas)
        etapas_agrupadas = []
        etapas_concluidas_dict = {}
        
        processo = ordem.processo
        
        if processo:
            try:
                # Prefetch relacionamentos de etapas concluídas se existirem
                from .models_stock import EtapaOrdemConcluida
                
                # Criar dicionário de etapas concluídas (etapa_id -> etapa_concluida_obj)
                etapas_concluidas = EtapaOrdemConcluida.objects.filter(
                    ordem=ordem
                ).select_related('etapa', 'concluida_por')
                
                for etapa_concluida in etapas_concluidas:
                    etapas_concluidas_dict[etapa_concluida.etapa_id] = etapa_concluida
                
                # Obter etapas do processo
                etapas = processo.etapas.all().select_related('responsavel').order_by('ordem', 'nome')
                etapas_por_ordem = {}
                for etapa in etapas:
                    ordem_num = etapa.ordem if hasattr(etapa, 'ordem') else 0
                    if ordem_num not in etapas_por_ordem:
                        etapas_por_ordem[ordem_num] = []
                    etapas_por_ordem[ordem_num].append(etapa)
                
                # Converter para lista ordenada
                for ordem_num in sorted(etapas_por_ordem.keys()):
                    etapas_agrupadas.append({
                        'ordem': ordem_num,
                        'etapas': etapas_por_ordem[ordem_num]
                    })
            except Exception as e:
                logger.warning(f"Erro ao processar etapas do processo para ordem {id}: {e}")
                # Continuar sem etapas se houver erro
        
        context = {
            'ordem': ordem,
            'etapas_agrupadas': etapas_agrupadas,
            'etapas_concluidas_dict': etapas_concluidas_dict,
        }
        return render(request, 'producao/ordens/detail.html', context)
    except Exception as e:
        logger.error(f"Erro ao exibir detalhes da ordem {id}: {e}", exc_info=True)
        messages.error(request, f'Erro ao carregar detalhes da ordem de produção: {str(e)}')
        return redirect('producao:ordens')


@login_required
@require_http_methods(["POST"])
def producao_ordem_delete(request, id):
    """Deletar ordem de produção"""
    ordem = get_object_or_404(OrdemProducao, id=id)
    
    # Validação: não pode deletar ordens em produção ou concluídas
    if ordem.status == 'EM_PRODUCAO':
        messages.error(request, 'Não é possível deletar uma ordem que está em produção. Cancele a ordem primeiro.')
        return redirect('producao:ordens')
    
    if ordem.status == 'CONCLUIDA':
        messages.error(request, 'Não é possível deletar uma ordem concluída. Apenas ordens em rascunho, planejadas ou canceladas podem ser deletadas.')
        return redirect('producao:ordens')
    
    try:
        codigo_ordem = ordem.codigo
        ordem.delete()
        messages.success(request, f'Ordem de produção {codigo_ordem} deletada com sucesso.')
    except Exception as e:
        logger.error(f"Erro ao deletar ordem de produção {id}: {e}", exc_info=True)
        messages.error(request, f'Erro ao deletar ordem de produção: {str(e)}')
    
    return redirect('producao:ordens')


@login_required
@require_http_methods(["POST"])
def producao_ordem_atualizar_progresso(request, id):
    """Atualizar progresso da ordem de produção (quantidade produzida)"""
    ordem = get_object_or_404(OrdemProducao, id=id)
    
    try:
        quantidade_produzida = request.POST.get('quantidade_produzida', '').strip()
        
        if not quantidade_produzida:
            messages.error(request, 'Quantidade produzida é obrigatória.')
            return redirect('producao:ordem_detail', id=id)
        
        try:
            quantidade_produzida_int = int(quantidade_produzida)
        except (ValueError, TypeError):
            messages.error(request, 'Quantidade produzida deve ser um número válido.')
            return redirect('producao:ordem_detail', id=id)
        
        if quantidade_produzida_int < 0:
            messages.error(request, 'Quantidade produzida não pode ser negativa.')
            return redirect('producao:ordem_detail', id=id)
        
        if quantidade_produzida_int > ordem.quantidade:
            messages.error(request, f'Quantidade produzida ({quantidade_produzida_int}) não pode ser maior que a quantidade planejada ({ordem.quantidade}).')
            return redirect('producao:ordem_detail', id=id)
        
        with transaction.atomic():
            ordem.quantidade_produzida = quantidade_produzida_int
            
            # Atualizar status automaticamente
            if quantidade_produzida_int == 0 and ordem.status != 'RASCUNHO':
                # Se voltou para 0, manter status atual (pode ser planejada)
                pass
            elif quantidade_produzida_int > 0 and ordem.status == 'RASCUNHO':
                # Se começou a produzir, mudar para em produção
                ordem.status = 'EM_PRODUCAO'
                if not ordem.data_inicio:
                    ordem.data_inicio = timezone.now()
            elif quantidade_produzida_int >= ordem.quantidade:
                # Se completou, marcar como concluída
                ordem.status = 'CONCLUIDA'
                ordem.quantidade_produzida = ordem.quantidade  # Garantir que não ultrapasse
                if not ordem.data_conclusao:
                    ordem.data_conclusao = timezone.now()
            
            ordem.save()
            
            messages.success(request, f'Progresso atualizado: {quantidade_produzida_int} de {ordem.quantidade} unidades produzidas.')
            
    except Exception as e:
        logger.error(f"Erro ao atualizar progresso da ordem {id}: {e}", exc_info=True)
        messages.error(request, f'Erro ao atualizar progresso: {str(e)}')
    
    return redirect('producao:ordem_detail', id=id)


@login_required
@require_http_methods(["POST"])
def producao_ordem_alterar_status(request, id):
    """Alterar status da ordem de produção (iniciar, pausar, finalizar)"""
    ordem = get_object_or_404(OrdemProducao, id=id)
    
    try:
        nova_acao = request.POST.get('acao', '').strip()
        
        with transaction.atomic():
            if nova_acao == 'iniciar':
                if ordem.status in ['CONCLUIDA', 'CANCELADA']:
                    messages.error(request, 'Não é possível iniciar uma ordem concluída ou cancelada.')
                    return redirect('producao:ordem_detail', id=id)
                
                ordem.status = 'EM_PRODUCAO'
                if not ordem.data_inicio:
                    ordem.data_inicio = timezone.now()
                messages.success(request, f'Ordem {ordem.codigo} iniciada com sucesso.')
                
            elif nova_acao == 'pausar':
                if ordem.status != 'EM_PRODUCAO':
                    messages.error(request, 'Apenas ordens em produção podem ser pausadas.')
                    return redirect('producao:ordem_detail', id=id)
                
                ordem.status = 'PAUSADA'
                messages.success(request, f'Ordem {ordem.codigo} pausada.')
                
            elif nova_acao == 'retomar':
                if ordem.status != 'PAUSADA':
                    messages.error(request, 'Apenas ordens pausadas podem ser retomadas.')
                    return redirect('producao:ordem_detail', id=id)
                
                ordem.status = 'EM_PRODUCAO'
                messages.success(request, f'Ordem {ordem.codigo} retomada.')
                
            elif nova_acao == 'finalizar':
                if ordem.status not in ['EM_PRODUCAO', 'PAUSADA']:
                    messages.error(request, 'Apenas ordens em produção ou pausadas podem ser finalizadas.')
                    return redirect('producao:ordem_detail', id=id)
                
                ordem.status = 'CONCLUIDA'
                ordem.quantidade_produzida = ordem.quantidade  # Completar quantidade
                if not ordem.data_conclusao:
                    ordem.data_conclusao = timezone.now()
                messages.success(request, f'Ordem {ordem.codigo} finalizada com sucesso.')
                
            else:
                messages.error(request, 'Ação inválida.')
                return redirect('producao:ordem_detail', id=id)
            
            ordem.save()
            
    except Exception as e:
        logger.error(f"Erro ao alterar status da ordem {id}: {e}", exc_info=True)
        messages.error(request, f'Erro ao alterar status: {str(e)}')
    
    return redirect('producao:ordem_detail', id=id)


@login_required
@require_http_methods(["POST"])
def producao_ordem_toggle_etapa(request, id, etapa_id):
    """Marcar/desmarcar etapa como concluída"""
    ordem = get_object_or_404(OrdemProducao, id=id)
    etapa = get_object_or_404(EtapaProcesso, id=etapa_id)
    
    # Verificar se a etapa pertence ao processo da ordem
    if ordem.processo and etapa.processo != ordem.processo:
        messages.error(request, 'Esta etapa não pertence ao processo desta ordem.')
        return redirect('producao:ordem_detail', id=id)
    
    try:
        with transaction.atomic():
            # Verificar se já está concluída
            etapa_concluida = EtapaOrdemConcluida.objects.filter(ordem=ordem, etapa=etapa).first()
            
            if etapa_concluida:
                # Desmarcar como concluída
                etapa_concluida.delete()
                messages.success(request, f'Etapa "{etapa.nome}" desmarcada como concluída.')
            else:
                # Marcar como concluída
                EtapaOrdemConcluida.objects.create(
                    ordem=ordem,
                    etapa=etapa,
                    concluida_por=request.user,
                    observacoes=request.POST.get('observacoes', '').strip()
                )
                messages.success(request, f'Etapa "{etapa.nome}" marcada como concluída.')
            
            # Atualizar quantidade produzida baseado no progresso das etapas (opcional)
            # Se todas as etapas estiverem concluídas, pode sugerir completar a ordem
            if ordem.processo:
                total_etapas = ordem.processo.etapas.count()
                etapas_concluidas = ordem.etapas_concluidas.count()
                
                if etapas_concluidas == total_etapas and total_etapas > 0:
                    # Todas as etapas concluídas - sugerir completar quantidade
                    if ordem.quantidade_produzida < ordem.quantidade:
                        messages.info(request, f'Todas as etapas foram concluídas! Considere atualizar a quantidade produzida para {ordem.quantidade}.')
            
    except Exception as e:
        logger.error(f"Erro ao atualizar etapa da ordem {id}: {e}", exc_info=True)
        messages.error(request, f'Erro ao atualizar etapa: {str(e)}')
    
    return redirect('producao:ordem_detail', id=id)


@login_required
def producao_receita_documentos(request, receita_id):
    """Exibe uma página dedicada para mostrar os documentos PDF da receita"""
    receita = get_object_or_404(Receita, id=receita_id)
    
    context = {
        'receita': receita,
    }
    
    return render(request, 'producao/receitas/documentos.html', context)


@login_required
def producao_receita_projeto(request, receita_id):
    """Exibe uma página dedicada para mostrar o projeto PDF da receita"""
    receita = get_object_or_404(Receita, id=receita_id)
    
    context = {
        'receita': receita,
    }
    
    return render(request, 'producao/receitas/projeto.html', context)


@login_required
@xframe_options_sameorigin
def producao_receita_plano_corte_pdf_view(request, receita_id):
    """Servir PDF do plano de corte da receita permitindo exibição em iframe"""
    from django.http import HttpResponse
    
    try:
        receita = get_object_or_404(Receita, id=receita_id)
        logger.info(f"Receita encontrada: {receita_id} - {receita.nome}")
        
        if not receita.plano_corte_pdf:
            logger.warning(f"Receita {receita_id} não tem plano_corte_pdf")
            html_error = """
            <!DOCTYPE html>
            <html>
            <head><title>PDF não encontrado</title></head>
            <body style="font-family: Arial; text-align: center; padding: 50px;">
                <h2>PDF não encontrado</h2>
                <p>Esta receita não possui um plano de corte PDF anexado.</p>
            </body>
            </html>
            """
            response = HttpResponse(html_error, content_type='text/html')
            response['X-Frame-Options'] = 'SAMEORIGIN'
            return response
        
        # Tentar usar o método path do FileField
        try:
            if not receita.plano_corte_pdf.name:
                logger.warning(f"Receita {receita_id} tem plano_corte_pdf mas sem nome")
                html_error = """
                <!DOCTYPE html>
                <html>
                <head><title>PDF não encontrado</title></head>
                <body style="font-family: Arial; text-align: center; padding: 50px;">
                    <h2>PDF não encontrado</h2>
                    <p>Esta receita não possui um plano de corte PDF válido anexado.</p>
                </body>
                </html>
                """
                response = HttpResponse(html_error, content_type='text/html')
                response['X-Frame-Options'] = 'SAMEORIGIN'
                return response
            
            pdf_path = receita.plano_corte_pdf.path
            logger.info(f"Tentando servir plano de corte PDF do caminho: {pdf_path}")
            
            if not os.path.exists(pdf_path):
                logger.warning(f"Arquivo PDF não existe no caminho: {pdf_path}")
                try:
                    receita.plano_corte_pdf.open('rb')
                    file_content = receita.plano_corte_pdf.read()
                    receita.plano_corte_pdf.close()
                    
                    response = HttpResponse(file_content, content_type='application/pdf')
                    response['X-Frame-Options'] = 'SAMEORIGIN'
                    filename = receita.plano_corte_pdf.name.split('/')[-1]
                    response['Content-Disposition'] = f'inline; filename="{filename}"'
                    logger.info(f"Plano de corte PDF servido via storage com sucesso")
                    return response
                except Exception as storage_error:
                    logger.error(f"Erro ao ler arquivo via storage: {storage_error}")
                    html_error = f"""
                    <!DOCTYPE html>
                    <html>
                    <head><title>PDF não encontrado</title></head>
                    <body style="font-family: Arial; text-align: center; padding: 50px;">
                        <h2>Arquivo PDF não encontrado</h2>
                        <p>O arquivo PDF não foi encontrado no sistema de arquivos.</p>
                        <p><small>Caminho esperado: {pdf_path}</small></p>
                        <p><small>Nome do arquivo: {receita.plano_corte_pdf.name}</small></p>
                    </body>
                    </html>
                    """
                    response = HttpResponse(html_error, content_type='text/html')
                    response['X-Frame-Options'] = 'SAMEORIGIN'
                    return response
            
            # Servir o arquivo PDF usando FileResponse
            file_handle = open(pdf_path, 'rb')
            response = FileResponse(
                file_handle,
                content_type='application/pdf'
            )
            response['X-Frame-Options'] = 'SAMEORIGIN'
            filename = os.path.basename(pdf_path) or receita.plano_corte_pdf.name.split('/')[-1]
            response['Content-Disposition'] = f'inline; filename="{filename}"'
            logger.info(f"Plano de corte PDF servido com sucesso: {pdf_path}")
            return response
        except (ValueError, AttributeError) as e:
            logger.info(f"Tentando servir plano de corte PDF via storage para receita {receita_id}: {e}")
            try:
                receita.plano_corte_pdf.open('rb')
                file_content = receita.plano_corte_pdf.read()
                receita.plano_corte_pdf.close()
                
                response = HttpResponse(file_content, content_type='application/pdf')
                response['X-Frame-Options'] = 'SAMEORIGIN'
                filename = receita.plano_corte_pdf.name.split('/')[-1]
                response['Content-Disposition'] = f'inline; filename="{filename}"'
                logger.info(f"Plano de corte PDF servido via storage com sucesso")
                return response
            except Exception as storage_error:
                logger.error(f"Erro ao ler arquivo via storage: {storage_error}")
                html_error = f"""
                <!DOCTYPE html>
                <html>
                <head><title>Erro ao carregar PDF</title></head>
                <body style="font-family: Arial; text-align: center; padding: 50px;">
                    <h2>Erro ao carregar PDF</h2>
                    <p>Não foi possível carregar o arquivo PDF do plano de corte.</p>
                    <p><small>Erro: {str(storage_error)}</small></p>
                </body>
                </html>
                """
                response = HttpResponse(html_error, content_type='text/html')
                response['X-Frame-Options'] = 'SAMEORIGIN'
                return response
    except Http404:
        html_error = """
        <!DOCTYPE html>
        <html>
        <head><title>Receita não encontrada</title></head>
        <body style="font-family: Arial; text-align: center; padding: 50px;">
            <h2>Receita não encontrada</h2>
            <p>A receita solicitada não foi encontrada.</p>
        </body>
        </html>
        """
        response = HttpResponse(html_error, content_type='text/html')
        response['X-Frame-Options'] = 'SAMEORIGIN'
        return response


@login_required
@xframe_options_sameorigin
def producao_receita_pdf_view(request, receita_id):
    """Servir PDF da receita permitindo exibição em iframe"""
    from django.http import HttpResponse
    
    try:
        receita = get_object_or_404(Receita, id=receita_id)
        logger.info(f"Receita encontrada: {receita_id} - {receita.nome}")
        
        if not receita.documento_pdf:
            logger.warning(f"Receita {receita_id} não tem documento_pdf")
            # Retornar resposta HTML em vez de 404 para evitar redirecionamento
            html_error = """
            <!DOCTYPE html>
            <html>
            <head><title>PDF não encontrado</title></head>
            <body style="font-family: Arial; text-align: center; padding: 50px;">
                <h2>PDF não encontrado</h2>
                <p>Esta receita não possui um documento PDF anexado.</p>
            </body>
            </html>
            """
            response = HttpResponse(html_error, content_type='text/html')
            response['X-Frame-Options'] = 'SAMEORIGIN'
            return response
        
        # Tentar usar o método path do FileField
        try:
            # Verificar se o arquivo tem um nome (pode estar vazio mesmo que documento_pdf não seja None)
            if not receita.documento_pdf.name:
                logger.warning(f"Receita {receita_id} tem documento_pdf mas sem nome")
                html_error = """
                <!DOCTYPE html>
                <html>
                <head><title>PDF não encontrado</title></head>
                <body style="font-family: Arial; text-align: center; padding: 50px;">
                    <h2>PDF não encontrado</h2>
                    <p>Esta receita não possui um documento PDF válido anexado.</p>
                </body>
                </html>
                """
                response = HttpResponse(html_error, content_type='text/html')
                response['X-Frame-Options'] = 'SAMEORIGIN'
                return response
            
            pdf_path = receita.documento_pdf.path
            logger.info(f"Tentando servir PDF do caminho: {pdf_path}")
            
            if not os.path.exists(pdf_path):
                logger.warning(f"Arquivo PDF não existe no caminho: {pdf_path}")
                # Tentar via storage como fallback
                logger.info(f"Tentando ler via storage como fallback...")
                try:
                    receita.documento_pdf.open('rb')
                    file_content = receita.documento_pdf.read()
                    receita.documento_pdf.close()
                    
                    response = HttpResponse(file_content, content_type='application/pdf')
                    response['X-Frame-Options'] = 'SAMEORIGIN'
                    filename = receita.documento_pdf.name.split('/')[-1]
                    response['Content-Disposition'] = f'inline; filename="{filename}"'
                    logger.info(f"PDF servido via storage com sucesso (arquivo não existe localmente)")
                    return response
                except Exception as storage_error:
                    logger.error(f"Erro ao ler arquivo via storage: {storage_error}")
                    html_error = f"""
                    <!DOCTYPE html>
                    <html>
                    <head><title>PDF não encontrado</title></head>
                    <body style="font-family: Arial; text-align: center; padding: 50px;">
                        <h2>Arquivo PDF não encontrado</h2>
                        <p>O arquivo PDF não foi encontrado no sistema de arquivos.</p>
                        <p><small>Caminho esperado: {pdf_path}</small></p>
                        <p><small>Nome do arquivo: {receita.documento_pdf.name}</small></p>
                    </body>
                    </html>
                    """
                    response = HttpResponse(html_error, content_type='text/html')
                    response['X-Frame-Options'] = 'SAMEORIGIN'
                    return response
            
            # Servir o arquivo PDF usando FileResponse
            file_handle = open(pdf_path, 'rb')
            response = FileResponse(
                file_handle,
                content_type='application/pdf'
            )
            # Permitir exibição em iframe do mesmo domínio
            response['X-Frame-Options'] = 'SAMEORIGIN'
            filename = os.path.basename(pdf_path) or receita.documento_pdf.name.split('/')[-1]
            response['Content-Disposition'] = f'inline; filename="{filename}"'
            logger.info(f"PDF servido com sucesso: {pdf_path}")
            return response
        except (ValueError, AttributeError) as e:
            # Se o arquivo não está salvo localmente (pode estar em storage remoto)
            # Tentar ler o arquivo através do storage
            logger.info(f"Tentando servir PDF via storage para receita {receita_id}: {e}")
            try:
                receita.documento_pdf.open('rb')
                file_content = receita.documento_pdf.read()
                receita.documento_pdf.close()
                
                response = HttpResponse(file_content, content_type='application/pdf')
                response['X-Frame-Options'] = 'SAMEORIGIN'
                filename = receita.documento_pdf.name.split('/')[-1]
                response['Content-Disposition'] = f'inline; filename="{filename}"'
                logger.info(f"PDF servido via storage com sucesso")
                return response
            except Exception as storage_error:
                logger.error(f"Erro ao ler arquivo via storage: {storage_error}")
                html_error = f"""
                <!DOCTYPE html>
                <html>
                <head><title>Erro ao carregar PDF</title></head>
                <body style="font-family: Arial; text-align: center; padding: 50px;">
                    <h2>Erro ao carregar PDF</h2>
                    <p>Não foi possível carregar o arquivo PDF.</p>
                    <p><small>Erro: {str(storage_error)}</small></p>
                </body>
                </html>
                """
                response = HttpResponse(html_error, content_type='text/html')
                response['X-Frame-Options'] = 'SAMEORIGIN'
                return response
    except Http404:
        # Retornar resposta HTML em vez de levantar Http404 para evitar redirecionamento
        html_error = """
        <!DOCTYPE html>
        <html>
        <head><title>Receita não encontrada</title></head>
        <body style="font-family: Arial; text-align: center; padding: 50px;">
            <h2>Receita não encontrada</h2>
            <p>A receita solicitada não foi encontrada.</p>
        </body>
        </html>
        """
        response = HttpResponse(html_error, content_type='text/html', status=404)
        response['X-Frame-Options'] = 'SAMEORIGIN'
        return response
    except Exception as e:
        logger.error(f"Erro ao servir PDF da receita {receita_id}: {e}", exc_info=True)
        html_error = f"""
        <!DOCTYPE html>
        <html>
        <head><title>Erro</title></head>
        <body style="font-family: Arial; text-align: center; padding: 50px;">
            <h2>Erro ao carregar PDF</h2>
            <p>Ocorreu um erro ao tentar carregar o PDF.</p>
            <p><small>Erro: {str(e)}</small></p>
        </body>
        </html>
        """
        response = HttpResponse(html_error, content_type='text/html', status=500)
        response['X-Frame-Options'] = 'SAMEORIGIN'
        return response


@login_required
@require_http_methods(["GET", "POST"])
def producao_processo_add(request):
    """Adicionar novo processo de produção"""
    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        descricao = request.POST.get('descricao', '').strip()
        receita_id = request.POST.get('receita')
        status = request.POST.get('status', 'RASCUNHO')
        observacoes = request.POST.get('observacoes', '').strip()
        
        # Validação
        if not nome:
            messages.error(request, 'Nome é obrigatório.')
            return redirect('producao:processo_add')
        
        try:
            with transaction.atomic():
                # Criar processo
                processo = ProcessoProducao(
                    nome=nome,
                    codigo='',  # Será gerado automaticamente
                    descricao=descricao,
                    status=status,
                    observacoes=observacoes,
                    criado_por=request.user
                )
                
                processo.save()
                
                # Processar receitas (ManyToMany)
                receitas_str = request.POST.get('receitas', '').strip()
                if receitas_str:
                    receitas_ids = [int(id) for id in receitas_str.split(',') if id.strip()]
                    if receitas_ids:
                        receitas = Receita.objects.filter(id__in=receitas_ids)
                        processo.receitas.set(receitas)
                    else:
                        processo.receitas.clear()
                else:
                    processo.receitas.clear()
                
                # Processar etapas
                etapas_data = request.POST.get('etapas', '[]')
                if etapas_data and etapas_data.strip() != '[]':
                    try:
                        import json
                        etapas_json = json.loads(etapas_data)
                        for etapa_data in etapas_json:
                            etapa_nome = etapa_data.get('nome', '').strip()
                            etapa_descricao = etapa_data.get('descricao', '').strip()
                            etapa_ordem = etapa_data.get('ordem', 1)
                            etapa_tempo = etapa_data.get('tempo_estimado', 0)
                            etapa_responsavel_id = etapa_data.get('responsavel')
                            
                            if etapa_nome:
                                EtapaProcesso.objects.create(
                                    processo=processo,
                                    nome=etapa_nome,
                                    descricao=etapa_descricao,
                                    ordem=int(etapa_ordem),
                                    tempo_estimado=Decimal(str(etapa_tempo)),
                                    responsavel=User.objects.get(id=etapa_responsavel_id) if etapa_responsavel_id else None
                                )
                    except (json.JSONDecodeError, ValueError, User.DoesNotExist) as e:
                        logger.warning(f"Erro ao processar etapas: {e}")
                        messages.warning(request, 'Algumas etapas não puderam ser adicionadas.')
                
                # Recalcular tempo total
                processo.save()
                
                messages.success(request, 'Processo de produção adicionado com sucesso.')
                return redirect('producao:processos')
        except Receita.DoesNotExist:
            messages.error(request, 'Receita selecionada não encontrada.')
        except Exception as e:
            logger.error(f"Erro ao adicionar processo: {e}", exc_info=True)
            messages.error(request, f'Erro ao adicionar processo: {str(e)}')
    
    context = {
        'receitas': Receita.objects.filter(status__in=['ATIVA', 'APROVADA']).order_by('nome'),
        'status_choices': ProcessoProducao.STATUS_CHOICES,
        'usuarios': User.objects.filter(is_active=True).order_by('username'),
    }
    return render(request, 'producao/processos/form.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def producao_processo_edit(request, id):
    """Editar processo de produção"""
    processo = get_object_or_404(ProcessoProducao.objects.prefetch_related('etapas'), id=id)
    
    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        descricao = request.POST.get('descricao', '').strip()
        receita_id = request.POST.get('receita')
        status = request.POST.get('status', 'RASCUNHO')
        observacoes = request.POST.get('observacoes', '').strip()
        
        # Validação
        if not nome:
            messages.error(request, 'Nome é obrigatório.')
            return redirect('producao:processo_edit', id=id)
        
        try:
            with transaction.atomic():
                # Atualizar processo
                processo.nome = nome
                processo.descricao = descricao
                processo.status = status
                processo.observacoes = observacoes
                
                processo.save()
                
                # Processar receitas (ManyToMany)
                receitas_str = request.POST.get('receitas', '').strip()
                if receitas_str:
                    receitas_ids = [int(id) for id in receitas_str.split(',') if id.strip()]
                    if receitas_ids:
                        receitas = Receita.objects.filter(id__in=receitas_ids)
                        processo.receitas.set(receitas)
                    else:
                        processo.receitas.clear()
                else:
                    processo.receitas.clear()
                
                # Remover etapas existentes
                processo.etapas.all().delete()
                
                # Adicionar novas etapas
                etapas_data = request.POST.get('etapas', '[]')
                if etapas_data and etapas_data.strip() != '[]':
                    try:
                        import json
                        etapas_json = json.loads(etapas_data)
                        for etapa_data in etapas_json:
                            etapa_nome = etapa_data.get('nome', '').strip()
                            etapa_descricao = etapa_data.get('descricao', '').strip()
                            etapa_ordem = etapa_data.get('ordem', 1)
                            etapa_tempo = etapa_data.get('tempo_estimado', 0)
                            etapa_responsavel_id = etapa_data.get('responsavel')
                            
                            if etapa_nome:
                                EtapaProcesso.objects.create(
                                    processo=processo,
                                    nome=etapa_nome,
                                    descricao=etapa_descricao,
                                    ordem=int(etapa_ordem),
                                    tempo_estimado=Decimal(str(etapa_tempo)),
                                    responsavel=User.objects.get(id=etapa_responsavel_id) if etapa_responsavel_id else None
                                )
                    except (json.JSONDecodeError, ValueError, User.DoesNotExist) as e:
                        logger.warning(f"Erro ao processar etapas: {e}")
                        messages.warning(request, 'Algumas etapas não puderam ser adicionadas.')
                
                # Recalcular tempo total
                processo.save()
                
                messages.success(request, 'Processo de produção atualizado com sucesso.')
                return redirect('producao:processos')
        except Receita.DoesNotExist:
            messages.error(request, 'Receita selecionada não encontrada.')
        except Exception as e:
            logger.error(f"Erro ao editar processo {id}: {e}", exc_info=True)
            messages.error(request, f'Erro ao atualizar processo: {str(e)}')
    
    context = {
        'processo': processo,
        'receitas': Receita.objects.filter(status__in=['ATIVA', 'APROVADA']).order_by('nome'),
        'status_choices': ProcessoProducao.STATUS_CHOICES,
        'usuarios': User.objects.filter(is_active=True).order_by('username'),
    }
    return render(request, 'producao/processos/form.html', context)


@login_required
def producao_processo_detail(request, id):
    """Detalhes do processo de produção"""
    try:
        processo = get_object_or_404(ProcessoProducao.objects.select_related(
            'receita', 'receita__produto', 'criado_por'
        ).prefetch_related('etapas__responsavel'), id=id)
        
        context = {
            'processo': processo,
        }
        return render(request, 'producao/processos/detail.html', context)
    except Exception as e:
        logger.error(f"Erro ao exibir detalhes do processo {id}: {e}", exc_info=True)
        messages.error(request, 'Erro ao carregar detalhes do processo.')
        return redirect('producao:processos')


@login_required
@require_http_methods(["POST"])
def producao_processo_delete(request, id):
    """Deletar processo de produção"""
    processo = get_object_or_404(ProcessoProducao, id=id)
    
    try:
        codigo_processo = processo.codigo
        processo.delete()
        messages.success(request, f'Processo de produção {codigo_processo} deletado com sucesso.')
    except Exception as e:
        logger.error(f"Erro ao deletar processo de produção {id}: {e}", exc_info=True)
        messages.error(request, f'Erro ao deletar processo: {str(e)}')
    
    return redirect('producao:processos')


# ========== PROPOSTAS TÉCNICAS ==========

@login_required
def producao_propostas_tecnicas(request):
    """Lista todas as propostas técnicas com filtros"""
    from .models_stock import PropostaTecnica
    
    propostas = PropostaTecnica.objects.select_related(
        'cliente', 'sucursal', 'responsavel', 'criado_por'
    ).all()
    
    # Filtros
    status_filter = request.GET.get('status')
    estagio_filter = request.GET.get('estagio')
    cliente_filter = request.GET.get('cliente')
    
    if status_filter:
        propostas = propostas.filter(status=status_filter)
    if estagio_filter:
        propostas = propostas.filter(estagio_atual=estagio_filter)
    if cliente_filter:
        propostas = propostas.filter(cliente__nome__icontains=cliente_filter)

    from django.utils import timezone
    hoje = timezone.now().date()
    em_andamento_count = propostas.filter(status='EM_ANDAMENTO').count()
    atrasadas_count = propostas.exclude(status__in=['CONCLUIDA', 'CANCELADA']).filter(
        data_fim_prevista__lt=hoje
    ).count()
    concluidas_count = propostas.filter(status='CONCLUIDA').count()

    context = {
        'propostas': propostas,
        'status_choices': PropostaTecnica.STATUS_CHOICES,
        'estagio_choices': PropostaTecnica.ESTAGIO_CHOICES,
        'status_filter': status_filter,
        'estagio_filter': estagio_filter,
        'cliente_filter': cliente_filter,
        'em_andamento_count': em_andamento_count,
        'atrasadas_count': atrasadas_count,
        'concluidas_count': concluidas_count,
    }
    return render(request, 'producao/propostas_tecnicas/list.html', context)


@login_required
def producao_proposta_tecnica_add(request):
    """Adicionar nova proposta técnica"""
    from .models_stock import PropostaTecnica, ClienteServico, Sucursal, TaxaServicoCategoria
    from django.contrib.auth.models import User
    modo_levantamento = bool(getattr(request, '_modo_levantamento', False))
    
    if request.method == 'POST':
        try:
            # Obter cliente_id ou null
            cliente_id = request.POST.get('cliente')
            if cliente_id == '' or cliente_id is None:
                cliente_id = None
            
            # Obter sucursal do usuário logado (automático)
            sucursal_id = None
            if hasattr(request.user, 'perfil_usuario') and request.user.perfil_usuario.sucursal:
                sucursal_id = request.user.perfil_usuario.sucursal.id
            elif hasattr(request.user, 'funcionario') and request.user.funcionario.sucursal:
                sucursal_id = request.user.funcionario.sucursal.id
            
            # Convert string dates to date objects if provided
            data_inicio = None
            data_fim = None
            if request.POST.get('data_inicio_prevista'):
                try:
                    from datetime import datetime
                    data_inicio = datetime.strptime(request.POST.get('data_inicio_prevista'), '%Y-%m-%d').date()
                except ValueError:
                    data_inicio = None
            
            if request.POST.get('data_fim_prevista'):
                try:
                    from datetime import datetime
                    data_fim = datetime.strptime(request.POST.get('data_fim_prevista'), '%Y-%m-%d').date()
                except ValueError:
                    data_fim = None

            proposta = PropostaTecnica(
                titulo=request.POST.get('titulo'),
                escopo=request.POST.get('escopo'),
                cliente_id=cliente_id,
                nome_cliente_personalizado=request.POST.get('nome_cliente_personalizado'),
                nuit_cliente_personalizado=request.POST.get('nuit_cliente_personalizado'),
                telefone_cliente_personalizado=request.POST.get('telefone_cliente_personalizado'),
                sucursal_id=sucursal_id,  # Automático baseado no usuário
                responsavel_id=request.POST.get('responsavel') or None,
                data_inicio_prevista=data_inicio,
                data_fim_prevista=data_fim,
                duracao_prevista_horas=request.POST.get('duracao_prevista_horas') or None,
                valor_levantamento_previsto=request.POST.get('valor_levantamento_previsto') or None,
                observacoes=request.POST.get('observacoes'),
                criado_por=request.user,
            )
            proposta.save()
            
            if modo_levantamento:
                messages.success(request, f'Levantamento em obra {proposta.codigo} criado com sucesso!')
            else:
                messages.success(request, f'Proposta técnica {proposta.codigo} criada com sucesso!')
            return redirect('producao:proposta_tecnica_detail', id=proposta.id)
            
        except Exception as e:
            messages.error(request, f'Erro ao criar proposta: {str(e)}')
    
    context = {
        'clientes': ClienteServico.objects.all().order_by('nome'),
        'responsaveis': User.objects.filter(is_active=True).order_by('first_name'),
        'status_choices': PropostaTecnica.STATUS_CHOICES,
        'estagio_choices': PropostaTecnica.ESTAGIO_CHOICES,
        'taxas_categoria': {taxa.categoria: float(taxa.taxa_horaria) for taxa in TaxaServicoCategoria.objects.filter(ativo=True)},
        'modo_levantamento': modo_levantamento,
    }
    return render(request, 'producao/propostas_tecnicas/form.html', context)


@login_required
def producao_levantamento_obra_add(request):
    """Nova funcionalidade: tela dedicada para levantamento em obra."""
    return render(request, 'producao/levantamentos/obras/add.html', {})


@login_required
def producao_proposta_tecnica_detail(request, id):
    """Detalhes da proposta técnica"""
    from .models_stock import PropostaTecnica
    
    proposta = get_object_or_404(PropostaTecnica, id=id)
    
    # Calcular o índice do estágio atual
    estagio_atual_index = 0
    for i, (value, label) in enumerate(PropostaTecnica.ESTAGIO_CHOICES):
        if value == proposta.estagio_atual:
            estagio_atual_index = i
            break
    
    context = {
        'proposta': proposta,
        'estagio_choices': PropostaTecnica.ESTAGIO_CHOICES,
        'estagio_midpoint': estagio_atual_index,
    }
    return render(request, 'producao/propostas_tecnicas/detail.html', context)


@login_required
def producao_proposta_tecnica_edit(request, id):
    """Editar proposta técnica"""
    from .models_stock import PropostaTecnica, ClienteServico, Sucursal, TaxaServicoCategoria
    from django.contrib.auth.models import User
    
    proposta = get_object_or_404(PropostaTecnica, id=id)
    
    if request.method == 'POST':
        try:
            # Obter cliente_id ou null
            cliente_id = request.POST.get('cliente')
            if cliente_id == '' or cliente_id is None:
                cliente_id = None
            
            # Obter sucursal do usuário logado (automático)
            sucursal_id = None
            if hasattr(request.user, 'perfil_usuario') and request.user.perfil_usuario.sucursal:
                sucursal_id = request.user.perfil_usuario.sucursal.id
            elif hasattr(request.user, 'funcionario') and request.user.funcionario.sucursal:
                sucursal_id = request.user.funcionario.sucursal.id
            
            proposta.titulo = request.POST.get('titulo')
            proposta.escopo = request.POST.get('escopo')
            proposta.cliente_id = cliente_id
            proposta.nome_cliente_personalizado = request.POST.get('nome_cliente_personalizado')
            proposta.nuit_cliente_personalizado = request.POST.get('nuit_cliente_personalizado')
            proposta.telefone_cliente_personalizado = request.POST.get('telefone_cliente_personalizado')
            proposta.sucursal_id = sucursal_id  # Automático baseado no usuário
            proposta.responsavel_id = request.POST.get('responsavel') or None
            # Convert string dates to date objects if provided
            if request.POST.get('data_inicio_prevista'):
                try:
                    from datetime import datetime
                    proposta.data_inicio_prevista = datetime.strptime(request.POST.get('data_inicio_prevista'), '%Y-%m-%d').date()
                except ValueError:
                    proposta.data_inicio_prevista = None
            else:
                proposta.data_inicio_prevista = None
            
            if request.POST.get('data_fim_prevista'):
                try:
                    from datetime import datetime
                    proposta.data_fim_prevista = datetime.strptime(request.POST.get('data_fim_prevista'), '%Y-%m-%d').date()
                except ValueError:
                    proposta.data_fim_prevista = None
            else:
                proposta.data_fim_prevista = None
            proposta.duracao_prevista_horas = request.POST.get('duracao_prevista_horas') or None
            proposta.valor_levantamento_previsto = request.POST.get('valor_levantamento_previsto') or None
            proposta.observacoes = request.POST.get('observacoes')
            
            proposta.save()
            
            messages.success(request, f'Proposta técnica {proposta.codigo} atualizada com sucesso!')
            return redirect('producao:proposta_tecnica_detail', id=proposta.id)
            
        except Exception as e:
            messages.error(request, f'Erro ao atualizar proposta: {str(e)}')
    
    context = {
        'proposta': proposta,
        'clientes': ClienteServico.objects.all().order_by('nome'),
        'sucursais': Sucursal.objects.all().order_by('nome'),
        'responsaveis': User.objects.filter(is_active=True).order_by('first_name'),
        'status_choices': PropostaTecnica.STATUS_CHOICES,
        'estagio_choices': PropostaTecnica.ESTAGIO_CHOICES,
    }
    return render(request, 'producao/propostas_tecnicas/form.html', context)


@login_required
def producao_proposta_tecnica_delete(request, id):
    """Excluir proposta técnica"""
    from .models_stock import PropostaTecnica
    
    proposta = get_object_or_404(PropostaTecnica, id=id)
    
    if request.method == 'POST':
        codigo = proposta.codigo
        proposta.delete()
        messages.success(request, f'Proposta técnica {codigo} excluída com sucesso!')
        return redirect('producao:propostas_tecnicas')
    
    context = {'proposta': proposta}
    return render(request, 'producao/propostas_tecnicas/delete_confirm.html', context)


@login_required
def producao_proposta_tecnica_mudar_estagio(request, id):
    """Mudar estágio da proposta técnica"""
    from .models_stock import PropostaTecnica
    
    proposta = get_object_or_404(PropostaTecnica, id=id)
    
    if request.method == 'POST':
        novo_estagio = request.POST.get('novo_estagio')
        if novo_estagio in [choice[0] for choice in PropostaTecnica.ESTAGIO_CHOICES]:
            proposta.estagio_atual = novo_estagio
            proposta.save()
            
            messages.success(request, f'Estágio atualizado para {proposta.get_estagio_atual_display()}!')
        else:
            messages.error(request, 'Estágio inválido!')
        
        return redirect('producao:proposta_tecnica_detail', id=proposta.id)
    
    # Encontrar o índice do estágio atual
    estagio_atual_index = 0
    for i, (value, label) in enumerate(PropostaTecnica.ESTAGIO_CHOICES):
        if value == proposta.estagio_atual:
            estagio_atual_index = i
            break
    
    context = {
        'proposta': proposta,
        'estagio_choices': PropostaTecnica.ESTAGIO_CHOICES,
        'estagio_midpoint': estagio_atual_index,
    }
    return render(request, 'producao/propostas_tecnicas/mudar_estagio.html', context)


def _build_cronograma_propostas_tecnicas(data_inicio, data_fim, status_filter=None, estagio_filter=None, cliente_filter=None):
    """Constrói contexto do cronograma de propostas técnicas (server-side, estilo Finanças)."""
    from .models_stock import PropostaTecnica
    from datetime import date, timedelta
    from django.utils import timezone
    from django.urls import reverse

    hoje = timezone.now().date()
    # Propostas com período previsto que cruza [data_inicio, data_fim]
    qs = PropostaTecnica.objects.filter(
        data_inicio_prevista__isnull=False,
        data_inicio_prevista__lte=data_fim,
    ).filter(
        Q(data_fim_prevista__gte=data_inicio) |
        Q(data_fim_prevista__isnull=True, data_inicio_prevista__gte=data_inicio)
    )
    if status_filter:
        qs = qs.filter(status=status_filter)
    if estagio_filter:
        qs = qs.filter(estagio_atual=estagio_filter)
    if cliente_filter and cliente_filter.strip():
        qs = qs.filter(
            Q(cliente__nome__icontains=cliente_filter.strip()) |
            Q(nome_cliente_personalizado__icontains=cliente_filter.strip())
        )
    qs = qs.select_related('cliente', 'responsavel').order_by('data_inicio_prevista')

    gantt_min = data_inicio - timedelta(days=3)
    gantt_max = data_fim + timedelta(days=14)
    total_days = max(1, (gantt_max - gantt_min).days)

    # Ticks: primeiro e último dia + primeiro de cada mês (como Finanças)
    gantt_ticks = [{'date': gantt_min, 'pct': 0.0}, {'date': gantt_max, 'pct': 100.0}]
    y, m = gantt_min.year, gantt_min.month
    while True:
        first_of_month = date(y, m, 1)
        if first_of_month <= gantt_min:
            y, m = (y, m + 1) if m < 12 else (y + 1, 1)
            continue
        if first_of_month >= gantt_max:
            break
        pct = (first_of_month - gantt_min).days / total_days * 100
        gantt_ticks.append({'date': first_of_month, 'pct': round(pct, 1)})
        m += 1
        if m > 12:
            m, y = 1, y + 1
    gantt_ticks.sort(key=lambda x: x['date'])
    seen_pct = set()
    out = []
    for t in gantt_ticks:
        p = round(t['pct'], 1)
        if t['date'] == gantt_max:
            p = 100.0
        elif p >= 97.0:
            continue
        if p not in seen_pct or t['date'] == gantt_min or t['date'] == gantt_max:
            seen_pct.add(p)
            out.append({'date': t['date'], 'pct': p})
    gantt_ticks = out

    hoje_pct = None
    if gantt_min <= hoje <= gantt_max:
        hoje_pct = round((hoje - gantt_min).days / total_days * 100, 1)

    cronograma_propostas = []
    for proposta in qs:
        start = proposta.data_inicio_prevista
        end = proposta.data_fim_prevista or proposta.data_inicio_prevista
        start_clamp = max(start, gantt_min)
        end_clamp = min(end, gantt_max)
        left_pct = (start_clamp - gantt_min).days / total_days * 100
        width_pct = (end_clamp - start_clamp).days / total_days * 100
        width_pct = max(1.0, min(100 - left_pct, width_pct))
        left_pct = round(left_pct, 1)
        width_pct = round(width_pct, 1)
        style = f"left: {left_pct}%; width: {width_pct}%;"
        cliente_nome = proposta.cliente.nome if proposta.cliente else (proposta.nome_cliente_personalizado or '—')
        label = f"{proposta.codigo} - {proposta.titulo}"
        status_slug = (proposta.status or '').lower().replace(' ', '_')
        cronograma_propostas.append({
            'id': proposta.id,
            'url': reverse('producao:proposta_tecnica_detail', args=[proposta.id]),
            'label': label,
            'cliente': cliente_nome,
            'estagio_display': proposta.get_estagio_atual_display(),
            'data_inicio': start,
            'data_fim': end,
            'style': style,
            'left_pct': left_pct,
            'width_pct': width_pct,
            'status_slug': status_slug or 'disponivel',
        })

    gantt_scale_min_px = max(800, min(4000, total_days * 8))

    return {
        'cronograma_propostas': cronograma_propostas,
        'gantt_min_date': gantt_min,
        'gantt_max_date': gantt_max,
        'gantt_ticks': gantt_ticks,
        'gantt_hoje_pct': hoje_pct,
        'has_hoje_line': hoje_pct is not None,
        'gantt_scale_min_px': gantt_scale_min_px,
    }


@login_required
def producao_propostas_tecnicas_cronograma(request):
    """Cronograma/plano de trabalho de propostas técnicas (server-side, como Finanças)."""
    from .models_stock import PropostaTecnica
    from datetime import timedelta
    from django.utils import timezone

    now = timezone.now().date()
    data_inicio = now - timedelta(days=30)
    data_fim = now + timedelta(days=120)
    if request.GET.get('data_inicio'):
        try:
            data_inicio = timezone.datetime.strptime(request.GET['data_inicio'], '%Y-%m-%d').date()
        except ValueError:
            pass
    if request.GET.get('data_fim'):
        try:
            data_fim = timezone.datetime.strptime(request.GET['data_fim'], '%Y-%m-%d').date()
        except ValueError:
            pass
    if data_fim < data_inicio:
        data_fim = data_inicio + timedelta(days=90)

    status_filter = request.GET.get('status') or None
    estagio_filter = request.GET.get('estagio') or None
    cliente_filter = request.GET.get('cliente') or None

    ctx = _build_cronograma_propostas_tecnicas(data_inicio, data_fim, status_filter, estagio_filter, cliente_filter)
    context = {
        'status_choices': PropostaTecnica.STATUS_CHOICES,
        'estagio_choices': PropostaTecnica.ESTAGIO_CHOICES,
        'data_inicio': data_inicio.isoformat(),
        'data_fim': data_fim.isoformat(),
        'filtro_status': status_filter,
        'filtro_estagio': estagio_filter,
        'filtro_cliente': cliente_filter or '',
        **ctx,
    }
    return render(request, 'producao/propostas_tecnicas/cronograma.html', context)


@login_required
def producao_proposta_tecnica_converter_orcamento(request, id):
    """Converter proposta técnica aprovada em orçamento de serviços"""
    from .models_stock import PropostaTecnica, OrdemServico, ClienteServico
    from django.db import transaction
    
    proposta = get_object_or_404(PropostaTecnica, id=id)
    
    # Verificar se já foi convertida
    if proposta.orcamento_servico:
        messages.warning(request, 'Esta proposta já foi convertida em orçamento.')
        return redirect('producao:servico_orcamento_detail', proposta.orcamento_servico.id)
    
    # Verificar se está aprovada
    if proposta.estagio_atual != 'APROVACAO':
        messages.error(request, 'Apenas propostas aprovadas podem ser convertidas em orçamento.')
        return redirect('producao:proposta_tecnica_detail', id=id)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Criar orçamento de serviço
                orcamento = OrdemServico.objects.create(
                    titulo=proposta.titulo,
                    descricao=proposta.escopo or '',
                    cliente=proposta.cliente,
                    sucursal=proposta.sucursal,
                    responsavel=proposta.responsavel,
                    data_agendada=proposta.data_inicio_prevista,
                    valor_total=proposta.valor_levantamento_previsto or 0,
                    observacoes=f"Gerado a partir da proposta técnica {proposta.codigo}\n\n{proposta.observacoes or ''}",
                    status='ORCAMENTO',
                    criado_por=request.user,
                )
                
                # Vincular proposta ao orçamento e marcar como concluída (spec)
                proposta.orcamento_servico = orcamento
                proposta.data_conclusao = timezone.now()
                proposta.status = 'CONCLUIDA'
                proposta.save(update_fields=['orcamento_servico', 'data_conclusao', 'status'])

                # Primeira linha do orçamento = Levantamento (serviço configurado no catálogo)
                from .models_base import ConfiguracaoFiscal
                from .models_stock import ServicoOrcamentoServico
                config_fiscal = ConfiguracaoFiscal.objects.first()
                servico_lev = getattr(config_fiscal, 'servico_levantamento', None) if config_fiscal else None
                if servico_lev and (proposta.valor_levantamento_previsto or proposta.duracao_prevista_horas):
                    qtd = proposta.duracao_prevista_horas or Decimal('1.00')
                    if isinstance(qtd, (int, float)):
                        qtd = Decimal(str(qtd))
                    preco_hora = getattr(servico_lev, 'preco_venda', None) or getattr(servico_lev, 'preco', None) or Decimal('0')
                    if preco_hora and qtd > 0:
                        valor_unit = preco_hora
                    else:
                        valor_unit = (proposta.valor_levantamento_previsto or Decimal('0')) / qtd if qtd else Decimal('0')
                    ServicoOrcamentoServico.objects.create(
                        ordem_servico=orcamento,
                        servico=servico_lev,
                        quantidade=qtd,
                        valor_unitario=valor_unit,
                    )

                # Adiantamento financeiro (conta a receber) para descontar na faturação
                if proposta.valor_levantamento_previsto and proposta.valor_levantamento_previsto > 0:
                    from .models_financas import PendenteContaReceber
                    credor_nome = (proposta.cliente.nome if proposta.cliente else None) or proposta.nome_cliente_personalizado or f"Cliente {proposta.codigo}"
                    PendenteContaReceber.objects.create(
                        credor=credor_nome,
                        valor=proposta.valor_levantamento_previsto,
                        descricao=f"Adiantamento - Levantamento {proposta.codigo}",
                        data_vencimento=timezone.now().date(),
                        origem_tipo='PROPOSTA_TECNICA',
                        origem_id=proposta.id,
                        url_origem=request.build_absolute_uri(reverse('producao:proposta_tecnica_detail', kwargs={'id': proposta.id})),
                    )
                
                messages.success(request, f'Proposta {proposta.codigo} convertida com sucesso no orçamento {orcamento.codigo}!')
                return redirect('producao:servico_orcamento_detail', id=orcamento.id)
                
        except Exception as e:
            messages.error(request, f'Erro ao converter proposta: {str(e)}')
    
    context = {
        'proposta': proposta,
    }
    return render(request, 'producao/propostas_tecnicas/converter_orcamento.html', context)


@login_required
def producao_proposta_tecnica_recibo_levantamento(request, id):
    """Gerar recibo de levantamento vinculado à proposta"""
    from .models_stock import PropostaTecnica
    from .models_base import DadosEmpresa
    from django.template.loader import render_to_string
    from django.conf import settings
    from xhtml2pdf import pisa
    import io
    
    proposta = get_object_or_404(PropostaTecnica, id=id)
    
    if not proposta.valor_levantamento_previsto or proposta.valor_levantamento_previsto <= 0:
        messages.error(request, 'Esta proposta não possui valor de levantamento definido.')
        return redirect('producao:proposta_tecnica_detail', id=id)
    
    dados_empresa = DadosEmpresa.objects.first()
    if not dados_empresa:
        dados_empresa = type('Obj', (), {
            'nome': 'Conception Lda', 'nuit': '401932089',
            'endereco': 'Rua Carlos Cardoso; Quarteirão 20 N. 192', 
            'telefone': '', 'representante_legal': None, 'cargo_representante': ''
        })()
    
    logo_url = ''
    if dados_empresa and getattr(dados_empresa, 'logo', None) and dados_empresa.logo:
        try:
            logo_url = f"{request.scheme}://{request.get_host()}{settings.MEDIA_URL}{dados_empresa.logo.name}"
        except Exception:
            logo_url = ''
    
    try:
        valor_extenso = __import__('num2words', fromlist=['num2words']).num2words(
            float(proposta.valor_levantamento_previsto), lang='pt', to='currency', currency='EUR'
        ).replace('euros', 'meticais').replace('euro', 'metical')
    except Exception:
        valor_extenso = str(proposta.valor_levantamento_previsto)
    
    hoje = timezone.now().date()
    rep = getattr(dados_empresa, 'representante_legal', None)
    
    # Criar objeto cliente compatível com template
    cliente_obj = type('ClienteObj', (), {})()
    if proposta.cliente:
        cliente_obj = proposta.cliente
    elif proposta.nome_cliente_personalizado:
        cliente_obj.nome = proposta.nome_cliente_personalizado
        cliente_obj.nuit = proposta.nuit_cliente_personalizado
        cliente_obj.telefone = proposta.telefone_cliente_personalizado
        cliente_obj.email = None
        cliente_obj.endereco = None
    else:
        cliente_obj.nome = 'Cliente não especificado'
        cliente_obj.nuit = None
        cliente_obj.telefone = None
        cliente_obj.email = None
        cliente_obj.endereco = None

    ctx = {
        'dados_empresa': dados_empresa,
        'logo_url': logo_url,
        'numero_recibo': f"RL-PROPOSTA-{hoje.year}-{proposta.id:06d}",
        'data_emissao': hoje.strftime('%d de %B de %Y'),
        'proposta': proposta,
        'representante_nome': rep.get_full_name() if rep else '',
        'representante_cargo': getattr(dados_empresa, 'cargo_representante', None) or 'Representante Legal',
        'valor': f"{proposta.valor_levantamento_previsto:,.2f}".replace(',', ' ').replace('.', ',').replace(' ', '.'),
        'valor_extenso': valor_extenso,
        'descricao': f"Levantamento técnico - Proposta {proposta.codigo}",
        'cliente': cliente_obj,
    }
    
    html = render_to_string('producao/propostas_tecnicas/recibo_levantamento.html', ctx)
    result = io.BytesIO()
    pisa.CreatePDF(html.encode('utf-8'), dest=result, encoding='utf-8')
    result.seek(0)
    
    response = HttpResponse(result.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="recibo_levantamento_{proposta.codigo}.pdf"'
    return response

