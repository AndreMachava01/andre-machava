"""Lógica de hierarquia organizacional e posições."""
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from meuprojeto.empresa.models_rh import (
    Funcionario,
    PosicaoHierarquica,
    SolicitacaoAlteracaoHierarquia,
)


def obter_stats_hierarquia():
    solicitacoes = SolicitacaoAlteracaoHierarquia.objects.all()
    return {
        'solicitacoes_pendentes': solicitacoes.filter(status='ABERTO').count(),
        'total_solicitacoes': solicitacoes.count(),
        'total_posicoes': PosicaoHierarquica.objects.filter(ativa=True).count(),
    }


def queryset_posicoes():
    return (
        PosicaoHierarquica.objects
        .prefetch_related('departamentos', 'cargos')
        .select_related('posicao_superior')
        .order_by('nivel', 'nome')
    )


def encontrar_chefe_para_nivel(funcionario, novo_nivel):
    """Encontra chefe sugerido conforme nível hierárquico."""
    if novo_nivel is None:
        return None
    if novo_nivel <= 0:
        return None

    nivel_chefe = novo_nivel - 1
    qs = Funcionario.objects.filter(status='AT', posicao__nivel=nivel_chefe)

    if novo_nivel >= 2 and funcionario.departamento_id:
        qs = qs.filter(
            Q(departamento_id=funcionario.departamento_id)
            | Q(posicao__departamentos=funcionario.departamento_id)
        ).distinct()

    return qs.exclude(id=funcionario.id).first()


def encontrar_posicao_para_nivel(funcionario, novo_nivel):
    if novo_nivel is None:
        return None
    qs = PosicaoHierarquica.objects.filter(ativa=True, nivel=novo_nivel)
    if funcionario.departamento_id:
        qs = qs.filter(departamentos=funcionario.departamento_id)
    return qs.first()


@transaction.atomic
def criar_solicitacao_hierarquia(funcionario_id, novo_nivel, motivo, user):
    funcionario = Funcionario.objects.select_related('departamento', 'posicao', 'chefe').get(
        id=funcionario_id, status='AT',
    )
    novo_chefe = encontrar_chefe_para_nivel(funcionario, int(novo_nivel))
    nova_posicao = encontrar_posicao_para_nivel(funcionario, int(novo_nivel))

    return SolicitacaoAlteracaoHierarquia.objects.create(
        funcionario=funcionario,
        novo_nivel=int(novo_nivel),
        novo_chefe=novo_chefe,
        novo_posicao=nova_posicao,
        motivo=motivo.strip(),
        solicitado_por=user,
    )


@transaction.atomic
def aprovar_solicitacao_hierarquia(solicitacao, user, observacao=''):
    if solicitacao.status != 'ABERTO':
        return False, 'Solicitação já processada.'

    funcionario = solicitacao.funcionario
    novo_chefe = solicitacao.novo_chefe

    if solicitacao.novo_nivel is not None and solicitacao.novo_nivel > 0 and not novo_chefe:
        novo_chefe = encontrar_chefe_para_nivel(funcionario, solicitacao.novo_nivel)

    if solicitacao.novo_posicao:
        funcionario.posicao = solicitacao.novo_posicao
    elif solicitacao.novo_nivel is not None:
        posicao = encontrar_posicao_para_nivel(funcionario, solicitacao.novo_nivel)
        if posicao:
            funcionario.posicao = posicao

    funcionario.chefe = novo_chefe if solicitacao.novo_nivel != 0 else None
    funcionario.save(update_fields=['chefe', 'posicao', 'data_atualizacao'])

    solicitacao.status = 'APROVADO'
    solicitacao.aprovado_por = user
    solicitacao.observacao_aprovacao = observacao or ''
    solicitacao.save(update_fields=['status', 'aprovado_por', 'observacao_aprovacao', 'atualizado_em'])
    return True, 'Hierarquia actualizada com sucesso.'


@transaction.atomic
def rejeitar_solicitacao_hierarquia(solicitacao, user, observacao=''):
    if solicitacao.status != 'ABERTO':
        return False, 'Solicitação já processada.'
    solicitacao.status = 'REJEITADO'
    solicitacao.aprovado_por = user
    solicitacao.observacao_aprovacao = observacao or ''
    solicitacao.save(update_fields=['status', 'aprovado_por', 'observacao_aprovacao', 'atualizado_em'])
    return True, 'Solicitação rejeitada.'


def niveis_disponiveis():
    niveis = set(PosicaoHierarquica.objects.filter(ativa=True).values_list('nivel', flat=True))
    niveis.update({0, 1, 2, 3, 4, 5})
    return sorted(niveis)
