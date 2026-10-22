"""Tests for the template constraints: isosceles shapes, perpendicular tab width,
bevelled corner trimming, tab intersections, and the runtime validator."""

import dataclasses
import math

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from domeprint.geometry import (
    GeometryError,
    TabSpec,
    Triangle,
    Vec2,
    build_piece,
    build_tab,
    convex_overlap_depth,
    distance,
    is_simple_polygon,
    piece_problems,
    validate_piece,
)
from domeprint.geometry.tabs import MIN_TAB_WIDTH_MM

from .conftest import line_distance

DEG = math.pi / 180


def isosceles_from_apex(apex_deg: float, leg: float = 100.0) -> Triangle:
    base = 2 * leg * math.sin(math.radians(apex_deg) / 2)
    return Triangle.isosceles(base, leg)


def mirror(p: Vec2, axis_x: float) -> Vec2:
    return Vec2(2 * axis_x - p.x, p.y)


def ccw_angle(u: Vec2, v: Vec2) -> float:
    """Counter-clockwise angle from u to v in [0, 2pi)."""
    return math.atan2(u.cross(v), u.dot(v)) % math.tau


def outline_interior_angle(outline, vertex: Vec2) -> float:
    i = outline.index(vertex)
    prev, nxt = outline[i - 1], outline[(i + 1) % len(outline)]
    return ccw_angle(nxt - vertex, prev - vertex)


def close(p: Vec2, x: float, y: float, tol=1e-12):
    return math.isclose(p.x, x, abs_tol=tol) and math.isclose(p.y, y, abs_tol=tol)


apex_angles = st.floats(0.5, 175.0)
legs = st.floats(5.0, 2000.0)
width_fracs = st.floats(0.01, 0.99)  # tab width as a fraction of the inradius


@st.composite
def isosceles_pieces(draw, max_angle=None, clamp=True):
    t = isosceles_from_apex(draw(apex_angles), draw(legs))
    w = t.inradius * draw(width_fracs)
    assume(w >= MIN_TAB_WIDTH_MM)  # narrower tabs are rejected by TabSpec
    angle = draw(st.floats(1, 90)) if max_angle is None else max_angle
    return build_piece(t, TabSpec(w, max_end_angle_deg=angle, clamp_to_bisector=clamp))


# ======================================================== exact reference case
class TestReferenceIsosceles:
    """Base 60, legs 50: C = (30, 40), tan(B/2) = 1/2, tan(C/2) = 3/4, inradius 15.

    Tab width 5 => insets 5/(1/2) = 10 at base corners, 5/(3/4) = 20/3 at the apex.
    """

    t = Triangle.isosceles(60, 50)
    piece = build_piece(t, TabSpec(5))

    def test_triangle(self):
        _a, _b, c = self.t.vertices
        assert close(c, 30, 40)
        assert math.isclose(self.t.inradius, 15, rel_tol=1e-15)
        assert math.isclose(math.tan(self.t.angles[0] / 2), 0.5, rel_tol=1e-14)
        assert math.isclose(math.tan(self.t.angles[2] / 2), 0.75, rel_tol=1e-14)

    def test_base_tab(self):
        ab = self.piece.tabs[0]
        assert close(ab.outer[0], 10, -5) and close(ab.outer[1], 50, -5)

    def test_leg_tabs(self):
        bc, ca = self.piece.tabs[1], self.piece.tabs[2]
        assert close(bc.outer[0], 58, 11) and close(bc.outer[1], 38, 40 - 20 / 3 * 0.8 + 3)
        assert close(ca.outer[0], 22, 40 - 20 / 3 * 0.8 + 3) and close(ca.outer[1], 2, 11)

    def test_full_outline(self):
        y_top = 40 - 16 / 3 + 3
        expected = [(0, 0), (10, -5), (50, -5), (60, 0), (58, 11), (38, y_top), (30, 40), (22, y_top), (2, 11)]
        assert len(self.piece.cut_outline) == len(expected)
        for p, (x, y) in zip(self.piece.cut_outline, expected):
            assert close(p, x, y), (p, x, y)

    def test_bevel_lengths(self):
        # Bevel (slanted end) length = w / sin(theta): sin(B/2) = 1/sqrt5, sin(C/2) = 3/5
        bc = self.piece.tabs[1]
        assert math.isclose(distance(bc.start, bc.outer[0]), 5 * math.sqrt(5), rel_tol=1e-14)
        assert math.isclose(distance(bc.end, bc.outer[1]), 5 / 0.6, rel_tol=1e-14)


