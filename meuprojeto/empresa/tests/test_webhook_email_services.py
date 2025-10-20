"""
Testes para os serviços de webhook e email.
"""
import json
from unittest.mock import patch, MagicMock
from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User
from django.http import JsonResponse

from ..models_stock import Transportadora, RastreamentoEntrega, EventoRastreamento
from ..services.webhook_service import WebhookService, CarrierWebhookView
from ..services.email_service import EmailNotificationService


class WebhookServiceTests(TestCase):
    """Testes para o serviço de webhook."""
    
    def setUp(self):
        """Configuração inicial dos testes."""
        self.webhook_service = WebhookService()
        
        # Criar transportadora de teste
        self.transportadora = Transportadora.objects.create(
            nome='Test Carrier',
            codigo='TEST001',
            tipo='TRANSPORTADORA',
            status='ATIVO'
        )
        
        # Criar rastreamento de teste
        self.rastreamento = RastreamentoEntrega.objects.create(
            codigo_rastreamento='TEST123',
            transportadora=self.transportadora,
            status_atual='PENDENTE'
        )
    
    def test_verify_signature_valid(self):
        """Testa verificação de assinatura válida."""
        payload = '{"test": "data"}'
        secret = 'test_secret'
        
        # Simular configuração de segredo
        with patch.object(self.webhook_service, 'webhook_secrets', {'test': secret}):
            import hmac
            import hashlib
            
            signature = hmac.new(
                secret.encode('utf-8'),
                payload.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            result = self.webhook_service.verify_signature(payload, signature, 'test')
            self.assertTrue(result)
    
    def test_verify_signature_invalid(self):
        """Testa verificação de assinatura inválida."""
        payload = '{"test": "data"}'
        signature = 'invalid_signature'
        
        with patch.object(self.webhook_service, 'webhook_secrets', {'test': 'secret'}):
            result = self.webhook_service.verify_signature(payload, signature, 'test')
            self.assertFalse(result)
    
    def test_process_tracking_update_success(self):
        """Testa processamento de atualização de rastreamento com sucesso."""
        data = {
            'tracking_code': 'TEST123',
            'status': 'EM_TRANSITO',
            'event_date': '2024-01-01T10:00:00Z',
            'location': 'Maputo',
            'description': 'Em trânsito para destino'
        }
        
        result = self.webhook_service.process_tracking_update('test carrier', data)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['tracking_code'], 'TEST123')
        self.assertEqual(result['status'], 'EM_TRANSITO')
        
        # Verificar se o evento foi criado
        evento = EventoRastreamento.objects.filter(
            rastreamento=self.rastreamento
        ).first()
        self.assertIsNotNone(evento)
        self.assertEqual(evento.status_atual, 'EM_TRANSITO')
    
    def test_process_tracking_update_not_found(self):
        """Testa processamento quando rastreamento não é encontrado."""
        data = {
            'tracking_code': 'NOTFOUND',
            'status': 'EM_TRANSITO'
        }
        
        result = self.webhook_service.process_tracking_update('test carrier', data)
        
        self.assertFalse(result['success'])
        self.assertIn('não encontrado', result['error'])
    
    def test_process_pickup_confirmation(self):
        """Testa confirmação de coleta."""
        data = {
            'tracking_code': 'TEST123',
            'pickup_date': '2024-01-01T08:00:00Z',
            'pickup_location': 'Centro de Distribuição'
        }
        
        result = self.webhook_service.process_pickup_confirmation('test carrier', data)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['status'], 'COLETADO')
        
        # Verificar se o status foi atualizado
        self.rastreamento.refresh_from_db()
        self.assertEqual(self.rastreamento.status_atual, 'COLETADO')
    
    def test_process_delivery_confirmation(self):
        """Testa confirmação de entrega."""
        data = {
            'tracking_code': 'TEST123',
            'delivery_date': '2024-01-02T14:00:00Z',
            'delivery_location': 'Casa do Cliente'
        }
        
        result = self.webhook_service.process_delivery_confirmation('test carrier', data)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['status'], 'ENTREGUE')
        
        # Verificar se o status foi atualizado
        self.rastreamento.refresh_from_db()
        self.assertEqual(self.rastreamento.status_atual, 'ENTREGUE')
    
    def test_process_exception(self):
        """Testa processamento de exceção."""
        data = {
            'tracking_code': 'TEST123',
            'exception_type': 'TENTATIVA_ENTREGA',
            'exception_date': '2024-01-02T10:00:00Z',
            'location': 'Endereço do Cliente',
            'description': 'Cliente não estava presente'
        }
        
        result = self.webhook_service.process_exception('test carrier', data)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['status'], 'TENTATIVA_ENTREGA')
        
        # Verificar se o status foi atualizado
        self.rastreamento.refresh_from_db()
        self.assertEqual(self.rastreamento.status_atual, 'TENTATIVA_ENTREGA')


