"""Views do módulo de férias."""
from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from meuprojeto.empresa.models_rh import Funcionario, SolicitacaoFerias
from meuprojeto.empresa.services.rh_ferias_service import (
    aprovar_solicitacao_ferias,
    cancelar_solicitacao_ferias,
    criar_solicitacao_ferias,
    obter_stats_ferias,
    rejeitar_solicitacao_ferias,
)


@login_required
def rh_ferias(request):
    status_filter = request.GET.get('status', '')
    qs = (
        SolicitacaoFerias.objects
        .select_related('funcionario__departamento', 'solicitado_por', 'aprovado_por')
        .order_by('-criado_em')
    )
    if status_filter:
        qs = qs.filter(status=status_filter)
    return render(request, 'rh/ferias/main.html', {
        'solicitacoes': qs[:100],
        'status_filter': status_filter,
        'status_choices': SolicitacaoFerias.STATUS_CHOICES,
        'stats': obter_stats_ferias(),
    })


@login_required
def rh_ferias_solicitar(request):
    if request.method == 'POST':
        funcionario_id = request.POST.get('funcionario_id')
        data_inicio = request.POST.get('data_inicio')
        data_fim = request.POST.get('data_fim')
        motivo = request.POST.get('motivo', '').strip()
        try:
            di = datetime.strptime(data_inicio, '%Y-%m-%d').date()
            df = datetime.strptime(data_fim, '%Y-%m-%d').date()
            criar_solicitacao_ferias(funcionario_id, di, df, motivo, request.user)
            messages.success(request, 'Pedido de férias registado.')
            return redirect('rh:ferias')
        except Funcionario.DoesNotExist:
            messages.error(request, 'Funcionário não encontrado.')
        except ValueError as exc:
            messages.error(request, str(exc))
        except Exception as exc:
            messages.error(request, f'Erro: {exc}')

    return render(request, 'rh/ferias/form.html', {
        'funcionarios': Funcionario.objects.filter(status='AT').order_by('nome_completo'),
    })


@login_required
def rh_ferias_aprovar(request, solicitacao_id):
    solicitacao = get_object_or_404(SolicitacaoFerias, id=solicitacao_id, status='PENDENTE')
    if request.method == 'POST':
        acao = request.POST.get('acao')
        observacao = request.POST.get('observacao', '')
        if acao == 'aprovar':
            ok, msg = aprovar_solicitacao_ferias(solicitacao, request.user, observacao)
        else:
            ok, msg = rejeitar_solicitacao_ferias(solicitacao, request.user, observacao)
        (messages.success if ok else messages.error)(request, msg)
        return redirect('rh:ferias')
    return render(request, 'rh/ferias/aprovar.html', {'solicitacao': solicitacao})


@login_required
def rh_ferias_cancelar(request, solicitacao_id):
    solicitacao = get_object_or_404(SolicitacaoFerias, id=solicitacao_id)
    if request.method == 'POST':
        ok, msg = cancelar_solicitacao_ferias(solicitacao, request.user)
        (messages.success if ok else messages.error)(request, msg)
    return redirect('rh:ferias')
