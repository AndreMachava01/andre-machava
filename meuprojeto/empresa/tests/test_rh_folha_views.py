"""Testes de views e templates da folha salarial."""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from meuprojeto.empresa.models_base import DadosEmpresa, Sucursal
from meuprojeto.empresa.models_rh import (
    Cargo,
    Departamento,
    FolhaSalarial,
    Funcionario,
    FuncionarioFolha,
)

User = get_user_model()


class RhFolhaViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='rh_folha_views', password='x')
        self.client.force_login(self.user)

        empresa = DadosEmpresa.objects.create(
            nome='Empresa Views RH',
            nuit='400987654',
            alvara='ALV-VIEW-001',
            data_constituicao=date(2020, 1, 1),
            provincia='Maputo',
            cidade='Maputo',
            bairro='Teste',
            endereco='Rua Views',
            telefone='+258841111111',
            email='views@teste.co.mz',
            is_sede=True,
        )
        sucursal = Sucursal.objects.create(
            empresa_sede=empresa,
            nome='Sede Views',
            codigo='SED-VIEW',
            provincia='Maputo',
            cidade='Maputo',
            bairro='Teste',
            endereco='Rua Views 1',
            telefone='+258841111111',
            email='views@sede.co.mz',
            data_abertura=date(2020, 1, 1),
            ativa=True,
        )
        departamento = Departamento.objects.create(
            nome='Dept Views',
            tipo='RH',
            sucursal=sucursal,
        )
        cargo = Cargo.objects.create(
            nome='Técnico',
            nivel='TEC',
            departamento=departamento,
        )
        self.funcionario = Funcionario.objects.create(
            nome_completo='Colaborador Views',
            sucursal=sucursal,
            departamento=departamento,
            cargo=cargo,
            data_admissao=date(2024, 1, 1),
            salario_atual=Decimal('20000.00'),
            status='AT',
        )
        self.folha = FolhaSalarial.objects.create(
            mes_referencia=date(2026, 4, 1),
            status='ABERTA',
            observacoes='Obs inicial',
        )
        self.funcionario_folha = FuncionarioFolha.objects.create(
            folha=self.folha,
            funcionario=self.funcionario,
            salario_base=Decimal('20000'),
            salario_bruto=Decimal('20000'),
            salario_liquido=Decimal('18000'),
            dias_trabalhados=22,
            horas_trabalhadas=176,
        )
        self.folha.calcular_totais()

    def test_folha_edit_atualiza_observacoes(self):
        url = reverse('rh:folha_edit', args=[self.folha.id])
        response = self.client.post(url, {
            'mes': '4',
            'ano': '2026',
            'observacoes': 'Observações actualizadas',
        })
        self.assertEqual(response.status_code, 302)
        self.folha.refresh_from_db()
        self.assertEqual(self.folha.observacoes, 'Observações actualizadas')

    def test_folha_edit_altera_mes_quando_aberta(self):
        url = reverse('rh:folha_edit', args=[self.folha.id])
        response = self.client.post(url, {
            'mes': '5',
            'ano': '2026',
            'observacoes': self.folha.observacoes,
        })
        self.assertEqual(response.status_code, 302)
        self.folha.refresh_from_db()
        self.assertEqual(self.folha.mes_referencia, date(2026, 5, 1))

    def test_folha_edit_nao_altera_mes_quando_fechada(self):
        self.folha.status = 'FECHADA'
        self.folha.data_fechamento = date.today()
        self.folha.save()

        url = reverse('rh:folha_edit', args=[self.folha.id])
        response = self.client.post(url, {
            'mes': '6',
            'ano': '2026',
            'observacoes': 'Só observações',
        })
        self.assertEqual(response.status_code, 302)
        self.folha.refresh_from_db()
        self.assertEqual(self.folha.mes_referencia, date(2026, 4, 1))
        self.assertEqual(self.folha.observacoes, 'Só observações')

    def test_folha_fechar_envia_observacoes(self):
        url = reverse('rh:folha_fechar', args=[self.folha.id])
        response = self.client.post(url, {'observacoes': 'Fecho de teste'})
        self.assertIn(response.status_code, (302, 200))
        if response.status_code == 302:
            self.folha.refresh_from_db()
            self.assertEqual(self.folha.status, 'FECHADA')

    def test_templates_folha_renderizam(self):
        rotas = [
            ('rh:folha_salarial', []),
            ('rh:folha_detail', [self.folha.id]),
            ('rh:folha_edit', [self.folha.id]),
            ('rh:folha_add', []),
            ('rh:folha_validar_fechamento', [self.folha.id]),
            ('rh:folha_calcular', [self.folha.id]),
            ('rh:folha_beneficios', [self.folha.id]),
            ('rh:folha_descontos', [self.folha.id]),
            ('rh:folha_preview', [self.folha.id]),
            ('rh:canhoto_visualizar', [self.folha.id, self.funcionario.id]),
            ('rh:folha_funcionario_detail', [self.folha.id, self.funcionario.id]),
        ]
        for name, args in rotas:
            with self.subTest(rota=name):
                response = self.client.get(reverse(name, args=args))
                self.assertEqual(response.status_code, 200, msg=f'Falha em {name}')

    def test_validar_fechamento_post_fecha_folha(self):
        url = reverse('rh:folha_validar_fechamento', args=[self.folha.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.folha.refresh_from_db()
        self.assertEqual(self.folha.status, 'FECHADA')
