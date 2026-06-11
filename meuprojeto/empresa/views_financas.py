"""
Views do módulo de Finanças — agregação de receitas e despesas dos departamentos.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum
from django.http import HttpResponse
from django.db import transaction
from functools import wraps
from datetime import datetime, timedelta, date
from decimal import Decimal
import csv
import io
import logging

logger = logging.getLogger(__name__)


def _excel_relatorio_organizado(titulo, periodo_str, headers, rows, col_larguras=None,
                                total_row_indices=None, metadata=None, dados_empresa=None):
    """
    Gera um ficheiro Excel com design profissional para relatórios.
    - Cabeçalho da empresa (nome, NUIT, endereço, contacto) quando dados_empresa é passado
    - Título do relatório e período
    - Cabeçalhos de coluna em estilo profissional
    - Linhas alternadas para legibilidade
    - Linhas de total em destaque
    - Rodapé com data de geração
    - Painéis congelados para navegação
    """
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.page import PageMargins

    ncols = len(headers)
    last_col = get_column_letter(ncols)
    total_row_indices = total_row_indices or []

    wb = Workbook()
    ws = wb.active
    ws.title = titulo[:31]

    # Paleta profissional
    HEADER_BG = '1e3a5f'      # Azul escuro corporativo
    HEADER_FONT = 'FFFFFF'
    SUBTITLE_FONT = '5a6c7d'
    ROW_ALT_BG = 'f8fafc'     # Cinza muito claro
    TOTAL_BG = 'e8eef4'       # Cinza azulado para totais
    BORDER_COLOR = 'c5d0de'
    EMPRESA_FONT = '374151'

    thin = Side(style='thin', color=BORDER_COLOR)
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    # Offset quando há cabeçalho da empresa
    offset = 0
    if dados_empresa:
        nome = getattr(dados_empresa, 'nome', None) or 'Conception Lda'
        nuit = getattr(dados_empresa, 'nuit', None) or ''
        endereco = getattr(dados_empresa, 'endereco', None) or ''
        telefone = getattr(dados_empresa, 'telefone', None) or ''
        email = getattr(dados_empresa, 'email', None) or ''
        ws['A1'] = nome
        ws['A1'].font = Font(bold=True, size=14, color=EMPRESA_FONT)
        ws.merge_cells(f'A1:{last_col}1')
        ws.row_dimensions[1].height = 22
        line2 = f'NUIT: {nuit}' if nuit else ''
        if endereco:
            line2 = f'{line2}  |  {endereco}' if line2 else endereco
        if line2:
            ws['A2'] = line2
            ws['A2'].font = Font(size=10, color=SUBTITLE_FONT)
            ws.merge_cells(f'A2:{last_col}2')
        line3 = f'Tel: {telefone}' if telefone else ''
        if email:
            line3 = f'{line3}  |  {email}' if line3 else email
        if line3:
            ws['A3'] = line3
            ws['A3'].font = Font(size=10, color=SUBTITLE_FONT)
            ws.merge_cells(f'A3:{last_col}3')
        offset = 5  # 5 linhas: empresa + vazia

    # Título principal
    r_title = 1 + offset
    ws.cell(row=r_title, column=1, value=titulo)
    ws.cell(row=r_title, column=1).font = Font(bold=True, size=16, color=HEADER_FONT)
    ws.cell(row=r_title, column=1).fill = PatternFill(start_color=HEADER_BG, end_color=HEADER_BG, fill_type='solid')
    ws.cell(row=r_title, column=1).alignment = Alignment(horizontal='left', vertical='center')
    ws.merge_cells(start_row=r_title, start_column=1, end_row=r_title, end_column=ncols)
    ws.row_dimensions[r_title].height = 28

    # Período
    r_period = r_title + 1
    ws.cell(row=r_period, column=1, value=f'Período: {periodo_str}')
    ws.cell(row=r_period, column=1).font = Font(size=11, color=SUBTITLE_FONT)
    ws.merge_cells(start_row=r_period, start_column=1, end_row=r_period, end_column=ncols)

    # Metadata opcional
    r_meta = r_period + 1
    if metadata:
        ws.cell(row=r_meta, column=1, value=metadata)
        ws.cell(row=r_meta, column=1).font = Font(size=10, color=SUBTITLE_FONT)
        ws.merge_cells(start_row=r_meta, start_column=1, end_row=r_meta, end_column=ncols)
        header_row = r_meta + 1
    else:
        header_row = r_meta

    # Cabeçalhos das colunas
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=header_row, column=col, value=h)
        cell.font = Font(bold=True, size=11, color=HEADER_FONT)
        cell.fill = PatternFill(start_color=HEADER_BG, end_color=HEADER_BG, fill_type='solid')
        cell.alignment = Alignment(horizontal='left' if col == 1 else 'right', vertical='center', wrap_text=True)
        cell.border = border
    ws.row_dimensions[header_row].height = 22

    # Dados
    for i, row_data in enumerate(rows):
        r = header_row + 1 + i
        is_total = i in total_row_indices
        for c, val in enumerate(row_data, 1):
            cell = ws.cell(row=r, column=c, value=val)
            if isinstance(val, (int, float)) and val != '':
                cell.number_format = '#,##0.00'
            cell.alignment = Alignment(horizontal='left' if c == 1 else 'right', vertical='center')
            cell.border = border
            if is_total:
                cell.font = Font(bold=True)
                cell.fill = PatternFill(start_color=TOTAL_BG, end_color=TOTAL_BG, fill_type='solid')
            elif i % 2 == 1 and not is_total:
                cell.fill = PatternFill(start_color=ROW_ALT_BG, end_color=ROW_ALT_BG, fill_type='solid')

    last_data_row = header_row + len(rows)

    # Rodapé: data de geração
    footer_row = last_data_row + 2
    ws.cell(row=footer_row, column=1, value=f'Gerado em {timezone.now().strftime("%d/%m/%Y %H:%M")}')
    ws.cell(row=footer_row, column=1).font = Font(size=9, color='9ca3af', italic=True)
    ws.merge_cells(start_row=footer_row, start_column=1, end_row=footer_row, end_column=ncols)

    # Larguras das colunas
    larguras = col_larguras or ([25] + [15] * (ncols - 1))
    for i, w in enumerate(larguras[:ncols], 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # Congelar painéis (cabeçalhos de coluna)
    ws.freeze_panes = ws.cell(row=header_row + 1, column=1)

    # Margens para impressão
    ws.page_margins = PageMargins(left=0.5, right=0.5, top=0.75, bottom=0.75)

    return wb


def require_financas_access(view_func):
    """Decorator: exige login e permissão 'empresa.acesso_financas' (ou is_superuser) para aceder ao módulo Finanças."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())
        if request.user.is_superuser or request.user.has_perm('empresa.acesso_financas'):
            return view_func(request, *args, **kwargs)
        messages.error(request, 'Não tem permissão para aceder ao módulo Finanças.')
        return redirect('dashboard')
    return _wrapped


def _context_empresa(request):
    """Retorna dados_empresa e logo_url para cabeçalho dos relatórios (identidade da empresa)."""
    from .models_base import DadosEmpresa
    from django.conf import settings
    dados_empresa = DadosEmpresa.objects.first()
    if not dados_empresa:
        dados_empresa = type('Obj', (), {
            'nome': 'Conception Lda', 'nuit': '', 'endereco': '', 'telefone': '', 'email': ''
        })()
    logo_url = ''
    if dados_empresa and getattr(dados_empresa, 'logo', None) and dados_empresa.logo:
        try:
            logo_url = f"{request.scheme}://{request.get_host()}{settings.MEDIA_URL}{dados_empresa.logo.name}"
        except Exception:
            logo_url = ''
    return {'dados_empresa': dados_empresa, 'logo_url': logo_url}


def _parse_periodo(request, default_days=365):
    """Extrai data_inicio e data_fim do request (GET ou padrão último N dias)."""
    hoje = timezone.now().date()
    di_str = request.GET.get('data_inicio', '') or request.POST.get('data_inicio', '')
    df_str = request.GET.get('data_fim', '') or request.POST.get('data_fim', '')
    if di_str and df_str:
        try:
            di = datetime.strptime(di_str, '%Y-%m-%d').date()
            df = datetime.strptime(df_str, '%Y-%m-%d').date()
            if di > df:
                di, df = df, di
            return di, df, di_str, df_str
        except (ValueError, TypeError):
            pass
    di = hoje - timedelta(days=default_days)
    df = hoje
    return di, df, di.isoformat(), df.isoformat()


def _receitas_from_lancamentos(di, df):
    """Receitas no período a partir dos lançamentos contabilísticos (reflecte confirmações de recebimento)."""
    from .models_financas import LancamentoFinanceiro
    receitas_71 = LancamentoFinanceiro.objects.filter(
        data__gte=di, data__lte=df, conta__codigo='71.01',
    ).aggregate(s=Sum('valor'))
    receitas_72 = LancamentoFinanceiro.objects.filter(
        data__gte=di, data__lte=df, conta__codigo='72.01',
    ).aggregate(s=Sum('valor'))
    total_v = receitas_71['s'] or Decimal('0.00')
    total_log_r = receitas_72['s'] or Decimal('0.00')
    return total_v, total_log_r


def _compute_totais_periodo(di, df):
    """Calcula totais de receitas e despesas por origem no período (receitas = lançamentos; despesas = fontes operacionais)."""
    from .models_stock import OrdemCompra
    total_v, total_log_r = _receitas_from_lancamentos(di, df)
    total_compras = Decimal('0.00')
    for oc in OrdemCompra.objects.filter(
        data_criacao__date__gte=di, data_criacao__date__lte=df, status='RECEBIDA',
    ).prefetch_related('itens'):
        total_compras += sum(
            item.quantidade_solicitada * (item.preco_unitario or Decimal('0'))
            for item in oc.itens.all()
        )
    total_rh = Decimal('0.00')
    try:
        from .models_financas import LancamentoFinanceiro
        lanc_folha = LancamentoFinanceiro.objects.filter(
            data__gte=di, data__lte=df,
            conta__codigo='62.01', origem_tipo='RH',
        ).aggregate(s=Sum('valor'))
        total_rh = abs(lanc_folha['s'] or Decimal('0.00'))
    except Exception:
        pass
    try:
        from .models_rh import Treinamento
        trein = Treinamento.objects.filter(
            status='CONCLUIDO', custo_total__gt=0,
            data_fim__gte=di, data_fim__lte=df,
        ).aggregate(s=Sum('custo_total'))
        total_rh += trein['s'] or Decimal('0.00')
    except Exception:
        pass
    try:
        from .models_rh import TrabalhoEmpreitada
        emp = TrabalhoEmpreitada.objects.filter(
            status='CONCLUIDO', valor_fixo__gt=0,
            data_conclusao__gte=di, data_conclusao__lte=df,
        ).aggregate(s=Sum('valor_fixo'))
        total_rh += emp['s'] or Decimal('0.00')
    except Exception:
        pass
    total_log_d = Decimal('0.00')
    try:
        from .models_cost_billing import CustoLogistico
        cl = CustoLogistico.objects.filter(
            status='APROVADO', data_custo__gte=di, data_custo__lte=df,
        ).aggregate(s=Sum('valor'))
        total_log_d = cl['s'] or Decimal('0.00')
    except Exception:
        pass
    return {
        'receitas_vendas': total_v,
        'receitas_logistica': total_log_r,
        'despesas_compras': total_compras,
        'despesas_rh': total_rh,
        'despesas_logistica': total_log_d,
    }


