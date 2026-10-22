# Architecture

```
src/domeprint/
  geometry/   pure math in mm: Vec2, Triangle, glue tabs, Piece (cut outline + fold
              lines), runtime validation, convex-polygon tools, rigid Transform2D
  layout/     where pieces go on paper: Sheet / Placement model, single-piece
              layouts, multi-piece packing (no-fit polygons), layout validation
  render/     display.py turns a Sheet into renderer-neutral paths and text;
              svg.py and pdf.py write that list as-is (pdf.py is standard library only)
  cli.py      command line
```

## Data flow

```
Triangle(ab, bc, ca) + TabSpec(width)
        │  build_piece()            geometry: exact shape, validated
        ▼
      Piece  (cut outline, fold lines, tabs)
        │  tight_sheet() / single_on_paper() / pack()
        ▼
  Sheet(s)  (paper size, Placements = Piece + rigid transform, ruler)
        │  display_list()
        ▼
  paths + text in sheet mm
        │  render_svg() / render_pdf()
        ▼
   .svg / .pdf  at 1:1 scale
```

## Rules between layers

- **geometry** knows nothing about paper or file formats. Everything is in
  millimetres, y-up.
- **layout** may only move and rotate pieces (`Transform2D` cannot scale or
  mirror). Any layout can be checked with `layout_problems()`.
- **render** never computes geometry. It draws what the display list says, in
  the same units. Both formats share one display list, so they always agree.

## Extension points

- **New output format:** add `render/<format>.py` that serializes
  `display_list(sheet, style)`.
- **Dome calculator:** a future `dome/` package can turn diameter, frequency and
  configuration into triangle types and counts. Each type becomes a `Piece` and a
  `Demand(piece, count, label)` for `pack()`.
- **New packing strategy:** anything that returns `Sheet`s can be validated
  with `layout_problems()` and rendered unchanged.

## Tests

| File | Covers |
|---|---|
| `test_triangle.py`, `test_tabs.py`, `test_piece.py`, `test_constraints.py` | geometry, glue tabs, validation (property-based) |
| `test_transform.py`, `test_convex.py`, `test_nfp.py` | rigid transforms, convex tools, no-fit polygons |
| `test_layout.py`, `test_packing.py` | single-piece layouts, packing capacity and validity |
| `test_labels.py` | labels stay on glue tabs |
| `test_svg.py`, `test_pdf.py` | output formats, exact physical size (poppler tests skip if not installed) |
| `test_cli.py` | command line |
