"""Testes de férias, hierarquia e presenças (serviços e views)."""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from meuprojeto.empresa.models_base import DadosEmpresa, Sucursal
from meuprojeto.empresa.models_rh import (
    Cargo,
    Departamento,
    Funcionario,
    PosicaoHierarquica,
    Presenca,
    SolicitacaoAlteracaoHierarquia,
    SolicitacaoFerias,
    TipoPresenca,
)
from meuprojeto.empresa.services.rh_ferias_service import (
    aprovar_solicitacao_ferias,
    criar_solicitacao_ferias,
    obter_stats_ferias,
    rejeitar_solicitacao_ferias,
)
from meuprojeto.empresa.services.rh_hierarquia_service import (
    aprovar_solicitacao_hierarquia,
    criar_solicitacao_hierarquia,
    obter_stats_hierarquia,
    rejeitar_solicitacao_hierarquia,
)

User = get_user_model()


def _criar_contexto_rh():
    empresa = DadosEmpresa.objects.create(
        nome='Empresa RH Sub',
        nuit='400111222',
        alvara='ALV-SUB-001',
        data_constituicao=date(2020, 1, 1),
        provincia='Maputo',
        cidade='Maputo',
        bairro='Central',
        endereco='Rua Sub',
        telefone='+258840000001',
        email='sub@teste.co.mz',
        is_sede=True,
    )
    sucursal = Sucursal.objects.create(
        empresa_sede=empresa,
        nome='Sede Sub',
        codigo='SED-SUB',
        provincia='Maputo',
        cidade='Maputo',
        bairro='Central',
        endereco='Rua Sub 1',
        telefone='+258840000001',
        email='sub@sede.co.mz',
        data_abertura=date(2020, 1, 1),
        ativa=True,
    )
    departamento = Departamento.objects.create(
        nome='Operações Sub',
        tipo='OPR',
        sucursal=sucursal,
        ativo=True,
    )
    cargo = Cargo.objects.create(
        nome='Assistente',
        nivel='ASS',
        departamento=departamento,
        ativo=True,
    )
    posicao = PosicaoHierarquica.objects.create(nome='Analista', nivel=2, ativa=True)
    posicao.departamentos.add(departamento)
    posicao_superior = PosicaoHierarquica.objects.create(nome='Gerente', nivel=1, ativa=True)
    posicao_superior.departamentos.add(departamento)

    funcionario = Funcionario.objects.create(
        nome_completo='Funcionário Sub',
        sucursal=sucursal,
        departamento=departamento,
        cargo=cargo,
        posicao=posicao,
        data_admissao=date(2024, 1, 1),
        salario_atual=Decimal('15000.00'),
        status='AT',
    )
    chefe = Funcionario.objects.create(
        nome_completo='Chefe Sub',
        sucursal=sucursal,
        departamento=departamento,
        cargo=cargo,
        posicao=posicao_superior,
        data_admissao=date(2023, 1, 1),
        salario_atual=Decimal('30000.00'),
        status='AT',
    )
    funcionario.chefe = chefe
    funcionario.save(update_fields=['chefe'])

    tipo_ferias, _ = TipoPresenca.objects.get_or_create(
        codigo='FE',
        defaults={'nome': 'Férias', 'ativo': True},
    )
    return {
        'user': User.objects.create_user(username='rh_sub_test', password='x'),
        'funcionario': funcionario,
        'chefe': chefe,
        'departamento': departamento,
        'posicao': posicao,
        'posicao_superior': posicao_superior,
        'tipo_ferias': tipo_ferias,
    }


class RhFeriasServiceTest(TestCase):
    def setUp(self):
        ctx = _criar_contexto_rh()
        self.user = ctx['user']
        self.funcionario = ctx['funcionario']

    def test_criar_solicitacao_ferias(self):
        inicio = date.today() + timedelta(days=30)
        fim = inicio + timedelta(days=4)
        sol = criar_solicitacao_ferias(
            self.funcionario.id, inicio, fim, 'Férias anuais', self.user,
        )
        self.assertEqual(sol.status, 'PENDENTE')
        self.assertEqual(sol.funcionario_id, self.funcionario.id)
        stats = obter_stats_ferias()
        self.assertEqual(stats['pendentes'], 1)

    def test_criar_rejeita_periodo_invalido(self):
        inicio = date.today() + timedelta(days=10)
        fim = inicio - timedelta(days=1)
        with self.assertRaises(ValueError):
            criar_solicitacao_ferias(self.funcionario.id, inicio, fim, 'Erro', self.user)

    def test_aprovar_marca_presencas(self):
        inicio = date.today() + timedelta(days=40)
        fim = inicio + timedelta(days=2)
        sol = criar_solicitacao_ferias(
            self.funcionario.id, inicio, fim, 'Descanso', self.user,
        )
        ok, msg = aprovar_solicitacao_ferias(sol, self.user)
        self.assertTrue(ok, msg)
        sol.refresh_from_db()
        self.assertEqual(sol.status, 'APROVADO')
        self.assertEqual(
            Presenca.objects.filter(funcionario=self.funcionario, tipo_presenca__codigo='FE').count(),
            3,
        )

    def test_rejeitar_solicitacao(self):
        inicio = date.today() + timedelta(days=50)
        fim = inicio + timedelta(days=1)
        sol = criar_solicitacao_ferias(self.funcionario.id, inicio, fim, 'Teste', self.user)
        ok, _ = rejeitar_solicitacao_ferias(sol, self.user, 'Indisponível')
        self.assertTrue(ok)
        sol.refresh_from_db()
        self.assertEqual(sol.status, 'REJEITADO')


