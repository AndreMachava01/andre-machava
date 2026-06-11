from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from decimal import Decimal
from .models_stock import PropostaTecnica, ClienteServico, Sucursal
from .models_financas import PendenteContaReceber


class PropostasTecnicasTestCase(TestCase):
    """Testes para o módulo de Propostas Técnicas"""
    
    def setUp(self):
        """Configuração inicial dos testes"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        
        self.cliente = ClienteServico.objects.create(
            nome='Cliente Teste',
            telefone='+258 84 123 4567',
            email='cliente@teste.com'
        )
        
        self.sucursal = Sucursal.objects.create(
            nome='Sucursal Teste',
            endereco='Endereço Teste'
        )
        
        self.client.login(username='testuser', password='testpass123')
    
    def test_list_propostas_tecnicas(self):
        """Testa listagem de propostas técnicas"""
        response = self.client.get(reverse('producao:propostas_tecnicas'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Propostas Técnicas')
    
    def test_create_proposta_tecnica(self):
        """Testa criação de nova proposta técnica"""
        data = {
            'titulo': 'Proposta Teste',
            'escopo': 'Escopo da proposta teste',
            'cliente': self.cliente.id,
            'sucursal': self.sucursal.id,
            'responsavel': self.user.id,
            'data_inicio_prevista': '2024-01-01',
            'data_fim_prevista': '2024-01-07',
            'duracao_prevista_horas': '40.00',
            'valor_levantamento_previsto': '5000.00',
            'observacoes': 'Observações teste'
        }
        
        response = self.client.post(reverse('producao:proposta_tecnica_add'), data)
        self.assertEqual(response.status_code, 302)
        
        # Verifica se a proposta foi criada
        proposta = PropostaTecnica.objects.get(titulo='Proposta Teste')
        self.assertEqual(proposta.cliente, self.cliente)
        self.assertEqual(proposta.responsavel, self.user)
        self.assertEqual(proposta.valor_levantamento_previsto, Decimal('5000.00'))
        self.assertTrue(proposta.codigo.startswith('PT2024'))
    
    def test_proposta_tecnica_detail(self):
        """Testa visualização de detalhes da proposta"""
        proposta = PropostaTecnica.objects.create(
            titulo='Proposta Detalhe Teste',
            cliente=self.cliente,
            criado_por=self.user
        )
        
        response = self.client.get(reverse('producao:proposta_tecnica_detail', kwargs={'id': proposta.id}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, proposta.codigo)
        self.assertContains(response, proposta.titulo)
    
    def test_mudar_estagio_proposta(self):
        """Testa mudança de estágio da proposta"""
        proposta = PropostaTecnica.objects.create(
            titulo='Proposta Estágio Teste',
            cliente=self.cliente,
            estagio_atual='LEVANTAMENTO',
            criado_por=self.user
        )
        
        data = {'novo_estagio': 'ANALISE_TECNICA'}
        response = self.client.post(
            reverse('producao:proposta_tecnica_mudar_estagio', kwargs={'id': proposta.id}),
            data
        )
        
        self.assertEqual(response.status_code, 302)
        proposta.refresh_from_db()
        self.assertEqual(proposta.estagio_atual, 'ANALISE_TECNICA')
    
    def test_converter_proposta_em_orcamento(self):
        """Testa conversão de proposta em orçamento"""
        proposta = PropostaTecnica.objects.create(
            titulo='Proposta Converter Teste',
            cliente=self.cliente,
            estagio_atual='APROVACAO',
            valor_levantamento_previsto=Decimal('5000.00'),
            criado_por=self.user
        )
        
        response = self.client.post(reverse('producao:proposta_tecnica_converter_orcamento', kwargs={'id': proposta.id}))
        self.assertEqual(response.status_code, 302)
        
        # Verifica se o orçamento foi criado
        proposta.refresh_from_db()
        self.assertIsNotNone(proposta.orcamento_servico)
        self.assertEqual(proposta.orcamento_servico.titulo, proposta.titulo)
        self.assertEqual(proposta.orcamento_servico.cliente, proposta.cliente)
        
        # Verifica se o adiantamento foi criado
        adiantamento = PendenteContaReceber.objects.filter(
            origem_tipo='PROPOSTA_TECNICA',
            origem_id=proposta.id
        ).first()
        self.assertIsNotNone(adiantamento)
        self.assertEqual(adiantamento.valor, Decimal('5000.00'))
    
    def test_recibo_levantamento_pdf(self):
        """Testa geração de recibo de levantamento em PDF"""
        proposta = PropostaTecnica.objects.create(
            titulo='Proposta Recibo Teste',
            cliente=self.cliente,
            valor_levantamento_previsto=Decimal('5000.00'),
            criado_por=self.user
        )
        
        response = self.client.get(reverse('producao:proposta_tecnica_recibo_levantamento', kwargs={'id': proposta.id}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment', response['Content-Disposition'])
    
    def test_cronograma_page(self):
        """Testa página do cronograma (server-side)"""
        response = self.client.get(reverse('producao:propostas_tecnicas_cronograma'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Plano de trabalho', response.content)
        self.assertIn(b'Cronograma', response.content)

    def test_delete_proposta_tecnica(self):
        """Testa exclusão de proposta técnica"""
        proposta = PropostaTecnica.objects.create(
            titulo='Proposta Excluir Teste',
            cliente=self.cliente,
            criado_por=self.user
        )
        
        response = self.client.post(reverse('producao:proposta_tecnica_delete', kwargs={'id': proposta.id}))
        self.assertEqual(response.status_code, 302)
        
        # Verifica se a proposta foi excluída
        with self.assertRaises(PropostaTecnica.DoesNotExist):
            PropostaTecnica.objects.get(id=proposta.id)
    
    def test_status_automatico_atrasada(self):
        """Testa atualização automática de status para atrasada"""
        data_passada = timezone.now().date() - timezone.timedelta(days=10)
        
        proposta = PropostaTecnica.objects.create(
            titulo='Proposta Atrasada Teste',
            cliente=self.cliente,
            data_fim_prevista=data_passada,
            criado_por=self.user
        )
        
        # O status deve ser atualizado automaticamente para ATRASADA
        proposta.refresh_from_db()
        self.assertTrue(proposta.esta_atrasada)
        self.assertEqual(proposta.status, 'ATRASADA')
    
    def test_codigo_automatico(self):
        """Testa geração automática de código"""
        proposta1 = PropostaTecnica.objects.create(
            titulo='Proposta Código 1',
            cliente=self.cliente,
            criado_por=self.user
        )
        
        proposta2 = PropostaTecnica.objects.create(
            titulo='Proposta Código 2',
            cliente=self.cliente,
            criado_por=self.user
        )
        
        self.assertTrue(proposta1.codigo.startswith('PT2024'))
        self.assertTrue(proposta2.codigo.startswith('PT2024'))
        self.assertNotEqual(proposta1.codigo, proposta2.codigo)


class PropostasTecnicasIntegrationTestCase(TestCase):
    """Testes de integração para o módulo de Propostas Técnicas"""
    
    def setUp(self):
        """Configuração inicial dos testes de integração"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='integrationuser',
            email='integration@example.com',
            password='testpass123'
        )
        
        self.cliente = ClienteServico.objects.create(
            nome='Cliente Integração',
            email='integracao@teste.com'
        )
        
        self.client.login(username='integrationuser', password='testpass123')
    
    def test_fluxo_completo_proposta(self):
        """Testa fluxo completo: criação -> estágios -> conversão -> orçamento"""
        # 1. Criar proposta
        data = {
            'titulo': 'Proposta Fluxo Completo',
            'cliente': self.cliente.id,
            'valor_levantamento_previsto': '10000.00',
            'data_inicio_prevista': '2024-01-01',
            'data_fim_prevista': '2024-01-07'
        }
        
        response = self.client.post(reverse('producao:proposta_tecnica_add'), data)
        self.assertEqual(response.status_code, 302)
        
        proposta = PropostaTecnica.objects.get(titulo='Proposta Fluxo Completo')
        
        # 2. Avançar estágios
        estagios = ['ANALISE_TECNICA', 'ELABORACAO_PROPOSTA', 'APRESENTACAO', 'APROVACAO']
        
        for estagio in estagios:
            response = self.client.post(
                reverse('producao:proposta_tecnica_mudar_estagio', kwargs={'id': proposta.id}),
                {'novo_estagio': estagio}
            )
            self.assertEqual(response.status_code, 302)
            
            proposta.refresh_from_db()
            self.assertEqual(proposta.estagio_atual, estagio)
        
        # 3. Converter em orçamento
        response = self.client.post(
            reverse('producao:proposta_tecnica_converter_orcamento', kwargs={'id': proposta.id})
        )
        self.assertEqual(response.status_code, 302)
        
        # 4. Verificar resultados
        proposta.refresh_from_db()
        self.assertIsNotNone(proposta.orcamento_servico)
        self.assertEqual(proposta.status, 'CONCLUIDA')
        
        # 5. Verificar adiantamento financeiro
        adiantamento = PendenteContaReceber.objects.filter(
            origem_tipo='PROPOSTA_TECNICA',
            origem_id=proposta.id
        ).first()
        self.assertIsNotNone(adiantamento)
        self.assertEqual(adiantamento.valor, Decimal('10000.00'))
    
    def test_filtros_lista_propostas(self):
        """Testa filtros na lista de propostas"""
        # Criar propostas com diferentes características
        PropostaTecnica.objects.create(
            titulo='Proposta Disponível',
            cliente=self.cliente,
            status='DISPONIVEL',
            estagio_atual='LEVANTAMENTO',
            criado_por=self.user
        )
        
        PropostaTecnica.objects.create(
            titulo='Proposta Em Andamento',
            cliente=self.cliente,
            status='EM_ANDAMENTO',
            estagio_atual='ANALISE_TECNICA',
            criado_por=self.user
        )
        
        # Testar filtro por status
        response = self.client.get(reverse('producao:propostas_tecnicas') + '?status=DISPONIVEL')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Proposta Disponível')
        self.assertNotContains(response, 'Proposta Em Andamento')
        
        # Testar filtro por estágio
        response = self.client.get(reverse('producao:propostas_tecnicas') + '?estagio=ANALISE_TECNICA')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Proposta Em Andamento')
        self.assertNotContains(response, 'Proposta Disponível')
