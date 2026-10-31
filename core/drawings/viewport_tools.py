"""Geometry helpers for interactive drawing viewport tools."""
from __future__ import annotations

from dataclasses import dataclass
import math


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
        """For display pixels; raw CAD scene units may be millimetres or tiny decimals."""
        if not math.isfinite(min_size) or min_size < 0:
            raise ValueError("min_size must be finite and non-negative")
        return (
            all(math.isfinite(x) for x in (self.left,self.top,self.right,self.bottom))
            and self.width > 0 and self.height > 0
            and self.width >= min_size and self.height >= min_size
        )

    def clamped(self, bounds: "ViewportRect") -> "ViewportRect":
        """Return the intersection with bounds; empty intersections have zero area."""
        left = max(self.left, bounds.left)
        top = max(self.top, bounds.top)
        right = max(left, min(self.right, bounds.right))
        bottom = max(top, min(self.bottom, bounds.bottom))
        return ViewportRect(left, top, right, bottom)


    def contains_rect(self, other: "ViewportRect") -> bool:
        """All of a CAD entity's rendered bounds must be inside the window.

        Touching the edge counts as contained, but a crossing entity must not
        be counted at full length/area when the user selected only a fragment.
        """
        if (not self.is_usable(0) or
            not all(math.isfinite(v) for v in (other.left,other.top,other.right,other.bottom)) or
            other.width < 0 or other.height < 0):
            return False
        return (self.left <= other.left <= other.right <= self.right and
                self.top <= other.top <= other.bottom <= self.bottom)

    def intersects_rect(self, other: "ViewportRect") -> bool:
        # Real CAD LINEs often have zero bbox height (horizontal) or width
        # (vertical). Degenerate *element bounds* are valid intersection
        # operands even though a zero-area *selection window* is not.
        if (not self.is_usable(0) or
            not all(math.isfinite(v) for v in (other.left,other.top,other.right,other.bottom)) or
            other.width < 0 or other.height < 0):
            return False
        return (self.left <= other.right and other.left <= self.right and
                self.top <= other.bottom and other.top <= self.bottom)

    def classify_rect(self, other: "ViewportRect") -> str:
        """Safe scope classification: 'inside', 'crossing', 'outside'.

        Never silently count a partly overlapping CAD entity as fully measured.
        """
        if self.contains_rect(other):
            return "inside"
        if self.intersects_rect(other):
            return "crossing"
        return "outside"
