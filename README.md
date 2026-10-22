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

## Web viewer

A live preview in the browser: change the triangle, tabs or sheet and see the
packed sheets immediately, then download the PDF or per-sheet SVG.

The **Dome 3D** tab shows a geodesic dome (1V–12V, any radius, 3/8 to full
sphere) coloured by triangle or strut type, with the exact lengths and how many
of each you need. "Template →" loads a triangle type into the template view.

**Loads** checks the full-size frame: pick a radius in metres, strut material and
section, snow and wind. It shows strut forces per load case, a utilisation check
over all Eurocode combinations and wind directions, and foundation reactions.
The math, sources and limits are in [docs/loads.md](docs/loads.md).

```sh
./dev.sh          # API on :8000 (restarts on Python changes) + Vite on :5173 (hot reload)
```

Open http://localhost:5173. Needs [uv](https://docs.astral.sh/uv/) and Node.js 20+.
Set `API_PORT` / `WEB_PORT` to change ports.

Without the dev server: `npm --prefix web install && npm --prefix web run build`,
then `uv run domeprint-server` serves the built UI and the API on http://127.0.0.1:8000.

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
