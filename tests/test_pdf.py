"""PDF output: exact 1:1 physical size on every paper format.

Three independent checks:
  1. pypdf parses the file: page sizes and every drawn coordinate, converted
     back to mm, match the geometry to 1e-6 mm.
  2. poppler's pdfinfo reports the page size (and recognises standard papers).
  3. poppler's pdftoppm rasterises at 254 dpi = exactly 10 px/mm, and lengths
     measured in pixels match the requested millimetres.
"""

from __future__ import annotations

import io
import math
import re
import shutil
import subprocess

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pypdf import PdfReader
from pypdf.generic import ContentStream

from domeprint.geometry import TabSpec, Triangle, Vec2, build_piece, distance, signed_area
from domeprint.layout import PAPER_SIZES_MM, Sheet, single_on_paper, tight_sheet
from domeprint.render import MM_TO_PT, RenderStyle, render_pdf
from domeprint.render.pdf import _pdf_string, text_width

from .conftest import triangles

# Coordinates are written at 1 nm resolution, so a length can be off by
# up to ~1.4 nm (two rounded endpoints).
TOL_MM = 2e-6
PAPERS = sorted(PAPER_SIZES_MM)

needs_poppler = pytest.mark.skipif(
    not (shutil.which("pdfinfo") and shutil.which("pdftoppm")), reason="poppler not installed"
)


def sample_sheet(paper="A4", sides=(120, 100, 100), tab=5.0):
    return single_on_paper(build_piece(Triangle(*sides), TabSpec(tab)), paper)


def read(pdf: bytes) -> PdfReader:
    return PdfReader(io.BytesIO(pdf), strict=True)


def strokes(reader: PdfReader, page_index: int = 0) -> tuple[float, list[dict]]:
    """Parse our content stream into stroked paths (coordinates in mm)."""
    page = reader.pages[page_index]
    ops = ContentStream(page.get_contents(), reader).operations
    scale = None
    result, current, state = [], [], {}
    for operands, op in ops:
        op = op.decode()
        if op == "cm":
            a, b, c, d, e, f = map(float, operands)
            assert b == c == e == f == 0 and a == d
            scale = a
        elif op == "RG":
            state["color"] = tuple(map(float, operands))
        elif op == "w":
            state["width"] = float(operands[0])
        elif op == "d":
            state["dash"] = tuple(float(x) for x in operands[0])
        elif op == "m":
            current.append({"pts": [Vec2(float(operands[0]), float(operands[1]))], "closed": False})
        elif op == "l":
            current[-1]["pts"].append(Vec2(float(operands[0]), float(operands[1])))
        elif op == "h":
            current[-1]["closed"] = True
        elif op == "S":
            result.append({**state, "subpaths": current})
            current = []
    assert scale is not None
    return scale, result


def mm_size(page) -> tuple[float, float]:
    box = page.mediabox
    return float(box.width) / MM_TO_PT, float(box.height) / MM_TO_PT


# ======================================================== page size
def test_mm_to_pt_constant():
    assert MM_TO_PT == 72 / 25.4
    assert 210 * MM_TO_PT == pytest.approx(595.2755905511812, abs=1e-12)


@pytest.mark.parametrize("paper", PAPERS)
def test_page_size_exact_on_every_paper(paper):
    reader = read(render_pdf(sample_sheet(paper)))
    w, h = mm_size(reader.pages[0])
    pw, ph = PAPER_SIZES_MM[paper]
    assert w == pytest.approx(pw, abs=TOL_MM)
    assert h == pytest.approx(ph, abs=TOL_MM)
    assert reader.pages[0].cropbox == reader.pages[0].mediabox


def test_tight_page_size_exact():
    sheet = tight_sheet(build_piece(Triangle(77.7, 66.6, 55.5), TabSpec(4.2)))
    w, h = mm_size(read(render_pdf(sheet)).pages[0])
    assert w == pytest.approx(sheet.width, abs=TOL_MM)
    assert h == pytest.approx(sheet.height, abs=TOL_MM)


def test_user_space_is_millimetres():
    scale, _ = strokes(read(render_pdf(sample_sheet())))
    assert scale == pytest.approx(MM_TO_PT, rel=1e-9)


def test_print_scaling_none():
    reader = read(render_pdf(sample_sheet()))
    assert reader.trailer["/Root"]["/ViewerPreferences"]["/PrintScaling"] == "/None"


# ======================================================== drawn geometry
@pytest.mark.parametrize("paper", PAPERS)
def test_cut_outline_exact_on_every_paper(paper):
    sheet = sample_sheet(paper)
    _, paths = strokes(read(render_pdf(sheet)))
    cut = paths[0]
    assert len(cut["subpaths"]) == 1 and cut["subpaths"][0]["closed"]
    pts = cut["subpaths"][0]["pts"]
    expected = sheet.placements[0].cut_outline
    assert len(pts) == len(expected)
    for p, e in zip(pts, expected):
        assert distance(p, e) <= TOL_MM


