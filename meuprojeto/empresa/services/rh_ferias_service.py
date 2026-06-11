"""Gestão de pedidos de férias."""
from datetime import date

from django.db import transaction

from meuprojeto.empresa.models_rh import Funcionario, Presenca, SolicitacaoFerias
from meuprojeto.empresa.presenca_utils import PresencaAutomatica


def obter_stats_ferias():
    qs = SolicitacaoFerias.objects.all()
    hoje = date.today()
    return {
        'total': qs.count(),
        'pendentes': qs.filter(status='PENDENTE').count(),
        'aprovadas': qs.filter(status='APROVADO').count(),
        'em_curso': qs.filter(
            status='APROVADO',
            data_inicio__lte=hoje,
            data_fim__gte=hoje,
        ).count(),
    }


def verificar_conflitos_ferias(funcionario_id, data_inicio, data_fim):
    return PresencaAutomatica.verificar_conflitos(funcionario_id, data_inicio, data_fim)


@transaction.atomic
def criar_solicitacao_ferias(funcionario_id, data_inicio, data_fim, motivo, user):
    funcionario = Funcionario.objects.get(id=funcionario_id, status='AT')
    if data_fim < data_inicio:
        raise ValueError('Data fim deve ser posterior à data início.')

    conflitos = verificar_conflitos_ferias(funcionario_id, data_inicio, data_fim)
    if conflitos.get('tem_conflitos'):
        raise ValueError(
            f'Existem {conflitos["total_conflitos"]} presença(s) registada(s) no período.',
        )

    return SolicitacaoFerias.objects.create(
        funcionario=funcionario,
        data_inicio=data_inicio,
        data_fim=data_fim,
        motivo=motivo.strip(),
        solicitado_por=user,
    )


@transaction.atomic
def aprovar_solicitacao_ferias(solicitacao, user, observacao=''):
    if solicitacao.status != 'PENDENTE':
        return False, 'Pedido já processado.'

    resultado = PresencaAutomatica.marcar_ferias(
        funcionario_id=solicitacao.funcionario_id,
        data_inicio=solicitacao.data_inicio,
        data_fim=solicitacao.data_fim,
        observacoes=solicitacao.motivo,
    )
    if not resultado.get('success'):
        return False, resultado.get('error', 'Erro ao marcar férias no calendário.')

    solicitacao.status = 'APROVADO'
    solicitacao.aprovado_por = user
    solicitacao.observacao_aprovacao = observacao or ''
    solicitacao.save(update_fields=['status', 'aprovado_por', 'observacao_aprovacao', 'atualizado_em'])
    return True, f'Férias aprovadas ({resultado.get("sucessos", 0)} dia(s) marcados).'


@transaction.atomic
def rejeitar_solicitacao_ferias(solicitacao, user, observacao=''):
    if solicitacao.status != 'PENDENTE':
        return False, 'Pedido já processado.'
    solicitacao.status = 'REJEITADO'
    solicitacao.aprovado_por = user
    solicitacao.observacao_aprovacao = observacao or ''
    solicitacao.save(update_fields=['status', 'aprovado_por', 'observacao_aprovacao', 'atualizado_em'])
    return True, 'Pedido de férias rejeitado.'


@transaction.atomic
def cancelar_solicitacao_ferias(solicitacao, user):
    if solicitacao.status == 'APROVADO':
        PresencaAutomatica.cancelar_ferias(
            solicitacao.funcionario_id,
            solicitacao.data_inicio,
            solicitacao.data_fim,
        )
    solicitacao.status = 'CANCELADO'
    solicitacao.aprovado_por = user
    solicitacao.save(update_fields=['status', 'aprovado_por', 'atualizado_em'])
    return True, 'Pedido cancelado.'
