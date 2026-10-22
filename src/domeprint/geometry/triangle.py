"""A triangle defined by its three side lengths (mm), placed in a canonical position.

Naming convention (avoids the usual "side a is opposite vertex A" ambiguity):

    ab = |AB|, bc = |BC|, ca = |CA|

Canonical placement: A = (0, 0), B = (ab, 0), C above the x-axis.
The vertex order A -> B -> C is therefore counter-clockwise, so the outward
normal of every directed edge (A->B, B->C, C->A) is its right-hand perpendicular.

Numerically stable formulas are used throughout (Kahan's Heron formula for the
area, atan2-based angles), so near-degenerate slivers stay accurate.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .vec import Vec2

#: Relative tolerance for rejecting (near-)degenerate triangles.
DEGENERACY_REL_TOL = 1e-9


class InvalidTriangleError(ValueError):
    """Raised when three lengths cannot form a non-degenerate triangle."""


@dataclass(frozen=True, slots=True)
class Edge:
    """A directed edge of the counter-clockwise triangle."""

    name: str  # "AB", "BC" or "CA"
    start: Vec2
    end: Vec2
    length: float
    start_angle: float  # interior angle of the triangle at `start`, radians
    end_angle: float  # interior angle of the triangle at `end`, radians

    @property
    def direction(self) -> Vec2:
        return (self.end - self.start) / self.length

    @property
    def outward_normal(self) -> Vec2:
        return self.direction.perp_right()

    @property
    def midpoint(self) -> Vec2:
        return (self.start + self.end) * 0.5


def _validate_length(name: str, value: float) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError) as exc:
        raise InvalidTriangleError(f"side {name} must be a number, got {value!r}") from exc
    if not math.isfinite(v):
        raise InvalidTriangleError(f"side {name} must be finite, got {v}")
    if v <= 0.0:
        raise InvalidTriangleError(f"side {name} must be positive, got {v}")
    return v


def _kahan_area(x: float, y: float, z: float) -> float:
    """Heron's formula in Kahan's stable form. Arguments in any order."""
    a, b, c = sorted((x, y, z), reverse=True)
    prod = (a + (b + c)) * (c - (a - b)) * (c + (a - b)) * (a + (b - c))
    return 0.25 * math.sqrt(max(prod, 0.0))


@dataclass(frozen=True, slots=True)
class Triangle:
    ab: float
    bc: float
    ca: float

    def __post_init__(self) -> None:
        ab = _validate_length("AB", self.ab)
        bc = _validate_length("BC", self.bc)
        ca = _validate_length("CA", self.ca)
        longest, mid, short = sorted((ab, bc, ca), reverse=True)
        # Strict triangle inequality with a relative tolerance.
        if (mid + short) - longest <= DEGENERACY_REL_TOL * longest:
            raise InvalidTriangleError(
                f"sides AB={ab}, BC={bc}, CA={ca} violate the triangle inequality "
                f"(longest side must be strictly shorter than the sum of the other two)"
            )
        object.__setattr__(self, "ab", ab)
        object.__setattr__(self, "bc", bc)
        object.__setattr__(self, "ca", ca)

    # ---- constructors -------------------------------------------------
    @classmethod
    def isosceles(cls, base: float, leg: float) -> Triangle:
        """Base AB, legs BC = CA."""
        return cls(ab=base, bc=leg, ca=leg)

    @classmethod
    def equilateral(cls, side: float) -> Triangle:
        return cls(side, side, side)

    # ---- scalar properties --------------------------------------------
    @property
    def sides(self) -> tuple[float, float, float]:
        return (self.ab, self.bc, self.ca)

    @property
    def perimeter(self) -> float:
        return self.ab + self.bc + self.ca

    @property
    def semiperimeter(self) -> float:
        return self.perimeter / 2.0

    @property
    def area(self) -> float:
        return _kahan_area(self.ab, self.bc, self.ca)

    @property
    def inradius(self) -> float:
        return self.area / self.semiperimeter

    @property
    def circumradius(self) -> float:
        return self.ab * self.bc * self.ca / (4.0 * self.area)

    @property
    def angles(self) -> tuple[float, float, float]:
        """Interior angles (radians) at A, B, C.

        Uses tan(angle) = 4K / (adjacent1^2 + adjacent2^2 - opposite^2), which is
        well-conditioned for all angles, unlike acos of the law of cosines.
        """
        k4 = 4.0 * self.area
        ab2, bc2, ca2 = self.ab**2, self.bc**2, self.ca**2
        angle_a = math.atan2(k4, ab2 + ca2 - bc2)
        angle_b = math.atan2(k4, ab2 + bc2 - ca2)
        angle_c = math.atan2(k4, bc2 + ca2 - ab2)
        return (angle_a, angle_b, angle_c)

    @property
    def angles_deg(self) -> tuple[float, float, float]:
        return tuple(math.degrees(a) for a in self.angles)  # type: ignore[return-value]

    # ---- canonical coordinates ----------------------------------------
    @property
    def vertices(self) -> tuple[Vec2, Vec2, Vec2]:
        a = Vec2(0.0, 0.0)
        b = Vec2(self.ab, 0.0)
        # Foot of C onto AB, and height from area (more stable than sqrt(ca^2 - x^2)).
        cx = (self.ca**2 + self.ab**2 - self.bc**2) / (2.0 * self.ab)
        cy = 2.0 * self.area / self.ab
        return (a, b, Vec2(cx, cy))

    @property
    def incenter(self) -> Vec2:
        a, b, c = self.vertices
        # Weights are the lengths of the opposite sides.
        w_a, w_b, w_c = self.bc, self.ca, self.ab
        return (a * w_a + b * w_b + c * w_c) / self.perimeter

    @property
    def edges(self) -> tuple[Edge, Edge, Edge]:
        a, b, c = self.vertices
        ang_a, ang_b, ang_c = self.angles
        return (
            Edge("AB", a, b, self.ab, ang_a, ang_b),
            Edge("BC", b, c, self.bc, ang_b, ang_c),
            Edge("CA", c, a, self.ca, ang_c, ang_a),
        )
