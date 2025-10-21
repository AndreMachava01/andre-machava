"""
Serviço para alocação automática de VeiculoInterno vs Transportadora por custo/SLA.
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
from django.db.models import Q, F, Count, Sum, Avg, Min, Max
from django.utils import timezone
from django.core.exceptions import ValidationError

from ..models_stock import (
    RastreamentoEntrega, Transportadora, VeiculoInterno, 
    EventoRastreamento, NotificacaoLogisticaUnificada
)
from ..models_routing import ZonaEntrega, Rota, PlanejamentoEntrega
from ..services.pricing import calculate_quote, PricingItem
from ..services.logistica_ops import confirmar_coleta, iniciar_transporte

logger = logging.getLogger(__name__)


class AllocationCriteria:
    """Critérios para alocação automática."""
    
    def __init__(self, 
                 priorizar_custo: bool = True,
                 priorizar_sla: bool = False,
                 peso_custo: float = 0.7,
                 peso_sla: float = 0.3,
                 peso_capacidade: float = 0.2,
                 peso_disponibilidade: float = 0.1,
                 custo_maximo_diferenca: Decimal = Decimal('50.00'),
                 sla_maximo_diferenca_dias: int = 2,
                 considerar_zonas: bool = True,
                 considerar_janelas_tempo: bool = True):
        """
        Inicializa critérios de alocação.
        
        Args:
            priorizar_custo: Se deve priorizar menor custo
            priorizar_sla: Se deve priorizar menor SLA
            peso_custo: Peso do custo na pontuação (0-1)
            peso_sla: Peso do SLA na pontuação (0-1)
            peso_capacidade: Peso da capacidade na pontuação (0-1)
            peso_disponibilidade: Peso da disponibilidade na pontuação (0-1)
            custo_maximo_diferenca: Diferença máxima de custo aceitável
            sla_maximo_diferenca_dias: Diferença máxima de SLA em dias
            considerar_zonas: Se deve considerar zonas de entrega
            considerar_janelas_tempo: Se deve considerar janelas de tempo
        """
        self.priorizar_custo = priorizar_custo
        self.priorizar_sla = priorizar_sla
        self.peso_custo = peso_custo
        self.peso_sla = peso_sla
        self.peso_capacidade = peso_capacidade
        self.peso_disponibilidade = peso_disponibilidade
        self.custo_maximo_diferenca = custo_maximo_diferenca
        self.sla_maximo_diferenca_dias = sla_maximo_diferenca_dias
        self.considerar_zonas = considerar_zonas
        self.considerar_janelas_tempo = considerar_janelas_tempo
        
        # Validar pesos
        total_peso = peso_custo + peso_sla + peso_capacidade + peso_disponibilidade
        if abs(total_peso - 1.0) > 0.01:
            logger.warning(f"Pesos não somam 1.0: {total_peso}")


class AllocationResult:
    """Resultado de uma alocação."""
    
    def __init__(self, 
                 rastreamento_id: int,
                 opcao_recomendada: str,  # 'VEICULO_INTERNO' ou 'TRANSPORTADORA'
                 opcao_id: int,
                 custo_estimado: Decimal,
                 sla_estimado_dias: int,
                 pontuacao: float,
                 motivo: str,
                 alternativas: List[Dict[str, Any]] = None):
        self.rastreamento_id = rastreamento_id
        self.opcao_recomendada = opcao_recomendada
        self.opcao_id = opcao_id
        self.custo_estimado = custo_estimado
        self.sla_estimado_dias = sla_estimado_dias
        self.pontuacao = pontuacao
        self.motivo = motivo
        self.alternativas = alternativas or []


class AutoAllocationService:
    """Serviço para alocação automática de recursos logísticos."""
    
    def __init__(self):
        self.criteria = AllocationCriteria()
    
    def configurar_criterios(self, criteria: AllocationCriteria):
        """Configura os critérios de alocação."""
        self.criteria = criteria
        logger.info(f"Critérios de alocação configurados: {criteria.__dict__}")
    
    def alocar_rastreamento(self, 
                           rastreamento_id: int,
                           criterios_personalizados: Optional[AllocationCriteria] = None) -> AllocationResult:
        """
        Aloca automaticamente um rastreamento para VeiculoInterno ou Transportadora.
        
        Args:
            rastreamento_id: ID do rastreamento
            criterios_personalizados: Critérios específicos para esta alocação
            
        Returns:
            AllocationResult com a recomendação
        """
        try:
            rastreamento = RastreamentoEntrega.objects.get(id=rastreamento_id)
            criteria = criterios_personalizados or self.criteria
            
            # Obter opções disponíveis
            opcoes_veiculo_interno = self._obter_opcoes_veiculo_interno(rastreamento, criteria)
            opcoes_transportadora = self._obter_opcoes_transportadora(rastreamento, criteria)
            
            # Calcular pontuações
            opcoes_veiculo_interno = self._calcular_pontuacoes(opcoes_veiculo_interno, rastreamento, criteria)
            opcoes_transportadora = self._calcular_pontuacoes(opcoes_transportadora, rastreamento, criteria)
            
            # Combinar todas as opções
            todas_opcoes = opcoes_veiculo_interno + opcoes_transportadora
            
            if not todas_opcoes:
                raise ValueError("Nenhuma opção de alocação disponível")
            
            # Ordenar por pontuação (maior pontuação = melhor opção)
            todas_opcoes.sort(key=lambda x: x['pontuacao'], reverse=True)
            
            # Selecionar melhor opção
            melhor_opcao = todas_opcoes[0]
            
            # Criar resultado
            resultado = AllocationResult(
                rastreamento_id=rastreamento_id,
                opcao_recomendada=melhor_opcao['tipo'],
                opcao_id=melhor_opcao['id'],
                custo_estimado=melhor_opcao['custo'],
                sla_estimado_dias=melhor_opcao['sla_dias'],
                pontuacao=melhor_opcao['pontuacao'],
                motivo=melhor_opcao['motivo'],
                alternativas=todas_opcoes[1:6]  # Top 5 alternativas
            )
            
            logger.info(f"Alocação recomendada para {rastreamento.codigo_rastreamento}: "
                       f"{melhor_opcao['tipo']} ID {melhor_opcao['id']} "
                       f"(pontuação: {melhor_opcao['pontuacao']:.2f})")
            
            return resultado
            
        except Exception as e:
            logger.error(f"Erro na alocação automática para rastreamento {rastreamento_id}: {e}")
            raise
    
    def _obter_opcoes_veiculo_interno(self, 
                                    rastreamento: RastreamentoEntrega, 
                                    criteria: AllocationCriteria) -> List[Dict[str, Any]]:
        """Obtém opções de veículos internos disponíveis."""
        opcoes = []
        
        # Filtrar veículos ativos e disponíveis
        veiculos = VeiculoInterno.objects.filter(
            ativo=True,
            sucursal=rastreamento.sucursal_origem  # Assumindo que existe este campo
        )
        
        for veiculo in veiculos:
            # Verificar disponibilidade
            if not self._verificar_disponibilidade_veiculo(veiculo, rastreamento):
                continue
            
            # Calcular custo estimado (custo operacional interno)
            custo_estimado = self._calcular_custo_veiculo_interno(veiculo, rastreamento)
            
            # Calcular SLA estimado
            sla_estimado = self._calcular_sla_veiculo_interno(veiculo, rastreamento)
            
            opcao = {
                'id': veiculo.id,
                'tipo': 'VEICULO_INTERNO',
                'nome': f"{veiculo.matricula} - {veiculo.modelo}",
                'custo': custo_estimado,
                'sla_dias': sla_estimado,
                'capacidade_kg': veiculo.capacidade_kg or Decimal('1000.00'),
                'capacidade_volume': veiculo.capacidade_volume or Decimal('10.00'),
                'disponibilidade': self._calcular_disponibilidade_veiculo(veiculo),
                'zona_cobertura': self._obter_zonas_cobertura_veiculo(veiculo),
                'pontuacao': 0.0,  # Será calculada depois
                'motivo': ''
            }
            
            opcoes.append(opcao)
        
        return opcoes
    
    def _obter_opcoes_transportadora(self, 
                                   rastreamento: RastreamentoEntrega, 
                                   criteria: AllocationCriteria) -> List[Dict[str, Any]]:
        """Obtém opções de transportadoras disponíveis."""
        opcoes = []
        
        # Filtrar transportadoras ativas
        transportadoras = Transportadora.objects.filter(
            ativo=True,
            tipo__in=['CORREIOS', 'DHL', 'LOCAL']  # Excluir tipos internos
        )
        
        for transportadora in transportadoras:
            # Verificar se atende a zona/região
            if not self._verificar_cobertura_transportadora(transportadora, rastreamento):
                continue
            
            # Calcular custo usando serviço de pricing
            try:
                # Criar item de pricing
                item = PricingItem(
                    weight_kg=float(rastreamento.peso_total or 1.0),
                    length_cm=10,  # Valores padrão
                    width_cm=10,
                    height_cm=10,
                    declared_value=float(rastreamento.valor_declarado or 0.0)
                )
                
                resultado_pricing = calculate_quote(
                    transportadora=transportadora,
                    items=[item]
                )
                custo_estimado = Decimal(str(resultado_pricing.total_cost))
            except Exception as e:
                logger.warning(f"Erro ao calcular custo para {transportadora.nome}: {e}")
                custo_estimado = transportadora.custo_fixo or Decimal('50.00')
            
            # SLA da transportadora
            sla_estimado = transportadora.prazo_entrega_padrao or 3
            
            opcao = {
                'id': transportadora.id,
                'tipo': 'TRANSPORTADORA',
                'nome': transportadora.nome,
                'custo': custo_estimado,
                'sla_dias': sla_estimado,
                'capacidade_kg': transportadora.peso_maximo or Decimal('50000.00'),
                'capacidade_volume': transportadora.volume_maximo or Decimal('100.00'),
                'disponibilidade': 1.0,  # Transportadoras sempre disponíveis
                'zona_cobertura': self._obter_zonas_cobertura_transportadora(transportadora),
                'pontuacao': 0.0,  # Será calculada depois
                'motivo': ''
            }
            
            opcoes.append(opcao)
        
        return opcoes
    
    def _calcular_pontuacoes(self, 
                           opcoes: List[Dict[str, Any]], 
                           rastreamento: RastreamentoEntrega, 
                           criteria: AllocationCriteria) -> List[Dict[str, Any]]:
        """Calcula pontuações para todas as opções."""
        if not opcoes:
            return opcoes
        
        # Normalizar valores para pontuação
        custos = [opcao['custo'] for opcao in opcoes]
        slas = [opcao['sla_dias'] for opcao in opcoes]
        capacidades = [opcao['capacidade_kg'] for opcao in opcoes]
        disponibilidades = [opcao['disponibilidade'] for opcao in opcoes]
        
        min_custo = min(custos)
        max_custo = max(custos)
        min_sla = min(slas)
        max_sla = max(slas)
        min_capacidade = min(capacidades)
        max_capacidade = max(capacidades)
        
        for opcao in opcoes:
            # Normalizar custo (menor custo = maior pontuação)
            if max_custo > min_custo:
                pontuacao_custo = 1.0 - ((opcao['custo'] - min_custo) / (max_custo - min_custo))
            else:
                pontuacao_custo = 1.0
            
            # Normalizar SLA (menor SLA = maior pontuação)
            if max_sla > min_sla:
                pontuacao_sla = 1.0 - ((opcao['sla_dias'] - min_sla) / (max_sla - min_sla))
            else:
                pontuacao_sla = 1.0
            
            # Normalizar capacidade (maior capacidade = maior pontuação)
            if max_capacidade > min_capacidade:
                pontuacao_capacidade = (opcao['capacidade_kg'] - min_capacidade) / (max_capacidade - min_capacidade)
            else:
                pontuacao_capacidade = 1.0
            
            # Disponibilidade já está normalizada (0-1)
            pontuacao_disponibilidade = opcao['disponibilidade']
            
            # Calcular pontuação final
            pontuacao_final = (
                pontuacao_custo * criteria.peso_custo +
                pontuacao_sla * criteria.peso_sla +
                pontuacao_capacidade * criteria.peso_capacidade +
                pontuacao_disponibilidade * criteria.peso_disponibilidade
            )
            
            opcao['pontuacao'] = pontuacao_final
            
            # Gerar motivo da pontuação
            motivo = self._gerar_motivo_pontuacao(opcao, criteria)
            opcao['motivo'] = motivo
        
        return opcoes
    
    def _verificar_disponibilidade_veiculo(self, 
                                         veiculo: VeiculoInterno, 
                                         rastreamento: RastreamentoEntrega) -> bool:
        """Verifica se o veículo está disponível para o rastreamento."""
        # Verificar se o veículo não está em manutenção
        if not veiculo.ativo:
            return False
        
        # Verificar se há rotas ativas para o veículo na data
        data_entrega = rastreamento.data_prevista_entrega or timezone.now().date()
        rotas_ativas = Rota.objects.filter(
            veiculo=veiculo,
            data_planeamento=data_entrega,
            status__in=['PLANEADA', 'EM_ANDAMENTO']
        )
        
        # Se já tem muitas rotas, considerar indisponível
        if rotas_ativas.count() >= 3:  # Limite arbitrário
            return False
        
        return True
    
    def _calcular_custo_veiculo_interno(self, 
                                       veiculo: VeiculoInterno, 
                                       rastreamento: RastreamentoEntrega) -> Decimal:
        """Calcula custo estimado para veículo interno."""
        # Custo base por km
        custo_por_km = Decimal('0.50')  # Valor padrão
        
        # Distância estimada (simplificado)
        distancia_estimada = Decimal('50.00')  # km
        
        # Custo de combustível
        custo_combustivel = distancia_estimada * custo_por_km
        
        # Custo de motorista (proporcional)
        custo_motorista = Decimal('20.00')  # Valor fixo por entrega
        
        # Custo de manutenção (proporcional)
        custo_manutencao = Decimal('5.00')  # Valor fixo por entrega
        
        return custo_combustivel + custo_motorista + custo_manutencao
    
    def _calcular_sla_veiculo_interno(self, 
                                    veiculo: VeiculoInterno, 
                                    rastreamento: RastreamentoEntrega) -> int:
        """Calcula SLA estimado para veículo interno."""
        # SLA base para veículos internos (geralmente mais rápido)
        sla_base = 1  # 1 dia
        
        # Ajustar baseado na distância/região
        # Por enquanto, retornar valor fixo
        return sla_base
    
    def _calcular_disponibilidade_veiculo(self, veiculo: VeiculoInterno) -> float:
        """Calcula disponibilidade do veículo (0-1)."""
        # Verificar status do veículo
        if not veiculo.ativo:
            return 0.0
        
        # Verificar rotas ativas hoje
        hoje = timezone.now().date()
        rotas_hoje = Rota.objects.filter(
            veiculo=veiculo,
            data_planeamento=hoje,
            status__in=['PLANEADA', 'EM_ANDAMENTO']
        ).count()
        
        # Calcular disponibilidade baseada no número de rotas
        max_rotas_dia = 5  # Limite arbitrário
        disponibilidade = max(0.0, 1.0 - (rotas_hoje / max_rotas_dia))
        
        return disponibilidade
    
    def _verificar_cobertura_transportadora(self, 
                                          transportadora: Transportadora, 
                                          rastreamento: RastreamentoEntrega) -> bool:
        """Verifica se a transportadora atende a região do rastreamento."""
        # Por enquanto, assumir que todas as transportadoras ativas atendem
        # Em um sistema real, verificaríamos zonas de cobertura
        return transportadora.ativo
    
    def _obter_zonas_cobertura_veiculo(self, veiculo: VeiculoInterno) -> List[str]:
        """Obtém zonas de cobertura do veículo."""
        # Por enquanto, retornar lista vazia
        # Em um sistema real, consultaríamos tabela de zonas por veículo
        return []
    
    def _obter_zonas_cobertura_transportadora(self, transportadora: Transportadora) -> List[str]:
        """Obtém zonas de cobertura da transportadora."""
        # Por enquanto, retornar lista vazia
        # Em um sistema real, consultaríamos tabela de zonas por transportadora
        return []
    
    def _gerar_motivo_pontuacao(self, opcao: Dict[str, Any], criteria: AllocationCriteria) -> str:
        """Gera motivo explicativo da pontuação."""
        motivo_parts = []
        
        if criteria.priorizar_custo:
            motivo_parts.append(f"Custo: R$ {opcao['custo']:.2f}")
        
        if criteria.priorizar_sla:
            motivo_parts.append(f"SLA: {opcao['sla_dias']} dias")
        
        motivo_parts.append(f"Capacidade: {opcao['capacidade_kg']} kg")
        motivo_parts.append(f"Disponibilidade: {opcao['disponibilidade']:.1%}")
        
        return " | ".join(motivo_parts)
    
    def aplicar_alocacao(self, resultado: AllocationResult) -> bool:
        """
        Aplica a alocação recomendada ao rastreamento.
        
        Args:
            resultado: Resultado da alocação
            
        Returns:
            True se aplicado com sucesso
        """
        try:
            rastreamento = RastreamentoEntrega.objects.get(id=resultado.rastreamento_id)
            
            if resultado.opcao_recomendada == 'VEICULO_INTERNO':
                rastreamento.veiculo_interno_id = resultado.opcao_id
                rastreamento.transportadora = None
                rastreamento.tipo_transporte = 'INTERNO'
            else:
                rastreamento.transportadora_id = resultado.opcao_id
                rastreamento.veiculo_interno = None
                rastreamento.tipo_transporte = 'EXTERNO'
            
            rastreamento.custo_estimado = resultado.custo_estimado
            rastreamento.sla_estimado_dias = resultado.sla_estimado_dias
            rastreamento.data_atualizacao = timezone.now()
            rastreamento.save()
            
            # Criar evento de rastreamento
            EventoRastreamento.objects.create(
                rastreamento=rastreamento,
                tipo_evento='ALOCADO',
                descricao=f"Alocação automática: {resultado.opcao_recomendada} "
                         f"(pontuação: {resultado.pontuacao:.2f}) - {resultado.motivo}",
                localizacao="Sistema de Alocação",
                data_evento=timezone.now()
            )
            
            logger.info(f"Alocação aplicada para {rastreamento.codigo_rastreamento}: "
                       f"{resultado.opcao_recomendada} ID {resultado.opcao_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Erro ao aplicar alocação: {e}")
            return False
    
    def alocar_lote(self, 
                   rastreamentos_ids: List[int],
                   criterios_personalizados: Optional[AllocationCriteria] = None) -> List[AllocationResult]:
        """
        Aloca múltiplos rastreamentos em lote.
        
        Args:
            rastreamentos_ids: Lista de IDs dos rastreamentos
            criterios_personalizados: Critérios específicos
            
        Returns:
            Lista de resultados de alocação
        """
        resultados = []
        
        for rastreamento_id in rastreamentos_ids:
            try:
                resultado = self.alocar_rastreamento(rastreamento_id, criterios_personalizados)
                resultados.append(resultado)
            except Exception as e:
                logger.error(f"Erro na alocação do rastreamento {rastreamento_id}: {e}")
                # Criar resultado de erro
                erro_resultado = AllocationResult(
                    rastreamento_id=rastreamento_id,
                    opcao_recomendada='ERRO',
                    opcao_id=0,
                    custo_estimado=Decimal('0.00'),
                    sla_estimado_dias=0,
                    pontuacao=0.0,
                    motivo=f"Erro na alocação: {str(e)}"
                )
                resultados.append(erro_resultado)
        
        return resultados
    
    def obter_estatisticas_alocacao(self, 
                                   data_inicio: Optional[datetime.date] = None,
                                   data_fim: Optional[datetime.date] = None) -> Dict[str, Any]:
        """
        Obtém estatísticas de alocação.
        
        Args:
            data_inicio: Data de início do período
            data_fim: Data de fim do período
            
        Returns:
            Dicionário com estatísticas
        """
        queryset = RastreamentoEntrega.objects.all()
        
        if data_inicio:
            queryset = queryset.filter(data_criacao__date__gte=data_inicio)
        
        if data_fim:
            queryset = queryset.filter(data_criacao__date__lte=data_fim)
        
        stats = {
            'total_rastreamentos': queryset.count(),
            'alocados_veiculo_interno': queryset.filter(
                veiculo_interno__isnull=False
            ).count(),
            'alocados_transportadora': queryset.filter(
                transportadora__isnull=False
            ).count(),
            'nao_alocados': queryset.filter(
                veiculo_interno__isnull=True,
                transportadora__isnull=True
            ).count(),
            'custo_medio_veiculo_interno': queryset.filter(
                veiculo_interno__isnull=False
            ).aggregate(
                custo_medio=Avg('custo_estimado')
            )['custo_medio'] or Decimal('0.00'),
            'custo_medio_transportadora': queryset.filter(
                transportadora__isnull=False
            ).aggregate(
                custo_medio=Avg('custo_estimado')
            )['custo_medio'] or Decimal('0.00'),
            'sla_medio_veiculo_interno': queryset.filter(
                veiculo_interno__isnull=False
            ).aggregate(
                sla_medio=Avg('sla_estimado_dias')
            )['sla_medio'] or 0,
            'sla_medio_transportadora': queryset.filter(
                transportadora__isnull=False
            ).aggregate(
                sla_medio=Avg('sla_estimado_dias')
            )['sla_medio'] or 0,
        }
        
        return stats


# Instância global do serviço
auto_allocation_service = AutoAllocationService()
