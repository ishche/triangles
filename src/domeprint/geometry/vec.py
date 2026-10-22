"""Minimal immutable 2D vector. All coordinates are millimetres in a y-up frame."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Vec2:
    x: float
    y: float

    def __add__(self, other: Vec2) -> Vec2:
        return Vec2(self.x + other.x, self.y + other.y)

    def __sub__(self, other: Vec2) -> Vec2:
        return Vec2(self.x - other.x, self.y - other.y)

    def __mul__(self, k: float) -> Vec2:
        return Vec2(self.x * k, self.y * k)

    __rmul__ = __mul__

    def __truediv__(self, k: float) -> Vec2:
        return Vec2(self.x / k, self.y / k)

    def __neg__(self) -> Vec2:
        return Vec2(-self.x, -self.y)

    def dot(self, other: Vec2) -> float:
        return self.x * other.x + self.y * other.y

    def cross(self, other: Vec2) -> float:
        """z-component of the 3D cross product (positive if `other` is counter-clockwise)."""
        return self.x * other.y - self.y * other.x

    def length(self) -> float:
        return math.hypot(self.x, self.y)

    def normalized(self) -> Vec2:
        n = self.length()
        if n == 0.0:
            raise ValueError("cannot normalize a zero-length vector")
        return Vec2(self.x / n, self.y / n)

    def perp_left(self) -> Vec2:
        """Rotate +90 degrees (counter-clockwise)."""
        return Vec2(-self.y, self.x)

    def perp_right(self) -> Vec2:
        """Rotate -90 degrees (clockwise)."""
        return Vec2(self.y, -self.x)

    def rotated(self, angle: float) -> Vec2:
        c, s = math.cos(angle), math.sin(angle)
        return Vec2(c * self.x - s * self.y, s * self.x + c * self.y)

    def angle(self) -> float:
        """Direction angle in radians, in (-pi, pi]."""
        return math.atan2(self.y, self.x)


def distance(p: Vec2, q: Vec2) -> float:
    return math.hypot(q.x - p.x, q.y - p.y)
