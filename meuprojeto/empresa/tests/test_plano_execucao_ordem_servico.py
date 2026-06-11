"""
Testes do plano de execução da ordem de serviço:
- Conversão cotação → ordem redirecciona para definir plano
- Definir etapas (actividades e subactividades) com nomes e prazos
- Botões Iniciar / Pausar / Retomar / Concluir por etapa e sequência
- Avanço e cronograma
- Avisos Finanças (parcelas / conclusão total)
"""
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from meuprojeto.empresa.models_stock import (
    OrdemServico,
    ServicoOrcamentoServico,
    AtividadeExecucao,
    ClienteServico,
    Item,
    CategoriaProduto,
)
from meuprojeto.empresa.models_financas import PendenteContaReceber
from meuprojeto.empresa.cronograma_plano_service import build_cronograma_context

User = get_user_model()


class PlanoExecucaoOrdemServicoTests(TestCase):
    """Testes do fluxo plano de execução ao converter cotação em ordem de serviço."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='test_plano',
            password='test123',
        )
        self.client.login(username='test_plano', password='test123')

        self.cliente = ClienteServico.objects.create(
            nome='Cliente Plano Teste',
            nuit='987654321',
            telefone='840000000',
            endereco='Endereço Teste',
            cidade='Maputo',
        )
        self.categoria_servico = CategoriaProduto.objects.create(
            nome='Serviços',
            codigo='CAT-SERV-01',
            tipo='SERVICO',
        )
        self.servico_item = Item.objects.create(
            nome='Serviço de instalação',
            tipo='PRODUTO',
            produto_tipo='SERVICO',
            codigo='SERV-PLANO-001',
            categoria=self.categoria_servico,
        )
        # Cotação (COT) com um serviço para poder confirmar
        self.cotacao = OrdemServico.objects.create(
            codigo='COT-2026-PLANO01',
            cliente=self.cliente,
            data_agendada=timezone.now(),
            endereco_servico='Rua do Serviço',
            cidade_servico='Maputo',
            status='AGENDADA',
            quantidade=Decimal('1'),
            valor_total=Decimal('10000'),
            validade_garantia_dias=90,
            criado_por=self.user,
        )
        ServicoOrcamentoServico.objects.create(
            ordem_servico=self.cotacao,
            servico=self.servico_item,
            quantidade=Decimal('1'),
            valor_unitario=Decimal('10000'),
            desconto=Decimal('0'),
        )

    def test_confirmar_cotacao_redirects_to_plano_execucao(self):
        """Ao confirmar cotação, o sistema redirecciona para definir plano de execução."""
        url = reverse('producao:servico_orcamento_confirmar_acao', args=[self.cotacao.id])
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            response.url.startswith(reverse('producao:servico_ordem_plano_execucao', args=[0]).replace('0', ''))
            or 'plano-execucao' in response.url
        )
        # Ordem de serviço foi criada
        ordem = OrdemServico.objects.filter(orcamento_origem=self.cotacao, codigo__startswith='OS').first()
        self.assertIsNotNone(ordem)
        self.assertIn(str(ordem.id), response.url)

    def test_plano_execucao_page_loads(self):
        """Página de definir plano de execução carrega e mostra formulário de etapas."""
        ordem = OrdemServico.objects.create(
            codigo='OS-2026-PLANO1',
            orcamento_origem=self.cotacao,
            cliente=self.cliente,
            data_agendada=timezone.now(),
            endereco_servico='Rua do Serviço',
            cidade_servico='Maputo',
            status='AGENDADA',
            quantidade=Decimal('1'),
            valor_total=Decimal('10000'),
            criado_por=self.user,
        )
        ServicoOrcamentoServico.objects.create(
            ordem_servico=ordem,
            servico=self.servico_item,
            quantidade=Decimal('1'),
            valor_unitario=Decimal('10000'),
            desconto=Decimal('0'),
        )
        url = reverse('producao:servico_ordem_plano_execucao', args=[ordem.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Plano de execução')
        self.assertContains(response, 'Nome da etapa')
        self.assertContains(response, 'Prazo previsto')

    def test_save_plano_creates_etapas(self):
        """Guardar plano com etapas cria registos AtividadeExecucao."""
        ordem = OrdemServico.objects.create(
            codigo='OS-2026-PLANO2',
            orcamento_origem=self.cotacao,
            cliente=self.cliente,
            data_agendada=timezone.now(),
            endereco_servico='Rua do Serviço',
            cidade_servico='Maputo',
            status='AGENDADA',
            quantidade=Decimal('1'),
            valor_total=Decimal('10000'),
            criado_por=self.user,
        )
        ServicoOrcamentoServico.objects.create(
            ordem_servico=ordem,
            servico=self.servico_item,
            quantidade=Decimal('1'),
            valor_unitario=Decimal('10000'),
            desconto=Decimal('0'),
        )
        url = reverse('producao:servico_ordem_plano_execucao', args=[ordem.id])
        get_resp = self.client.get(url)
        csrf = get_resp.cookies.get('csrftoken', '') or ''
        if not csrf and 'csrfmiddlewaretoken' in get_resp.content.decode():
            import re
            m = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', get_resp.content.decode())
            if m:
                csrf = m.group(1)
        data = {
            'csrfmiddlewaretoken': csrf,
            'etapa_count': '2',
            'etapa_0_nome': 'Montagem',
            'etapa_0_data_prevista': '2026-03-01',
            'etapa_0_parent_idx': '-1',
            'etapa_1_nome': 'Instalação',
            'etapa_1_data_prevista': '2026-03-15',
            'etapa_1_parent_idx': '-1',
        }
        response = self.client.post(url, data, follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('producao:servico_ordem_detail', args=[ordem.id]))
        self.assertEqual(AtividadeExecucao.objects.filter(ordem_servico=ordem).count(), 2)
        a1, a2 = AtividadeExecucao.objects.filter(ordem_servico=ordem).order_by('numero_ordem')
        self.assertEqual(a1.nome, 'Montagem')
        self.assertEqual(a2.nome, 'Instalação')
        self.assertIsNone(a1.parent_id)
        self.assertIsNone(a2.parent_id)

    def test_activity_iniciar_and_concluir(self):
        """Iniciar e concluir uma actividade altera o estado e datas."""
        ordem = OrdemServico.objects.create(
            codigo='OS-2026-PLANO3',
            orcamento_origem=self.cotacao,
            cliente=self.cliente,
            data_agendada=timezone.now(),
            endereco_servico='Rua do Serviço',
            cidade_servico='Maputo',
            status='AGENDADA',
            quantidade=Decimal('1'),
            valor_total=Decimal('10000'),
            criado_por=self.user,
        )
        atv = AtividadeExecucao.objects.create(
            ordem_servico=ordem,
            nome='Etapa única',
            numero_ordem=1,
            status='AGENDADA',
        )
        url_status = reverse('producao:servico_atividade_alterar_status', args=[ordem.id, atv.id])

        response = self.client.post(url_status, {'acao': 'iniciar'})
        self.assertEqual(response.status_code, 302)
        atv.refresh_from_db()
        self.assertEqual(atv.status, 'EM_ANDAMENTO')
        self.assertIsNotNone(atv.data_inicio)

        response = self.client.post(url_status, {'acao': 'concluir'})
        self.assertEqual(response.status_code, 302)
        atv.refresh_from_db()
        self.assertEqual(atv.status, 'CONCLUIDA')
        self.assertIsNotNone(atv.data_conclusao)

    def test_all_activities_concluded_marks_order_concluded(self):
        """Quando todas as etapas estão concluídas, a ordem fica CONCLUIDA."""
        ordem = OrdemServico.objects.create(
            codigo='OS-2026-PLANO4',
            orcamento_origem=self.cotacao,
            cliente=self.cliente,
            data_agendada=timezone.now(),
            endereco_servico='Rua do Serviço',
            cidade_servico='Maputo',
            status='EM_ANDAMENTO',
            quantidade=Decimal('1'),
            valor_total=Decimal('10000'),
            criado_por=self.user,
        )
        a1 = AtividadeExecucao.objects.create(
            ordem_servico=ordem,
            nome='Etapa 1',
            numero_ordem=1,
            status='CONCLUIDA',
            data_conclusao=timezone.now(),
        )
        a2 = AtividadeExecucao.objects.create(
            ordem_servico=ordem,
            nome='Etapa 2',
            numero_ordem=2,
            status='AGENDADA',
        )
        url_status = reverse('producao:servico_atividade_alterar_status', args=[ordem.id, a2.id])
        self.client.post(url_status, {'acao': 'iniciar'})
        self.client.post(url_status, {'acao': 'concluir'})

        ordem.refresh_from_db()
        self.assertEqual(ordem.status, 'CONCLUIDA')
        self.assertIsNotNone(ordem.data_conclusao)

    def test_subactivity_can_be_concluded_before_parent(self):
        """Subactividades podem ser concluídas antes da actividade principal."""
        ordem = OrdemServico.objects.create(
            codigo='OS-2026-PLANO5',
            orcamento_origem=self.cotacao,
            cliente=self.cliente,
            data_agendada=timezone.now(),
            endereco_servico='Rua do Serviço',
            cidade_servico='Maputo',
            status='AGENDADA',
            quantidade=Decimal('1'),
            valor_total=Decimal('10000'),
            criado_por=self.user,
        )
        pai = AtividadeExecucao.objects.create(
            ordem_servico=ordem,
            nome='Actividade principal',
            numero_ordem=1,
            status='AGENDADA',
        )
        sub = AtividadeExecucao.objects.create(
            ordem_servico=ordem,
            parent=pai,
            nome='Subactividade',
            numero_ordem=1,
            status='AGENDADA',
        )
        # Concluir subactividade primeiro
        url_sub = reverse('producao:servico_atividade_alterar_status', args=[ordem.id, sub.id])
        self.client.post(url_sub, {'acao': 'iniciar'})
        self.client.post(url_sub, {'acao': 'concluir'})
        sub.refresh_from_db()
        self.assertEqual(sub.status, 'CONCLUIDA')
        # Principal ainda pode ser iniciada e depois concluída
        url_pai = reverse('producao:servico_atividade_alterar_status', args=[ordem.id, pai.id])
        self.client.post(url_pai, {'acao': 'iniciar'})
        self.client.post(url_pai, {'acao': 'concluir'})
        pai.refresh_from_db()
        self.assertEqual(pai.status, 'CONCLUIDA')

    def test_order_detail_shows_plano_and_progress(self):
        """A página de detalhe da ordem mostra plano de execução e avanço."""
        ordem = OrdemServico.objects.create(
            codigo='OS-2026-PLANO6',
            orcamento_origem=self.cotacao,
            cliente=self.cliente,
            data_agendada=timezone.now(),
            endereco_servico='Rua do Serviço',
            cidade_servico='Maputo',
            status='EM_ANDAMENTO',
            quantidade=Decimal('1'),
            valor_total=Decimal('10000'),
            criado_por=self.user,
        )
        AtividadeExecucao.objects.create(
            ordem_servico=ordem,
            nome='Etapa A',
            numero_ordem=1,
            status='CONCLUIDA',
            data_conclusao=timezone.now(),
        )
        AtividadeExecucao.objects.create(
            ordem_servico=ordem,
            nome='Etapa B',
            numero_ordem=2,
            status='AGENDADA',
        )
        url = reverse('producao:servico_ordem_detail', args=[ordem.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Plano de execução')
        self.assertContains(response, 'Etapa A')
        self.assertContains(response, 'Etapa B')
        self.assertContains(response, 'Avanço')
        self.assertContains(response, '1 / 2')

    def test_pode_iniciar_respects_sequence(self):
        """Só é possível iniciar a próxima etapa quando a anterior está concluída."""
        ordem = OrdemServico.objects.create(
            codigo='OS-2026-PLANO7',
            orcamento_origem=self.cotacao,
            cliente=self.cliente,
            data_agendada=timezone.now(),
            endereco_servico='Rua do Serviço',
            cidade_servico='Maputo',
            status='AGENDADA',
            quantidade=Decimal('1'),
            valor_total=Decimal('10000'),
            criado_por=self.user,
        )
        a1 = AtividadeExecucao.objects.create(
            ordem_servico=ordem,
            nome='Primeira',
            numero_ordem=1,
            status='AGENDADA',
        )
        a2 = AtividadeExecucao.objects.create(
            ordem_servico=ordem,
            nome='Segunda',
            numero_ordem=2,
            status='AGENDADA',
        )
        self.assertTrue(a1.pode_iniciar())
        self.assertFalse(a2.pode_iniciar())
        a1.status = 'CONCLUIDA'
        a1.save()
        a2.refresh_from_db()
        self.assertTrue(a2.pode_iniciar())

    def test_cronograma_context_returns_bars_and_scale(self):
        """O serviço de cronograma devolve escala e barras quando há actividades com datas."""
        from datetime import date, datetime, timedelta
        ordem = OrdemServico.objects.create(
            codigo='OS-2026-CRONO',
            orcamento_origem=self.cotacao,
            cliente=self.cliente,
            data_agendada=timezone.now(),
            endereco_servico='Rua do Serviço',
            cidade_servico='Maputo',
            status='EM_ANDAMENTO',
            quantidade=Decimal('1'),
            valor_total=Decimal('10000'),
            criado_por=self.user,
        )
        hoje = date.today()
        a1 = AtividadeExecucao.objects.create(
            ordem_servico=ordem,
            nome='Etapa com prazo',
            numero_ordem=1,
            status='CONCLUIDA',
            data_prevista_conclusao=hoje - timedelta(days=5),
            data_inicio=timezone.make_aware(datetime.combine(hoje - timedelta(days=7), datetime.min.time())),
            data_conclusao=timezone.make_aware(datetime.combine(hoje - timedelta(days=5), datetime.min.time())),
        )
        ctx = build_cronograma_context(ordem, hoje=hoje)
        self.assertTrue(ctx['plano_tem_etapas'])
        self.assertIsNotNone(ctx['gantt_min_date'])
        self.assertIsNotNone(ctx['gantt_max_date'])
        self.assertEqual(len(ctx['cronograma_gantt']), 1)
        g = ctx['cronograma_gantt'][0]
        self.assertGreater(g['width_p'], 0, 'Barra prevista deve ter largura quando há prazo')
        self.assertGreater(g['width_a'], 0, 'Barra real deve ter largura quando há início e conclusão')
        self.assertEqual(len(ctx['gantt_ticks']), 5)
        self.assertIn('cronograma_atrasos', ctx)
        self.assertIn('progresso_etapas', ctx)
