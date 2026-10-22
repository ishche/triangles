from __future__ import annotations

import math

from hypothesis import assume, settings
from hypothesis import strategies as st

from domeprint.geometry import InvalidTriangleError, Triangle, Vec2

settings.register_profile("default", max_examples=300, deadline=None)
settings.load_profile("default")


@st.composite
def triangles(draw, min_side: float = 0.5, max_side: float = 2000.0) -> Triangle:
    """Random valid triangles, from slivers to equilateral, over a wide size range."""
    x = draw(st.floats(min_side, max_side))
    y = draw(st.floats(min_side, max_side))
    t = draw(st.floats(0.02, 0.98))
    lo, hi = abs(x - y), x + y
    z = lo + t * (hi - lo)
    assume(z >= min_side)
    try:
        return Triangle(x, y, z)
    except InvalidTriangleError:
        assume(False)
        raise


def line_distance(p: Vec2, a: Vec2, b: Vec2) -> float:
    """Signed distance from p to the line a->b (positive on the left)."""
    d = b - a
    return d.cross(p - a) / d.length()


def reflect(p: Vec2, a: Vec2, b: Vec2) -> Vec2:
    d = (b - a).normalized()
    v = p - a
    proj = a + d * v.dot(d)
    return proj * 2 - p


def point_in_convex_ccw(p: Vec2, poly, eps: float) -> bool:
    n = len(poly)
    return all(line_distance(p, poly[i], poly[(i + 1) % n]) >= -eps for i in range(n))


def convex_overlap_depth(p1, p2) -> float:
    """Separating-axis test. Returns the minimum overlap along all edge normals.

    <= 0 (or tiny) means the convex polygons are disjoint or only touch.
    """
    best = math.inf
    for poly in (p1, p2):
        n = len(poly)
        for i in range(n):
            e = poly[(i + 1) % n] - poly[i]
            if e.length() == 0:
                continue
            axis = e.perp_left().normalized()
            a = [axis.dot(p) for p in p1]
            b = [axis.dot(p) for p in p2]
            overlap = min(max(a), max(b)) - max(min(a), min(b))
            best = min(best, overlap)
    return best
