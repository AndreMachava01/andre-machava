import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


class LogisticaFinancasSyncTests(unittest.TestCase):
    @patch('meuprojeto.empresa.models_financas.LancamentoFinanceiro')
    @patch('meuprojeto.empresa.models_financas.PendenteContaReceber')
    def test_criar_pendente_receber_fatura(self, mock_pendente, mock_lanc):
        from meuprojeto.empresa.services.logistica_financas_sync import (
            criar_ou_actualizar_pendente_receber_fatura,
        )

        mock_lanc.objects.filter.return_value.exists.return_value = False
        qs = MagicMock()
        qs.exclude.return_value.first.return_value = None
        mock_pendente.objects.filter.return_value = qs
        mock_pendente.objects.create.return_value = MagicMock(id=1)

        fatura = SimpleNamespace(
            id=5,
            status='ENVIADO',
            numero_fatura='LOG2026000001',
            cliente_nome='Cliente Teste',
            valor_liquido=Decimal('2250.00'),
            data_vencimento='2026-07-08',
        )
        result = criar_ou_actualizar_pendente_receber_fatura(fatura)
        self.assertIsNotNone(result)
        mock_pendente.objects.create.assert_called_once()
        kwargs = mock_pendente.objects.create.call_args.kwargs
        self.assertEqual(kwargs['origem_tipo'], 'LOGISTICA')
        self.assertEqual(kwargs['origem_id'], 5)
        self.assertEqual(kwargs['valor'], Decimal('2250.00'))

    @patch('meuprojeto.empresa.models_financas.LancamentoFinanceiro')
    @patch('meuprojeto.empresa.models_financas.PendenteContaPagar')
    def test_criar_pendente_pagar_custo(self, mock_pendente, mock_lanc):
        from meuprojeto.empresa.services.logistica_financas_sync import criar_pendente_pagar_custo

        mock_lanc.objects.filter.return_value.exists.return_value = False
        qs = MagicMock()
        qs.exclude.return_value.exists.return_value = False
        mock_pendente.objects.filter.return_value = qs
        mock_pendente.objects.create.return_value = MagicMock(id=2)

        custo = SimpleNamespace(
            id=9,
            status='APROVADO',
            codigo='CL-001',
            descricao='Combustível rota Maputo',
            valor=Decimal('500.00'),
            data_custo='2026-06-01',
            centro_custo_id=1,
            centro_custo=SimpleNamespace(nome='Transporte'),
            tipo_custo_id=1,
            tipo_custo=SimpleNamespace(nome='Combustível'),
            rastreamento_entrega_id=None,
            rastreamento_entrega=None,
        )
        result = criar_pendente_pagar_custo(custo)
        self.assertIsNotNone(result)
        kwargs = mock_pendente.objects.create.call_args.kwargs
        self.assertEqual(kwargs['origem_tipo'], 'LOGISTICA')
        self.assertEqual(kwargs['origem_id'], 9)


if __name__ == '__main__':
    unittest.main()
