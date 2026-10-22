# Printing at exact size

## How to print

1. Open the PDF and print at **100% / "Actual size"**. Never use "Fit to page"
   or "Shrink oversized pages". The PDF asks viewers to default to actual
   size (`/PrintScaling /None`), but check the dialog anyway.
2. Measure the ruler at the bottom of each sheet with a real ruler. It must be
   exactly 100 mm (50 mm on small pages), with ticks every 10 mm. If it isn't,
   your printer or driver is scaling the page.
3. Cut along the solid black lines. Fold along the dashed blue lines, which are
   the original triangle edges. Labels are printed on the glue tabs, so they end
   up hidden.

`--no-calibration` removes the ruler.

## How exact size is guaranteed

- **PDF:** each page box is the paper size in points (1 mm = 72/25.4 pt),
  rounded *down* at 1e-6 pt, so a page is never larger than the paper. Rounding
  up even that little makes poppler rasterise A4 at 2101 px instead of 2100 at
  10 px/mm. A single `cm` operator scales the content to millimetres, so all
  coordinates are written in mm at 1 nm resolution.
- **SVG:** `width="210mm"`, with a viewBox in the same numbers (1 unit = 1 mm).

## How it is tested

`tests/test_pdf.py` checks every paper size (A3, A4, A5, Letter, Legal) three
independent ways:
- pypdf parses page sizes and every drawn coordinate, which match the geometry
  to within 2 nm;
- poppler's `pdfinfo` reports the page size;
- poppler's `pdftoppm` rasterises at exactly 10 px/mm. The 100 mm ruler
  measures 1000 px ± 1, and every cut segment lies on its exact position
  ± 0.1 mm.

As a check on the tests themselves, a deliberate 0.2% scale error makes 21 of
them fail. The poppler tests are skipped when poppler isn't installed.
