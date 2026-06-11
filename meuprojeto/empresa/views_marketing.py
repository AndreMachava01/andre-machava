"""
Views do módulo Gestão de Marketing.
"""
from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q

from django.db.models import Sum
from .models_marketing import (
    CampanhaMarketing,
    EstadoCampanha,
    PublicacaoRedesSociais,
    EstadoPublicacao,
    InvestimentoPublicidade,
)


@login_required
def marketing_main(request):
    """Página principal do módulo Gestão de Marketing."""
    hoje = timezone.now().date()
    try:
        data_inicio_str = request.GET.get('data_inicio')
        data_fim_str = request.GET.get('data_fim')
        if data_inicio_str:
            data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
        else:
            data_inicio = hoje - timedelta(days=365)
        if data_fim_str:
            data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
        else:
            data_fim = hoje
    except (ValueError, TypeError):
        data_inicio = hoje - timedelta(days=365)
        data_fim = hoje

    total_campanhas = CampanhaMarketing.objects.filter(ativo=True).count()
    campanhas_ativas = CampanhaMarketing.objects.filter(
        ativo=True,
        estado=EstadoCampanha.EM_CURSO
    ).count()
    # Ações no período = campanhas com data_inicio no intervalo
    total_acoes = CampanhaMarketing.objects.filter(
        ativo=True,
        data_inicio__gte=data_inicio,
        data_inicio__lte=data_fim
    ).count()

    context = {
        'title': 'Gestão de Marketing',
        'data_inicio': data_inicio.isoformat(),
        'data_fim': data_fim.isoformat(),
        'total_campanhas': total_campanhas,
        'campanhas_ativas': campanhas_ativas,
        'total_acoes': total_acoes,
    }
    return render(request, 'marketing/main.html', context)


@login_required
def campanha_list(request):
    """Lista de campanhas de marketing."""
    search = request.GET.get('q', '').strip()
    estado_filter = request.GET.get('estado', '').strip()
    campanhas = CampanhaMarketing.objects.filter(ativo=True).select_related('responsavel').order_by('-data_criacao')

    if search:
        campanhas = campanhas.filter(
            Q(nome__icontains=search) | Q(descricao__icontains=search) | Q(canal__icontains=search)
        )
    if estado_filter:
        campanhas = campanhas.filter(estado=estado_filter)

    context = {
        'title': 'Campanhas de Marketing',
        'campanhas': campanhas,
        'estado_choices': EstadoCampanha.choices,
        'search': search,
        'estado_filter': estado_filter,
    }
    return render(request, 'marketing/campanhas/list.html', context)


@login_required
def campanha_add(request):
    """Adicionar nova campanha."""
    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        descricao = request.POST.get('descricao', '').strip()
        estado = request.POST.get('estado', EstadoCampanha.RASCUNHO)
        data_inicio_str = request.POST.get('data_inicio', '').strip()
        data_fim_str = request.POST.get('data_fim', '').strip()
        orcamento_str = request.POST.get('orcamento', '0').strip().replace(',', '.')
        canal = request.POST.get('canal', '').strip()
        responsavel_id = request.POST.get('responsavel', '').strip() or None
        observacoes = request.POST.get('observacoes', '').strip()

        if not nome:
            messages.error(request, 'Nome da campanha é obrigatório.')
            return redirect('marketing:campanha_add')

        data_inicio = None
        if data_inicio_str:
            try:
                data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        data_fim = None
        if data_fim_str:
            try:
                data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        orcamento = Decimal('0.00')
        if orcamento_str:
            try:
                orcamento = Decimal(orcamento_str)
            except Exception:
                pass

        campanha = CampanhaMarketing.objects.create(
            nome=nome,
            descricao=descricao,
            estado=estado,
            data_inicio=data_inicio,
            data_fim=data_fim,
            orcamento=orcamento or None,
            canal=canal or '',
            responsavel_id=int(responsavel_id) if responsavel_id else None,
            observacoes=observacoes,
            ativo=True,
        )
        messages.success(request, f'Campanha "{campanha.nome}" criada com sucesso.')
        return redirect('marketing:campanha_list')

    from django.contrib.auth import get_user_model
    User = get_user_model()
    usuarios = User.objects.filter(is_active=True).order_by('first_name', 'username')

    context = {
        'title': 'Nova Campanha',
        'estado_choices': EstadoCampanha.choices,
        'usuarios': usuarios,
    }
    return render(request, 'marketing/campanhas/form.html', context)


