"""
Serviço para UX Mobile e painel motorista.
"""
import logging
import time
import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
from django.db.models import Q, F, Count, Sum, Avg, Min, Max
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.core.cache import cache

from ..models_mobile import (
    SessaoMotorista, EventoMotorista, PODOffline,
    RotaMotorista, ParadaRota, ConfiguracaoMobile, LogMobile
)
from ..models_stock import RastreamentoEntrega, VeiculoInterno
from ..models_pod import ProvaEntrega

logger = logging.getLogger(__name__)


class MobileService:
    """Serviço para UX Mobile e painel motorista."""
    
    def __init__(self):
        self._config_padrao = None
    
    @property
    def config_padrao(self):
        """Obtém a configuração padrão mobile."""
        if self._config_padrao is None:
            self._config_padrao = self._get_configuracao_padrao()
        return self._config_padrao
    
    def _get_configuracao_padrao(self) -> ConfiguracaoMobile:
        """Obtém a configuração padrão mobile."""
        try:
            return ConfiguracaoMobile.objects.get(padrao=True, ativo=True)
        except ConfiguracaoMobile.DoesNotExist:
            # Criar configuração padrão se não existir
            return ConfiguracaoMobile.objects.create(
                nome='Configuração Padrão',
                padrao=True,
                ativo=True
            )
    
    def _log_operacao_mobile(self,
                           tipo_operacao: str,
                           descricao: str,
                           dados_operacao: Dict[str, Any],
                           sessao_motorista: Optional[SessaoMotorista] = None,
                           dispositivo_info: Optional[Dict] = None,
                           versao_app: str = '',
                           plataforma: str = '',
                           sucesso: bool = True,
                           erro_mensagem: str = '',
                           tempo_execucao_ms: Optional[int] = None,
                           tamanho_dados_kb: Optional[int] = None):
        """Registra log de operação mobile."""
        try:
            LogMobile.objects.create(
                sessao_motorista=sessao_motorista,
                tipo_operacao=tipo_operacao,
                descricao=descricao,
                dados_operacao=dados_operacao,
                dispositivo_info=dispositivo_info or {},
                versao_app=versao_app,
                plataforma=plataforma,
                sucesso=sucesso,
                erro_mensagem=erro_mensagem,
                tempo_execucao_ms=tempo_execucao_ms,
                tamanho_dados_kb=tamanho_dados_kb
            )
        except Exception as e:
            logger.error(f"Erro ao registrar log mobile: {e}")
    
    def iniciar_sessao_motorista(self,
                                motorista: User,
                                veiculo_interno_id: Optional[int],
                                latitude: Decimal,
                                longitude: Decimal,
                                dispositivo_info: Dict[str, Any],
                                versao_app: str = '',
                                plataforma: str = '') -> SessaoMotorista:
        """
        Inicia uma sessão de motorista.
        
        Args:
            motorista: Usuário motorista
            veiculo_interno_id: ID do veículo interno
            latitude: Latitude inicial
            longitude: Longitude inicial
            dispositivo_info: Informações do dispositivo
            versao_app: Versão do aplicativo
            plataforma: Plataforma (Android/iOS)
            
        Returns:
            SessaoMotorista criada
        """
        inicio_tempo = time.time()
        
        try:
            # Verificar se já existe sessão ativa
            sessao_ativa = SessaoMotorista.objects.filter(
                motorista=motorista,
                status='ATIVA'
            ).first()
            
            if sessao_ativa:
                # Finalizar sessão anterior
                self.finalizar_sessao_motorista(sessao_ativa.id)
            
            # Obter veículo interno
            veiculo_interno = None
            if veiculo_interno_id:
                try:
                    veiculo_interno = VeiculoInterno.objects.get(id=veiculo_interno_id)
                except VeiculoInterno.DoesNotExist:
                    pass
            
            # Gerar token de sessão
            token_sessao = self._gerar_token_sessao()
            
            # Criar sessão
            sessao = SessaoMotorista.objects.create(
                motorista=motorista,
                veiculo_interno=veiculo_interno,
                latitude_inicial=latitude,
                longitude_inicial=longitude,
                latitude_atual=latitude,
                longitude_atual=longitude,
                dispositivo_info=dispositivo_info,
                versao_app=versao_app,
                status='ATIVA'
            )
            
            # Atualizar token
            sessao.token_sessao = token_sessao
            sessao.save()
            
            fim_tempo = time.time()
            tempo_execucao_ms = int((fim_tempo - inicio_tempo) * 1000)
            
            self._log_operacao_mobile(
                tipo_operacao='LOGIN',
                descricao='Sessão de motorista iniciada',
                dados_operacao={
                    'sessao_id': sessao.id,
                    'veiculo_id': veiculo_interno_id,
                    'latitude': float(latitude),
                    'longitude': float(longitude)
                },
                sessao_motorista=sessao,
                dispositivo_info=dispositivo_info,
                versao_app=versao_app,
                plataforma=plataforma,
                sucesso=True,
                tempo_execucao_ms=tempo_execucao_ms
            )
            
            logger.info(f"Sessão de motorista iniciada: {sessao.token_sessao}")
            return sessao
            
        except Exception as e:
            fim_tempo = time.time()
            tempo_execucao_ms = int((fim_tempo - inicio_tempo) * 1000)
            
            self._log_operacao_mobile(
                tipo_operacao='LOGIN',
                descricao='Erro ao iniciar sessão',
                dados_operacao={
                    'motorista_id': motorista.id,
                    'veiculo_id': veiculo_interno_id
                },
                dispositivo_info=dispositivo_info,
                versao_app=versao_app,
                plataforma=plataforma,
                sucesso=False,
                erro_mensagem=str(e),
                tempo_execucao_ms=tempo_execucao_ms
            )
            
            logger.error(f"Erro ao iniciar sessão de motorista: {e}")
            raise
    
    def _gerar_token_sessao(self) -> str:
        """Gera token único para sessão."""
        import secrets
        import string
        
        # Gerar token alfanumérico de 32 caracteres
        alphabet = string.ascii_letters + string.digits
        token = ''.join(secrets.choice(alphabet) for _ in range(32))
        
        # Verificar se token já existe
        while SessaoMotorista.objects.filter(token_sessao=token).exists():
            token = ''.join(secrets.choice(alphabet) for _ in range(32))
        
        return token
    
    def finalizar_sessao_motorista(self,
                                  sessao_id: int,
                                  latitude_final: Optional[Decimal] = None,
                                  longitude_final: Optional[Decimal] = None) -> SessaoMotorista:
        """
        Finaliza uma sessão de motorista.
        
        Args:
            sessao_id: ID da sessão
            latitude_final: Latitude final
            longitude_final: Longitude final
            
        Returns:
            SessaoMotorista finalizada
        """
        try:
            sessao = SessaoMotorista.objects.get(id=sessao_id)
            
            if sessao.status != 'ATIVA':
                raise ValueError("Sessão não está ativa")
            
            # Atualizar coordenadas finais
            if latitude_final and longitude_final:
                sessao.latitude_atual = latitude_final
                sessao.longitude_atual = longitude_final
            
            # Finalizar sessão
            sessao.status = 'FINALIZADA'
            sessao.data_fim = timezone.now()
            sessao.save()
            
            self._log_operacao_mobile(
                tipo_operacao='LOGOUT',
                descricao='Sessão de motorista finalizada',
                dados_operacao={
                    'sessao_id': sessao.id,
                    'duracao_minutos': int((sessao.data_fim - sessao.data_inicio).total_seconds() / 60),
                    'total_entregas': sessao.total_entregas_realizadas,
                    'total_km': float(sessao.total_km_percorridos)
                },
                sessao_motorista=sessao,
                sucesso=True
            )
            
            logger.info(f"Sessão de motorista finalizada: {sessao.token_sessao}")
            return sessao
            
        except Exception as e:
            logger.error(f"Erro ao finalizar sessão de motorista: {e}")
            raise
    
    def registrar_evento_motorista(self,
                                  sessao_id: int,
                                  tipo_evento: str,
                                  descricao: str = '',
                                  observacoes: str = '',
                                  latitude: Optional[Decimal] = None,
                                  longitude: Optional[Decimal] = None,
                                  precisao_gps: Optional[Decimal] = None,
                                  rastreamento_id: Optional[int] = None,
                                  dados_evento: Optional[Dict] = None,
                                  fotos: Optional[List[str]] = None,
                                  offline: bool = False) -> EventoMotorista:
        """
        Registra um evento do motorista.
        
        Args:
            sessao_id: ID da sessão
            tipo_evento: Tipo do evento
            descricao: Descrição do evento
            observacoes: Observações
            latitude: Latitude do evento
            longitude: Longitude do evento
            precisao_gps: Precisão do GPS
            rastreamento_id: ID do rastreamento relacionado
            dados_evento: Dados adicionais do evento
            fotos: Lista de URLs de fotos
            offline: Se foi registrado offline
            
        Returns:
            EventoMotorista criado
        """
        try:
            sessao = SessaoMotorista.objects.get(id=sessao_id)
            
            # Obter rastreamento se fornecido
            rastreamento = None
            if rastreamento_id:
                try:
                    rastreamento = RastreamentoEntrega.objects.get(id=rastreamento_id)
                except RastreamentoEntrega.DoesNotExist:
                    pass
            
            # Criar evento
            evento = EventoMotorista.objects.create(
                sessao_motorista=sessao,
                rastreamento_entrega=rastreamento,
                tipo_evento=tipo_evento,
                descricao=descricao,
                observacoes=observacoes,
                latitude=latitude,
                longitude=longitude,
                precisao_gps=precisao_gps,
                dados_evento=dados_evento or {},
                fotos=fotos or [],
                offline=offline,
                sincronizado=not offline
            )
            
            # Atualizar estatísticas da sessão
            if tipo_evento == 'FIM_ENTREGA':
                sessao.total_entregas_realizadas += 1
                sessao.save()
            
            self._log_operacao_mobile(
                tipo_operacao='EVENTO',
                descricao=f'Evento registrado: {tipo_evento}',
                dados_operacao={
                    'evento_id': evento.id,
                    'tipo_evento': tipo_evento,
                    'rastreamento_id': rastreamento_id,
                    'offline': offline
                },
                sessao_motorista=sessao,
                sucesso=True
            )
            
            logger.info(f"Evento registrado: {tipo_evento} - {evento.id}")
            return evento
            
        except Exception as e:
            logger.error(f"Erro ao registrar evento: {e}")
            raise
    
    def criar_pod_offline(self,
                         sessao_id: int,
                         rastreamento_id: int,
                         tipo_entrega: str,
                         nome_destinatario: str,
                         documento_destinatario: str = '',
                         telefone_destinatario: str = '',
                         latitude: Decimal = Decimal('0.0'),
                         longitude: Decimal = Decimal('0.0'),
                         precisao_gps: Optional[Decimal] = None,
                         endereco_entrega: str = '',
                         assinatura_digital: Optional[Dict] = None,
                         fotos_entrega: Optional[List[str]] = None,
                         fotos_produto: Optional[List[str]] = None,
                         fotos_destinatario: Optional[List[str]] = None,
                         observacoes: str = '',
                         motivo_recusa: str = '') -> PODOffline:
        """
        Cria uma POD offline.
        
        Args:
            sessao_id: ID da sessão
            rastreamento_id: ID do rastreamento
            tipo_entrega: Tipo da entrega
            nome_destinatario: Nome do destinatário
            documento_destinatario: Documento do destinatário
            telefone_destinatario: Telefone do destinatário
            latitude: Latitude da entrega
            longitude: Longitude da entrega
            precisao_gps: Precisão do GPS
            endereco_entrega: Endereço da entrega
            assinatura_digital: Dados da assinatura
            fotos_entrega: Fotos da entrega
            fotos_produto: Fotos do produto
            fotos_destinatario: Fotos do destinatário
            observacoes: Observações
            motivo_recusa: Motivo da recusa
            
        Returns:
            PODOffline criada
        """
        try:
            sessao = SessaoMotorista.objects.get(id=sessao_id)
            rastreamento = RastreamentoEntrega.objects.get(id=rastreamento_id)
            
            # Validar GPS se obrigatório
            if self.config_padrao.gps_obrigatorio and (latitude == Decimal('0.0') or longitude == Decimal('0.0')):
                raise ValueError("Coordenadas GPS são obrigatórias")
            
            # Criar POD offline
            pod_offline = PODOffline.objects.create(
                sessao_motorista=sessao,
                rastreamento_entrega=rastreamento,
                tipo_entrega=tipo_entrega,
                nome_destinatario=nome_destinatario,
                documento_destinatario=documento_destinatario,
                telefone_destinatario=telefone_destinatario,
                latitude=latitude,
                longitude=longitude,
                precisao_gps=precisao_gps,
                endereco_entrega=endereco_entrega,
                assinatura_digital=assinatura_digital or {},
                fotos_entrega=fotos_entrega or [],
                fotos_produto=fotos_produto or [],
                fotos_destinatario=fotos_destinatario or [],
                observacoes=observacoes,
                motivo_recusa=motivo_recusa,
                data_entrega=timezone.now(),
                status='PENDENTE_SINCRONIZACAO'
            )
            
            self._log_operacao_mobile(
                tipo_operacao='POD',
                descricao='POD offline criada',
                dados_operacao={
                    'pod_offline_id': pod_offline.id,
                    'rastreamento_id': rastreamento_id,
                    'tipo_entrega': tipo_entrega,
                    'destinatario': nome_destinatario
                },
                sessao_motorista=sessao,
                sucesso=True
            )
            
            logger.info(f"POD offline criada: {pod_offline.codigo_offline}")
            return pod_offline
            
        except Exception as e:
            logger.error(f"Erro ao criar POD offline: {e}")
            raise
    
    def sincronizar_pod_offline(self, pod_offline_id: int) -> Tuple[bool, str]:
        """
        Sincroniza uma POD offline com o sistema principal.
        
        Args:
            pod_offline_id: ID da POD offline
            
        Returns:
            Tupla (sucesso, mensagem)
        """
        try:
            pod_offline = PODOffline.objects.get(id=pod_offline_id)
            
            if pod_offline.status != 'PENDENTE_SINCRONIZACAO':
                return False, "POD já foi sincronizada"
            
            # Criar POD no sistema principal
            from ..services.pod_service import PODService
            pod_service = PODService()
            
            prova_entrega = pod_service.criar_prova_entrega(
                rastreamento_id=pod_offline.rastreamento_entrega.id,
                tipo_entrega=pod_offline.tipo_entrega,
                endereco_entrega=pod_offline.endereco_entrega,
                latitude=pod_offline.latitude,
                longitude=pod_offline.longitude,
                precisao_gps=pod_offline.precisao_gps,
                nome_destinatario=pod_offline.nome_destinatario,
                documento_destinatario=pod_offline.documento_destinatario,
                telefone_destinatario=pod_offline.telefone_destinatario,
                observacoes=pod_offline.observacoes,
                motivo_recusa=pod_offline.motivo_recusa,
                entregue_por_id=pod_offline.sessao_motorista.motorista.id
            )
            
            # Adicionar assinatura se existir
            if pod_offline.assinatura_digital:
                pod_service.adicionar_assinatura_digital(
                    prova_id=prova_entrega.id,
                    dados_assinatura=pod_offline.assinatura_digital
                )
            
            # Marcar POD offline como sincronizada
            pod_offline.status = 'SINCRONIZADO'
            pod_offline.data_sincronizacao = timezone.now()
            pod_offline.save()
            
            self._log_operacao_mobile(
                tipo_operacao='SINCRONIZACAO',
                descricao='POD offline sincronizada',
                dados_operacao={
                    'pod_offline_id': pod_offline.id,
                    'prova_entrega_id': prova_entrega.id
                },
                sessao_motorista=pod_offline.sessao_motorista,
                sucesso=True
            )
            
            logger.info(f"POD offline sincronizada: {pod_offline.codigo_offline}")
            return True, "POD sincronizada com sucesso"
            
        except Exception as e:
            # Marcar como erro
            pod_offline.status = 'ERRO_SINCRONIZACAO'
            pod_offline.erro_sincronizacao = str(e)
            pod_offline.save()
            
            logger.error(f"Erro ao sincronizar POD offline: {e}")
            return False, str(e)
    
    def obter_rotas_motorista(self,
                             motorista_id: int,
                             data: Optional[date] = None) -> List[RotaMotorista]:
        """
        Obtém rotas de um motorista.
        
        Args:
            motorista_id: ID do motorista
            data: Data específica (opcional)
            
        Returns:
            Lista de rotas
        """
        try:
            queryset = RotaMotorista.objects.filter(
                motorista_id=motorista_id
            ).select_related('veiculo_interno')
            
            if data:
                queryset = queryset.filter(data_planejada=data)
            else:
                # Por padrão, mostrar rotas dos próximos 7 dias
                data_limite = timezone.now().date() + timedelta(days=7)
                queryset = queryset.filter(data_planejada__lte=data_limite)
            
            return list(queryset.order_by('data_planejada', 'hora_inicio_prevista'))
            
        except Exception as e:
            logger.error(f"Erro ao obter rotas do motorista: {e}")
            raise
    
    def obter_estatisticas_mobile(self) -> Dict[str, Any]:
        """
        Obtém estatísticas do sistema mobile.
        
        Returns:
            Dicionário com estatísticas
        """
        try:
            hoje = timezone.now().date()
            ultimos_7_dias = hoje - timedelta(days=7)
            
            stats = {
                'sessoes': {
                    'total_sessoes': SessaoMotorista.objects.count(),
                    'sessoes_ativas': SessaoMotorista.objects.filter(status='ATIVA').count(),
                    'ultimos_7_dias': SessaoMotorista.objects.filter(
                        data_inicio__date__gte=ultimos_7_dias
                    ).count(),
                    'sessoes_finalizadas': SessaoMotorista.objects.filter(status='FINALIZADA').count()
                },
                'eventos': {
                    'total_eventos': EventoMotorista.objects.count(),
                    'ultimos_7_dias': EventoMotorista.objects.filter(
                        data_evento__date__gte=ultimos_7_dias
                    ).count(),
                    'eventos_offline': EventoMotorista.objects.filter(offline=True).count(),
                    'eventos_sincronizados': EventoMotorista.objects.filter(sincronizado=True).count(),
                    'por_tipo': dict(
                        EventoMotorista.objects.values('tipo_evento')
                        .annotate(count=Count('id'))
                        .values_list('tipo_evento', 'count')
                    )
                },
                'pods_offline': {
                    'total_pods': PODOffline.objects.count(),
                    'pendentes_sincronizacao': PODOffline.objects.filter(
                        status='PENDENTE_SINCRONIZACAO'
                    ).count(),
                    'sincronizadas': PODOffline.objects.filter(status='SINCRONIZADO').count(),
                    'erro_sincronizacao': PODOffline.objects.filter(
                        status='ERRO_SINCRONIZACAO'
                    ).count(),
                    'ultimos_7_dias': PODOffline.objects.filter(
                        data_criacao_offline__date__gte=ultimos_7_dias
                    ).count()
                },
                'rotas': {
                    'total_rotas': RotaMotorista.objects.count(),
                    'rotas_planejadas': RotaMotorista.objects.filter(status='PLANEJADA').count(),
                    'rotas_em_andamento': RotaMotorista.objects.filter(status='EM_ANDAMENTO').count(),
                    'rotas_concluidas': RotaMotorista.objects.filter(status='CONCLUIDA').count(),
                    'ultimos_7_dias': RotaMotorista.objects.filter(
                        data_planejada__gte=ultimos_7_dias
                    ).count()
                },
                'logs': {
                    'total_logs': LogMobile.objects.count(),
                    'ultimos_7_dias': LogMobile.objects.filter(
                        data_operacao__date__gte=ultimos_7_dias
                    ).count(),
                    'operacoes_sucesso': LogMobile.objects.filter(sucesso=True).count(),
                    'operacoes_erro': LogMobile.objects.filter(sucesso=False).count(),
                    'por_tipo': dict(
                        LogMobile.objects.values('tipo_operacao')
                        .annotate(count=Count('id'))
                        .values_list('tipo_operacao', 'count')
                    )
                }
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas mobile: {e}")
            raise


# Instância global do serviço
mobile_service = MobileService()
