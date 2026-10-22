"""Edge labels sit on the glue tabs (hidden after assembly), never on the triangle face."""

import math

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from domeprint.geometry import TabSpec, Triangle, Vec2, build_piece
from domeprint.geometry.polygon import point_in_convex_polygon
from domeprint.geometry.tabs import MIN_TAB_WIDTH_MM
from domeprint.layout import Demand, PackOptions, pack, tight_sheet
from domeprint.render import RenderStyle, display_list
from domeprint.render.display import CAP_HEIGHT, MIN_LABEL_SIZE_MM, TextItem, tab_label, text_width

from .conftest import triangles

STYLE = RenderStyle()


def label_box(item: TextItem) -> list[Vec2]:
    """Corners of the label's ink box: baseline to cap height, full text width."""
    d = Vec2(math.cos(item.angle), math.sin(item.angle))
    up = d.perp_left()
    half = text_width(item.text, item.size) / 2
    base = item.position
    cap = up * (CAP_HEIGHT * item.size)
    return [base - d * half, base + d * half, base + d * half + cap, base - d * half + cap]


def assert_on_tab(item: TextItem, tab, triangle_vertices):
    box = label_box(item)
    scale = max((tab.end - tab.start).length(), 1.0)
    for p in box:
        assert point_in_convex_polygon(p, tab.polygon, eps=1e-9 * scale), "label leaves the tab"
        # Not on the visible face: on or beyond the fold line.
        edge_dir = tab.end - tab.start
        assert edge_dir.cross(p - tab.start) <= 1e-9 * scale


# ---------------------------------------------------------------- exact placement
REF = build_piece(Triangle.isosceles(60, 50), TabSpec(5))


def test_reference_labels_are_on_tabs_and_upright_from_outside():
    for edge, tab in zip(REF.triangle.edges, REF.tabs):
        item = tab_label(tab, f"{edge.name} {edge.length:.1f}", STYLE)
        assert item is not None
        assert_on_tab(item, tab, REF.vertices)
        # Text runs against the edge direction so the glyphs point outward.
        up = Vec2(math.cos(item.angle), math.sin(item.angle)).perp_left()
        assert up.x == pytest.approx(edge.outward_normal.x, abs=1e-12)
        assert up.y == pytest.approx(edge.outward_normal.y, abs=1e-12)


def test_label_size_and_vertical_centering():
    tab = REF.tabs[0]  # base AB, 5 mm tab
    item = tab_label(tab, "AB 60.0", STYLE)
    assert item.size == pytest.approx(3.0)  # min(label_size 3, 0.6 * 5)
    baseline_offset = -(tab.end - tab.start).normalized().cross(item.position - tab.start)
    assert baseline_offset == pytest.approx((5 - CAP_HEIGHT * 3) / 2)


def test_label_centered_between_the_bevels():
    # Base tab of the reference: both ends bevelled at 26.57 deg -> symmetric about x = 30.
    item = tab_label(REF.tabs[0], "AB 60.0", STYLE)
    assert item.position.x == pytest.approx(30.0)


def test_narrow_tab_shrinks_font():
    piece = build_piece(Triangle.isosceles(60, 50), TabSpec(2))
    item = tab_label(piece.tabs[0], "AB 60.0", STYLE)
    assert item.size == pytest.approx(1.2)


def test_too_narrow_tab_has_no_label():
    piece = build_piece(Triangle.isosceles(60, 50), TabSpec(1))
    assert tab_label(piece.tabs[0], "AB 60.0", STYLE) is None


def test_short_edge_shrinks_or_drops_label():
    piece = build_piece(Triangle.equilateral(12), TabSpec(3))
    item = tab_label(piece.tabs[0], "AB 12.0", STYLE)
    if item is not None:
        assert item.size < 1.8
        assert_on_tab(item, piece.tabs[0], piece.vertices)


# ---------------------------------------------------------------- properties
@given(triangles(min_side=5, max_side=500), st.floats(0.5, 15))
def test_every_label_lies_on_its_tab(t, w):
    w = min(w, 0.95 * t.inradius)
    assume(w >= MIN_TAB_WIDTH_MM)
    piece = build_piece(t, TabSpec(w))
    for edge, tab in zip(t.edges, piece.tabs):
        item = tab_label(tab, f"{edge.name} {edge.length:.1f}", STYLE)
        if item is None:
            continue
        assert item.size >= MIN_LABEL_SIZE_MM
        assert item.size <= min(STYLE.label_size, 0.6 * tab.height) + 1e-12
        assert_on_tab(item, tab, piece.vertices)


# ---------------------------------------------------------------- display list
def labels(sheet):
    return [i for g in display_list(sheet, STYLE) for i in g.items if isinstance(i, TextItem) and i.role == "label"]


def test_no_tabs_no_labels():
    sheet = tight_sheet(build_piece(Triangle.equilateral(100), TabSpec(0)))
    assert labels(sheet) == []


def test_placed_labels_follow_rotated_tabs():
    piece = build_piece(Triangle.isosceles(61.8, 54.7), TabSpec(5))
    res = pack([Demand(piece, 18)], PackOptions())
    sheet = res.sheets[0]
    items = labels(sheet)
    assert len(items) == 3 * 18
    for pl, chunk in zip(sheet.placements, [items[i : i + 3] for i in range(0, len(items), 3)]):
        tf = pl.transform
        for tab, item in zip(pl.piece.tabs, chunk):
            placed_tab = type(tab)(
                tf.apply(tab.start),
                tf.apply(tab.end),
                tuple(tf.apply(p) for p in tab.outer),
                tab.start_angle,
                tab.end_angle,
                tab.requested_width,
                tab.height,
            )
            assert_on_tab(item, placed_tab, tf.apply_all(pl.piece.vertices))