@login_required
def campanha_edit(request, pk):
    """Editar campanha existente."""
    campanha = get_object_or_404(CampanhaMarketing, pk=pk, ativo=True)

    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        descricao = request.POST.get('descricao', '').strip()
        estado = request.POST.get('estado', EstadoCampanha.RASCUNHO)
        data_inicio_str = request.POST.get('data_inicio', '').strip()
        data_fim_str = request.POST.get('data_fim', '').strip()
        orcamento_str = request.POST.get('orcamento', '0').strip().replace(',', '.')
        canal = request.POST.get('canal', '').strip()
        responsavel_id = request.POST.get('responsavel', '').strip() or None
        observacoes = request.POST.get('observacoes', '').strip()

        if not nome:
            messages.error(request, 'Nome da campanha é obrigatório.')
            return redirect('marketing:campanha_edit', pk=pk)

        data_inicio = None
        if data_inicio_str:
            try:
                data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        data_fim = None
        if data_fim_str:
            try:
                data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        orcamento = Decimal('0.00')
        if orcamento_str:
            try:
                orcamento = Decimal(orcamento_str)
            except Exception:
                pass

        campanha.nome = nome
        campanha.descricao = descricao
        campanha.estado = estado
        campanha.data_inicio = data_inicio
        campanha.data_fim = data_fim
        campanha.orcamento = orcamento or None
        campanha.canal = canal or ''
        campanha.responsavel_id = int(responsavel_id) if responsavel_id else None
        campanha.observacoes = observacoes
        campanha.save()

        messages.success(request, f'Campanha "{campanha.nome}" atualizada com sucesso.')
        return redirect('marketing:campanha_list')

    from django.contrib.auth import get_user_model
    User = get_user_model()
    usuarios = User.objects.filter(is_active=True).order_by('first_name', 'username')

    context = {
        'title': 'Editar Campanha',
        'campanha': campanha,
        'estado_choices': EstadoCampanha.choices,
        'usuarios': usuarios,
    }
    return render(request, 'marketing/campanhas/form.html', context)


@login_required
def campanha_detail(request, pk):
    """Detalhe de uma campanha."""
    campanha = get_object_or_404(CampanhaMarketing, pk=pk, ativo=True)
    context = {
        'title': campanha.nome,
        'campanha': campanha,
    }
    return render(request, 'marketing/campanhas/detail.html', context)


# =============================================================================
# REDES SOCIAIS
# =============================================================================

@login_required
def redes_sociais_list(request):
    """Lista de publicações em redes sociais."""
    search = request.GET.get('q', '').strip()
    canal_filter = request.GET.get('canal', '').strip()
    estado_filter = request.GET.get('estado', '').strip()
    publicacoes = PublicacaoRedesSociais.objects.filter(ativo=True).select_related(
        'campanha', 'responsavel'
    ).order_by('-data_agendada', '-data_criacao')

    if search:
        publicacoes = publicacoes.filter(
            Q(texto__icontains=search) | Q(canal__icontains=search)
        )
    if canal_filter:
        publicacoes = publicacoes.filter(canal__icontains=canal_filter)
    if estado_filter:
        publicacoes = publicacoes.filter(estado=estado_filter)

    context = {
        'title': 'Redes Sociais',
        'publicacoes': publicacoes,
        'estado_choices': EstadoPublicacao.choices,
        'search': search,
        'canal_filter': canal_filter,
        'estado_filter': estado_filter,
    }
    return render(request, 'marketing/redes_sociais/list.html', context)


