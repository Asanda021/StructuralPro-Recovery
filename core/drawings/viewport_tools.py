"""Geometry helpers for interactive drawing viewport tools."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ViewportRect:
    """Axis-aligned rectangle expressed in scene coordinates."""

    left: float
    top: float
    right: float
    bottom: float

    @classmethod
    def from_points(cls, x1: float, y1: float, x2: float, y2: float) -> "ViewportRect":
        return cls(min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))

    @property
    def width(self) -> float:
        return self.right - self.left

    @property
    def height(self) -> float:
        return self.bottom - self.top

    @property
    def area(self) -> float:
        return self.width * self.height

    def is_usable(self, min_size: float = 8.0) -> bool:
        """Reject click-sized drags and invalid rectangles without changing view."""
        if min_size < 0:
            raise ValueError("min_size cannot be negative")
        return self.width >= min_size and self.height >= min_size

    def clamped(self, bounds: "ViewportRect") -> "ViewportRect":
        """Return the intersection with bounds; empty intersections have zero area."""
        left = max(self.left, bounds.left)
        top = max(self.top, bounds.top)
        right = max(left, min(self.right, bounds.right))
        bottom = max(top, min(self.bottom, bounds.bottom))
        return ViewportRect(left, top, right, bottom)