@require_financas_access
def financas_main(request):
    """Dashboard Finanças: totais de receitas e despesas por origem no período. Receitas = lançamentos contabilísticos (reflecte confirmação de recebimentos)."""
    try:
        di, df, di_str, df_str = _parse_periodo(request, default_days=365)

        # Receitas — a partir dos lançamentos (conta 71.01 Vendas, 72.01 Logística) para reflectir confirmações
        total_receitas_vendas, total_receitas_log = _receitas_from_lancamentos(di, df)
        total_receitas = total_receitas_vendas + total_receitas_log

        # Despesas — Compras: apenas ordens recebidas (RECEBIDA), para coincidir com a listagem
        from .models_stock import OrdemCompra, ItemOrdemCompra
        ordens_compra = OrdemCompra.objects.filter(
            data_criacao__date__gte=di,
            data_criacao__date__lte=df,
            status='RECEBIDA',
        )
        total_despesas_compras = Decimal('0.00')
        for oc in ordens_compra:
            total_despesas_compras += sum(
                (item.quantidade_solicitada * (item.preco_unitario or Decimal('0')))
                for item in oc.itens.all()
            )

        # Despesas — RH (desdobramento: Folha | Treinamentos | Empreitadas concluídas)
        # Folha: a partir dos lançamentos (62.01) para o resumo reflectir o que está na contabilidade
        despesas_rh_folha = Decimal('0.00')
        despesas_rh_treinamento = Decimal('0.00')
        despesas_rh_empreitada = Decimal('0.00')
        try:
            from .models_financas import LancamentoFinanceiro
            lanc_folha = LancamentoFinanceiro.objects.filter(
                data__gte=di,
                data__lte=df,
                conta__codigo='62.01',
                origem_tipo='RH',
            ).aggregate(s=Sum('valor'))
            # valor em 62.01 é negativo (débito); despesa = valor absoluto
            despesas_rh_folha = abs(lanc_folha['s'] or Decimal('0.00'))
            total_despesas_rh = despesas_rh_folha
        except Exception:
            total_despesas_rh = Decimal('0.00')
        try:
            from .models_rh import Treinamento
            trein = Treinamento.objects.filter(
                status='CONCLUIDO', custo_total__gt=0,
                data_fim__gte=di, data_fim__lte=df,
            ).aggregate(s=Sum('custo_total'))
            despesas_rh_treinamento = trein['s'] or Decimal('0.00')
            total_despesas_rh += despesas_rh_treinamento
        except Exception:
            pass
        try:
            from .models_rh import TrabalhoEmpreitada
            emp = TrabalhoEmpreitada.objects.filter(
                status='CONCLUIDO', valor_fixo__gt=0,
                data_conclusao__gte=di, data_conclusao__lte=df,
            ).aggregate(s=Sum('valor_fixo'))
            despesas_rh_empreitada = emp['s'] or Decimal('0.00')
            total_despesas_rh += despesas_rh_empreitada
        except Exception:
            pass

        # Despesas — Logística (CustoLogistico aprovados)
        try:
            from .models_cost_billing import CustoLogistico
            custos = CustoLogistico.objects.filter(
                status='APROVADO',
                data_custo__gte=di,
                data_custo__lte=df,
            ).aggregate(s=Sum('valor'))
            total_despesas_log = custos['s'] or Decimal('0.00')
        except Exception:
            total_despesas_log = Decimal('0.00')

        total_despesas = total_despesas_compras + total_despesas_rh + total_despesas_log
        saldo = total_receitas - total_despesas

        # Notificações: contas a pagar e a receber pendentes
        from .models_financas import PendenteContaPagar, PendenteContaReceber
        contas_pagar_pendentes = PendenteContaPagar.objects.filter(estado='PENDENTE')
        contas_receber_pendentes = PendenteContaReceber.objects.filter(estado='PENDENTE')
        contas_pagar_count = contas_pagar_pendentes.count()
        contas_receber_count = contas_receber_pendentes.count()
        contas_pagar_total = contas_pagar_pendentes.aggregate(s=Sum('valor'))['s'] or Decimal('0')
        contas_receber_total = contas_receber_pendentes.aggregate(s=Sum('valor'))['s'] or Decimal('0')

        context = {
            'title': 'Finanças',
            'contas_pagar_count': contas_pagar_count,
            'contas_receber_count': contas_receber_count,
            'contas_pagar_total': contas_pagar_total,
            'contas_receber_total': contas_receber_total,
            'data_inicio': di_str,
            'data_fim': df_str,
            'total_receitas': total_receitas,
            'total_despesas': total_despesas,
            'saldo': saldo,
            'receitas_vendas': total_receitas_vendas,
            'receitas_logistica': total_receitas_log,
            'despesas_compras': total_despesas_compras,
            'despesas_rh': total_despesas_rh,
            'despesas_rh_folha': despesas_rh_folha,
            'despesas_rh_treinamento': despesas_rh_treinamento,
            'despesas_rh_empreitada': despesas_rh_empreitada,
            'despesas_logistica': total_despesas_log,
            'chart_receitas': float(total_receitas),
            'chart_despesas': float(total_despesas),
        }
        return render(request, 'financas/main.html', context)
    except Exception as e:
        logger.error(f'Erro ao carregar dashboard Finanças: {e}', exc_info=True)
        messages.error(request, 'Erro ao carregar o módulo de Finanças.')
        return redirect('dashboard')


@require_financas_access
def financas_receitas(request):
    """Listagem de receitas por origem — mesma fonte do dashboard (lançamentos 71.01 e 72.01). O total coincide com o total de receitas do período."""
    try:
        di, df, di_str, df_str = _parse_periodo(request, default_days=365)

        from .models_financas import LancamentoFinanceiro
        lista = []
        # Lançamentos de receita no período (conta 71.01 = Prestação de Serviços, 72.01 = Logística)
        lancamentos = LancamentoFinanceiro.objects.filter(
            data__gte=di,
            data__lte=df,
            conta__codigo__in=('71.01', '72.01'),
            valor__gt=0,
        ).select_related('conta').order_by('-data', '-id')
        for lanc in lancamentos:
            origem = 'Vendas' if lanc.conta.codigo == '71.01' else 'Logística'
            descricao = lanc.descricao or lanc.documento_ref or '—'
            url, url_label = '', '—'
            if lanc.origem_tipo == 'VENDAS' and lanc.origem_id:
                try:
                    from django.urls import reverse
                    url = reverse('producao:servico_ordem_detail', args=[lanc.origem_id])
                except Exception:
                    url = ''
                url_label = 'Ver ordem de serviço'
            elif lanc.origem_tipo == 'LOGISTICA' and lanc.origem_id:
                try:
                    from .models_cost_billing import FaturamentoFrete
                    if FaturamentoFrete.objects.filter(id=lanc.origem_id).exists():
                        url = f"/stock/cost-billing/faturas/{lanc.origem_id}/"
                        url_label = 'Ver fatura'
                except Exception:
                    pass
            lista.append({
                'data': lanc.data,
                'origem': origem,
                'descricao': descricao,
                'valor': lanc.valor,
                'url': url,
                'url_label': url_label,
            })

        # Filtro por origem (Vendas, Logística)
        origem_filter = request.GET.get('origem', '').strip()
        if origem_filter:
            lista = [r for r in lista if r['origem'] == origem_filter]

        total = sum(r['valor'] for r in lista)

        context = {
            'title': 'Receitas',
            'data_inicio': di_str,
            'data_fim': df_str,
            'lista': lista,
            'total': total,
            'origem_filter': origem_filter,
        }
        return render(request, 'financas/receitas.html', context)
    except Exception as e:
        logger.error(f'Erro ao carregar receitas: {e}', exc_info=True)
        messages.error(request, 'Erro ao carregar receitas.')
        return redirect('financas:main')


@require_financas_access
def financas_despesas(request):
    """Listagem de despesas por origem (Compras, RH, Logística)."""
    try:
        di, df, di_str, df_str = _parse_periodo(request, default_days=365)

        from .models_stock import OrdemCompra
        lista = []
        despesas_rh_folha = Decimal('0.00')
        despesas_rh_treinamento = Decimal('0.00')
        despesas_rh_empreitada = Decimal('0.00')
        adiantamentos_rh = []

        # Compras — apenas ordens recebidas (RECEBIDA), para não listar ordens revertidas
        from django.urls import reverse
        ordens = OrdemCompra.objects.filter(
            data_criacao__date__gte=di,
            data_criacao__date__lte=df,
            status='RECEBIDA',
        ).select_related('fornecedor').order_by('-data_criacao')
        for oc in ordens:
            valor = sum(
                item.quantidade_solicitada * (item.preco_unitario or Decimal('0'))
                for item in oc.itens.all()
            )
            try:
                url_ordem = reverse('stock:requisicoes:ordem_compra_preview', args=[oc.id])
            except Exception:
                url_ordem = '/stock/requisicoes/ordens-compra/'
            lista.append({
                'data': oc.data_criacao.date() if oc.data_criacao else None,
                'origem': 'Compras',
                'subtipo_rh': '',
                'descricao': f"{oc.codigo} - {oc.fornecedor.nome if oc.fornecedor else 'N/A'}",
                'valor': valor,
                'url': url_ordem,
                'url_label': f'Ver ordem {oc.codigo}',
            })

        # RH — Folhas (a partir dos lançamentos 62.01 para reflectir a contabilidade)
        try:
            from .models_financas import LancamentoFinanceiro
            from django.urls import reverse
            lancamentos_folha = LancamentoFinanceiro.objects.filter(
                data__gte=di,
                data__lte=df,
                conta__codigo='62.01',
                origem_tipo='RH',
                valor__lt=0,
            ).select_related('conta').order_by('-data')
            for lanc in lancamentos_folha:
                valor = abs(lanc.valor)
                despesas_rh_folha += valor
                try:
                    url_folha = reverse('rh:folha_detail', args=[lanc.origem_id]) if lanc.origem_id else '/rh/'
                except Exception:
                    url_folha = '/rh/'
                lista.append({
                    'data': lanc.data,
                    'origem': 'RH',
                    'subtipo_rh': 'Folha',
                    'descricao': lanc.descricao or f"Folha (doc. {lanc.documento_ref or lanc.origem_id})",
                    'valor': valor,
                    'url': url_folha,
                    'url_label': 'Ver folha',
                })
        except Exception:
            pass

        # RH — Treinamentos concluídos
        try:
            from .models_rh import Treinamento
            treinamentos = Treinamento.objects.filter(
                status='CONCLUIDO',
                custo_total__gt=0,
                data_fim__gte=di,
                data_fim__lte=df,
            ).order_by('-data_fim')
            for t in treinamentos:
                val = t.custo_total or Decimal('0.00')
                despesas_rh_treinamento += val
                lista.append({
                    'data': t.data_fim,
                    'origem': 'RH',
                    'subtipo_rh': 'Treinamento',
                    'descricao': f"Treinamento: {t.nome}",
                    'valor': val,
                    'url': '/rh/treinamentos/',
                    'url_label': 'Módulo RH',
                })
        except Exception:
            pass

        # RH — Empreitadas (trabalhos por tarefa concluídos; não inclui parcelas à assinatura)
        try:
            from .models_rh import TrabalhoEmpreitada
            trabalhos = TrabalhoEmpreitada.objects.filter(
                status='CONCLUIDO',
                valor_fixo__gt=0,
                data_conclusao__gte=di,
                data_conclusao__lte=df,
            ).select_related('prestador').order_by('-data_conclusao')
            for trab in trabalhos:
                val = trab.valor_fixo or Decimal('0.00')
                despesas_rh_empreitada += val
                lista.append({
                    'data': trab.data_conclusao,
                    'origem': 'RH',
                    'subtipo_rh': 'Empreitada (trabalho concluído)',
                    'descricao': f"Empreitada: {trab.prestador.nome if trab.prestador else 'N/A'} — trabalho concluído",
                    'valor': val,
                    'url': '/rh/empreitadas/',
                    'url_label': 'Módulo RH',
                })
        except Exception:
            pass

        # Adiantamentos empreitada (parcelas à assinatura) confirmados no período — não somam ao total RH; informativo
        adiantamentos_rh = []
        try:
            from .models_financas import PendenteContaPagar
            from django.db.models import Q
            pendentes_adiant = PendenteContaPagar.objects.filter(
                estado='CONFIRMADO',
                origem_tipo__in=('RH_EMP_PARCELA', 'RH_EMPREITADA'),
                data_confirmacao__date__gte=di,
                data_confirmacao__date__lte=df,
            ).order_by('-data_confirmacao')
            for p in pendentes_adiant:
                adiantamentos_rh.append({
                    'data': p.data_confirmacao.date() if p.data_confirmacao else None,
                    'descricao': p.descricao,
                    'valor': p.valor,
                    'beneficiario': p.beneficiario,
                })
        except Exception:
            pass

        # Logística — Custos aprovados
        try:
            from .models_cost_billing import CustoLogistico
            custos = CustoLogistico.objects.filter(
                status='APROVADO',
                data_custo__gte=di,
                data_custo__lte=df,
            ).select_related('tipo_custo').order_by('-data_custo')
            for c in custos:
                lista.append({
                    'data': c.data_custo,
                    'origem': 'Logística',
                    'subtipo_rh': '',
                    'descricao': f"{c.codigo} - {c.tipo_custo.nome if c.tipo_custo else ''}",
                    'valor': c.valor or Decimal('0.00'),
                    'url': f"/stock/cost-billing/custos/{c.id}/",
                    'url_label': 'Ver custo',
                })
        except Exception:
            pass

        lista.sort(key=lambda x: x['data'] or timezone.now().date(), reverse=True)

        # Filtro por origem (Compras, RH, Logística)
        origem_filter = request.GET.get('origem', '').strip()
        if origem_filter:
            lista = [d for d in lista if d['origem'] == origem_filter]

        total = sum(d['valor'] for d in lista)

        context = {
            'title': 'Despesas',
            'data_inicio': di_str,
            'data_fim': df_str,
            'lista': lista,
            'total': total,
            'origem_filter': origem_filter,
            'despesas_rh_folha': despesas_rh_folha,
            'despesas_rh_treinamento': despesas_rh_treinamento,
            'despesas_rh_empreitada': despesas_rh_empreitada,
            'adiantamentos_rh': adiantamentos_rh,
        }
        return render(request, 'financas/despesas.html', context)
    except Exception as e:
        logger.error(f'Erro ao carregar despesas: {e}', exc_info=True)
        messages.error(request, 'Erro ao carregar despesas.')
        return redirect('financas:main')


