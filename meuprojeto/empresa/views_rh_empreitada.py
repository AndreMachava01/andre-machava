"""Views de empreitadas e contratos com prestadores."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from meuprojeto.empresa.models_rh import ContratoEmpreitada, PrestadorServico, TrabalhoEmpreitada
from meuprojeto.empresa.services.rh_empreitada_service import (
    aplicar_clausulas_contrato,
    atualizar_trabalho_empreitada,
    build_formulario_empreitada_json,
    confirmar_assinatura_contrato,
    contexto_editar_contrato,
    contexto_preview_contrato,
    criar_trabalhos_empreitada,
    queryset_empreitadas_lista,
    salvar_parcelas_contrato,
)


@login_required
def rh_empreitadas(request):
    status_filter = request.GET.get('status', '')
    contratos, trabalhos_sem_contrato = queryset_empreitadas_lista(status_filter)
    base_qs = TrabalhoEmpreitada.objects.all()
    context = {
        'contratos': contratos,
        'trabalhos_sem_contrato': trabalhos_sem_contrato,
        'status_filter': status_filter,
        'status_choices': TrabalhoEmpreitada.STATUS_CHOICES,
        'stats': {
            'total': base_qs.count(),
            'pendentes': base_qs.filter(status='PENDENTE').count(),
            'em_andamento': base_qs.filter(status='EM_ANDAMENTO').count(),
            'concluidos': base_qs.filter(status='CONCLUIDO').count(),
        },
    }
    return render(request, 'rh/empreitadas/main.html', context)


def _contexto_form_empreitada(trabalho=None):
    ordens, ordens_json, atividades_json = build_formulario_empreitada_json()
    return {
        'trabalho': trabalho,
        'prestadores': PrestadorServico.objects.filter(ativo=True).order_by('nome'),
        'ordens_aprovadas': ordens,
        'ordens_servicos_json': ordens_json,
        'ordens_atividades_json': atividades_json,
        'status_choices': TrabalhoEmpreitada.STATUS_CHOICES,
    }


@login_required
def rh_empreitada_add(request):
    if request.method == 'POST':
        criados = criar_trabalhos_empreitada(request.POST)
        if criados:
            messages.success(request, f'{criados} trabalho(s) por empreitada registado(s).')
            return redirect('rh:empreitadas')
        messages.error(request, 'Indique pelo menos um prestador e descrição válidos.')
    return render(request, 'rh/empreitadas/form.html', _contexto_form_empreitada())


@login_required
def rh_empreitada_edit(request, trabalho_id):
    trabalho = get_object_or_404(TrabalhoEmpreitada, id=trabalho_id)
    if request.method == 'POST':
        atualizar_trabalho_empreitada(trabalho, request.POST)
        messages.success(request, 'Trabalho actualizado com sucesso.')
        return redirect('rh:empreitada_detail', trabalho_id=trabalho.id)
    ctx = _contexto_form_empreitada(trabalho)
    return render(request, 'rh/empreitadas/form.html', ctx)


@login_required
def rh_empreitada_detail(request, trabalho_id):
    trabalho = get_object_or_404(
        TrabalhoEmpreitada.objects.select_related(
            'prestador', 'sucursal', 'servico_orcamento__ordem_servico',
            'servico_orcamento__servico', 'atividade_execucao__ordem_servico',
            'contrato_empreitada',
        ),
        id=trabalho_id,
    )
    return render(request, 'rh/empreitadas/detail.html', {'trabalho': trabalho})


@login_required
def rh_empreitada_delete(request, trabalho_id):
    trabalho = get_object_or_404(TrabalhoEmpreitada, id=trabalho_id)
    if request.method == 'POST':
        contrato = trabalho.contrato_empreitada
        trabalho.delete()
        if contrato and not contrato.trabalhos.exists():
            contrato.delete()
        messages.success(request, 'Trabalho eliminado.')
        return redirect('rh:empreitadas')
    return render(request, 'rh/empreitadas/delete.html', {'trabalho': trabalho})


@login_required
def rh_editar_contrato_empreitada(request, contrato_id):
    contrato = get_object_or_404(
        ContratoEmpreitada.objects.select_related('prestador', 'ordem_servico'),
        id=contrato_id,
    )
    trabalho_id = request.GET.get('trabalho')
    trabalho = None
    if trabalho_id:
        trabalho = contrato.trabalhos.filter(id=trabalho_id).first()

    if request.method == 'POST':
        if not contrato.pode_editar_clausulas:
            messages.error(request, 'Cláusulas bloqueadas: há trabalhos iniciados ou concluídos.')
            return redirect('rh:editar_contrato_empreitada', contrato_id=contrato.id)
        aplicar_clausulas_contrato(contrato, request.POST)
        salvar_parcelas_contrato(contrato, request.POST)
        messages.success(request, 'Cláusulas guardadas.')
        if request.POST.get('acao') == 'preview':
            return redirect('rh:preview_contrato_empreitada', contrato_id=contrato.id)
        return redirect('rh:editar_contrato_empreitada', contrato_id=contrato.id)

    ctx = contexto_editar_contrato(contrato, trabalho)
    return render(request, 'rh/empreitadas/editar_contrato.html', ctx)


@login_required
def rh_preview_contrato_empreitada(request, contrato_id):
    contrato = get_object_or_404(ContratoEmpreitada, id=contrato_id)
    ctx = contexto_preview_contrato(contrato, request)
    return render(request, 'rh/empreitadas/contrato_template.html', ctx)


@login_required
def rh_confirmar_assinatura_contrato_empreitada(request, contrato_id):
    contrato = get_object_or_404(ContratoEmpreitada, id=contrato_id)
    if confirmar_assinatura_contrato(contrato):
        messages.success(request, 'Assinatura confirmada. Conta a pagar criada para Finanças, se aplicável.')
    else:
        messages.info(request, 'Contrato já estava assinado.')
    return redirect('rh:editar_contrato_empreitada', contrato_id=contrato.id)
