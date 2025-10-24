"""
Serviço para gerenciamento de notificações push logísticas.
"""
import logging
import json
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import Count

# from ..models_mobile import NotificacaoMobile
from ..models_stock import RastreamentoEntrega, EventoRastreamento

logger = logging.getLogger(__name__)


class NotificationService:
    """Serviço para gerenciamento de notificações push."""
    
    def __init__(self):
        self.firebase_server_key = getattr(settings, 'FIREBASE_SERVER_KEY', None)
        self.firebase_url = 'https://fcm.googleapis.com/fcm/send'
    
    def enviar_notificacao(self,
                          destinatario_id: int,
                          tipo_notificacao: str,
                          canal: str = 'PUSH',
                          titulo: str = '',
                          mensagem: str = '',
                          dados_extras: Dict[str, Any] = None,
                          prioridade: str = 'NORMAL') -> None:  # NotificacaoMobile:
        """
        Envia uma notificação para um usuário.
        
        Args:
            destinatario_id: ID do usuário destinatário
            tipo_notificacao: Tipo da notificação
            canal: Canal de envio (PUSH, EMAIL, SMS, WHATSAPP)
            titulo: Título da notificação
            mensagem: Mensagem da notificação
            dados_extras: Dados extras em formato JSON
            prioridade: Prioridade da notificação
            
        Returns:
            # NotificacaoMobile criada
        """
        try:
            destinatario = User.objects.get(id=destinatario_id)
            
            # Criar notificação no banco
            # notificacao = NotificacaoMobile.objects.create(
            #     destinatario=destinatario,
            #     tipo_notificacao=tipo_notificacao,
            #     canal=canal,
            #     titulo=titulo,
            #     mensagem=mensagem,
            #     dados_extras=dados_extras or {},
            #     prioridade=prioridade
            # )
            
            # Enviar via canal específico
            # if canal == 'PUSH':
            #     self._enviar_push_notification(notificacao)
            # elif canal == 'EMAIL':
            #     self._enviar_email_notification(notificacao)
            # elif canal == 'SMS':
            #     self._enviar_sms_notification(notificacao)
            # elif canal == 'WHATSAPP':
            #     self._enviar_whatsapp_notification(notificacao)
            
            # logger.info(f"Notificação enviada: {notificacao.id} - {tipo_notificacao}")
            # return notificacao
            
        except Exception as e:
            logger.error(f"Erro ao enviar notificação: {e}")
            raise
    
    def _enviar_push_notification(self, notificacao):  # NotificacaoMobile):
        """Envia notificação push via Firebase."""
        try:
            if not self.firebase_server_key:
                logger.warning("Firebase Server Key não configurada")
                return
            
            # Obter token FCM do usuário (implementar conforme necessário)
            fcm_token = self._obter_fcm_token(notificacao.destinatario)
            if not fcm_token:
                logger.warning(f"Token FCM não encontrado para usuário {notificacao.destinatario.id}")
                return
            
            headers = {
                'Authorization': f'key={self.firebase_server_key}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'to': fcm_token,
                'notification': {
                    'title': notificacao.titulo,
                    'body': notificacao.mensagem,
                    'sound': 'default',
                    'badge': 1
                },
                'data': {
                    'tipo_notificacao': notificacao.tipo_notificacao,
                    'notificacao_id': str(notificacao.id),
                    'prioridade': notificacao.prioridade,
                    **notificacao.dados_extras
                },
                'priority': 'high' if notificacao.prioridade == 'ALTA' else 'normal'
            }
            
            response = requests.post(self.firebase_url, headers=headers, json=payload)
            
            if response.status_code == 200:
                logger.info(f"Push notification enviada com sucesso: {notificacao.id}")
            else:
                logger.error(f"Erro ao enviar push notification: {response.text}")
                
        except Exception as e:
            logger.error(f"Erro ao enviar push notification: {e}")
    
    def _enviar_email_notification(self, notificacao):  # NotificacaoMobile):
        """Envia notificação por email."""
        try:
            from django.core.mail import send_mail
            
            subject = f"[Logística] {notificacao.titulo}"
            message = f"""
{notificacao.mensagem}

Tipo: {notificacao.get_tipo_notificacao_display()}
Prioridade: {notificacao.get_prioridade_display()}
Data: {notificacao.data_criacao.strftime('%d/%m/%Y %H:%M')}

Acesse o sistema para mais detalhes.
            """.strip()
            
            send_mail(
                subject=subject,
                message=message,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@empresa.com'),
                recipient_list=[notificacao.destinatario.email],
                fail_silently=True
            )
            
            logger.info(f"Email notification enviada: {notificacao.id}")
            
        except Exception as e:
            logger.error(f"Erro ao enviar email notification: {e}")
    
    def _enviar_sms_notification(self, notificacao):  # NotificacaoMobile):
        """Envia notificação por SMS."""
        try:
            # Implementar integração com provedor de SMS
            # Exemplo: Twilio, AWS SNS, etc.
            logger.info(f"SMS notification enviada: {notificacao.id}")
            
        except Exception as e:
            logger.error(f"Erro ao enviar SMS notification: {e}")
    
    def _enviar_whatsapp_notification(self, notificacao):  # NotificacaoMobile):
        """Envia notificação por WhatsApp."""
        try:
            # Implementar integração com WhatsApp Business API
            logger.info(f"WhatsApp notification enviada: {notificacao.id}")
            
        except Exception as e:
            logger.error(f"Erro ao enviar WhatsApp notification: {e}")
    
    def _obter_fcm_token(self, usuario: User) -> Optional[str]:
        """Obtém o token FCM do usuário."""
        # Implementar conforme necessário
        # Pode ser armazenado em um modelo separado ou no perfil do usuário
        return None
    
    def notificar_mudanca_status(self,
                                rastreamento_id: int,
                                status_anterior: str,
                                status_novo: str,
                                observacoes: str = ''):
        """Notifica mudança de status de rastreamento."""
        try:
            rastreamento = RastreamentoEntrega.objects.get(id=rastreamento_id)
            
            # Verificar se deve notificar
            if not self._deve_notificar_mudanca_status():
                return
            
            # Determinar destinatários
            destinatarios = self._obter_destinatarios_rastreamento(rastreamento)
            
            for destinatario in destinatarios:
                self.enviar_notificacao(
                    destinatario_id=destinatario.id,
                    tipo_notificacao='STATUS_MUDANCA',
                    canal='PUSH',
                    titulo=f'Status Atualizado - {rastreamento.codigo_rastreamento}',
                    mensagem=f'Status alterado de {status_anterior} para {status_novo}. {observacoes}',
                    dados_extras={
                        'rastreamento_id': rastreamento_id,
                        'status_anterior': status_anterior,
                        'status_novo': status_novo,
                        'codigo_rastreamento': rastreamento.codigo_rastreamento
                    },
                    prioridade='NORMAL'
                )
                
        except Exception as e:
            logger.error(f"Erro ao notificar mudança de status: {e}")
    
    def notificar_atraso(self,
                        rastreamento_id: int,
                        data_prevista: datetime.date,
                        dias_atraso: int = 0):
        """Notifica atraso na entrega."""
        try:
            rastreamento = RastreamentoEntrega.objects.get(id=rastreamento_id)
            
            # Verificar se deve notificar
            if not self._deve_notificar_atraso():
                return
            
            # Determinar destinatários
            destinatarios = self._obter_destinatarios_rastreamento(rastreamento)
            
            for destinatario in destinatarios:
                self.enviar_notificacao(
                    destinatario_id=destinatario.id,
                    tipo_notificacao='ATRASO',
                    canal='PUSH',
                    titulo=f'Entrega Atrasada - {rastreamento.codigo_rastreamento}',
                    mensagem=f'Entrega prevista para {data_prevista.strftime("%d/%m/%Y")} está atrasada em {dias_atraso} dias.',
                    dados_extras={
                        'rastreamento_id': rastreamento_id,
                        'data_prevista': data_prevista.isoformat(),
                        'dias_atraso': dias_atraso,
                        'codigo_rastreamento': rastreamento.codigo_rastreamento
                    },
                    prioridade='ALTA'
                )
                
        except Exception as e:
            logger.error(f"Erro ao notificar atraso: {e}")
    
    def notificar_excecao(self,
                          excecao_id: int,
                          tipo_excecao: str,
                          descricao: str = ''):
        """Notifica exceção logística."""
        try:
            from ..models_exceptions import ExcecaoLogistica
            excecao = ExcecaoLogistica.objects.get(id=excecao_id)
            
            # Verificar se deve notificar
            if not self._deve_notificar_excecao():
                return
            
            # Determinar destinatários (administradores)
            destinatarios = User.objects.filter(is_staff=True, is_active=True)
            
            for destinatario in destinatarios:
                self.enviar_notificacao(
                    destinatario_id=destinatario.id,
                    tipo_notificacao='EXCECAO',
                    canal='PUSH',
                    titulo=f'Exceção Logística - {tipo_excecao}',
                    mensagem=f'{descricao}',
                    dados_extras={
                        'excecao_id': excecao_id,
                        'tipo_excecao': tipo_excecao,
                        'rastreamento_id': excecao.rastreamento_entrega.id if excecao.rastreamento_entrega else None
                    },
                    prioridade='ALTA'
                )
                
        except Exception as e:
            logger.error(f"Erro ao notificar exceção: {e}")
    
    def notificar_pod_criada(self, pod_id: int):
        """Notifica criação de POD."""
        try:
            from ..models_pod import ProvaEntrega
            pod = ProvaEntrega.objects.get(id=pod_id)
            
            # Verificar se deve notificar
            if not self._deve_notificar_pod_criada():
                return
            
            # Determinar destinatários
            destinatarios = self._obter_destinatarios_pod(pod)
            
            for destinatario in destinatarios:
                self.enviar_notificacao(
                    destinatario_id=destinatario.id,
                    tipo_notificacao='POD_CRIADA',
                    canal='PUSH',
                    titulo=f'POD Criada - {pod.codigo}',
                    mensagem=f'Prova de entrega criada para {pod.rastreamento_entrega.codigo_rastreamento}',
                    dados_extras={
                        'pod_id': pod_id,
                        'rastreamento_id': pod.rastreamento_entrega.id,
                        'codigo_pod': pod.codigo
                    },
                    prioridade='NORMAL'
                )
                
        except Exception as e:
            logger.error(f"Erro ao notificar POD criada: {e}")
    
    def notificar_pod_validada(self, pod_id: int):
        """Notifica validação de POD."""
        try:
            from ..models_pod import ProvaEntrega
            pod = ProvaEntrega.objects.get(id=pod_id)
            
            # Verificar se deve notificar
            if not self._deve_notificar_pod_validada():
                return
            
            # Determinar destinatários
            destinatarios = self._obter_destinatarios_pod(pod)
            
            for destinatario in destinatarios:
                self.enviar_notificacao(
                    destinatario_id=destinatario.id,
                    tipo_notificacao='POD_VALIDADA',
                    canal='PUSH',
                    titulo=f'POD Validada - {pod.codigo}',
                    mensagem=f'Prova de entrega validada para {pod.rastreamento_entrega.codigo_rastreamento}',
                    dados_extras={
                        'pod_id': pod_id,
                        'rastreamento_id': pod.rastreamento_entrega.id,
                        'codigo_pod': pod.codigo,
                        'validada_por': pod.validada_por.username if pod.validada_por else None
                    },
                    prioridade='NORMAL'
                )
                
        except Exception as e:
            logger.error(f"Erro ao notificar POD validada: {e}")
    
    def _deve_notificar_mudanca_status(self) -> bool:
        """Verifica se deve notificar mudança de status."""
        configuracao = cache.get('configuracao_notificacoes_automaticas', {})
        return configuracao.get('notificar_status_mudanca', True)
    
    def _deve_notificar_atraso(self) -> bool:
        """Verifica se deve notificar atraso."""
        configuracao = cache.get('configuracao_notificacoes_automaticas', {})
        return configuracao.get('notificar_atraso', True)
    
    def _deve_notificar_excecao(self) -> bool:
        """Verifica se deve notificar exceção."""
        configuracao = cache.get('configuracao_notificacoes_automaticas', {})
        return configuracao.get('notificar_excecao', True)
    
    def _deve_notificar_pod_criada(self) -> bool:
        """Verifica se deve notificar POD criada."""
        configuracao = cache.get('configuracao_notificacoes_automaticas', {})
        return configuracao.get('notificar_pod_criada', True)
    
    def _deve_notificar_pod_validada(self) -> bool:
        """Verifica se deve notificar POD validada."""
        configuracao = cache.get('configuracao_notificacoes_automaticas', {})
        return configuracao.get('notificar_pod_validada', True)
    
    def _obter_destinatarios_rastreamento(self, rastreamento: RastreamentoEntrega) -> List[User]:
        """Obtém destinatários para notificações de rastreamento."""
        destinatarios = []
        
        # Adicionar usuário que criou o rastreamento
        if rastreamento.usuario:
            destinatarios.append(rastreamento.usuario)
        
        # Adicionar administradores
        administradores = User.objects.filter(is_staff=True, is_active=True)
        destinatarios.extend(administradores)
        
        # Remover duplicatas
        return list(set(destinatarios))
    
    def _obter_destinatarios_pod(self, pod) -> List[User]:
        """Obtém destinatários para notificações de POD."""
        destinatarios = []
        
        # Adicionar usuário que entregou
        if pod.entregue_por:
            destinatarios.append(pod.entregue_por)
        
        # Adicionar usuário que criou o rastreamento
        if pod.rastreamento_entrega.usuario:
            destinatarios.append(pod.rastreamento_entrega.usuario)
        
        # Adicionar administradores
        administradores = User.objects.filter(is_staff=True, is_active=True)
        destinatarios.extend(administradores)
        
        # Remover duplicatas
        return list(set(destinatarios))
    
    def obter_estatisticas_notificacoes(self,
                                       data_inicio: Optional[datetime.date] = None,
                                       data_fim: Optional[datetime.date] = None) -> Dict[str, Any]:
        """Obtém estatísticas de notificações."""
        
        # queryset = NotificacaoMobile.objects.all()
        
        if data_inicio:
            queryset = queryset.filter(data_criacao__date__gte=data_inicio)
        
        if data_fim:
            queryset = queryset.filter(data_criacao__date__lte=data_fim)
        
        stats = {
            'total_notificacoes': queryset.count(),
            'notificacoes_lidas': queryset.filter(lida=True).count(),
            'notificacoes_nao_lidas': queryset.filter(lida=False).count(),
            'por_tipo': dict(queryset.values('tipo_notificacao').annotate(
                count=Count('id')
            ).values_list('tipo_notificacao', 'count')),
            'por_canal': dict(queryset.values('canal').annotate(
                count=Count('id')
            ).values_list('canal', 'count')),
            'por_prioridade': dict(queryset.values('prioridade').annotate(
                count=Count('id')
            ).values_list('prioridade', 'count')),
        }
        
        # Calcular taxa de leitura
        if stats['total_notificacoes'] > 0:
            stats['taxa_leitura'] = round(
                (stats['notificacoes_lidas'] / stats['total_notificacoes']) * 100, 2
            )
        else:
            stats['taxa_leitura'] = 0
        
        return stats


# Instância global do serviço de notificações
notification_service = NotificationService()
