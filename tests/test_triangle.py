import math

import pytest
from hypothesis import given

from domeprint.geometry import InvalidTriangleError, Triangle, distance, signed_area

from .conftest import line_distance, triangles

REL = 1e-12


def rel_close(a, b, rel=REL, abs_=1e-12):
    return math.isclose(a, b, rel_tol=rel, abs_tol=abs_)


# ---------------------------------------------------------------- known cases
def test_equilateral():
    t = Triangle.equilateral(100)
    a, b, c = t.vertices
    assert a.x == 0 and a.y == 0
    assert b.x == 100 and b.y == 0
    assert c.x == pytest.approx(50, abs=1e-12)
    assert c.y == pytest.approx(50 * math.sqrt(3), abs=1e-12)
    for ang in t.angles_deg:
        assert ang == pytest.approx(60, abs=1e-12)
    assert t.area == pytest.approx(math.sqrt(3) / 4 * 100**2, rel=1e-14)
    assert t.inradius == pytest.approx(100 / (2 * math.sqrt(3)), rel=1e-14)
    assert t.circumradius == pytest.approx(100 / math.sqrt(3), rel=1e-14)


def test_right_triangle_3_4_5():
    t = Triangle(ab=3, bc=4, ca=5)
    ang_a, ang_b, _ang_c = t.angles_deg
    assert ang_b == pytest.approx(90, abs=1e-12)  # between AB and BC
    assert ang_a == pytest.approx(math.degrees(math.atan2(4, 3)), abs=1e-12)
    assert t.area == pytest.approx(6, rel=1e-15)
    assert t.inradius == pytest.approx(1, rel=1e-15)
    assert t.vertices[2].x == pytest.approx(3, abs=1e-12)
    assert t.vertices[2].y == pytest.approx(4, abs=1e-12)


def test_isosceles_is_symmetric():
    t = Triangle.isosceles(base=80, leg=120)
    assert (t.ab, t.bc, t.ca) == (80, 120, 120)
    _a, _b, c = t.vertices
    assert c.x == pytest.approx(40, abs=1e-12)
    assert c.y == pytest.approx(math.sqrt(120**2 - 40**2), rel=1e-14)
    ang_a, ang_b, _ = t.angles
    assert ang_a == pytest.approx(ang_b, abs=1e-14)


def test_geodesic_2v_triangle():
    # 2V icosahedral dome, radius 1000 mm: chord factors A=0.54653, B=0.61803.
    t = Triangle.isosceles(base=546.53, leg=618.03)
    assert sum(t.angles_deg) == pytest.approx(180, abs=1e-12)
    for edge, expected in zip(t.edges, (546.53, 618.03, 618.03)):
        assert distance(edge.start, edge.end) == pytest.approx(expected, abs=1e-9)


@pytest.mark.parametrize("scale", [0.01, 1.0, 1e5])
def test_extreme_scales(scale):
    t = Triangle(3 * scale, 4 * scale, 5 * scale)
    assert t.area == pytest.approx(6 * scale**2, rel=1e-14)
    for edge, s in zip(t.edges, t.sides):
        assert distance(edge.start, edge.end) == pytest.approx(s, rel=1e-13)


def test_sliver_triangle_is_accurate():
    # Very flat but valid: stable formulas must still reproduce the side lengths.
    t = Triangle(1.0, 1.0, 2.0 - 1e-6)
    a, b, c = t.vertices
    assert distance(a, b) == pytest.approx(1.0, rel=1e-12)
    assert distance(b, c) == pytest.approx(1.0, rel=1e-9)
    assert distance(c, a) == pytest.approx(2.0 - 1e-6, rel=1e-12)
    assert sum(t.angles) == pytest.approx(math.pi, abs=1e-12)
    assert t.area > 0


# ---------------------------------------------------------------- invalid input
@pytest.mark.parametrize(
    "sides",
    [
        (0, 1, 1),
        (-1, 1, 1),
        (1, 1, float("nan")),
        (1, float("inf"), 1),
        ("x", 1, 1),
        (None, 1, 1),
        (1, 2, 3),  # degenerate: equality
        (1, 1, 3),  # violates inequality
        (1, 1, 2 - 1e-12),  # within degeneracy tolerance
        (5, 1, 1),
    ],
)
def test_invalid_triangles_rejected(sides):
    with pytest.raises(InvalidTriangleError):
        Triangle(*sides)


def test_numeric_strings_and_ints_coerced_to_float():
    t = Triangle("3", 4, 5.0)
    assert isinstance(t.ab, float) and t.ab == 3.0


def test_triangle_is_immutable():
    t = Triangle(3, 4, 5)
    with pytest.raises(AttributeError):
        t.ab = 10  # type: ignore[misc]


# ---------------------------------------------------------------- properties
@given(triangles())
def test_vertices_reproduce_side_lengths(t):
    a, b, c = t.vertices
    assert rel_close(distance(a, b), t.ab)
    assert math.isclose(distance(b, c), t.bc, rel_tol=1e-9)
    assert math.isclose(distance(c, a), t.ca, rel_tol=1e-9)


@given(triangles())
def test_canonical_orientation_is_ccw(t):
    a, b, c = t.vertices
    assert a.x == 0 and a.y == 0 and b.y == 0 and b.x > 0
    assert c.y > 0
    assert signed_area(t.vertices) > 0


@given(triangles())
def test_angles_valid_and_sum_to_pi(t):
    for ang in t.angles:
        assert 0 < ang < math.pi
    assert math.isclose(sum(t.angles), math.pi, abs_tol=1e-12)


@given(triangles())
def test_angles_match_vertex_geometry(t):
    a, b, c = t.vertices
    for vertex, p, q, ang in ((a, b, c, t.angles[0]), (b, c, a, t.angles[1]), (c, a, b, t.angles[2])):
        u, v = p - vertex, q - vertex
        measured = math.atan2(abs(u.cross(v)), u.dot(v))
        assert math.isclose(measured, ang, abs_tol=1e-9)


@given(triangles())
def test_area_heron_matches_shoelace(t):
    assert math.isclose(signed_area(t.vertices), t.area, rel_tol=1e-9)


@given(triangles())
def test_law_of_sines(t):
    two_r = 2 * t.circumradius
    for side, ang in ((t.bc, t.angles[0]), (t.ca, t.angles[1]), (t.ab, t.angles[2])):
        assert math.isclose(side / math.sin(ang), two_r, rel_tol=1e-9)


@given(triangles())
def test_incenter_is_inradius_from_every_edge(t):
    i = t.incenter
    for e in t.edges:
        assert math.isclose(line_distance(i, e.start, e.end), t.inradius, rel_tol=1e-8, abs_tol=1e-9)


@given(triangles())
def test_edges_are_consistent(t):
    names = [e.name for e in t.edges]
    assert names == ["AB", "BC", "CA"]
    for e, s in zip(t.edges, t.sides):
        assert e.length == s
    # end angle of each edge equals start angle of the next
    for e, nxt in zip(t.edges, t.edges[1:] + t.edges[:1]):
        assert e.end == nxt.start
        assert e.end_angle == nxt.start_angle
    # outward normal points away from the interior
    for e in t.edges:
        assert e.outward_normal.dot(t.incenter - e.midpoint) < 0
