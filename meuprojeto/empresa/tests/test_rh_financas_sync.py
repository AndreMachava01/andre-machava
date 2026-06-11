from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase


class RhFinancasSyncTests(SimpleTestCase):
    @patch('meuprojeto.empresa.models_financas.LancamentoFinanceiro')
    @patch('meuprojeto.empresa.models_financas.PendenteContaPagar')
    def test_criar_pendente_pagar_folha(self, mock_pendente, mock_lanc):
        from meuprojeto.empresa.services.rh_financas_sync import criar_ou_actualizar_pendente_pagar_folha

        mock_lanc.objects.filter.return_value.exists.return_value = False
        qs = MagicMock()
        qs.exclude.return_value.first.return_value = None
        mock_pendente.objects.filter.return_value = qs
        mock_pendente.objects.create.return_value = MagicMock(id=7)

        folha = SimpleNamespace(
            id=3,
            status='FECHADA',
            total_liquido=Decimal('150000.00'),
            total_bruto=Decimal('160000.00'),
            total_funcionarios=5,
            mes_referencia=SimpleNamespace(strftime=lambda fmt: '03/2026'),
            data_fechamento='2026-03-31',
        )
        result = criar_ou_actualizar_pendente_pagar_folha(folha)
        self.assertIsNotNone(result)
        mock_pendente.objects.create.assert_called_once()
        kwargs = mock_pendente.objects.create.call_args.kwargs
        self.assertEqual(kwargs['origem_tipo'], 'RH_FOLHA_SALARIAL')
        self.assertEqual(kwargs['origem_id'], 3)
        self.assertEqual(kwargs['valor'], Decimal('150000.00'))

    @patch('meuprojeto.empresa.models_financas.PendenteContaPagar')
    def test_nao_cria_pendente_folha_aberta(self, mock_pendente):
        from meuprojeto.empresa.services.rh_financas_sync import criar_ou_actualizar_pendente_pagar_folha

        folha = SimpleNamespace(id=1, status='ABERTA', total_liquido=Decimal('100'))
        self.assertIsNone(criar_ou_actualizar_pendente_pagar_folha(folha))
        mock_pendente.objects.create.assert_not_called()
