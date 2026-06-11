import unittest
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.utils import timezone

from meuprojeto.empresa.services.codigo_sequencial import gerar_codigo_ano_mes, periodo_ano_mes


class CodigoSequencialTests(unittest.TestCase):
    def test_periodo_ano_mes(self):
        dt = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.get_current_timezone())
        self.assertEqual(periodo_ano_mes(dt), '202606')

    @patch('meuprojeto.empresa.services.codigo_sequencial.timezone.now')
    def test_gerar_primeiro_codigo_do_mes(self, mock_now):
        mock_now.return_value = datetime(2026, 3, 1, tzinfo=timezone.get_current_timezone())
        qs = MagicMock()
        qs.select_for_update.return_value = qs
        qs.filter.return_value = qs
        qs.order_by.return_value = qs
        qs.values_list.return_value.first.return_value = None
        qs.filter.return_value.exists.return_value = False

        model = MagicMock()
        model.objects = qs

        codigo = gerar_codigo_ano_mes(model, 'COMP')
        self.assertEqual(codigo, 'COMP2026030001')

    @patch('meuprojeto.empresa.services.codigo_sequencial.timezone.now')
    def test_gerar_proximo_codigo_do_mes(self, mock_now):
        mock_now.return_value = datetime(2026, 3, 10, tzinfo=timezone.get_current_timezone())

        class FakeQuerySet:
            def __init__(self, manager):
                self.manager = manager

            def select_for_update(self):
                return self

            def filter(self, **kwargs):
                self.manager.last_filter = kwargs
                return self

            def order_by(self, *args):
                return self

            def values_list(self, *args, **kwargs):
                return self

            def first(self):
                if self.manager.last_filter.get('codigo__startswith'):
                    return self.manager.ultimo
                return None

            def exists(self):
                return False

        class FakeManager:
            def __init__(self):
                self.ultimo = 'COMP2026030009'
                self.last_filter = {}

            def select_for_update(self):
                return FakeQuerySet(self)

            def filter(self, **kwargs):
                qs = FakeQuerySet(self)
                qs.last_filter = kwargs
                return qs

        model = SimpleNamespace(objects=FakeManager())
        codigo = gerar_codigo_ano_mes(model, 'COMP')
        self.assertEqual(codigo, 'COMP2026030010')

    @patch('meuprojeto.empresa.services.codigo_sequencial.gerar_codigo_ano_mes')
    def test_gerar_codigo_rastreamento_entrega(self, mock_gerar):
        mock_gerar.return_value = 'RAST2026060001'
        from meuprojeto.empresa.models_stock import RastreamentoEntrega
        from meuprojeto.empresa.services.codigo_sequencial import gerar_codigo_rastreamento_entrega

        codigo = gerar_codigo_rastreamento_entrega()
        self.assertEqual(codigo, 'RAST2026060001')
        mock_gerar.assert_called_once_with(
            RastreamentoEntrega,
            'RAST',
            campo='codigo_rastreamento',
        )


if __name__ == '__main__':
    unittest.main()
