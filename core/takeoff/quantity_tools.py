"""Reusable quantity adjustments."""
from __future__ import annotations
from typing import Iterable, Any

def apply_waste(quantity: float, waste: float = 0.0) -> float:
    q=float(quantity); w=float(waste)
    if q<0: raise ValueError("quantity must be non-negative")
    if w<0: raise ValueError("waste must be non-negative")
    return q*(1+w/100.0) if w else q

def apply_factor(quantity: float, factor: float = 1.0) -> float:
    q=float(quantity); f=float(factor)
    if q<0 or f<0: raise ValueError("quantity and factor must be non-negative")
    return q*f

def sum_quantities(rows: Iterable[Any], field: str = "quantity") -> float:
    total=0.0
    for row in rows:
        value=row.get(field,0) if isinstance(row,dict) else getattr(row,field,0)
        total += float(value or 0)
    return total
