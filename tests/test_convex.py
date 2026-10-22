"""Convex-polygon primitives used by the packer: hull, Minkowski sum, sections,
offset (padding) and distance."""

import math

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from domeprint.geometry import Vec2, signed_area
from domeprint.geometry.convex import (
    convex_distance,
    convex_hull,
    minkowski_sum,
    negate,
    offset_convex,
    support,
    translate,
    x_section,
    y_section,
)
from domeprint.geometry.polygon import convex_overlap_depth, is_convex_ccw, point_in_convex_polygon


def V(*xy):
    return [Vec2(float(x), float(y)) for x, y in xy]


SQ = V((0, 0), (1, 0), (1, 1), (0, 1))
TRI = V((0, 0), (4, 0), (2, 2))

coords = st.floats(-100, 100)
point_lists = st.lists(st.builds(Vec2, coords, coords), min_size=3, max_size=12)


@st.composite
def convex_polys(draw):
    pts = draw(point_lists)
    try:
        hull = convex_hull(pts)
    except ValueError:
        assume(False)
        raise
    assume(signed_area(hull) > 1.0)
    return hull


def same_set(a, b, tol=1e-9):
    return len(a) == len(b) and all(any((p - q).length() <= tol for q in b) for p in a)


# ======================================================== hull
def test_hull_drops_interior_duplicate_and_collinear_points():
    pts = SQ + V((0.5, 0.5), (0.5, 0), (1, 0.5), (0, 0))
    h = convex_hull(pts)
    assert same_set(h, SQ)
    assert signed_area(h) == 1.0


def test_hull_is_ccw_and_starts_at_lowest_leftmost():
    h = convex_hull(list(reversed(SQ)))
    assert h[0] == Vec2(0, 0)
    assert signed_area(h) > 0


def test_hull_of_collinear_points_raises():
    with pytest.raises(ValueError):
        convex_hull(V((0, 0), (1, 1), (2, 2)))


@given(point_lists)
def test_hull_contains_all_points(pts):
    try:
        h = convex_hull(pts)
    except ValueError:
        return
    assert is_convex_ccw(h)
    assert all(p in pts for p in h)
    for p in pts:
        assert point_in_convex_polygon(p, h, eps=1e-7)


# ======================================================== negate / translate / support
def test_negate_is_point_reflection_and_ccw():
    n = negate(SQ)
    assert same_set(n, V((0, 0), (-1, 0), (-1, -1), (0, -1)))
    assert signed_area(n) > 0


def test_translate():
    assert translate(SQ, Vec2(2, 3))[2] == Vec2(3, 4)


def test_support():
    assert support(TRI, Vec2(0, 1)) == 2
    assert support(TRI, Vec2(-1, 0)) == 0


# ======================================================== Minkowski sum
def test_minkowski_of_squares():
    big = V((0, 0), (2, 0), (2, 2), (0, 2))
    assert same_set(minkowski_sum(SQ, big), V((0, 0), (3, 0), (3, 3), (0, 3)))


def test_triangle_difference_body_is_hexagon_with_six_times_area():
    t = V((0, 0), (4, 0), (1, 3))
    m = minkowski_sum(t, negate(t))
    assert len(m) == 6
    assert signed_area(m) == pytest.approx(6 * signed_area(t))


@given(convex_polys(), convex_polys())
def test_minkowski_sum_properties(p, q):
    m = minkowski_sum(p, q)
    assert is_convex_ccw(m, eps=1e-7)
    for a in p:
        for b in q:
            assert point_in_convex_polygon(a + b, m, eps=1e-7)
    for v in m:
        assert any((v - (a + b)).length() <= 1e-9 for a in p for b in q)
    # support functions add: h_{P+Q}(u) = h_P(u) + h_Q(u)
    for k in range(8):
        u = Vec2(math.cos(k), math.sin(k))
        assert support(m, u) == pytest.approx(support(p, u) + support(q, u), abs=1e-7)


# ======================================================== sections
def test_x_section_square():
    assert x_section(SQ, 0.5) == (0, 1)
    assert x_section(SQ, 0) is None  # touching the bottom edge is not overlap
    assert x_section(SQ, 1) is None
    assert x_section(SQ, 2) is None


def test_x_section_triangle():
    assert x_section(TRI, 1) == pytest.approx((1, 3))


def test_y_section_triangle():
    assert y_section(TRI, 1) == pytest.approx((0, 1))
    assert y_section(TRI, 2) == pytest.approx((0, 2))
    assert y_section(TRI, 0) is None
    assert y_section(TRI, 4) is None


@given(convex_polys(), st.floats(0.05, 0.95))
def test_section_endpoints_on_boundary(p, f):
    ys = [v.y for v in p]
    y = min(ys) + f * (max(ys) - min(ys))
    lo, hi = x_section(p, y)
    assert lo <= hi
    for x in (lo, hi):
        assert point_in_convex_polygon(Vec2(x, y), p, eps=1e-7)
        assert not point_in_convex_polygon(Vec2(x + (1e-4 if x == hi else -1e-4), y), p, eps=0)


# ======================================================== offset (padding)
def test_offset_zero_is_identity():
    assert offset_convex(SQ, 0) == tuple(SQ)


def test_offset_square_mitres():
    assert same_set(offset_convex(SQ, 1), V((-1, -1), (2, -1), (2, 2), (-1, 2)))


def test_offset_sharp_corner_is_bevelled():
    sliver = V((0, 0), (10, 0), (0, 1))  # ~5.7 deg corner at (10, 0)
    off = offset_convex(sliver, 1)
    assert len(off) > 3
    # A plain mitre would reach ~10 mm past the tip; the bevel keeps it within 2d.
    assert max(convex_distance([v], sliver) for v in off) <= 2 + 1e-9
    assert max(v.x for v in off) < 12


def test_offset_negative_raises():
    with pytest.raises(ValueError):
        offset_convex(SQ, -1)


@given(convex_polys(), st.floats(0.01, 5))
def test_offset_properties(p, d):
    off = offset_convex(p, d)
    assert is_convex_ccw(off, eps=1e-7)
    # Contains every point within distance d of the polygon (the round offset).
    for v in p:
        for k in range(16):
            a = k * math.tau / 16
            assert point_in_convex_polygon(v + Vec2(math.cos(a), math.sin(a)) * d, off, eps=1e-7)
    # Each edge moves out by exactly d.
    n = len(p)
    for i in range(n):
        normal = (p[(i + 1) % n] - p[i]).perp_right().normalized()
        assert support(off, normal) == pytest.approx(support(p, normal) + d, abs=1e-7)
    # Bevelled corners never stick out more than 2d.
    assert max(convex_distance([v], p) for v in off) <= 2 * d + 1e-7


# ======================================================== distance
def test_distance_cases():
    assert convex_distance(SQ, translate(SQ, Vec2(3, 0))) == pytest.approx(2)
    assert convex_distance(SQ, translate(SQ, Vec2(2, 2))) == pytest.approx(math.sqrt(2))
    assert convex_distance(SQ, translate(SQ, Vec2(1, 0))) == 0
    assert convex_distance(SQ, translate(SQ, Vec2(0.5, 0.2))) == 0


@given(convex_polys(), st.floats(0, 2 * math.pi), st.floats(0.01, 50))
def test_distance_after_separating_by_gap(p, angle, gap):
    u = Vec2(math.cos(angle), math.sin(angle))
    width = support(p, u) + support(p, -u)
    q = translate(p, u * (width + gap))
    d = convex_distance(p, q)
    assert d >= gap - 1e-7
    assert convex_overlap_depth(p, q) <= 1e-9
