"""Polygon helpers used for validation and layout (bounding boxes, area, simplicity)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .vec import Vec2


@dataclass(frozen=True, slots=True)
class BBox:
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    @property
    def width(self) -> float:
        return self.max_x - self.min_x

    @property
    def height(self) -> float:
        return self.max_y - self.min_y

    @property
    def min(self) -> Vec2:
        return Vec2(self.min_x, self.min_y)

    @property
    def center(self) -> Vec2:
        return Vec2((self.min_x + self.max_x) / 2, (self.min_y + self.max_y) / 2)


def bounding_box(points: Sequence[Vec2]) -> BBox:
    if not points:
        raise ValueError("bounding box of an empty point set")
    xs = [p.x for p in points]
    ys = [p.y for p in points]
    return BBox(min(xs), min(ys), max(xs), max(ys))


def signed_area(polygon: Sequence[Vec2]) -> float:
    """Shoelace formula. Positive for counter-clockwise polygons."""
    n = len(polygon)
    total = 0.0
    for i in range(n):
        total += polygon[i].cross(polygon[(i + 1) % n])
    return total / 2.0


def _orient(a: Vec2, b: Vec2, c: Vec2) -> float:
    """Signed distance (length units) of c from the line through a->b."""
    d = b - a
    n = d.length()
    return d.cross(c - a) / n if n else 0.0


def _on_segment(p: Vec2, a: Vec2, b: Vec2, eps: float) -> bool:
    return min(a.x, b.x) - eps <= p.x <= max(a.x, b.x) + eps and min(a.y, b.y) - eps <= p.y <= max(a.y, b.y) + eps


def segments_intersect(p1: Vec2, p2: Vec2, q1: Vec2, q2: Vec2, eps: float = 1e-9) -> bool:
    """True if closed segments p1p2 and q1q2 share at least one point (eps is a distance)."""
    d1 = _orient(q1, q2, p1)
    d2 = _orient(q1, q2, p2)
    d3 = _orient(p1, p2, q1)
    d4 = _orient(p1, p2, q2)
    if ((d1 > eps and d2 < -eps) or (d1 < -eps and d2 > eps)) and (
        (d3 > eps and d4 < -eps) or (d3 < -eps and d4 > eps)
    ):
        return True
    if abs(d1) <= eps and _on_segment(p1, q1, q2, eps):
        return True
    if abs(d2) <= eps and _on_segment(p2, q1, q2, eps):
        return True
    if abs(d3) <= eps and _on_segment(q1, p1, p2, eps):
        return True
    return abs(d4) <= eps and _on_segment(q2, p1, p2, eps)


def is_simple_polygon(polygon: Sequence[Vec2], eps: float = 1e-9, angle_eps: float = 1e-12) -> bool:
    """True if the closed polygon has no self-intersections and no repeated/backtracking edges.

    eps is a distance tolerance; angle_eps is the sine below which two adjacent
    edges pointing the same way from their shared vertex count as overlapping.
    """
    n = len(polygon)
    if n < 3:
        return False
    edges = [(polygon[i], polygon[(i + 1) % n]) for i in range(n)]
    for a, b in edges:
        if (b - a).length() <= eps:
            return False
    for i in range(n):
        a1, a2 = edges[i]
        for j in range(i + 1, n):
            b1, b2 = edges[j]
            adjacent = j == i + 1 or (i == 0 and j == n - 1)
            if adjacent:
                # Adjacent edges share one vertex; they must not fold back over each other.
                shared = a2 if j == i + 1 else a1
                other_a = a1 if j == i + 1 else a2
                other_b = b2 if j == i + 1 else b1
                da, db = other_a - shared, other_b - shared
                if abs(da.cross(db)) <= angle_eps * da.length() * db.length() and da.dot(db) > 0:
                    return False
                continue
            if segments_intersect(a1, a2, b1, b2, eps):
                return False
    return True


def point_in_convex_polygon(p: Vec2, polygon: Sequence[Vec2], eps: float = 1e-9) -> bool:
    """True if p is inside or within eps (a distance) of a convex CCW polygon."""
    n = len(polygon)
    return all(_orient(polygon[i], polygon[(i + 1) % n], p) >= -eps for i in range(n))


def convex_overlap_depth(p: Sequence[Vec2], q: Sequence[Vec2]) -> float:
    """Separating-axis test for two convex polygons.

    Returns the smallest overlap of their projections over all edge normals:
    a value <= 0 means they are disjoint or only touch along a boundary.
    """
    best = float("inf")
    for poly in (p, q):
        n = len(poly)
        for i in range(n):
            e = poly[(i + 1) % n] - poly[i]
            if e.length() == 0.0:
                continue
            axis = e.perp_left().normalized()
            a = [axis.dot(v) for v in p]
            b = [axis.dot(v) for v in q]
            best = min(best, min(max(a), max(b)) - max(min(a), min(b)))
    return best


def is_convex_ccw(polygon: Sequence[Vec2], eps: float = 1e-9) -> bool:
    """True if every turn of the polygon is a left turn (collinear within eps allowed)."""
    n = len(polygon)
    return n >= 3 and all(_orient(polygon[i], polygon[(i + 1) % n], polygon[(i + 2) % n]) >= -eps for i in range(n))