# ======================================================== isosceles symmetry
@given(isosceles_pieces())
def test_isosceles_piece_is_mirror_symmetric(piece):
    t = piece.triangle
    axis = t.ab / 2
    scale = max(t.sides)
    outline = piece.cut_outline
    mirrored = [mirror(p, axis) for p in reversed(outline)]
    # Mirror reverses orientation; after reversing, the outline maps onto itself.
    # Align on vertex A (which is the mirror image of B).
    a = t.vertices[0]
    shift = outline.index(a) - next(k for k, p in enumerate(mirrored) if distance(p, a) <= 1e-9 * scale)
    for k, p in enumerate(mirrored):
        q = outline[(k + shift) % len(outline)]
        assert distance(p, q) <= 1e-9 * scale


@given(isosceles_pieces())
def test_isosceles_leg_tabs_are_congruent(piece):
    _, bc, ca = piece.tabs
    assert math.isclose(bc.area, ca.area, rel_tol=1e-9)
    assert math.isclose(bc.start_angle, ca.end_angle, rel_tol=1e-12)
    assert math.isclose(bc.end_angle, ca.start_angle, rel_tol=1e-12)
    ab = piece.tabs[0]
    assert math.isclose(ab.start_angle, ab.end_angle, rel_tol=1e-12)


# ======================================================== acute angles
@pytest.mark.parametrize("apex", [0.5, 1, 2, 5, 10, 20, 36, 45, 60])
@pytest.mark.parametrize("frac", [0.1, 0.5, 0.9, 0.999])
def test_acute_apex_below_inradius(apex, frac):
    t = isosceles_from_apex(apex, leg=300)
    piece = build_piece(t, TabSpec(t.inradius * frac))
    assert piece_problems(piece) == []
    apex_tab_angle = piece.tabs[1].end_angle
    assert math.isclose(apex_tab_angle, math.radians(apex) / 2, rel_tol=1e-9)
    assert not any(tab.truncated for tab in piece.tabs)
    # Inset along each leg at the apex is w / tan(apex/2): long for sharp apexes.
    bc = piece.tabs[1]
    inset = (bc.end - bc.outer[1]).dot((bc.end - bc.start).normalized())
    assert math.isclose(inset, bc.height / math.tan(apex_tab_angle), rel_tol=1e-9)


@pytest.mark.parametrize("apex", [0.5, 1, 5, 20])
def test_acute_apex_wide_tabs_truncate_but_stay_valid(apex):
    t = isosceles_from_apex(apex, leg=300)
    piece = build_piece(t, TabSpec(t.inradius * 3))
    assert all(tab.truncated for tab in piece.tabs)
    assert len(piece.warnings) == 3
    assert piece_problems(piece) == []


def test_sharp_sliver_with_5mm_tab():
    # 10 mm base, 200 mm legs: apex ~2.86 deg, inradius ~4.88 mm < 5 mm.
    t = Triangle.isosceles(10, 200)
    assert t.inradius < 5
    piece = build_piece(t, TabSpec(5))
    assert all(tab.truncated for tab in piece.tabs)
    assert all(math.isclose(tab.height, t.inradius, rel_tol=1e-9) for tab in piece.tabs)
    ok = build_piece(t, TabSpec(2))
    assert not any(tab.truncated for tab in ok.tabs)


@pytest.mark.parametrize("apex", [100, 120, 150, 170, 178])
def test_obtuse_apex(apex):
    t = isosceles_from_apex(apex, leg=100)
    piece = build_piece(t, TabSpec(t.inradius * 0.8))
    # Obtuse apex: 45deg cap applies there; sharp base corners use their bisector.
    assert math.isclose(piece.tabs[1].end_angle, 45 * DEG, rel_tol=1e-12)
    assert math.isclose(piece.tabs[0].start_angle, t.angles[0] / 2, rel_tol=1e-12)
    assert piece_problems(piece) == []


# ======================================================== perpendicular width
@given(isosceles_pieces(max_angle=90))
def test_tab_width_is_perpendicular_to_edge(piece):
    t = piece.triangle
    eps = 1e-9 * max(t.sides)
    for e, tab in zip(t.edges, piece.tabs):
        assert tab.height == tab.requested_width  # pure bisector, below inradius: never truncated
        u = e.direction
        for o in tab.outer:
            assert math.isclose(-line_distance(o, e.start, e.end), tab.requested_width, rel_tol=1e-9)
            # Foot of the perpendicular lies on the edge itself.
            s = (o - e.start).dot(u)
            assert -eps <= s <= e.length + eps
        # Outer edge is parallel to the fold line.
        top = tab.outer[1] - tab.outer[0]
        assert abs(top.normalized().cross(u)) <= 1e-9
        assert top.dot(u) > 0
        # No point of the tab is farther than the width from the edge line.
        assert max(-line_distance(p, e.start, e.end) for p in tab.polygon) <= tab.requested_width + eps