class CarrierWebhookViewTests(TestCase):
    """Testes para a view de webhook de transportadora."""
    
    def setUp(self):
        """Configuração inicial dos testes."""
        self.factory = RequestFactory()
        self.view = CarrierWebhookView()
        
        # Criar transportadora de teste
        self.transportadora = Transportadora.objects.create(
            nome='Test Carrier',
            codigo='TEST001',
            tipo='TRANSPORTADORA',
            status='ATIVO'
        )
        
        # Criar rastreamento de teste
        self.rastreamento = RastreamentoEntrega.objects.create(
            codigo_rastreamento='TEST123',
            transportadora=self.transportadora,
            status_atual='PENDENTE'
        )
    
    def test_post_tracking_update_success(self):
        """Testa POST com atualização de rastreamento bem-sucedida."""
        data = {
            'type': 'tracking_update',
            'tracking_code': 'TEST123',
            'status': 'EM_TRANSITO',
            'event_date': '2024-01-01T10:00:00Z',
            'location': 'Maputo'
        }
        
        request = self.factory.post(
            '/webhook/test/',
            data=json.dumps(data),
            content_type='application/json'
        )
        
        with patch.object(WebhookService, 'verify_signature', return_value=True):
            response = self.view.post(request, 'test')
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
    
    def test_post_invalid_carrier(self):
        """Testa POST com transportadora não suportada."""
        data = {'type': 'tracking_update'}
        
        request = self.factory.post(
            '/webhook/invalid/',
            data=json.dumps(data),
            content_type='application/json'
        )
        
        response = self.view.post(request, 'invalid')
        
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertFalse(response_data['success'])
        self.assertIn('não suportada', response_data['error'])
    
    def test_post_invalid_json(self):
        """Testa POST com JSON inválido."""
        request = self.factory.post(
            '/webhook/test/',
            data='invalid json',
            content_type='application/json'
        )
        
        response = self.view.post(request, 'test')
        
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertFalse(response_data['success'])
        self.assertEqual(response_data['error'], 'Payload inválido')
    
    def test_post_invalid_signature(self):
        """Testa POST com assinatura inválida."""
        data = {'type': 'tracking_update'}
        
        request = self.factory.post(
            '/webhook/test/',
            data=json.dumps(data),
            content_type='application/json'
        )
        request.headers = {'X-Signature': 'invalid_signature'}
        
        with patch.object(WebhookService, 'verify_signature', return_value=False):
            response = self.view.post(request, 'test')
        
        self.assertEqual(response.status_code, 401)
        response_data = json.loads(response.content)
        self.assertFalse(response_data['success'])
        self.assertEqual(response_data['error'], 'Assinatura inválida')


