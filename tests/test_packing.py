"""Multi-piece packing: rows of 180-degree-paired pieces with exact NFP contacts."""

import itertools
import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from domeprint.geometry import TabSpec, Transform2D, Triangle, Vec2, build_piece, signed_area
from domeprint.layout import (
    Demand,
    DoesNotFitError,
    PackOptions,
    Placement,
    Sheet,
    layout_problems,
    pack,
)
from domeprint.layout.packing import orient, row_area_per_piece

EQ = build_piece(Triangle.equilateral(50), TabSpec(0))
EQ_H = 25 * math.sqrt(3)
NO_GAP = PackOptions(paper="A4", margin=10, spacing=0)


# ======================================================== orientation
@pytest.mark.parametrize("edge", [0, 1, 2])
def test_orient_up_puts_chosen_edge_at_bottom(edge):
    piece = build_piece(Triangle(100, 70, 50), TabSpec(5))
    shape = orient(piece, edge, up=True)
    outline = shape.local_transform.apply_all(piece.cut_outline)
    xs, ys = [p.x for p in outline], [p.y for p in outline]
    assert min(xs) == pytest.approx(0, abs=1e-9) and min(ys) == pytest.approx(0, abs=1e-9)
    assert shape.width == pytest.approx(max(xs)) and shape.height == pytest.approx(max(ys))
    e = piece.triangle.edges[edge]
    a, b = shape.local_transform.apply(e.start), shape.local_transform.apply(e.end)
    assert a.y == pytest.approx(b.y, abs=1e-9)  # edge horizontal
    assert b.x > a.x  # running left to right, so the triangle is above it
    assert signed_area(outline) > 0  # rotation only, never mirrored


@pytest.mark.parametrize("edge", [0, 1, 2])
def test_orient_down_is_the_up_shape_turned_180(edge):
    piece = build_piece(Triangle(100, 70, 50), TabSpec(5))
    up, down = orient(piece, edge, up=True), orient(piece, edge, up=False)
    assert down.width == pytest.approx(up.width) and down.height == pytest.approx(up.height)
    turn = math.remainder(down.local_transform.angle - up.local_transform.angle, math.tau)
    assert abs(turn) == pytest.approx(math.pi, abs=1e-12)
    for p_up, p_down in zip(
        up.local_transform.apply_all(piece.cut_outline), down.local_transform.apply_all(piece.cut_outline)
    ):
        # 180-degree turn about the centre of the bounding box
        assert p_down.x == pytest.approx(up.width - p_up.x, abs=1e-9)
        assert p_down.y == pytest.approx(up.height - p_up.y, abs=1e-9)


# ======================================================== row density math
@pytest.mark.parametrize("sides", [(50, 50, 50), (100, 70, 50), (120, 100, 100), (30, 40, 50)])
@pytest.mark.parametrize("edge", [0, 1, 2])
def test_alternating_row_of_bare_triangles_has_no_waste(sides, edge):
    """U/D pairs tile a strip: area per piece equals the triangle area exactly."""
    piece = build_piece(Triangle(*sides), TabSpec(0))
    assert row_area_per_piece(piece, edge, spacing=0) == pytest.approx(piece.triangle.area, rel=1e-9)


@pytest.mark.parametrize("sides", [(50, 50, 50), (100, 70, 50)])
def test_same_orientation_row_wastes_half(sides):
    """Why pairing matters: without 180-degree turns a row uses twice the area."""
    piece = build_piece(Triangle(*sides), TabSpec(0))
    assert row_area_per_piece(piece, 0, spacing=0, alternate=False) == pytest.approx(2 * piece.triangle.area, rel=1e-9)


def test_spacing_increases_row_area():
    piece = build_piece(Triangle(100, 90, 90), TabSpec(5))
    assert row_area_per_piece(piece, 0, spacing=2) > row_area_per_piece(piece, 0, spacing=0)


# ======================================================== exact capacities
def test_equilateral_capacity_landscape_a4():
    # Landscape A4 printable area: 277 x 182 mm (8 mm calibration band).
    # Row of n alternating triangles is 25(n+1) mm long -> 10 per row; 4 rows of 43.3 mm.
    res = pack([Demand(EQ, 40)], NO_GAP)
    assert len(res.sheets) == 1
    assert (res.sheets[0].width, res.sheets[0].height) == (297, 210)
    assert len(res.sheets[0].placements) == 40


