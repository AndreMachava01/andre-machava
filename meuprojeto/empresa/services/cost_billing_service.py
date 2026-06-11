"""
Serviço para gestão de custos e faturamento logístico.
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, date, timedelta
from decimal import Decimal
from django.db.models import Q, F, Count, Sum, Avg, Min, Max
from django.utils import timezone
from django.core.exceptions import ValidationError

from ..models_cost_billing import (
    CentroCusto, TipoCusto, CustoLogistico, RateioCusto,
    FaturamentoFrete, ItemFaturamento, ConfiguracaoFaturamento
)
from ..models_stock import RastreamentoEntrega, Transportadora, VeiculoInterno

logger = logging.getLogger(__name__)


class CostBillingService:
    """Serviço para gestão de custos e faturamento logístico."""
    
    def __init__(self):
        self._config_padrao = None
    
    @property
    def config_padrao(self):
        """Obtém a configuração padrão de faturamento."""
        if self._config_padrao is None:
            self._config_padrao = self._get_configuracao_padrao()
        return self._config_padrao
    
    def _get_configuracao_padrao(self) -> ConfiguracaoFaturamento:
        """Obtém a configuração padrão de faturamento."""
        try:
            return ConfiguracaoFaturamento.objects.get(padrao=True, ativo=True)
        except ConfiguracaoFaturamento.DoesNotExist:
            # Criar configuração padrão se não existir
            return ConfiguracaoFaturamento.objects.create(
                nome='Configuração Padrão',
                padrao=True,
                ativo=True
            )
    
    def registrar_custo_logistico(self,
                                rastreamento_id: Optional[int],
                                tipo_custo_id: int,
                                centro_custo_id: int,
                                descricao: str,
                                valor: Decimal,
                                data_custo: Optional[date] = None,
                                numero_documento: str = '',
                                arquivo_comprovante=None,
                                criado_por_id: Optional[int] = None) -> CustoLogistico:
        """
        Registra um novo custo logístico.
        
        Args:
            rastreamento_id: ID do rastreamento (opcional)
            tipo_custo_id: ID do tipo de custo
            centro_custo_id: ID do centro de custo
            descricao: Descrição do custo
            valor: Valor do custo
            data_custo: Data do custo
            numero_documento: Número do documento
            arquivo_comprovante: Arquivo de comprovante
            criado_por_id: ID do usuário que criou
            
        Returns:
            CustoLogistico criado
        """
        try:
            tipo_custo = TipoCusto.objects.get(id=tipo_custo_id)
            centro_custo = CentroCusto.objects.get(id=centro_custo_id)
            
            custo = CustoLogistico.objects.create(
                rastreamento_entrega_id=rastreamento_id,
                tipo_custo=tipo_custo,
                centro_custo=centro_custo,
                descricao=descricao,
                valor=valor,
                data_custo=data_custo or timezone.now().date(),
                numero_documento=numero_documento,
                arquivo_comprovante=arquivo_comprovante,
                criado_por_id=criado_por_id,
                status='PENDENTE'
            )
            
            # Aplicar rateio automático se configurado
            if tipo_custo.rateio_automatico:
                self._aplicar_rateio_automatico(custo)
            
            logger.info(f"Custo logístico registrado: {custo.codigo}")
            return custo
            
        except Exception as e:
            logger.error(f"Erro ao registrar custo logístico: {e}")
            raise
    
    def _aplicar_rateio_automatico(self, custo: CustoLogistico):
        """Aplica rateio automático baseado no tipo de custo."""
        try:
            # Obter centros de custo relacionados
            centros_relacionados = self._obter_centros_relacionados(custo.centro_custo)
            
            if not centros_relacionados:
                return
            
            # Calcular valor por centro
            valor_por_centro = custo.valor / len(centros_relacionados)
            percentual_por_centro = Decimal('100.00') / len(centros_relacionados)
            
            for centro in centros_relacionados:
                RateioCusto.objects.create(
                    custo_logistico=custo,
                    centro_custo_destino=centro,
                    valor_rateado=valor_por_centro,
                    percentual_rateio=percentual_por_centro,
                    criterio_rateio='AUTOMATICO',
                    status='APROVADO'
                )
            
            custo.status = 'RATEADO'
            custo.valor_rateado = custo.valor
            custo.percentual_rateio = Decimal('100.00')
            custo.save()
            
            logger.info(f"Rateio automático aplicado para custo {custo.codigo}")
            
        except Exception as e:
            logger.error(f"Erro ao aplicar rateio automático: {e}")
    
    def _obter_centros_relacionados(self, centro_origem: CentroCusto) -> List[CentroCusto]:
        """Obtém centros de custo relacionados para rateio."""
        # Por enquanto, retornar centros do mesmo tipo
        return CentroCusto.objects.filter(
            tipo=centro_origem.tipo,
            ativo=True
        ).exclude(id=centro_origem.id)
    
    def aprovar_custo_logistico(self,
                               custo_id: int,
                               aprovado_por_id: int,
                               observacoes: str = '') -> CustoLogistico:
        """
        Aprova um custo logístico.
        
        Args:
            custo_id: ID do custo
            aprovado_por_id: ID do usuário que aprovou
            observacoes: Observações da aprovação
            
        Returns:
            CustoLogistico aprovado
        """
        try:
            custo = CustoLogistico.objects.get(id=custo_id)
            
            if custo.status != 'PENDENTE':
                raise ValueError("Custo não está no status 'PENDENTE'")
            
            custo.status = 'APROVADO'
            custo.aprovado_por_id = aprovado_por_id
            custo.data_aprovacao = timezone.now()
            custo.observacoes_aprovacao = observacoes
            custo.save()
            
            logger.info(f"Custo logístico aprovado: {custo.codigo}")
            return custo
            
        except Exception as e:
            logger.error(f"Erro ao aprovar custo logístico: {e}")
            raise
    
    def rejeitar_custo_logistico(self,
                                custo_id: int,
                                rejeitado_por_id: int,
                                motivo_rejeicao: str) -> CustoLogistico:
        """
        Rejeita um custo logístico.
        
        Args:
            custo_id: ID do custo
            rejeitado_por_id: ID do usuário que rejeitou
            motivo_rejeicao: Motivo da rejeição
            
        Returns:
            CustoLogistico rejeitado
        """
        try:
            custo = CustoLogistico.objects.get(id=custo_id)
            
            if custo.status != 'PENDENTE':
                raise ValueError("Custo não está no status 'PENDENTE'")
            
            custo.status = 'REJEITADO'
            custo.aprovado_por_id = rejeitado_por_id
            custo.data_aprovacao = timezone.now()
            custo.observacoes_aprovacao = motivo_rejeicao
            custo.save()
            
            logger.info(f"Custo logístico rejeitado: {custo.codigo}")
            return custo
            
        except Exception as e:
            logger.error(f"Erro ao rejeitar custo logístico: {e}")
            raise
    
    def criar_rateio_manual(self,
                           custo_id: int,
                           rateios: List[Dict[str, Any]],
                           criado_por_id: Optional[int] = None) -> List[RateioCusto]:
        """
        Cria rateio manual para um custo.
        
        Args:
            custo_id: ID do custo
            rateios: Lista de rateios com centro_custo_id, valor_rateado, percentual_rateio
            criado_por_id: ID do usuário que criou
            
        Returns:
            Lista de RateioCusto criados
        """
        try:
            custo = CustoLogistico.objects.get(id=custo_id)
            
            # Validar total dos rateios
            total_rateado = sum(Decimal(str(r['valor_rateado'])) for r in rateios)
            if abs(total_rateado - custo.valor) > Decimal('0.01'):
                raise ValueError("Total dos rateios deve ser igual ao valor do custo")
            
            rateios_criados = []
            
            for rateio_data in rateios:
                centro_custo = CentroCusto.objects.get(id=rateio_data['centro_custo_id'])
                
                rateio = RateioCusto.objects.create(
                    custo_logistico=custo,
                    centro_custo_destino=centro_custo,
                    valor_rateado=Decimal(str(rateio_data['valor_rateado'])),
                    percentual_rateio=Decimal(str(rateio_data['percentual_rateio'])),
                    criterio_rateio='MANUAL',
                    status='PENDENTE'
                )
                
                rateios_criados.append(rateio)
            
            # Atualizar custo
            custo.valor_rateado = total_rateado
            custo.percentual_rateio = Decimal('100.00')
            custo.status = 'RATEADO'
            custo.save()
            
            logger.info(f"Rateio manual criado para custo {custo.codigo}")
            return rateios_criados
            
        except Exception as e:
            logger.error(f"Erro ao criar rateio manual: {e}")
            raise
    
    def gerar_faturamento_frete(self,
                               cliente_dados: Dict[str, Any],
                               rastreamentos_ids: List[int],
                               periodo_inicio: date,
                               periodo_fim: date,
                               emitido_por_id: Optional[int] = None,
                               observacoes: str = '',
                               desconto_percentual: Decimal = Decimal('0.00')) -> FaturamentoFrete:
        """
        Gera faturamento de frete para um cliente.
        
        Args:
            cliente_dados: Dados do cliente
            rastreamentos_ids: Lista de IDs dos rastreamentos
            periodo_inicio: Data de início do período
            periodo_fim: Data de fim do período
            emitido_por_id: ID do usuário que emitiu
            observacoes: Observações da fatura
            desconto_percentual: Percentual de desconto
            
        Returns:
            FaturamentoFrete criado
        """
        try:
            config = self.config_padrao
            
            # Validar desconto
            if desconto_percentual > config.desconto_maximo_percentual:
                raise ValueError(f"Desconto máximo permitido: {config.desconto_maximo_percentual}%")
            
            # Obter rastreamentos
            rastreamentos = RastreamentoEntrega.objects.filter(
                id__in=rastreamentos_ids,
                status_atual__in=['ENTREGUE', 'ENTREGUE_PARCIAL']
            )
            
            if not rastreamentos.exists():
                raise ValueError("Nenhum rastreamento válido encontrado")
            
            # Calcular valor total
            valor_total = Decimal('0.00')
            for rastreamento in rastreamentos:
                custo_frete = rastreamento.custo_estimado or Decimal('0.00')
                valor_total += custo_frete
            
            # Aplicar desconto
            valor_desconto = valor_total * (desconto_percentual / Decimal('100.00'))
            valor_liquido = valor_total - valor_desconto
            
            # Criar faturamento
            faturamento = FaturamentoFrete.objects.create(
                serie_fatura=config.serie_padrao,
                cliente_nome=cliente_dados['nome'],
                cliente_documento=cliente_dados['documento'],
                cliente_endereco=cliente_dados['endereco'],
                cliente_email=cliente_dados.get('email', ''),
                periodo_inicio=periodo_inicio,
                periodo_fim=periodo_fim,
                data_emissao=timezone.now().date(),
                data_vencimento=timezone.now().date() + timedelta(days=config.prazo_pagamento_dias),
                valor_total=valor_total,
                valor_desconto=valor_desconto,
                valor_liquido=valor_liquido,
                observacoes=observacoes,
                instrucoes_pagamento=config.incluir_instrucoes_pagamento,
                emitido_por_id=emitido_por_id,
                status='RASCUNHO'
            )
            
            # Criar itens da fatura
            for rastreamento in rastreamentos:
                custo_frete = rastreamento.custo_estimado or Decimal('0.00')
                
                ItemFaturamento.objects.create(
                    faturamento=faturamento,
                    rastreamento_entrega=rastreamento,
                    descricao=f"Frete - {rastreamento.codigo_rastreamento}",
                    quantidade=1,
                    valor_unitario=custo_frete,
                    valor_total=custo_frete,
                    data_servico=rastreamento.data_entrega or rastreamento.data_criacao.date()
                )
            
            logger.info(f"Faturamento gerado: {faturamento.numero_fatura}")
            return faturamento
            
        except Exception as e:
            logger.error(f"Erro ao gerar faturamento: {e}")
            raise
    
    def enviar_faturamento(self, faturamento_id: int) -> FaturamentoFrete:
        """
        Envia faturamento para o cliente.
        
        Args:
            faturamento_id: ID do faturamento
            
        Returns:
            FaturamentoFrete enviado
        """
        try:
            faturamento = FaturamentoFrete.objects.get(id=faturamento_id)
            
            if faturamento.status != 'RASCUNHO':
                raise ValueError("Faturamento não está no status 'RASCUNHO'")
            
            faturamento.status = 'ENVIADO'
            faturamento.save()
            
            # Aqui você implementaria o envio real por email
            # Por enquanto, apenas log
            logger.info(f"Faturamento enviado: {faturamento.numero_fatura}")
            
            return faturamento
            
        except Exception as e:
            logger.error(f"Erro ao enviar faturamento: {e}")
            raise
    
    def marcar_faturamento_pago(self, faturamento_id: int, data_pagamento: Optional[date] = None) -> FaturamentoFrete:
        """
        Marca faturamento como pago.
        
        Args:
            faturamento_id: ID do faturamento
            data_pagamento: Data do pagamento
            
        Returns:
            FaturamentoFrete marcado como pago
        """
        try:
            faturamento = FaturamentoFrete.objects.get(id=faturamento_id)
            
            if faturamento.status not in ['ENVIADO', 'VENCIDO']:
                raise ValueError("Faturamento não pode ser marcado como pago")
            
            faturamento.status = 'PAGO'
            faturamento.data_pagamento = data_pagamento or timezone.now().date()
            faturamento.save()
            
            logger.info(f"Faturamento marcado como pago: {faturamento.numero_fatura}")
            return faturamento
            
        except Exception as e:
            logger.error(f"Erro ao marcar faturamento como pago: {e}")
            raise
    
    def obter_estatisticas_custos(self,
                                 data_inicio: Optional[date] = None,
                                 data_fim: Optional[date] = None) -> Dict[str, Any]:
        """
        Obtém estatísticas de custos.
        
        Args:
            data_inicio: Data de início do período
            data_fim: Data de fim do período
            
        Returns:
            Dicionário com estatísticas
        """
        queryset = CustoLogistico.objects.all()
        
        if data_inicio:
            queryset = queryset.filter(data_custo__gte=data_inicio)
        
        if data_fim:
            queryset = queryset.filter(data_custo__lte=data_fim)
        
        stats = {
            'total_custos': queryset.count(),
            'valor_total': queryset.aggregate(
                total=Sum('valor')
            )['total'] or Decimal('0.00'),
            'custos_pendentes': queryset.filter(status='PENDENTE').count(),
            'custos_aprovados': queryset.filter(status='APROVADO').count(),
            'custos_rateados': queryset.filter(status='RATEADO').count(),
            'custos_por_tipo': dict(queryset.values('tipo_custo__nome').annotate(
                count=Count('id'),
                valor=Sum('valor')
            ).values_list('tipo_custo__nome', 'valor')),
            'custos_por_centro': dict(queryset.values('centro_custo__nome').annotate(
                count=Count('id'),
                valor=Sum('valor')
            ).values_list('centro_custo__nome', 'valor')),
        }
        
        return stats
    
    def obter_estatisticas_faturamento(self,
                                      data_inicio: Optional[date] = None,
                                      data_fim: Optional[date] = None) -> Dict[str, Any]:
        """
        Obtém estatísticas de faturamento.
        
        Args:
            data_inicio: Data de início do período
            data_fim: Data de fim do período
            
        Returns:
            Dicionário com estatísticas
        """
        queryset = FaturamentoFrete.objects.all()
        
        if data_inicio:
            queryset = queryset.filter(data_emissao__gte=data_inicio)
        
        if data_fim:
            queryset = queryset.filter(data_emissao__lte=data_fim)
        
        stats = {
            'total_faturas': queryset.count(),
            'valor_total_faturado': queryset.aggregate(
                total=Sum('valor_liquido')
            )['total'] or Decimal('0.00'),
            'faturas_pagas': queryset.filter(status='PAGO').count(),
            'faturas_pendentes': queryset.filter(status='ENVIADO').count(),
            'faturas_vencidas': queryset.filter(status='VENCIDO').count(),
            'valor_pendente': queryset.filter(
                status__in=['ENVIADO', 'VENCIDO']
            ).aggregate(
                total=Sum('valor_liquido')
            )['total'] or Decimal('0.00'),
            'valor_pago': queryset.filter(status='PAGO').aggregate(
                total=Sum('valor_liquido')
            )['total'] or Decimal('0.00'),
        }
        
        return stats


# Instância global do serviço
cost_billing_service = CostBillingService()