@require_financas_access
def financas_contas_pagar(request):
    """Contas a pagar — itens pendentes de confirmação pelo departamento de Finanças."""
    from .models_financas import PendenteContaPagar
    estado_filter = request.GET.get('estado', 'PENDENTE')
    pendentes = PendenteContaPagar.objects.all().order_by('-data_criacao')
    if estado_filter:
        pendentes = pendentes.filter(estado=estado_filter)
    total_pendente = PendenteContaPagar.objects.filter(estado='PENDENTE').aggregate(
        s=Sum('valor')
    )
    total_pendente_val = total_pendente['s'] or Decimal('0.00')
    context = {
        'title': 'Contas a Pagar',
        'pendentes': pendentes,
        'estado_filter': estado_filter,
        'total_pendente': total_pendente_val,
        'estado_choices': PendenteContaPagar.ESTADO_CHOICES,
    }
    return render(request, 'financas/contas_pagar.html', context)


@require_financas_access
def financas_contas_receber(request):
    """Contas a receber — itens pendentes de confirmação pelo departamento de Finanças."""
    from .models_financas import PendenteContaReceber
    estado_filter = request.GET.get('estado', 'PENDENTE')
    pendentes = PendenteContaReceber.objects.all().order_by('-data_criacao')
    if estado_filter:
        pendentes = pendentes.filter(estado=estado_filter)
    total_pendente = PendenteContaReceber.objects.filter(estado='PENDENTE').aggregate(
        s=Sum('valor')
    )
    total_pendente_val = total_pendente['s'] or Decimal('0.00')
    context = {
        'title': 'Contas a Receber',
        'pendentes': pendentes,
        'estado_filter': estado_filter,
        'total_pendente': total_pendente_val,
        'estado_choices': PendenteContaReceber.ESTADO_CHOICES,
    }
    return render(request, 'financas/contas_receber.html', context)


def _build_cronograma_financeiro_context(di, df):
    """
    Constrói dados para o cronograma físico financeiro: contas a receber e a pagar
    com data_vencimento no período (ou sem filtro de data se período largo).
    Retorna dict com cronograma_receber, cronograma_pagar, gantt_min_date, gantt_max_date,
    gantt_ticks, gantt_hoje_pct, total_days.
    """
    from .models_financas import PendenteContaPagar, PendenteContaReceber
    from django.urls import reverse

    hoje = timezone.now().date()
    # Incluir itens com data_vencimento no período ou sem data (mostrar no cronograma)
    receber_qs = PendenteContaReceber.objects.filter(estado__in=['PENDENTE', 'CONFIRMADO'])
    pagar_qs = PendenteContaPagar.objects.filter(estado__in=['PENDENTE', 'CONFIRMADO'])

    receber = []
    for p in receber_qs:
        d = p.data_vencimento
        if d is None:
            d = p.data_criacao.date() if p.data_criacao else hoje
        # Incluir se data no período OU se for pendente (mostrar previstos sempre)
        if di <= d <= df or p.estado == 'PENDENTE':
            receber.append({
                'id': p.id,
                'data': d,
                'label': f"{p.credor} — {p.valor} MT",
                'valor': p.valor,
                'url': reverse('financas:contas_receber'),
                'estado': p.estado,
            })
    pagar = []
    for p in pagar_qs:
        d = p.data_vencimento
        if d is None:
            d = p.data_criacao.date() if p.data_criacao else hoje
        if di <= d <= df or p.estado == 'PENDENTE':
            pagar.append({
                'id': p.id,
                'data': d,
                'label': f"{p.beneficiario} — {p.valor} MT",
                'valor': p.valor,
                'url': reverse('financas:contas_pagar'),
                'estado': p.estado,
            })

    # Recebimentos previstos: etapas do plano com parcela (vendas) e data prevista, ainda não exigidas
    try:
        from .models_stock import AtividadeExecucao
        from .parcelas_vendas_utils import _valor_total_com_iva_ordem, ordem_e_so_servicos
        pendente_receber_parcela_ids = set(
            PendenteContaReceber.objects.filter(origem_tipo='VENDAS_PARCELA').values_list('origem_id', flat=True)
        )
        for atv in AtividadeExecucao.objects.filter(
            parcela__isnull=False,
            status__in=('AGENDADA', 'EM_ANDAMENTO', 'PAUSADA'),
            data_prevista_conclusao__isnull=False,
        ).select_related('ordem_servico', 'ordem_servico__cliente', 'parcela'):
            if atv.parcela_id in pendente_receber_parcela_ids:
                continue
            if not ordem_e_so_servicos(atv.ordem_servico):
                continue
            d_prev = atv.data_prevista_conclusao
            if d_prev is None or not (di <= d_prev <= df):
                continue
            valor_total_iva = _valor_total_com_iva_ordem(atv.ordem_servico)
            if valor_total_iva <= 0:
                continue
            valor = valor_total_iva * Decimal(atv.parcela.percentagem) / Decimal('100')
            if valor <= 0:
                continue
            credor = (atv.ordem_servico.cliente.nome if atv.ordem_servico.cliente else atv.ordem_servico.nome_cliente_pagamento or 'Cliente')[:300]
            try:
                url_os = reverse('producao:servico_ordem_detail', args=[atv.ordem_servico_id])
            except Exception:
                url_os = reverse('financas:contas_receber')
            receber.append({
                'id': f'prev-rc-{atv.id}',
                'data': d_prev,
                'label': f"{credor} — {valor} MT (prev. {atv.ordem_servico.codigo})",
                'valor': valor,
                'url': url_os,
                'estado': 'PREVISTO',
            })
    except Exception:
        pass

    # Pagamentos previstos: contrato de empreitada + parcelas + plano de trabalho (data = conclusão prevista)
    try:
        from .models_rh import ParcelaPagamentoEmpreitada
        pendente_emp_parcela_ids = set(
            PendenteContaPagar.objects.filter(origem_tipo='RH_EMP_PARCELA').values_list('origem_id', flat=True)
        )
        # Parcelas de conclusão (trabalhos ou total) de contratos ligados a uma ordem
        parcelas_qs = ParcelaPagamentoEmpreitada.objects.filter(
            contrato_empreitada__ordem_servico__isnull=False,
            tipo__in=(ParcelaPagamentoEmpreitada.TIPO_CONCLUSAO_TRABALHOS, ParcelaPagamentoEmpreitada.TIPO_CONCLUSAO_TOTAL),
        ).exclude(
            id__in=pendente_emp_parcela_ids,
        ).select_related('contrato_empreitada', 'contrato_empreitada__prestador').prefetch_related(
            'trabalhos', 'trabalhos__atividade_execucao', 'contrato_empreitada__trabalhos', 'contrato_empreitada__trabalhos__atividade_execucao',
        )
        for parcela in parcelas_qs:
            contrato = parcela.contrato_empreitada
            if parcela.tipo == ParcelaPagamentoEmpreitada.TIPO_CONCLUSAO_TRABALHOS:
                trabalhos = list(parcela.trabalhos.all())
            else:
                trabalhos = list(contrato.trabalhos.all())
            # Data prevista = maior data_prevista_conclusao das actividades dos trabalhos (ainda não concluídos)
            datas_prev = []
            for t in trabalhos:
                if t.status == 'CONCLUIDO':
                    continue
                atv = getattr(t, 'atividade_execucao', None)
                if atv and getattr(atv, 'data_prevista_conclusao', None):
                    datas_prev.append(atv.data_prevista_conclusao)
            if not datas_prev:
                continue
            d_prev = max(datas_prev)
            if not (di <= d_prev <= df):
                continue
            valor = parcela.valor_parcela()
            if valor is None or valor <= 0:
                continue
            benef = (contrato.prestador.nome if contrato.prestador else 'Prestador')[:300]
            codigo = contrato.ordem_servico.codigo if contrato.ordem_servico else '—'
            try:
                url_origem = reverse('rh:editar_contrato_empreitada', args=[contrato.id])
            except Exception:
                url_origem = reverse('financas:contas_pagar')
            pagar.append({
                'id': f'prev-pg-emp-{parcela.id}',
                'data': d_prev,
                'label': f"{benef} — {valor} MT (prev. parcela {parcela.numero_ordem} {codigo})",
                'valor': valor,
                'url': url_origem,
                'estado': 'PREVISTO',
            })
    except Exception:
        pass

    all_dates = [di, df, hoje]
    for r in receber:
        all_dates.append(r['data'])
    for p in pagar:
        all_dates.append(p['data'])
    gantt_min = min(all_dates) - timedelta(days=3)
    gantt_max = max(all_dates) + timedelta(days=14)
    total_days = max(1, (gantt_max - gantt_min).days)

    # Ticks: escala mensal — primeiro dia de cada mês no intervalo + primeiro e último dia
    gantt_ticks = [
        {'date': gantt_min, 'pct': 0.0},
        {'date': gantt_max, 'pct': 100.0},
    ]
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
    # Remover duplicados de pct; evitar tick intermédio demasiado perto do fim (ex.: 99.5% e 100%)
    SCALE_PX = 600
    seen_pct = set()
    out = []
    for t in gantt_ticks:
        p = round(t['pct'], 1)
        if t['date'] == gantt_max:
            # último dia: usar sempre 100%
            p = 100.0
        elif p >= 97.0:
            # omitir tick intermédio muito perto do fim para não concentrar datas
            continue
        if p not in seen_pct or t['date'] == gantt_min or t['date'] == gantt_max:
            seen_pct.add(p)
            left_px = round(t['pct'] / 100.0 * SCALE_PX)
            out.append({'date': t['date'], 'pct': p, 'left_px': left_px})
    gantt_ticks = out

    hoje_pct = None
    hoje_px = None
    if gantt_min <= hoje <= gantt_max:
        hoje_pct = round((hoje - gantt_min).days / total_days * 100, 1)
        hoje_px = round(hoje_pct / 100.0 * SCALE_PX)

    # Barras visíveis: mínimo 3%, máximo 12% (evitar sobreposição quando muitas no mesmo dia)
    bar_width_pct = 100.0 / total_days * 2
    bar_width_pct = max(3.0, min(12.0, bar_width_pct))

    def add_style(items_list):
        for it in items_list:
            # Posição na escala: 0% = gantt_min, 100% = gantt_max (igual aos ticks)
            date_pct = (it['data'] - gantt_min).days / total_days * 100
            # Centrar a barra na data de vencimento
            left_pct = date_pct - bar_width_pct / 2
            left_pct = max(0, min(100 - bar_width_pct, left_pct))
            it['left_pct'] = round(left_pct, 1)
            it['width_pct'] = round(bar_width_pct, 1)

    add_style(receber)
    add_style(pagar)

    # #region agent log
    import os
    import json
    _log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'debug-24ec57.log')
    try:
        first_r = receber[0] if receber else None
        first_p = pagar[0] if pagar else None
        with open(_log_path, 'a', encoding='utf-8') as _f:
            _f.write(json.dumps({
                'sessionId': '24ec57', 'hypothesisId': 'H1', 'location': 'views_financas._build_cronograma',
                'message': 'cronograma context', 'timestamp': int(timezone.now().timestamp() * 1000),
                'data': {
                    'n_receber': len(receber), 'n_pagar': len(pagar),
                    'first_receber_left_pct': first_r.get('left_pct') if first_r else None,
                    'first_pagar_left_pct': first_p.get('left_pct') if first_p else None,
                    'bar_width_pct': round(bar_width_pct, 1), 'total_days': total_days,
                    'gantt_min': str(gantt_min), 'gantt_max': str(gantt_max), 'hoje_pct': hoje_pct,
                    'n_ticks': len(gantt_ticks), 'tick_pcts': [t['pct'] for t in gantt_ticks],
                }
            }) + '\n')
    except Exception as _e:
        pass
    # #endregion

    # Largura mínima da escala (px) para scroll confortável: ~8px por dia, entre 800 e 4000
    gantt_scale_min_px = max(800, min(4000, total_days * 8))

    return {
        'cronograma_receber': receber,
        'cronograma_pagar': pagar,
        'gantt_min_date': gantt_min,
        'gantt_max_date': gantt_max,
        'gantt_ticks': gantt_ticks,
        'gantt_hoje_pct': hoje_pct,
        'gantt_hoje_px': hoje_px,
        'total_days': total_days,
        'bar_width_pct': round(bar_width_pct, 1),
        'gantt_scale_min_px': gantt_scale_min_px,
    }


