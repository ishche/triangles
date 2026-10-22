"""Command line: domeprint AB BC CA --tab 5 -o piece.svg|piece.pdf"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

from .geometry import InvalidTriangleError, TabSpec, Triangle, build_piece
from .layout import (
    PAPER_SIZES_MM,
    Demand,
    DoesNotFitError,
    PackOptions,
    fill_sheet,
    pack,
    single_on_paper,
    tight_sheet,
)
from .render import RenderStyle, render_pdf, render_svg


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="domeprint",
        description="Print-ready SVG or PDF templates (cut + fold lines, glue tabs) for a geodesic dome triangle. "
        "By default, fills one A4 sheet with as many copies as fit.",
    )
    p.add_argument("ab", type=float, help="side AB in mm (base)")
    p.add_argument("bc", type=float, help="side BC in mm")
    p.add_argument("ca", type=float, help="side CA in mm")
    p.add_argument("--tab", type=float, default=5.0, help="glue tab width in mm (default 5, 0 = none)")
    p.add_argument("--max-tab-angle", type=float, default=45.0, help="max angle of tab ends in degrees (default 45)")
    p.add_argument(
        "--no-bisector",
        action="store_true",
        help="do not limit tab end angles to half the corner angle (tabs may collide when folded flat)",
    )
    p.add_argument(
        "--paper",
        default="A4",
        help=f"one of: {', '.join(PAPER_SIZES_MM)} (default A4), or 'tight' for one piece on a page sized to it",
    )
    p.add_argument("--margin", type=float, default=10.0, help="page margin in mm (default 10)")
    p.add_argument(
        "--count",
        type=int,
        help="number of copies, packed onto as few sheets as needed (default: as many as fit on one sheet)",
    )
    p.add_argument("--spacing", type=float, default=2.0, help="min distance between packed pieces, mm (default 2)")
    p.add_argument("--no-labels", action="store_true", help="omit edge labels")
    p.add_argument("--no-calibration", action="store_true", help="omit the calibration ruler")
    p.add_argument("-o", "--output", type=Path, help="output .svg or .pdf file (default: SVG on stdout)")
    p.add_argument(
        "--format", choices=["svg", "pdf"], help="output format (default: from the output file extension, else svg)"
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        triangle = Triangle(args.ab, args.bc, args.ca)
        spec = TabSpec(args.tab, args.max_tab_angle, clamp_to_bisector=not args.no_bisector)
        piece = build_piece(triangle, spec)
        calibration = not args.no_calibration
        if args.count is not None and args.count < 1:
            raise ValueError("--count must be at least 1")
        tight = args.paper.lower() == "tight"
        if tight and args.count not in (None, 1):
            raise ValueError("--paper tight holds a single piece; choose a paper size to print several")
        opts = None if tight else PackOptions(args.paper, args.margin, args.spacing, calibration)
        fill = None
        if tight:
            sheets = [tight_sheet(piece, args.margin, calibration=calibration)]
        elif args.count is None:
            sheets = [fill_sheet(piece, opts)]
        elif args.count == 1:
            sheets = [single_on_paper(piece, args.paper, args.margin, calibration=calibration)]
        else:
            result = pack([Demand(piece, args.count)], opts)
            sheets, fill = list(result.sheets), result.fill_ratio
    except (InvalidTriangleError, DoesNotFitError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    fmt = args.format or ("pdf" if args.output and args.output.suffix.lower() == ".pdf" else "svg")
    style = RenderStyle(show_labels=not args.no_labels)
    written: list[Path] = []
    if fmt == "pdf":
        data = render_pdf(sheets, style)
        if args.output:
            args.output.write_bytes(data)
            written.append(args.output)
        else:
            sys.stdout.buffer.write(data)
    elif len(sheets) == 1:
        data = render_svg(sheets[0], style).encode("utf-8")
        if args.output:
            args.output.write_bytes(data)
            written.append(args.output)
        else:
            sys.stdout.buffer.write(data)
    else:
        if not args.output:
            print("error: SVG on stdout holds only one sheet; use -o file.svg or file.pdf", file=sys.stderr)
            return 2
        for i, sh in enumerate(sheets, start=1):
            path = args.output.with_name(f"{args.output.stem}-{i}{args.output.suffix}")
            path.write_bytes(render_svg(sh, style).encode("utf-8"))
            written.append(path)
    sys.stdout.flush()
    sheet = sheets[0]

    a, b, c = triangle.angles_deg
    info = [
        f"triangle AB={triangle.ab:g} BC={triangle.bc:g} CA={triangle.ca:g} mm",
        f"angles A={a:.4f} B={b:.4f} C={c:.4f} deg; inradius {triangle.inradius:.3f} mm",
        f"sheet {sheet.width:.2f} x {sheet.height:.2f} mm",
    ]
    if not tight and args.count is None:
        info.append(f"{len(sheet.placements)} pieces on 1 sheet (as many as fit)")
    elif fill is not None:
        info.append(f"{args.count} pieces on {len(sheets)} sheets, paper use {fill:.0%} of printable area")
    for tab, edge in zip(piece.tabs, triangle.edges):
        info.append(
            f"tab {edge.name}: ends {math.degrees(tab.start_angle):.2f}/{math.degrees(tab.end_angle):.2f} deg, "
            f"height {tab.height:.3f} mm"
        )
    info += [f"warning: {w}" for w in piece.warnings]
    if written:
        info.append(f"wrote {', '.join(map(str, written))} - print at 100% scale (no 'fit to page')")
    print("\n".join(info), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
