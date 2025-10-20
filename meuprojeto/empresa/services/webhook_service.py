"""
Serviço de webhooks para integração com transportadoras.
"""
import json
import logging
import hashlib
import hmac
from typing import Dict, Any, Optional
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views import View
from django.conf import settings

from ..models_stock import RastreamentoEntrega, EventoRastreamento, Transportadora
from .logistica_sync import sincronizar_rastreamento_com_notificacao

logger = logging.getLogger(__name__)


class WebhookService:
    """Serviço para processar webhooks de transportadoras."""
    
    def __init__(self):
        self.webhook_secrets = self._load_webhook_secrets()
    
    def _load_webhook_secrets(self) -> Dict[str, str]:
        """Carrega segredos de webhook das variáveis de ambiente."""
        return {
            'correios': getattr(settings, 'CORREIOS_WEBHOOK_SECRET', ''),
            'dhl': getattr(settings, 'DHL_WEBHOOK_SECRET', ''),
            'local': getattr(settings, 'LOCAL_CARRIER_WEBHOOK_SECRET', ''),
        }
    
    def verify_signature(self, payload: str, signature: str, carrier: str) -> bool:
        """
        Verifica a assinatura do webhook.
        
        Args:
            payload: Corpo da requisição
            signature: Assinatura recebida
            carrier: Nome da transportadora
            
        Returns:
            bool: True se a assinatura for válida
        """
        secret = self.webhook_secrets.get(carrier)
        if not secret:
            logger.warning(f"Segredo não configurado para {carrier}")
            return False
        
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
    
    def process_tracking_update(self, carrier: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processa atualização de rastreamento de transportadora.
        
        Args:
            carrier: Nome da transportadora
            data: Dados do webhook
            
        Returns:
            Dict com resultado do processamento
        """
        try:
            tracking_code = data.get('tracking_code')
            if not tracking_code:
                return {'success': False, 'error': 'tracking_code é obrigatório'}
            
            # Buscar rastreamento existente
            try:
                rastreamento = RastreamentoEntrega.objects.get(
                    codigo_rastreamento=tracking_code,
                    transportadora__nome__iexact=carrier
                )
            except RastreamentoEntrega.DoesNotExist:
                logger.warning(f"Rastreamento não encontrado: {tracking_code} - {carrier}")
                return {'success': False, 'error': 'Rastreamento não encontrado'}
            
            # Atualizar status se fornecido
            new_status = data.get('status')
            if new_status:
                old_status = rastreamento.status_atual
                rastreamento.status_atual = new_status
                rastreamento.save()
                
                # Criar evento de rastreamento
                EventoRastreamento.objects.create(
                    rastreamento=rastreamento,
                    status_anterior=old_status,
                    status_atual=new_status,
                    data_evento=data.get('event_date'),
                    localizacao=data.get('location', ''),
                    observacoes=data.get('description', ''),
                    origem_evento='WEBHOOK'
                )
                
                logger.info(f"Status atualizado via webhook: {tracking_code} - {old_status} -> {new_status}")
            
            # Sincronizar com notificações se necessário
            if hasattr(rastreamento, 'notificacao'):
                sincronizar_rastreamento_com_notificacao(rastreamento.notificacao)
            
            return {
                'success': True,
                'tracking_code': tracking_code,
                'status': rastreamento.status_atual
            }
            
        except Exception as e:
            logger.error(f"Erro ao processar webhook de rastreamento: {e}")
            return {'success': False, 'error': str(e)}
    
    def process_pickup_confirmation(self, carrier: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processa confirmação de coleta.
        
        Args:
            carrier: Nome da transportadora
            data: Dados do webhook
            
        Returns:
            Dict com resultado do processamento
        """
        try:
            tracking_code = data.get('tracking_code')
            if not tracking_code:
                return {'success': False, 'error': 'tracking_code é obrigatório'}
            
            # Buscar rastreamento
            try:
                rastreamento = RastreamentoEntrega.objects.get(
                    codigo_rastreamento=tracking_code,
                    transportadora__nome__iexact=carrier
                )
            except RastreamentoEntrega.DoesNotExist:
                return {'success': False, 'error': 'Rastreamento não encontrado'}
            
            # Atualizar para status de coleta confirmada
            rastreamento.status_atual = 'COLETADO'
            rastreamento.save()
            
            # Criar evento
            EventoRastreamento.objects.create(
                rastreamento=rastreamento,
                status_anterior=rastreamento.status_atual,
                status_atual='COLETADO',
                data_evento=data.get('pickup_date'),
                localizacao=data.get('pickup_location', ''),
                observacoes=f"Coleta confirmada pela transportadora {carrier}",
                origem_evento='WEBHOOK'
            )
            
            logger.info(f"Coleta confirmada via webhook: {tracking_code}")
            
            return {
                'success': True,
                'tracking_code': tracking_code,
                'status': 'COLETADO'
            }
            
        except Exception as e:
            logger.error(f"Erro ao processar confirmação de coleta: {e}")
            return {'success': False, 'error': str(e)}
    
    def process_delivery_confirmation(self, carrier: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processa confirmação de entrega.
        
        Args:
            carrier: Nome da transportadora
            data: Dados do webhook
            
        Returns:
            Dict com resultado do processamento
        """
        try:
            tracking_code = data.get('tracking_code')
            if not tracking_code:
                return {'success': False, 'error': 'tracking_code é obrigatório'}
            
            # Buscar rastreamento
            try:
                rastreamento = RastreamentoEntrega.objects.get(
                    codigo_rastreamento=tracking_code,
                    transportadora__nome__iexact=carrier
                )
            except RastreamentoEntrega.DoesNotExist:
                return {'success': False, 'error': 'Rastreamento não encontrado'}
            
            # Atualizar para entregue
            rastreamento.status_atual = 'ENTREGUE'
            rastreamento.data_entrega = data.get('delivery_date')
            rastreamento.save()
            
            # Criar evento
            EventoRastreamento.objects.create(
                rastreamento=rastreamento,
                status_anterior=rastreamento.status_atual,
                status_atual='ENTREGUE',
                data_evento=data.get('delivery_date'),
                localizacao=data.get('delivery_location', ''),
                observacoes=f"Entrega confirmada pela transportadora {carrier}",
                origem_evento='WEBHOOK'
            )
            
            logger.info(f"Entrega confirmada via webhook: {tracking_code}")
            
            return {
                'success': True,
                'tracking_code': tracking_code,
                'status': 'ENTREGUE'
            }
            
        except Exception as e:
            logger.error(f"Erro ao processar confirmação de entrega: {e}")
            return {'success': False, 'error': str(e)}
    
    def process_exception(self, carrier: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processa exceções (problemas na entrega).
        
        Args:
            carrier: Nome da transportadora
            data: Dados do webhook
            
        Returns:
            Dict com resultado do processamento
        """
        try:
            tracking_code = data.get('tracking_code')
            if not tracking_code:
                return {'success': False, 'error': 'tracking_code é obrigatório'}
            
            # Buscar rastreamento
            try:
                rastreamento = RastreamentoEntrega.objects.get(
                    codigo_rastreamento=tracking_code,
                    transportadora__nome__iexact=carrier
                )
            except RastreamentoEntrega.DoesNotExist:
                return {'success': False, 'error': 'Rastreamento não encontrado'}
            
            exception_type = data.get('exception_type', 'PROBLEMA')
            rastreamento.status_atual = exception_type
            rastreamento.save()
            
            # Criar evento
            EventoRastreamento.objects.create(
                rastreamento=rastreamento,
                status_anterior=rastreamento.status_atual,
                status_atual=exception_type,
                data_evento=data.get('exception_date'),
                localizacao=data.get('location', ''),
                observacoes=data.get('description', f"Exceção reportada pela transportadora {carrier}"),
                origem_evento='WEBHOOK'
            )
            
            logger.info(f"Exceção processada via webhook: {tracking_code} - {exception_type}")
            
            return {
                'success': True,
                'tracking_code': tracking_code,
                'status': exception_type
            }
            
        except Exception as e:
            logger.error(f"Erro ao processar exceção: {e}")
            return {'success': False, 'error': str(e)}


# Instância global do serviço
webhook_service = WebhookService()


@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(require_http_methods(["POST"]), name='dispatch')
class CarrierWebhookView(View):
    """View para receber webhooks de transportadoras."""
    
    def post(self, request: HttpRequest, carrier_name: str):
        """
        Processa webhook de transportadora.
        
        Args:
            request: Requisição HTTP
            carrier_name: Nome da transportadora
            
        Returns:
            JsonResponse com resultado do processamento
        """
        try:
            # Verificar se a transportadora é suportada
            supported_carriers = ['correios', 'dhl', 'local']
            if carrier_name.lower() not in supported_carriers:
                return JsonResponse({
                    'success': False,
                    'error': f'Transportadora não suportada: {carrier_name}'
                }, status=400)
            
            # Obter dados do webhook
            try:
                payload = request.body.decode('utf-8')
                data = json.loads(payload)
            except (UnicodeDecodeError, json.JSONDecodeError) as e:
                logger.error(f"Erro ao decodificar payload do webhook: {e}")
                return JsonResponse({
                    'success': False,
                    'error': 'Payload inválido'
                }, status=400)
            
            # Verificar assinatura se configurada
            signature = request.headers.get('X-Signature', '')
            if signature and not webhook_service.verify_signature(payload, signature, carrier_name.lower()):
                logger.warning(f"Assinatura inválida para webhook de {carrier_name}")
                return JsonResponse({
                    'success': False,
                    'error': 'Assinatura inválida'
                }, status=401)
            
            # Processar webhook baseado no tipo
            webhook_type = data.get('type', 'tracking_update')
            
            if webhook_type == 'tracking_update':
                result = webhook_service.process_tracking_update(carrier_name.lower(), data)
            elif webhook_type == 'pickup_confirmation':
                result = webhook_service.process_pickup_confirmation(carrier_name.lower(), data)
            elif webhook_type == 'delivery_confirmation':
                result = webhook_service.process_delivery_confirmation(carrier_name.lower(), data)
            elif webhook_type == 'exception':
                result = webhook_service.process_exception(carrier_name.lower(), data)
            else:
                return JsonResponse({
                    'success': False,
                    'error': f'Tipo de webhook não suportado: {webhook_type}'
                }, status=400)
            
            # Retornar resultado
            status_code = 200 if result['success'] else 400
            return JsonResponse(result, status=status_code)
            
        except Exception as e:
            logger.error(f"Erro geral no webhook de {carrier_name}: {e}")
            return JsonResponse({
                'success': False,
                'error': 'Erro interno do servidor'
            }, status=500)
