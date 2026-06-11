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
    distancia_km: Optional[float] = None,
    currency: str = 'MZN',
    fuel_surcharge_pct: float = 0.0,
    tolls_flat: float = 0.0,
    insurance_pct: float = 0.0,
) -> PricingResult:
    """
    Cálculo de frete para transportadora externa:
      - custo_fixo + custo_por_kg * peso_efetivo + custo_por_km * distancia_km
      - adicionais: combustível (%), pedágios (flat), seguro (%)
      - prazo: usa prazo_entrega_padrao; se origem == destino, reduz 1 dia (mínimo 1)
    """
    total_effective_weight = 0.0
    declared_total = 0.0
    peso_real_total = 0.0
    peso_volumetrico_total = 0.0
    for it in items:
        volumetric = _volumetric_weight_kg(it.length_cm, it.width_cm, it.height_cm)
        effective = _effective_weight_kg(it)
        total_effective_weight += effective
        peso_real_total += max(0.0, it.weight_kg or 0.0)
        peso_volumetrico_total += volumetric
        declared_total += max(0.0, it.declared_value or 0.0)

    distancia = max(0.0, float(distancia_km or 0))
    custo_fixo = float(getattr(transportadora, 'custo_fixo', 0) or 0)
    custo_peso = float(getattr(transportadora, 'custo_por_kg', 0) or 0) * total_effective_weight
    custo_distancia = float(getattr(transportadora, 'custo_por_km', 0) or 0) * distancia
    base_cost = custo_fixo + custo_peso + custo_distancia

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
            'custo_fixo': round(custo_fixo, 2),
            'custo_peso': round(custo_peso, 2),
            'custo_distancia': round(custo_distancia, 2),
            'base_cost': round(base_cost, 2),
            'fuel_surcharge': round(fuel, 2),
            'tolls': round(tolls, 2),
            'insurance': round(insurance, 2),
            'weight_kg': round(total_effective_weight, 3),
            'peso_real_kg': round(peso_real_total, 3),
            'peso_volumetrico_kg': round(peso_volumetrico_total, 3),
            'distancia_km': round(distancia, 3),
            'declared_total': round(declared_total, 2),
        },
    )


def calculate_freight_veiculo_interno(
    *,
    veiculo,
    distancia_km: float,
    peso_kg: float = 1.0,
    custo_fixo_entrega: float = 20.0,
    currency: str = 'MZN',
) -> PricingResult:
    """Frete para frota interna: custo por km + custo fixo por entrega."""
    distancia = max(0.0, float(distancia_km or 0))
    custo_km = float(getattr(veiculo, 'custo_por_km', 0) or 0)
    custo_distancia = custo_km * distancia
    custo_fixo = max(0.0, float(custo_fixo_entrega))
    total_cost = custo_distancia + custo_fixo

    return PricingResult(
        total_cost=round(total_cost, 2),
        currency=currency,
        estimated_days=1,
        breakdown={
            'custo_distancia': round(custo_distancia, 2),
            'custo_fixo_entrega': round(custo_fixo, 2),
            'distancia_km': round(distancia, 3),
            'custo_por_km': round(custo_km, 2),
            'weight_kg': round(max(0.0, peso_kg), 3),
        },
    )