@given(isosceles_pieces())
def test_tab_height_never_exceeds_width_with_any_cap(piece):
    """Small angle caps lengthen the bevels, so short edges may truncate even
    below the inradius; the result is still exactly perpendicular and never wider."""
    t = piece.triangle
    for e, tab in zip(t.edges, piece.tabs):
        assert tab.height <= tab.requested_width
        for o in tab.outer:
            assert math.isclose(-line_distance(o, e.start, e.end), tab.height, rel_tol=1e-9)
        if tab.truncated:
            cot = lambda a: math.cos(a) / math.sin(a)  # noqa: E731
            assert tab.requested_width * (cot(tab.start_angle) + cot(tab.end_angle)) >= e.length * (1 - 1e-9)
            assert math.isclose(tab.height, e.length / (cot(tab.start_angle) + cot(tab.end_angle)), rel_tol=1e-9)


@given(isosceles_pieces())
def test_bevel_is_longer_than_width(piece):
    """Width is measured perpendicular, so the slanted end is w / sin(theta) >= w."""
    for tab in piece.tabs:
        assert math.isclose(distance(tab.start, tab.outer[0]), tab.height / math.sin(tab.start_angle), rel_tol=1e-9)
        assert math.isclose(distance(tab.end, tab.outer[-1]), tab.height / math.sin(tab.end_angle), rel_tol=1e-9)


# ======================================================== corner trimming
@given(isosceles_pieces())
def test_corner_trim_angles_at_every_vertex(piece):
    """Interior angle of the cut outline at a vertex = alpha + both bevel angles."""
    t = piece.triangle
    tabs = piece.tabs
    for k, e in enumerate(t.edges):
        vertex, alpha = e.start, e.start_angle
        theta_in = tabs[k - 1].end_angle  # tab arriving at this vertex
        theta_out = tabs[k].start_angle  # tab leaving this vertex
        measured = outline_interior_angle(piece.cut_outline, vertex)
        assert math.isclose(measured, alpha + theta_in + theta_out, abs_tol=1e-9)
        # The remaining gap is never closed: tabs cannot meet beyond the vertex.
        assert math.tau - measured > 0


@given(isosceles_pieces(max_angle=90))
def test_bisector_trim_bounds_the_gap(piece):
    """With bisector trimming, each bevel is at most alpha/2, so the gap >= 2pi - 2alpha."""
    t = piece.triangle
    for k, e in enumerate(t.edges):
        alpha = e.start_angle
        assert piece.tabs[k].start_angle <= alpha / 2 + 1e-15
        assert piece.tabs[k - 1].end_angle <= alpha / 2 + 1e-15
        measured = outline_interior_angle(piece.cut_outline, e.start)
        assert math.tau - measured >= math.tau - 2 * alpha - 1e-9


@given(isosceles_pieces())
def test_bevel_lines_pass_through_the_vertex(piece):
    for tab in piece.tabs:
        d = (tab.end - tab.start).normalized()
        b1 = (tab.outer[0] - tab.start).normalized()
        b2 = (tab.outer[-1] - tab.end).normalized()
        assert math.isclose(math.atan2(-d.cross(b1), d.dot(b1)), tab.start_angle, abs_tol=1e-9)
        assert math.isclose(math.atan2(-d.cross(b2), -d.dot(b2)), tab.end_angle, abs_tol=1e-9)


@given(st.builds(isosceles_from_apex, apex_angles, legs), st.floats(1.01, 5))
def test_truncated_apex_lies_on_both_bevel_lines(t, factor):
    piece = build_piece(t, TabSpec(t.inradius * factor))
    for tab in piece.tabs:
        assert tab.truncated
        (apex,) = tab.outer
        d = (tab.end - tab.start).normalized()
        to_apex_s = apex - tab.start
        to_apex_e = apex - tab.end
        assert math.isclose(math.atan2(-d.cross(to_apex_s), d.dot(to_apex_s)), tab.start_angle, abs_tol=1e-9)
        assert math.isclose(math.atan2(-d.cross(to_apex_e), -d.dot(to_apex_e)), tab.end_angle, abs_tol=1e-9)


# ======================================================== tab intersections
@given(isosceles_pieces())
def test_flat_tabs_do_not_overlap_each_other_or_the_triangle(piece):
    t = piece.triangle
    eps = 1e-9 * max(t.sides)
    tabs = piece.tabs
    for i in range(3):
        assert convex_overlap_depth(tabs[i].polygon, t.vertices) <= eps
        for j in range(i + 1, 3):
            assert convex_overlap_depth(tabs[i].polygon, tabs[j].polygon) <= eps


