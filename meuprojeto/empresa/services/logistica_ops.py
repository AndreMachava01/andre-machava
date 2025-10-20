from django.utils import timezone
import logging


logger = logging.getLogger(__name__)


def _ensure_tracking(models, notificacao, user):
    """Ensure RastreamentoEntrega exists and is synced; return rastreamento."""
    RastreamentoEntrega = models['RastreamentoEntrega']
    EventoRastreamento = models['EventoRastreamento']
    get_or_create_rastreamento_for_notificacao = models['get_or_create']
    sync = models['sync']

    rastreamento = get_or_create_rastreamento_for_notificacao(
        RastreamentoEntrega,
        EventoRastreamento,
        notificacao,
        user,
    )
    sync(EventoRastreamento, notificacao, rastreamento, user)
    return rastreamento


def confirmar_coleta(models, notificacao, user, observacoes=''):
    """Domain rule to confirm pickup and emit tracking events."""
    if notificacao.status != 'ATRIBUIDA':
        raise ValueError('Operação não pode ser coletada no status atual.')

    notificacao.status = 'COLETADA'
    notificacao.data_coleta = timezone.now()
    notificacao.observacoes_coleta = observacoes or notificacao.observacoes_coleta
    notificacao.save()

    rastreamento = _ensure_tracking(models, notificacao, user)
    return rastreamento


def iniciar_transporte(models, notificacao, user, observacoes=''):
    """Domain rule to start transportation and emit tracking events."""
    if notificacao.status != 'COLETADA':
        raise ValueError('Operação não pode iniciar transporte no status atual.')

    notificacao.status = 'EM_TRANSITO'
    notificacao.data_inicio_transporte = timezone.now()
    try:
        notificacao.observacoes_transporte = observacoes or getattr(notificacao, 'observacoes_transporte', '')
    except Exception:
        pass
    notificacao.save()

    rastreamento = _ensure_tracking(models, notificacao, user)
    return rastreamento


def confirmar_entrega(models, notificacao, user, observacoes=''):
    """Domain rule to confirm delivery and emit tracking events."""
    if notificacao.status != 'EM_TRANSITO':
        raise ValueError('Operação não pode ser entregue no status atual.')

    notificacao.status = 'ENTREGUE'
    notificacao.data_entrega = timezone.now()
    try:
        notificacao.observacoes_entrega = observacoes or getattr(notificacao, 'observacoes_entrega', '')
    except Exception:
        pass
    notificacao.save()

    rastreamento = _ensure_tracking(models, notificacao, user)
    return rastreamento


def concluir_operacao(models, notificacao, user, observacoes=''):
    """Domain rule to conclude operation after delivery; optional note."""
    if notificacao.status != 'ENTREGUE':
        raise ValueError('Operação não pode ser concluída no status atual.')

    notificacao.status = 'CONCLUIDA'
    notificacao.data_conclusao = timezone.now()
    # manter observacoes_conclusao se existir
    try:
        notificacao.observacoes_conclusao = observacoes or getattr(notificacao, 'observacoes_conclusao', '')
    except Exception:
        pass
    notificacao.save()

    # Conclusão não muda rastreamento diretamente além do histórico já gerado
    return True


