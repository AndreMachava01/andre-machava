"""Views de prestadores de serviços externos."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from meuprojeto.empresa.models_rh import PrestadorServico


@login_required
def rh_prestadores(request):
    tipo_filter = request.GET.get('tipo', '')
    qs = PrestadorServico.objects.all().order_by('nome')
    if tipo_filter:
        qs = qs.filter(tipo=tipo_filter)
    total = PrestadorServico.objects.count()
    return render(request, 'rh/prestadores/main.html', {
        'prestadores': qs,
        'tipo_filter': tipo_filter,
        'tipo_choices': PrestadorServico.TIPO_CHOICES,
        'stats': {
            'total': total,
            'activos': PrestadorServico.objects.filter(ativo=True).count(),
            'singulares': PrestadorServico.objects.filter(tipo='SINGULAR').count(),
            'empresas': PrestadorServico.objects.filter(tipo='EMPRESA').count(),
        },
    })


@login_required
def rh_prestador_add(request):
    if request.method == 'POST':
        prestador = PrestadorServico(
            tipo=request.POST.get('tipo', 'SINGULAR'),
            nome=request.POST.get('nome', '').strip(),
            representante_legal=request.POST.get('representante_legal', ''),
            contacto=request.POST.get('contacto', ''),
            email=request.POST.get('email', ''),
            nuit=request.POST.get('nuit', ''),
            endereco=request.POST.get('endereco', ''),
            observacoes=request.POST.get('observacoes', ''),
            ativo=request.POST.get('ativo') == 'on',
        )
        if not prestador.nome:
            messages.error(request, 'Nome é obrigatório.')
        else:
            prestador.save()
            messages.success(request, 'Prestador registado.')
            return redirect('rh:prestadores')
    return render(request, 'rh/prestadores/form.html', {
        'tipo_choices': PrestadorServico.TIPO_CHOICES,
    })


@login_required
def rh_prestador_detail(request, prestador_id):
    prestador = get_object_or_404(PrestadorServico, id=prestador_id)
    return render(request, 'rh/prestadores/detail.html', {'prestador': prestador})


@login_required
def rh_prestador_edit(request, prestador_id):
    prestador = get_object_or_404(PrestadorServico, id=prestador_id)
    if request.method == 'POST':
        prestador.tipo = request.POST.get('tipo', prestador.tipo)
        prestador.nome = request.POST.get('nome', '').strip()
        prestador.representante_legal = request.POST.get('representante_legal', '')
        prestador.contacto = request.POST.get('contacto', '')
        prestador.email = request.POST.get('email', '')
        prestador.nuit = request.POST.get('nuit', '')
        prestador.endereco = request.POST.get('endereco', '')
        prestador.observacoes = request.POST.get('observacoes', '')
        prestador.ativo = request.POST.get('ativo') == 'on'
        if not prestador.nome:
            messages.error(request, 'Nome é obrigatório.')
        else:
            prestador.save()
            messages.success(request, 'Prestador actualizado.')
            return redirect('rh:prestador_detail', prestador_id=prestador.id)
    return render(request, 'rh/prestadores/form.html', {
        'prestador': prestador,
        'tipo_choices': PrestadorServico.TIPO_CHOICES,
    })


@login_required
def rh_prestador_delete(request, prestador_id):
    prestador = get_object_or_404(PrestadorServico, id=prestador_id)
    if request.method == 'POST':
        prestador.delete()
        messages.success(request, 'Prestador eliminado.')
        return redirect('rh:prestadores')
    return render(request, 'rh/prestadores/delete.html', {'prestador': prestador})
