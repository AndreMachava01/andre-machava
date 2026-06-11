"""Estatísticas e helpers do módulo RH."""
from datetime import date, timedelta

from django.db import transaction
from django.db.models import Avg

from meuprojeto.empresa.models_rh import (
    AvaliacaoDesempenho,
    Cargo,
    Departamento,
    Funcionario,
    Presenca,
    Promocao,
    SolicitacaoFerias,
    TipoPresenca,
    Treinamento,
    TrabalhoEmpreitada,
    InscricaoTreinamento,
)


def obter_estatisticas_rh():
    hoje = date.today()
    return {
        'total_funcionarios': Funcionario.objects.filter(status='AT').count(),
        'total_departamentos': Departamento.objects.filter(ativo=True).count(),
        'total_cargos': Cargo.objects.filter(ativo=True).count(),
        'presencas_hoje': Presenca.objects.filter(data=hoje).count(),
        'empreitadas_pendentes': TrabalhoEmpreitada.objects.filter(status='PENDENTE').count(),
        'empreitadas_em_andamento': TrabalhoEmpreitada.objects.filter(status='EM_ANDAMENTO').count(),
        'ferias_pendentes': SolicitacaoFerias.objects.filter(status='PENDENTE').count(),
    }


def obter_stats_funcionarios_lista():
    qs = Funcionario.objects.all()
    return {
        'total_funcionarios': qs.count(),
        'funcionarios_ativos': qs.filter(status='AT').count(),
        'funcionarios_inativos': qs.filter(status='IN').count(),
        'total_departamentos': Departamento.objects.count(),
    }


def obter_stats_departamentos_lista():
    total = Departamento.objects.count()
    activos = Departamento.objects.filter(ativo=True).count()
    return {
        'total_departamentos': total,
        'departamentos_ativos': activos,
        'departamentos_inativos': total - activos,
        'total_funcionarios': Funcionario.objects.filter(status='AT').count(),
    }


def obter_stats_cargos_lista():
    qs = Cargo.objects.all()
    return {
        'total_cargos': qs.count(),
        'cargos_ativos': qs.filter(ativo=True).count(),
        'total_funcionarios': Funcionario.objects.filter(status='AT').count(),
    }


def obter_stats_treinamentos_lista():
    hoje = date.today()
    data_limite = hoje + timedelta(days=7)
    return {
        'total_treinamentos': Treinamento.objects.count(),
        'treinamentos_ativos': Treinamento.objects.filter(status='EM_ANDAMENTO').count(),
        'treinamentos_planejados': Treinamento.objects.filter(status='PLANEJADO').count(),
        'treinamentos_concluidos': Treinamento.objects.filter(status='CONCLUIDO').count(),
        'proximos_7_dias': Treinamento.objects.filter(
            data_inicio__lte=data_limite, data_inicio__gte=hoje,
        ).count(),
        'total_inscricoes': InscricaoTreinamento.objects.count(),
    }


def obter_stats_promocoes_lista():
    qs = Promocao.objects.all()
    return {
        'total': qs.count(),
        'pendentes': qs.filter(status='PENDENTE').count(),
        'aprovadas': qs.filter(status='APROVADO').count(),
        'implementadas': qs.filter(status='IMPLEMENTADO').count(),
        'rejeitadas': qs.filter(status='REJEITADO').count(),
    }


def obter_stats_avaliacoes_lista():
    qs = AvaliacaoDesempenho.objects.all()
    nota_media = qs.filter(status='CONCLUIDA', nota_geral__isnull=False).aggregate(
        media=Avg('nota_geral'),
    )['media']
    return {
        'total_avaliacoes': qs.count(),
        'planejadas': qs.filter(status='PLANEJADA').count(),
        'em_andamento': qs.filter(status='EM_ANDAMENTO').count(),
        'concluidas': qs.filter(status='CONCLUIDA').count(),
        'canceladas': qs.filter(status='CANCELADA').count(),
        'nota_media': nota_media or 0,
    }


@transaction.atomic
def marcar_presencas_automaticas(
    funcionario_id,
    data_inicio,
    data_fim,
    tipo_presenca_codigo,
    observacoes='',
):
    """Marca presenças automáticas (férias, licenças, etc.) no calendário."""
    try:
        funcionario = Funcionario.objects.get(id=funcionario_id, status='AT')
        tipo = TipoPresenca.objects.get(codigo=tipo_presenca_codigo, ativo=True)
    except Funcionario.DoesNotExist:
        return {'success': False, 'error': 'Funcionário não encontrado ou inativo'}
    except TipoPresenca.DoesNotExist:
        return {'success': False, 'error': f'Tipo de presença «{tipo_presenca_codigo}» não encontrado'}

    sucessos = 0
    erros = 0
    data_atual = data_inicio
    while data_atual <= data_fim:
        _, created = Presenca.objects.update_or_create(
            funcionario=funcionario,
            data=data_atual,
            defaults={
                'tipo_presenca': tipo,
                'observacoes': observacoes,
            },
        )
        if created:
            sucessos += 1
        else:
            sucessos += 1
        data_atual += timedelta(days=1)

    return {'success': True, 'sucessos': sucessos, 'erros': erros}


@transaction.atomic
def remover_presencas_automaticas(funcionario_id, data_inicio, data_fim, tipo_presenca_codigo):
    """Remove presenças automáticas no período indicado."""
    try:
        funcionario = Funcionario.objects.get(id=funcionario_id)
        tipo = TipoPresenca.objects.get(codigo=tipo_presenca_codigo)
    except (Funcionario.DoesNotExist, TipoPresenca.DoesNotExist) as exc:
        return {'success': False, 'error': str(exc)}

    removidos, _ = Presenca.objects.filter(
        funcionario=funcionario,
        data__range=[data_inicio, data_fim],
        tipo_presenca=tipo,
    ).delete()

    return {'success': True, 'removidos': removidos}
