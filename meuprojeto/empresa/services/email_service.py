"""
Serviço de notificações por email interno para logística.
"""
import logging
from typing import Dict, List, Optional
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


class EmailNotificationService:
    """Serviço para envio de notificações por email."""
    
    def __init__(self):
        self.from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@empresa.com')
        self.template_dir = 'stock/logistica/emails'
    
    def send_tracking_update(self, 
                           recipient_email: str,
                           tracking_code: str,
                           status: str,
                           location: Optional[str] = None,
                           estimated_delivery: Optional[str] = None) -> bool:
        """
        Envia notificação de atualização de rastreamento.
        
        Args:
            recipient_email: Email do destinatário
            tracking_code: Código de rastreamento
            status: Status atual da entrega
            location: Localização atual (opcional)
            estimated_delivery: Data estimada de entrega (opcional)
            
        Returns:
            bool: True se enviado com sucesso
        """
        try:
            subject = f"Atualização de Rastreamento - {tracking_code}"
            
            context = {
                'tracking_code': tracking_code,
                'status': status,
                'location': location,
                'estimated_delivery': estimated_delivery,
                'company_name': getattr(settings, 'COMPANY_NAME', 'Empresa')
            }
            
            # Renderizar template HTML
            html_message = render_to_string(
                f'{self.template_dir}/tracking_update.html',
                context
            )
            
            # Versão texto simples
            plain_message = self._generate_plain_text_tracking_update(context)
            
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=self.from_email,
                recipient_list=[recipient_email],
                html_message=html_message,
                fail_silently=False
            )
            
            logger.info(f"Email de rastreamento enviado para {recipient_email} - {tracking_code}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao enviar email de rastreamento: {e}")
            return False
    
    def send_delivery_confirmation(self,
                                 recipient_email: str,
                                 tracking_code: str,
                                 delivery_date: str,
                                 signature_name: Optional[str] = None) -> bool:
        """
        Envia confirmação de entrega.
        
        Args:
            recipient_email: Email do destinatário
            tracking_code: Código de rastreamento
            delivery_date: Data da entrega
            signature_name: Nome de quem assinou (opcional)
            
        Returns:
            bool: True se enviado com sucesso
        """
        try:
            subject = f"Entrega Confirmada - {tracking_code}"
            
            context = {
                'tracking_code': tracking_code,
                'delivery_date': delivery_date,
                'signature_name': signature_name,
                'company_name': getattr(settings, 'COMPANY_NAME', 'Empresa')
            }
            
            html_message = render_to_string(
                f'{self.template_dir}/delivery_confirmation.html',
                context
            )
            
            plain_message = self._generate_plain_text_delivery_confirmation(context)
            
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=self.from_email,
                recipient_list=[recipient_email],
                html_message=html_message,
                fail_silently=False
            )
            
            logger.info(f"Email de confirmação de entrega enviado para {recipient_email} - {tracking_code}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao enviar email de confirmação de entrega: {e}")
            return False
    
    def send_delay_notification(self,
                              recipient_email: str,
                              tracking_code: str,
                              original_date: str,
                              new_date: str,
                              reason: Optional[str] = None) -> bool:
        """
        Envia notificação de atraso.
        
        Args:
            recipient_email: Email do destinatário
            tracking_code: Código de rastreamento
            original_date: Data original de entrega
            new_date: Nova data estimada
            reason: Motivo do atraso (opcional)
            
        Returns:
            bool: True se enviado com sucesso
        """
        try:
            subject = f"Atraso na Entrega - {tracking_code}"
            
            context = {
                'tracking_code': tracking_code,
                'original_date': original_date,
                'new_date': new_date,
                'reason': reason,
                'company_name': getattr(settings, 'COMPANY_NAME', 'Empresa')
            }
            
            html_message = render_to_string(
                f'{self.template_dir}/delay_notification.html',
                context
            )
            
            plain_message = self._generate_plain_text_delay_notification(context)
            
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=self.from_email,
                recipient_list=[recipient_email],
                html_message=html_message,
                fail_silently=False
            )
            
            logger.info(f"Email de atraso enviado para {recipient_email} - {tracking_code}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao enviar email de atraso: {e}")
            return False
    
    def send_bulk_notifications(self, notifications: List[Dict]) -> Dict[str, int]:
        """
        Envia múltiplas notificações em lote.
        
        Args:
            notifications: Lista de dicionários com dados das notificações
            
        Returns:
            Dict com contadores de sucesso e falha
        """
        results = {'success': 0, 'failed': 0}
        
        for notification in notifications:
            notification_type = notification.get('type')
            
            if notification_type == 'tracking_update':
                success = self.send_tracking_update(**notification.get('data', {}))
            elif notification_type == 'delivery_confirmation':
                success = self.send_delivery_confirmation(**notification.get('data', {}))
            elif notification_type == 'delay_notification':
                success = self.send_delay_notification(**notification.get('data', {}))
            else:
                logger.warning(f"Tipo de notificação desconhecido: {notification_type}")
                success = False
            
            if success:
                results['success'] += 1
            else:
                results['failed'] += 1
        
        logger.info(f"Envio em lote concluído: {results['success']} sucessos, {results['failed']} falhas")
        return results
    
    def _generate_plain_text_tracking_update(self, context: Dict) -> str:
        """Gera versão texto simples da notificação de rastreamento."""
        return f"""
Atualização de Rastreamento - {context['tracking_code']}

Status: {context['status']}
{f"Localização: {context['location']}" if context.get('location') else ""}
{f"Entrega estimada: {context['estimated_delivery']}" if context.get('estimated_delivery') else ""}

Acompanhe seu pedido em: {getattr(settings, 'TRACKING_URL', 'https://empresa.com/rastreamento')}

{context['company_name']}
        """.strip()
    
    def _generate_plain_text_delivery_confirmation(self, context: Dict) -> str:
        """Gera versão texto simples da confirmação de entrega."""
        return f"""
Entrega Confirmada - {context['tracking_code']}

Sua entrega foi realizada com sucesso em {context['delivery_date']}.
{f"Assinado por: {context['signature_name']}" if context.get('signature_name') else ""}

Obrigado por escolher {context['company_name']}!
        """.strip()
    
    def _generate_plain_text_delay_notification(self, context: Dict) -> str:
        """Gera versão texto simples da notificação de atraso."""
        return f"""
Atraso na Entrega - {context['tracking_code']}

Lamentamos informar que sua entrega prevista para {context['original_date']} 
foi adiada para {context['new_date']}.

{f"Motivo: {context['reason']}" if context.get('reason') else ""}

Acompanhe seu pedido em: {getattr(settings, 'TRACKING_URL', 'https://empresa.com/rastreamento')}

{context['company_name']}
        """.strip()


# Instância global do serviço
email_service = EmailNotificationService()