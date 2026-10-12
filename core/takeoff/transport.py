"""Offline transport quantity/cost helpers."""
from __future__ import annotations
from typing import Any

def calculate_transport(quantity: float, distance_km: float, unit_cost: float = 0.0, trips: float = 1.0) -> dict[str,float]:
    q=float(quantity); d=float(distance_km); c=float(unit_cost); t=float(trips)
    if min(q,d,c,t)<0: raise ValueError("transport inputs must be non-negative")
    return {
        "quantity": q,
        "distance_km": d,
        "trips": t,
        "ton_km_or_unit_km": q*d*t,
        "transport_cost": q*d*t*c,
    }
