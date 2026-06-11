from dataclasses import dataclass
from typing import List, Optional, Dict


@dataclass
class PricingItem:
    weight_kg: float
    length_cm: float = 0
    width_cm: float = 0
    height_cm: float = 0
    declared_value: float = 0.0


@dataclass
class PricingResult:
    total_cost: float
    currency: str
    estimated_days: int
    breakdown: Dict[str, float]


def _volumetric_weight_kg(length_cm: float, width_cm: float, height_cm: float, divisor: float = 6000.0) -> float:
    if not (length_cm and width_cm and height_cm):
        return 0.0
    return (length_cm * width_cm * height_cm) / divisor


def _effective_weight_kg(item: PricingItem) -> float:
    volumetric = _volumetric_weight_kg(item.length_cm, item.width_cm, item.height_cm)
    return max(item.weight_kg, volumetric)


def calculate_quote(
    *,
    transportadora,
    items: List[PricingItem],
    origem_provincia: Optional[str] = None,
    destino_provincia: Optional[str] = None,
    currency: str = 'MZN',
    fuel_surcharge_pct: float = 0.0,
    tolls_flat: float = 0.0,
    insurance_pct: float = 0.0,
) -> PricingResult:
    """
    Cálculo básico de frete usando campos já existentes em Transportadora:
      - custo_fixo + custo_por_kg * peso_efetivo (soma dos itens)
      - adicionais: combustível (%), pedágios (flat), seguro (%)
      - prazo: usa prazo_entrega_padrao; se origem == destino, reduz 1 dia (mínimo 1)

    Este serviço é intencionalmente simples (sem modelos de tabela). Posteriormente,
    pode ser estendido para consumir tabelas de tarifa/SLA.
    """
    total_effective_weight = 0.0
    declared_total = 0.0
    for it in items:
        total_effective_weight += _effective_weight_kg(it)
        declared_total += max(0.0, it.declared_value or 0.0)

    base_cost = float(getattr(transportadora, 'custo_fixo', 0) or 0) + (
        float(getattr(transportadora, 'custo_por_kg', 0) or 0) * total_effective_weight
    )

    fuel = base_cost * max(0.0, fuel_surcharge_pct)
    tolls = max(0.0, tolls_flat)
    insurance = declared_total * max(0.0, insurance_pct)

    total_cost = base_cost + fuel + tolls + insurance

    prazo = int(getattr(transportadora, 'prazo_entrega_padrao', 1) or 1)
    if origem_provincia and destino_provincia and origem_provincia == destino_provincia:
        prazo = max(1, prazo - 1)

    return PricingResult(
        total_cost=round(total_cost, 2),
        currency=currency,
        estimated_days=prazo,
        breakdown={
            'base_cost': round(base_cost, 2),
            'fuel_surcharge': round(fuel, 2),
            'tolls': round(tolls, 2),
            'insurance': round(insurance, 2),
            'weight_kg': round(total_effective_weight, 3),
            'declared_total': round(declared_total, 2),
        },
    )


