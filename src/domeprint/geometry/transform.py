"""Rigid 2D transforms (rotation + translation).

Scaling and mirroring are deliberately impossible: layout may move and rotate
pieces but can never change their size or turn a scalene triangle into its
mirror image.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .vec import Vec2


@dataclass(frozen=True, slots=True)
class Transform2D:
    angle: float = 0.0  # radians, counter-clockwise
    offset: Vec2 = Vec2(0.0, 0.0)

    @classmethod
    def identity(cls) -> Transform2D:
        return cls()

    @classmethod
    def rotation(cls, angle: float) -> Transform2D:
        return cls(angle, Vec2(0.0, 0.0))

    @classmethod
    def translation(cls, dx: float, dy: float) -> Transform2D:
        return cls(0.0, Vec2(dx, dy))

    def apply(self, p: Vec2) -> Vec2:
        return p.rotated(self.angle) + self.offset

    def apply_all(self, points) -> tuple[Vec2, ...]:
        return tuple(self.apply(p) for p in points)

    def then(self, other: Transform2D) -> Transform2D:
        """Transform that applies `self` first, then `other`."""
        return Transform2D(
            math.remainder(self.angle + other.angle, math.tau),
            self.offset.rotated(other.angle) + other.offset,
        )

    def inverse(self) -> Transform2D:
        return Transform2D(-self.angle, (-self.offset).rotated(-self.angle))