@pytest.mark.parametrize("paper", PAPERS)
def test_fold_lines_exact_lengths_on_every_paper(paper):
    _, paths = strokes(read(render_pdf(sample_sheet(paper))))
    fold = paths[1]
    lengths = [distance(*s["pts"]) for s in fold["subpaths"]]
    assert lengths == pytest.approx([120, 100, 100], abs=TOL_MM)


def test_cut_and_fold_styles_differ():
    _, paths = strokes(read(render_pdf(sample_sheet())))
    cut, fold = paths[0], paths[1]
    assert cut["dash"] == ()
    assert fold["dash"] == (2.0, 1.0)  # mm
    assert cut["color"] != fold["color"]
    assert cut["width"] == fold["width"] == 0.2  # mm


def test_calibration_bar_is_100mm():
    _, paths = strokes(read(render_pdf(sample_sheet())))
    bar = paths[-1]["subpaths"][0]["pts"]
    assert distance(bar[0], bar[1]) == pytest.approx(100, abs=TOL_MM)


def test_no_calibration_sentence_printed():
    pdf = render_pdf(sample_sheet())
    assert b"must measure" not in pdf
    assert "must measure" not in read(pdf).pages[0].extract_text()


def test_handedness_preserved():
    sheet = tight_sheet(build_piece(Triangle(100, 70, 50), TabSpec(5)))
    _, paths = strokes(read(render_pdf(sheet)))
    pts = paths[0]["subpaths"][0]["pts"]
    assert signed_area(pts) == pytest.approx(signed_area(sheet.placements[0].cut_outline), rel=1e-9)
    assert signed_area(pts) > 0


def test_labels_present_and_toggle():
    sheet = sample_sheet()
    text = read(render_pdf(sheet)).pages[0].extract_text()
    for label in ("AB 120.0", "BC 100.0", "CA 100.0"):
        assert label in text
    assert read(render_pdf(sheet, RenderStyle(show_labels=False))).pages[0].extract_text().strip() == ""


@given(triangles(min_side=2, max_side=180), st.floats(0.5, 8), st.sampled_from(PAPERS))
def test_rendered_geometry_property(t, w, paper):
    from domeprint.layout import DoesNotFitError

    try:
        sheet = single_on_paper(build_piece(t, TabSpec(w)), paper)
    except DoesNotFitError:
        return
    reader = read(render_pdf(sheet))
    _, paths = strokes(reader)
    for (seg), side in zip(paths[1]["subpaths"], t.sides):
        assert math.isclose(distance(*seg["pts"]), side, abs_tol=TOL_MM)
    for p, e in zip(paths[0]["subpaths"][0]["pts"], sheet.placements[0].cut_outline):
        assert distance(p, e) <= TOL_MM


# ======================================================== file structure
def test_multi_page():
    a4, a3 = sample_sheet("A4"), sample_sheet("A3")
    reader = read(render_pdf([a4, a3]))
    assert len(reader.pages) == 2
    assert mm_size(reader.pages[0]) == pytest.approx((210, 297), abs=TOL_MM)
    assert mm_size(reader.pages[1]) == pytest.approx((297, 420), abs=TOL_MM)


def test_empty_sheet_list_rejected():
    with pytest.raises(ValueError):
        render_pdf([])


def test_xref_offsets_point_at_objects():
    pdf = render_pdf([sample_sheet(), sample_sheet("A3")])
    start = int(re.search(rb"startxref\n(\d+)", pdf).group(1))
    assert pdf[start:].startswith(b"xref\n")
    entries = re.findall(rb"(\d{10}) 00000 n \n", pdf[start:])
    for num, off in enumerate(entries, start=1):
        assert pdf[int(off) :].startswith(b"%d 0 obj\n" % num)


def test_string_escaping():
    assert _pdf_string("a(b)c\\") == b"(a\\(b\\)c\\\\)"


def test_text_width_helvetica():
    assert text_width("AB 120.0", 1000) == 667 + 667 + 278 + 556 * 3 + 278 + 556


# ======================================================== poppler: independent tools
@needs_poppler
@pytest.mark.parametrize("paper", PAPERS)
def test_pdfinfo_page_size(tmp_path, paper):
    f = tmp_path / "p.pdf"
    f.write_bytes(render_pdf(sample_sheet(paper)))
    out = subprocess.run(["pdfinfo", str(f)], capture_output=True, text=True, check=True).stdout
    m = re.search(r"Page size:\s+([\d.]+) x ([\d.]+) pts", out)
    pw, ph = PAPER_SIZES_MM[paper]
    # pdfinfo prints 2 decimals
    assert float(m.group(1)) == pytest.approx(pw * MM_TO_PT, abs=0.006)
    assert float(m.group(2)) == pytest.approx(ph * MM_TO_PT, abs=0.006)
    if paper in ("A4", "A3", "LETTER"):  # pdfinfo has no name for A5/Legal
        assert f"({paper.lower()})" in out.lower()


