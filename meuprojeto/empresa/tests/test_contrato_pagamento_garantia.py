from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from meuprojeto.empresa.models_base import FormaPagamento, PeriodoPagamento
from meuprojeto.empresa.models_stock import ClienteServico, OrdemServico


class ContratoPagamentoGarantiaViewTests(TestCase):
    def setUp(self) -> None:
        self.client = Client()
        User = get_user_model()
        self.user = User.objects.create_user(
            username="tester", email="tester@example.com", password="123456"
        )

        self.client.force_login(self.user)

        # Cliente simples
        self.cliente = ClienteServico.objects.create(
            nome="Cliente Teste", telefone="840000000"
        )

        # Forma de pagamento com períodos nomeados
        self.forma_pagamento = FormaPagamento.objects.create(
            nome="Plano Teste", descricao="Plano parcelado de teste", padrao=False
        )

        PeriodoPagamento.objects.create(
            forma_pagamento=self.forma_pagamento,
            nome="Entrada",
            percentual=Decimal("50.00"),
            dias_apos_evento=0,
            evento_referencia="ASSINATURA",
            ordem=1,
        )
        PeriodoPagamento.objects.create(
            forma_pagamento=self.forma_pagamento,
            nome="Saldo",
            percentual=Decimal("50.00"),
            dias_apos_evento=30,
            evento_referencia="CONCLUSAO",
            ordem=2,
        )

        # Cotação / orçamento mínimo para o teste
        self.orcamento = OrdemServico.objects.create(
            cliente=self.cliente,
            data_agendada="2026-01-01T08:00:00Z",
            endereco_servico="Maputo",
            cidade_servico="Maputo",
            quantidade=Decimal("1.00"),
            valor_unitario=Decimal("1000.00"),
            desconto=Decimal("0.00"),
            validade_garantia_dias=120,
            forma_pagamento_configurada=self.forma_pagamento,
        )

    def test_preview_contrato_expoe_garantia_e_condicoes_pagamento(self):
        url = reverse("producao:preview_contrato_servico", args=[self.orcamento.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

        # Garantia deve respeitar o campo validade_garantia_dias
        self.assertIn("120", response.content.decode("utf-8"))

        # Condições de pagamento devem vir de FormaPagamento.get_texto_condicoes()
        texto_condicoes = self.forma_pagamento.get_texto_condicoes()
        self.assertIn(texto_condicoes, response.content.decode("utf-8"))