@require_financas_access
def financas_cronograma(request):
    """Cronograma físico financeiro: contas a receber e a pagar por data de vencimento."""
    di, df, di_str, df_str = _parse_periodo(request, default_days=30)
    # #region agent log
    import os
    import json
    _log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'debug-24ec57.log')
    try:
        with open(_log_path, 'a', encoding='utf-8') as _f:
            _f.write(json.dumps({'sessionId': '24ec57', 'hypothesisId': 'H2', 'location': 'views_financas.financas_cronograma', 'message': 'periodo', 'timestamp': int(timezone.now().timestamp() * 1000), 'data': {'di': str(di), 'df': str(df)}}) + '\n')
    except Exception:
        pass
    # #endregion
    ctx = _build_cronograma_financeiro_context(di, df)
    context = {
        'title': 'Cronograma físico financeiro',
        'data_inicio': di_str,
        'data_fim': df_str,
        **ctx,
    }
    return render(request, 'financas/cronograma.html', context)


@require_financas_access
def financas_confirmar_conta_pagar(request, pendente_id):
    """Confirma um item de Contas a pagar — cria os lançamentos financeiros."""
    from .models_financas import PendenteContaPagar, Conta, LancamentoFinanceiro
    from .models_rh import ParcelaPagamentoEmpreitada, FolhaSalarial
    from django.urls import reverse

    pendente = get_object_or_404(PendenteContaPagar, id=pendente_id)
    if pendente.estado != 'PENDENTE':
        messages.warning(request, 'Este item já foi processado.')
        return redirect('financas:contas_pagar')

    if request.method != 'POST':
        context = {'pendente': pendente}
        return render(request, 'financas/confirmar_conta_pagar.html', context)

    data_mov = pendente.data_vencimento or date.today()
    valor = pendente.valor
    descricao = pendente.descricao

    # Definir doc_ref e origem_tipo do lançamento conforme origem do pendente
    if pendente.origem_tipo == 'RH_FOLHA_SALARIAL':
        origem_tipo_lanc = 'RH'
        try:
            folha = FolhaSalarial.objects.get(id=pendente.origem_id)
            doc_ref = f"Folha-{folha.mes_referencia}"
        except FolhaSalarial.DoesNotExist:
            doc_ref = f"Folha-{pendente.origem_id}"
    elif pendente.origem_tipo == 'RH_EMP_PARCELA':
        origem_tipo_lanc = 'RH_EMP_PARCELA'
        doc_ref = f"EMP-P{pendente.origem_id}"
    elif pendente.origem_tipo == 'LOGISTICA':
        origem_tipo_lanc = 'LOGISTICA'
        doc_ref = f"CL-{pendente.origem_id}"
        try:
            from .models_cost_billing import CustoLogistico
            custo = CustoLogistico.objects.filter(id=pendente.origem_id).first()
            if custo:
                doc_ref = custo.codigo
        except Exception:
            pass
    else:
        origem_tipo_lanc = 'RH_EMPREITADA'
        doc_ref = f"EMP-{pendente.origem_id}"

    with transaction.atomic():
        # Evitar lançamentos duplicados: se já existir lançamento para esta origem, só marcar pendente como confirmado
        existing = LancamentoFinanceiro.objects.filter(
            origem_tipo=origem_tipo_lanc,
            origem_id=pendente.origem_id,
            valor__lt=0,
        ).first()
        if existing:
            pendente.estado = 'CONFIRMADO'
            pendente.data_confirmacao = timezone.now()
            pendente.confirmado_por = request.user
            pendente.lancamento = existing
            pendente.save(update_fields=['estado', 'data_confirmacao', 'confirmado_por', 'lancamento'])
            if pendente.origem_tipo == 'RH_EMP_PARCELA' and pendente.origem_id:
                try:
                    parcela = ParcelaPagamentoEmpreitada.objects.get(id=pendente.origem_id)
                    if not parcela.data_pago:
                        parcela.data_pago = timezone.now()
                        parcela.save(update_fields=['data_pago'])
                except ParcelaPagamentoEmpreitada.DoesNotExist:
                    pass
            if pendente.origem_tipo == 'LOGISTICA' and pendente.origem_id:
                try:
                    from .services.logistica_financas_sync import marcar_custo_faturado_apos_confirmacao
                    marcar_custo_faturado_apos_confirmacao(pendente.origem_id)
                except Exception:
                    pass
            messages.success(request, f'Pagamento de {valor:.2f} MT já estava registado. Este item foi marcado como confirmado.')
            return redirect('financas:contas_pagar')

        # Folha salarial: 62.01 Pessoal (folha) + 33 Remunerações a pagar
        if pendente.origem_tipo == 'LOGISTICA':
            conta_despesa, _ = Conta.objects.get_or_create(
                codigo='63.01',
                defaults={'nome': 'Custos Logística', 'tipo': 'DESPESA', 'ativo': True, 'ordem': 0},
            )
            conta_passivo, _ = Conta.objects.get_or_create(
                codigo='33',
                defaults={'nome': 'Fornecedores e outros credores', 'tipo': 'PASSIVO', 'ativo': True, 'ordem': 0},
            )
        elif pendente.origem_tipo == 'RH_FOLHA_SALARIAL':
            conta_despesa, _ = Conta.objects.get_or_create(
                codigo='62.01',
                defaults={'nome': 'Pessoal (folha)', 'tipo': 'DESPESA', 'ativo': True, 'ordem': 0},
            )
            conta_passivo, _ = Conta.objects.get_or_create(
                codigo='33',
                defaults={'nome': 'Estado e outros credores', 'tipo': 'PASSIVO', 'ativo': True, 'ordem': 0},
            )
        else:
            # Empreitada / parcela: 62.03 + 33
            conta_despesa, _ = Conta.objects.get_or_create(
                codigo='62.03',
                defaults={'nome': 'Pessoal por empreitada', 'tipo': 'DESPESA', 'ativo': True, 'ordem': 0},
            )
            conta_passivo, _ = Conta.objects.get_or_create(
                codigo='33',
                defaults={'nome': 'Remunerações a pagar', 'tipo': 'PASSIVO', 'ativo': True, 'ordem': 0},
            )

        l1 = LancamentoFinanceiro.objects.create(
            data=data_mov, conta=conta_despesa, valor=-valor,
            descricao=descricao, documento_ref=doc_ref,
            origem_tipo=origem_tipo_lanc,
            origem_id=pendente.origem_id, criado_por=request.user,
        )
        l2 = LancamentoFinanceiro.objects.create(
            data=data_mov, conta=conta_passivo, valor=valor,
            descricao=descricao, documento_ref=doc_ref,
            origem_tipo=origem_tipo_lanc,
            origem_id=pendente.origem_id, criado_por=request.user,
        )
        pendente.estado = 'CONFIRMADO'
        pendente.data_confirmacao = timezone.now()
        pendente.confirmado_por = request.user
        pendente.lancamento = l1
        pendente.save(update_fields=['estado', 'data_confirmacao', 'confirmado_por', 'lancamento'])

        if pendente.origem_tipo == 'RH_EMP_PARCELA' and pendente.origem_id:
            try:
                parcela = ParcelaPagamentoEmpreitada.objects.get(id=pendente.origem_id)
                parcela.data_pago = timezone.now()
                parcela.save(update_fields=['data_pago'])
            except ParcelaPagamentoEmpreitada.DoesNotExist:
                pass
        if pendente.origem_tipo == 'LOGISTICA' and pendente.origem_id:
            try:
                from .services.logistica_financas_sync import marcar_custo_faturado_apos_confirmacao
                marcar_custo_faturado_apos_confirmacao(pendente.origem_id)
            except Exception:
                pass

    messages.success(request, f'Pagamento de {valor:.2f} MT confirmado. Lançamentos criados.')
    if pendente.origem_tipo in ('RH_FOLHA_SALARIAL', 'LOGISTICA'):
        return redirect('financas:contas_pagar')
    return redirect('financas:recibo_adiantamento_pagar', pendente_id=pendente_id)


@require_financas_access
def financas_rejeitar_conta_pagar(request, pendente_id):
    """Rejeita um item de Contas a pagar — não cria lançamentos."""
    from .models_financas import PendenteContaPagar
    pendente = get_object_or_404(PendenteContaPagar, id=pendente_id)
    if pendente.estado != 'PENDENTE':
        messages.warning(request, 'Este item já foi processado.')
        return redirect('financas:contas_pagar')
    if request.method == 'POST':
        pendente.estado = 'REJEITADO'
        pendente.data_confirmacao = timezone.now()
        pendente.confirmado_por = request.user
        pendente.save(update_fields=['estado', 'data_confirmacao', 'confirmado_por'])
        messages.success(request, 'Item rejeitado.')
    return redirect('financas:contas_pagar')