@given(isosceles_pieces(max_angle=90, clamp=False))
def test_no_overlap_even_without_bisector_clamp(piece):
    """Bevels up to 90deg cannot make neighbouring flat tabs overlap (alpha < 180deg)."""
    eps = 1e-9 * max(piece.triangle.sides)
    tabs = piece.tabs
    for i in range(3):
        for j in range(i + 1, 3):
            assert convex_overlap_depth(tabs[i].polygon, tabs[j].polygon) <= eps
    assert is_simple_polygon(piece.cut_outline, eps)


@given(st.builds(isosceles_from_apex, apex_angles, legs), st.floats(0.01, 10))
def test_any_width_gives_valid_piece(t, factor):
    assume(t.inradius * factor >= MIN_TAB_WIDTH_MM)
    piece = build_piece(t, TabSpec(t.inradius * factor))
    assert piece_problems(piece) == []


def test_untrimmed_tabs_would_overlap():
    """Sanity check of the overlap test itself: plain rectangular strips at an
    acute corner do overlap, which is why trimming is needed."""
    t = Triangle.isosceles(60, 50)
    edges = t.edges
    w = 5
    rect = [(e.start, e.start + e.outward_normal * w, e.end + e.outward_normal * w, e.end) for e in edges]
    # Extend each strip past its vertices like an untrimmed offset band.
    ext = []
    for e in edges:
        u, n = e.direction, e.outward_normal
        a, b = e.start - u * 20, e.end + u * 20
        ext.append((a, a + n * w, b + n * w, b))
    assert convex_overlap_depth(ext[0], ext[1]) > 1
    assert all(convex_overlap_depth(rect[i], rect[(i + 1) % 3]) <= 1e-9 for i in range(3))


# ======================================================== validator
class TestValidatorDetectsViolations:
    piece = build_piece(Triangle.isosceles(60, 50), TabSpec(5))

    def test_valid_piece_passes(self):
        assert validate_piece(self.piece) is self.piece

    def test_build_piece_validates(self, monkeypatch):
        import domeprint.geometry.piece as piece_mod

        good = piece_mod._construct
        monkeypatch.setattr(piece_mod, "_construct", lambda t, s: dataclasses.replace(good(t, s), fold_lines=()))
        with pytest.raises(GeometryError, match="fold lines"):
            build_piece(Triangle.isosceles(60, 50), TabSpec(5))

    def test_shifted_fold_line(self):
        f = list(self.piece.fold_lines)
        f[0] = dataclasses.replace(f[0], start=f[0].start + Vec2(0.01, 0))
        bad = dataclasses.replace(self.piece, fold_lines=tuple(f))
        assert any("fold line AB" in p for p in piece_problems(bad))

    def test_tab_on_inner_side(self):
        tabs = list(self.piece.tabs)
        e = self.piece.triangle.edges[0]
        tabs[0] = build_tab(e.end, e.start, 30 * DEG, 30 * DEG, 5)  # reversed => inward
        bad = dataclasses.replace(self.piece, tabs=tuple(tabs))
        problems = piece_problems(bad)
        assert any("not attached" in p for p in problems)
        assert any("inside the triangle" in p for p in problems)

    def test_wrong_width(self):
        tabs = list(self.piece.tabs)
        e = self.piece.triangle.edges[0]
        t0 = tabs[0]
        tabs[0] = build_tab(e.start, e.end, t0.start_angle, t0.end_angle, 4.9)
        tabs[0] = dataclasses.replace(tabs[0], requested_width=5.0)
        bad = dataclasses.replace(self.piece, tabs=tuple(tabs))
        assert any("height" in p for p in piece_problems(bad))

    def test_overlapping_tabs(self):
        # Untrimmed strips extended 20 mm past both vertices (like an offset band):
        # neighbouring strips overlap in the wedge opposite each corner.
        tabs = []
        for tab, e in zip(self.piece.tabs, self.piece.triangle.edges):
            u, n = e.direction, e.outward_normal
            tabs.append(dataclasses.replace(tab, outer=(e.start - u * 20 + n * 5, e.end + u * 20 + n * 5)))
        bad = dataclasses.replace(self.piece, tabs=tuple(tabs))
        problems = piece_problems(bad)
        assert any("tabs AB and BC overlap" in p for p in problems)
        assert any("tabs AB and CA overlap" in p for p in problems)

    def test_self_intersecting_outline(self):
        o = list(self.piece.cut_outline)
        o[1], o[2] = o[2], o[1]
        bad = dataclasses.replace(self.piece, cut_outline=tuple(o))
        assert any("self-intersects" in p for p in piece_problems(bad))

    def test_clockwise_outline(self):
        bad = dataclasses.replace(self.piece, cut_outline=tuple(reversed(self.piece.cut_outline)))
        assert any("counter-clockwise" in p for p in piece_problems(bad))

    def test_problems_raise(self):
        bad = dataclasses.replace(self.piece, fold_lines=())
        with pytest.raises(GeometryError):
            validate_piece(bad)
