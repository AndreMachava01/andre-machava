"""
Serviço para gerenciamento de POD (Prova de Entrega) e documentos logísticos.
"""
import logging
import json
import base64
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
from django.db.models import Q, F, Count, Sum, Avg
from django.utils import timezone
from django.core.files.base import ContentFile
from django.core.mail import send_mail
from django.conf import settings
from PIL import Image
import io

from ..models_pod import (
    TipoDocumento, ProvaEntrega, DocumentoPOD, AssinaturaDigital,
    GuiaRemessa, Etiqueta, ConfiguracaoPOD
)
from ..models_stock import RastreamentoEntrega, EventoRastreamento
from ..models_exceptions import ExcecaoLogistica

logger = logging.getLogger(__name__)


class PODService:
    """Serviço para gerenciamento de POD e documentos logísticos."""
    
    def __init__(self):
        self._config_padrao = None
    
    @property
    def config_padrao(self):
        """Obtém a configuração padrão de forma lazy."""
        if self._config_padrao is None:
            self._config_padrao = self._get_configuracao_padrao()
        return self._config_padrao
    
    def _get_configuracao_padrao(self) -> ConfiguracaoPOD:
        """Obtém a configuração padrão de POD."""
        try:
            return ConfiguracaoPOD.objects.get(padrao=True, ativo=True)
        except ConfiguracaoPOD.DoesNotExist:
            # Criar configuração padrão se não existir
            config = ConfiguracaoPOD.objects.create(
                nome='Configuração Padrão POD',
                padrao=True,
                ativo=True,
                formatos_permitidos=['JPG', 'JPEG', 'PNG', 'PDF', 'DOC', 'DOCX'],
                tamanho_maximo_mb=10,
                obrigatorio_foto=True,
                obrigatorio_assinatura=True,
                obrigatorio_gps=False
            )
            return config
    
    def criar_prova_entrega(self,
                           rastreamento_id: int,
                           tipo_entrega: str = 'COMPLETA',
                           endereco_entrega: str = '',
                           latitude: Optional[Decimal] = None,
                           longitude: Optional[Decimal] = None,
                           precisao_gps: Optional[Decimal] = None,
                           nome_destinatario: str = '',
                           documento_destinatario: str = '',
                           telefone_destinatario: str = '',
                           parentesco_destinatario: str = '',
                           observacoes: str = '',
                           motivo_recusa: str = '',
                           entregue_por_id: Optional[int] = None) -> ProvaEntrega:
        """
        Cria uma nova prova de entrega.
        
        Args:
            rastreamento_id: ID do rastreamento
            tipo_entrega: Tipo da entrega
            endereco_entrega: Endereço da entrega
            latitude: Latitude GPS
            longitude: Longitude GPS
            precisao_gps: Precisão do GPS em metros
            nome_destinatario: Nome do destinatário
            documento_destinatario: Documento do destinatário
            telefone_destinatario: Telefone do destinatário
            parentesco_destinatario: Parentesco do destinatário
            observacoes: Observações da entrega
            motivo_recusa: Motivo da recusa (se aplicável)
            entregue_por_id: ID do usuário que entregou
            
        Returns:
            ProvaEntrega criada
        """
        rastreamento = RastreamentoEntrega.objects.get(id=rastreamento_id)
        
        # Validar GPS se obrigatório
        if self.config_padrao.obrigatorio_gps and (not latitude or not longitude):
            raise ValueError("Coordenadas GPS são obrigatórias")
        
        # Validar precisão GPS
        if precisao_gps and precisao_gps > self.config_padrao.precisao_gps_minima:
            raise ValueError(f"Precisão GPS deve ser menor que {self.config_padrao.precisao_gps_minima}m")
        
        prova = ProvaEntrega.objects.create(
            rastreamento_entrega=rastreamento,
            tipo_entrega=tipo_entrega,
            endereco_entrega=endereco_entrega,
            latitude=latitude,
            longitude=longitude,
            precisao_gps=precisao_gps,
            nome_destinatario=nome_destinatario,
            documento_destinatario=documento_destinatario,
            telefone_destinatario=telefone_destinatario,
            parentesco_destinatario=parentesco_destinatario,
            observacoes=observacoes,
            motivo_recusa=motivo_recusa,
            entregue_por_id=entregue_por_id
        )
        
        # Atualizar status do rastreamento
        self._atualizar_status_rastreamento(rastreamento, tipo_entrega)
        
        logger.info(f"Prova de entrega criada: {prova.codigo}")
        return prova
    
    def _atualizar_status_rastreamento(self, rastreamento: RastreamentoEntrega, tipo_entrega: str):
        """Atualiza status do rastreamento baseado no tipo de entrega."""
        status_map = {
            'COMPLETA': 'ENTREGUE',
            'PARCIAL': 'ENTREGUE',
            'RECUSADA': 'RECUSADA',
            'DEVOLVIDA': 'DEVOLVIDA',
        }
        
        novo_status = status_map.get(tipo_entrega, 'ENTREGUE')
        rastreamento.status_atual = novo_status
        rastreamento.data_atualizacao = timezone.now()
        rastreamento.save()
        
        # Criar evento de rastreamento
        EventoRastreamento.objects.create(
            rastreamento=rastreamento,
            tipo_evento=novo_status,
            descricao=f"Status atualizado via POD - {tipo_entrega}",
            localizacao="Sistema POD",
            data_evento=timezone.now(),
            usuario=None  # Poderia ser passado como parâmetro se necessário
        )
    
    def adicionar_documento_pod(self,
                               prova_id: int,
                               tipo: str,
                               arquivo_data: bytes,
                               nome_arquivo: str,
                               descricao: str = '',
                               observacoes: str = '') -> DocumentoPOD:
        """
        Adiciona um documento à prova de entrega.
        
        Args:
            prova_id: ID da prova de entrega
            tipo: Tipo do documento
            arquivo_data: Dados do arquivo em bytes
            nome_arquivo: Nome do arquivo
            descricao: Descrição do documento
            observacoes: Observações
            
        Returns:
            DocumentoPOD criado
        """
        prova = ProvaEntrega.objects.get(id=prova_id)
        
        # Validar tamanho do arquivo
        tamanho_mb = len(arquivo_data) / (1024 * 1024)
        if tamanho_mb > self.config_padrao.tamanho_maximo_mb:
            raise ValueError(f"Arquivo muito grande. Máximo: {self.config_padrao.tamanho_maximo_mb}MB")
        
        # Validar formato do arquivo
        extensao = nome_arquivo.split('.')[-1].upper()
        if extensao not in self.config_padrao.formatos_permitidos:
            raise ValueError(f"Formato não permitido. Permitidos: {self.config_padrao.formatos_permitidos}")
        
        # Criar arquivo Django
        arquivo = ContentFile(arquivo_data, name=nome_arquivo)
        
        documento = DocumentoPOD.objects.create(
            prova_entrega=prova,
            tipo=tipo,
            nome_arquivo=nome_arquivo,
            arquivo=arquivo,
            tamanho_arquivo=len(arquivo_data),
            descricao=descricao,
            observacoes=observacoes
        )
        
        logger.info(f"Documento adicionado à POD {prova.codigo}: {tipo}")
        return documento
    
    def adicionar_assinatura_digital(self,
                                   prova_id: int,
                                   dados_assinatura: Dict[str, Any],
                                   imagem_assinatura_data: Optional[bytes] = None,
                                   dispositivo: str = '',
                                   navegador: str = '',
                                   ip_address: str = '') -> AssinaturaDigital:
        """
        Adiciona assinatura digital à prova de entrega.
        
        Args:
            prova_id: ID da prova de entrega
            dados_assinatura: Dados da assinatura em formato JSON
            imagem_assinatura_data: Dados da imagem da assinatura
            dispositivo: Informações do dispositivo
            navegador: Informações do navegador
            ip_address: Endereço IP
            
        Returns:
            AssinaturaDigital criada
        """
        prova = ProvaEntrega.objects.get(id=prova_id)
        
        # Gerar hash de validação
        hash_data = json.dumps(dados_assinatura, sort_keys=True)
        hash_validacao = hashlib.sha256(hash_data.encode()).hexdigest()
        
        assinatura = AssinaturaDigital.objects.create(
            prova_entrega=prova,
            dados_assinatura=dados_assinatura,
            dispositivo=dispositivo,
            navegador=navegador,
            ip_address=ip_address,
            hash_validacao=hash_validacao
        )
        
        # Adicionar imagem se fornecida
        if imagem_assinatura_data:
            imagem = ContentFile(imagem_assinatura_data, name=f"assinatura_{prova.codigo}.png")
            assinatura.imagem_assinatura = imagem
            assinatura.save()
        
        logger.info(f"Assinatura digital adicionada à POD {prova.codigo}")
        return assinatura
    
    def validar_prova_entrega(self,
                             prova_id: int,
                             validada_por_id: int,
                             observacoes_validacao: str = '') -> ProvaEntrega:
        """
        Valida uma prova de entrega.
        
        Args:
            prova_id: ID da prova de entrega
            validada_por_id: ID do usuário que validou
            observacoes_validacao: Observações da validação
            
        Returns:
            ProvaEntrega validada
        """
        prova = ProvaEntrega.objects.get(id=prova_id)
        
        # Verificar se todos os documentos obrigatórios estão presentes
        documentos_obrigatorios = self._verificar_documentos_obrigatorios(prova)
        if not documentos_obrigatorios['completo']:
            raise ValueError(f"Documentos obrigatórios ausentes: {documentos_obrigatorios['ausentes']}")
        
        # Validar GPS se obrigatório
        if self.config_padrao.obrigatorio_gps and (not prova.latitude or not prova.longitude):
            raise ValueError("Coordenadas GPS são obrigatórias")
        
        # Marcar como validada
        prova.validada = True
        prova.validada_por_id = validada_por_id
        prova.data_validacao = timezone.now()
        prova.status = 'CONCLUIDA'
        prova.save()
        
        # Enviar notificação de validação
        self._enviar_notificacao_validacao(prova)
        
        logger.info(f"Prova de entrega validada: {prova.codigo}")
        return prova
    
    def _verificar_documentos_obrigatorios(self, prova: ProvaEntrega) -> Dict[str, Any]:
        """Verifica se todos os documentos obrigatórios estão presentes."""
        documentos_presentes = set(prova.documentos.values_list('tipo', flat=True))
        
        obrigatorios = []
        if self.config_padrao.obrigatorio_foto:
            obrigatorios.append('FOTO_ENTREGA')
        if self.config_padrao.obrigatorio_assinatura:
            obrigatorios.append('ASSINATURA')
        
        ausentes = [doc for doc in obrigatorios if doc not in documentos_presentes]
        
        return {
            'completo': len(ausentes) == 0,
            'ausentes': ausentes,
            'presentes': list(documentos_presentes)
        }
    
    def _enviar_notificacao_validacao(self, prova: ProvaEntrega):
        """Envia notificação sobre validação da POD."""
        try:
            subject = f"POD Validada - {prova.codigo}"
            
            message = f"""
Prova de Entrega Validada

Código POD: {prova.codigo}
Rastreamento: {prova.rastreamento_entrega.codigo_rastreamento}
Tipo de Entrega: {prova.get_tipo_entrega_display()}
Data da Entrega: {prova.data_entrega.strftime('%d/%m/%Y %H:%M')}
Destinatário: {prova.nome_destinatario}

Validada por: {prova.validada_por.get_full_name() if prova.validada_por else 'Sistema'}
Data de Validação: {prova.data_validacao.strftime('%d/%m/%Y %H:%M')}

Acesse o sistema para mais detalhes.
            """.strip()
            
            # Enviar para administradores
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
            logger.error(f"Erro ao enviar notificação de validação: {e}")
    
    def gerar_guia_remessa(self,
                          rastreamento_id: int,
                          data_prevista_entrega: datetime.date,
                          nome_remetente: str = '',
                          endereco_remetente: str = '',
                          telefone_remetente: str = '',
                          descricao_produto: str = '',
                          peso: Optional[Decimal] = None,
                          valor_declarado: Optional[Decimal] = None,
                          instrucoes_especiais: str = '',
                          observacoes: str = '') -> GuiaRemessa:
        """
        Gera uma guia de remessa.
        
        Args:
            rastreamento_id: ID do rastreamento
            data_prevista_entrega: Data prevista para entrega
            nome_remetente: Nome do remetente
            endereco_remetente: Endereço do remetente
            telefone_remetente: Telefone do remetente
            descricao_produto: Descrição do produto
            peso: Peso do produto
            valor_declarado: Valor declarado
            instrucoes_especiais: Instruções especiais
            observacoes: Observações
            
        Returns:
            GuiaRemessa criada
        """
        rastreamento = RastreamentoEntrega.objects.get(id=rastreamento_id)
        
        guia = GuiaRemessa.objects.create(
            rastreamento_entrega=rastreamento,
            data_prevista_entrega=data_prevista_entrega,
            nome_remetente=nome_remetente,
            endereco_remetente=endereco_remetente,
            telefone_remetente=telefone_remetente,
            nome_destinatario=rastreamento.nome_destinatario or '',
            endereco_destinatario=rastreamento.endereco_entrega or '',
            telefone_destinatario=rastreamento.telefone_destinatario or '',
            descricao_produto=descricao_produto,
            peso=peso,
            valor_declarado=valor_declarado,
            instrucoes_especiais=instrucoes_especiais,
            observacoes=observacoes
        )
        
        # Gerar etiquetas se configurado
        if self.config_padrao.incluir_codigo_barras or self.config_padrao.incluir_qr_code:
            self._gerar_etiquetas_guia(guia)
        
        logger.info(f"Guia de remessa gerada: {guia.codigo}")
        return guia
    
    def _gerar_etiquetas_guia(self, guia: GuiaRemessa):
        """Gera etiquetas para uma guia de remessa."""
        conteudo_etiqueta = {
            'codigo_guia': guia.codigo,
            'codigo_rastreamento': guia.rastreamento_entrega.codigo_rastreamento,
            'destinatario': guia.nome_destinatario,
            'endereco': guia.endereco_destinatario,
            'data_prevista': guia.data_prevista_entrega.strftime('%d/%m/%Y'),
            'peso': str(guia.peso) if guia.peso else '',
            'valor': str(guia.valor_declarado) if guia.valor_declarado else ''
        }
        
        Etiqueta.objects.create(
            guia_remessa=guia,
            tipo='ENVIO',
            conteudo=conteudo_etiqueta,
            largura_mm=self.config_padrao.dimensoes_etiqueta.get('largura', 100),
            altura_mm=self.config_padrao.dimensoes_etiqueta.get('altura', 60)
        )
    
    def gerar_etiqueta_rastreamento(self,
                                   rastreamento_id: int,
                                   tipo: str = 'RASTREAMENTO',
                                   conteudo_personalizado: Optional[Dict[str, Any]] = None) -> Etiqueta:
        """
        Gera uma etiqueta de rastreamento.
        
        Args:
            rastreamento_id: ID do rastreamento
            tipo: Tipo da etiqueta
            conteudo_personalizado: Conteúdo personalizado da etiqueta
            
        Returns:
            Etiqueta criada
        """
        rastreamento = RastreamentoEntrega.objects.get(id=rastreamento_id)
        
        conteudo = conteudo_personalizado or {
            'codigo_rastreamento': rastreamento.codigo_rastreamento,
            'destinatario': rastreamento.nome_destinatario or '',
            'endereco': rastreamento.endereco_entrega or '',
            'transportadora': rastreamento.transportadora.nome if rastreamento.transportadora else '',
            'status': rastreamento.status_atual
        }
        
        etiqueta = Etiqueta.objects.create(
            rastreamento_entrega=rastreamento,
            tipo=tipo,
            conteudo=conteudo,
            largura_mm=self.config_padrao.dimensoes_etiqueta.get('largura', 100),
            altura_mm=self.config_padrao.dimensoes_etiqueta.get('altura', 60)
        )
        
        logger.info(f"Etiqueta de rastreamento gerada: {etiqueta.codigo}")
        return etiqueta
    
    def obter_provas_pendentes(self,
                              dias_atraso: Optional[int] = None) -> List[ProvaEntrega]:
        """
        Obtém provas de entrega pendentes de validação.
        
        Args:
            dias_atraso: Filtrar por dias de atraso
            
        Returns:
            Lista de provas pendentes
        """
        queryset = ProvaEntrega.objects.filter(
            status__in=['PENDENTE', 'EM_ANDAMENTO'],
            validada=False
        ).select_related('rastreamento_entrega')
        
        if dias_atraso:
            data_limite = timezone.now() - timedelta(days=dias_atraso)
            queryset = queryset.filter(data_entrega__lte=data_limite)
        
        return list(queryset.order_by('data_entrega'))
    
    def obter_estatisticas_pod(self,
                              data_inicio: Optional[datetime.date] = None,
                              data_fim: Optional[datetime.date] = None) -> Dict[str, Any]:
        """
        Obtém estatísticas de POD.
        
        Args:
            data_inicio: Data de início do período
            data_fim: Data de fim do período
            
        Returns:
            Dicionário com estatísticas
        """
        queryset = ProvaEntrega.objects.all()
        
        if data_inicio:
            queryset = queryset.filter(data_entrega__date__gte=data_inicio)
        
        if data_fim:
            queryset = queryset.filter(data_entrega__date__lte=data_fim)
        
        stats = {
            'total_provas': queryset.count(),
            'provas_pendentes': queryset.filter(status='PENDENTE').count(),
            'provas_validadas': queryset.filter(validada=True).count(),
            'provas_por_tipo': dict(queryset.values('tipo_entrega').annotate(
                count=Count('id')
            ).values_list('tipo_entrega', 'count')),
            'provas_com_gps': queryset.filter(
                latitude__isnull=False,
                longitude__isnull=False
            ).count(),
            'provas_com_assinatura': queryset.filter(
                assinatura__isnull=False
            ).count(),
            'tempo_medio_validacao': queryset.filter(
                validada=True,
                data_validacao__isnull=False
            ).aggregate(
                tempo_medio=Avg(F('data_validacao') - F('data_entrega'))
            )['tempo_medio']
        }
        
        return stats


# Instância global do serviço (criada lazy quando necessário)
# pod_service = PODService()
