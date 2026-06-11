from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from decimal import Decimal
from meuprojeto.empresa.models_stock import OrdemServico, ClienteServico
from meuprojeto.empresa.models_base import FormaPagamento, PeriodoPagamento

User = get_user_model()


class EditarContratoViewTests(TestCase):
    """Testes para a view de edição de contrato"""
    
    def setUp(self):
        """Configuração inicial para os testes"""
        self.client = Client()
        
        # Criar usuário
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')
        
        # Criar cliente
        self.cliente = ClienteServico.objects.create(
            nome='Cliente Teste',
            nuit='123456789',
            telefone='841234567',
            endereco='Endereço Teste',
            cidade='Maputo'
        )
        
        # Criar orçamento (cotação)
        self.orcamento = OrdemServico.objects.create(
            codigo='COT-2026-000001',
            cliente=self.cliente,
            data_agendada='2026-02-10 08:00:00',
            endereco_servico='Endereço do Serviço',
            cidade_servico='Maputo',
            status='AGENDADA',
            prioridade='NORMAL',
            quantidade=Decimal('1.00'),
            valor_total=Decimal('1000.00'),
            validade_garantia_dias=90,
            criado_por=self.user
        )
    
    def test_editar_contrato_page_accessible(self):
        """Testa se a página de edição do contrato é acessível"""
        url = reverse('producao:editar_contrato_servico', args=[self.orcamento.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Editar Cláusulas do Contrato')
        self.assertContains(response, self.orcamento.codigo)
    
    def test_editar_contrato_has_editor_fields(self):
        """Testa se os campos de edição estão presentes na página"""
        url = reverse('producao:editar_contrato_servico', args=[self.orcamento.id])
        response = self.client.get(url)
        
        # Verificar se os campos de cláusulas estão presentes
        self.assertContains(response, 'clausula4_obrigacoes')
        self.assertContains(response, 'clausula5_garantia')
        self.assertContains(response, 'clausula6_alteracoes')
        self.assertContains(response, 'clausula7_rescisao')
        self.assertContains(response, 'clausula8_confidencialidade')
        self.assertContains(response, 'clausula9_foro')
        
        # Verificar se os editores Quill estão presentes
        self.assertContains(response, 'editor-clausula4')
        self.assertContains(response, 'editor-clausula5')
        self.assertContains(response, 'editor-clausula6')
        self.assertContains(response, 'editor-clausula7')
        self.assertContains(response, 'editor-clausula8')
        self.assertContains(response, 'editor-clausula9')
    
    def test_save_clausulas_contrato(self):
        """Testa se é possível salvar as cláusulas editadas"""
        url = reverse('producao:editar_contrato_servico', args=[self.orcamento.id])
        
        # Dados de teste para as cláusulas
        clausula4_texto = '<p><strong>Da CONTRATADA:</strong></p><p>Executar serviços com qualidade.</p>'
        clausula5_texto = '<p>Garantia de 90 dias.</p>'
        
        response = self.client.post(url, {
            'clausula4_obrigacoes': clausula4_texto,
            'clausula5_garantia': clausula5_texto,
            'clausula6_alteracoes': '<p>Alterações por escrito.</p>',
            'clausula7_rescisao': '<p>Rescisão por acordo.</p>',
            'clausula8_confidencialidade': '<p>Mantém sigilo.</p>',
            'clausula9_foro': '<p>Foro de Maputo.</p>',
            'acao': 'salvar'
        })
        
        # Verificar redirecionamento após salvar
        self.assertEqual(response.status_code, 302)
        
        # Recarregar o orçamento do banco
        self.orcamento.refresh_from_db()
        
        # Verificar se as cláusulas foram salvas
        self.assertEqual(self.orcamento.clausula4_obrigacoes, clausula4_texto)
        self.assertEqual(self.orcamento.clausula5_garantia, clausula5_texto)
    
    def test_editar_contrato_blocked_after_confirmation(self):
        """Testa se a edição é bloqueada após confirmação do serviço"""
        # Criar ordem de serviço a partir do orçamento (simular confirmação)
        ordem_servico = OrdemServico.objects.create(
            codigo='OS-2026-000001',
            orcamento_origem=self.orcamento,
            cliente=self.cliente,
            data_agendada='2026-02-10 08:00:00',
            endereco_servico='Endereço do Serviço',
            cidade_servico='Maputo',
            status='EM_ANDAMENTO',
            prioridade='NORMAL',
            quantidade=Decimal('1.00'),
            valor_total=Decimal('1000.00'),
            criado_por=self.user
        )
        
        url = reverse('producao:editar_contrato_servico', args=[self.orcamento.id])
        response = self.client.get(url)
        
        # Deve redirecionar com mensagem de erro
        self.assertEqual(response.status_code, 302)
        self.assertIn(ordem_servico.codigo, str(response.url))
    
    def test_preview_after_save(self):
        """Testa se é possível pré-visualizar após salvar"""
        url = reverse('producao:editar_contrato_servico', args=[self.orcamento.id])
        
        response = self.client.post(url, {
            'clausula4_obrigacoes': '<p>Teste de obrigações.</p>',
            'clausula5_garantia': '<p>Garantia de 90 dias.</p>',
            'clausula6_alteracoes': '',
            'clausula7_rescisao': '',
            'clausula8_confidencialidade': '',
            'clausula9_foro': '',
            'acao': 'preview'
        })
        
        # Deve redirecionar para preview
        self.assertEqual(response.status_code, 302)
        self.assertIn('preview-contrato', response.url)
