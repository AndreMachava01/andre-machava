"""Testes do ciclo de vida da folha salarial."""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from meuprojeto.empresa.models_base import DadosEmpresa, Sucursal
from meuprojeto.empresa.models_financas import PendenteContaPagar
from meuprojeto.empresa.models_rh import (
    Cargo,
    Departamento,
    FolhaSalarial,
    Funcionario,
    FuncionarioFolha,
)
from meuprojeto.empresa.services.rh_folha_service import (
    calcular_folha,
    fechar_folha,
    marcar_folha_paga,
    reabrir_folha,
)

User = get_user_model()


class RhFolhaServiceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='rh_folha_test', password='x')
        self.empresa = DadosEmpresa.objects.create(
            nome='Empresa Teste RH',
            nuit='400123456',
            alvara='ALV-TEST-001',
            data_constituicao=date(2020, 1, 1),
            provincia='Maputo',
            cidade='Maputo',
            bairro='Sommerschield',
            endereco='Rua Teste',
            telefone='+258841234567',
            email='rh@teste.co.mz',
            is_sede=True,
        )
        self.sucursal = Sucursal.objects.create(
            empresa_sede=self.empresa,
            nome='Sede Teste',
            codigo='SED-TEST',
            provincia='Maputo',
            cidade='Maputo',
            bairro='Sommerschield',
            endereco='Rua Teste 1',
            telefone='+258841234567',
            email='sede@teste.co.mz',
            data_abertura=date(2020, 1, 1),
            ativa=True,
        )
        self.departamento = Departamento.objects.create(
            nome='RH Teste',
            tipo='RH',
            sucursal=self.sucursal,
        )
        self.cargo = Cargo.objects.create(
            nome='Analista',
            nivel='ANA',
            departamento=self.departamento,
        )
        self.funcionario = Funcionario.objects.create(
            nome_completo='Funcionário Teste',
            sucursal=self.sucursal,
            departamento=self.departamento,
            cargo=self.cargo,
            data_admissao=date(2024, 1, 1),
            salario_atual=Decimal('25000.00'),
            status='AT',
        )
        self.folha = FolhaSalarial.objects.create(
            mes_referencia=date(2026, 3, 1),
            status='ABERTA',
        )

    def test_calcular_folha_adiciona_funcionario_activo(self):
        resultado = calcular_folha(self.folha)
        self.assertEqual(resultado['funcionarios_adicionados'], 1)
        self.assertEqual(self.folha.funcionarios_folha.count(), 1)
        self.assertEqual(self.folha.status, 'ABERTA')

    def test_fechar_folha_cria_pendente_financas(self):
        FuncionarioFolha.objects.create(
            folha=self.folha,
            funcionario=self.funcionario,
            salario_base=Decimal('25000'),
            salario_bruto=Decimal('25000'),
            salario_liquido=Decimal('22000'),
            dias_trabalhados=22,
            horas_trabalhadas=176,
        )
        self.folha.calcular_totais()

        fechar_folha(self.folha, user=self.user)
        self.folha.refresh_from_db()
        self.assertEqual(self.folha.status, 'FECHADA')

        pendente = PendenteContaPagar.objects.filter(
            origem_tipo='RH_FOLHA_SALARIAL',
            origem_id=self.folha.id,
        ).first()
        self.assertIsNotNone(pendente)
        self.assertEqual(pendente.estado, 'PENDENTE')
        self.assertGreater(pendente.valor, 0)

    def test_reabrir_folha_rejeita_pendente(self):
        FuncionarioFolha.objects.create(
            folha=self.folha,
            funcionario=self.funcionario,
            salario_base=Decimal('25000'),
            salario_bruto=Decimal('25000'),
            salario_liquido=Decimal('22000'),
            dias_trabalhados=22,
            horas_trabalhadas=176,
        )
        self.folha.calcular_totais()
        fechar_folha(self.folha, user=self.user)

        reabrir_folha(self.folha, user=self.user, motivo='Correcção')
        self.folha.refresh_from_db()
        self.assertEqual(self.folha.status, 'ABERTA')

        pendente = PendenteContaPagar.objects.get(
            origem_tipo='RH_FOLHA_SALARIAL',
            origem_id=self.folha.id,
        )
        self.assertEqual(pendente.estado, 'REJEITADO')

    def test_marcar_paga_apenas_folha_fechada(self):
        with self.assertRaises(ValidationError):
            marcar_folha_paga(self.folha)

        FuncionarioFolha.objects.create(
            folha=self.folha,
            funcionario=self.funcionario,
            salario_base=Decimal('25000'),
            salario_bruto=Decimal('25000'),
            salario_liquido=Decimal('22000'),
            dias_trabalhados=22,
            horas_trabalhadas=176,
        )
        self.folha.calcular_totais()
        fechar_folha(self.folha, user=self.user)
        marcar_folha_paga(self.folha)
        self.folha.refresh_from_db()
        self.assertEqual(self.folha.status, 'PAGA')
        self.assertIsNotNone(self.folha.data_pagamento)