def rasterize(tmp_path, pdf: bytes, dpi: int = 254):
    """Render page 1 to an 8-bit grayscale image without anti-aliasing."""
    f = tmp_path / "p.pdf"
    f.write_bytes(pdf)
    prefix = tmp_path / "img"
    subprocess.run(
        ["pdftoppm", "-gray", "-r", str(dpi), "-aa", "no", "-aaVector", "no", "-singlefile", str(f), str(prefix)],
        check=True,
    )
    data = (tmp_path / "img.pgm").read_bytes()
    m = re.match(rb"P5\s+(\d+)\s+(\d+)\s+(\d+)\s", data)
    w, h = int(m.group(1)), int(m.group(2))
    pixels = data[m.end() :]
    assert len(pixels) == w * h
    return w, h, pixels


def dark_runs(row: bytes) -> list[tuple[int, int]]:
    runs, start = [], None
    for i, v in enumerate(row):
        if v < 128 and start is None:
            start = i
        elif v >= 128 and start is not None:
            runs.append((start, i - 1))
            start = None
    if start is not None:
        runs.append((start, len(row) - 1))
    return runs


PX_PER_MM = 10  # 254 dpi


@needs_poppler
@pytest.mark.parametrize("paper", PAPERS)
def test_raster_page_is_exact_pixel_size(tmp_path, paper):
    w, h, _ = rasterize(tmp_path, render_pdf(sample_sheet(paper)))
    pw, ph = PAPER_SIZES_MM[paper]
    assert (w, h) == (round(pw * PX_PER_MM), round(ph * PX_PER_MM))


@needs_poppler
@pytest.mark.parametrize("paper", PAPERS)
def test_raster_calibration_ruler_measures_100mm(tmp_path, paper):
    sheet = sample_sheet(paper)
    w, h, px = rasterize(tmp_path, render_pdf(sheet))
    cal = sheet.calibration
    # A row 2.5 mm above the bar crosses only the two 3 mm end ticks.
    y_mm = cal.origin.y + 2.5
    row_index = round((sheet.height - y_mm) * PX_PER_MM)
    runs = dark_runs(px[row_index * w : (row_index + 1) * w])
    assert len(runs) == 2
    centers = [(a + b + 1) / 2 for a, b in runs]  # pixel i spans [i, i+1)
    assert centers[0] == pytest.approx(cal.origin.x * PX_PER_MM, abs=1)
    assert centers[1] - centers[0] == pytest.approx(100 * PX_PER_MM, abs=1)  # 100 mm +/- 0.1 mm


def stroke_center(px, w, h, x: float, y: float, vertical_scan: bool, reach: int = 6) -> float | None:
    """Centre of the dark run crossing the scanline through (x, y) px, or None."""
    if vertical_scan:
        c = int(math.floor(x))
        line = bytes(px[r * w + c] for r in range(h))
        pos = y
    else:
        r = int(math.floor(y))
        line = px[r * w : (r + 1) * w]
        pos = x
    lo, hi = int(pos) - reach, int(pos) + reach
    runs = [(a, b) for a, b in dark_runs(line[lo:hi]) ]
    if len(runs) != 1:
        return None
    a, b = runs[0]
    return lo + (a + b + 1) / 2  # pixel i spans [i, i+1)


@needs_poppler
@pytest.mark.parametrize("paper", PAPERS)
@pytest.mark.parametrize("sides", [(120, 100, 100), (100, 70, 50), (60, 50, 50)])
def test_raster_cut_outline_lies_exactly_on_geometry(tmp_path, paper, sides):
    """Every cut segment, sampled away from corners, is printed where the
    geometry says (+/- 1 px = 0.1 mm), on every paper size.

    Note: measuring ink extents would be wrong here: at sharp corners a mitred
    stroke legitimately reaches (width/2)/sin(angle/2) beyond the vertex.
    """
    sheet = sample_sheet(paper, sides)
    sheet = Sheet(sheet.width, sheet.height, sheet.placements, None)
    w, h, px = rasterize(tmp_path, render_pdf(sheet, RenderStyle(show_labels=False)))
    outline = [Vec2(p.x * PX_PER_MM, (sheet.height - p.y) * PX_PER_MM) for p in sheet.placements[0].cut_outline]
    checked = 0
    for i, a in enumerate(outline):
        b = outline[(i + 1) % len(outline)]
        d = b - a
        if d.length() < 40:  # skip segments shorter than 4 mm
            continue
        mostly_horizontal = abs(d.x) >= abs(d.y)
        for t in (0.3, 0.5, 0.7):
            p = a + d * t
            # Scan across the line: columns for horizontal-ish, rows for vertical-ish lines.
            got = stroke_center(px, w, h, p.x, p.y, vertical_scan=mostly_horizontal)
            if got is None:
                continue  # scanline also crosses a label or another stroke
            expected = p.y if mostly_horizontal else p.x
            # Sample at the pixel-column/row centre the scan actually used.
            if mostly_horizontal:
                xc = math.floor(p.x) + 0.5
                expected = a.y + d.y * (xc - a.x) / d.x
            else:
                yc = math.floor(p.y) + 0.5
                expected = a.x + d.x * (yc - a.y) / d.y
            assert got == pytest.approx(expected, abs=1.0), (i, t, got, expected)
            checked += 1
    assert checked >= 12
