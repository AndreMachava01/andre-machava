"""
Serviço para gestão de dados mestres (masterdata) logísticos.
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, date, timedelta
from decimal import Decimal
from django.db.models import Q, F, Count, Sum, Avg, Min, Max
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User

from ..models_masterdata import (
    Regiao, HubLogistico, CatalogoDimensoes,
    RestricaoLogistica, PermissaoLogistica, ConfiguracaoMasterdata,
    LogMasterdata
)
from ..models_routing import ZonaEntrega
from ..models_stock import RastreamentoEntrega, Transportadora, VeiculoInterno

logger = logging.getLogger(__name__)


class MasterdataService:
    """Serviço para gestão de dados mestres logísticos."""
    
    def __init__(self):
        self._config_padrao = None
    
    @property
    def config_padrao(self):
        """Obtém a configuração padrão de masterdata."""
        if self._config_padrao is None:
            self._config_padrao = self._get_configuracao_padrao()
        return self._config_padrao
    
    def _get_configuracao_padrao(self) -> ConfiguracaoMasterdata:
        """Obtém a configuração padrão de masterdata."""
        try:
            return ConfiguracaoMasterdata.objects.get(padrao=True, ativo=True)
        except ConfiguracaoMasterdata.DoesNotExist:
            # Criar configuração padrão se não existir
            return ConfiguracaoMasterdata.objects.create(
                nome='Configuração Padrão',
                padrao=True,
                ativo=True
            )
    
    def _log_operacao(self, 
                      tipo_operacao: str,
                      modelo_afetado: str,
                      objeto_id: int,
                      dados_anteriores: Optional[Dict] = None,
                      dados_novos: Optional[Dict] = None,
                      usuario: Optional[User] = None,
                      ip_address: Optional[str] = None,
                      user_agent: Optional[str] = None):
        """Registra log de operação em dados mestres."""
        try:
            LogMasterdata.objects.create(
                tipo_operacao=tipo_operacao,
                modelo_afetado=modelo_afetado,
                objeto_id=objeto_id,
                dados_anteriores=dados_anteriores,
                dados_novos=dados_novos,
                usuario=usuario,
                ip_address=ip_address,
                user_agent=user_agent
            )
        except Exception as e:
            logger.error(f"Erro ao registrar log de masterdata: {e}")
    
    def criar_regiao(self,
                    codigo: str,
                    nome: str,
                    provincia: str,
                    distrito: str = '',
                    latitude_centro: Optional[Decimal] = None,
                    longitude_centro: Optional[Decimal] = None,
                    prioridade: int = 1,
                    usuario: Optional[User] = None) -> Regiao:
        """
        Cria uma nova região.
        
        Args:
            codigo: Código único da região
            nome: Nome da região
            provincia: Província
            distrito: Distrito (opcional)
            latitude_centro: Latitude do centro da região
            longitude_centro: Longitude do centro da região
            prioridade: Prioridade da região
            usuario: Usuário que criou
            
        Returns:
            Regiao criada
        """
        try:
            regiao = Regiao.objects.create(
                codigo=codigo,
                nome=nome,
                provincia=provincia,
                distrito=distrito,
                latitude_centro=latitude_centro,
                longitude_centro=longitude_centro,
                prioridade=prioridade,
                ativo=True
            )
            
            self._log_operacao(
                tipo_operacao='CRIAR',
                modelo_afetado='Regiao',
                objeto_id=regiao.id,
                dados_novos={
                    'codigo': codigo,
                    'nome': nome,
                    'provincia': provincia,
                    'distrito': distrito,
                    'prioridade': prioridade
                },
                usuario=usuario
            )
            
            logger.info(f"Região criada: {regiao.codigo}")
            return regiao
            
        except Exception as e:
            logger.error(f"Erro ao criar região: {e}")
            raise
    
    def criar_zona_entrega(self,
                          codigo: str,
                          nome: str,
                          regiao_id: int,
                          prazo_entrega_dias: int = 1,
                          custo_adicional: Decimal = Decimal('0.00'),
                          peso_maximo_kg: Optional[Decimal] = None,
                          volume_maximo_m3: Optional[Decimal] = None,
                          horario_inicio: str = '08:00',
                          horario_fim: str = '18:00',
                          dias_funcionamento: List[int] = None,
                          usuario: Optional[User] = None) -> ZonaEntrega:
        """
        Cria uma nova zona de entrega.
        
        Args:
            codigo: Código único da zona
            nome: Nome da zona
            regiao_id: ID da região
            prazo_entrega_dias: Prazo de entrega em dias
            custo_adicional: Custo adicional da zona
            peso_maximo_kg: Peso máximo permitido
            volume_maximo_m3: Volume máximo permitido
            horario_inicio: Horário de início
            horario_fim: Horário de fim
            dias_funcionamento: Dias de funcionamento
            usuario: Usuário que criou
            
        Returns:
            ZonaEntrega criada
        """
        try:
            regiao = Regiao.objects.get(id=regiao_id)
            
            if dias_funcionamento is None:
                dias_funcionamento = [0, 1, 2, 3, 4]  # Segunda a sexta
            
            zona = ZonaEntrega.objects.create(
                codigo=codigo,
                nome=nome,
                regiao=regiao,
                prazo_entrega_dias=prazo_entrega_dias,
                custo_adicional=custo_adicional,
                peso_maximo_kg=peso_maximo_kg,
                volume_maximo_m3=volume_maximo_m3,
                horario_inicio=horario_inicio,
                horario_fim=horario_fim,
                dias_funcionamento=dias_funcionamento,
                ativo=True
            )
            
            self._log_operacao(
                tipo_operacao='CRIAR',
                modelo_afetado='ZonaEntrega',
                objeto_id=zona.id,
                dados_novos={
                    'codigo': codigo,
                    'nome': nome,
                    'regiao': regiao.nome,
                    'prazo_entrega_dias': prazo_entrega_dias,
                    'custo_adicional': float(custo_adicional)
                },
                usuario=usuario
            )
            
            logger.info(f"Zona de entrega criada: {zona.codigo}")
            return zona
            
        except Exception as e:
            logger.error(f"Erro ao criar zona de entrega: {e}")
            raise
    
    def criar_hub_logistico(self,
                           codigo: str,
                           nome: str,
                           endereco: str,
                           cidade: str,
                           regiao_id: int,
                           latitude: Decimal,
                           longitude: Decimal,
                           tipo: str = 'DISTRIBUICAO',
                           capacidade_maxima_m3: Optional[Decimal] = None,
                           capacidade_maxima_kg: Optional[Decimal] = None,
                           horario_inicio: str = '06:00',
                           horario_fim: str = '22:00',
                           funcionamento_24h: bool = False,
                           telefone: str = '',
                           email: str = '',
                           responsavel: str = '',
                           usuario: Optional[User] = None) -> HubLogistico:
        """
        Cria um novo hub logístico.
        
        Args:
            codigo: Código único do hub
            nome: Nome do hub
            endereco: Endereço completo
            cidade: Cidade
            regiao_id: ID da região
            latitude: Latitude
            longitude: Longitude
            tipo: Tipo do hub
            capacidade_maxima_m3: Capacidade máxima em m³
            capacidade_maxima_kg: Capacidade máxima em kg
            horario_inicio: Horário de início
            horario_fim: Horário de fim
            funcionamento_24h: Se funciona 24h
            telefone: Telefone de contato
            email: Email de contato
            responsavel: Responsável pelo hub
            usuario: Usuário que criou
            
        Returns:
            HubLogistico criado
        """
        try:
            regiao = Regiao.objects.get(id=regiao_id)
            
            hub = HubLogistico.objects.create(
                codigo=codigo,
                nome=nome,
                endereco=endereco,
                cidade=cidade,
                regiao=regiao,
                latitude=latitude,
                longitude=longitude,
                tipo=tipo,
                capacidade_maxima_m3=capacidade_maxima_m3,
                capacidade_maxima_kg=capacidade_maxima_kg,
                horario_inicio=horario_inicio,
                horario_fim=horario_fim,
                funcionamento_24h=funcionamento_24h,
                telefone=telefone,
                email=email,
                responsavel=responsavel,
                ativo=True
            )
            
            self._log_operacao(
                tipo_operacao='CRIAR',
                modelo_afetado='HubLogistico',
                objeto_id=hub.id,
                dados_novos={
                    'codigo': codigo,
                    'nome': nome,
                    'cidade': cidade,
                    'regiao': regiao.nome,
                    'tipo': tipo,
                    'capacidade_m3': float(capacidade_maxima_m3) if capacidade_maxima_m3 else None,
                    'capacidade_kg': float(capacidade_maxima_kg) if capacidade_maxima_kg else None
                },
                usuario=usuario
            )
            
            logger.info(f"Hub logístico criado: {hub.codigo}")
            return hub
            
        except Exception as e:
            logger.error(f"Erro ao criar hub logístico: {e}")
            raise
    
    def criar_catalogo_dimensoes(self,
                                codigo: str,
                                nome: str,
                                comprimento_cm: Decimal,
                                largura_cm: Decimal,
                                altura_cm: Decimal,
                                peso_kg: Decimal,
                                categoria: str = 'PACOTE_MEDIO',
                                usuario: Optional[User] = None) -> CatalogoDimensoes:
        """
        Cria uma nova entrada no catálogo de dimensões.
        
        Args:
            codigo: Código único
            nome: Nome da dimensão
            comprimento_cm: Comprimento em cm
            largura_cm: Largura em cm
            altura_cm: Altura em cm
            peso_kg: Peso em kg
            categoria: Categoria da dimensão
            usuario: Usuário que criou
            
        Returns:
            CatalogoDimensoes criado
        """
        try:
            dimensao = CatalogoDimensoes.objects.create(
                codigo=codigo,
                nome=nome,
                comprimento_cm=comprimento_cm,
                largura_cm=largura_cm,
                altura_cm=altura_cm,
                peso_kg=peso_kg,
                categoria=categoria,
                ativo=True
            )
            
            self._log_operacao(
                tipo_operacao='CRIAR',
                modelo_afetado='CatalogoDimensoes',
                objeto_id=dimensao.id,
                dados_novos={
                    'codigo': codigo,
                    'nome': nome,
                    'comprimento_cm': float(comprimento_cm),
                    'largura_cm': float(largura_cm),
                    'altura_cm': float(altura_cm),
                    'peso_kg': float(peso_kg),
                    'categoria': categoria,
                    'volume_m3': float(dimensao.volume_m3)
                },
                usuario=usuario
            )
            
            logger.info(f"Catálogo de dimensões criado: {dimensao.codigo}")
            return dimensao
            
        except Exception as e:
            logger.error(f"Erro ao criar catálogo de dimensões: {e}")
            raise
    
    def criar_restricao_logistica(self,
                                 codigo: str,
                                 nome: str,
                                 tipo: str,
                                 valor_minimo: Optional[Decimal] = None,
                                 valor_maximo: Optional[Decimal] = None,
                                 unidade_medida: str = '',
                                 aplicavel_veiculo_interno: bool = True,
                                 aplicavel_transportadora: bool = True,
                                 acao_violacao: str = 'AVISAR',
                                 usuario: Optional[User] = None) -> RestricaoLogistica:
        """
        Cria uma nova restrição logística.
        
        Args:
            codigo: Código único da restrição
            nome: Nome da restrição
            tipo: Tipo da restrição
            valor_minimo: Valor mínimo permitido
            valor_maximo: Valor máximo permitido
            unidade_medida: Unidade de medida
            aplicavel_veiculo_interno: Se aplicável a veículos internos
            aplicavel_transportadora: Se aplicável a transportadoras
            acao_violacao: Ação quando violada
            usuario: Usuário que criou
            
        Returns:
            RestricaoLogistica criada
        """
        try:
            restricao = RestricaoLogistica.objects.create(
                codigo=codigo,
                nome=nome,
                tipo=tipo,
                valor_minimo=valor_minimo,
                valor_maximo=valor_maximo,
                unidade_medida=unidade_medida,
                aplicavel_veiculo_interno=aplicavel_veiculo_interno,
                aplicavel_transportadora=aplicavel_transportadora,
                acao_violacao=acao_violacao,
                ativo=True
            )
            
            self._log_operacao(
                tipo_operacao='CRIAR',
                modelo_afetado='RestricaoLogistica',
                objeto_id=restricao.id,
                dados_novos={
                    'codigo': codigo,
                    'nome': nome,
                    'tipo': tipo,
                    'valor_minimo': float(valor_minimo) if valor_minimo else None,
                    'valor_maximo': float(valor_maximo) if valor_maximo else None,
                    'unidade_medida': unidade_medida,
                    'acao_violacao': acao_violacao
                },
                usuario=usuario
            )
            
            logger.info(f"Restrição logística criada: {restricao.codigo}")
            return restricao
            
        except Exception as e:
            logger.error(f"Erro ao criar restrição logística: {e}")
            raise
    
    def validar_restricoes(self,
                          peso_kg: Optional[Decimal] = None,
                          volume_m3: Optional[Decimal] = None,
                          dimensoes: Optional[Dict[str, Decimal]] = None,
                          valor_declarado: Optional[Decimal] = None,
                          zona_entrega_id: Optional[int] = None,
                          transportadora_id: Optional[int] = None,
                          veiculo_interno_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Valida restrições logísticas para uma operação.
        
        Args:
            peso_kg: Peso em kg
            volume_m3: Volume em m³
            dimensoes: Dimensões (comprimento, largura, altura)
            valor_declarado: Valor declarado
            zona_entrega_id: ID da zona de entrega
            transportadora_id: ID da transportadora
            veiculo_interno_id: ID do veículo interno
            
        Returns:
            Dicionário com resultado da validação
        """
        try:
            restricoes_violadas = []
            avisos = []
            bloqueios = []
            
            # Obter restrições ativas
            restricoes = RestricaoLogistica.objects.filter(ativo=True)
            
            for restricao in restricoes:
                # Verificar se restrição se aplica
                aplicavel = False
                if transportadora_id and restricao.aplicavel_transportadora:
                    aplicavel = True
                elif veiculo_interno_id and restricao.aplicavel_veiculo_interno:
                    aplicavel = True
                
                if not aplicavel:
                    continue
                
                # Validar por tipo de restrição
                if restricao.tipo == 'PESO' and peso_kg is not None:
                    if restricao.valor_maximo and peso_kg > restricao.valor_maximo:
                        violacao = {
                            'restricao': restricao.nome,
                            'tipo': 'PESO',
                            'valor_atual': float(peso_kg),
                            'valor_limite': float(restricao.valor_maximo),
                            'unidade': restricao.unidade_medida
                        }
                        restricoes_violadas.append(violacao)
                        
                        if restricao.acao_violacao == 'BLOQUEAR':
                            bloqueios.append(violacao)
                        else:
                            avisos.append(violacao)
                
                elif restricao.tipo == 'VOLUME' and volume_m3 is not None:
                    if restricao.valor_maximo and volume_m3 > restricao.valor_maximo:
                        violacao = {
                            'restricao': restricao.nome,
                            'tipo': 'VOLUME',
                            'valor_atual': float(volume_m3),
                            'valor_limite': float(restricao.valor_maximo),
                            'unidade': restricao.unidade_medida
                        }
                        restricoes_violadas.append(violacao)
                        
                        if restricao.acao_violacao == 'BLOQUEAR':
                            bloqueios.append(violacao)
                        else:
                            avisos.append(violacao)
                
                elif restricao.tipo == 'VALOR' and valor_declarado is not None:
                    if restricao.valor_maximo and valor_declarado > restricao.valor_maximo:
                        violacao = {
                            'restricao': restricao.nome,
                            'tipo': 'VALOR',
                            'valor_atual': float(valor_declarado),
                            'valor_limite': float(restricao.valor_maximo),
                            'unidade': restricao.unidade_medida
                        }
                        restricoes_violadas.append(violacao)
                        
                        if restricao.acao_violacao == 'BLOQUEAR':
                            bloqueios.append(violacao)
                        else:
                            avisos.append(violacao)
            
            resultado = {
                'valido': len(bloqueios) == 0,
                'restricoes_violadas': restricoes_violadas,
                'avisos': avisos,
                'bloqueios': bloqueios,
                'total_violacoes': len(restricoes_violadas)
            }
            
            return resultado
            
        except Exception as e:
            logger.error(f"Erro ao validar restrições: {e}")
            raise
    
    def obter_estatisticas_masterdata(self) -> Dict[str, Any]:
        """
        Obtém estatísticas dos dados mestres.
        
        Returns:
            Dicionário com estatísticas
        """
        try:
            stats = {
                'regioes': {
                    'total': Regiao.objects.filter(ativo=True).count(),
                    'com_coordenadas': Regiao.objects.filter(
                        ativo=True,
                        latitude_centro__isnull=False,
                        longitude_centro__isnull=False
                    ).count()
                },
                'zonas_entrega': {
                    'total': ZonaEntrega.objects.filter(ativo=True).count(),
                    'por_regiao': dict(
                        ZonaEntrega.objects.filter(ativo=True)
                        .values('regiao__nome')
                        .annotate(count=Count('id'))
                        .values_list('regiao__nome', 'count')
                    )
                },
                'hubs_logisticos': {
                    'total': HubLogistico.objects.filter(ativo=True).count(),
                    'por_tipo': dict(
                        HubLogistico.objects.filter(ativo=True)
                        .values('tipo')
                        .annotate(count=Count('id'))
                        .values_list('tipo', 'count')
                    ),
                    'funcionamento_24h': HubLogistico.objects.filter(
                        ativo=True,
                        funcionamento_24h=True
                    ).count()
                },
                'catalogo_dimensoes': {
                    'total': CatalogoDimensoes.objects.filter(ativo=True).count(),
                    'por_categoria': dict(
                        CatalogoDimensoes.objects.filter(ativo=True)
                        .values('categoria')
                        .annotate(count=Count('id'))
                        .values_list('categoria', 'count')
                    )
                },
                'restricoes_logisticas': {
                    'total': RestricaoLogistica.objects.filter(ativo=True).count(),
                    'por_tipo': dict(
                        RestricaoLogistica.objects.filter(ativo=True)
                        .values('tipo')
                        .annotate(count=Count('id'))
                        .values_list('tipo', 'count')
                    )
                },
                'permissoes_logisticas': {
                    'total': PermissaoLogistica.objects.filter(ativo=True).count(),
                    'por_modulo': dict(
                        PermissaoLogistica.objects.filter(ativo=True)
                        .values('modulo')
                        .annotate(count=Count('id'))
                        .values_list('modulo', 'count')
                    )
                }
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas de masterdata: {e}")
            raise
    
    def obter_logs_masterdata(self,
                             modelo_afetado: Optional[str] = None,
                             usuario_id: Optional[int] = None,
                             data_inicio: Optional[date] = None,
                             data_fim: Optional[date] = None,
                             limite: int = 100) -> List[LogMasterdata]:
        """
        Obtém logs de operações em dados mestres.
        
        Args:
            modelo_afetado: Filtrar por modelo específico
            usuario_id: Filtrar por usuário específico
            data_inicio: Data de início
            data_fim: Data de fim
            limite: Limite de resultados
            
        Returns:
            Lista de logs
        """
        try:
            queryset = LogMasterdata.objects.all()
            
            if modelo_afetado:
                queryset = queryset.filter(modelo_afetado=modelo_afetado)
            
            if usuario_id:
                queryset = queryset.filter(usuario_id=usuario_id)
            
            if data_inicio:
                queryset = queryset.filter(data_operacao__date__gte=data_inicio)
            
            if data_fim:
                queryset = queryset.filter(data_operacao__date__lte=data_fim)
            
            return list(queryset.order_by('-data_operacao')[:limite])
            
        except Exception as e:
            logger.error(f"Erro ao obter logs de masterdata: {e}")
            raise


# Instância global do serviço
masterdata_service = MasterdataService()
