from django.utils import timezone
import logging


logger = logging.getLogger(__name__)


def criar_evento_rastreamento(EventoRastreamento, rastreamento, user, tipo_evento, descricao=''):
    EventoRastreamento.objects.create(
        rastreamento=rastreamento,
        tipo_evento=tipo_evento,
        descricao=descricao or '',
        localizacao='',
        data_evento=timezone.now(),
        usuario=user,
    )


def sincronizar_rastreamento_com_notificacao(EventoRastreamento, notificacao, rastreamento, user):
    estados_para_eventos = {
        'ATRIBUIDA': ['PREPARANDO'],
        'COLETADA': ['PREPARANDO', 'COLETADO'],
        'EM_TRANSITO': ['PREPARANDO', 'COLETADO', 'EM_TRANSITO'],
        'ENTREGUE': ['PREPARANDO', 'COLETADO', 'EM_TRANSITO', 'ENTREGUE'],
        'CONCLUIDA': ['PREPARANDO', 'COLETADO', 'EM_TRANSITO', 'ENTREGUE'],
    }
    eventos_existentes = set(rastreamento.eventos.values_list('tipo_evento', flat=True))
    for tipo in estados_para_eventos.get(notificacao.status, []):
        if tipo not in eventos_existentes:
            try:
                criar_evento_rastreamento(EventoRastreamento, rastreamento, user, tipo, '')
            except Exception:
                logger.exception('Falha ao criar evento %s para rastreamento %s', tipo, getattr(rastreamento, 'id', None))


def get_or_create_rastreamento_for_notificacao(RastreamentoEntrega, EventoRastreamento, notificacao, user):
    rastreamento = None
    if getattr(notificacao, 'transferencia_id', None):
        rastreamento = RastreamentoEntrega.objects.filter(transferencia_id=notificacao.transferencia_id).first()
    if not rastreamento and getattr(notificacao, 'ordem_compra_id', None):
        rastreamento = RastreamentoEntrega.objects.filter(ordem_compra_id=notificacao.ordem_compra_id).first()

    if not rastreamento:
        if notificacao.tipo_operacao == 'TRANSFERENCIA':
            destinatario_nome = notificacao.transferencia.sucursal_destino.nome
            endereco = getattr(notificacao.transferencia.sucursal_destino, 'endereco', '') or 'Endereço a definir'
            cidade = getattr(notificacao.transferencia.sucursal_destino, 'cidade', '') or 'Cidade'
            provincia = getattr(notificacao.transferencia.sucursal_destino, 'provincia', '') or 'Província'
        else:
            destinatario_nome = notificacao.ordem_compra.sucursal_destino.nome
            endereco = getattr(notificacao.ordem_compra.sucursal_destino, 'endereco', '') or 'Endereço a definir'
            cidade = getattr(notificacao.ordem_compra.sucursal_destino, 'cidade', '') or 'Cidade'
            provincia = getattr(notificacao.ordem_compra.sucursal_destino, 'provincia', '') or 'Província'

        rastreamento = RastreamentoEntrega(
            transferencia_id=getattr(notificacao, 'transferencia_id', None),
            ordem_compra_id=getattr(notificacao, 'ordem_compra_id', None),
            veiculo_interno_id=getattr(notificacao, 'veiculo_interno_id', None),
            transportadora_id=getattr(notificacao, 'transportadora_externa_id', None),
            criado_por=user,
            destinatario_nome=destinatario_nome,
            endereco_entrega=endereco,
            cidade_entrega=cidade,
            provincia_entrega=provincia,
        )
        rastreamento.save()

    changed = False
    if getattr(notificacao, 'veiculo_interno_id', None) and rastreamento.veiculo_interno_id != notificacao.veiculo_interno_id:
        rastreamento.veiculo_interno_id = notificacao.veiculo_interno_id
        changed = True
    if getattr(notificacao, 'transportadora_externa_id', None) and rastreamento.transportadora_id != notificacao.transportadora_externa_id:
        rastreamento.transportadora_id = notificacao.transportadora_externa_id
        changed = True
    if changed:
        rastreamento.save()

    try:
        sincronizar_rastreamento_com_notificacao(EventoRastreamento, notificacao, rastreamento, user)
    except Exception:
        logger.exception('Falha ao sincronizar rastreamento com notificacao %s', getattr(notificacao, 'id', None))
    return rastreamento


