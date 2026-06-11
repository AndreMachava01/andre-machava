"""Views de hierarquia e posições hierárquicas."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from meuprojeto.empresa.forms_rh_hierarquia import PosicaoHierarquicaForm
from meuprojeto.empresa.models_rh import Funcionario, SolicitacaoAlteracaoHierarquia
from meuprojeto.empresa.services.rh_hierarquia_service import (
    aprovar_solicitacao_hierarquia,
    criar_solicitacao_hierarquia,
    niveis_disponiveis,
    obter_stats_hierarquia,
    queryset_posicoes,
    rejeitar_solicitacao_hierarquia,
)


@login_required
def rh_hierarquia_main(request):
    context = {
        'posicoes': queryset_posicoes(),
        **obter_stats_hierarquia(),
    }
    return render(request, 'rh/hierarquia/main.html', context)


@login_required
def rh_posicoes(request):
    return render(request, 'rh/posicoes/main.html', {
        'posicoes': queryset_posicoes(),
        **obter_stats_hierarquia(),
    })


@login_required
def rh_posicao_add(request):
    form = PosicaoHierarquicaForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Posição hierárquica criada.')
        return redirect('rh:hierarquia_main')
    return render(request, 'rh/posicoes/form.html', {'form': form})


@login_required
def rh_posicao_edit(request, posicao_id):
    posicao = get_object_or_404(queryset_posicoes(), id=posicao_id)
    form = PosicaoHierarquicaForm(request.POST or None, instance=posicao)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Posição actualizada.')
        return redirect('rh:hierarquia_main')
    return render(request, 'rh/posicoes/form.html', {'form': form, 'posicao': posicao})


@login_required
def rh_posicao_delete(request, posicao_id):
    posicao = get_object_or_404(queryset_posicoes(), id=posicao_id)
    if request.method == 'POST':
        if posicao.funcionarios.exists():
            messages.error(request, 'Não é possível eliminar: existem funcionários nesta posição.')
        else:
            posicao.delete()
            messages.success(request, 'Posição eliminada.')
            return redirect('rh:hierarquia_main')
    return render(request, 'rh/posicoes/delete.html', {'posicao': posicao})


@login_required
def rh_hierarquia_solicitar(request):
    if request.method == 'POST':
        funcionario_id = request.POST.get('funcionario_id')
        novo_nivel = request.POST.get('novo_nivel')
        motivo = request.POST.get('motivo', '').strip()
        if not all([funcionario_id, novo_nivel, motivo]):
            messages.error(request, 'Funcionário, nível e motivo são obrigatórios.')
        else:
            try:
                criar_solicitacao_hierarquia(funcionario_id, novo_nivel, motivo, request.user)
                messages.success(request, 'Solicitação enviada para aprovação.')
                return redirect('rh:hierarquia_main')
            except Funcionario.DoesNotExist:
                messages.error(request, 'Funcionário não encontrado.')
            except Exception as exc:
                messages.error(request, f'Erro ao criar solicitação: {exc}')

    funcionarios = (
        Funcionario.objects.filter(status='AT')
        .select_related('departamento', 'chefe', 'posicao')
        .order_by('nome_completo')
    )
    return render(request, 'rh/hierarquia/solicitar.html', {
        'funcionarios': funcionarios,
        'niveis_disponiveis': niveis_disponiveis(),
        'posicoes': queryset_posicoes(),
    })


@login_required
def rh_hierarquia_aprovar(request):
    if request.method == 'POST':
        solicitacao_id = request.POST.get('solicitacao_id')
        acao = request.POST.get('acao')
        observacao = request.POST.get('observacao', '')
        solicitacao = get_object_or_404(
            SolicitacaoAlteracaoHierarquia.objects.select_related(
                'funcionario', 'novo_chefe', 'novo_posicao', 'solicitado_por',
            ),
            id=solicitacao_id,
            status='ABERTO',
        )
        if acao == 'aprovar':
            ok, msg = aprovar_solicitacao_hierarquia(solicitacao, request.user, observacao)
        else:
            ok, msg = rejeitar_solicitacao_hierarquia(solicitacao, request.user, observacao)
        (messages.success if ok else messages.error)(request, msg)
        return redirect('rh:hierarquia_aprovar')

    solicitacoes = (
        SolicitacaoAlteracaoHierarquia.objects.filter(status='ABERTO')
        .select_related(
            'funcionario__departamento',
            'novo_chefe__departamento',
            'novo_chefe__posicao',
            'novo_posicao',
            'solicitado_por',
        )
        .order_by('-criado_em')
    )
    return render(request, 'rh/hierarquia/aprovar.html', {'solicitacoes': solicitacoes})


@login_required
def rh_hierarquia_historico(request):
    solicitacoes = (
        SolicitacaoAlteracaoHierarquia.objects.exclude(status='ABERTO')
        .select_related('funcionario', 'novo_chefe', 'aprovado_por', 'solicitado_por')
        .order_by('-atualizado_em')[:100]
    )
    return render(request, 'rh/hierarquia/historico.html', {
        'historico': solicitacoes,
        'total_solicitacoes': SolicitacaoAlteracaoHierarquia.objects.count(),
    })
