"""
Serviço de roteirização e planejamento logístico.
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta, time
from decimal import Decimal
from dataclasses import dataclass
from django.db.models import Q, F, Count, Sum, Avg
from django.utils import timezone

from ..models_routing import (
    ZonaEntrega, Rota, ParadaRota, PlanejamentoEntrega, ConfiguracaoRoteirizacao
)
from ..models_stock import VeiculoInterno, RastreamentoEntrega

logger = logging.getLogger(__name__)


@dataclass
class ParadaOtimizada:
    """Representa uma parada otimizada para roteirização."""
    planejamento_id: int
    endereco: str
    cidade: str
    provincia: str
    latitude: Optional[Decimal]
    longitude: Optional[Decimal]
    janela_inicio: time
    janela_fim: time
    prioridade: str
    tempo_estimado: int  # minutos
    peso_total: float  # kg
    observacoes: str


@dataclass
class RotaOtimizada:
    """Representa uma rota otimizada."""
    veiculo_id: int
    motorista_id: Optional[int]
    paradas: List[ParadaOtimizada]
    distancia_total: float  # km
    tempo_total: int  # minutos
    custo_estimado: Decimal
    eficiencia: float  # 0-1


class RoutingService:
    """Serviço para roteirização e planejamento logístico."""
    
    def __init__(self):
        self._config_padrao = None
    
    @property
    def config_padrao(self):
        """Obtém a configuração padrão de forma lazy."""
        if self._config_padrao is None:
            self._config_padrao = self._get_configuracao_padrao()
        return self._config_padrao
    
    def _get_configuracao_padrao(self) -> ConfiguracaoRoteirizacao:
        """Obtém a configuração padrão de roteirização."""
        try:
            return ConfiguracaoRoteirizacao.objects.get(padrao=True, ativo=True)
        except ConfiguracaoRoteirizacao.DoesNotExist:
            # Criar configuração padrão se não existir
            return ConfiguracaoRoteirizacao.objects.create(
                nome='Configuração Padrão',
                padrao=True,
                ativo=True
            )
    
    def criar_planejamento_entrega(self, 
                                 rastreamento: RastreamentoEntrega,
                                 endereco: str,
                                 cidade: str,
                                 provincia: str,
                                 data_entrega: datetime.date,
                                 janela_inicio: time,
                                 janela_fim: time,
                                 prioridade: str = 'NORMAL',
                                 observacoes: str = '',
                                 contato_nome: str = '',
                                 contato_telefone: str = '',
                                 contato_email: str = '') -> PlanejamentoEntrega:
        """
        Cria um planejamento de entrega.
        
        Args:
            rastreamento: RastreamentoEntrega associado
            endereco: Endereço completo de entrega
            cidade: Cidade de destino
            provincia: Província de destino
            data_entrega: Data preferida para entrega
            janela_inicio: Horário de início da janela
            janela_fim: Horário de fim da janela
            prioridade: Prioridade da entrega
            observacoes: Observações adicionais
            contato_nome: Nome do contato
            contato_telefone: Telefone do contato
            contato_email: Email do contato
            
        Returns:
            PlanejamentoEntrega criado
        """
        # Determinar zona de entrega
        zona = self._determinar_zona_entrega(cidade, provincia)
        
        # Gerar código único
        codigo = self._gerar_codigo_planejamento()
        
        planejamento = PlanejamentoEntrega.objects.create(
            codigo=codigo,
            zona_entrega=zona,
            endereco_completo=endereco,
            cidade=cidade,
            provincia=provincia,
            data_entrega_preferida=data_entrega,
            janela_inicio=janela_inicio,
            janela_fim=janela_fim,
            prioridade=prioridade,
            observacoes_entrega=observacoes,
            contato_nome=contato_nome,
            contato_telefone=contato_telefone,
            contato_email=contato_email,
            rastreamento_entrega=rastreamento,
            status='PENDENTE'
        )
        
        logger.info(f"Planejamento de entrega criado: {codigo}")
        return planejamento
    
    def _determinar_zona_entrega(self, cidade: str, provincia: str) -> ZonaEntrega:
        """Determina a zona de entrega baseada na cidade e província."""
        try:
            # Buscar zona específica por cidade
            zona = ZonaEntrega.objects.filter(
                cidade__iexact=cidade,
                provincia__iexact=provincia,
                ativo=True
            ).first()
            
            if zona:
                return zona
            
            # Buscar zona genérica por província
            zona = ZonaEntrega.objects.filter(
                provincia__iexact=provincia,
                ativo=True
            ).first()
            
            if zona:
                return zona
            
            # Criar zona padrão se não existir
            return ZonaEntrega.objects.create(
                nome=f"Zona {cidade}",
                codigo=f"{provincia[:3].upper()}-{cidade[:3].upper()}",
                provincia=provincia,
                cidade=cidade,
                bairros="Todos os bairros"
            )
            
        except Exception as e:
            logger.error(f"Erro ao determinar zona de entrega: {e}")
            raise
    
    def _gerar_codigo_planejamento(self) -> str:
        """Gera código único para planejamento."""
        from datetime import datetime
        
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        count = PlanejamentoEntrega.objects.filter(
            codigo__startswith=f"PLAN-{timestamp}"
        ).count()
        
        return f"PLAN-{timestamp}-{count + 1:03d}"
    
    def otimizar_rotas(self, 
                      data: datetime.date,
                      veiculos_disponiveis: Optional[List[int]] = None,
                      zonas: Optional[List[int]] = None) -> List[RotaOtimizada]:
        """
        Otimiza rotas para uma data específica.
        
        Args:
            data: Data para otimização
            veiculos_disponiveis: Lista de IDs de veículos disponíveis
            zonas: Lista de IDs de zonas para considerar
            
        Returns:
            Lista de rotas otimizadas
        """
        # Obter planejamentos pendentes
        planejamentos = self._obter_planejamentos_pendentes(data, zonas)
        
        if not planejamentos:
            logger.info(f"Nenhum planejamento pendente para {data}")
            return []
        
        # Obter veículos disponíveis
        veiculos = self._obter_veiculos_disponiveis(data, veiculos_disponiveis)
        
        if not veiculos:
            logger.warning(f"Nenhum veículo disponível para {data}")
            return []
        
        # Converter planejamentos para paradas otimizadas
        paradas = self._converter_para_paradas_otimizadas(planejamentos)
        
        # Executar algoritmo de otimização
        rotas_otimizadas = self._executar_algoritmo_otimizacao(paradas, veiculos)
        
        logger.info(f"Otimização concluída: {len(rotas_otimizadas)} rotas geradas")
        return rotas_otimizadas
    
    def _obter_planejamentos_pendentes(self, 
                                     data: datetime.date,
                                     zonas: Optional[List[int]] = None) -> List[PlanejamentoEntrega]:
        """Obtém planejamentos pendentes para uma data."""
        queryset = PlanejamentoEntrega.objects.filter(
            status='PENDENTE',
            data_entrega_preferida=data
        ).select_related('zona_entrega', 'rastreamento_entrega')
        
        if zonas:
            queryset = queryset.filter(zona_entrega_id__in=zonas)
        
        return list(queryset.order_by('prioridade', 'janela_inicio'))
    
    def _obter_veiculos_disponiveis(self, 
                                  data: datetime.date,
                                  veiculos_ids: Optional[List[int]] = None) -> List[VeiculoInterno]:
        """Obtém veículos internos disponíveis para uma data."""
        queryset = VeiculoInterno.objects.filter(
            status='ATIVO',
            disponivel=True
        )
        
        if veiculos_ids:
            queryset = queryset.filter(id__in=veiculos_ids)
        
        # Verificar se não há rotas já atribuídas para esta data
        rotas_existentes = Rota.objects.filter(
            data_planejada=data,
            status__in=['PLANEJADA', 'EM_EXECUCAO']
        ).values_list('veiculo_interno_id', flat=True)
        
        if rotas_existentes:
            queryset = queryset.exclude(id__in=rotas_existentes)
        
        return list(queryset)
    
    def _converter_para_paradas_otimizadas(self, 
                                        planejamentos: List[PlanejamentoEntrega]) -> List[ParadaOtimizada]:
        """Converte planejamentos em paradas otimizadas."""
        paradas = []
        
        for planejamento in planejamentos:
            # Calcular peso total (simulado - pode vir do rastreamento)
            peso_total = self._calcular_peso_total(planejamento)
            
            # Calcular tempo estimado baseado na prioridade
            tempo_estimado = self._calcular_tempo_estimado(planejamento.prioridade)
            
            parada = ParadaOtimizada(
                planejamento_id=planejamento.id,
                endereco=planejamento.endereco_completo,
                cidade=planejamento.cidade,
                provincia=planejamento.provincia,
                latitude=planejamento.latitude,
                longitude=planejamento.longitude,
                janela_inicio=planejamento.janela_inicio,
                janela_fim=planejamento.janela_fim,
                prioridade=planejamento.prioridade,
                tempo_estimado=tempo_estimado,
                peso_total=peso_total,
                observacoes=planejamento.observacoes_entrega
            )
            paradas.append(parada)
        
        return paradas
    
    def _calcular_peso_total(self, planejamento: PlanejamentoEntrega) -> float:
        """Calcula o peso total estimado da entrega."""
        # Implementação simplificada - pode ser expandida
        # Baseado na prioridade e observações
        peso_base = 1.0  # kg
        
        if planejamento.prioridade == 'URGENTE':
            peso_base *= 0.5
        elif planejamento.prioridade == 'ALTA':
            peso_base *= 0.8
        elif planejamento.prioridade == 'BAIXA':
            peso_base *= 1.5
        
        return peso_base
    
    def _calcular_tempo_estimado(self, prioridade: str) -> int:
        """Calcula tempo estimado para entrega baseado na prioridade."""
        tempos = {
            'URGENTE': 15,  # minutos
            'ALTA': 20,
            'NORMAL': 30,
            'BAIXA': 45
        }
        return tempos.get(prioridade, 30)
    
    def _executar_algoritmo_otimizacao(self, 
                                     paradas: List[ParadaOtimizada],
                                     veiculos: List[VeiculoInterno]) -> List[RotaOtimizada]:
        """
        Executa algoritmo de otimização de rotas.
        
        Implementação simplificada usando algoritmo guloso.
        """
        rotas_otimizadas = []
        paradas_restantes = paradas.copy()
        
        # Ordenar paradas por prioridade e janela de tempo
        paradas_restantes.sort(key=lambda p: (
            self._prioridade_numerica(p.prioridade),
            p.janela_inicio
        ))
        
        for veiculo in veiculos:
            if not paradas_restantes:
                break
            
            rota = self._criar_rota_para_veiculo(veiculo, paradas_restantes)
            if rota:
                rotas_otimizadas.append(rota)
                # Remover paradas atribuídas
                paradas_atribuidas = [p.planejamento_id for p in rota.paradas]
                paradas_restantes = [
                    p for p in paradas_restantes 
                    if p.planejamento_id not in paradas_atribuidas
                ]
        
        return rotas_otimizadas
    
    def _prioridade_numerica(self, prioridade: str) -> int:
        """Converte prioridade em valor numérico para ordenação."""
        valores = {
            'URGENTE': 1,
            'ALTA': 2,
            'NORMAL': 3,
            'BAIXA': 4
        }
        return valores.get(prioridade, 3)
    
    def _criar_rota_para_veiculo(self, 
                               veiculo: VeiculoInterno,
                               paradas: List[ParadaOtimizada]) -> Optional[RotaOtimizada]:
        """Cria uma rota otimizada para um veículo específico."""
        paradas_rota = []
        capacidade_atual = 0.0
        tempo_atual = 0
        distancia_atual = 0.0
        
        capacidade_maxima = self.config_padrao.capacidade_maxima_veiculo
        tempo_maximo = self.config_padrao.tempo_maximo_rota_horas * 60  # minutos
        distancia_maxima = self.config_padrao.distancia_maxima_rota_km
        
        for parada in paradas:
            # Verificar restrições
            if (capacidade_atual + parada.peso_total > capacidade_maxima or
                tempo_atual + parada.tempo_estimado > tempo_maximo):
                continue
            
            # Simular distância (implementação simplificada)
            distancia_adicional = self._calcular_distancia_estimada(parada)
            if distancia_atual + distancia_adicional > distancia_maxima:
                continue
            
            paradas_rota.append(parada)
            capacidade_atual += parada.peso_total
            tempo_atual += parada.tempo_estimado
            distancia_atual += distancia_adicional
        
        if not paradas_rota:
            return None
        
        # Calcular custo estimado
        custo_estimado = self._calcular_custo_rota(distancia_atual, tempo_atual)
        
        # Calcular eficiência
        eficiencia = self._calcular_eficiencia_rota(paradas_rota, distancia_atual, tempo_atual)
        
        return RotaOtimizada(
            veiculo_id=veiculo.id,
            motorista_id=None,  # Pode ser atribuído posteriormente
            paradas=paradas_rota,
            distancia_total=distancia_atual,
            tempo_total=tempo_atual,
            custo_estimado=custo_estimado,
            eficiencia=eficiencia
        )
    
    def _calcular_distancia_estimada(self, parada: ParadaOtimizada) -> float:
        """Calcula distância estimada para uma parada."""
        # Implementação simplificada - pode usar APIs de geocoding
        # Por enquanto, retorna valor fixo baseado na cidade
        distancias_cidade = {
            'Maputo': 5.0,
            'Matola': 8.0,
            'Beira': 3.0,
            'Nampula': 4.0,
        }
        return distancias_cidade.get(parada.cidade, 6.0)
    
    def _calcular_custo_rota(self, distancia: float, tempo: int) -> Decimal:
        """Calcula custo estimado de uma rota."""
        # Implementação simplificada
        custo_por_km = Decimal('0.50')
        custo_por_hora = Decimal('10.00')
        
        custo_distancia = Decimal(str(distancia)) * custo_por_km
        custo_tempo = Decimal(str(tempo / 60)) * custo_por_hora
        
        return custo_distancia + custo_tempo
    
    def _calcular_eficiencia_rota(self, 
                                paradas: List[ParadaOtimizada],
                                distancia: float,
                                tempo: int) -> float:
        """Calcula eficiência de uma rota (0-1)."""
        if not paradas:
            return 0.0
        
        # Fatores de eficiência
        fator_paradas = len(paradas) / 10.0  # Ideal: 10 paradas por rota
        fator_distancia = 1.0 - (distancia / 200.0)  # Ideal: <200km
        fator_tempo = 1.0 - (tempo / 480.0)  # Ideal: <8h
        
        # Peso das prioridades
        peso_prioridades = sum(
            self._prioridade_numerica(p.prioridade) for p in paradas
        ) / (len(paradas) * 4.0)  # Normalizar para 0-1
        
        eficiencia = (
            fator_paradas * 0.3 +
            fator_distancia * 0.3 +
            fator_tempo * 0.3 +
            peso_prioridades * 0.1
        )
        
        return max(0.0, min(1.0, eficiencia))
    
    def salvar_rotas_otimizadas(self, 
                              rotas: List[RotaOtimizada],
                              data: datetime.date,
                              criado_por_id: int) -> List[Rota]:
        """
        Salva rotas otimizadas no banco de dados.
        
        Args:
            rotas: Lista de rotas otimizadas
            data: Data das rotas
            criado_por_id: ID do usuário que criou as rotas
            
        Returns:
            Lista de rotas salvas
        """
        rotas_salvas = []
        
        for i, rota_otimizada in enumerate(rotas):
            # Criar rota
            codigo_rota = f"ROTA-{data.strftime('%Y%m%d')}-{i+1:03d}"
            
            rota = Rota.objects.create(
                codigo=codigo_rota,
                nome=f"Rota {i+1} - {data}",
                zona_origem_id=1,  # Zona padrão - pode ser melhorado
                veiculo_interno_id=rota_otimizada.veiculo_id,
                motorista_id=rota_otimizada.motorista_id,
                data_planejada=data,
                hora_inicio_prevista=time(8, 0),  # Hora padrão
                hora_fim_prevista=time(17, 0),   # Hora padrão
                distancia_total_km=Decimal(str(rota_otimizada.distancia_total)),
                tempo_estimado_minutos=rota_otimizada.tempo_total,
                status='PLANEJADA',
                criado_por_id=criado_por_id
            )
            
            # Criar paradas
            for j, parada in enumerate(rota_otimizada.paradas):
                planejamento = PlanejamentoEntrega.objects.get(id=parada.planejamento_id)
                
                ParadaRota.objects.create(
                    rota=rota,
                    sequencia=j + 1,
                    tipo='ENTREGA',
                    endereco=parada.endereco,
                    cidade=parada.cidade,
                    provincia=parada.provincia,
                    latitude=parada.latitude,
                    longitude=parada.longitude,
                    hora_chegada_prevista=parada.janela_inicio,
                    hora_saida_prevista=parada.janela_fim,
                    tempo_estimado_minutos=parada.tempo_estimado,
                    observacoes=parada.observacoes,
                    contato_nome=planejamento.contato_nome,
                    contato_telefone=planejamento.contato_telefone,
                    rastreamento_entrega_id=planejamento.rastreamento_entrega_id
                )
                
                # Atualizar planejamento
                planejamento.status = 'AGENDADA'
                planejamento.rota_atribuida = rota
                planejamento.save()
            
            rotas_salvas.append(rota)
            logger.info(f"Rota salva: {codigo_rota} com {len(rota_otimizada.paradas)} paradas")
        
        return rotas_salvas


# Instância global do serviço (criada lazy quando necessário)
# routing_service = RoutingService()