def _parse_publicacao_form(request):
    """Extrai dados do POST para publicacao."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    campanha_id = request.POST.get('campanha', '').strip() or None
    canal = request.POST.get('canal', '').strip()
    texto = request.POST.get('texto', '').strip()
    imagem_url = request.POST.get('imagem_url', '').strip()
    data_agendada_str = request.POST.get('data_agendada', '').strip()
    estado = request.POST.get('estado', EstadoPublicacao.RASCUNHO)
    link_post = request.POST.get('link_post', '').strip()
    responsavel_id = request.POST.get('responsavel', '').strip() or None
    observacoes = request.POST.get('observacoes', '').strip()

    data_agendada = None
    if data_agendada_str:
        try:
            data_agendada = datetime.strptime(data_agendada_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            try:
                data_agendada = datetime.strptime(data_agendada_str, '%Y-%m-%d %H:%M')
            except ValueError:
                try:
                    data_agendada = datetime.strptime(data_agendada_str, '%Y-%m-%d')
                except ValueError:
                    pass

    usuarios = User.objects.filter(is_active=True).order_by('first_name', 'username')
    campanhas = CampanhaMarketing.objects.filter(ativo=True).order_by('nome')

    return {
        'campanha_id': int(campanha_id) if campanha_id else None,
        'canal': canal,
        'texto': texto,
        'imagem_url': imagem_url,
        'data_agendada': data_agendada,
        'estado': estado,
        'link_post': link_post,
        'responsavel_id': int(responsavel_id) if responsavel_id else None,
        'observacoes': observacoes,
        'usuarios': usuarios,
        'campanhas': campanhas,
    }


@login_required
def redes_sociais_add(request):
    """Adicionar publicação."""
    if request.method == 'POST':
        d = _parse_publicacao_form(request)
        if not d['canal'] or not d['texto']:
            messages.error(request, 'Canal e texto são obrigatórios.')
            context = {
                'title': 'Nova Publicação',
                'estado_choices': EstadoPublicacao.choices,
                'usuarios': d['usuarios'],
                'campanhas': d['campanhas'],
            }
            return render(request, 'marketing/redes_sociais/form.html', context)

        pub = PublicacaoRedesSociais.objects.create(
            campanha_id=d['campanha_id'],
            canal=d['canal'],
            texto=d['texto'],
            imagem_url=d['imagem_url'] or '',
            data_agendada=d['data_agendada'],
            estado=d['estado'],
            link_post=d['link_post'] or '',
            responsavel_id=d['responsavel_id'],
            observacoes=d['observacoes'],
            ativo=True,
        )
        messages.success(request, 'Publicação criada com sucesso.')
        return redirect('marketing:redes_sociais_list')

    from django.contrib.auth import get_user_model
    User = get_user_model()
    context = {
        'title': 'Nova Publicação',
        'estado_choices': EstadoPublicacao.choices,
        'usuarios': User.objects.filter(is_active=True).order_by('first_name', 'username'),
        'campanhas': CampanhaMarketing.objects.filter(ativo=True).order_by('nome'),
    }
    return render(request, 'marketing/redes_sociais/form.html', context)


@login_required
def redes_sociais_edit(request, pk):
    """Editar publicação."""
    pub = get_object_or_404(PublicacaoRedesSociais, pk=pk, ativo=True)
    if request.method == 'POST':
        d = _parse_publicacao_form(request)
        if not d['canal'] or not d['texto']:
            messages.error(request, 'Canal e texto são obrigatórios.')
            context = {
                'title': 'Editar Publicação',
                'publicacao': pub,
                'estado_choices': EstadoPublicacao.choices,
                'usuarios': d['usuarios'],
                'campanhas': d['campanhas'],
            }
            return render(request, 'marketing/redes_sociais/form.html', context)

        pub.campanha_id = d['campanha_id']
        pub.canal = d['canal']
        pub.texto = d['texto']
        pub.imagem_url = d['imagem_url'] or ''
        pub.data_agendada = d['data_agendada']
        pub.estado = d['estado']
        pub.link_post = d['link_post'] or ''
        pub.responsavel_id = d['responsavel_id']
        pub.observacoes = d['observacoes']
        pub.save()
        messages.success(request, 'Publicação atualizada com sucesso.')
        return redirect('marketing:redes_sociais_list')

    from django.contrib.auth import get_user_model
    User = get_user_model()
    context = {
        'title': 'Editar Publicação',
        'publicacao': pub,
        'estado_choices': EstadoPublicacao.choices,
        'usuarios': User.objects.filter(is_active=True).order_by('first_name', 'username'),
        'campanhas': CampanhaMarketing.objects.filter(ativo=True).order_by('nome'),
    }
    return render(request, 'marketing/redes_sociais/form.html', context)


@login_required
def redes_sociais_detail(request, pk):
    """Detalhe de publicação."""
    pub = get_object_or_404(PublicacaoRedesSociais, pk=pk, ativo=True)
    context = {'title': f'{pub.canal} - {pub.texto[:40]}...', 'publicacao': pub}
    return render(request, 'marketing/redes_sociais/detail.html', context)


# =============================================================================
# PUBLICIDADE
# =============================================================================

@login_required
def publicidade_list(request):
    """Lista de investimentos em publicidade."""
    search = request.GET.get('q', '').strip()
    canal_filter = request.GET.get('canal', '').strip()
    investimentos = InvestimentoPublicidade.objects.filter(ativo=True).select_related(
        'campanha'
    ).order_by('-data_investimento', '-data_criacao')

    if search:
        investimentos = investimentos.filter(
            Q(canal__icontains=search) | Q(descricao__icontains=search)
        )
    if canal_filter:
        investimentos = investimentos.filter(canal__icontains=canal_filter)

    total_investido = investimentos.aggregate(s=Sum('valor'))['s'] or Decimal('0.00')

    context = {
        'title': 'Publicidade',
        'investimentos': investimentos,
        'total_investido': total_investido,
        'search': search,
        'canal_filter': canal_filter,
    }
    return render(request, 'marketing/publicidade/list.html', context)


@login_required
def publicidade_add(request):
    """Adicionar investimento em publicidade."""
    if request.method == 'POST':
        campanha_id = request.POST.get('campanha', '').strip() or None
        canal = request.POST.get('canal', '').strip()
        descricao = request.POST.get('descricao', '').strip()
        valor_str = request.POST.get('valor', '0').strip().replace(',', '.')
        data_str = request.POST.get('data_investimento', '').strip()
        observacoes = request.POST.get('observacoes', '').strip()

        if not canal or not valor_str:
            messages.error(request, 'Canal e valor são obrigatórios.')
            return redirect('marketing:publicidade_add')

        try:
            valor = Decimal(valor_str)
        except Exception:
            valor = Decimal('0.00')
        data_inv = None
        if data_str:
            try:
                data_inv = datetime.strptime(data_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        if not data_inv:
            data_inv = timezone.now().date()

        InvestimentoPublicidade.objects.create(
            campanha_id=int(campanha_id) if campanha_id else None,
            canal=canal,
            descricao=descricao,
            valor=valor,
            data_investimento=data_inv,
            observacoes=observacoes,
            ativo=True,
        )
        messages.success(request, 'Investimento registado com sucesso.')
        return redirect('marketing:publicidade_list')

    context = {
        'title': 'Novo Investimento',
        'campanhas': CampanhaMarketing.objects.filter(ativo=True).order_by('nome'),
    }
    return render(request, 'marketing/publicidade/form.html', context)


@login_required
def publicidade_edit(request, pk):
    """Editar investimento."""
    inv = get_object_or_404(InvestimentoPublicidade, pk=pk, ativo=True)
    if request.method == 'POST':
        campanha_id = request.POST.get('campanha', '').strip() or None
        canal = request.POST.get('canal', '').strip()
        descricao = request.POST.get('descricao', '').strip()
        valor_str = request.POST.get('valor', '0').strip().replace(',', '.')
        data_str = request.POST.get('data_investimento', '').strip()
        observacoes = request.POST.get('observacoes', '').strip()

        if not canal or not valor_str:
            messages.error(request, 'Canal e valor são obrigatórios.')
            return redirect('marketing:publicidade_edit', pk=pk)

        try:
            valor = Decimal(valor_str)
        except Exception:
            valor = inv.valor
        data_inv = inv.data_investimento
        if data_str:
            try:
                data_inv = datetime.strptime(data_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        inv.campanha_id = int(campanha_id) if campanha_id else None
        inv.canal = canal
        inv.descricao = descricao
        inv.valor = valor
        inv.data_investimento = data_inv
        inv.observacoes = observacoes
        inv.save()
        messages.success(request, 'Investimento atualizado com sucesso.')
        return redirect('marketing:publicidade_list')

    context = {
        'title': 'Editar Investimento',
        'investimento': inv,
        'campanhas': CampanhaMarketing.objects.filter(ativo=True).order_by('nome'),
    }
    return render(request, 'marketing/publicidade/form.html', context)


# =============================================================================
# ANÁLISE E MÉTRICAS
# =============================================================================

@login_required
def analise_metricas(request):
    """Dashboard de análise e métricas de marketing."""
    hoje = timezone.now().date()
    try:
        data_inicio_str = request.GET.get('data_inicio')
        data_fim_str = request.GET.get('data_fim')
        if data_inicio_str:
            data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
        else:
            data_inicio = hoje - timedelta(days=90)
        if data_fim_str:
            data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
        else:
            data_fim = hoje
    except (ValueError, TypeError):
        data_inicio = hoje - timedelta(days=90)
        data_fim = hoje

    total_campanhas = CampanhaMarketing.objects.filter(ativo=True).count()
    campanhas_ativas = CampanhaMarketing.objects.filter(
        ativo=True, estado=EstadoCampanha.EM_CURSO
    ).count()
    total_publicacoes = PublicacaoRedesSociais.objects.filter(ativo=True).count()
    publicacoes_periodo = PublicacaoRedesSociais.objects.filter(
        ativo=True,
        data_criacao__date__gte=data_inicio,
        data_criacao__date__lte=data_fim,
    ).count()
    total_investido = InvestimentoPublicidade.objects.filter(ativo=True).aggregate(
        s=Sum('valor')
    )['s'] or Decimal('0.00')
    investido_periodo = InvestimentoPublicidade.objects.filter(
        ativo=True,
        data_investimento__gte=data_inicio,
        data_investimento__lte=data_fim,
    ).aggregate(s=Sum('valor'))['s'] or Decimal('0.00')

    campanhas_por_estado = []
    for cod, nome in EstadoCampanha.choices:
        cnt = CampanhaMarketing.objects.filter(ativo=True, estado=cod).count()
        campanhas_por_estado.append({'cod': cod, 'nome': nome, 'count': cnt})

    context = {
        'title': 'Análise e Métricas',
        'data_inicio': data_inicio.isoformat(),
        'data_fim': data_fim.isoformat(),
        'total_campanhas': total_campanhas,
        'campanhas_ativas': campanhas_ativas,
        'total_publicacoes': total_publicacoes,
        'publicacoes_periodo': publicacoes_periodo,
        'total_investido': total_investido,
        'investido_periodo': investido_periodo,
        'campanhas_por_estado': campanhas_por_estado,
    }
    return render(request, 'marketing/analise_metricas/dashboard.html', context)
