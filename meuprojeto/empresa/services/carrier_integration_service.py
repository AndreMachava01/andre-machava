"""
Implementações reais de integração com APIs de transportadoras.
"""
import logging
import requests
import json
import base64
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from decimal import Decimal
import xml.etree.ElementTree as ET
from django.utils import timezone

from ..models_stock import Transportadora, RastreamentoEntrega
from ..services.carriers.contracts import (
    CarrierClient, QuoteRequest, QuoteResponse, 
    PickupRequest, PickupResponse, TrackingResponse,
    ProofOfDeliveryRequest, ProofOfDeliveryResponse
)

logger = logging.getLogger(__name__)


class CorreiosClient(CarrierClient):
    """Cliente para integração com Correios (Brasil)."""
    
    def __init__(self, api_key: str, api_secret: str, environment: str = 'sandbox'):
        self.api_key = api_key
        self.api_secret = api_secret
        self.environment = environment
        self.base_url = 'https://api.correios.com.br' if environment == 'production' else 'https://api-sandbox.correios.com.br'
        self.session = requests.Session()
        self._setup_auth()
    
    def _setup_auth(self):
        """Configura autenticação com Correios."""
        auth_string = f"{self.api_key}:{self.api_secret}"
        auth_bytes = auth_string.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
        
        self.session.headers.update({
            'Authorization': f'Basic {auth_b64}',
            'Content-Type': 'application/json',
            'User-Agent': 'LogisticaApp/1.0'
        })
    
    def quote(self, request: QuoteRequest) -> QuoteResponse:
        """Calcula cotação de frete com Correios."""
        try:
            # Preparar dados para API dos Correios
            payload = {
                'servicos': ['PAC', 'SEDEX', 'SEDEX10', 'SEDEX12'],
                'cepOrigem': request.origin_zipcode,
                'cepDestino': request.destination_zipcode,
                'peso': str(request.weight_kg),
                'comprimento': str(request.length_cm),
                'altura': str(request.height_cm),
                'largura': str(request.width_cm),
                'valorDeclarado': str(request.declared_value),
                'maoPropria': 'N',
                'avisoRecebimento': 'N'
            }
            
            response = self.session.post(
                f"{self.base_url}/v1/calculador/calcular",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Processar resposta dos Correios
                quotes = []
                for servico in data.get('servicos', []):
                    if servico.get('erro') == '0':  # Sem erro
                        quotes.append({
                            'service_code': servico.get('codigo'),
                            'service_name': servico.get('nome'),
                            'cost': Decimal(servico.get('valor', '0')),
                            'delivery_days': int(servico.get('prazoEntrega', 0)),
                            'delivery_date': self._calculate_delivery_date(int(servico.get('prazoEntrega', 0))),
                            'carrier': 'CORREIOS'
                        })
                
                return QuoteResponse(
                    success=True,
                    quotes=quotes,
                    currency='BRL',
                    raw_response=data
                )
            else:
                return QuoteResponse(
                    success=False,
                    error=f"Erro na API Correios: {response.status_code} - {response.text}",
                    quotes=[]
                )
                
        except Exception as e:
            logger.error(f"Erro ao calcular cotação Correios: {e}")
            return QuoteResponse(
                success=False,
                error=str(e),
                quotes=[]
            )
    
    def request_pickup(self, request: PickupRequest) -> PickupResponse:
        """Solicita coleta com Correios."""
        try:
            payload = {
                'numeroPedido': request.order_number,
                'cepOrigem': request.origin_zipcode,
                'cepDestino': request.destination_zipcode,
                'peso': str(request.weight_kg),
                'valorDeclarado': str(request.declared_value),
                'servico': request.service_code,
                'dataColeta': request.pickup_date.strftime('%Y-%m-%d'),
                'horarioColeta': request.pickup_time.strftime('%H:%M'),
                'observacoes': request.notes or ''
            }
            
            response = self.session.post(
                f"{self.base_url}/v1/coleta/solicitar",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                return PickupResponse(
                    success=True,
                    pickup_id=data.get('numeroColeta'),
                    tracking_code=data.get('codigoRastreamento'),
                    pickup_date=datetime.strptime(data.get('dataColeta'), '%Y-%m-%d').date(),
                    estimated_cost=Decimal(data.get('valorEstimado', '0')),
                    raw_response=data
                )
            else:
                return PickupResponse(
                    success=False,
                    error=f"Erro na solicitação de coleta: {response.status_code} - {response.text}"
                )
                
        except Exception as e:
            logger.error(f"Erro ao solicitar coleta Correios: {e}")
            return PickupResponse(
                success=False,
                error=str(e)
            )
    
    def track_shipment(self, request) -> TrackingResponse:  # TrackingRequest
        """Rastreia envio com Correios."""
        try:
            response = self.session.get(
                f"{self.base_url}/v1/rastreamento/{request.tracking_code}",
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Processar eventos de rastreamento
                events = []
                for evento in data.get('eventos', []):
                    events.append({
                        'date': datetime.strptime(evento.get('data'), '%d/%m/%Y').date(),
                        'time': evento.get('hora', '00:00'),
                        'location': evento.get('local', ''),
                        'status': evento.get('status', ''),
                        'description': evento.get('descricao', '')
                    })
                
                return TrackingResponse(
                    success=True,
                    tracking_code=request.tracking_code,
                    status=data.get('statusAtual', ''),
                    events=events,
                    estimated_delivery=data.get('dataPrevistaEntrega'),
                    raw_response=data
                )
            else:
                return TrackingResponse(
                    success=False,
                    error=f"Erro no rastreamento: {response.status_code} - {response.text}"
                )
                
        except Exception as e:
            logger.error(f"Erro ao rastrear envio Correios: {e}")
            return TrackingResponse(
                success=False,
                error=str(e)
            )
    
    def request_proof_of_delivery(self, request: ProofOfDeliveryRequest) -> ProofOfDeliveryResponse:
        """Solicita comprovante de entrega com Correios."""
        try:
            payload = {
                'codigoRastreamento': request.tracking_code,
                'tipoComprovante': request.proof_type,
                'formato': request.format
            }
            
            response = self.session.post(
                f"{self.base_url}/v1/comprovante/solicitar",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                return ProofOfDeliveryResponse(
                    success=True,
                    proof_url=data.get('urlComprovante'),
                    proof_data=data.get('dadosComprovante'),
                    raw_response=data
                )
            else:
                return ProofOfDeliveryResponse(
                    success=False,
                    error=f"Erro ao solicitar comprovante: {response.status_code} - {response.text}"
                )
                
        except Exception as e:
            logger.error(f"Erro ao solicitar comprovante Correios: {e}")
            return ProofOfDeliveryResponse(
                success=False,
                error=str(e)
            )
    
    def _calculate_delivery_date(self, delivery_days: int) -> datetime.date:
        """Calcula data de entrega baseada nos dias úteis."""
        from datetime import datetime, timedelta
        
        current_date = datetime.now().date()
        business_days = 0
        
        while business_days < delivery_days:
            current_date += timedelta(days=1)
            # Considerar apenas dias úteis (segunda a sexta)
            if current_date.weekday() < 5:
                business_days += 1
        
        return current_date


class DHLClient(CarrierClient):
    """Cliente para integração com DHL."""
    
    def __init__(self, api_key: str, api_secret: str, environment: str = 'sandbox'):
        self.api_key = api_key
        self.api_secret = api_secret
        self.environment = environment
        self.base_url = 'https://api-eu.dhl.com' if environment == 'production' else 'https://api-sandbox.dhl.com'
        self.session = requests.Session()
        self._setup_auth()
    
    def _setup_auth(self):
        """Configura autenticação com DHL."""
        auth_string = f"{self.api_key}:{self.api_secret}"
        auth_bytes = auth_string.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
        
        self.session.headers.update({
            'Authorization': f'Basic {auth_b64}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
    
    def quote(self, request: QuoteRequest) -> QuoteResponse:
        """Calcula cotação de frete com DHL."""
        try:
            payload = {
                'originCountryCode': 'BR',
                'originPostalCode': request.origin_zipcode,
                'destinationCountryCode': 'BR',
                'destinationPostalCode': request.destination_zipcode,
                'weight': request.weight_kg,
                'length': request.length_cm,
                'width': request.width_cm,
                'height': request.height_cm,
                'declaredValue': request.declared_value,
                'currency': 'BRL'
            }
            
            response = self.session.post(
                f"{self.base_url}/v1/rates",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                quotes = []
                for rate in data.get('rates', []):
                    quotes.append({
                        'service_code': rate.get('serviceCode'),
                        'service_name': rate.get('serviceName'),
                        'cost': Decimal(str(rate.get('totalPrice', 0))),
                        'delivery_days': rate.get('deliveryDays', 0),
                        'delivery_date': self._parse_delivery_date(rate.get('deliveryDate')),
                        'carrier': 'DHL'
                    })
                
                return QuoteResponse(
                    success=True,
                    quotes=quotes,
                    currency='BRL',
                    raw_response=data
                )
            else:
                return QuoteResponse(
                    success=False,
                    error=f"Erro na API DHL: {response.status_code} - {response.text}",
                    quotes=[]
                )
                
        except Exception as e:
            logger.error(f"Erro ao calcular cotação DHL: {e}")
            return QuoteResponse(
                success=False,
                error=str(e),
                quotes=[]
            )
    
    def request_pickup(self, request: PickupRequest) -> PickupResponse:
        """Solicita coleta com DHL."""
        try:
            payload = {
                'pickupDate': request.pickup_date.strftime('%Y-%m-%d'),
                'pickupTime': request.pickup_time.strftime('%H:%M'),
                'originPostalCode': request.origin_zipcode,
                'destinationPostalCode': request.destination_zipcode,
                'weight': request.weight_kg,
                'declaredValue': request.declared_value,
                'serviceCode': request.service_code,
                'notes': request.notes or ''
            }
            
            response = self.session.post(
                f"{self.base_url}/v1/pickups",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 201:
                data = response.json()
                
                return PickupResponse(
                    success=True,
                    pickup_id=data.get('pickupId'),
                    tracking_code=data.get('trackingNumber'),
                    pickup_date=datetime.strptime(data.get('pickupDate'), '%Y-%m-%d').date(),
                    estimated_cost=Decimal(str(data.get('estimatedCost', 0))),
                    raw_response=data
                )
            else:
                return PickupResponse(
                    success=False,
                    error=f"Erro na solicitação de coleta: {response.status_code} - {response.text}"
                )
                
        except Exception as e:
            logger.error(f"Erro ao solicitar coleta DHL: {e}")
            return PickupResponse(
                success=False,
                error=str(e)
            )
    
    def track_shipment(self, request) -> TrackingResponse:  # TrackingRequest
        """Rastreia envio com DHL."""
        try:
            response = self.session.get(
                f"{self.base_url}/v1/tracking/{request.tracking_code}",
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                events = []
                for event in data.get('events', []):
                    events.append({
                        'date': datetime.strptime(event.get('date'), '%Y-%m-%d').date(),
                        'time': event.get('time', '00:00'),
                        'location': event.get('location', ''),
                        'status': event.get('status', ''),
                        'description': event.get('description', '')
                    })
                
                return TrackingResponse(
                    success=True,
                    tracking_code=request.tracking_code,
                    status=data.get('status', ''),
                    events=events,
                    estimated_delivery=data.get('estimatedDelivery'),
                    raw_response=data
                )
            else:
                return TrackingResponse(
                    success=False,
                    error=f"Erro no rastreamento: {response.status_code} - {response.text}"
                )
                
        except Exception as e:
            logger.error(f"Erro ao rastrear envio DHL: {e}")
            return TrackingResponse(
                success=False,
                error=str(e)
            )
    
    def request_proof_of_delivery(self, request: ProofOfDeliveryRequest) -> ProofOfDeliveryResponse:
        """Solicita comprovante de entrega com DHL."""
        try:
            payload = {
                'trackingNumber': request.tracking_code,
                'proofType': request.proof_type,
                'format': request.format
            }
            
            response = self.session.post(
                f"{self.base_url}/v1/proof-of-delivery",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                return ProofOfDeliveryResponse(
                    success=True,
                    proof_url=data.get('proofUrl'),
                    proof_data=data.get('proofData'),
                    raw_response=data
                )
            else:
                return ProofOfDeliveryResponse(
                    success=False,
                    error=f"Erro ao solicitar comprovante: {response.status_code} - {response.text}"
                )
                
        except Exception as e:
            logger.error(f"Erro ao solicitar comprovante DHL: {e}")
            return ProofOfDeliveryResponse(
                success=False,
                error=str(e)
            )
    
    def _parse_delivery_date(self, delivery_date_str: str) -> Optional[datetime.date]:
        """Converte string de data para objeto date."""
        if not delivery_date_str:
            return None
        
        try:
            return datetime.strptime(delivery_date_str, '%Y-%m-%d').date()
        except ValueError:
            return None


class LocalCarrierClient(CarrierClient):
    """Cliente para integração com transportadoras locais."""
    
    def __init__(self, api_key: str, api_url: str, environment: str = 'sandbox'):
        self.api_key = api_key
        self.api_url = api_url
        self.environment = environment
        self.session = requests.Session()
        self._setup_auth()
    
    def _setup_auth(self):
        """Configura autenticação com transportadora local."""
        self.session.headers.update({
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'User-Agent': 'LogisticaApp/1.0'
        })
    
    def quote(self, request: QuoteRequest) -> QuoteResponse:
        """Calcula cotação de frete com transportadora local."""
        try:
            payload = {
                'origin_zipcode': request.origin_zipcode,
                'destination_zipcode': request.destination_zipcode,
                'weight_kg': request.weight_kg,
                'length_cm': request.length_cm,
                'width_cm': request.width_cm,
                'height_cm': request.height_cm,
                'declared_value': request.declared_value,
                'currency': 'BRL'
            }
            
            response = self.session.post(
                f"{self.api_url}/api/v1/quotes",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                quotes = []
                for quote in data.get('quotes', []):
                    quotes.append({
                        'service_code': quote.get('service_code'),
                        'service_name': quote.get('service_name'),
                        'cost': Decimal(str(quote.get('cost', 0))),
                        'delivery_days': quote.get('delivery_days', 0),
                        'delivery_date': self._parse_delivery_date(quote.get('delivery_date')),
                        'carrier': 'LOCAL'
                    })
                
                return QuoteResponse(
                    success=True,
                    quotes=quotes,
                    currency='BRL',
                    raw_response=data
                )
            else:
                return QuoteResponse(
                    success=False,
                    error=f"Erro na API local: {response.status_code} - {response.text}",
                    quotes=[]
                )
                
        except Exception as e:
            logger.error(f"Erro ao calcular cotação local: {e}")
            return QuoteResponse(
                success=False,
                error=str(e),
                quotes=[]
            )
    
    def request_pickup(self, request: PickupRequest) -> PickupResponse:
        """Solicita coleta com transportadora local."""
        try:
            payload = {
                'pickup_date': request.pickup_date.strftime('%Y-%m-%d'),
                'pickup_time': request.pickup_time.strftime('%H:%M'),
                'origin_zipcode': request.origin_zipcode,
                'destination_zipcode': request.destination_zipcode,
                'weight_kg': request.weight_kg,
                'declared_value': request.declared_value,
                'service_code': request.service_code,
                'notes': request.notes or ''
            }
            
            response = self.session.post(
                f"{self.api_url}/api/v1/pickups",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 201:
                data = response.json()
                
                return PickupResponse(
                    success=True,
                    pickup_id=data.get('pickup_id'),
                    tracking_code=data.get('tracking_code'),
                    pickup_date=datetime.strptime(data.get('pickup_date'), '%Y-%m-%d').date(),
                    estimated_cost=Decimal(str(data.get('estimated_cost', 0))),
                    raw_response=data
                )
            else:
                return PickupResponse(
                    success=False,
                    error=f"Erro na solicitação de coleta: {response.status_code} - {response.text}"
                )
                
        except Exception as e:
            logger.error(f"Erro ao solicitar coleta local: {e}")
            return PickupResponse(
                success=False,
                error=str(e)
            )
    
    def track_shipment(self, request) -> TrackingResponse:  # TrackingRequest
        """Rastreia envio com transportadora local."""
        try:
            response = self.session.get(
                f"{self.api_url}/api/v1/tracking/{request.tracking_code}",
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                events = []
                for event in data.get('events', []):
                    events.append({
                        'date': datetime.strptime(event.get('date'), '%Y-%m-%d').date(),
                        'time': event.get('time', '00:00'),
                        'location': event.get('location', ''),
                        'status': event.get('status', ''),
                        'description': event.get('description', '')
                    })
                
                return TrackingResponse(
                    success=True,
                    tracking_code=request.tracking_code,
                    status=data.get('status', ''),
                    events=events,
                    estimated_delivery=data.get('estimated_delivery'),
                    raw_response=data
                )
            else:
                return TrackingResponse(
                    success=False,
                    error=f"Erro no rastreamento: {response.status_code} - {response.text}"
                )
                
        except Exception as e:
            logger.error(f"Erro ao rastrear envio local: {e}")
            return TrackingResponse(
                success=False,
                error=str(e)
            )
    
    def request_proof_of_delivery(self, request: ProofOfDeliveryRequest) -> ProofOfDeliveryResponse:
        """Solicita comprovante de entrega com transportadora local."""
        try:
            payload = {
                'tracking_code': request.tracking_code,
                'proof_type': request.proof_type,
                'format': request.format
            }
            
            response = self.session.post(
                f"{self.api_url}/api/v1/proof-of-delivery",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                return ProofOfDeliveryResponse(
                    success=True,
                    proof_url=data.get('proof_url'),
                    proof_data=data.get('proof_data'),
                    raw_response=data
                )
            else:
                return ProofOfDeliveryResponse(
                    success=False,
                    error=f"Erro ao solicitar comprovante: {response.status_code} - {response.text}"
                )
                
        except Exception as e:
            logger.error(f"Erro ao solicitar comprovante local: {e}")
            return ProofOfDeliveryResponse(
                success=False,
                error=str(e)
            )
    
    def _parse_delivery_date(self, delivery_date_str: str) -> Optional[datetime.date]:
        """Converte string de data para objeto date."""
        if not delivery_date_str:
            return None
        
        try:
            return datetime.strptime(delivery_date_str, '%Y-%m-%d').date()
        except ValueError:
            return None


class CarrierIntegrationService:
    """Serviço para gerenciar integrações com transportadoras."""
    
    def __init__(self):
        self.clients = {}
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Inicializa clientes das transportadoras."""
        from django.conf import settings
        
        # Correios
        if hasattr(settings, 'CORREIOS_API_KEY'):
            self.clients['CORREIOS'] = CorreiosClient(
                api_key=settings.CORREIOS_API_KEY,
                api_secret=settings.CORREIOS_API_SECRET,
                environment=getattr(settings, 'CORREIOS_ENVIRONMENT', 'sandbox')
            )
        
        # DHL
        if hasattr(settings, 'DHL_API_KEY'):
            self.clients['DHL'] = DHLClient(
                api_key=settings.DHL_API_KEY,
                api_secret=settings.DHL_API_SECRET,
                environment=getattr(settings, 'DHL_ENVIRONMENT', 'sandbox')
            )
        
        # Transportadora Local
        if hasattr(settings, 'LOCAL_CARRIER_API_KEY'):
            self.clients['LOCAL'] = LocalCarrierClient(
                api_key=settings.LOCAL_CARRIER_API_KEY,
                api_url=settings.LOCAL_CARRIER_API_URL,
                environment=getattr(settings, 'LOCAL_CARRIER_ENVIRONMENT', 'sandbox')
            )
    
    def get_client(self, carrier_code: str) -> Optional[CarrierClient]:
        """Obtém cliente da transportadora."""
        return self.clients.get(carrier_code)
    
    def quote_all_carriers(self, request: QuoteRequest) -> Dict[str, QuoteResponse]:
        """Calcula cotações de todas as transportadoras disponíveis."""
        results = {}
        
        for carrier_code, client in self.clients.items():
            try:
                results[carrier_code] = client.quote(request)
            except Exception as e:
                logger.error(f"Erro ao cotar com {carrier_code}: {e}")
                results[carrier_code] = QuoteResponse(
                    success=False,
                    error=str(e),
                    quotes=[]
                )
        
        return results
    
    def track_all_carriers(self, tracking_code: str) -> Dict[str, TrackingResponse]:
        """Rastreia em todas as transportadoras disponíveis."""
        results = {}
        # request = TrackingRequest(tracking_code=tracking_code)
        
        for carrier_code, client in self.clients.items():
            try:
                results[carrier_code] = client.track_shipment(request)
            except Exception as e:
                logger.error(f"Erro ao rastrear com {carrier_code}: {e}")
                results[carrier_code] = TrackingResponse(
                    success=False,
                    error=str(e)
                )
        
        return results
    
    def sync_tracking_data(self, rastreamento_id: int):
        """Sincroniza dados de rastreamento com transportadoras."""
        try:
            rastreamento = RastreamentoEntrega.objects.get(id=rastreamento_id)
            
            if not rastreamento.codigo_rastreamento:
                logger.warning(f"Rastreamento {rastreamento_id} sem código de rastreamento")
                return
            
            # Determinar transportadora
            carrier_code = self._determine_carrier_code(rastreamento)
            if not carrier_code:
                logger.warning(f"Não foi possível determinar transportadora para rastreamento {rastreamento_id}")
                return
            
            client = self.get_client(carrier_code)
            if not client:
                logger.warning(f"Cliente não disponível para transportadora {carrier_code}")
                return
            
            # Rastrear envio
            # request = TrackingRequest(tracking_code=rastreamento.codigo_rastreamento)
            response = client.track_shipment(request)
            
            if response.success:
                # Atualizar status do rastreamento
                rastreamento.status_atual = response.status
                rastreamento.data_atualizacao = timezone.now()
                rastreamento.save()
                
                # Criar eventos de rastreamento
                self._create_tracking_events(rastreamento, response.events)
                
                logger.info(f"Dados de rastreamento sincronizados para {rastreamento_id}")
            else:
                logger.error(f"Erro ao sincronizar rastreamento {rastreamento_id}: {response.error}")
                
        except Exception as e:
            logger.error(f"Erro ao sincronizar dados de rastreamento: {e}")
    
    def _determine_carrier_code(self, rastreamento: RastreamentoEntrega) -> Optional[str]:
        """Determina código da transportadora baseado no rastreamento."""
        if rastreamento.transportadora:
            # Mapear transportadora para código
            nome = rastreamento.transportadora.nome.upper()
            if 'CORREIOS' in nome:
                return 'CORREIOS'
            elif 'DHL' in nome:
                return 'DHL'
            else:
                return 'LOCAL'
        
        return None
    
    def _create_tracking_events(self, rastreamento: RastreamentoEntrega, events: List[Dict]):
        """Cria eventos de rastreamento baseado nos dados da transportadora."""
        from ..models_stock import EventoRastreamento
        
        for event_data in events:
            try:
                # Verificar se evento já existe
                existing_event = EventoRastreamento.objects.filter(
                    rastreamento=rastreamento,
                    data_evento__date=event_data['date'],
                    descricao=event_data['description']
                ).first()
                
                if not existing_event:
                    EventoRastreamento.objects.create(
                        rastreamento=rastreamento,
                        tipo_evento=event_data['status'],
                        descricao=event_data['description'],
                        localizacao=event_data['location'],
                        data_evento=datetime.combine(event_data['date'], datetime.strptime(event_data['time'], '%H:%M').time()),
                        usuario=None
                    )
                    
            except Exception as e:
                logger.error(f"Erro ao criar evento de rastreamento: {e}")


# Instância global do serviço de integração
carrier_integration_service = CarrierIntegrationService()