@require_financas_access
def financas_confirmar_conta_receber(request, pendente_id):
    """Confirma um item de Contas a receber — cria os lançamentos financeiros (Débito 22 + Crédito 71.01)."""
    from .models_financas import PendenteContaReceber, Conta, LancamentoFinanceiro

    pendente = get_object_or_404(PendenteContaReceber, id=pendente_id)
    if pendente.estado != 'PENDENTE':
        messages.warning(request, 'Este item já foi processado.')
        return redirect('financas:contas_receber')

    if request.method != 'POST':
        context = {'pendente': pendente}
        return render(request, 'financas/confirmar_conta_receber.html', context)

    data_mov = pendente.data_vencimento or date.today()
    valor = pendente.valor
    descricao = pendente.descricao
    codigo_conta_receita = '71.01'
    nome_conta_receita = 'Receitas - Prestação de Serviços'
    ordem_vendas = None

    if pendente.origem_tipo == 'LOGISTICA':
        origem_tipo_lanc = 'LOGISTICA'
        origem_id_lanc = pendente.origem_id or pendente.id
        doc_ref = f"FAT-FRETE-{origem_id_lanc}"
        codigo_conta_receita = '72.01'
        nome_conta_receita = 'Receitas Logística (faturamento)'
        try:
            from .models_cost_billing import FaturamentoFrete
            fatura = FaturamentoFrete.objects.filter(id=pendente.origem_id).first()
            if fatura:
                doc_ref = fatura.numero_fatura
        except Exception:
            pass
    elif pendente.origem_tipo in ('VENDAS_FATURA', 'VENDAS_PARCELA'):
        origem_tipo_lanc = 'VENDAS'
        origem_id_lanc = pendente.origem_id or pendente.id
        doc_ref = f"REC-{pendente.origem_tipo}-{origem_id_lanc}"
    else:
        origem_tipo_lanc = pendente.origem_tipo or 'OUTRO'
        origem_id_lanc = pendente.origem_id or pendente.id
        doc_ref = f"REC-{pendente.origem_tipo}-{origem_id_lanc}"

    if pendente.origem_tipo == 'VENDAS_FATURA' and pendente.origem_id:
        try:
            from .models_stock import OrdemServico
            ordem_vendas = OrdemServico.objects.filter(id=pendente.origem_id).first()
            if ordem_vendas and ordem_vendas.numero_fatura_fiscal:
                doc_ref = ordem_vendas.numero_fatura_fiscal
        except Exception:
            pass
    elif pendente.origem_tipo == 'VENDAS_PARCELA' and pendente.origem_id:
        try:
            from .models_stock import ParcelaPagamentoOrcamento
            parcela = ParcelaPagamentoOrcamento.objects.filter(id=pendente.origem_id).select_related('ordem_servico').first()
            if parcela and parcela.ordem_servico:
                ordem_vendas = parcela.ordem_servico
                origem_id_lanc = ordem_vendas.id
                if ordem_vendas.numero_fatura_fiscal:
                    doc_ref = ordem_vendas.numero_fatura_fiscal
        except Exception:
            pass

    with transaction.atomic():
        conta_clientes, _ = Conta.objects.get_or_create(
            codigo='22',
            defaults={'nome': 'Clientes e outros devedores', 'tipo': 'ATIVO', 'ativo': True, 'ordem': 0},
        )
        conta_receitas, _ = Conta.objects.get_or_create(
            codigo=codigo_conta_receita,
            defaults={'nome': nome_conta_receita, 'tipo': 'RECEITA', 'ativo': True, 'ordem': 0},
        )
        l1 = LancamentoFinanceiro.objects.create(
            data=data_mov, conta=conta_clientes, valor=valor,
            descricao=descricao, documento_ref=doc_ref,
            origem_tipo=origem_tipo_lanc,
            origem_id=origem_id_lanc, criado_por=request.user,
        )
        l2 = LancamentoFinanceiro.objects.create(
            data=data_mov, conta=conta_receitas, valor=valor,
            descricao=descricao, documento_ref=doc_ref,
            origem_tipo=origem_tipo_lanc,
            origem_id=origem_id_lanc, criado_por=request.user,
        )
        # CMV (PGC-NIRF) para faturas de vendas
        if pendente.origem_tipo in ('VENDAS_FATURA', 'VENDAS_PARCELA') and ordem_vendas:
            try:
                from .fatura_ordem_utils import _custo_total_ordem_servico
                custo_total = _custo_total_ordem_servico(ordem_vendas)
                if custo_total and custo_total > 0 and not LancamentoFinanceiro.objects.filter(origem_tipo='VENDAS', origem_id=ordem_vendas.id, conta__codigo='61.01').exists():
                    conta_cmv, _ = Conta.objects.get_or_create(codigo='61.01', defaults={'nome': 'Custo da mercadoria vendida', 'tipo': 'DESPESA', 'ativo': True, 'ordem': 0})
                    conta_inventarios, _ = Conta.objects.get_or_create(codigo='21', defaults={'nome': 'Inventários', 'tipo': 'ATIVO', 'ativo': True, 'ordem': 0})
                    desc_cmv = f"CMV {doc_ref} - {ordem_vendas.codigo}"
                    LancamentoFinanceiro.objects.create(data=data_mov, conta=conta_cmv, valor=-custo_total, descricao=desc_cmv, documento_ref=doc_ref, origem_tipo='VENDAS', origem_id=ordem_vendas.id, criado_por=request.user)
                    LancamentoFinanceiro.objects.create(data=data_mov, conta=conta_inventarios, valor=custo_total, descricao=desc_cmv, documento_ref=doc_ref, origem_tipo='VENDAS', origem_id=ordem_vendas.id, criado_por=request.user)
            except Exception:
                pass
        pendente.estado = 'CONFIRMADO'
        pendente.data_confirmacao = timezone.now()
        pendente.confirmado_por = request.user
        pendente.lancamento = l1
        pendente.save(update_fields=['estado', 'data_confirmacao', 'confirmado_por', 'lancamento'])

        if pendente.origem_tipo == 'LOGISTICA' and pendente.origem_id:
            try:
                from .services.logistica_financas_sync import marcar_fatura_paga_apos_confirmacao
                marcar_fatura_paga_apos_confirmacao(pendente.origem_id, data_mov)
            except Exception:
                pass

    messages.success(request, f'Recebimento de {valor:.2f} MT confirmado. Lançamentos criados.')
    if pendente.origem_tipo == 'LOGISTICA':
        return redirect('financas:contas_receber')
    return redirect('financas:recibo_adiantamento_receber', pendente_id=pendente_id)


@require_financas_access
def financas_rejeitar_conta_receber(request, pendente_id):
    """Rejeita um item de Contas a receber — não cria lançamentos."""
    from .models_financas import PendenteContaReceber
    pendente = get_object_or_404(PendenteContaReceber, id=pendente_id)
    if pendente.estado != 'PENDENTE':
        messages.warning(request, 'Este item já foi processado.')
        return redirect('financas:contas_receber')
    if request.method == 'POST':
        pendente.estado = 'REJEITADO'
        pendente.data_confirmacao = timezone.now()
        pendente.confirmado_por = request.user
        pendente.save(update_fields=['estado', 'data_confirmacao', 'confirmado_por'])
        messages.success(request, 'Item rejeitado.')
    return redirect('financas:contas_receber')


def _data_extenso_pt(d):
    """Formata data por extenso em português (ex.: 5 de Fevereiro de 2026)."""
    MESES = ('Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
             'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro')
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


