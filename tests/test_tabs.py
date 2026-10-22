import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from domeprint.geometry import TabSpec, Vec2, build_tab, signed_area, tab_end_angle

from .conftest import line_distance

DEG = math.pi / 180


def approx_vec(p, x, y, tol=1e-12):
    assert p.x == pytest.approx(x, abs=tol) and p.y == pytest.approx(y, abs=tol)


# ---------------------------------------------------------------- TabSpec
@pytest.mark.parametrize("width", [-1, float("nan"), float("inf")])
def test_tabspec_rejects_bad_width(width):
    with pytest.raises(ValueError):
        TabSpec(width)


@pytest.mark.parametrize("angle", [0, -5, 90.0001, float("nan")])
def test_tabspec_rejects_bad_angle(angle):
    with pytest.raises(ValueError):
        TabSpec(5, max_end_angle_deg=angle)


@pytest.mark.parametrize("width", [2.2e-311, 1e-9, 0.0009])
def test_tabspec_rejects_microscopic_width(width):
    """Found by the packing property test: a denormal width built tab points on
    top of the fold line, which the validator rightly rejected deep inside."""
    with pytest.raises(ValueError, match="at least"):
        TabSpec(width)


def test_smallest_allowed_tab_builds_valid_pieces():
    from domeprint.geometry import Triangle, build_piece

    for sides in [(0.5, 0.5, 0.5), (50, 40, 30), (2000, 1500, 1200)]:
        build_piece(Triangle(*sides), TabSpec(0.001))  # validates internally


def test_tabspec_zero_width_disables():
    assert not TabSpec(0).enabled
    assert TabSpec(0.1).enabled


def test_tab_end_angle_clamps_to_bisector():
    spec = TabSpec(5, max_end_angle_deg=45)
    assert tab_end_angle(60 * DEG, spec) == pytest.approx(30 * DEG)
    assert tab_end_angle(120 * DEG, spec) == pytest.approx(45 * DEG)
    unclamped = TabSpec(5, max_end_angle_deg=45, clamp_to_bisector=False)
    assert tab_end_angle(60 * DEG, unclamped) == pytest.approx(45 * DEG)


# ---------------------------------------------------------------- build_tab
def test_trapezoid_45_degrees_exact():
    tab = build_tab(Vec2(0, 0), Vec2(100, 0), 45 * DEG, 45 * DEG, 5)
    assert not tab.truncated
    approx_vec(tab.outer[0], 5, -5)
    approx_vec(tab.outer[1], 95, -5)
    assert tab.height == 5
    assert tab.top_length == pytest.approx(90)
    assert tab.area == pytest.approx(5 * (100 + 90) / 2)


def test_trapezoid_asymmetric_angles():
    tab = build_tab(Vec2(0, 0), Vec2(100, 0), 30 * DEG, 60 * DEG, 5)
    approx_vec(tab.outer[0], 5 / math.tan(30 * DEG), -5)
    approx_vec(tab.outer[1], 100 - 5 / math.tan(60 * DEG), -5)


def test_truncated_to_triangle():
    tab = build_tab(Vec2(0, 0), Vec2(8, 0), 45 * DEG, 45 * DEG, 5)
    assert tab.truncated
    approx_vec(tab.outer[0], 4, -4)
    assert tab.height == pytest.approx(4)
    assert tab.requested_width == 5
    assert tab.top_length == 0
    assert tab.area == pytest.approx(16)


def test_exact_limit_becomes_single_apex():
    tab = build_tab(Vec2(0, 0), Vec2(10, 0), 45 * DEG, 45 * DEG, 5)
    assert tab.truncated
    approx_vec(tab.outer[0], 5, -5)
    assert tab.height == pytest.approx(5)


def test_right_angle_ends_give_rectangle():
    tab = build_tab(Vec2(0, 0), Vec2(10, 0), 90 * DEG, 90 * DEG, 3)
    approx_vec(tab.outer[0], 0, -3)
    approx_vec(tab.outer[1], 10, -3)


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(width=0),
        dict(width=-1),
        dict(width=float("inf")),
        dict(start_angle=0),
        dict(end_angle=91 * DEG),
    ],
)
def test_build_tab_rejects_bad_arguments(kwargs):
    args = dict(start=Vec2(0, 0), end=Vec2(10, 0), start_angle=DEG * 45, end_angle=DEG * 45, width=1)
    args.update(kwargs)
    with pytest.raises(ValueError):
        build_tab(**args)


def test_build_tab_rejects_zero_length_edge():
    with pytest.raises(ValueError):
        build_tab(Vec2(1, 1), Vec2(1, 1), DEG * 45, DEG * 45, 1)


edge_points = st.builds(Vec2, st.floats(-500, 500), st.floats(-500, 500))
angles = st.floats(1.0, 90.0).map(math.radians)


@given(edge_points, edge_points, angles, angles, st.floats(0.1, 30))
def test_tab_geometry_properties(p, q, a_s, a_e, w):
    if (q - p).length() < 1.0:
        return
    tab = build_tab(p, q, a_s, a_e, w)
    u = (q - p).normalized()

    # Outer points lie on the outward (right) side at exactly `height`.
    for o in tab.outer:
        assert math.isclose(-line_distance(o, p, q), tab.height, rel_tol=1e-9, abs_tol=1e-9)
    assert tab.height <= w * (1 + 1e-12)
    if not tab.truncated:
        assert tab.height == w

    # Slanted ends make the requested angle with the fold line.
    first, last = tab.outer[0], tab.outer[-1]
    v1, v2 = first - p, last - q
    ang_s = math.atan2(abs(u.cross(v1)), u.dot(v1))
    ang_e = math.atan2(abs(u.cross(v2)), (-u).dot(v2))
    assert math.isclose(ang_s, a_s, abs_tol=1e-9)
    assert math.isclose(ang_e, a_e, abs_tol=1e-9)

    # Shape is a CCW polygon whose shoelace area matches the closed-form area.
    poly = tab.polygon
    assert signed_area(poly) > 0
    assert math.isclose(signed_area(poly), tab.area, rel_tol=1e-9, abs_tol=1e-9)