class EmailNotificationServiceTests(TestCase):
    """Testes para o serviço de notificação por email."""
    
    def setUp(self):
        """Configuração inicial dos testes."""
        self.email_service = EmailNotificationService()
    
    @patch('meuprojeto.empresa.services.email_service.send_mail')
    def test_send_tracking_update_success(self, mock_send_mail):
        """Testa envio de notificação de rastreamento com sucesso."""
        mock_send_mail.return_value = True
        
        result = self.email_service.send_tracking_update(
            recipient_email='test@example.com',
            tracking_code='TEST123',
            status='EM_TRANSITO',
            location='Maputo',
            estimated_delivery='2024-01-02'
        )
        
        self.assertTrue(result)
        mock_send_mail.assert_called_once()
        
        # Verificar argumentos da chamada
        call_args = mock_send_mail.call_args
        self.assertEqual(call_args[1]['subject'], 'Atualização de Rastreamento - TEST123')
        self.assertIn('test@example.com', call_args[1]['recipient_list'])
    
    @patch('meuprojeto.empresa.services.email_service.send_mail')
    def test_send_delivery_confirmation_success(self, mock_send_mail):
        """Testa envio de confirmação de entrega com sucesso."""
        mock_send_mail.return_value = True
        
        result = self.email_service.send_delivery_confirmation(
            recipient_email='test@example.com',
            tracking_code='TEST123',
            delivery_date='2024-01-02',
            signature_name='João Silva'
        )
        
        self.assertTrue(result)
        mock_send_mail.assert_called_once()
        
        # Verificar argumentos da chamada
        call_args = mock_send_mail.call_args
        self.assertEqual(call_args[1]['subject'], 'Entrega Confirmada - TEST123')
    
    @patch('meuprojeto.empresa.services.email_service.send_mail')
    def test_send_delay_notification_success(self, mock_send_mail):
        """Testa envio de notificação de atraso com sucesso."""
        mock_send_mail.return_value = True
        
        result = self.email_service.send_delay_notification(
            recipient_email='test@example.com',
            tracking_code='TEST123',
            original_date='2024-01-01',
            new_date='2024-01-03',
            reason='Problemas de trânsito'
        )
        
        self.assertTrue(result)
        mock_send_mail.assert_called_once()
        
        # Verificar argumentos da chamada
        call_args = mock_send_mail.call_args
        self.assertEqual(call_args[1]['subject'], 'Atraso na Entrega - TEST123')
    
    @patch('meuprojeto.empresa.services.email_service.send_mail')
    def test_send_email_failure(self, mock_send_mail):
        """Testa falha no envio de email."""
        mock_send_mail.side_effect = Exception('SMTP Error')
        
        result = self.email_service.send_tracking_update(
            recipient_email='test@example.com',
            tracking_code='TEST123',
            status='EM_TRANSITO'
        )
        
        self.assertFalse(result)
    
    def test_send_bulk_notifications(self):
        """Testa envio de notificações em lote."""
        notifications = [
            {
                'type': 'tracking_update',
                'data': {
                    'recipient_email': 'test1@example.com',
                    'tracking_code': 'TEST001',
                    'status': 'EM_TRANSITO'
                }
            },
            {
                'type': 'delivery_confirmation',
                'data': {
                    'recipient_email': 'test2@example.com',
                    'tracking_code': 'TEST002',
                    'delivery_date': '2024-01-02'
                }
            }
        ]
        
        with patch.object(self.email_service, 'send_tracking_update', return_value=True), \
             patch.object(self.email_service, 'send_delivery_confirmation', return_value=True):
            
            results = self.email_service.send_bulk_notifications(notifications)
        
        self.assertEqual(results['success'], 2)
        self.assertEqual(results['failed'], 0)
    
    def test_generate_plain_text_tracking_update(self):
        """Testa geração de texto simples para atualização de rastreamento."""
        context = {
            'tracking_code': 'TEST123',
            'status': 'EM_TRANSITO',
            'location': 'Maputo',
            'estimated_delivery': '2024-01-02',
            'company_name': 'Test Company'
        }
        
        result = self.email_service._generate_plain_text_tracking_update(context)
        
        self.assertIn('TEST123', result)
        self.assertIn('EM_TRANSITO', result)
        self.assertIn('Maputo', result)
        self.assertIn('2024-01-02', result)
