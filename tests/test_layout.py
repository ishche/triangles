import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from domeprint.geometry import TabSpec, Triangle, build_piece, distance, signed_area
from domeprint.layout import (
    CALIBRATION_BAND_MM,
    PAPER_SIZES_MM,
    DoesNotFitError,
    single_on_paper,
    tight_sheet,
)

from .conftest import triangles


def assert_inside(sheet, margin):
    for pl in sheet.placements:
        bb = pl.bbox
        assert bb.min_x >= margin - 1e-9 and bb.max_x <= sheet.width - margin + 1e-9
        assert bb.min_y >= margin - 1e-9 and bb.max_y <= sheet.height - margin + 1e-9
    if sheet.calibration:
        c = sheet.calibration
        assert c.origin.x >= margin - 1e-9 and c.origin.x + c.length <= sheet.width - margin + 1e-9


def assert_rigid(pl):
    """Placed geometry has exactly the original dimensions and handedness."""
    src, dst = pl.piece.cut_outline, pl.cut_outline
    n = len(src)
    for i in range(n):
        j = (i + 1) % n
        assert math.isclose(distance(dst[i], dst[j]), distance(src[i], src[j]), rel_tol=1e-9, abs_tol=1e-9)
    assert math.isclose(signed_area(dst), signed_area(src), rel_tol=1e-9)
    for e, s in zip(pl.edges, pl.piece.triangle.sides):
        assert math.isclose(distance(e.start, e.end), s, rel_tol=1e-9)


def test_paper_sizes():
    assert PAPER_SIZES_MM["A4"] == (210.0, 297.0)


def test_unknown_paper():
    piece = build_piece(Triangle.equilateral(50), TabSpec(5))
    with pytest.raises(ValueError):
        single_on_paper(piece, "B7")


def test_tight_sheet_dimensions():
    piece = build_piece(Triangle.equilateral(100), TabSpec(5))
    sheet = tight_sheet(piece, margin=10)
    bb = piece.bbox
    assert sheet.width == pytest.approx(max(bb.width, 100) + 20)
    assert sheet.height == pytest.approx(bb.height + 20 + CALIBRATION_BAND_MM)
    assert sheet.calibration.length == 100
    assert_inside(sheet, 10)


def test_tight_sheet_without_calibration():
    piece = build_piece(Triangle.equilateral(30), TabSpec(3))
    sheet = tight_sheet(piece, margin=5, calibration=False)
    assert sheet.calibration is None
    assert sheet.width == pytest.approx(piece.bbox.width + 10)
    assert sheet.height == pytest.approx(piece.bbox.height + 10)


def test_a4_keeps_upright_when_it_fits():
    piece = build_piece(Triangle.isosceles(150, 120), TabSpec(5))
    sheet = single_on_paper(piece, "A4")
    assert (sheet.width, sheet.height) == (210, 297)
    assert sheet.placements[0].transform.angle == 0
    assert_inside(sheet, 10)


def test_a4_rotates_long_piece_to_fit():
    # 230 mm base does not fit 190 mm usable width but fits the 265 mm height.
    piece = build_piece(Triangle.isosceles(230, 130), TabSpec(5))
    sheet = single_on_paper(piece, "A4")
    assert sheet.placements[0].transform.angle != 0
    assert_inside(sheet, 10)
    assert_rigid(sheet.placements[0])


def test_too_large_raises():
    piece = build_piece(Triangle.equilateral(400), TabSpec(5))
    with pytest.raises(DoesNotFitError):
        single_on_paper(piece, "A4")


@given(triangles(min_side=5, max_side=180), st.floats(0.5, 10), st.sampled_from(["A4", "A3", "LETTER"]))
def test_single_on_paper_is_rigid_and_inside(t, w, paper):
    piece = build_piece(t, TabSpec(w))
    try:
        sheet = single_on_paper(piece, paper)
    except DoesNotFitError:
        return
    assert_inside(sheet, 10)
    assert_rigid(sheet.placements[0])


@given(triangles(), st.floats(0.5, 10))
def test_tight_sheet_is_rigid_and_inside(t, w):
    sheet = tight_sheet(build_piece(t, TabSpec(w)))
    assert_inside(sheet, 10)
    assert_rigid(sheet.placements[0])