def test_equilateral_needs_landscape_for_two_sheets():
    # 80 pieces fit on 2 landscape sheets (40 each); portrait (36 each) would need 3.
    res = pack([Demand(EQ, 80)], NO_GAP)
    assert [len(s.placements) for s in res.sheets] == [40, 40]
    assert all(s.width == 297 for s in res.sheets)


def test_tie_on_sheet_count_prefers_least_paper_on_last_sheet():
    # 41 pieces need 2 sheets either way; portrait leaves less used on the last sheet.
    res = pack([Demand(EQ, 41)], NO_GAP)
    assert len(res.sheets) == 2 and sum(len(s.placements) for s in res.sheets) == 41


# ======================================================== mixed row orientations per sheet
RIGHT = build_piece(Triangle(50, 40, 30), TabSpec(0))  # right angle at C
SMALL = PackOptions(paper=(150, 78), margin=0, spacing=0, calibration=False, allow_landscape=False)


def test_row_options_of_right_triangle():
    """Hand-computed rows on 150 mm: base 50 -> 24 mm tall, 5 pieces;
    base 40 -> 30 mm, 6 pieces; base 30 -> 40 mm, 10 pieces (pairs form rectangles)."""
    from domeprint.layout.packing import _NfpCache, _row_options, printable_area

    area, _ = printable_area(150, 78, SMALL)
    opts = {round(o.height, 9): len(o.template) for o in _row_options(0, RIGHT, "", 0.0, area, _NfpCache())}
    assert opts == {24.0: 5, 30.0: 6, 40.0: 10}


def test_best_row_mix_is_optimal():
    from domeprint.layout.packing import _best_rows

    # (height, pieces) options on 78 mm, no spacing: 24+24+30 or 40+30 -> 16 pieces.
    options = [(24.0, 5), (30.0, 6), (40.0, 10)]
    rows = _best_rows(options, budget=78.0, spacing=0.0, remaining=1000)
    assert sum(options[i][1] for i in rows) == 16
    assert sum(options[i][0] for i in rows) == 70  # tie on pieces -> least height
    # Limited demand: the fewest-height combination that covers it.
    rows = _best_rows(options, budget=78.0, spacing=0.0, remaining=6)
    assert [options[i] for i in rows] == [(30.0, 6)]
    # Spacing counts between rows only.
    rows = _best_rows([(24.0, 5)], budget=78.0, spacing=3.0, remaining=1000)
    assert len(rows) == 3  # 24*3 + 3*2 = 78


def test_mixed_row_orientations_beat_uniform_rows():
    res = pack([Demand(RIGHT, 16)], SMALL)
    assert [len(s.placements) for s in res.sheets] == [16]
    assert layout_problems(res.sheets, [Demand(RIGHT, 16)], SMALL) == []


def test_portrait_only_capacity():
    # Portrait: 190 x 269 -> 6 per row, 6 rows = 36.
    res = pack([Demand(EQ, 40)], PackOptions(paper="A4", margin=10, spacing=0, allow_landscape=False))
    assert [len(s.placements) for s in res.sheets] == [36, 4]
    assert all((s.width, s.height) == (210, 297) for s in res.sheets)


def test_bare_triangles_touch_exactly():
    res = pack([Demand(EQ, 10)], NO_GAP)
    xs = sorted(p.bbox.min_x for p in res.sheets[0].placements)
    gaps = [b - a for a, b in itertools.pairwise(xs)]
    assert gaps == pytest.approx([25.0] * 9, abs=1e-9)


# ======================================================== row start and mirror orientations
DOME_A = build_piece(Triangle.isosceles(61.8, 54.7), TabSpec(5))


def test_row_tries_both_starting_orientations():
    """Leg as base: the gaps alternate 47.7 / 39.8 mm. Starting the row with the
    piece that gives the short gap first fits 6 pieces in 277 mm instead of 5."""
    from domeprint.layout.packing import _build_row, _NfpCache, printable_area

    area, _ = printable_area(297, 210, PackOptions())
    for edge in (1, 2):
        u = orient(DOME_A, edge, True, 2, key=(0, edge, True))
        d = orient(DOME_A, edge, False, 2, key=(0, edge, False))
        row = _build_row([(0, "")] * 20, [(u, d)], area, _NfpCache())
        assert len(row) == 6, edge


