from dataclasses import dataclass
from typing import List, Optional, Protocol, Dict, Any


@dataclass
class QuoteItem:
    weight_kg: float
    length_cm: float
    width_cm: float
    height_cm: float
    declared_value: float = 0.0


@dataclass
class QuoteRequest:
    origin_postal_code: str
    destination_postal_code: str
    items: List[QuoteItem]
    service_level: Optional[str] = None  # e.g., ECONOMY, EXPRESS
    insurance: bool = False


@dataclass
class QuoteResponse:
    carrier_code: str
    service_level: str
    total_cost: float
    currency: str = 'MZN'
    estimated_days: Optional[int] = None
    breakdown: Optional[Dict[str, float]] = None  # fuel, tolls, insurance, etc.


@dataclass
class TrackingEvent:
    code: str  # e.g., COLETADO, EM_TRANSITO, ENTREGUE, TENTATIVA_ENTREGA
    description: str
    timestamp_iso: str
    location: Optional[str] = None


@dataclass
class TrackingInfo:
    tracking_code: str
    status: str
    events: List[TrackingEvent]


@dataclass
class PickupRequest:
    scheduled_date_iso: str
    address: str
    contact_name: str
    contact_phone: str
    reference: Optional[str] = None


@dataclass
class PickupResponse:
    pickup_id: str
    scheduled_date_iso: str
    status: str


@dataclass
class ProofOfDelivery:
    delivered_at_iso: str
    receiver_name: str
    signature_image_b64: Optional[str] = None
    photos_b64: Optional[List[str]] = None
    gps_lat: Optional[float] = None
    gps_lng: Optional[float] = None


class CarrierClient(Protocol):
    """Carrier client contract. Concrete implementations must be provided later."""

    def quote(self, request: QuoteRequest) -> List[QuoteResponse]:
        ...

    def track(self, tracking_code: str) -> TrackingInfo:
        ...

    def schedule_pickup(self, request: PickupRequest) -> PickupResponse:
        ...

    def get_pod(self, tracking_code: str) -> ProofOfDelivery:
        ...


