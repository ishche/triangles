# domeprint

Print-ready paper templates for geodesic dome triangles.

Give it the three side lengths of a triangle and a glue tab width. It produces
an SVG or PDF at exact physical size, where:
- solid lines are cuts;
- dashed lines are folds;
- edge labels are printed on the glue tabs.

Many copies are packed onto as few sheets as possible.

```sh
uv sync
uv run domeprint 120 100 100 --tab 5 -o piece.svg              # one piece, page sized to it
uv run domeprint 120 100 100 --tab 5 --paper A4 -o piece.pdf   # one piece on A4
uv run domeprint 61.8 54.7 54.7 --count 30 -o sheets.pdf        # 30 copies packed on A4 sheets
```

Print at **100% / "Actual size"** and check that the ruler on the sheet
measures exactly 100 mm. See [docs/printing.md](docs/printing.md).

## Options

| Option | Default | Meaning |
|---|---|---|
| `AB BC CA` | (required) | side lengths in mm |
| `--tab` | 5 | glue tab width in mm, measured perpendicular to the edge; 0 = no tabs |
| `--max-tab-angle` | 45 | steepest tab end, degrees from the fold line |
| `--no-bisector` | off | don't limit tab ends to half the corner angle |
| `--count` | 1 | number of copies; more than 1 packs them onto sheets |
| `--spacing` | 2 | minimum gap between packed pieces, mm |
| `--paper` | tight | `tight` (page fits one piece), `A3`, `A4`, `A5`, `LETTER`, `LEGAL` (A4 when packing) |
| `--margin` | 10 | page margin, mm |
| `--no-labels` | off | no edge labels |
| `--no-calibration` | off | no ruler |
| `-o`, `--format` | SVG to stdout | output file; the format follows the extension (`.pdf` / `.svg`) |

Packing more than one sheet into SVG writes one file per sheet (`name-1.svg`, …).

## Python API

```python
from domeprint.geometry import Triangle, TabSpec, build_piece
from domeprint.layout import Demand, PackOptions, pack
from domeprint.render import render_pdf

a = build_piece(Triangle.isosceles(61.8, 54.7), TabSpec(5))
b = build_piece(Triangle.equilateral(61.8), TabSpec(5))
result = pack([Demand(a, 30, "A"), Demand(b, 10, "B")], PackOptions(paper="A4", spacing=2))
open("dome.pdf", "wb").write(render_pdf(result.sheets))
```

## How it works

- [docs/geometry.md](docs/geometry.md): triangle construction, glue tabs and
  corner bevels, validation, labels.
- [docs/layout.md](docs/layout.md): packing algorithm (180° pairing, no-fit
  polygons, per-sheet row planning) and measured efficiency.
- [docs/printing.md](docs/printing.md): printing instructions and how exact
  size is guaranteed and tested.
- [docs/architecture.md](docs/architecture.md): modules, data flow, extension
  points, test map.

## Development

```sh
uv sync                     # Python 3.11+, installs pytest, hypothesis, pypdf, ruff
uv run pytest               # full test suite
uv run ruff check           # lint
uv run ruff format          # format
```

The exact-size tests in `tests/test_pdf.py` also use poppler (`pdfinfo`,
`pdftoppm`). Install it with `brew install poppler` or
`apt install poppler-utils`; without it, those tests are skipped.

## License

MIT. See [LICENSE](LICENSE).
