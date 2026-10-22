# domeprint

Print-ready paper templates for geodesic dome triangles. You give the three side
lengths and the glue tab width. You get a vector file at exact physical size
(mm), where solid lines are cuts and dashed lines are folds.

```sh
uv sync
uv run domeprint 120 100 100 --tab 5 -o piece.svg                # SVG, page sized to the piece
uv run domeprint 120 100 100 --tab 5 --paper A4 -o piece.pdf     # PDF on A4 (A3, A5, LETTER, LEGAL)
uv run pytest                                                    # test suite
```

The output format follows the file extension; `--format pdf|svg` overrides it.
Solid black lines are cuts; dashed blue lines are folds (the original triangle
edges).

Print at **100% / "actual size"**, never "fit to page". The PDF asks viewers
for this by default (`/PrintScaling /None`). The ruler at the bottom (10 mm
ticks) must measure exactly 100 mm, or 50 mm on small pieces. `--no-calibration`
removes it.

## Exact size: how it is guaranteed and tested

- **PDF:** each page box is the paper size in points (1 mm = 72/25.4 pt), rounded
  *down* at 1e-6 pt so a page is never larger than the paper. Rounding up even
  that little makes poppler rasterise A4 at 2101 px instead of 2100 at 10 px/mm.
  A single `cm` operator scales the content to mm, so coordinates are written
  in mm at 1 nm resolution.
- **SVG:** `width="210mm"`, with a viewBox in the same numbers (1 unit = 1 mm).
- **Tests** in `tests/test_pdf.py` check every paper size three independent ways:
  - pypdf parses page sizes and every drawn coordinate, which match the geometry to 2 nm;
  - poppler's `pdfinfo` reports the page size;
  - poppler's `pdftoppm` rasterises at exactly 10 px/mm. The 100 mm ruler measures
    1000 px ± 1, and every cut segment lies on its exact position ± 0.1 mm.
- A deliberate 0.2% scale error makes 21 of those tests fail.

## Geometry

Sides are named by their endpoints: `AB`, `BC`, `CA`. The triangle is placed
with `A = (0,0)`, `B = (AB, 0)` and `C` above the x-axis, so `A→B→C` runs
counter-clockwise and the outward side of every edge is its right-hand side.
Area uses Kahan's stable form of Heron's formula. Angles use
`atan2(4K, b²+c²−a²)`. Both stay accurate for very thin triangles.

**Glue tabs.** Each edge carries a trapezoidal tab of perpendicular width `w`.
Its slanted ends start exactly at the triangle corners. The angle θ between the
fold line and a tab end, at a corner with interior angle α, is

    θ = min(max_end_angle, α / 2)        (max_end_angle defaults to 45°)

Capping at α/2 (the corner's angle bisector) guarantees that the three tabs of a
triangle never collide, even when folded fully flat against its back. Folded
over, each tab stays inside the region bounded by its edge and the two
bisectors, and those regions don't overlap. `--no-bisector` turns the cap off.

If an edge is too short for a full-width trapezoid, the tab becomes a triangle
whose tip is where the two slanted ends meet. Its height is reduced and a
warning is printed. With the bisector cap this happens exactly when
`w > inradius`. All three tabs then collapse to the incenter mirrored across
their edges, and the tests check this.

**Validation.** `build_piece` checks every piece it makes against the template
constraints and raises `GeometryError` if any fail. See `geometry/validate.py`:
- fold lines are exactly the triangle edges;
- each tab is attached to its edge and lies wholly outside the triangle;
- tab width is measured perpendicular to the edge, and the tab's outer edge is parallel to it;
- tabs don't overlap each other;
- each corner keeps a gap between neighbouring tabs;
- the cut outline doesn't cross itself, and its area equals the triangle plus the tabs.

**Corner trimming: bevel, not miter.** Each tab end is a straight cut through
the vertex. A miter join would put the tab end at 180° − α/2 from the edge,
which is more than 90°. Neighbouring tabs would then overhang the vertex, share
a cut line, and collide when folded.

## Architecture

```
src/domeprint/
  geometry/   pure math in mm: Vec2, Triangle, tabs, Piece (cut outline + fold lines),
              rigid Transform2D (rotation + translation only: no scaling, no mirroring)
  layout/     Sheet model (paper size, placed pieces, calibration ruler); single-piece layouts
  render/     display.py: Sheet -> renderer-neutral paths and text (shared by all formats)
              svg.py, pdf.py: write that list as-is; pdf.py needs only the standard library
  cli.py
```

Each layer depends only on the ones above it. Renderers never compute geometry.
Layout can only move and rotate pieces.

**Next step (designed for, not built):** multi-piece layout. Add a packer in
`layout/` that returns a list of `Sheet`s. `render_pdf` already writes a list of
sheets as a multi-page PDF, and the rigidity and inside-page checks in
`tests/test_layout.py` apply to any placement.

## License

MIT. See [LICENSE](LICENSE).
