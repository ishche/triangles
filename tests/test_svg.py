import math
import re
import xml.etree.ElementTree as ET

import pytest
from hypothesis import given
from hypothesis import strategies as st

from domeprint.geometry import TabSpec, Triangle, Vec2, build_piece, distance, signed_area
from domeprint.layout import single_on_paper, tight_sheet
from domeprint.render import SvgStyle, render_svg

from .conftest import triangles

NS = {"svg": "http://www.w3.org/2000/svg"}


def parse(svg: str):
    return ET.fromstring(svg.encode())


def path_subpaths(d: str) -> list[list[Vec2]]:
    """Parse the M/L/Z absolute paths we emit into lists of points."""
    subpaths: list[list[Vec2]] = []
    for cmd, x, y in re.findall(r"([ML])\s+(-?[\d.]+)\s+(-?[\d.]+)", d):
        if cmd == "M":
            subpaths.append([])
        subpaths[-1].append(Vec2(float(x), float(y)))
    return subpaths


def to_geometry(points, sheet_height):
    return [Vec2(p.x, sheet_height - p.y) for p in points]


@pytest.fixture
def sample():
    piece = build_piece(Triangle.isosceles(120, 100), TabSpec(5))
    sheet = single_on_paper(piece, "A4")
    return sheet, parse(render_svg(sheet))


def test_physical_units(sample):
    sheet, root = sample
    assert root.get("width") == "210mm"
    assert root.get("height") == "297mm"
    assert root.get("viewBox") == "0 0 210 297"


def test_cut_and_fold_are_distinct(sample):
    _, root = sample
    cut = root.find(".//svg:path[@class='cut']", NS)
    fold = root.find(".//svg:path[@class='fold']", NS)
    assert cut is not None and fold is not None
    assert cut.get("stroke-dasharray") is None
    assert fold.get("stroke-dasharray") is not None
    assert cut.get("stroke") != fold.get("stroke")
    assert cut.get("fill") == fold.get("fill") == "none"
    assert cut.get("d").rstrip().endswith("Z")


def test_cut_path_matches_geometry_exactly(sample):
    sheet, root = sample
    pl = sheet.placements[0]
    d = root.find(".//svg:path[@class='cut']", NS).get("d")
    (pts,) = path_subpaths(d)
    got = to_geometry(pts, sheet.height)
    assert len(got) == len(pl.cut_outline)
    for g, e in zip(got, pl.cut_outline):
        assert distance(g, e) < 1e-4  # rounding to 4 decimals = 0.05 micrometre max


def test_fold_lines_have_exact_lengths(sample):
    sheet, root = sample
    d = root.find(".//svg:path[@class='fold']", NS).get("d")
    segs = path_subpaths(d)
    assert len(segs) == 3
    lengths = sorted(distance(a, b) for a, b in segs)
    assert lengths == pytest.approx(sorted([120, 100, 100]), abs=2e-4)


def test_handedness_preserved():
    # Scalene triangle: the rendered shape must not be mirrored.
    piece = build_piece(Triangle(100, 70, 50), TabSpec(5))
    sheet = tight_sheet(piece)
    root = parse(render_svg(sheet))
    (pts,) = path_subpaths(root.find(".//svg:path[@class='cut']", NS).get("d"))
    back = to_geometry(pts, sheet.height)
    assert signed_area(back) > 0  # still counter-clockwise in the y-up frame
    # coordinates are rounded to 1e-4 mm; area error is bounded by ~perimeter * 1e-4
    assert signed_area(back) == pytest.approx(signed_area(piece.cut_outline), abs=0.05)


def test_no_tabs_draws_triangle_as_cut_only():
    piece = build_piece(Triangle.equilateral(50), TabSpec(0))
    root = parse(render_svg(tight_sheet(piece)))
    assert root.find(".//svg:path[@class='fold']", NS) is None
    (pts,) = path_subpaths(root.find(".//svg:path[@class='cut']", NS).get("d"))
    assert len(pts) == 3


def test_labels_toggle():
    piece = build_piece(Triangle.equilateral(100), TabSpec(5))
    sheet = tight_sheet(piece)
    with_labels = parse(render_svg(sheet))
    without = parse(render_svg(sheet, SvgStyle(show_labels=False)))
    texts = [t.text for t in with_labels.findall(".//svg:text[@class='label']", NS)]
    assert texts == ["AB 100.0", "BC 100.0", "CA 100.0"]
    assert without.findall(".//svg:text[@class='label']", NS) == []


def test_labels_lie_inside_triangle():
    piece = build_piece(Triangle(120, 100, 90), TabSpec(5))
    sheet = tight_sheet(piece)
    root = parse(render_svg(sheet))
    a, b, c = sheet.placements[0].edges[0].start, sheet.placements[0].edges[1].start, sheet.placements[0].edges[2].start
    for t in root.findall(".//svg:text[@class='label']", NS):
        p = Vec2(float(t.get("x")), sheet.height - float(t.get("y")))
        for s, e in ((a, b), (b, c), (c, a)):
            assert (e - s).cross(p - s) > 0


def test_calibration_bar_length():
    sheet = tight_sheet(build_piece(Triangle.equilateral(120), TabSpec(5)))
    root = parse(render_svg(sheet))
    d = root.find(".//svg:path[@class='calibration']", NS).get("d")
    bar = path_subpaths(d)[0]
    assert distance(bar[0], bar[1]) == pytest.approx(100, abs=1e-9)


def test_number_formatting_has_no_negative_zero_or_exponent():
    root = parse(render_svg(tight_sheet(build_piece(Triangle.equilateral(10), TabSpec(1)))))
    for path in root.findall(".//svg:path", NS):
        for token in re.findall(r"[-\d.e]+", path.get("d")):
            assert re.fullmatch(r"-?\d+(\.\d+)?", token), token
            assert token != "-0"


@given(triangles(min_side=2, max_side=500), st.floats(0.5, 10))
def test_rendered_fold_lengths_property(t, w):
    sheet = tight_sheet(build_piece(t, TabSpec(w)))
    root = parse(render_svg(sheet))
    segs = path_subpaths(root.find(".//svg:path[@class='fold']", NS).get("d"))
    for (a, b), side in zip(segs, t.sides):
        assert math.isclose(distance(a, b), side, abs_tol=2e-4)