@require_financas_access
def financas_gerar_recibo_adiantamento_pagar(request, pendente_id):
    """Gera PDF do recibo de adiantamento (pagamento) para assinatura entre empresa e beneficiário."""
    from .models_financas import PendenteContaPagar
    from .models_base import DadosEmpresa
    from django.template.loader import render_to_string
    from django.conf import settings
    from xhtml2pdf import pisa
    import io

    pendente = get_object_or_404(PendenteContaPagar, id=pendente_id)
    dados_empresa = DadosEmpresa.objects.first()
    if not dados_empresa:
        dados_empresa = type('Obj', (), {
            'nome': 'Conception Lda', 'nuit': '401932089',
            'endereco': '', 'telefone': '', 'representante_legal': None, 'cargo_representante': ''
        })()
    logo_url = ''
    if dados_empresa and getattr(dados_empresa, 'logo', None) and dados_empresa.logo:
        try:
            logo_url = f"{request.scheme}://{request.get_host()}{settings.MEDIA_URL}{dados_empresa.logo.name}"
        except Exception:
            logo_url = ''
    try:
        valor_extenso = __import__('num2words', fromlist=['num2words']).num2words(
            float(pendente.valor), lang='pt', to='currency', currency='EUR'
        ).replace('euros', 'meticais').replace('euro', 'metical')
    except Exception:
        valor_extenso = str(pendente.valor)
    hoje = timezone.now().date()
    rep = getattr(dados_empresa, 'representante_legal', None)
    ctx = {
        'dados_empresa': dados_empresa,
        'logo_url': logo_url,
        'numero_recibo': f"REC-PAG-{hoje.year}-{pendente_id:06d}",
        'data_emissao': _data_extenso_pt(hoje),
        'representante_nome': rep.get_full_name() if rep else '',
        'representante_cargo': getattr(dados_empresa, 'cargo_representante', None) or 'Representante Legal',
        'valor': f"{pendente.valor:,.2f}".replace(',', ' ').replace('.', ',').replace(' ', '.'),
        'valor_extenso': valor_extenso,
        'descricao': pendente.descricao,
        'beneficiario': pendente.beneficiario,
        'data': _data_extenso_pt(pendente.data_vencimento or hoje),
    }
    html = render_to_string('financas/recibo_adiantamento_pagamento.html', ctx)
    result = io.BytesIO()
    pisa.CreatePDF(html.encode('utf-8'), dest=result, encoding='utf-8')
    result.seek(0)
    response = HttpResponse(result.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="recibo_adiantamento_pagamento_{pendente_id}.pdf"'
    return response


@require_financas_access
def financas_gerar_recibo_adiantamento_receber(request, pendente_id):
    """Gera PDF do recibo de adiantamento (recebimento) para assinatura entre empresa e cliente."""
    from .models_financas import PendenteContaReceber
    from .models_base import DadosEmpresa
    from django.template.loader import render_to_string
    from django.conf import settings
    from xhtml2pdf import pisa
    import io

    pendente = get_object_or_404(PendenteContaReceber, id=pendente_id)
    dados_empresa = DadosEmpresa.objects.first()
    if not dados_empresa:
        dados_empresa = type('Obj', (), {
            'nome': 'Conception Lda', 'nuit': '401932089',
            'endereco': '', 'telefone': '', 'representante_legal': None, 'cargo_representante': ''
        })()
    logo_url = ''
    if dados_empresa and getattr(dados_empresa, 'logo', None) and dados_empresa.logo:
        try:
            logo_url = f"{request.scheme}://{request.get_host()}{settings.MEDIA_URL}{dados_empresa.logo.name}"
        except Exception:
            logo_url = ''
    try:
        valor_extenso = __import__('num2words', fromlist=['num2words']).num2words(
            float(pendente.valor), lang='pt', to='currency', currency='EUR'
        ).replace('euros', 'meticais').replace('euro', 'metical')
    except Exception:
        valor_extenso = str(pendente.valor)
    hoje = timezone.now().date()
    rep = getattr(dados_empresa, 'representante_legal', None)
    ctx = {
        'dados_empresa': dados_empresa,
        'logo_url': logo_url,
        'numero_recibo': f"REC-REC-{hoje.year}-{pendente_id:06d}",
        'data_emissao': _data_extenso_pt(hoje),
        'representante_nome': rep.get_full_name() if rep else '',
        'representante_cargo': getattr(dados_empresa, 'cargo_representante', None) or 'Representante Legal',
        'valor': f"{pendente.valor:,.2f}".replace(',', ' ').replace('.', ',').replace(' ', '.'),
        'valor_extenso': valor_extenso,
        'descricao': pendente.descricao,
        'credor': pendente.credor,
        'data': _data_extenso_pt(pendente.data_vencimento or hoje),
    }
    html = render_to_string('financas/recibo_adiantamento_recebimento.html', ctx)
    result = io.BytesIO()
    pisa.CreatePDF(html.encode('utf-8'), dest=result, encoding='utf-8')
    result.seek(0)
    response = HttpResponse(result.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="recibo_adiantamento_recebimento_{pendente_id}.pdf"'
    return response


@require_financas_access
def financas_relatorio(request):
    """Relatório por período: totais por categoria e saldo. ?format=csv para exportar."""
    try:
        di, df, di_str, df_str = _parse_periodo(request, default_days=365)

        from .models_stock import OrdemCompra

        # Receitas — a partir dos lançamentos contabilísticos (reflecte confirmação de recebimentos)
        total_receitas_vendas, total_receitas_log = _receitas_from_lancamentos(di, df)
        total_receitas = total_receitas_vendas + total_receitas_log

        # Despesas
        ordens_compra = OrdemCompra.objects.filter(
            data_criacao__date__gte=di, data_criacao__date__lte=df, status='RECEBIDA',
        )
        total_despesas_compras = Decimal('0.00')
        for oc in ordens_compra:
            total_despesas_compras += sum(
                item.quantidade_solicitada * (item.preco_unitario or Decimal('0'))
                for item in oc.itens.all()
            )

        total_despesas_rh = Decimal('0.00')
        try:
            from .models_financas import LancamentoFinanceiro
            lanc_folha = LancamentoFinanceiro.objects.filter(
                data__gte=di, data__lte=df,
                conta__codigo='62.01', origem_tipo='RH',
            ).aggregate(s=Sum('valor'))
            total_despesas_rh = abs(lanc_folha['s'] or Decimal('0.00'))
        except Exception:
            pass
        try:
            from .models_rh import Treinamento
            trein = Treinamento.objects.filter(
                status='CONCLUIDO', custo_total__gt=0,
                data_fim__gte=di, data_fim__lte=df,
            ).aggregate(s=Sum('custo_total'))
            total_despesas_rh += trein['s'] or Decimal('0.00')
        except Exception:
            pass
        try:
            from .models_rh import TrabalhoEmpreitada
            emp = TrabalhoEmpreitada.objects.filter(
                status='CONCLUIDO', valor_fixo__gt=0,
                data_conclusao__gte=di, data_conclusao__lte=df,
            ).aggregate(s=Sum('valor_fixo'))
            total_despesas_rh += emp['s'] or Decimal('0.00')
        except Exception:
            pass

        total_despesas_log = Decimal('0.00')
        try:
            from .models_cost_billing import CustoLogistico
            cl = CustoLogistico.objects.filter(
                status='APROVADO',
                data_custo__gte=di, data_custo__lte=df,
            ).aggregate(s=Sum('valor'))
            total_despesas_log = cl['s'] or Decimal('0.00')
        except Exception:
            pass

        total_despesas = total_despesas_compras + total_despesas_rh + total_despesas_log
        saldo = total_receitas - total_despesas

        ctx_empresa = _context_empresa(request)
        dados_empresa = ctx_empresa.get('dados_empresa')

        if request.GET.get('format') == 'csv':
            buf = io.StringIO()
            w = csv.writer(buf)
            # Cabeçalho da empresa
            nome = getattr(dados_empresa, 'nome', None) or 'Conception Lda'
            w.writerow([nome])
            if getattr(dados_empresa, 'nuit', None):
                w.writerow(['NUIT:', getattr(dados_empresa, 'nuit', '')])
            if getattr(dados_empresa, 'endereco', None):
                w.writerow(['Morada:', getattr(dados_empresa, 'endereco', '')])
            if getattr(dados_empresa, 'telefone', None) or getattr(dados_empresa, 'email', None):
                w.writerow(['Contacto:', getattr(dados_empresa, 'telefone', '') or '', getattr(dados_empresa, 'email', '') or ''])
            w.writerow([])
            w.writerow(['Relatório Finanças', f'Período: {di_str} a {df_str}'])
            w.writerow([])
            w.writerow(['Conceito', 'Valor (MT)'])
            w.writerow(['Receitas - Prestação de Serviços', str(total_receitas_vendas)])
            w.writerow(['Receitas Logística', str(total_receitas_log)])
            w.writerow(['Total Receitas', str(total_receitas)])
            w.writerow(['Compras', str(total_despesas_compras)])
            w.writerow(['RH (folha)', str(total_despesas_rh)])
            w.writerow(['Custos Logística', str(total_despesas_log)])
            w.writerow(['Total Despesas', str(total_despesas)])
            w.writerow(['Saldo', str(saldo)])
            w.writerow([])
            w.writerow([f'Gerado em {timezone.now().strftime("%d/%m/%Y %H:%M")}'])
            resp = HttpResponse('\ufeff' + buf.getvalue(), content_type='text/csv; charset=utf-8-sig')
            resp['Content-Disposition'] = f'attachment; filename="relatorio_financas_{di_str}_{df_str}.csv"'
            return resp

        if request.GET.get('format') == 'xlsx':
            try:
                wb = _excel_relatorio_organizado(
                    titulo='Relatório Finanças',
                    periodo_str=f'{di_str} a {df_str}',
                    headers=['Conceito', 'Valor (MT)'],
                    rows=[
                        ['Receitas - Prestação de Serviços', float(total_receitas_vendas)],
                        ['Receitas Logística', float(total_receitas_log)],
                        ['Total Receitas', float(total_receitas)],
                        ['Compras', float(total_despesas_compras)],
                        ['RH (folha)', float(total_despesas_rh)],
                        ['Custos Logística', float(total_despesas_log)],
                        ['Total Despesas', float(total_despesas)],
                        ['Saldo', float(saldo)],
                    ],
                    col_larguras=[30, 18],
                    total_row_indices=[2, 6, 7],
                    dados_empresa=dados_empresa,
                )
                buf = io.BytesIO()
                wb.save(buf)
                buf.seek(0)
                resp = HttpResponse(buf.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                resp['Content-Disposition'] = f'attachment; filename="relatorio_financas_{di_str}_{df_str}.xlsx"'
                return resp
            except ImportError:
                pass  # openpyxl não instalado, continuar sem Excel

        if request.GET.get('format') == 'pdf':
            from reportlab.lib.pagesizes import A4
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib import colors
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
            styles = getSampleStyleSheet()
            emp_style = ParagraphStyle(name='Empresa', parent=styles['Normal'], fontSize=11, textColor=colors.HexColor('#374151'))
            emp_small = ParagraphStyle(name='EmpresaSmall', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#6b7280'))
            title_style = ParagraphStyle(name='Title', parent=styles['Heading1'], fontSize=16, textColor=colors.HexColor('#1e3a5f'))
            flow = []
            # Cabeçalho da empresa
            nome = getattr(dados_empresa, 'nome', None) or 'Conception Lda'
            flow.append(Paragraph(f'<b>{nome}</b>', emp_style))
            if getattr(dados_empresa, 'nuit', None):
                flow.append(Paragraph(f'NUIT: {dados_empresa.nuit}', emp_small))
            if getattr(dados_empresa, 'endereco', None):
                flow.append(Paragraph(dados_empresa.endereco, emp_small))
            if getattr(dados_empresa, 'telefone', None) or getattr(dados_empresa, 'email', None):
                contactos = []
                if getattr(dados_empresa, 'telefone', None):
                    contactos.append(f'Tel: {dados_empresa.telefone}')
                if getattr(dados_empresa, 'email', None):
                    contactos.append(f'Email: {dados_empresa.email}')
                flow.append(Paragraph('  |  '.join(contactos), emp_small))
            flow.append(Spacer(1, 16))
            flow.append(Paragraph('Relatório Finanças', title_style))
            flow.append(Paragraph(f'Período: {di_str} a {df_str}', emp_small))
            flow.append(Spacer(1, 20))
            data = [
                ['Conceito', 'Valor (MT)'],
                ['Receitas - Prestação de Serviços', f'{total_receitas_vendas:.2f}'],
                ['Receitas Logística', f'{total_receitas_log:.2f}'],
                ['Total Receitas', f'{total_receitas:.2f}'],
                ['Compras', f'{total_despesas_compras:.2f}'],
                ['RH (folha)', f'{total_despesas_rh:.2f}'],
                ['Custos Logística', f'{total_despesas_log:.2f}'],
                ['Total Despesas', f'{total_despesas:.2f}'],
                ['Saldo', f'{saldo:.2f}'],
            ]
            t = Table(data)
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a5f')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#c5d0de')),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
                ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor('#e8eef4')),
                ('BACKGROUND', (0, 6), (-1, 7), colors.HexColor('#e8eef4')),
            ]))
            flow.append(t)
            flow.append(Spacer(1, 12))
            flow.append(Paragraph(f'Gerado em {timezone.now().strftime("%d/%m/%Y %H:%M")}', emp_small))
            doc.build(flow)
            resp = HttpResponse(buffer.getvalue(), content_type='application/pdf')
            resp['Content-Disposition'] = f'attachment; filename="relatorio_financas_{di_str}_{df_str}.pdf"'
            return resp

        context = {
            'title': 'Relatório por período',
            'data_inicio': di_str,
            'data_fim': df_str,
            'total_receitas': total_receitas,
            'total_receitas_vendas': total_receitas_vendas,
            'total_receitas_log': total_receitas_log,
            'total_despesas': total_despesas,
            'total_despesas_compras': total_despesas_compras,
            'total_despesas_rh': total_despesas_rh,
            'total_despesas_log': total_despesas_log,
            'saldo': saldo,
        }
        context.update(_context_empresa(request))
        return render(request, 'financas/relatorio.html', context)
    except Exception as e:
        logger.error(f'Erro ao carregar relatório Finanças: {e}', exc_info=True)
        messages.error(request, 'Erro ao carregar relatório.')
        return redirect('financas:main')


@require_financas_access
def financas_plano_contas(request):
    """Listagem do Plano de Contas (contas activas)."""
    try:
        from .models_financas import Conta
        contas = Conta.objects.filter(ativo=True).select_related('conta_pai').order_by('codigo')
        context = {
            'title': 'Plano de Contas',
            'contas': contas,
        }
        return render(request, 'financas/plano_contas.html', context)
    except Exception as e:
        logger.error(f'Erro ao carregar plano de contas: {e}', exc_info=True)
        messages.error(request, 'Erro ao carregar plano de contas.')
        return redirect('financas:main')


