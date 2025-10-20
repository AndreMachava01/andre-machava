import unittest
from types import SimpleNamespace


class FakeEventosManager:
    def __init__(self, tipos=None):
        self._tipos = set(tipos or [])

    def values_list(self, *_args, **_kwargs):
        return list(self._tipos)


class FakeRastreamento:
    def __init__(self, eventos=None):
        self.eventos = SimpleNamespace(values_list=lambda *args, **kwargs: list(set(eventos or [])))
        self.saved = False

    def save(self):
        self.saved = True


class FakeEventoRastreamentoManager:
    def __init__(self):
        self.created = []

    def create(self, **kwargs):
        self.created.append(kwargs)
        return SimpleNamespace(**kwargs)


class LogisticaSyncTests(unittest.TestCase):
    def test_sincronizar_rastreamento_com_notificacao_cria_eventos_faltantes(self):
        from meuprojeto.empresa.services.logistica_sync import sincronizar_rastreamento_com_notificacao

        evento_mgr = FakeEventoRastreamentoManager()
        EventoRastreamento = SimpleNamespace(objects=evento_mgr)

        rastreamento = FakeRastreamento(eventos=['PREPARANDO'])
        notificacao = SimpleNamespace(status='EM_TRANSITO')
        user = SimpleNamespace(id=1)

        sincronizar_rastreamento_com_notificacao(EventoRastreamento, notificacao, rastreamento, user)

        created_types = {c['tipo_evento'] for c in evento_mgr.created}
        self.assertIn('COLETADO', created_types)
        self.assertIn('EM_TRANSITO', created_types)


class LogisticaOpsTests(unittest.TestCase):
    def setUp(self):
        from meuprojeto.empresa.services.logistica_sync import get_or_create_rastreamento_for_notificacao, sincronizar_rastreamento_com_notificacao
        self.models_ctx = {
            'RastreamentoEntrega': object,  # not used by our fakes in these unit tests
            'EventoRastreamento': object,   # not used by our fakes in these unit tests
            'get_or_create': lambda *args, **kwargs: FakeRastreamento(),
            'sync': lambda *args, **kwargs: None,
        }
        self.user = SimpleNamespace(id=1)

    def test_confirmar_coleta_transita_quando_atribuida(self):
        from meuprojeto.empresa.services import logistica_ops
        notificacao = SimpleNamespace(status='ATRIBUIDA', save=lambda: None)
        logistica_ops.confirmar_coleta(self.models_ctx, notificacao, self.user, 'ok')
        self.assertEqual(notificacao.status, 'COLETADA')

    def test_confirmar_coleta_rejeita_status_invalido(self):
        from meuprojeto.empresa.services import logistica_ops
        notificacao = SimpleNamespace(status='PENDENTE', save=lambda: None)
        with self.assertRaises(ValueError):
            logistica_ops.confirmar_coleta(self.models_ctx, notificacao, self.user, '')

    def test_iniciar_transporte_transita_quando_coletada(self):
        from meuprojeto.empresa.services import logistica_ops
        notificacao = SimpleNamespace(status='COLETADA', save=lambda: None)
        logistica_ops.iniciar_transporte(self.models_ctx, notificacao, self.user, '')
        self.assertEqual(notificacao.status, 'EM_TRANSITO')

    def test_confirmar_entrega_transita_quando_em_transito(self):
        from meuprojeto.empresa.services import logistica_ops
        notificacao = SimpleNamespace(status='EM_TRANSITO', save=lambda: None)
        logistica_ops.confirmar_entrega(self.models_ctx, notificacao, self.user, '')
        self.assertEqual(notificacao.status, 'ENTREGUE')

    def test_concluir_operacao_transita_quando_entregue(self):
        from meuprojeto.empresa.services import logistica_ops
        notificacao = SimpleNamespace(status='ENTREGUE', save=lambda: None)
        result = logistica_ops.concluir_operacao(self.models_ctx, notificacao, self.user, '')
        self.assertTrue(result)
        self.assertEqual(notificacao.status, 'CONCLUIDA')


if __name__ == '__main__':
    unittest.main()


