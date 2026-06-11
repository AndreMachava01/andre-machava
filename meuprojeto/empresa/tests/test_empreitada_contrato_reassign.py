"""
Testa a reassociação de trabalhos ao contrato correcto (prestador + cotação).
Quando um trabalho avulso é editado e associado a um serviço de uma cotação,
deve mover-se para o contrato dessa cotação.
"""
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model

from meuprojeto.empresa.models_rh import (
    PrestadorServico,
    TrabalhoEmpreitada,
    ContratoEmpreitada,
)
from meuprojeto.empresa.models_stock import (
    OrdemServico,
    ServicoOrcamentoServico,
    Item,
    ClienteServico,
)

User = get_user_model()


class EmpreitadaContratoReassignTest(TestCase):
    """Testa que trabalhos avulsos reassociados à cotação mudam de contrato."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='test_emp',
            password='test123',
        )
        self.prestador = PrestadorServico.objects.create(
            nome='Prestador Teste',
            tipo='SINGULAR',
            ativo=True,
        )
        self.cliente = ClienteServico.objects.create(
            nome='Cliente Teste',
            nuit='123456789',
            telefone='841234567',
            endereco='Rua Teste',
            cidade='Maputo',
        )
        self.servico_item = Item.objects.create(
            nome='Execução de projectos',
            tipo='PRODUTO',
            produto_tipo='SERVICO',
            codigo='SERV-TEST-001',
        )
        # Cotação (COT)
        self.cotacao = OrdemServico.objects.create(
            codigo='COT-2026-TEST001',
            cliente=self.cliente,
            data_agendada='2026-02-20 08:00:00',
            endereco_servico='Endereço',
            cidade_servico='Maputo',
            status='AGENDADA',
            quantidade=Decimal('1'),
            valor_total=Decimal('50000'),
            validade_garantia_dias=90,
            criado_por=self.user,
        )
        # Ordem de serviço (OS) gerada da cotação
        self.ordem_servico = OrdemServico.objects.create(
            codigo='OS-2026-000099',
            orcamento_origem=self.cotacao,
            cliente=self.cliente,
            data_agendada='2026-02-20 08:00:00',
            endereco_servico='Endereço',
            cidade_servico='Maputo',
            status='AGENDADA',
            quantidade=Decimal('1'),
            valor_total=Decimal('50000'),
            validade_garantia_dias=90,
            criado_por=self.user,
        )
        self.servico_orcamento = ServicoOrcamentoServico.objects.create(
            ordem_servico=self.ordem_servico,
            servico=self.servico_item,
            quantidade=Decimal('1'),
            valor_unitario=Decimal('50000'),
            desconto=Decimal('0'),
        )

    def test_trabalho_avulso_reassociado_muda_para_contrato_os(self):
        """Trabalho avulso ao ser associado a servico da OS deve ir para contrato da OS."""
        from meuprojeto.empresa.views import _get_or_create_contrato_empreitada

        # 1. Criar trabalho avulso (sem servico_orcamento)
        trabalho_avulso = TrabalhoEmpreitada.objects.create(
            prestador=self.prestador,
            descricao='Trabalho avulso',
            valor_fixo=Decimal('5999.40'),
            status='PENDENTE',
            servico_orcamento=None,
        )
        contrato_avulso = _get_or_create_contrato_empreitada(trabalho_avulso)
        trabalho_avulso.contrato_empreitada = contrato_avulso
        trabalho_avulso.save(update_fields=['contrato_empreitada'])

        self.assertIsNone(contrato_avulso.ordem_servico_id)
        self.assertEqual(trabalho_avulso.contrato_empreitada_id, contrato_avulso.id)

        # 2. Criar trabalho já associado à OS
        trabalho_os = TrabalhoEmpreitada.objects.create(
            prestador=self.prestador,
            descricao='Trabalho na OS',
            valor_fixo=Decimal('18000'),
            status='PENDENTE',
            servico_orcamento=self.servico_orcamento,
        )
        contrato_os = _get_or_create_contrato_empreitada(trabalho_os)
        trabalho_os.contrato_empreitada = contrato_os
        trabalho_os.save(update_fields=['contrato_empreitada'])

        self.assertEqual(contrato_os.ordem_servico_id, self.ordem_servico.id)
        self.assertNotEqual(contrato_avulso.id, contrato_os.id)

        # 3. Simular edição: associar trabalho avulso ao servico da OS
        trabalho_avulso.servico_orcamento = self.servico_orcamento
        trabalho_avulso.save()
        contrato_correto = _get_or_create_contrato_empreitada(trabalho_avulso)

        # Deve retornar o contrato da OS, não o avulso
        self.assertEqual(contrato_correto.id, contrato_os.id)
        self.assertEqual(contrato_correto.ordem_servico_id, self.ordem_servico.id)

        # 4. Reassign (como faz a view empreitada_edit)
        trabalho_avulso.contrato_empreitada = contrato_correto
        trabalho_avulso.save(update_fields=['contrato_empreitada'])

        # Ambos os trabalhos no mesmo contrato
        trabalhos_no_contrato = list(
            ContratoEmpreitada.objects.get(id=contrato_os.id).trabalhos.all()
        )
        self.assertEqual(len(trabalhos_no_contrato), 2)

        # Contrato avulso ficou vazio
        self.assertEqual(contrato_avulso.trabalhos.count(), 0)
