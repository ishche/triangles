"""No-fit polygon (NFP) and exact sliding contacts between convex shapes.

Definition: NFP(A, B) = A + (-B). A fixed at the origin and B translated by v
have overlapping interiors exactly when v lies strictly inside NFP(A, B).
"""

import math

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from domeprint.geometry import Vec2, signed_area
from domeprint.geometry.convex import convex_hull, translate
from domeprint.geometry.polygon import convex_overlap_depth
from domeprint.layout.nfp import no_fit_polygon, slide_right, slide_up

H = 25 * math.sqrt(3)  # height of an equilateral triangle with side 50
U = [Vec2(0, 0), Vec2(50, 0), Vec2(25, H)]  # apex up
D = [Vec2(25, 0), Vec2(50, H), Vec2(0, H)]  # apex down (U rotated 180 deg)
SQ = [Vec2(0, 0), Vec2(1, 0), Vec2(1, 1), Vec2(0, 1)]

coords = st.floats(-50, 50)


@st.composite
def convex_polys(draw):
    pts = draw(st.lists(st.builds(Vec2, coords, coords), min_size=3, max_size=9))
    try:
        hull = convex_hull(pts)
    except ValueError:
        assume(False)
        raise
    assume(signed_area(hull) > 5.0)
    return hull


def inside_margin(poly, p):
    """Signed distance to the boundary: positive inside, negative outside (convex CCW)."""
    n = len(poly)
    best = math.inf
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        d = b - a
        best = min(best, d.cross(p - a) / d.length())
    return best


@given(convex_polys(), convex_polys(), st.builds(Vec2, st.floats(-150, 150), st.floats(-150, 150)))
def test_nfp_characterises_overlap(a, b, v):
    nfp = no_fit_polygon(a, b)
    m = inside_margin(nfp, v)
    depth = convex_overlap_depth(a, translate(b, v))
    if m > 1e-6:
        assert depth > 0
    elif m < -1e-6:
        assert depth <= 1e-9


def test_slide_right_squares():
    assert slide_right(SQ, SQ, 0) == pytest.approx(1)
    assert slide_right(SQ, SQ, 0.5) == pytest.approx(1)
    assert slide_right(SQ, SQ, -0.99) == pytest.approx(1)
    assert slide_right(SQ, SQ, 1) is None  # only touching: no constraint
    assert slide_right(SQ, SQ, 5) is None


def test_slide_right_alternating_triangles_interlock():
    assert slide_right(U, D, 0) == pytest.approx(25)
    assert slide_right(D, U, 0) == pytest.approx(25)
    assert slide_right(U, U, 0) == pytest.approx(50)


def test_slide_up():
    assert slide_up(SQ, SQ, 0) == pytest.approx(1)
    assert slide_up(U, U, 0) == pytest.approx(H)
    assert slide_up(D, U, -25) == pytest.approx(H)
    assert slide_up(SQ, SQ, 1) is None


@given(convex_polys(), convex_polys(), st.floats(-0.9, 0.9))
def test_slide_right_is_tight(a, b, f):
    # Pick dy where the shapes overlap vertically.
    ya = [p.y for p in a]
    yb = [p.y for p in b]
    lo = min(ya) - max(yb)
    hi = max(ya) - min(yb)
    dy = (lo + hi) / 2 + f * (hi - lo) / 2
    dx = slide_right(a, b, dy)
    assume(dx is not None)
    assert convex_overlap_depth(a, translate(b, Vec2(dx, dy))) <= 1e-7  # touching
    assert convex_overlap_depth(a, translate(b, Vec2(dx - 1e-3, dy))) > 0  # any closer overlaps


@given(convex_polys(), convex_polys(), st.floats(-0.9, 0.9))
def test_slide_up_is_tight(a, b, f):
    xa = [p.x for p in a]
    xb = [p.x for p in b]
    lo = min(xa) - max(xb)
    hi = max(xa) - min(xb)
    dx = (lo + hi) / 2 + f * (hi - lo) / 2
    dy = slide_up(a, b, dx)
    assume(dy is not None)
    assert convex_overlap_depth(a, translate(b, Vec2(dx, dy))) <= 1e-7
    assert convex_overlap_depth(a, translate(b, Vec2(dx, dy - 1e-3))) > 0
