"""Convex polygon toolkit for packing.

All polygons are sequences of Vec2 in counter-clockwise order. Every function
here is exact up to floating point; none of them approximates curves.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from .polygon import convex_overlap_depth, point_in_convex_polygon, signed_area
from .vec import Vec2

Poly = Sequence[Vec2]


def convex_hull(points: Poly) -> tuple[Vec2, ...]:
    """Andrew's monotone chain. CCW, no collinear points, starting at the lowest
    (then leftmost) vertex. Raises ValueError if the points span no area."""
    pts = sorted(set(points), key=lambda p: (p.x, p.y))
    if len(pts) < 3:
        raise ValueError("convex hull needs at least 3 distinct points")

    def half(seq):
        chain: list[Vec2] = []
        for p in seq:
            while len(chain) >= 2 and (chain[-1] - chain[-2]).cross(p - chain[-2]) <= 0:
                chain.pop()
            chain.append(p)
        return chain

    lower, upper = half(pts), half(reversed(pts))
    hull = lower[:-1] + upper[:-1]
    if len(hull) < 3 or signed_area(hull) <= 0:
        raise ValueError("points are collinear")
    start = min(range(len(hull)), key=lambda i: (hull[i].y, hull[i].x))
    return tuple(hull[start:] + hull[:start])


def translate(poly: Poly, v: Vec2) -> tuple[Vec2, ...]:
    return tuple(p + v for p in poly)


def negate(poly: Poly) -> tuple[Vec2, ...]:
    """Point reflection through the origin (a 180 degree rotation: stays CCW)."""
    return tuple(-p for p in poly)


def support(poly: Poly, u: Vec2) -> float:
    """Support function h(u) = max over the polygon of <p, u>."""
    return max(p.dot(u) for p in poly)


def minkowski_sum(p: Poly, q: Poly) -> tuple[Vec2, ...]:
    """P + Q = {a + b}. For convex polygons it is the hull of the vertex sums."""
    return convex_hull([a + b for a in p for b in q])


def _section(poly: Poly, c: float, axis: int) -> tuple[float, float] | None:
    """Open cross-section of a convex polygon with the line {coord[axis] = c}.

    Returns (lo, hi) along the other axis, or None when the line misses the
    interior (including when it only touches a vertex or an edge).
    """
    along = [(p.y, p.x) if axis == 1 else (p.x, p.y) for p in poly]  # (line coord, other coord)
    cs = [a for a, _ in along]
    if not (min(cs) < c < max(cs)):
        return None
    hits: list[float] = []
    n = len(along)
    for i in range(n):
        (a1, o1), (a2, o2) = along[i], along[(i + 1) % n]
        if (a1 - c) * (a2 - c) <= 0 and a1 != a2:
            hits.append(o1 + (c - a1) * (o2 - o1) / (a2 - a1))
    return (min(hits), max(hits))


def x_section(poly: Poly, y: float) -> tuple[float, float] | None:
    """Interior x-interval of the polygon on the horizontal line at height y."""
    return _section(poly, y, axis=1)


def y_section(poly: Poly, x: float) -> tuple[float, float] | None:
    """Interior y-interval of the polygon on the vertical line at x."""
    return _section(poly, x, axis=0)


def offset_convex(poly: Poly, d: float, miter_limit: float = 2.0) -> tuple[Vec2, ...]:
    """Grow a convex CCW polygon outward by distance d.

    Every edge moves out by exactly d. Corners are mitred; if a mitre would
    reach more than miter_limit * d from the corner, it is bevelled by the
    line tangent to the radius-d circle around the corner. Either way the
    result contains every point within distance d of the polygon.
    """
    if not (d >= 0 and math.isfinite(d)):
        raise ValueError(f"offset distance must be >= 0, got {d!r}")
    if d == 0:
        return tuple(poly)
    n = len(poly)
    out: list[Vec2] = []
    for i in range(n):
        prev, v, nxt = poly[i - 1], poly[i], poly[(i + 1) % n]
        u1 = (v - prev).normalized()  # arriving direction
        u2 = (nxt - v).normalized()  # leaving direction
        n1, n2 = u1.perp_right(), u2.perp_right()  # outward normals
        cos_turn = n1.dot(n2)
        miter_len = d * math.sqrt(2.0 / (1.0 + cos_turn)) if cos_turn > -1 else math.inf
        if miter_len <= miter_limit * d:
            out.append(v + (n1 + n2) * (d / (1.0 + cos_turn)))
            continue
        b = (n1 + n2).normalized()  # outward bisector
        s1 = d * (1.0 - n1.dot(b)) / u1.dot(b)
        s2 = d * (1.0 - n2.dot(b)) / (-u2).dot(b)
        out.append(v + n1 * d + u1 * s1)
        out.append(v + n2 * d - u2 * s2)
    return tuple(out)


def _point_segment_distance(p: Vec2, a: Vec2, b: Vec2) -> float:
    ab = b - a
    denom = ab.dot(ab)
    t = 0.0 if denom == 0 else max(0.0, min(1.0, (p - a).dot(ab) / denom))
    return (p - (a + ab * t)).length()


def _edges(poly: Poly):
    n = len(poly)
    if n == 1:
        return [(poly[0], poly[0])]
    return [(poly[i], poly[(i + 1) % n]) for i in range(n)]


def convex_distance(p: Poly, q: Poly) -> float:
    """Euclidean distance between two convex polygons (0 if they touch or overlap).

    Either argument may also be a single point or a segment.
    """
    if len(p) >= 3 and len(q) >= 3 and convex_overlap_depth(p, q) > 0:
        return 0.0
    if len(p) >= 3 and any(point_in_convex_polygon(v, p, eps=0.0) for v in q):
        return 0.0
    if len(q) >= 3 and any(point_in_convex_polygon(v, q, eps=0.0) for v in p):
        return 0.0
    best = math.inf
    for a in p:
        for s, e in _edges(q):
            best = min(best, _point_segment_distance(a, s, e))
    for b in q:
        for s, e in _edges(p):
            best = min(best, _point_segment_distance(b, s, e))
    return best
