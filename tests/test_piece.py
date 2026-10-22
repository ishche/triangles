import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from domeprint.geometry import (
    TabSpec,
    Transform2D,
    Triangle,
    Vec2,
    build_piece,
    distance,
    is_simple_polygon,
    signed_area,
)

from .conftest import convex_overlap_depth, line_distance, point_in_convex_ccw, reflect, triangles

widths = st.floats(0.1, 20)


def test_no_tabs_outline_is_the_triangle():
    t = Triangle(3, 4, 5)
    piece = build_piece(t, TabSpec(0))
    assert piece.cut_outline == t.vertices
    assert piece.fold_lines == ()
    assert piece.tabs == ()
    assert piece.warnings == ()


def test_equilateral_5mm_tabs_explicit():
    t = Triangle.equilateral(100)
    piece = build_piece(t, TabSpec(5))  # 60 deg corners -> 30 deg tab ends
    tab_ab = piece.tabs[0]
    inset = 5 / math.tan(math.radians(30))
    assert tab_ab.outer[0].x == pytest.approx(inset, abs=1e-12)
    assert tab_ab.outer[0].y == pytest.approx(-5, abs=1e-12)
    assert tab_ab.outer[1].x == pytest.approx(100 - inset, abs=1e-12)
    assert tab_ab.top_length == pytest.approx(100 - 2 * inset, abs=1e-12)
    assert len(piece.cut_outline) == 9
    assert piece.warnings == ()


def test_fixed_angle_mode_ignores_bisector():
    t = Triangle.equilateral(100)
    piece = build_piece(t, TabSpec(5, max_end_angle_deg=45, clamp_to_bisector=False))
    for tab in piece.tabs:
        assert tab.start_angle == pytest.approx(math.radians(45))
        assert tab.end_angle == pytest.approx(math.radians(45))


def test_truncation_reports_warning():
    t = Triangle.equilateral(20)  # inradius ~5.77
    piece = build_piece(t, TabSpec(8))
    assert all(tab.truncated for tab in piece.tabs)
    assert len(piece.warnings) == 3
    assert "AB" in piece.warnings[0]


@given(triangles(), widths)
def test_fold_lines_are_the_exact_triangle_edges(t, w):
    piece = build_piece(t, TabSpec(w))
    assert len(piece.fold_lines) == 3
    for seg, edge in zip(piece.fold_lines, t.edges):
        assert seg.start == edge.start and seg.end == edge.end
        assert math.isclose(seg.length, edge.length, rel_tol=1e-9)


@given(triangles(), widths)
def test_outline_passes_through_every_vertex_in_order(t, w):
    piece = build_piece(t, TabSpec(w))
    outline = list(piece.cut_outline)
    idx = [outline.index(v) for v in t.vertices]
    assert idx == sorted(idx)
    # between consecutive vertices are exactly that edge's tab outer points
    for k, tab in enumerate(piece.tabs):
        start = idx[k]
        assert tuple(outline[start + 1 : start + 1 + len(tab.outer)]) == tab.outer


@given(triangles(), widths)
def test_outline_is_simple_ccw_polygon(t, w):
    piece = build_piece(t, TabSpec(w))
    assert signed_area(piece.cut_outline) > 0
    assert is_simple_polygon(piece.cut_outline, eps=1e-9 * max(t.sides))


@given(triangles(), widths, st.floats(5, 90), st.booleans())
def test_outline_area_is_triangle_plus_tabs(t, w, max_angle, clamp):
    piece = build_piece(t, TabSpec(w, max_end_angle_deg=max_angle, clamp_to_bisector=clamp))
    expected = t.area + sum(tab.area for tab in piece.tabs)
    assert math.isclose(signed_area(piece.cut_outline), expected, rel_tol=1e-9)


@given(triangles(), widths)
def test_tabs_lie_outside_triangle_at_requested_width(t, w):
    piece = build_piece(t, TabSpec(w))
    for edge, tab in zip(t.edges, piece.tabs):
        for o in tab.outer:
            # On the outward side of its own edge, at exactly the tab height.
            assert math.isclose(-line_distance(o, edge.start, edge.end), tab.height, rel_tol=1e-9)
        if not tab.truncated:
            assert tab.height == w


@given(triangles(), widths)
def test_tab_end_angles_follow_bisector_rule(t, w):
    piece = build_piece(t, TabSpec(w, max_end_angle_deg=45))
    for edge, tab in zip(t.edges, piece.tabs):
        assert tab.start_angle == pytest.approx(min(math.radians(45), edge.start_angle / 2))
        assert tab.end_angle == pytest.approx(min(math.radians(45), edge.end_angle / 2))
        assert tab.start_angle <= edge.start_angle / 2 + 1e-15
        assert tab.end_angle <= edge.end_angle / 2 + 1e-15


@given(triangles(), widths, st.floats(5, 90))
def test_folded_tabs_stay_inside_triangle_and_never_overlap(t, w, max_angle):
    """Folding every tab flat onto its own triangle (worst case) must be collision-free."""
    piece = build_piece(t, TabSpec(w, max_end_angle_deg=max_angle))
    scale = max(t.sides)
    folded = []
    for edge, tab in zip(t.edges, piece.tabs):
        poly = [reflect(p, edge.start, edge.end) for p in tab.polygon]
        for p in poly:
            assert point_in_convex_ccw(p, t.vertices, eps=1e-9 * scale)
        folded.append(poly[::-1])  # reflection flips orientation; restore CCW
    for i in range(3):
        for j in range(i + 1, 3):
            assert convex_overlap_depth(folded[i], folded[j]) <= 1e-9 * scale


@given(triangles(), st.floats(0.05, 0.95))
def test_no_truncation_below_inradius(t, frac):
    piece = build_piece(t, TabSpec(t.inradius * frac, max_end_angle_deg=90))
    assert not any(tab.truncated for tab in piece.tabs)


@given(triangles(), st.floats(1.05, 3))
def test_above_inradius_all_tabs_truncate_to_mirrored_incenter(t, factor):
    # With pure bisector ends, all three trapezoids collapse at w == inradius,
    # and the apex is the incenter reflected across the edge.
    piece = build_piece(t, TabSpec(t.inradius * factor, max_end_angle_deg=90))
    for edge, tab in zip(t.edges, piece.tabs):
        assert tab.truncated
        assert math.isclose(tab.height, t.inradius, rel_tol=1e-9)
        mirrored = reflect(t.incenter, edge.start, edge.end)
        assert distance(tab.outer[0], mirrored) <= 1e-9 * max(t.sides)


@given(triangles(), widths, st.floats(-math.pi, math.pi), st.floats(-1000, 1000), st.floats(-1000, 1000))
def test_rigid_transform_preserves_dimensions_and_chirality(t, w, ang, dx, dy):
    piece = build_piece(t, TabSpec(w))
    tf = Transform2D(ang, Vec2(dx, dy))
    moved = tf.apply_all(piece.cut_outline)
    n = len(moved)
    for i in range(n):
        a, b = piece.cut_outline[i], piece.cut_outline[(i + 1) % n]
        assert math.isclose(distance(tf.apply(a), tf.apply(b)), distance(a, b), rel_tol=1e-9, abs_tol=1e-9)
    # Shoelace after a large translation loses ~eps * offset^2 to cancellation.
    tol = 1e-12 * (1 + abs(dx) + abs(dy) + max(t.sides)) ** 2
    assert math.isclose(signed_area(moved), signed_area(piece.cut_outline), rel_tol=1e-9, abs_tol=tol)
