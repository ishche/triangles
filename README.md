# domeprint

Print-ready paper templates for geodesic dome triangles.

Give it the three side lengths of a triangle and a glue tab width. It produces
an SVG or PDF at exact physical size, where:
- solid lines are cuts;
- dashed lines are folds.

By default it fills one A4 sheet with as many copies as fit.

```sh
uv sync
uv run domeprint 61.8 54.7 54.7 -o sheet.pdf               # one A4 sheet, as many as fit (18)
uv run domeprint 61.8 54.7 54.7 --count 30 -o sheets.pdf   # exactly 30 copies, as few sheets as needed
uv run domeprint 120 100 100 --count 1 -o piece.pdf        # one piece, centred on A4
uv run domeprint 120 100 100 --paper tight -o piece.svg    # one piece, page sized to it
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
| `--count` | fill one sheet | number of copies, packed onto as few sheets as needed |
| `--spacing` | 2 | minimum gap between packed pieces, mm |
| `--paper` | A4 | `A3`, `A4`, `A5`, `LETTER`, `LEGAL`, or `tight` (one piece, page sized to it) |
| `--margin` | 10 | page margin, mm |
| `--no-labels` | off | no edge labels |
| `--no-calibration` | off | no ruler |
| `-o`, `--format` | SVG to stdout | output file; the format follows the extension (`.pdf` / `.svg`) |

Packing more than one sheet into SVG writes one file per sheet (`name-1.svg`, …).

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
