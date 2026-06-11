"""Testes de serviços e views de empreitadas e relatórios RH."""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import Client, TestCase
from django.urls import reverse

from meuprojeto.empresa.models_rh import (
    ContratoEmpreitada,
    PrestadorServico,
    TrabalhoEmpreitada,
)
from meuprojeto.empresa.services.rh_empreitada_service import (
    get_or_create_contrato_empreitada,
    queryset_empreitadas_lista,
    vincular_trabalho_ao_contrato,
)
from meuprojeto.empresa.services.rh_relatorios_service import (
    montar_contexto_relatorio_custos_rh,
    montar_contexto_relatorio_geral_rh,
)

User = get_user_model()


class RhEmpreitadaServiceTest(TestCase):
    def setUp(self):
        self.prestador = PrestadorServico.objects.create(
            nome='Prestador Empreitada Teste',
            tipo='SINGULAR',
            ativo=True,
        )
        self.trabalho_avulso = TrabalhoEmpreitada.objects.create(
            descricao='Trabalho avulso',
            valor_fixo=Decimal('10000'),
            status='PENDENTE',
            prestador=self.prestador,
        )
        self.trabalho_vinculado = TrabalhoEmpreitada.objects.create(
            descricao='Trabalho com contrato',
            valor_fixo=Decimal('25000'),
            status='EM_ANDAMENTO',
            prestador=self.prestador,
        )
        vincular_trabalho_ao_contrato(self.trabalho_vinculado)

    def test_get_or_create_contrato_trabalho_avulso(self):
        contrato = get_or_create_contrato_empreitada(self.trabalho_avulso)
        self.assertIsNotNone(contrato.id)
        self.assertEqual(contrato.prestador_id, self.prestador.id)
        self.assertIsNone(contrato.ordem_servico_id)

        mesmo = get_or_create_contrato_empreitada(self.trabalho_avulso)
        self.assertEqual(contrato.id, mesmo.id)
        self.assertEqual(
            ContratoEmpreitada.objects.filter(
                prestador=self.prestador,
                ordem_servico__isnull=True,
            ).count(),
            1,
        )

    def test_vincular_trabalho_ao_contrato(self):
        contrato = vincular_trabalho_ao_contrato(self.trabalho_avulso)
        self.trabalho_avulso.refresh_from_db()
        self.assertEqual(self.trabalho_avulso.contrato_empreitada_id, contrato.id)

        outro = vincular_trabalho_ao_contrato(self.trabalho_avulso)
        self.assertEqual(contrato.id, outro.id)

    def test_queryset_empreitadas_lista_separa_sem_contrato(self):
        contratos, sem_contrato = queryset_empreitadas_lista()
        ids_contratos = {c.id for c in contratos}
        self.trabalho_vinculado.refresh_from_db()
        self.assertIn(self.trabalho_vinculado.contrato_empreitada_id, ids_contratos)
        ids_sem = {t.id for t in sem_contrato}
        self.assertIn(self.trabalho_avulso.id, ids_sem)

    def test_queryset_empreitadas_lista_filtra_status(self):
        contratos, sem_contrato = queryset_empreitadas_lista('EM_ANDAMENTO')
        todos_ids = set()
        for contrato in contratos:
            for t in contrato.trabalhos.all():
                todos_ids.add(t.id)
                self.assertEqual(t.status, 'EM_ANDAMENTO')
        for t in sem_contrato:
            todos_ids.add(t.id)
            self.assertEqual(t.status, 'EM_ANDAMENTO')
        self.assertIn(self.trabalho_vinculado.id, todos_ids)
        self.assertNotIn(self.trabalho_avulso.id, todos_ids)


class RhRelatoriosServiceTest(TestCase):
    def test_montar_contexto_relatorio_geral_defaults(self):
        ctx = montar_contexto_relatorio_geral_rh({})
        self.assertIn('total_funcionarios', ctx)
        self.assertIn('filtros', ctx)
        self.assertIn('data_inicio', ctx['filtros'])
        self.assertIn('data_fim', ctx['filtros'])
        self.assertEqual(ctx['total_funcionarios'], 0)

    def test_montar_contexto_relatorio_custos_defaults(self):
        ctx = montar_contexto_relatorio_custos_rh({})
        self.assertIn('total_geral_custos_rh', ctx)
        self.assertIn('custos_por_departamento', ctx)
        self.assertEqual(ctx['total_salarios'], Decimal('0'))
        self.assertEqual(ctx['quantidade_treinamentos'], 0)

    def test_montar_contexto_relatorio_geral_mes_referencia(self):
        ctx = montar_contexto_relatorio_geral_rh({'mes_referencia': '2026-01'})
        self.assertEqual(ctx['filtros']['mes_referencia'], '2026-01')
        self.assertEqual(ctx['filtros']['data_inicio'].month, 1)
        self.assertEqual(ctx['filtros']['data_inicio'].year, 2026)
        self.assertEqual(ctx['filtros']['data_fim'].month, 1)


class RhEmpreitadasRelatoriosViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='rh_emp_rel', password='x')
        self.client.force_login(self.user)
        self.prestador = PrestadorServico.objects.create(
            nome='Prestador View',
            tipo='SINGULAR',
            ativo=True,
        )
        self.trabalho = TrabalhoEmpreitada.objects.create(
            descricao='Trabalho view teste',
            valor_fixo=Decimal('5000'),
            prestador=self.prestador,
        )
        vincular_trabalho_ao_contrato(self.trabalho)
        self.trabalho.refresh_from_db()

    def test_templates_empreitadas_renderizam(self):
        rotas = [
            ('rh:empreitadas', []),
            ('rh:empreitada_add', []),
            ('rh:empreitada_detail', [self.trabalho.id]),
            ('rh:empreitada_edit', [self.trabalho.id]),
        ]
        if self.trabalho.contrato_empreitada_id:
            rotas.append(
                ('rh:preview_contrato_empreitada', [self.trabalho.contrato_empreitada_id]),
            )
        for name, args in rotas:
            with self.subTest(rota=name):
                response = self.client.get(reverse(name, args=args))
                self.assertEqual(response.status_code, 200, msg=f'Falha em {name}')

    def test_templates_relatorios_renderizam(self):
        rotas = [
            ('rh:relatorios', []),
            ('rh:relatorio_funcionarios_documento', []),
            ('rh:relatorio_presencas_documento', []),
            ('rh:relatorio_salarios_documento', []),
            ('rh:relatorio_treinamentos_documento', []),
            ('rh:relatorio_avaliacoes_documento', []),
            ('rh:relatorio_horas_extras_documento', []),
            ('rh:relatorio_feriados_documento', []),
            ('rh:relatorio_geral_rh_documento', []),
            ('rh:relatorio_custos_rh_documento', []),
        ]
        for name, args in rotas:
            with self.subTest(rota=name):
                response = self.client.get(reverse(name, args=args))
                self.assertEqual(response.status_code, 200, msg=f'Falha em {name}')


class RhRelatoriosPdfViewsTest(TestCase):
    """Views PDF de relatórios RH sem depender de Chrome/Edge no ambiente de teste."""

    ROTAS_PDF = [
        'rh:relatorio_funcionarios_pdf',
        'rh:relatorio_presencas_pdf',
        'rh:relatorio_salarios_pdf',
        'rh:relatorio_treinamentos_pdf',
        'rh:relatorio_avaliacoes_pdf',
        'rh:relatorio_horas_extras_pdf',
        'rh:relatorio_feriados_pdf',
        'rh:relatorio_geral_rh_pdf',
        'rh:relatorio_custos_rh_pdf',
    ]

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='rh_pdf_views', password='x')
        self.client.force_login(self.user)
        self.mock_pdf = patch(
            'meuprojeto.empresa.views_rh_relatorios.render_pdf_from_html_string',
            side_effect=self._fake_pdf_response,
        ).start()
        self.addCleanup(patch.stopall)

    @staticmethod
    def _fake_pdf_response(request, html_string, filename, landscape=False):
        response = HttpResponse(b'%PDF-mock', content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    def test_relatorios_pdf_views_retornam_pdf_mockado(self):
        for name in self.ROTAS_PDF:
            with self.subTest(rota=name):
                self.mock_pdf.reset_mock()
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200, msg=f'Falha em {name}')
                self.assertEqual(response['Content-Type'], 'application/pdf')
                self.assertIn('attachment', response['Content-Disposition'])
                self.mock_pdf.assert_called_once()
                _request, html_string, filename = self.mock_pdf.call_args[0]
                self.assertGreater(len(html_string), 50)
                self.assertTrue(filename.endswith('.pdf'))

    def test_relatorio_pdf_get_gerar_formulario(self):
        response = self.client.get(reverse('rh:relatorio_pdf'))
        self.assertEqual(response.status_code, 200)
        self.mock_pdf.assert_not_called()

    def test_relatorio_pdf_post_redireciona_para_pdf(self):
        response = self.client.post(reverse('rh:relatorio_pdf'), {
            'tipo_relatorio': 'geral',
            'formato': 'pdf',
            'mes_referencia': '2026-01',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            reverse('rh:relatorio_geral_rh_pdf') + '?mes_referencia=2026-01',
        )

    def test_relatorio_pdf_post_redireciona_para_html(self):
        response = self.client.post(reverse('rh:relatorio_pdf'), {
            'tipo_relatorio': 'custos',
            'formato': 'html',
            'data_inicio': '2026-01-01',
            'data_fim': '2026-01-31',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            reverse('rh:relatorio_custos_rh_documento')
            + '?data_inicio=2026-01-01&data_fim=2026-01-31',
        )

    def test_relatorio_pdf_post_segue_redirect_e_gera_pdf(self):
        response = self.client.post(reverse('rh:relatorio_pdf'), {
            'tipo_relatorio': 'funcionarios',
            'formato': 'pdf',
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.mock_pdf.assert_called_once()
