import unittest
from decimal import Decimal
from types import SimpleNamespace

from meuprojeto.empresa.services.freight_service import (
    calcular_distancia_km,
    resolver_coordenadas,
)
from meuprojeto.empresa.services.pricing import calculate_quote, calculate_freight_veiculo_interno, PricingItem


class FreightPricingTests(unittest.TestCase):
    def test_calculate_quote_inclui_distancia(self):
        transportadora = SimpleNamespace(
            custo_fixo=100,
            custo_por_kg=5,
            custo_por_km=2,
            prazo_entrega_padrao=3,
        )
        result = calculate_quote(
            transportadora=transportadora,
            items=[PricingItem(weight_kg=10, declared_value=1000)],
            distancia_km=50,
        )
        self.assertEqual(result.total_cost, 250.0)
        self.assertEqual(result.breakdown['custo_distancia'], 100.0)
        self.assertEqual(result.breakdown['custo_peso'], 50.0)

    def test_calculate_freight_veiculo_interno(self):
        veiculo = SimpleNamespace(custo_por_km=Decimal('3.50'))
        result = calculate_freight_veiculo_interno(
            veiculo=veiculo,
            distancia_km=40,
            custo_fixo_entrega=20,
        )
        self.assertEqual(result.total_cost, 160.0)
        self.assertEqual(result.breakdown['custo_distancia'], 140.0)

    def test_calcular_distancia_maputo_matola(self):
        maputo = resolver_coordenadas('Maputo', 'Maputo', 'Maputo', '')
        matola = resolver_coordenadas('Matola', 'Matola', 'Maputo', '')
        distancia = calcular_distancia_km(
            maputo.latitude, maputo.longitude,
            matola.latitude, matola.longitude,
        )
        self.assertGreater(distancia, Decimal('5'))
        self.assertLess(distancia, Decimal('20'))


    def test_resolver_coordenadas_machava_no_nome_fornecedor(self):
        ponto = resolver_coordenadas(
            '[EXTERNO] MACHAVA SERVICOS',
            '',
            '',
            'Polana Caniço B Quarteirão 20 Rua 3734 Casa 192',
        )
        self.assertEqual(ponto.fonte, 'catalogo_texto')
        self.assertEqual(ponto.latitude, Decimal('-25.976000'))
        distancia = calcular_distancia_km(
            ponto.latitude, ponto.longitude,
            Decimal('-25.969248'), Decimal('32.573924'),
        )
        self.assertLess(distancia, Decimal('20'))

    def test_resolver_coordenadas_provincia_codigo_ma(self):
        ponto = resolver_coordenadas('Sede', 'Maputo', 'MA', '')
        self.assertIn(ponto.fonte, ('catalogo_cidade', 'catalogo_provincia_codigo'))
        self.assertLess(abs(ponto.latitude - Decimal('-25.96')), Decimal('0.05'))

    def test_distancia_result_com_override(self):
        from meuprojeto.empresa.services.freight_service import distancia_result_com_override

        notificacao = SimpleNamespace(
            tipo_operacao='TRANSFERENCIA',
            transferencia=SimpleNamespace(
                sucursal_origem=SimpleNamespace(
                    nome='A', cidade='Maputo', provincia='Maputo', endereco='',
                ),
                sucursal_destino=SimpleNamespace(
                    nome='B', cidade='Matola', provincia='Maputo', endereco='',
                ),
            ),
            ordem_compra=None,
        )
        manual = distancia_result_com_override(notificacao, '42.5')
        self.assertEqual(manual.distancia_km, Decimal('42.5'))

    def test_resolver_carga_params_sem_peso_nem_dimensoes(self):
        from meuprojeto.empresa.services.freight_service import resolver_carga_params

        notificacao = SimpleNamespace(
            tipo_operacao='TRANSFERENCIA',
            transferencia=SimpleNamespace(itens=SimpleNamespace(all=lambda: [])),
            ordem_compra=None,
        )
        carga = resolver_carga_params(notificacao)
        self.assertFalse(carga.usar_peso)
        self.assertFalse(carga.usar_dimensoes)

    def test_calculate_quote_com_dimensoes_volumetricas(self):
        transportadora = SimpleNamespace(
            custo_fixo=0,
            custo_por_kg=10,
            custo_por_km=0,
            prazo_entrega_padrao=1,
        )
        result = calculate_quote(
            transportadora=transportadora,
            items=[PricingItem(weight_kg=1, length_cm=100, width_cm=100, height_cm=100)],
            distancia_km=0,
        )
        self.assertEqual(result.breakdown['peso_volumetrico_kg'], 166.667)
        self.assertEqual(result.breakdown['weight_kg'], 166.667)
        self.assertEqual(result.total_cost, 1666.67)


    def test_suplemento_percentual_volume_e_peso(self):
        from meuprojeto.empresa.services.freight_service import (
            calcular_frete_operacao,
            resolver_carga_params,
            calcular_suplemento_percentual_carga,
        )

        viatura = SimpleNamespace(
            tipo='VIATURA_INTERNA_ENTREGA',
            custo_fixo=100,
            custo_por_kg=0,
            custo_por_km=0,
            volume_m3_franquia=Decimal('1'),
            peso_kg_franquia=Decimal('25'),
            percentual_suplemento_carga=Decimal('10'),
            prazo_entrega_padrao=1,
        )
        sup_vol = calcular_suplemento_percentual_carga(viatura, 3, 10, 1000)
        self.assertTrue(sup_vol['excede_franquia_volume'])
        self.assertEqual(sup_vol['custo_suplemento_percentual'], 100.0)

        sup_peso = calcular_suplemento_percentual_carga(viatura, 0.5, 30, 1000)
        self.assertTrue(sup_peso['excede_franquia_peso'])
        self.assertEqual(sup_peso['custo_suplemento_percentual'], 100.0)

        sup_ok = calcular_suplemento_percentual_carga(viatura, 1, 20, 1000)
        self.assertFalse(sup_ok['excede_franquia_volume'])
        self.assertFalse(sup_ok['excede_franquia_peso'])
        self.assertEqual(sup_ok['custo_suplemento_percentual'], 0)

        notificacao = SimpleNamespace(valor_operacao=0, tipo_operacao='TRANSFERENCIA', transferencia=None, ordem_compra=None)
        dist = SimpleNamespace(
            distancia_km=Decimal('10'),
            origem=SimpleNamespace(label='A', provincia='Maputo'),
            destino=SimpleNamespace(label='B', provincia='Maputo'),
        )
        f3 = calcular_frete_operacao(
            notificacao, transportadora=viatura, distancia=dist,
            carga=resolver_carga_params(notificacao, volume_m3_manual='3'),
        )
        self.assertEqual(float(f3.total_cost), 110.0)

    def test_volume_m3_altera_preco_quando_tarifa_tem_custo_por_kg(self):
        from meuprojeto.empresa.services.freight_service import (
            calcular_frete_operacao,
            resolver_carga_params,
            dimensoes_cubo_from_volume_m3,
        )

        viatura = SimpleNamespace(
            tipo='VIATURA_INTERNA_ENTREGA',
            custo_fixo=100,
            custo_por_kg=2,
            custo_por_km=0,
            volume_m3_franquia=Decimal('1'),
            peso_kg_franquia=Decimal('25'),
            percentual_suplemento_carga=Decimal('0'),
            prazo_entrega_padrao=1,
        )
        notificacao = SimpleNamespace(valor_operacao=0, tipo_operacao='TRANSFERENCIA', transferencia=None, ordem_compra=None)
        dist = SimpleNamespace(
            distancia_km=Decimal('10'),
            origem=SimpleNamespace(label='A', provincia='Maputo'),
            destino=SimpleNamespace(label='B', provincia='Maputo'),
        )
        c1, _, _ = dimensoes_cubo_from_volume_m3(Decimal('1'))
        c3, _, _ = dimensoes_cubo_from_volume_m3(Decimal('3'))
        self.assertEqual(float(c1), 100.0)
        self.assertEqual(float(c3), 144.2)

        frete1 = calcular_frete_operacao(
            notificacao,
            transportadora=viatura,
            distancia=dist,
            carga=resolver_carga_params(notificacao, volume_m3_manual='1'),
        )
        frete3 = calcular_frete_operacao(
            notificacao,
            transportadora=viatura,
            distancia=dist,
            carga=resolver_carga_params(notificacao, volume_m3_manual='3'),
        )
        self.assertNotEqual(float(frete1.total_cost), float(frete3.total_cost))
        self.assertLess(float(frete1.total_cost), float(frete3.total_cost))

    def test_estimar_peso_transferencia_usa_quantidade_solicitada(self):
        from meuprojeto.empresa.services.freight_service import estimar_peso_kg, estimar_carga

        item = SimpleNamespace(quantidade_solicitada=12, quantidade_recebida=0)
        notificacao = SimpleNamespace(
            tipo_operacao='TRANSFERENCIA',
            transferencia=SimpleNamespace(itens=SimpleNamespace(all=lambda: [item])),
            ordem_compra=None,
        )
        self.assertEqual(estimar_peso_kg(notificacao), Decimal('12'))
        carga = estimar_carga(notificacao)
        self.assertEqual(carga.peso_kg, Decimal('12'))

    def test_calculate_frete_viatura_interna_usa_tarifas_transportadora(self):
        from meuprojeto.empresa.services.freight_service import calcular_frete_operacao, resolver_carga_params
        from types import SimpleNamespace

        viatura = SimpleNamespace(
            tipo='VIATURA_INTERNA_ENTREGA',
            custo_fixo=100,
            custo_por_kg=0.5,
            custo_por_km=2,
            prazo_entrega_padrao=1,
        )
        notificacao = SimpleNamespace(valor_operacao=0, tipo_operacao='TRANSFERENCIA', transferencia=None, ordem_compra=None)
        dist = SimpleNamespace(
            distancia_km=Decimal('10'),
            origem=SimpleNamespace(label='A', provincia='Maputo'),
            destino=SimpleNamespace(label='B', provincia='Maputo'),
        )
        carga = resolver_carga_params(notificacao, usar_peso=True, peso_kg_manual='20')
        result = calcular_frete_operacao(
            notificacao,
            transportadora=viatura,
            distancia=dist,
            carga=carga,
        )
        self.assertEqual(float(result.total_cost), 130.0)


if __name__ == '__main__':
    unittest.main()
