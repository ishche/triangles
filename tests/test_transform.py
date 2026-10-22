import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from domeprint.geometry import Transform2D, Vec2

finite = st.floats(-1e3, 1e3)
angle = st.floats(-math.tau, math.tau)
points = st.builds(Vec2, finite, finite)
transforms = st.builds(Transform2D, angle, points)


def close(p, q, tol=1e-7):
    return math.isclose(p.x, q.x, abs_tol=tol) and math.isclose(p.y, q.y, abs_tol=tol)


def test_rotation_quarter_turn():
    p = Transform2D.rotation(math.pi / 2).apply(Vec2(1, 0))
    assert p.x == pytest.approx(0, abs=1e-15) and p.y == pytest.approx(1)


def test_translation():
    assert Transform2D.translation(3, -2).apply(Vec2(1, 1)) == Vec2(4, -1)


@given(transforms, transforms, points)
def test_then_composes_in_order(t1, t2, p):
    assert close(t1.then(t2).apply(p), t2.apply(t1.apply(p)))


@given(transforms, points)
def test_inverse(t, p):
    assert close(t.inverse().apply(t.apply(p)), p)
