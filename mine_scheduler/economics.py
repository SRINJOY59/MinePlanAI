from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EconomicParameters:
    metal_price_per_grade_tonne: float = 9200.0
    drill_cost_per_hour: float = 650.0
    blast_cost_per_hour: float = 1250.0
    haul_cost_per_hour: float = 340.0
    processing_cost_per_tonne: float = 16.0
    discount_rate_per_hour: float = 0.0008


def compute_block_economics(
    tonnage: float,
    ore_grade: float,
    drill_hours: int,
    blast_hours: int,
    haul_hours: int,
    params: EconomicParameters | None = None,
) -> dict[str, float]:
    settings = params or EconomicParameters()
    revenue = tonnage * ore_grade * settings.metal_price_per_grade_tonne
    cost = (
        drill_hours * settings.drill_cost_per_hour
        + blast_hours * settings.blast_cost_per_hour
        + haul_hours * settings.haul_cost_per_hour
        + tonnage * settings.processing_cost_per_tonne
    )
    net_value = revenue - cost
    value_density = net_value / tonnage if tonnage else 0.0
    return {
        "revenue": round(revenue, 2),
        "cost": round(cost, 2),
        "net_value": round(net_value, 2),
        "value_density": round(value_density, 4),
    }


def discounted_value(
    net_value: float,
    completion_hour: int,
    discount_rate_per_hour: float,
) -> float:
    return net_value / ((1.0 + discount_rate_per_hour) ** completion_hour)
