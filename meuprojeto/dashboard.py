from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import render
from django.utils import timezone


def _safe_count(getter, default=0):
    try:
        return getter()
    except Exception:
        return default


@login_required(login_url='login')
def dashboard_view(request):
    from meuprojeto.empresa.models_base import DadosEmpresa, Sucursal
    from meuprojeto.empresa.models_financas import LancamentoFinanceiro, PendenteContaPagar, PendenteContaReceber
    from meuprojeto.empresa.models_marketing import CampanhaMarketing
    from meuprojeto.empresa.models_producao_servicos import OrdemProducao, OrdemServico, ProcessoProducao
    from meuprojeto.empresa.models_rh import Departamento, Funcionario
    from meuprojeto.empresa.models_stock import Item

    funcionarios_ativos = _safe_count(
        lambda: Funcionario.objects.filter(status='AT').count()
    )
    departamentos = _safe_count(lambda: Departamento.objects.count())
    produtos_ativos = _safe_count(
        lambda: Item.objects.filter(status='ATIVO').count()
    )
    itens_stock = _safe_count(lambda: Item.objects.count())
    orcamentos = _safe_count(
        lambda: OrdemServico.objects.filter(codigo__startswith='COT').count()
    )
    pedidos_venda = _safe_count(
        lambda: OrdemServico.objects.filter(codigo__startswith='OS').count()
    )
    ordens_producao = _safe_count(lambda: OrdemProducao.objects.count())
    producao_em_curso = _safe_count(
        lambda: OrdemProducao.objects.exclude(
            fase_atual__in=['FINALIZADA', 'CANCELADA']
        ).count()
    )
    processos_ativos = _safe_count(
        lambda: ProcessoProducao.objects.filter(status__in=['ATIVO', 'APROVADO']).count()
    )
    campanhas_ativas = _safe_count(
        lambda: CampanhaMarketing.objects.filter(ativo=True).count()
    )
    campanhas_em_curso = _safe_count(
        lambda: CampanhaMarketing.objects.filter(estado='EM_CURSO', ativo=True).count()
    )
    lancamentos_financeiros = _safe_count(lambda: LancamentoFinanceiro.objects.count())
    pendentes_financeiros = _safe_count(
        lambda: (
            PendenteContaPagar.objects.count() + PendenteContaReceber.objects.count()
        )
    )
    empresas = _safe_count(lambda: DadosEmpresa.objects.count())
    sucursais_ativas = _safe_count(lambda: Sucursal.objects.filter(ativa=True).count())

    modules = [
        {
            'url': '/rh/',
            'accent': 'rh',
            'icon': 'fa-users-cog',
            'title': 'Gestão de RH',
            'description': (
                'Funcionários, departamentos, presenças, folha salarial '
                'e processos de recursos humanos.'
            ),
            'stat_primary': funcionarios_ativos,
            'stat_primary_label': 'Funcionários ativos',
            'stat_secondary': departamentos,
            'stat_secondary_label': 'Departamentos',
        },
        {
            'url': '/stock/',
            'accent': 'stock',
            'icon': 'fa-warehouse',
            'title': 'Gestão de Stock e Logística',
            'description': (
                'Inventário, movimentações, requisições, logística '
                'e distribuição integrada.'
            ),
            'stat_primary': produtos_ativos,
            'stat_primary_label': 'Itens ativos',
            'stat_secondary': itens_stock,
            'stat_secondary_label': 'Total de itens',
        },
        {
            'url': '/vendas/',
            'accent': 'vendas',
            'icon': 'fa-shopping-cart',
            'title': 'Vendas',
            'description': (
                'Orçamentos, pedidos, faturamento e gestão comercial '
                'ligada a produção e serviços.'
            ),
            'stat_primary': orcamentos,
            'stat_primary_label': 'Orçamentos',
            'stat_secondary': pedidos_venda,
            'stat_secondary_label': 'Pedidos (OS)',
        },
        {
            'url': '/producao/',
            'accent': 'producao',
            'icon': 'fa-industry',
            'title': 'Produção',
            'description': (
                'Ordens de produção, serviços, receitas, máquinas, '
                'propostas técnicas e planeamento.'
            ),
            'stat_primary': ordens_producao,
            'stat_primary_label': 'Ordens de produção',
            'stat_secondary': producao_em_curso,
            'stat_secondary_label': 'Em curso',
        },
        {
            'url': '/marketing/',
            'accent': 'marketing',
            'icon': 'fa-bullhorn',
            'title': 'Marketing',
            'description': (
                'Campanhas, publicações, investimentos e acompanhamento '
                'de métricas de marketing.'
            ),
            'stat_primary': campanhas_ativas,
            'stat_primary_label': 'Campanhas ativas',
            'stat_secondary': campanhas_em_curso,
            'stat_secondary_label': 'Em curso',
        },
        {
            'url': '/financas/',
            'accent': 'financas',
            'icon': 'fa-coins',
            'title': 'Finanças',
            'description': (
                'Contas a pagar e receber, lançamentos, plano de contas '
                'e relatórios financeiros.'
            ),
            'stat_primary': lancamentos_financeiros,
            'stat_primary_label': 'Lançamentos',
            'stat_secondary': pendentes_financeiros,
            'stat_secondary_label': 'Pendentes',
        },
        {
            'url': '/admin/empresa/dadosempresa/',
            'accent': 'empresa',
            'icon': 'fa-building',
            'title': 'Empresas e Sucursais',
            'description': (
                'Dados da empresa, sucursais e configurações '
                'estruturais do sistema.'
            ),
            'stat_primary': empresas,
            'stat_primary_label': 'Empresas',
            'stat_secondary': sucursais_ativas,
            'stat_secondary_label': 'Sucursais ativas',
        },
    ]

    context = {
        'username': request.user.get_full_name() or request.user.username,
        'last_login': request.user.last_login,
        'current_time': timezone.now(),
        'total_users': User.objects.count(),
        'is_admin': request.user.is_superuser,
        'modules': modules,
        'summary': {
            'funcionarios_ativos': funcionarios_ativos,
            'orcamentos_abertos': orcamentos,
            'ordens_producao_abertas': producao_em_curso,
            'pendentes_financeiros': pendentes_financeiros,
        },
    }
    return render(request, 'dashboard.html', context)
