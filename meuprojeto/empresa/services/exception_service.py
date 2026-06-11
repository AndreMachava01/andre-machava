"""
Serviço para gerenciamento de exceções logísticas.
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
from django.db.models import Q, F, Count, Sum, Avg
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings

from ..models_exceptions import (
    TipoExcecao, ExcecaoLogistica, AcaoExcecao, DevolucaoLogistica, 
    Reentrega, ConfiguracaoExcecoes
)
from ..models_stock import RastreamentoEntrega, EventoRastreamento
from ..models_routing import PlanejamentoEntrega, Rota

logger = logging.getLogger(__name__)


class ExceptionService:
    """Serviço para gerenciamento de exceções logísticas."""
    
    def __init__(self):
        self._config_padrao = None
    
    @property
    def config_padrao(self):
        """Obtém a configuração padrão de forma lazy."""
        if self._config_padrao is None:
            self._config_padrao = self._get_configuracao_padrao()
        return self._config_padrao
    
    def _get_configuracao_padrao(self) -> ConfiguracaoExcecoes:
        """Obtém a configuração padrão de exceções."""
        try:
            return ConfiguracaoExcecoes.objects.get(padrao=True, ativo=True)
        except ConfiguracaoExcecoes.DoesNotExist:
            # Criar configuração padrão se não existir
            return ConfiguracaoExcecoes.objects.create(
                nome='Configuração Padrão',
                padrao=True,
                ativo=True
            )
    
    def criar_excecao(self,
                     tipo_codigo: str,
                     rastreamento_id: Optional[int] = None,
                     planejamento_id: Optional[int] = None,
                     rota_id: Optional[int] = None,
                     descricao: str = '',
                     observacoes: str = '',
                     local_ocorrencia: str = '',
                     latitude: Optional[Decimal] = None,
                     longitude: Optional[Decimal] = None,
                     prioridade: str = 'NORMAL',
                     reportado_por_id: Optional[int] = None,
                     evidencia_fotos: List[str] = None) -> ExcecaoLogistica:
        """
        Cria uma nova exceção logística.
        
        Args:
            tipo_codigo: Código do tipo de exceção
            rastreamento_id: ID do rastreamento relacionado
            planejamento_id: ID do planejamento relacionado
            rota_id: ID da rota relacionada
            descricao: Descrição da exceção
            observacoes: Observações adicionais
            local_ocorrencia: Local onde ocorreu a exceção
            latitude: Latitude do local
            longitude: Longitude do local
            prioridade: Prioridade da exceção
            reportado_por_id: ID do usuário que reportou
            evidencia_fotos: Lista de URLs de fotos
            
        Returns:
            ExcecaoLogistica criada
        """
        try:
            tipo_excecao = TipoExcecao.objects.get(codigo=tipo_codigo, ativo=True)
        except TipoExcecao.DoesNotExist:
            raise ValueError(f"Tipo de exceção '{tipo_codigo}' não encontrado")
        
        # Gerar código único
        codigo = self._gerar_codigo_excecao()
        
        excecao = ExcecaoLogistica.objects.create(
            codigo=codigo,
            tipo_excecao=tipo_excecao,
            rastreamento_entrega_id=rastreamento_id,
            planejamento_entrega_id=planejamento_id,
            rota_id=rota_id,
            descricao=descricao,
            observacoes=observacoes,
            local_ocorrencia=local_ocorrencia,
            latitude=latitude,
            longitude=longitude,
            prioridade=prioridade,
            reportado_por_id=reportado_por_id,
            evidencia_fotos=evidencia_fotos or []
        )
        
        # Atualizar status do rastreamento se necessário
        if rastreamento_id and tipo_excecao.bloqueia_entrega:
            self._atualizar_status_rastreamento(rastreamento_id, 'PROBLEMA')
        
        # Enviar notificações se configurado
        if tipo_excecao.requer_notificacao:
            self._enviar_notificacao_excecao(excecao)
        
        logger.info(f"Exceção criada: {codigo} - {tipo_excecao.nome}")
        return excecao
    
    def _gerar_codigo_excecao(self) -> str:
        """Gera código único para exceção."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        count = ExcecaoLogistica.objects.filter(
            codigo__startswith=f"EXC-{timestamp}"
        ).count()
        
        return f"EXC-{timestamp}-{count + 1:03d}"
    
    def _atualizar_status_rastreamento(self, rastreamento_id: int, novo_status: str):
        """Atualiza status do rastreamento."""
        try:
            rastreamento = RastreamentoEntrega.objects.get(id=rastreamento_id)
            rastreamento.status_atual = novo_status
            rastreamento.save()
            
            # Criar evento de rastreamento
            EventoRastreamento.objects.create(
                rastreamento=rastreamento,
                status_anterior=rastreamento.status_atual,
                status_atual=novo_status,
                data_evento=timezone.now(),
                observacoes=f"Status alterado devido a exceção",
                origem_evento='EXCECAO'
            )
        except RastreamentoEntrega.DoesNotExist:
            logger.warning(f"Rastreamento {rastreamento_id} não encontrado")
    
    def _enviar_notificacao_excecao(self, excecao: ExcecaoLogistica):
        """Envia notificação sobre exceção."""
        try:
            subject = f"Exceção Logística Reportada - {excecao.codigo}"
            
            message = f"""
Exceção Logística Reportada

Código: {excecao.codigo}
Tipo: {excecao.tipo_excecao.nome}
Prioridade: {excecao.prioridade}
Data: {excecao.data_ocorrencia.strftime('%d/%m/%Y %H:%M')}

Descrição:
{excecao.descricao}

Local: {excecao.local_ocorrencia}

Observações:
{excecao.observacoes}

Acesse o sistema para mais detalhes.
            """.strip()
            
            # Enviar para administradores (implementação simplificada)
            admin_emails = getattr(settings, 'ADMIN_EMAILS', [])
            if admin_emails:
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@empresa.com'),
                    recipient_list=admin_emails,
                    fail_silently=True
                )
                
        except Exception as e:
            logger.error(f"Erro ao enviar notificação de exceção: {e}")
    
    def adicionar_acao_excecao(self,
                              excecao_id: int,
                              tipo_acao: str,
                              descricao: str,
                              executado_por_id: Optional[int] = None,
                              data_prevista_conclusao: Optional[datetime] = None) -> AcaoExcecao:
        """
        Adiciona uma ação para resolver uma exceção.
        
        Args:
            excecao_id: ID da exceção
            tipo_acao: Tipo da ação
            descricao: Descrição da ação
            executado_por_id: ID do usuário que executará
            data_prevista_conclusao: Data prevista para conclusão
            
        Returns:
            AcaoExcecao criada
        """
        excecao = ExcecaoLogistica.objects.get(id=excecao_id)
        
        acao = AcaoExcecao.objects.create(
            excecao=excecao,
            tipo_acao=tipo_acao,
            descricao=descricao,
            executado_por_id=executado_por_id,
            data_prevista_conclusao=data_prevista_conclusao
        )
        
        # Atualizar status da exceção para "Em Análise"
        if excecao.status == 'ABERTA':
            excecao.status = 'EM_ANALISE'
            excecao.save()
        
        logger.info(f"Ação adicionada à exceção {excecao.codigo}: {tipo_acao}")
        return acao
    
    def concluir_acao_excecao(self,
                             acao_id: int,
                             resultado: str = '',
                             observacoes: str = '') -> AcaoExcecao:
        """
        Marca uma ação como concluída.
        
        Args:
            acao_id: ID da ação
            resultado: Resultado da ação
            observacoes: Observações sobre a conclusão
            
        Returns:
            AcaoExcecao atualizada
        """
        acao = AcaoExcecao.objects.get(id=acao_id)
        acao.concluida = True
        acao.data_conclusao = timezone.now()
        acao.resultado = resultado
        acao.observacoes = observacoes
        acao.save()
        
        # Verificar se todas as ações estão concluídas para resolver a exceção
        self._verificar_resolucao_excecao(acao.excecao)
        
        logger.info(f"Ação concluída: {acao.excecao.codigo} - {acao.tipo_acao}")
        return acao
    
    def _verificar_resolucao_excecao(self, excecao: ExcecaoLogistica):
        """Verifica se a exceção pode ser marcada como resolvida."""
        acoes_pendentes = excecao.acoes.filter(concluida=False).count()
        
        if acoes_pendentes == 0 and excecao.status == 'EM_ANALISE':
            excecao.status = 'RESOLVIDA'
            excecao.data_resolucao = timezone.now()
            excecao.save()
            
            # Restaurar status do rastreamento se necessário
            if excecao.rastreamento_entrega and excecao.tipo_excecao.bloqueia_entrega:
                self._restaurar_status_rastreamento(excecao.rastreamento_entrega)
            
            logger.info(f"Exceção resolvida: {excecao.codigo}")
    
    def _restaurar_status_rastreamento(self, rastreamento: RastreamentoEntrega):
        """Restaura status do rastreamento após resolução da exceção."""
        # Lógica simplificada - pode ser expandida
        if rastreamento.status_atual == 'PROBLEMA':
            rastreamento.status_atual = 'EM_TRANSITO'
            rastreamento.save()
            
            EventoRastreamento.objects.create(
                rastreamento=rastreamento,
                status_anterior='PROBLEMA',
                status_atual='EM_TRANSITO',
                data_evento=timezone.now(),
                observacoes="Status restaurado após resolução de exceção",
                origem_evento='EXCECAO'
            )
    
    def criar_devolucao(self,
                       rastreamento_id: int,
                       motivo: str,
                       descricao_motivo: str,
                       solicitado_por: str,
                       contato_solicitante: str = '',
                       excecao_id: Optional[int] = None,
                       observacoes: str = '',
                       instrucoes_coleta: str = '') -> DevolucaoLogistica:
        """
        Cria uma solicitação de devolução.
        
        Args:
            rastreamento_id: ID do rastreamento original
            motivo: Motivo da devolução
            descricao_motivo: Descrição detalhada do motivo
            solicitado_por: Nome de quem solicitou
            contato_solicitante: Contato do solicitante
            excecao_id: ID da exceção relacionada
            observacoes: Observações adicionais
            instrucoes_coleta: Instruções para coleta
            
        Returns:
            DevolucaoLogistica criada
        """
        rastreamento = RastreamentoEntrega.objects.get(id=rastreamento_id)
        
        # Gerar código único
        codigo = self._gerar_codigo_devolucao()
        
        devolucao = DevolucaoLogistica.objects.create(
            codigo=codigo,
            rastreamento_original=rastreamento,
            excecao_relacionada_id=excecao_id,
            motivo=motivo,
            descricao_motivo=descricao_motivo,
            solicitado_por=solicitado_por,
            contato_solicitante=contato_solicitante,
            observacoes=observacoes,
            instrucoes_coleta=instrucoes_coleta
        )
        
        logger.info(f"Devolução criada: {codigo} - {motivo}")
        return devolucao
    
    def _gerar_codigo_devolucao(self) -> str:
        """Gera código único para devolução."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        count = DevolucaoLogistica.objects.filter(
            codigo__startswith=f"DEV-{timestamp}"
        ).count()
        
        return f"DEV-{timestamp}-{count + 1:03d}"
    
    def aprovar_devolucao(self,
                         devolucao_id: int,
                         aprovado_por_id: int,
                         custo_devolucao: Optional[Decimal] = None) -> DevolucaoLogistica:
        """
        Aprova uma solicitação de devolução.
        
        Args:
            devolucao_id: ID da devolução
            aprovado_por_id: ID do usuário que aprovou
            custo_devolucao: Custo estimado da devolução
            
        Returns:
            DevolucaoLogistica atualizada
        """
        devolucao = DevolucaoLogistica.objects.get(id=devolucao_id)
        devolucao.status = 'APROVADA'
        devolucao.data_aprovacao = timezone.now()
        devolucao.aprovado_por_id = aprovado_por_id
        devolucao.custo_devolucao = custo_devolucao
        devolucao.save()
        
        logger.info(f"Devolução aprovada: {devolucao.codigo}")
        return devolucao
    
    def criar_reentrega(self,
                       rastreamento_id: int,
                       motivo_tentativa_anterior: str,
                       nova_data_entrega: datetime.date,
                       nova_janela_inicio: datetime.time,
                       nova_janela_fim: datetime.time,
                       excecao_id: Optional[int] = None,
                       agendado_por_id: Optional[int] = None,
                       observacoes: str = '',
                       instrucoes_especiais: str = '',
                       custo_reentrega: Optional[Decimal] = None) -> Reentrega:
        """
        Cria uma nova tentativa de entrega.
        
        Args:
            rastreamento_id: ID do rastreamento original
            motivo_tentativa_anterior: Motivo da falha anterior
            nova_data_entrega: Nova data para entrega
            nova_janela_inicio: Nova janela de início
            nova_janela_fim: Nova janela de fim
            excecao_id: ID da exceção relacionada
            agendado_por_id: ID do usuário que agendou
            observacoes: Observações adicionais
            instrucoes_especiais: Instruções especiais
            custo_reentrega: Custo adicional da reentrega
            
        Returns:
            Reentrega criada
        """
        rastreamento = RastreamentoEntrega.objects.get(id=rastreamento_id)
        
        # Gerar código único
        codigo = self._gerar_codigo_reentrega()
        
        reentrega = Reentrega.objects.create(
            codigo=codigo,
            rastreamento_original=rastreamento,
            excecao_relacionada_id=excecao_id,
            motivo_tentativa_anterior=motivo_tentativa_anterior,
            nova_data_entrega=nova_data_entrega,
            nova_janela_inicio=nova_janela_inicio,
            nova_janela_fim=nova_janela_fim,
            agendado_por_id=agendado_por_id,
            observacoes=observacoes,
            instrucoes_especiais=instrucoes_especiais,
            custo_reentrega=custo_reentrega
        )
        
        logger.info(f"Reentrega criada: {codigo} - {nova_data_entrega}")
        return reentrega
    
    def _gerar_codigo_reentrega(self) -> str:
        """Gera código único para reentrega."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        count = Reentrega.objects.filter(
            codigo__startswith=f"RE-{timestamp}"
        ).count()
        
        return f"RE-{timestamp}-{count + 1:03d}"
    
    def obter_excecoes_pendentes(self, 
                                prioridade: Optional[str] = None,
                                tipo_codigo: Optional[str] = None,
                                dias_atraso: Optional[int] = None) -> List[ExcecaoLogistica]:
        """
        Obtém exceções pendentes com filtros.
        
        Args:
            prioridade: Filtrar por prioridade
            tipo_codigo: Filtrar por tipo de exceção
            dias_atraso: Filtrar por dias de atraso
            
        Returns:
            Lista de exceções pendentes
        """
        queryset = ExcecaoLogistica.objects.filter(
            status__in=['ABERTA', 'EM_ANALISE']
        ).select_related('tipo_excecao', 'rastreamento_entrega')
        
        if prioridade:
            queryset = queryset.filter(prioridade=prioridade)
        
        if tipo_codigo:
            queryset = queryset.filter(tipo_excecao__codigo=tipo_codigo)
        
        if dias_atraso:
            data_limite = timezone.now() - timedelta(days=dias_atraso)
            queryset = queryset.filter(data_ocorrencia__lte=data_limite)
        
        return list(queryset.order_by('prioridade', 'data_ocorrencia'))
    
    def obter_estatisticas_excecoes(self, 
                                   data_inicio: Optional[datetime.date] = None,
                                   data_fim: Optional[datetime.date] = None) -> Dict[str, Any]:
        """
        Obtém estatísticas de exceções.
        
        Args:
            data_inicio: Data de início do período
            data_fim: Data de fim do período
            
        Returns:
            Dicionário com estatísticas
        """
        queryset = ExcecaoLogistica.objects.all()
        
        if data_inicio:
            queryset = queryset.filter(data_ocorrencia__date__gte=data_inicio)
        
        if data_fim:
            queryset = queryset.filter(data_ocorrencia__date__lte=data_fim)
        
        stats = {
            'total_excecoes': queryset.count(),
            'excecoes_abertas': queryset.filter(status='ABERTA').count(),
            'excecoes_em_analise': queryset.filter(status='EM_ANALISE').count(),
            'excecoes_resolvidas': queryset.filter(status='RESOLVIDA').count(),
            'excecoes_por_prioridade': dict(queryset.values('prioridade').annotate(
                count=Count('id')
            ).values_list('prioridade', 'count')),
            'excecoes_por_tipo': dict(queryset.values('tipo_excecao__nome').annotate(
                count=Count('id')
            ).values_list('tipo_excecao__nome', 'count')),
            'tempo_medio_resolucao': queryset.filter(
                status='RESOLVIDA',
                data_resolucao__isnull=False
            ).aggregate(
                tempo_medio=Avg(F('data_resolucao') - F('data_ocorrencia'))
            )['tempo_medio']
        }
        
        return stats


# Instância global do serviço (criada lazy quando necessário)
# exception_service = ExceptionService()