def test_mirror_orientations_are_not_merged():
    """Legs of an isosceles triangle give mirror-image shapes with equal bounding
    boxes. They are different shapes and must both be considered."""
    from domeprint.layout.packing import _distinct_edges

    assert sorted(_distinct_edges(DOME_A, 2)) == [0, 1, 2]
    eq = build_piece(Triangle.equilateral(50), TabSpec(5))
    assert len(_distinct_edges(eq, 2)) == 1  # truly identical shapes are merged


def test_dome_triangle_capacity_landscape_a4():
    res = pack([Demand(DOME_A, 36)], PackOptions(spacing=2))
    assert [len(s.placements) for s in res.sheets] == [18, 18]


# ======================================================== validity
dome_sides = st.tuples(st.floats(30, 90), st.floats(0.85, 1.15), st.floats(0.85, 1.15)).map(
    lambda t: (t[0], t[0] * t[1], t[0] * t[2])
)


@settings(max_examples=40, deadline=None)
@given(
    st.lists(st.tuples(dome_sides, st.integers(1, 25)), min_size=1, max_size=3),
    st.one_of(st.just(0.0), st.floats(0.5, 8)),
    st.floats(0, 4),
    st.sampled_from(["A4", "A3", "LETTER"]),
)
def test_random_jobs_are_valid(types, tab, spacing, paper):
    demands = []
    for k, (sides, count) in enumerate(types):
        try:
            t = Triangle(*sides)
        except ValueError:
            continue
        demands.append(Demand(build_piece(t, TabSpec(min(tab, 0.9 * t.inradius))), count, label=f"T{k}"))
    opts = PackOptions(paper=paper, margin=10, spacing=spacing)
    res = pack(demands, opts)
    assert layout_problems(res.sheets, demands, opts) == []


def test_spacing_is_respected():
    piece = build_piece(Triangle.isosceles(60, 50), TabSpec(5))
    opts = PackOptions(spacing=3)
    res = pack([Demand(piece, 30)], opts)
    assert layout_problems(res.sheets, [Demand(piece, 30)], opts) == []


def test_mixed_types_and_labels():
    a = build_piece(Triangle.isosceles(61.8, 54.7), TabSpec(5))
    b = build_piece(Triangle.equilateral(61.8), TabSpec(5))
    demands = [Demand(a, 30, "A"), Demand(b, 10, "B")]
    res = pack(demands, PackOptions())
    labels = [p.label for s in res.sheets for p in s.placements]
    assert labels.count("A") == 30 and labels.count("B") == 10
    assert layout_problems(res.sheets, demands, PackOptions()) == []


def test_empty_job():
    assert pack([], PackOptions()).sheets == ()


def test_too_large_piece_raises():
    with pytest.raises(DoesNotFitError):
        pack([Demand(build_piece(Triangle.equilateral(400), TabSpec(5)), 1)], PackOptions())


def test_bad_options():
    with pytest.raises(ValueError):
        PackOptions(spacing=-1)
    with pytest.raises(ValueError):
        Demand(EQ, -1)


def test_deterministic():
    d = [Demand(build_piece(Triangle(70, 60, 55), TabSpec(4)), 17)]
    assert pack(d, PackOptions()) == pack(d, PackOptions())


def test_custom_paper_size():
    res = pack([Demand(EQ, 4)], PackOptions(paper=(150, 100), margin=5, spacing=0, calibration=False))
    assert (res.sheets[0].width, res.sheets[0].height) in ((150, 100), (100, 150))
    assert res.sheets[0].calibration is None


