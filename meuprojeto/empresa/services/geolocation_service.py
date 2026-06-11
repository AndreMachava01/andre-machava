"""
Serviço para geolocalização e cálculo de distâncias.
"""
import logging
import math
import time
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
from django.db.models import Q, F, Count, Sum, Avg, Min, Max
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.core.cache import cache

from ..models_geolocation import (
    EnderecoNormalizado, CalculoDistancia, ETACalculo,
    ZonaGeografica, ConfiguracaoGeolocalizacao, LogGeolocalizacao
)

logger = logging.getLogger(__name__)


class GeolocationService:
    """Serviço para geolocalização e cálculo de distâncias."""
    
    def __init__(self):
        self._config_padrao = None
    
    @property
    def config_padrao(self):
        """Obtém a configuração padrão de geolocalização."""
        if self._config_padrao is None:
            self._config_padrao = self._get_configuracao_padrao()
        return self._config_padrao
    
    def _get_configuracao_padrao(self) -> ConfiguracaoGeolocalizacao:
        """Obtém a configuração padrão de geolocalização."""
        try:
            return ConfiguracaoGeolocalizacao.objects.get(padrao=True, ativo=True)
        except ConfiguracaoGeolocalizacao.DoesNotExist:
            # Criar configuração padrão se não existir
            return ConfiguracaoGeolocalizacao.objects.create(
                nome='Configuração Padrão',
                padrao=True,
                ativo=True
            )
    
    def _log_operacao(self,
                      tipo_operacao: str,
                      entrada_dados: Dict[str, Any],
                      resultado_dados: Dict[str, Any],
                      tempo_execucao_ms: int,
                      sucesso: bool = True,
                      erro_mensagem: str = '',
                      fonte_api: str = '',
                      custo_api: Optional[Decimal] = None,
                      usuario: Optional[User] = None,
                      ip_address: Optional[str] = None):
        """Registra log de operação de geolocalização."""
        try:
            LogGeolocalizacao.objects.create(
                tipo_operacao=tipo_operacao,
                entrada_dados=entrada_dados,
                resultado_dados=resultado_dados,
                tempo_execucao_ms=tempo_execucao_ms,
                sucesso=sucesso,
                erro_mensagem=erro_mensagem,
                fonte_api=fonte_api,
                custo_api=custo_api,
                usuario=usuario,
                ip_address=ip_address
            )
        except Exception as e:
            logger.error(f"Erro ao registrar log de geolocalização: {e}")
    
    def normalizar_endereco(self,
                           endereco_original: str,
                           usuario: Optional[User] = None,
                           ip_address: Optional[str] = None) -> EnderecoNormalizado:
        """
        Normaliza um endereço e obtém coordenadas.
        
        Args:
            endereco_original: Endereço original
            usuario: Usuário responsável
            ip_address: Endereço IP
            
        Returns:
            EnderecoNormalizado criado
        """
        inicio_tempo = time.time()
        
        try:
            # Verificar cache primeiro
            if self.config_padrao.cache_habilitado:
                cache_key = f"endereco:{hash(endereco_original)}"
                endereco_cached = cache.get(cache_key)
                if endereco_cached:
                    logger.info(f"Endereço encontrado no cache: {endereco_original}")
                    return endereco_cached
            
            # Verificar se já existe no banco
            endereco_existente = EnderecoNormalizado.objects.filter(
                endereco_original__iexact=endereco_original
            ).first()
            
            if endereco_existente:
                # Atualizar cache
                if self.config_padrao.cache_habilitado:
                    cache.set(cache_key, endereco_existente, self.config_padrao.tempo_cache_horas * 3600)
                
                fim_tempo = time.time()
                tempo_execucao_ms = int((fim_tempo - inicio_tempo) * 1000)
                
                self._log_operacao(
                    tipo_operacao='NORMALIZACAO',
                    entrada_dados={'endereco': endereco_original},
                    resultado_dados={'endereco_id': endereco_existente.id},
                    tempo_execucao_ms=tempo_execucao_ms,
                    sucesso=True,
                    fonte_api='CACHE',
                    usuario=usuario,
                    ip_address=ip_address
                )
                
                return endereco_existente
            
            # Realizar geocoding
            if self.config_padrao.geocoding_automatico:
                coordenadas = self._realizar_geocoding(endereco_original)
            else:
                # Coordenadas padrão para Maputo
                coordenadas = {
                    'latitude': Decimal('-25.969248'),
                    'longitude': Decimal('32.573924'),
                    'precisao': 'APPROXIMATE',
                    'nivel_confianca': Decimal('50.00')
                }
            
            # Normalizar endereço
            endereco_normalizado = self._normalizar_texto_endereco(endereco_original)
            
            # Criar endereço normalizado
            endereco = EnderecoNormalizado.objects.create(
                endereco_original=endereco_original,
                endereco_normalizado=endereco_normalizado,
                latitude=coordenadas['latitude'],
                longitude=coordenadas['longitude'],
                precisao=coordenadas['precisao'],
                nivel_confianca=coordenadas['nivel_confianca'],
                fonte_geocoding=self.config_padrao.api_geocoding,
                ativo=True,
                validado=False
            )
            
            # Atualizar cache
            if self.config_padrao.cache_habilitado:
                cache.set(cache_key, endereco, self.config_padrao.tempo_cache_horas * 3600)
            
            fim_tempo = time.time()
            tempo_execucao_ms = int((fim_tempo - inicio_tempo) * 1000)
            
            self._log_operacao(
                tipo_operacao='GEOCODING',
                entrada_dados={'endereco': endereco_original},
                resultado_dados={
                    'endereco_id': endereco.id,
                    'latitude': float(coordenadas['latitude']),
                    'longitude': float(coordenadas['longitude'])
                },
                tempo_execucao_ms=tempo_execucao_ms,
                sucesso=True,
                fonte_api=self.config_padrao.api_geocoding,
                usuario=usuario,
                ip_address=ip_address
            )
            
            logger.info(f"Endereço normalizado: {endereco_original}")
            return endereco
            
        except Exception as e:
            fim_tempo = time.time()
            tempo_execucao_ms = int((fim_tempo - inicio_tempo) * 1000)
            
            self._log_operacao(
                tipo_operacao='GEOCODING',
                entrada_dados={'endereco': endereco_original},
                resultado_dados={},
                tempo_execucao_ms=tempo_execucao_ms,
                sucesso=False,
                erro_mensagem=str(e),
                fonte_api=self.config_padrao.api_geocoding,
                usuario=usuario,
                ip_address=ip_address
            )
            
            logger.error(f"Erro ao normalizar endereço: {e}")
            raise
    
    def _realizar_geocoding(self, endereco: str) -> Dict[str, Any]:
        """Realiza geocoding do endereço."""
        try:
            # Implementação simplificada
            # Em um sistema real, você integraria com APIs como Google Maps, OpenStreetMap, etc.
            
            # Simular geocoding baseado em padrões conhecidos
            if 'maputo' in endereco.lower():
                return {
                    'latitude': Decimal('-25.969248'),
                    'longitude': Decimal('32.573924'),
                    'precisao': 'ROOFTOP',
                    'nivel_confianca': Decimal('95.00')
                }
            elif 'beira' in endereco.lower():
                return {
                    'latitude': Decimal('-19.833333'),
                    'longitude': Decimal('34.850000'),
                    'precisao': 'RANGE_INTERPOLATED',
                    'nivel_confianca': Decimal('85.00')
                }
            elif 'nampula' in endereco.lower():
                return {
                    'latitude': Decimal('-15.116667'),
                    'longitude': Decimal('39.266667'),
                    'precisao': 'RANGE_INTERPOLATED',
                    'nivel_confianca': Decimal('85.00')
                }
            else:
                # Coordenadas padrão para Moçambique
                return {
                    'latitude': Decimal('-18.665695'),
                    'longitude': Decimal('35.529562'),
                    'precisao': 'APPROXIMATE',
                    'nivel_confianca': Decimal('60.00')
                }
                
        except Exception as e:
            logger.error(f"Erro no geocoding: {e}")
            raise
    
    def _normalizar_texto_endereco(self, endereco: str) -> str:
        """Normaliza o texto do endereço."""
        # Implementação simplificada de normalização
        endereco_normalizado = endereco.strip().title()
        
        # Substituições comuns
        substituicoes = {
            'Rua': 'R.',
            'Avenida': 'Av.',
            'Travessa': 'Tv.',
            'Largo': 'Lg.',
            'Praça': 'Pç.',
            'Alameda': 'Al.',
        }
        
        for original, abreviacao in substituicoes.items():
            endereco_normalizado = endereco_normalizado.replace(original, abreviacao)
        
        return endereco_normalizado
    
    def calcular_distancia_haversine(self,
                                   lat1: Decimal,
                                   lon1: Decimal,
                                   lat2: Decimal,
                                   lon2: Decimal) -> Decimal:
        """
        Calcula distância usando a fórmula de Haversine.
        
        Args:
            lat1: Latitude do ponto 1
            lon1: Longitude do ponto 1
            lat2: Latitude do ponto 2
            lon2: Longitude do ponto 2
            
        Returns:
            Distância em quilômetros
        """
        try:
            # Converter para radianos
            lat1_rad = math.radians(float(lat1))
            lon1_rad = math.radians(float(lon1))
            lat2_rad = math.radians(float(lat2))
            lon2_rad = math.radians(float(lon2))
            
            # Diferenças
            dlat = lat2_rad - lat1_rad
            dlon = lon2_rad - lon1_rad
            
            # Fórmula de Haversine
            a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
            c = 2 * math.asin(math.sqrt(a))
            
            # Raio da Terra em km
            raio_terra = 6371
            
            # Distância em km
            distancia = raio_terra * c
            
            return Decimal(str(round(distancia, 3)))
            
        except Exception as e:
            logger.error(f"Erro ao calcular distância Haversine: {e}")
            raise
    
    def calcular_distancia_manhattan(self,
                                   lat1: Decimal,
                                   lon1: Decimal,
                                   lat2: Decimal,
                                   lon2: Decimal) -> Decimal:
        """
        Calcula distância usando a métrica de Manhattan.
        
        Args:
            lat1: Latitude do ponto 1
            lon1: Longitude do ponto 1
            lat2: Latitude do ponto 2
            lon2: Longitude do ponto 2
            
        Returns:
            Distância em quilômetros
        """
        try:
            # Converter diferenças para km
            dlat_km = abs(float(lat2 - lat1)) * 111.32  # Aproximadamente 111.32 km por grau
            dlon_km = abs(float(lon2 - lon1)) * 111.32 * math.cos(math.radians(float(lat1)))
            
            distancia = dlat_km + dlon_km
            
            return Decimal(str(round(distancia, 3)))
            
        except Exception as e:
            logger.error(f"Erro ao calcular distância Manhattan: {e}")
            raise
    
    def calcular_distancia_euclidiana(self,
                                    lat1: Decimal,
                                    lon1: Decimal,
                                    lat2: Decimal,
                                    lon2: Decimal) -> Decimal:
        """
        Calcula distância usando a métrica euclidiana.
        
        Args:
            lat1: Latitude do ponto 1
            lon1: Longitude do ponto 1
            lat2: Latitude do ponto 2
            lon2: Longitude do ponto 2
            
        Returns:
            Distância em quilômetros
        """
        try:
            # Converter diferenças para km
            dlat_km = abs(float(lat2 - lat1)) * 111.32
            dlon_km = abs(float(lon2 - lon1)) * 111.32 * math.cos(math.radians(float(lat1)))
            
            # Distância euclidiana
            distancia = math.sqrt(dlat_km**2 + dlon_km**2)
            
            return Decimal(str(round(distancia, 3)))
            
        except Exception as e:
            logger.error(f"Erro ao calcular distância Euclidiana: {e}")
            raise
    
    def calcular_distancia(self,
                          lat1: Decimal,
                          lon1: Decimal,
                          lat2: Decimal,
                          lon2: Decimal,
                          tipo_calculo: Optional[str] = None,
                          usuario: Optional[User] = None,
                          ip_address: Optional[str] = None) -> CalculoDistancia:
        """
        Calcula distância entre dois pontos.
        
        Args:
            lat1: Latitude do ponto 1
            lon1: Longitude do ponto 1
            lat2: Latitude do ponto 2
            lon2: Longitude do ponto 2
            tipo_calculo: Tipo de cálculo
            usuario: Usuário responsável
            ip_address: Endereço IP
            
        Returns:
            CalculoDistancia criado
        """
        inicio_tempo = time.time()
        
        try:
            tipo_calculo = tipo_calculo or self.config_padrao.calculo_distancia_padrao
            
            # Calcular distância baseada no tipo
            if tipo_calculo == 'HAVERSINE':
                distancia_km = self.calcular_distancia_haversine(lat1, lon1, lat2, lon2)
            elif tipo_calculo == 'MANHATTAN':
                distancia_km = self.calcular_distancia_manhattan(lat1, lon1, lat2, lon2)
            elif tipo_calculo == 'EUCLIDIANA':
                distancia_km = self.calcular_distancia_euclidiana(lat1, lon1, lat2, lon2)
            else:
                raise ValueError(f"Tipo de cálculo não suportado: {tipo_calculo}")
            
            # Calcular tempo estimado
            velocidade_kmh = self.config_padrao.velocidade_padrao_kmh
            tempo_estimado_minutos = int((distancia_km / velocidade_kmh) * 60)
            
            # Criar cálculo de distância
            calculo = CalculoDistancia.objects.create(
                origem_latitude=lat1,
                origem_longitude=lon1,
                destino_latitude=lat2,
                destino_longitude=lon2,
                distancia_km=distancia_km,
                tempo_estimado_minutos=tempo_estimado_minutos,
                tipo_calculo=tipo_calculo,
                velocidade_media_kmh=velocidade_kmh,
                precisao_calculo=Decimal('95.00'),
                fonte_dados='CALCULADO'
            )
            
            fim_tempo = time.time()
            tempo_execucao_ms = int((fim_tempo - inicio_tempo) * 1000)
            
            self._log_operacao(
                tipo_operacao='CALCULO_DISTANCIA',
                entrada_dados={
                    'origem': {'lat': float(lat1), 'lon': float(lon1)},
                    'destino': {'lat': float(lat2), 'lon': float(lon2)},
                    'tipo_calculo': tipo_calculo
                },
                resultado_dados={
                    'distancia_km': float(distancia_km),
                    'tempo_minutos': tempo_estimado_minutos
                },
                tempo_execucao_ms=tempo_execucao_ms,
                sucesso=True,
                usuario=usuario,
                ip_address=ip_address
            )
            
            logger.info(f"Distância calculada: {distancia_km}km")
            return calculo
            
        except Exception as e:
            fim_tempo = time.time()
            tempo_execucao_ms = int((fim_tempo - inicio_tempo) * 1000)
            
            self._log_operacao(
                tipo_operacao='CALCULO_DISTANCIA',
                entrada_dados={
                    'origem': {'lat': float(lat1), 'lon': float(lon1)},
                    'destino': {'lat': float(lat2), 'lon': float(lon2)},
                    'tipo_calculo': tipo_calculo
                },
                resultado_dados={},
                tempo_execucao_ms=tempo_execucao_ms,
                sucesso=False,
                erro_mensagem=str(e),
                usuario=usuario,
                ip_address=ip_address
            )
            
            logger.error(f"Erro ao calcular distância: {e}")
            raise
    
    def calcular_eta(self,
                   rastreamento_id: Optional[int],
                   calculo_distancia_id: int,
                   data_partida: datetime,
                   fator_trafego: Decimal = Decimal('1.00'),
                   fator_clima: Decimal = Decimal('1.00'),
                   fator_horario: Decimal = Decimal('1.00'),
                   usuario: Optional[User] = None,
                   ip_address: Optional[str] = None) -> ETACalculo:
        """
        Calcula ETA (Estimated Time of Arrival).
        
        Args:
            rastreamento_id: ID do rastreamento
            calculo_distancia_id: ID do cálculo de distância
            data_partida: Data de partida
            fator_trafego: Fator de tráfego
            fator_clima: Fator de clima
            fator_horario: Fator de horário
            usuario: Usuário responsável
            ip_address: Endereço IP
            
        Returns:
            ETACalculo criado
        """
        inicio_tempo = time.time()
        
        try:
            calculo_distancia = CalculoDistancia.objects.get(id=calculo_distancia_id)
            
            # Calcular tempo base
            tempo_base_minutos = calculo_distancia.tempo_estimado_minutos
            
            # Aplicar fatores
            tempo_total_minutos = int(
                tempo_base_minutos * fator_trafego * fator_clima * fator_horario
            )
            
            # Calcular data de chegada
            data_chegada_estimada = data_partida + timedelta(minutes=tempo_total_minutos)
            
            # Calcular confiabilidade
            confiabilidade = Decimal('80.00')
            if self.config_padrao.considerar_trafego:
                confiabilidade -= Decimal('10.00')
            if self.config_padrao.considerar_clima:
                confiabilidade -= Decimal('10.00')
            if self.config_padrao.considerar_horario:
                confiabilidade -= Decimal('5.00')
            
            # Criar ETA
            eta = ETACalculo.objects.create(
                rastreamento_entrega_id=rastreamento_id,
                calculo_distancia=calculo_distancia,
                tipo_eta='DISTANCIA',
                data_partida=data_partida,
                data_chegada_estimada=data_chegada_estimada,
                fator_trafego=fator_trafego,
                fator_clima=fator_clima,
                fator_horario=fator_horario,
                tempo_total_minutos=tempo_total_minutos,
                confiabilidade_percentual=confiabilidade,
                eta_atualizado=True
            )
            
            fim_tempo = time.time()
            tempo_execucao_ms = int((fim_tempo - inicio_tempo) * 1000)
            
            self._log_operacao(
                tipo_operacao='CALCULO_ETA',
                entrada_dados={
                    'rastreamento_id': rastreamento_id,
                    'calculo_distancia_id': calculo_distancia_id,
                    'data_partida': data_partida.isoformat(),
                    'fatores': {
                        'trafego': float(fator_trafego),
                        'clima': float(fator_clima),
                        'horario': float(fator_horario)
                    }
                },
                resultado_dados={
                    'eta_id': eta.id,
                    'tempo_total_minutos': tempo_total_minutos,
                    'data_chegada': data_chegada_estimada.isoformat(),
                    'confiabilidade': float(confiabilidade)
                },
                tempo_execucao_ms=tempo_execucao_ms,
                sucesso=True,
                usuario=usuario,
                ip_address=ip_address
            )
            
            logger.info(f"ETA calculado: {data_chegada_estimada}")
            return eta
            
        except Exception as e:
            fim_tempo = time.time()
            tempo_execucao_ms = int((fim_tempo - inicio_tempo) * 1000)
            
            self._log_operacao(
                tipo_operacao='CALCULO_ETA',
                entrada_dados={
                    'rastreamento_id': rastreamento_id,
                    'calculo_distancia_id': calculo_distancia_id,
                    'data_partida': data_partida.isoformat()
                },
                resultado_dados={},
                tempo_execucao_ms=tempo_execucao_ms,
                sucesso=False,
                erro_mensagem=str(e),
                usuario=usuario,
                ip_address=ip_address
            )
            
            logger.error(f"Erro ao calcular ETA: {e}")
            raise
    
    def obter_estatisticas_geolocalizacao(self) -> Dict[str, Any]:
        """
        Obtém estatísticas de geolocalização.
        
        Returns:
            Dicionário com estatísticas
        """
        try:
            hoje = timezone.now().date()
            ultimos_30_dias = hoje - timedelta(days=30)
            
            stats = {
                'enderecos': {
                    'total_normalizados': EnderecoNormalizado.objects.count(),
                    'ultimos_30_dias': EnderecoNormalizado.objects.filter(
                        data_geocoding__date__gte=ultimos_30_dias
                    ).count(),
                    'validados': EnderecoNormalizado.objects.filter(validado=True).count(),
                    'por_precisao': dict(
                        EnderecoNormalizado.objects.values('precisao')
                        .annotate(count=Count('id'))
                        .values_list('precisao', 'count')
                    )
                },
                'distancias': {
                    'total_calculadas': CalculoDistancia.objects.count(),
                    'ultimos_30_dias': CalculoDistancia.objects.filter(
                        data_calculo__date__gte=ultimos_30_dias
                    ).count(),
                    'por_tipo': dict(
                        CalculoDistancia.objects.values('tipo_calculo')
                        .annotate(count=Count('id'))
                        .values_list('tipo_calculo', 'count')
                    ),
                    'distancia_media': CalculoDistancia.objects.aggregate(
                        distancia_media=Avg('distancia_km')
                    )['distancia_media'] or 0
                },
                'etas': {
                    'total_calculados': ETACalculo.objects.count(),
                    'ultimos_30_dias': ETACalculo.objects.filter(
                        data_atualizacao__date__gte=ultimos_30_dias
                    ).count(),
                    'tempo_medio_minutos': ETACalculo.objects.aggregate(
                        tempo_medio=Avg('tempo_total_minutos')
                    )['tempo_medio'] or 0,
                    'confiabilidade_media': ETACalculo.objects.aggregate(
                        confiabilidade_media=Avg('confiabilidade_percentual')
                    )['confiabilidade_media'] or 0
                },
                'logs': {
                    'total_operacoes': LogGeolocalizacao.objects.count(),
                    'ultimos_30_dias': LogGeolocalizacao.objects.filter(
                        data_operacao__date__gte=ultimos_30_dias
                    ).count(),
                    'operacoes_sucesso': LogGeolocalizacao.objects.filter(sucesso=True).count(),
                    'operacoes_erro': LogGeolocalizacao.objects.filter(sucesso=False).count(),
                    'tempo_medio_ms': LogGeolocalizacao.objects.aggregate(
                        tempo_medio=Avg('tempo_execucao_ms')
                    )['tempo_medio'] or 0
                }
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas de geolocalização: {e}")
            raise


# Instância global do serviço
geolocation_service = GeolocationService()