@require_financas_access
def financas_movimentos(request):
    """Livro de movimentos financeiros; filtro por período; formulário para lançamento manual."""
    try:
        from .models_financas import Conta, LancamentoFinanceiro

        di, df, di_str, df_str = _parse_periodo(request, default_days=90)

        if request.method == 'POST':
            # Lançamento manual
            conta_id = request.POST.get('conta')
            valor_str = request.POST.get('valor', '0').replace(',', '.')
            descricao = (request.POST.get('descricao') or '').strip()
            documento_ref = (request.POST.get('documento_ref') or '').strip()
            data_str = request.POST.get('data', '')
            if not conta_id or not descricao or not data_str:
                messages.error(request, 'Preencha conta, data e descrição.')
            else:
                try:
                    data = datetime.strptime(data_str, '%Y-%m-%d').date()
                    valor = Decimal(valor_str or '0')
                    conta = Conta.objects.get(pk=conta_id, ativo=True)
                    LancamentoFinanceiro.objects.create(
                        data=data,
                        conta=conta,
                        valor=valor,
                        descricao=descricao,
                        documento_ref=documento_ref,
                        origem_tipo='MANUAL',
                        criado_por=request.user,
                    )
                    messages.success(request, 'Lançamento registado.')
                    return redirect('financas:movimentos')
                except (ValueError, Conta.DoesNotExist) as e:
                    messages.error(request, f'Dados inválidos: {e}')

        movimentos_qs = LancamentoFinanceiro.objects.filter(
            data__gte=di,
            data__lte=df,
        ).select_related('conta', 'criado_por').order_by('-data', '-data_criacao')
        movimentos = list(movimentos_qs[:200])
        total_entradas = sum(m.valor for m in movimentos if m.valor > 0)
        total_saidas = sum(-m.valor for m in movimentos if m.valor < 0)
        contas_ativas = Conta.objects.filter(ativo=True).order_by('codigo')

        ctx_empresa = _context_empresa(request)
        dados_empresa = ctx_empresa.get('dados_empresa')

        if request.GET.get('format') == 'xlsx':
            try:
                csv_entradas = movimentos_qs.filter(valor__gt=0).aggregate(s=Sum('valor'))['s'] or Decimal('0.00')
                csv_saidas = movimentos_qs.filter(valor__lt=0).aggregate(s=Sum('valor'))['s'] or Decimal('0.00')
                csv_saidas = -csv_saidas
                rows = []
                for m in movimentos_qs[:2000]:
                    rows.append([
                        m.data.strftime('%d/%m/%Y') if m.data else '',
                        f"{m.conta.codigo} - {m.conta.nome}" if m.conta else '',
                        (m.descricao or '')[:80],
                        float(m.valor),
                        m.documento_ref or '',
                        m.get_origem_tipo_display() if m.origem_tipo else '',
                    ])
                rows.append(['', '', 'Total entradas', float(csv_entradas), '', ''])
                rows.append(['', '', 'Total saídas', float(csv_saidas), '', ''])
                n = len(rows)
                wb = _excel_relatorio_organizado(
                    titulo='Movimentos Financeiros',
                    periodo_str=f'{di_str} a {df_str}',
                    headers=['Data', 'Conta', 'Descrição', 'Valor (MT)', 'Doc. ref', 'Origem'],
                    rows=rows,
                    col_larguras=[12, 22, 38, 14, 16, 14],
                    total_row_indices=[n - 2, n - 1],
                    dados_empresa=dados_empresa,
                )
                buf = io.BytesIO()
                wb.save(buf)
                buf.seek(0)
                resp = HttpResponse(buf.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                resp['Content-Disposition'] = f'attachment; filename="movimentos_financas_{di_str}_{df_str}.xlsx"'
                return resp
            except ImportError:
                pass

        if request.GET.get('format') == 'csv':
            csv_entradas = movimentos_qs.filter(valor__gt=0).aggregate(s=Sum('valor'))['s'] or Decimal('0.00')
            csv_saidas = movimentos_qs.filter(valor__lt=0).aggregate(s=Sum('valor'))['s'] or Decimal('0.00')
            csv_saidas = -csv_saidas
            buf = io.StringIO()
            w = csv.writer(buf)
            nome = getattr(dados_empresa, 'nome', None) or 'Conception Lda'
            w.writerow([nome])
            if getattr(dados_empresa, 'nuit', None):
                w.writerow(['NUIT:', getattr(dados_empresa, 'nuit', '')])
            if getattr(dados_empresa, 'endereco', None):
                w.writerow(['Morada:', getattr(dados_empresa, 'endereco', '')])
            if getattr(dados_empresa, 'telefone', None) or getattr(dados_empresa, 'email', None):
                w.writerow(['Contacto:', getattr(dados_empresa, 'telefone', '') or '', getattr(dados_empresa, 'email', '') or ''])
            w.writerow([])
            w.writerow(['Movimentos Financeiros', f'Período: {di_str} a {df_str}'])
            w.writerow([])
            w.writerow(['Data', 'Conta', 'Descrição', 'Valor (MT)', 'Doc. ref', 'Origem'])
            for m in movimentos_qs[:2000]:
                w.writerow([
                    m.data.strftime('%Y-%m-%d') if m.data else '',
                    f"{m.conta.codigo} - {m.conta.nome}" if m.conta else '',
                    m.descricao or '',
                    str(m.valor),
                    m.documento_ref or '',
                    m.get_origem_tipo_display() if m.origem_tipo else '',
                ])
            w.writerow([])
            w.writerow(['Total entradas', '', '', str(csv_entradas), '', ''])
            w.writerow(['Total saídas', '', '', str(csv_saidas), '', ''])
            w.writerow([])
            w.writerow([f'Gerado em {timezone.now().strftime("%d/%m/%Y %H:%M")}'])
            resp = HttpResponse('\ufeff' + buf.getvalue(), content_type='text/csv; charset=utf-8-sig')
            resp['Content-Disposition'] = f'attachment; filename="movimentos_financas_{di_str}_{df_str}.csv"'
            return resp

        context = {
            'title': 'Movimentos financeiros',
            'data_inicio': di_str,
            'data_fim': df_str,
            'movimentos': movimentos,
            'total_entradas': total_entradas,
            'total_saidas': total_saidas,
            'contas': contas_ativas,
        }
        return render(request, 'financas/movimentos.html', context)
    except Exception as e:
        logger.error(f'Erro ao carregar movimentos: {e}', exc_info=True)
        messages.error(request, 'Erro ao carregar movimentos.')
        return redirect('financas:main')


@require_financas_access
def financas_balanco_dre(request):
    """Balanço e Demonstração de Resultados por período (a partir dos lançamentos)."""
    try:
        from .models_financas import Conta, LancamentoFinanceiro

        di, df, di_str, df_str = _parse_periodo(request, default_days=365)

        # DRE: receitas e despesas (soma por tipo de conta)
        receitas_agg = LancamentoFinanceiro.objects.filter(
            data__gte=di, data__lte=df, conta__tipo='RECEITA'
        ).aggregate(s=Sum('valor'))
        despesas_agg = LancamentoFinanceiro.objects.filter(
            data__gte=di, data__lte=df, conta__tipo='DESPESA'
        ).aggregate(s=Sum('valor'))
        total_receitas_dre = receitas_agg['s'] or Decimal('0.00')
        total_despesas_dre = despesas_agg['s'] or Decimal('0.00')
        resultado_dre = total_receitas_dre - total_despesas_dre

        # Balanço: saldos acumulados até à data fim (data__lte=df), não só "no período"
        balanco = {}
        balanco_por_conta = {}
        for t in ['ATIVO', 'PASSIVO', 'PATRIMONIO']:
            agg = LancamentoFinanceiro.objects.filter(
                data__lte=df, conta__tipo=t
            ).aggregate(s=Sum('valor'))
            balanco[t] = agg['s'] or Decimal('0.00')
            # Detalhe por conta (código, nome, saldo acumulado até df)
            contas_tipo = (
                LancamentoFinanceiro.objects.filter(data__lte=df, conta__tipo=t)
                .values('conta__codigo', 'conta__nome')
                .annotate(saldo=Sum('valor'))
                .order_by('conta__codigo')
            )
            balanco_por_conta[t] = [
                {'codigo': r['conta__codigo'] or '—', 'nome': r['conta__nome'] or '—', 'saldo': r['saldo'] or Decimal('0.00')}
                for r in contas_tipo
            ]

        context = {
            'title': 'Balanço e DRE',
            'data_inicio': di_str,
            'data_fim': df_str,
            'total_receitas_dre': total_receitas_dre,
            'total_despesas_dre': total_despesas_dre,
            'resultado_dre': resultado_dre,
            'balanco': balanco,
            'balanco_por_conta': balanco_por_conta,
        }
        context.update(_context_empresa(request))
        return render(request, 'financas/balanco_dre.html', context)
    except Exception as e:
        logger.error(f'Erro ao carregar balanço/DRE: {e}', exc_info=True)
        messages.error(request, 'Erro ao carregar balanço e DRE.')
        return redirect('financas:main')


@require_financas_access
def financas_razao(request):
    """Livro razão: lançamentos por conta (filtro por conta e período)."""
    try:
        from .models_financas import Conta, LancamentoFinanceiro

        di, df, di_str, df_str = _parse_periodo(request, default_days=90)
        conta_id = request.GET.get('conta_id', '').strip()
        conta_selecionada = None
        movimentos = []
        total_conta = Decimal('0.00')

        if conta_id:
            try:
                conta_selecionada = Conta.objects.get(pk=conta_id, ativo=True)
                movimentos = LancamentoFinanceiro.objects.filter(
                    data__gte=di, data__lte=df, conta=conta_selecionada
                ).order_by('data', 'data_criacao')
                total_conta = sum(m.valor for m in movimentos)
            except (Conta.DoesNotExist, ValueError):
                conta_selecionada = None

        contas = Conta.objects.filter(ativo=True).order_by('codigo')

        context = {
            'title': 'Livro razão',
            'data_inicio': di_str,
            'data_fim': df_str,
            'contas': contas,
            'conta_selecionada': conta_selecionada,
            'movimentos': movimentos,
            'total_conta': total_conta,
        }
        return render(request, 'financas/razao.html', context)
    except Exception as e:
        logger.error(f'Erro ao carregar livro razão: {e}', exc_info=True)
        messages.error(request, 'Erro ao carregar livro razão.')
        return redirect('financas:main')


# Contas padrão para importação de totais — PGC-NIRF MZ (Decreto 70/2009)
# Compras de stock são registadas em 21 Inventários ao receber OC; não importar como despesa para não duplicar.
_CONTAS_IMPORT = [
    ('71.01', 'Receitas de Vendas', 'RECEITA', 'VENDAS'),
    ('72.01', 'Receitas Logística (faturamento)', 'RECEITA', 'LOGISTICA'),
    ('62.01', 'Pessoal (folha)', 'DESPESA', 'RH'),
    ('63.01', 'Custos Logística', 'DESPESA', 'LOGISTICA'),
]


@require_financas_access
def financas_importar_totais(request):
    """Importa totais do período (dashboard) para o livro como lançamentos (uma linha por origem)."""
    try:
        from .models_financas import Conta, LancamentoFinanceiro

        di, df, di_str, df_str = _parse_periodo(request, default_days=30)
        doc_ref = f"IMP-{di_str}-{df_str}"
        desc_base = f"{di.strftime('%d/%m/%Y')} a {df.strftime('%d/%m/%Y')}"

        if request.method == 'POST':
            if LancamentoFinanceiro.objects.filter(documento_ref=doc_ref).exists():
                messages.warning(request, f'Já existe importação para o período {desc_base}. Não foram criados duplicados.')
                return redirect('financas:movimentos')

            totais = _compute_totais_periodo(di, df)
            # Para importar: despesas_rh = apenas folhas (treinamentos e empreitadas criam lançamentos próprios)
            totais_import = dict(totais)
            try:
                from .models_rh import Treinamento, TrabalhoEmpreitada
                trein_sum = Treinamento.objects.filter(
                    status='CONCLUIDO', custo_total__gt=0,
                    data_fim__gte=di, data_fim__lte=df,
                ).aggregate(s=Sum('custo_total'))['s'] or Decimal('0.00')
                emp_sum = TrabalhoEmpreitada.objects.filter(
                    status='CONCLUIDO', valor_fixo__gt=0,
                    data_conclusao__gte=di, data_conclusao__lte=df,
                ).aggregate(s=Sum('valor_fixo'))['s'] or Decimal('0.00')
                totais_import['despesas_rh'] = totais['despesas_rh'] - trein_sum - emp_sum
            except Exception:
                pass
            # Receitas NÃO são importadas: já vêm do fluxo normal (confirmar conta receber).
            # Importar receitas duplicaria os lançamentos existentes em 71.01 e 72.01.
            linhas = [
                ('despesas_rh', 'Pessoal (folha)', '62.01', 'DESPESA', 'RH'),
                ('despesas_logistica', 'Custos Logística', '63.01', 'DESPESA', 'LOGISTICA'),
            ]
            criados = 0
            for key, nome, codigo, tipo, origem in linhas:
                valor = totais_import.get(key, totais[key])
                if valor == Decimal('0.00'):
                    continue
                conta, _ = Conta.objects.get_or_create(
                    codigo=codigo,
                    defaults={'nome': nome, 'tipo': tipo, 'ativo': True, 'ordem': 0},
                )
                if conta.tipo != tipo:
                    conta.tipo = tipo
                    conta.nome = nome
                    conta.save(update_fields=['tipo', 'nome'])
                LancamentoFinanceiro.objects.create(
                    data=df,
                    conta=conta,
                    valor=valor,
                    descricao=f"{nome} ({desc_base})",
                    documento_ref=doc_ref,
                    origem_tipo=origem,
                    criado_por=request.user,
                )
                criados += 1
            messages.success(request, f'Importação concluída: {criados} lançamento(s) criado(s) para o período {desc_base}.')
            return redirect('financas:movimentos')

        totais = _compute_totais_periodo(di, df)
        context = {
            'title': 'Importar totais do período',
            'data_inicio': di_str,
            'data_fim': df_str,
            'totais': totais,
        }
        return render(request, 'financas/importar_totais.html', context)
    except Exception as e:
        logger.error(f'Erro ao importar totais: {e}', exc_info=True)
        messages.error(request, 'Erro ao importar totais.')
        return redirect('financas:main')


@require_financas_access
def financas_iva(request):
    """Relatório IVA por período: base tributável e IVA estimados (vendas e compras)."""
    try:
        from .models_base import ConfiguracaoFiscal

        di, df, di_str, df_str = _parse_periodo(request, default_days=365)
        totais = _compute_totais_periodo(di, df)
        taxa_decimal = ConfiguracaoFiscal.get_taxa_iva_atual()
        taxa_pct = taxa_decimal * Decimal('100')

        # Vendas: assumir que valor_total inclui IVA (base = total / (1+taxa), iva = total - base)
        total_vendas = totais['receitas_vendas'] + totais['receitas_logistica']
        if total_vendas > 0:
            base_vendas = total_vendas / (Decimal('1') + taxa_decimal)
            iva_vendas = total_vendas - base_vendas
        else:
            base_vendas = iva_vendas = Decimal('0.00')

        # Compras: mesma hipótese para IVA dedutível
        total_compras = totais['despesas_compras']
        if total_compras > 0:
            base_compras = total_compras / (Decimal('1') + taxa_decimal)
            iva_compras = total_compras - base_compras
        else:
            base_compras = iva_compras = Decimal('0.00')

        iva_a_pagar = iva_vendas - iva_compras

        ctx_empresa_iva = _context_empresa(request)
        dados_empresa_iva = ctx_empresa_iva.get('dados_empresa')

        if request.GET.get('format') == 'csv':
            buf = io.StringIO()
            w = csv.writer(buf)
            nome = getattr(dados_empresa_iva, 'nome', None) or 'Conception Lda'
            w.writerow([nome])
            if getattr(dados_empresa_iva, 'nuit', None):
                w.writerow(['NUIT:', getattr(dados_empresa_iva, 'nuit', '')])
            if getattr(dados_empresa_iva, 'endereco', None):
                w.writerow(['Morada:', getattr(dados_empresa_iva, 'endereco', '')])
            if getattr(dados_empresa_iva, 'telefone', None) or getattr(dados_empresa_iva, 'email', None):
                w.writerow(['Contacto:', getattr(dados_empresa_iva, 'telefone', '') or '', getattr(dados_empresa_iva, 'email', '') or ''])
            w.writerow([])
            w.writerow(['Relatório IVA', f'Período: {di_str} a {df_str}'])
            w.writerow(['Taxa IVA', f'{taxa_pct}%'])
            w.writerow([])
            w.writerow(['Conceito', 'Base (MT)', 'IVA (MT)', 'Total (MT)'])
            w.writerow(['Prestação de Serviços e Logística (receitas)', str(base_vendas), str(iva_vendas), str(total_vendas)])
            w.writerow(['Compras (dedutível)', str(base_compras), str(-iva_compras), str(total_compras)])
            w.writerow(['IVA a pagar (estimado)', '', str(iva_a_pagar), ''])
            w.writerow([])
            w.writerow([f'Gerado em {timezone.now().strftime("%d/%m/%Y %H:%M")}'])
            resp = HttpResponse('\ufeff' + buf.getvalue(), content_type='text/csv; charset=utf-8-sig')
            resp['Content-Disposition'] = f'attachment; filename="relatorio_iva_{di_str}_{df_str}.csv"'
            return resp

        if request.GET.get('format') == 'xlsx':
            try:
                wb = _excel_relatorio_organizado(
                    titulo='Relatório IVA',
                    periodo_str=f'{di_str} a {df_str}',
                    metadata=f'Taxa IVA: {taxa_pct}%',
                    headers=['Conceito', 'Base (MT)', 'IVA (MT)', 'Total (MT)'],
                    rows=[
                        ['Prestação de Serviços e Logística (receitas)', float(base_vendas), float(iva_vendas), float(total_vendas)],
                        ['Compras (dedutível)', float(base_compras), float(-iva_compras), float(total_compras)],
                        ['IVA a pagar (estimado)', '', float(iva_a_pagar), ''],
                    ],
                    col_larguras=[28, 14, 14, 14],
                    total_row_indices=[2],
                    dados_empresa=dados_empresa_iva,
                )
                buf = io.BytesIO()
                wb.save(buf)
                buf.seek(0)
                resp = HttpResponse(buf.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                resp['Content-Disposition'] = f'attachment; filename="relatorio_iva_{di_str}_{df_str}.xlsx"'
                return resp
            except ImportError:
                messages.error(request, 'Exportação Excel não disponível (instale openpyxl).')
                return redirect('financas:iva')

        context = {
            'title': 'Relatório IVA',
            'data_inicio': di_str,
            'data_fim': df_str,
            'taxa_pct': taxa_pct,
            'total_vendas': total_vendas,
            'base_vendas': base_vendas,
            'iva_vendas': iva_vendas,
            'total_compras': total_compras,
            'base_compras': base_compras,
            'iva_compras': iva_compras,
            'iva_a_pagar': iva_a_pagar,
        }
        context.update(_context_empresa(request))
        return render(request, 'financas/iva.html', context)
    except Exception as e:
        logger.error(f'Erro ao carregar relatório IVA: {e}', exc_info=True)
        messages.error(request, 'Erro ao carregar relatório IVA.')
        return redirect('financas:main')


@require_financas_access
def financas_numeracao(request):
    """Página de controlo de numeração sequencial (séries por ano) para facturas/recibos."""
    try:
        from .models_financas import ContadorSerieDocumento

        contadores = ContadorSerieDocumento.objects.all().order_by('serie', '-ano')
        context = {
            'title': 'Numeração de documentos',
            'contadores': contadores,
        }
        return render(request, 'financas/numeracao.html', context)
    except Exception as e:
        logger.error(f'Erro ao carregar numeração: {e}', exc_info=True)
        messages.error(request, 'Erro ao carregar numeração.')
        return redirect('financas:main')


@require_financas_access
def financas_irpc(request):
    """Relatório IRPC por período: resultado (receitas - despesas) e IRPC estimado."""
    try:
        from .models_base import ConfiguracaoFiscal

        di, df, di_str, df_str = _parse_periodo(request, default_days=365)
        totais = _compute_totais_periodo(di, df)
        total_receitas = totais['receitas_vendas'] + totais['receitas_logistica']
        total_despesas = totais['despesas_compras'] + totais['despesas_rh'] + totais['despesas_logistica']
        resultado = total_receitas - total_despesas
        taxa_decimal = ConfiguracaoFiscal.get_taxa_irpc_atual()
        taxa_pct = taxa_decimal * Decimal('100')
        irpc_estimado = (resultado * taxa_decimal) if resultado > 0 else Decimal('0.00')

        context = {
            'title': 'Relatório IRPC',
            'data_inicio': di_str,
            'data_fim': df_str,
            'total_receitas': total_receitas,
            'total_despesas': total_despesas,
            'resultado': resultado,
            'taxa_pct': taxa_pct,
            'irpc_estimado': irpc_estimado,
        }
        context.update(_context_empresa(request))
        return render(request, 'financas/irpc.html', context)
    except Exception as e:
        logger.error(f'Erro ao carregar relatório IRPC: {e}', exc_info=True)
        messages.error(request, 'Erro ao carregar relatório IRPC.')
        return redirect('financas:main')


@require_financas_access
def financas_retencao(request):
    """Política de retenção de documentos: prazo configurado e alertas (documentos a atingir o prazo)."""
    try:
        from .models_base import ConfiguracaoFiscal
        from .models_financas import LancamentoFinanceiro

        config = ConfiguracaoFiscal.objects.filter(ativo=True, padrao=True).first()
        prazo_anos = getattr(config, 'prazo_retencao_documentos_anos', None) or 10
        prazo_anos = int(prazo_anos) if prazo_anos is not None else 10

        hoje = timezone.now().date()
        limite_antigo = hoje - timedelta(days=prazo_anos * 365)
        # Alertas: documentos com data anterior a (prazo - 1) ano que em breve atingirão o prazo
        limite_alerta = hoje - timedelta(days=max(0, prazo_anos - 1) * 365) if prazo_anos > 1 else limite_antigo

        # Movimentos mais antigos (para consciencialização)
        antigos = (
            LancamentoFinanceiro.objects.filter(data__lt=limite_alerta)
            .order_by('data')[:50]
            .select_related('conta', 'criado_por')
        )
        total_antigos = LancamentoFinanceiro.objects.filter(data__lt=limite_antigo).count()

        context = {
            'title': 'Política de retenção',
            'prazo_anos': prazo_anos,
            'limite_antigo': limite_antigo,
            'limite_alerta': limite_alerta,
            'antigos': antigos,
            'total_antigos': total_antigos,
            'alertas_count': LancamentoFinanceiro.objects.filter(data__lt=limite_alerta).count(),
        }
        return render(request, 'financas/retencao.html', context)
    except Exception as e:
        logger.error(f'Erro ao carregar retenção: {e}', exc_info=True)
        messages.error(request, 'Erro ao carregar política de retenção.')
        return redirect('financas:main')


@require_financas_access
def financas_tesouraria(request):
    """Registar cobranças (cliente pagou: 26+ / 22-) e pagamentos (pagámos fornecedor: 32- / 26-) — partida dupla."""
    try:
        from .models_financas import Conta, LancamentoFinanceiro

        if request.method == 'POST':
            tipo = request.POST.get('tipo')  # 'cobranca' ou 'pagamento'
            data_str = request.POST.get('data', '').strip()
            valor_str = request.POST.get('valor', '0').replace(',', '.')
            descricao = (request.POST.get('descricao') or '').strip()
            documento_ref = (request.POST.get('documento_ref') or '').strip()
            if not data_str or not descricao:
                messages.error(request, 'Preencha data e descrição.')
            else:
                try:
                    data = datetime.strptime(data_str, '%Y-%m-%d').date()
                    valor = Decimal(valor_str or '0')
                    if valor <= 0:
                        messages.error(request, 'O valor deve ser positivo.')
                    else:
                        with transaction.atomic():
                            conta_26, _ = Conta.objects.get_or_create(
                                codigo='26',
                                defaults={'nome': 'Caixa e depósitos bancários', 'tipo': 'ATIVO', 'ativo': True, 'ordem': 0},
                            )
                            conta_22, _ = Conta.objects.get_or_create(
                                codigo='22',
                                defaults={'nome': 'Clientes e outros devedores', 'tipo': 'ATIVO', 'ativo': True, 'ordem': 0},
                            )
                            conta_32, _ = Conta.objects.get_or_create(
                                codigo='32',
                                defaults={'nome': 'Fornecedores e outros credores', 'tipo': 'PASSIVO', 'ativo': True, 'ordem': 0},
                            )
                            if tipo == 'cobranca':
                                # Cobrança: cliente pagou — Débito 26 (caixa), Crédito 22 (clientes)
                                LancamentoFinanceiro.objects.create(
                                    data=data, conta=conta_26, valor=valor,
                                    descricao=descricao, documento_ref=documento_ref, origem_tipo='MANUAL',
                                    criado_por=request.user,
                                )
                                LancamentoFinanceiro.objects.create(
                                    data=data, conta=conta_22, valor=-valor,
                                    descricao=descricao, documento_ref=documento_ref, origem_tipo='MANUAL',
                                    criado_por=request.user,
                                )
                                messages.success(request, 'Cobrança registada (Caixa +, Clientes -).')
                            elif tipo == 'pagamento':
                                # Pagamento: pagámos fornecedor — Débito 32 (fornecedores), Crédito 26 (caixa)
                                LancamentoFinanceiro.objects.create(
                                    data=data, conta=conta_32, valor=-valor,
                                    descricao=descricao, documento_ref=documento_ref, origem_tipo='MANUAL',
                                    criado_por=request.user,
                                )
                                LancamentoFinanceiro.objects.create(
                                    data=data, conta=conta_26, valor=-valor,
                                    descricao=descricao, documento_ref=documento_ref, origem_tipo='MANUAL',
                                    criado_por=request.user,
                                )
                                messages.success(request, 'Pagamento registado (Fornecedores -, Caixa -).')
                            else:
                                messages.error(request, 'Tipo inválido.')
                        return redirect('financas:tesouraria')
                except ValueError as e:
                    messages.error(request, f'Dados inválidos: {e}')

        hoje = timezone.now().date().isoformat()
        context = {'title': 'Tesouraria — Cobranças e pagamentos', 'hoje': hoje}
        return render(request, 'financas/tesouraria.html', context)
    except Exception as e:
        logger.error(f'Erro tesouraria: {e}', exc_info=True)
        messages.error(request, 'Erro ao registar.')
        return redirect('financas:main')

