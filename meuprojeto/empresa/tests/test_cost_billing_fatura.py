import unittest
from decimal import Decimal
from types import SimpleNamespace

from meuprojeto.empresa.services.cost_billing_service import (
    chave_documento_origem,
    cliente_dados_de_rastreamento,
    rotulo_documento_origem,
)


class FaturaDocumentoOrigemTests(unittest.TestCase):
    def _sucursal(self):
        return SimpleNamespace(
            nome='Sede - Conception',
            codigo='001CON(SUCURSAL)001',
            email='info@conception.mz',
            endereco='Av. Principal',
            bairro='Sommerschield',
            cidade='Maputo',
            provincia='MA',
            get_provincia_display=lambda: 'Maputo Província',
            empresa_sede=SimpleNamespace(nuit='401932089'),
        )

    def test_ordem_compra_usa_sucursal_destino(self):
        rast = SimpleNamespace(
            transferencia_id=None,
            ordem_compra_id=1,
            transferencia=None,
            ordem_compra=SimpleNamespace(
                codigo='ORDCOMP2026060038',
                sucursal_destino=self._sucursal(),
            ),
            codigo_rastreamento='RAST001',
            destinatario_nome='X',
            destinatario_telefone='',
            endereco_entrega='',
            cidade_entrega='',
            provincia_entrega='',
        )
        dados = cliente_dados_de_rastreamento(rast)
        self.assertEqual(dados['nome'], 'Sede - Conception')
        self.assertEqual(dados['documento'], 'ORDCOMP2026060038')
        self.assertEqual(dados['nuit'], '401932089')
        self.assertEqual(dados['email'], 'info@conception.mz')
        self.assertEqual(chave_documento_origem(rast), ('ORDEM_COMPRA', 1))
        self.assertIn('ORDCOMP2026060038', rotulo_documento_origem(rast))

    def test_transferencia_agrupa_por_id(self):
        rast = SimpleNamespace(
            transferencia_id=5,
            ordem_compra_id=None,
            transferencia=SimpleNamespace(
                codigo='TRF2026060001',
                sucursal_destino=self._sucursal(),
            ),
            ordem_compra=None,
            codigo_rastreamento='RAST002',
            destinatario_nome='X',
            destinatario_telefone='',
            endereco_entrega='',
            cidade_entrega='',
            provincia_entrega='',
        )
        self.assertEqual(chave_documento_origem(rast), ('TRANSFERENCIA', 5))
        self.assertIn('TRF2026060001', rotulo_documento_origem(rast))


if __name__ == '__main__':
    unittest.main()