# ======================================================== efficiency
def bbox_grid_capacity(piece, options):
    """Baseline: each piece in its bounding box, boxes in a grid, on the same
    printable areas (both page turns, best edge)."""
    from domeprint.layout import printable_area

    best = 0
    for pw, ph in options.page_sizes():
        area, _ = printable_area(pw, ph, options)
        s = options.spacing
        for edge in range(3):
            o = orient(piece, edge, up=True)
            best = max(best, int((area.width + s) // (o.width + s)) * int((area.height + s) // (o.height + s)))
    return best


@pytest.mark.parametrize(
    "sides, tab, min_ratio",
    [
        # Bare triangles: U/D pairing removes the half-box waste of each triangle.
        ((61.8, 54.7, 54.7), 0, 1.5),
        ((61.8, 61.8, 61.8), 0, 1.5),
        ((70, 60, 55), 0, 1.5),
        ((40, 35, 35), 0, 1.5),
        # 5 mm tabs: facing tabs need 2*tab + spacing, so the gain is smaller.
        ((61.8, 54.7, 54.7), 5, 1.15),
        ((61.8, 61.8, 61.8), 5, 1.15),
        ((70, 60, 55), 5, 1.15),
        ((40, 35, 35), 5, 1.15),
        # Pieces this large leave room for only 4 either way: never worse.
        ((120, 100, 100), 5, 1.0),
    ],
)
def test_beats_bounding_box_grid(sides, tab, min_ratio):
    piece = build_piece(Triangle(*sides), TabSpec(tab))
    opts = PackOptions(spacing=2)
    per_sheet = len(pack([Demand(piece, 500)], opts).sheets[0].placements)
    baseline = bbox_grid_capacity(piece, opts)
    assert per_sheet >= min_ratio * baseline, (per_sheet, baseline)


@pytest.mark.parametrize(
    "sides, tab, expected",
    [
        ((61.8, 54.7, 54.7), 0, 25),
        ((61.8, 54.7, 54.7), 5, 18),
        ((61.8, 61.8, 61.8), 5, 15),
        ((120, 100, 100), 0, 7),
        ((40, 35, 35), 5, 36),
    ],
)
def test_capacity_regression(sides, tab, expected):
    """Pieces per A4 sheet (2 mm spacing). Guards against silent regressions."""
    piece = build_piece(Triangle(*sides), TabSpec(tab))
    assert len(pack([Demand(piece, 500)], PackOptions(spacing=2)).sheets[0].placements) == expected


def test_fill_ratio():
    res = pack([Demand(EQ, 40)], NO_GAP)
    assert res.fill_ratio == pytest.approx(40 * EQ.triangle.area / (277 * 182), rel=1e-9)


# ======================================================== validator
def test_validator_detects_overlap_and_missing():
    piece = build_piece(Triangle.equilateral(50), TabSpec(5))
    p1 = Placement(piece, Transform2D(0, Vec2(50, 50)))
    p2 = Placement(piece, Transform2D(0, Vec2(60, 50)))
    sheet = Sheet(210, 297, (p1, p2))
    problems = layout_problems((sheet,), [Demand(piece, 3)], PackOptions(spacing=0))
    assert any("overlap" in p or "closer" in p for p in problems)
    assert any("placed 2" in p for p in problems)


def test_validator_detects_outside_margin():
    piece = build_piece(Triangle.equilateral(50), TabSpec(5))
    sheet = Sheet(210, 297, (Placement(piece, Transform2D(0, Vec2(1, 50))),))
    problems = layout_problems((sheet,), [Demand(piece, 1)], PackOptions())
    assert any("outside" in p for p in problems)


# ======================================================== fill one sheet
@pytest.mark.parametrize(
    "piece, opts, expected",
    [
        (EQ, NO_GAP, 40),  # landscape A4, 4 rows of 10
        (DOME_A, PackOptions(spacing=2), 18),
        (RIGHT, SMALL, 16),  # needs the mixed row orientations
    ],
)
def test_fill_sheet_holds_as_many_as_fit(piece, opts, expected):
    from domeprint.layout import fill_sheet

    sheet = fill_sheet(piece, opts)
    assert len(sheet.placements) == expected
    assert layout_problems((sheet,), [Demand(piece, expected)], opts) == []
    # One more copy needs a second sheet.
    assert len(pack([Demand(piece, expected + 1)], opts).sheets) == 2


def test_fill_sheet_too_large_piece():
    from domeprint.layout import fill_sheet

    with pytest.raises(DoesNotFitError):
        fill_sheet(build_piece(Triangle.equilateral(400), TabSpec(5)), PackOptions())