class RhHierarquiaServiceTest(TestCase):
    def setUp(self):
        ctx = _criar_contexto_rh()
        self.user = ctx['user']
        self.funcionario = ctx['funcionario']
        self.posicao_superior = ctx['posicao_superior']

    def test_criar_solicitacao_hierarquia(self):
        sol = criar_solicitacao_hierarquia(
            self.funcionario.id, 1, 'Promoção interna', self.user,
        )
        self.assertEqual(sol.status, 'ABERTO')
        self.assertEqual(sol.novo_nivel, 1)
        stats = obter_stats_hierarquia()
        self.assertEqual(stats['solicitacoes_pendentes'], 1)

    def test_aprovar_atualiza_funcionario(self):
        sol = criar_solicitacao_hierarquia(
            self.funcionario.id, 1, 'Subir de nível', self.user,
        )
        ok, msg = aprovar_solicitacao_hierarquia(sol, self.user)
        self.assertTrue(ok, msg)
        self.funcionario.refresh_from_db()
        self.assertEqual(self.funcionario.posicao.nivel, 1)

    def test_rejeitar_solicitacao_hierarquia(self):
        sol = criar_solicitacao_hierarquia(
            self.funcionario.id, 1, 'Tentativa', self.user,
        )
        ok, _ = rejeitar_solicitacao_hierarquia(sol, self.user, 'Não aprovado')
        self.assertTrue(ok)
        sol.refresh_from_db()
        self.assertEqual(sol.status, 'REJEITADO')


class RhSubmodulosViewsTest(TestCase):
    def setUp(self):
        ctx = _criar_contexto_rh()
        self.user = ctx['user']
        self.funcionario = ctx['funcionario']
        self.client = Client()
        self.client.force_login(self.user)

        self.solicitacao_ferias = SolicitacaoFerias.objects.create(
            funcionario=self.funcionario,
            data_inicio=date.today() + timedelta(days=60),
            data_fim=date.today() + timedelta(days=62),
            motivo='Teste view',
            solicitado_por=self.user,
        )
        self.solicitacao_hierarquia = SolicitacaoAlteracaoHierarquia.objects.create(
            funcionario=self.funcionario,
            novo_nivel=1,
            motivo='Teste view hierarquia',
            solicitado_por=self.user,
        )

    def test_templates_submodulos_renderizam(self):
        rotas = [
            ('rh:ferias', []),
            ('rh:ferias_solicitar', []),
            ('rh:hierarquia_main', []),
            ('rh:hierarquia_solicitar', []),
            ('rh:hierarquia_aprovar', []),
            ('rh:hierarquia_historico', []),
            ('rh:posicoes', []),
            ('rh:presencas', []),
            ('rh:tipos_presenca', []),
            ('rh:calendario_presencas', []),
        ]
        for name, args in rotas:
            with self.subTest(rota=name):
                response = self.client.get(reverse(name, args=args))
                self.assertEqual(response.status_code, 200, msg=f'Falha em {name}')

    def test_ferias_solicitar_post(self):
        inicio = date.today() + timedelta(days=70)
        fim = inicio + timedelta(days=2)
        response = self.client.post(reverse('rh:ferias_solicitar'), {
            'funcionario_id': self.funcionario.id,
            'data_inicio': inicio.isoformat(),
            'data_fim': fim.isoformat(),
            'motivo': 'Pedido via view',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            SolicitacaoFerias.objects.filter(motivo='Pedido via view').exists(),
        )

    def test_hierarquia_solicitar_post(self):
        response = self.client.post(reverse('rh:hierarquia_solicitar'), {
            'funcionario_id': self.funcionario.id,
            'novo_nivel': '1',
            'motivo': 'Solicitação via view',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            SolicitacaoAlteracaoHierarquia.objects.filter(motivo='Solicitação via view').exists(),
        )

    def test_ferias_aprovar_post(self):
        response = self.client.post(
            reverse('rh:ferias_aprovar', args=[self.solicitacao_ferias.id]),
            {'acao': 'rejeitar', 'observacao': 'Teste'},
        )
        self.assertEqual(response.status_code, 302)
        self.solicitacao_ferias.refresh_from_db()
        self.assertEqual(self.solicitacao_ferias.status, 'REJEITADO')
