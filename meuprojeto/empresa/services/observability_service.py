"""
Serviço para observabilidade e métricas logísticas.
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, date, timedelta
from decimal import Decimal
from django.db.models import Q, F, Count, Sum, Avg, Min, Max
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User

from ..models_observability import (
    AuditoriaTransicao, MetricaLogistica, ValorMetrica,
    RelatorioLogistico, ExecucaoRelatorio, APILog,
    ConfiguracaoObservabilidade
)
from ..models_stock import RastreamentoEntrega, Transportadora, VeiculoInterno

logger = logging.getLogger(__name__)


class ObservabilityService:
    """Serviço para observabilidade e métricas logísticas."""
    
    def __init__(self):
        self._config_padrao = None
    
    @property
    def config_padrao(self):
        """Obtém a configuração padrão de observabilidade."""
        if self._config_padrao is None:
            self._config_padrao = self._get_configuracao_padrao()
        return self._config_padrao
    
    def _get_configuracao_padrao(self) -> ConfiguracaoObservabilidade:
        """Obtém a configuração padrão de observabilidade."""
        try:
            return ConfiguracaoObservabilidade.objects.get(padrao=True, ativo=True)
        except ConfiguracaoObservabilidade.DoesNotExist:
            # Criar configuração padrão se não existir
            return ConfiguracaoObservabilidade.objects.create(
                nome='Configuração Padrão',
                padrao=True,
                ativo=True
            )
    
    def registrar_auditoria_transicao(self,
                                     tipo_operacao: str,
                                     modelo_afetado: str,
                                     objeto_id: int,
                                     status_anterior: str = '',
                                     status_novo: str = '',
                                     dados_anteriores: Optional[Dict] = None,
                                     dados_novos: Optional[Dict] = None,
                                     contexto_operacao: Optional[Dict] = None,
                                     usuario: Optional[User] = None,
                                     ip_address: Optional[str] = None,
                                     user_agent: Optional[str] = None,
                                     session_id: Optional[str] = None,
                                     duracao_ms: Optional[int] = None,
                                     sucesso: bool = True,
                                     erro_mensagem: str = '') -> AuditoriaTransicao:
        """
        Registra auditoria de transição.
        
        Args:
            tipo_operacao: Tipo da operação
            modelo_afetado: Modelo afetado
            objeto_id: ID do objeto
            status_anterior: Status anterior
            status_novo: Status novo
            dados_anteriores: Dados anteriores
            dados_novos: Dados novos
            contexto_operacao: Contexto da operação
            usuario: Usuário que executou
            ip_address: Endereço IP
            user_agent: User agent
            session_id: ID da sessão
            duracao_ms: Duração em milissegundos
            sucesso: Se a operação foi bem-sucedida
            erro_mensagem: Mensagem de erro
            
        Returns:
            AuditoriaTransicao registrada
        """
        try:
            if not self.config_padrao.auditoria_habilitada:
                return None
            
            auditoria = AuditoriaTransicao.objects.create(
                tipo_operacao=tipo_operacao,
                modelo_afetado=modelo_afetado,
                objeto_id=objeto_id,
                status_anterior=status_anterior,
                status_novo=status_novo,
                dados_anteriores=dados_anteriores,
                dados_novos=dados_novos,
                contexto_operacao=contexto_operacao or {},
                usuario=usuario,
                ip_address=ip_address,
                user_agent=user_agent,
                session_id=session_id,
                duracao_ms=duracao_ms,
                sucesso=sucesso,
                erro_mensagem=erro_mensagem
            )
            
            logger.info(f"Auditoria registrada: {auditoria.uuid}")
            return auditoria
            
        except Exception as e:
            logger.error(f"Erro ao registrar auditoria: {e}")
            raise
    
    def calcular_metrica_otd(self,
                           data_inicio: date,
                           data_fim: date,
                           filtros: Optional[Dict] = None) -> Decimal:
        """
        Calcula métrica OTD (On-Time Delivery).
        
        Args:
            data_inicio: Data de início
            data_fim: Data de fim
            filtros: Filtros adicionais
            
        Returns:
            Percentual OTD
        """
        try:
            queryset = RastreamentoEntrega.objects.filter(
                data_criacao__date__range=[data_inicio, data_fim],
                status_atual__in=['ENTREGUE', 'ENTREGUE_PARCIAL']
            )
            
            # Aplicar filtros
            if filtros:
                if 'regiao' in filtros:
                    queryset = queryset.filter(endereco_entrega__icontains=filtros['regiao'])
                if 'transportadora' in filtros:
                    queryset = queryset.filter(transportadora__nome__icontains=filtros['transportadora'])
                if 'veiculo_interno' in filtros:
                    queryset = queryset.filter(veiculo_interno__nome__icontains=filtros['veiculo_interno'])
            
            total_entregas = queryset.count()
            if total_entregas == 0:
                return Decimal('0.00')
            
            # Calcular entregas no prazo
            entregas_no_prazo = queryset.filter(
                data_entrega__lte=F('data_prevista_entrega')
            ).count()
            
            otd_percentual = (entregas_no_prazo / total_entregas) * 100
            return Decimal(str(round(otd_percentual, 2)))
            
        except Exception as e:
            logger.error(f"Erro ao calcular OTD: {e}")
            raise
    
    def calcular_metrica_lead_time(self,
                                 data_inicio: date,
                                 data_fim: date,
                                 filtros: Optional[Dict] = None) -> Decimal:
        """
        Calcula métrica de Lead Time médio.
        
        Args:
            data_inicio: Data de início
            data_fim: Data de fim
            filtros: Filtros adicionais
            
        Returns:
            Lead Time médio em dias
        """
        try:
            queryset = RastreamentoEntrega.objects.filter(
                data_criacao__date__range=[data_inicio, data_fim],
                status_atual__in=['ENTREGUE', 'ENTREGUE_PARCIAL'],
                data_entrega__isnull=False
            )
            
            # Aplicar filtros
            if filtros:
                if 'regiao' in filtros:
                    queryset = queryset.filter(endereco_entrega__icontains=filtros['regiao'])
                if 'transportadora' in filtros:
                    queryset = queryset.filter(transportadora__nome__icontains=filtros['transportadora'])
            
            # Calcular lead time médio
            lead_times = queryset.annotate(
                lead_time=F('data_entrega') - F('data_criacao')
            ).aggregate(
                lead_time_medio=Avg('lead_time')
            )['lead_time_medio']
            
            if lead_times:
                # Converter para dias
                lead_time_dias = lead_times.total_seconds() / (24 * 3600)
                return Decimal(str(round(lead_time_dias, 2)))
            
            return Decimal('0.00')
            
        except Exception as e:
            logger.error(f"Erro ao calcular Lead Time: {e}")
            raise
    
    def calcular_metrica_custo_por_entrega(self,
                                          data_inicio: date,
                                          data_fim: date,
                                          filtros: Optional[Dict] = None) -> Decimal:
        """
        Calcula métrica de custo médio por entrega.
        
        Args:
            data_inicio: Data de início
            data_fim: Data de fim
            filtros: Filtros adicionais
            
        Returns:
            Custo médio por entrega
        """
        try:
            queryset = RastreamentoEntrega.objects.filter(
                data_criacao__date__range=[data_inicio, data_fim],
                status_atual__in=['ENTREGUE', 'ENTREGUE_PARCIAL'],
                custo_estimado__gt=0
            )
            
            # Aplicar filtros
            if filtros:
                if 'regiao' in filtros:
                    queryset = queryset.filter(endereco_entrega__icontains=filtros['regiao'])
                if 'transportadora' in filtros:
                    queryset = queryset.filter(transportadora__nome__icontains=filtros['transportadora'])
            
            # Calcular custo médio
            custo_medio = queryset.aggregate(
                custo_medio=Avg('custo_estimado')
            )['custo_medio']
            
            return custo_medio or Decimal('0.00')
            
        except Exception as e:
            logger.error(f"Erro ao calcular custo por entrega: {e}")
            raise
    
    def calcular_metrica_volume_entregue(self,
                                       data_inicio: date,
                                       data_fim: date,
                                       filtros: Optional[Dict] = None) -> Decimal:
        """
        Calcula métrica de volume total entregue.
        
        Args:
            data_inicio: Data de início
            data_fim: Data de fim
            filtros: Filtros adicionais
            
        Returns:
            Volume total entregue
        """
        try:
            queryset = RastreamentoEntrega.objects.filter(
                data_criacao__date__range=[data_inicio, data_fim],
                status_atual__in=['ENTREGUE', 'ENTREGUE_PARCIAL'],
                peso_kg__gt=0
            )
            
            # Aplicar filtros
            if filtros:
                if 'regiao' in filtros:
                    queryset = queryset.filter(endereco_entrega__icontains=filtros['regiao'])
                if 'transportadora' in filtros:
                    queryset = queryset.filter(transportadora__nome__icontains=filtros['transportadora'])
            
            # Calcular volume total
            volume_total = queryset.aggregate(
                volume_total=Sum('peso_kg')
            )['volume_total']
            
            return volume_total or Decimal('0.00')
            
        except Exception as e:
            logger.error(f"Erro ao calcular volume entregue: {e}")
            raise
    
    def calcular_metrica_taxa_excecoes(self,
                                     data_inicio: date,
                                     data_fim: date,
                                     filtros: Optional[Dict] = None) -> Decimal:
        """
        Calcula métrica de taxa de exceções.
        
        Args:
            data_inicio: Data de início
            data_fim: Data de fim
            filtros: Filtros adicionais
            
        Returns:
            Taxa de exceções em percentual
        """
        try:
            queryset = RastreamentoEntrega.objects.filter(
                data_criacao__date__range=[data_inicio, data_fim]
            )
            
            # Aplicar filtros
            if filtros:
                if 'regiao' in filtros:
                    queryset = queryset.filter(endereco_entrega__icontains=filtros['regiao'])
                if 'transportadora' in filtros:
                    queryset = queryset.filter(transportadora__nome__icontains=filtros['transportadora'])
            
            total_rastreamentos = queryset.count()
            if total_rastreamentos == 0:
                return Decimal('0.00')
            
            # Contar exceções
            excecoes = queryset.filter(
                status_atual__in=['DEVOLVIDA', 'RECUSADA', 'AVARIA', 'EXTRAVIADA']
            ).count()
            
            taxa_excecoes = (excecoes / total_rastreamentos) * 100
            return Decimal(str(round(taxa_excecoes, 2)))
            
        except Exception as e:
            logger.error(f"Erro ao calcular taxa de exceções: {e}")
            raise
    
    def calcular_metrica_utilizacao_frota(self,
                                        data_inicio: date,
                                        data_fim: date,
                                        filtros: Optional[Dict] = None) -> Decimal:
        """
        Calcula métrica de utilização da frota.
        
        Args:
            data_inicio: Data de início
            data_fim: Data de fim
            filtros: Filtros adicionais
            
        Returns:
            Percentual de utilização da frota
        """
        try:
            # Obter veículos internos ativos
            veiculos_ativos = VeiculoInterno.objects.filter(ativo=True)
            
            if not veiculos_ativos.exists():
                return Decimal('0.00')
            
            total_veiculos = veiculos_ativos.count()
            
            # Contar veículos utilizados no período
            veiculos_utilizados = RastreamentoEntrega.objects.filter(
                data_criacao__date__range=[data_inicio, data_fim],
                veiculo_interno__in=veiculos_ativos
            ).values('veiculo_interno').distinct().count()
            
            utilizacao_percentual = (veiculos_utilizados / total_veiculos) * 100
            return Decimal(str(round(utilizacao_percentual, 2)))
            
        except Exception as e:
            logger.error(f"Erro ao calcular utilização da frota: {e}")
            raise
    
    def calcular_metrica_eficiencia_rota(self,
                                       data_inicio: date,
                                       data_fim: date,
                                       filtros: Optional[Dict] = None) -> Decimal:
        """
        Calcula métrica de eficiência de rota.
        
        Args:
            data_inicio: Data de início
            data_fim: Data de fim
            filtros: Filtros adicionais
            
        Returns:
            Eficiência de rota (entregas por km)
        """
        try:
            queryset = RastreamentoEntrega.objects.filter(
                data_criacao__date__range=[data_inicio, data_fim],
                status_atual__in=['ENTREGUE', 'ENTREGUE_PARCIAL']
            )
            
            # Aplicar filtros
            if filtros:
                if 'regiao' in filtros:
                    queryset = queryset.filter(endereco_entrega__icontains=filtros['regiao'])
                if 'veiculo_interno' in filtros:
                    queryset = queryset.filter(veiculo_interno__nome__icontains=filtros['veiculo_interno'])
            
            total_entregas = queryset.count()
            
            # Calcular distância total estimada (simplificado)
            # Em um sistema real, isso viria de dados de GPS ou APIs de roteamento
            distancia_total_estimada = total_entregas * Decimal('50.0')  # 50km por entrega estimado
            
            if distancia_total_estimada > 0:
                eficiencia = total_entregas / distancia_total_estimada
                return Decimal(str(round(eficiencia, 4)))
            
            return Decimal('0.00')
            
        except Exception as e:
            logger.error(f"Erro ao calcular eficiência de rota: {e}")
            raise
    
    def calcular_todas_metricas(self,
                               data_inicio: date,
                               data_fim: date,
                               filtros: Optional[Dict] = None) -> Dict[str, Decimal]:
        """
        Calcula todas as métricas logísticas.
        
        Args:
            data_inicio: Data de início
            data_fim: Data de fim
            filtros: Filtros adicionais
            
        Returns:
            Dicionário com todas as métricas
        """
        try:
            metricas = {
                'otd': self.calcular_metrica_otd(data_inicio, data_fim, filtros),
                'lead_time': self.calcular_metrica_lead_time(data_inicio, data_fim, filtros),
                'custo_por_entrega': self.calcular_metrica_custo_por_entrega(data_inicio, data_fim, filtros),
                'volume_entregue': self.calcular_metrica_volume_entregue(data_inicio, data_fim, filtros),
                'taxa_excecoes': self.calcular_metrica_taxa_excecoes(data_inicio, data_fim, filtros),
                'utilizacao_frota': self.calcular_metrica_utilizacao_frota(data_inicio, data_fim, filtros),
                'eficiencia_rota': self.calcular_metrica_eficiencia_rota(data_inicio, data_fim, filtros),
            }
            
            return metricas
            
        except Exception as e:
            logger.error(f"Erro ao calcular métricas: {e}")
            raise
    
    def salvar_metricas_periodo(self,
                               data_referencia: date,
                               periodo_inicio: datetime,
                               periodo_fim: datetime,
                               filtros: Optional[Dict] = None) -> List[ValorMetrica]:
        """
        Salva métricas calculadas para um período.
        
        Args:
            data_referencia: Data de referência
            periodo_inicio: Início do período
            periodo_fim: Fim do período
            filtros: Filtros aplicados
            
        Returns:
            Lista de ValoresMetrica salvos
        """
        try:
            # Calcular todas as métricas
            metricas_calculadas = self.calcular_todas_metricas(
                data_referencia, data_referencia, filtros
            )
            
            valores_salvos = []
            
            for tipo_metrica, valor in metricas_calculadas.items():
                # Obter métrica
                try:
                    metrica = MetricaLogistica.objects.get(tipo_metrica=tipo_metrica.upper())
                except MetricaLogistica.DoesNotExist:
                    continue
                
                # Salvar valor
                valor_metrica, created = ValorMetrica.objects.get_or_create(
                    metrica=metrica,
                    data_referencia=data_referencia,
                    filtros=filtros or {},
                    defaults={
                        'periodo_inicio': periodo_inicio,
                        'periodo_fim': periodo_fim,
                        'valor': valor,
                        'quantidade_registros': 1,
                        'confiabilidade': Decimal('100.00')
                    }
                )
                
                if not created:
                    valor_metrica.valor = valor
                    valor_metrica.periodo_inicio = periodo_inicio
                    valor_metrica.periodo_fim = periodo_fim
                    valor_metrica.save()
                
                valores_salvos.append(valor_metrica)
            
            logger.info(f"Métricas salvas para período {data_referencia}")
            return valores_salvos
            
        except Exception as e:
            logger.error(f"Erro ao salvar métricas: {e}")
            raise
    
    def obter_estatisticas_observabilidade(self) -> Dict[str, Any]:
        """
        Obtém estatísticas de observabilidade.
        
        Returns:
            Dicionário com estatísticas
        """
        try:
            hoje = timezone.now().date()
            ultimos_30_dias = hoje - timedelta(days=30)
            
            stats = {
                'auditoria': {
                    'total_registros': AuditoriaTransicao.objects.count(),
                    'ultimos_30_dias': AuditoriaTransicao.objects.filter(
                        data_operacao__date__gte=ultimos_30_dias
                    ).count(),
                    'operacoes_por_tipo': dict(
                        AuditoriaTransicao.objects.values('tipo_operacao')
                        .annotate(count=Count('id'))
                        .values_list('tipo_operacao', 'count')
                    ),
                    'taxa_sucesso': AuditoriaTransicao.objects.aggregate(
                        taxa_sucesso=Avg('sucesso')
                    )['taxa_sucesso'] or 0
                },
                'metricas': {
                    'total_metricas': MetricaLogistica.objects.filter(ativo=True).count(),
                    'total_valores': ValorMetrica.objects.count(),
                    'ultimos_30_dias': ValorMetrica.objects.filter(
                        data_referencia__gte=ultimos_30_dias
                    ).count()
                },
                'relatorios': {
                    'total_relatorios': RelatorioLogistico.objects.filter(ativo=True).count(),
                    'execucoes_ultimos_30_dias': ExecucaoRelatorio.objects.filter(
                        data_inicio__date__gte=ultimos_30_dias
                    ).count(),
                    'execucoes_concluidas': ExecucaoRelatorio.objects.filter(
                        status='CONCLUIDO'
                    ).count()
                },
                'api_logs': {
                    'total_logs': APILog.objects.count(),
                    'ultimos_30_dias': APILog.objects.filter(
                        data_requisicao__date__gte=ultimos_30_dias
                    ).count(),
                    'tempo_resposta_medio': APILog.objects.aggregate(
                        tempo_medio=Avg('tempo_resposta_ms')
                    )['tempo_medio'] or 0
                }
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas de observabilidade: {e}")
            raise


# Instância global do serviço
observability_service = ObservabilityService()
